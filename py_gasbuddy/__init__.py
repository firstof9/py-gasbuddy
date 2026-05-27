"""Main functions for py-gasbuddy."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import aiohttp
import backoff
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError

from .cache import GasBuddyCache
from .consts import (
    BASE_URL,
    DEFAULT_HEADERS,
    EV_STATIONS_BOUNDS_QUERY,
    EV_STATIONS_NEARBY_QUERY,
    GAS_PRICE_QUERY,
    GB_HOME_URL,
    LOCATION_QUERY,
    LOCATION_QUERY_PRICES,
    TOKEN,
)
from .exceptions import (
    APIError,
    CloudflareBlocked,
    CSRFTokenMissing,
    LibraryError,
    MissingSearchData,
)
from .models import (
    EvStation as EvStation,
)
from .models import (
    EvStationResult,
    GraphQLQuery,
    LocationSearchResult,
    PriceServiceResult,
    StationPrice,
)
from .models import (
    StationSummary as StationSummary,
)
from .parsers import (
    build_discount_map,
    format_price_node,
    parse_cursor,
    parse_ev_stations,
    parse_location_results,
    parse_results,
    parse_trends,
)

__all__ = [
    "APIError",
    "CSRFTokenMissing",
    "CloudflareBlocked",
    "EvStation",
    "EvStationResult",
    "GasBuddy",
    "GraphQLQuery",
    "LibraryError",
    "LocationSearchResult",
    "MissingSearchData",
    "PriceServiceResult",
    "StationPrice",
    "StationSummary",
]

ERROR_TIMEOUT = "Timeout while updating"
CSRF_TIMEOUT = "Timeout while getting CSRF tokens"
# The sentinel value process_request returns in its error envelope when
# the CSRF token fetch failed (Cloudflare interstitial, no FlareSolverr,
# etc.). Callers can pattern-match this, but the preferred way to detect
# CSRF/Cloudflare blocks is to catch CloudflareBlocked at the public API
# methods (price_lookup, location_search, ev_stations_nearby, ...).
ERROR_MISSING_TOKEN = "Missing Token"  # noqa: S105 - not a secret, error sentinel
MAX_RETRIES = 5
_LOGGER = logging.getLogger(__name__)
CSRF_PATTERN = re.compile(r'window\.gbcsrf\s*=\s*(["])(.*?)\1')


def _raise_library_error(message: Any) -> None:
    """Raise the right library exception for a process_request error.

    Routes the well-known CSRF/Cloudflare sentinel to the dedicated
    ``CloudflareBlocked`` subclass and everything else to the generic
    ``LibraryError`` — both carry ``message`` as the first arg.
    """
    if message == ERROR_MISSING_TOKEN:
        raise CloudflareBlocked(message)
    raise LibraryError(message)


class GasBuddy:
    """Represent GasBuddy GraphQL calls."""

    def __init__(
        self,
        station_id: int | None = None,
        solver_url: str | None = None,
        cache_file: str = "",
        timeout: int = 60000,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize GasBuddy and connect to the GasBuddy API.

        Args:
            station_id: GasBuddy station ID for price lookups.
            solver_url: Optional Cloudflare solver URL.
            cache_file: Path to the CSRF-token cache file.
            timeout: Request timeout in milliseconds.
            session: An optional, caller-owned ``aiohttp.ClientSession``.
                When provided, GasBuddy will reuse this session for all HTTP
                requests and will **not** close or otherwise manage its
                lifecycle; the caller is responsible for closing it.
                When omitted, an ephemeral session is created and closed
                automatically for each request.  See :meth:`_get_session`
                for full lifecycle details.
        """
        self._url = BASE_URL
        self._id = station_id
        self._solver = solver_url
        self._tag = ""
        self._cf_last: bool | None = None
        self._cache_file = cache_file
        self._cache_manager: GasBuddyCache | None = None
        self._timeout = timeout
        self._session = session

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_time=60, max_tries=MAX_RETRIES
    )
    async def process_request(self, query: GraphQLQuery) -> dict[str, Any]:
        """Process API requests."""
        headers = dict(DEFAULT_HEADERS)
        try:
            await self._get_headers()
        except CSRFTokenMissing:
            _LOGGER.error("Skipping request due to missing token.")
            return {"error": ERROR_MISSING_TOKEN}

        headers["gbcsrf"] = self._tag

        async with self._get_session() as session:
            json_query: str = json.dumps(query)
            _LOGGER.debug("URL: %s\nQuery: %s", self._url, json_query)
            request_timeout = aiohttp.ClientTimeout(total=self._timeout / 1000)
            try:
                async with session.post(
                    self._url,
                    data=json_query,
                    headers=headers,
                    timeout=request_timeout,
                ) as response:
                    message: dict[str, Any] | Any = {}
                    try:
                        message = await response.text()
                    except UnicodeDecodeError:
                        _LOGGER.debug("Decoding error.")
                        data = await response.read()
                        message = data.decode(errors="replace")

                    try:
                        message = json.loads(message)
                        self._cf_last = True
                    except ValueError:
                        # Truncate body so Cloudflare interstitial HTML
                        # doesn't dump multi-KB pages to the HA log.
                        truncated = (
                            message
                            if isinstance(message, str) and len(message) <= 500
                            else (
                                f"{message[:500]}... (truncated)"
                                if isinstance(message, str)
                                else message
                            )
                        )
                        _LOGGER.warning("Non-JSON response: %s", truncated)
                        message = {"error": message}
                        self._cf_last = False
                    if response.status == 403:
                        _LOGGER.debug("Retrying request...")
                        self._cf_last = False
                    elif response.status != 200:
                        _LOGGER.error(
                            "An error retrieving data from the server, code: %s\nmessage: %s",  # noqa: E501
                            response.status,
                            message,
                        )
                        message = {"error": message}
                        self._cf_last = False
                    return message

            except (TimeoutError, ServerTimeoutError):
                _LOGGER.error("%s: %s", ERROR_TIMEOUT, self._url)
                message = {"error": ERROR_TIMEOUT}
            except ContentTypeError as err:
                _LOGGER.error("%s", err)
                message = {"error": err}

        return message

    @asynccontextmanager
    async def _get_session(self) -> AsyncIterator[aiohttp.ClientSession]:
        """Yield the active HTTP session, managing its lifecycle.

        Yields the injected session unchanged when one was provided at
        construction time (the caller retains ownership and the session is not
        closed here). Otherwise creates an ephemeral session with default
        headers and closes it on exit.
        """
        if self._session is not None:
            yield self._session
        else:
            session = aiohttp.ClientSession(headers=DEFAULT_HEADERS)
            try:
                yield session
            finally:
                await session.close()

    @staticmethod
    def _validate_coordinates(lat: float, lon: float) -> None:
        """Raise ValueError if lat/lon are outside valid WGS-84 ranges."""
        if not -90 <= lat <= 90:
            raise ValueError(f"lat must be between -90 and 90, got {lat}")
        if not -180 <= lon <= 180:
            raise ValueError(f"lon must be between -180 and 180, got {lon}")

    async def location_search(
        self,
        lat: float | None = None,
        lon: float | None = None,
        zipcode: int | None = None,
        brand_id: int | None = None,
        fuel: int | None = None,
        cursor: str | None = None,
    ) -> LocationSearchResult:
        """Return stations matching a location search.

        Args:
            lat: Latitude (requires lon).
            lon: Longitude (requires lat).
            zipcode: ZIP/postal code to search.
            brand_id: Filter by GasBuddy brand ID (e.g. 38 for Costco).
            fuel: Filter by fuel type integer ID. See FUEL_FILTER_IDS in consts.py
                (e.g. 1=Regular, 2=Midgrade, 3=Premium, 4=Diesel, 5=E85, 12=UNL88).
            cursor: Opaque pagination token from a previous call's ``next_cursor``.
        """
        variables: dict[str, Any] = {}
        if lat is not None and lon is not None:
            self._validate_coordinates(lat, lon)
            variables = {"maxAge": 0, "lat": lat, "lng": lon}
        elif zipcode is not None:
            variables = {"maxAge": 0, "search": str(zipcode)}
        else:
            _LOGGER.error("Missing search data.")
            raise MissingSearchData

        if brand_id is not None:
            variables["brandId"] = brand_id
        if fuel is not None:
            variables["fuel"] = fuel
        if cursor is not None:
            variables["cursor"] = cursor

        query: GraphQLQuery = {
            "operationName": "LocationBySearchTerm",
            "query": LOCATION_QUERY,
            "variables": variables,
        }

        response = await self.process_request(query)
        if "error" in response:
            _LOGGER.error(
                "An error occurred attempting to retrieve the data: %s",
                response["error"],
            )
            return cast(LocationSearchResult, {"results": [], "next_cursor": None})
        if "errors" in response:
            _LOGGER.error(
                "location_search: GraphQL errors returned: %s",
                response["errors"],
            )
            return cast(LocationSearchResult, {"results": [], "next_cursor": None})
        return parse_location_results(response)

    async def price_lookup(self) -> StationPrice:
        """Return gas price of station_id."""
        query: GraphQLQuery = {
            "operationName": "GetStation",
            "query": GAS_PRICE_QUERY,
            "variables": {"id": str(self._id)},
        }

        response = await self.process_request(query)

        _LOGGER.debug("price_lookup response: %s", response)

        if "error" in response.keys():
            message = response["error"]
            _LOGGER.error(
                "An error occurred attempting to retrieve the data: %s",
                message,
            )
            _raise_library_error(message)
        if "errors" in response.keys():
            try:
                message = response["errors"]["message"]
            except (ValueError, TypeError):
                try:
                    message = response["errors"][0]["message"]
                except (IndexError, ValueError, TypeError):
                    message = "Server side error occurred."
            _LOGGER.error(
                "An error occurred attempting to retrieve the data: %s",
                message,
            )
            raise APIError

        station = response.get("data", {}).get("station")
        if not station:
            _LOGGER.error("price_lookup: station payload missing or null in response")
            raise APIError
        raw: dict[str, Any] = {
            "station_id": station["id"],
            "name": station.get("name") or "",
            "unit_of_measure": station["priceUnit"],
            "currency": station["currency"],
            "latitude": station["latitude"],
            "longitude": station["longitude"],
            "image_url": station["brands"][0]["imageUrl"]
            if station.get("brands")
            else None,
            "address": station.get("address") or {},
            "brands": station.get("brands") or [],
            "amenities": station.get("amenities") or [],
            "hours": station.get("hours"),
            "phone": station.get("phone") or None,
            "open_status": station.get("openStatus"),
            "fuels": station.get("fuels") or [],
            "star_rating": station.get("starRating"),
            "ratings_count": station.get("ratingsCount"),
            "is_fuelman_site": bool(station.get("isFuelmanSite", False)),
            "has_active_outage": bool(station.get("hasActiveOutage", False)),
            "enterprise": bool(station.get("enterprise", False)),
            "emergency_status": station.get("emergencyStatus"),
            "offers": station.get("offers") or [],
        }

        pay_status_obj = station.get("payStatus")
        raw["pay_status"] = (pay_status_obj is None) or bool(
            (pay_status_obj or {}).get("isPayAvailable", False)
        )

        _LOGGER.debug("pre-price data: %s", raw)

        discount_map = (
            build_discount_map(station.get("offers") or []) if raw["pay_status"] else {}
        )
        for price in station.get("prices") or []:
            fuel_key = price["fuelProduct"]
            raw[fuel_key] = format_price_node(price, discount_map.get(fuel_key))

        _LOGGER.debug("final data: %s", raw)

        return cast(StationPrice, raw)

    async def price_lookup_service(
        self,
        lat: float | None = None,
        lon: float | None = None,
        zipcode: int | None = None,
        limit: int = 5,
        brand_id: int | None = None,
        fuel: int | None = None,
        cursor: str | None = None,
    ) -> PriceServiceResult:
        """Return gas prices for stations near a location.

        Args:
            lat: Latitude (requires lon).
            lon: Longitude (requires lat).
            zipcode: ZIP/postal code to search.
            limit: Maximum number of stations to return (client-side slice).
            brand_id: Filter by GasBuddy brand ID (e.g. 38 for Costco).
            fuel: Filter by fuel type integer ID. See FUEL_FILTER_IDS in consts.py
                (e.g. 1=Regular, 2=Midgrade, 3=Premium, 4=Diesel, 5=E85, 12=UNL88).
            cursor: Opaque pagination token from a previous call's ``next_cursor``.
        """
        variables: dict[str, Any] = {}
        if lat is not None and lon is not None:
            self._validate_coordinates(lat, lon)
            variables = {"maxAge": 0, "lat": lat, "lng": lon}
        elif zipcode is not None:
            variables = {"maxAge": 0, "search": str(zipcode)}
        else:
            _LOGGER.error("Missing search data.")
            raise MissingSearchData

        if brand_id is not None:
            variables["brandId"] = brand_id
        if fuel is not None:
            variables["fuel"] = fuel
        if cursor is not None:
            variables["cursor"] = cursor

        query: GraphQLQuery = {
            "operationName": "LocationBySearchTerm",
            "query": LOCATION_QUERY_PRICES,
            "variables": variables,
        }

        response = await self.process_request(query)

        _LOGGER.debug("price_lookup_service response: %s", response)

        if "error" in response.keys():
            message = response["error"]
            _LOGGER.error(
                "An error occurred attempting to retrieve the data: %s",
                message,
            )
            _raise_library_error(message)
        if "errors" in response.keys():
            try:
                message = response["errors"]["message"]
            except (ValueError, TypeError):
                try:
                    message = response["errors"][0]["message"]
                except (IndexError, ValueError, TypeError):
                    message = "Server side error occurred."
            _LOGGER.error(
                "An error occurred attempting to retrieve the data: %s",
                message,
            )
            raise APIError

        result_list = parse_results(response, limit)
        _LOGGER.debug("result data: %s", result_list)

        result: PriceServiceResult = {"results": result_list}
        trend_data = parse_trends(response)
        if trend_data:
            result["trend"] = trend_data
            _LOGGER.debug("trend data: %s", trend_data)
        next_cursor = parse_cursor(response)
        if next_cursor:
            result["next_cursor"] = next_cursor
        return result

    async def ev_stations_nearby(
        self,
        lat: float,
        lon: float,
        radius: float = 25,
        networks: str | None = None,
        connector_types: str | None = None,
        charging_levels: str | None = None,
        cards_accepted: str | None = None,
        access_code: str = "public",
        limit: int = 50,
    ) -> EvStationResult:
        """Return EV charging stations within ``radius`` miles of a coordinate.

        Args:
            lat: Latitude of the search centre.
            lon: Longitude of the search centre.
            radius: Search radius in miles (default 25).
            networks: Comma-separated network names; defaults to all known networks.
            connector_types: Comma-separated connector types (default all).
            charging_levels: Comma-separated charging levels (default all).
            cards_accepted: Comma-separated payment cards required (e.g.
                ``"A,V,M,D"`` for AmEx/Visa/MC/Discover); defaults to no filter.
            access_code: ``"public"`` or ``"private"`` (default ``"public"``).
            limit: Maximum stations to return (default 50).
        """
        self._validate_coordinates(lat, lon)
        variables: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "radius": radius,
            "accessCode": access_code,
            "limit": limit,
        }
        if networks is not None:
            variables["networks"] = networks
        if connector_types is not None:
            variables["connectorTypes"] = connector_types
        if charging_levels is not None:
            variables["chargingLevels"] = charging_levels
        if cards_accepted is not None:
            variables["cardsAccepted"] = cards_accepted

        query: GraphQLQuery = {
            "operationName": "EvStationsSearch",
            "query": EV_STATIONS_NEARBY_QUERY,
            "variables": variables,
        }
        response = await self.process_request(query)
        _LOGGER.debug("ev_stations_nearby response: %s", response)
        if "error" in response:
            _LOGGER.error(
                "An error occurred attempting to retrieve EV station data: %s",
                response["error"],
            )
            _raise_library_error(response["error"])
        if "errors" in response:
            try:
                message = response["errors"][0]["message"]
            except (IndexError, KeyError, TypeError):
                message = "Server side error occurred."
            _LOGGER.error(
                "An error occurred attempting to retrieve EV station data: %s",
                message,
            )
            raise APIError
        ev_data = response["data"]["evStationsNearby"]
        return {
            "stations": parse_ev_stations(ev_data["stations"] or []),
            "total": ev_data["total"],
        }

    async def ev_stations_by_bounds(
        self,
        ne_lat: float,
        ne_lng: float,
        sw_lat: float,
        sw_lng: float,
        networks: str | None = None,
        connector_types: str | None = None,
        charging_levels: str | None = None,
        cards_accepted: str | None = None,
        access_code: str = "public",
        limit: int = 200,
    ) -> EvStationResult:
        """Return EV charging stations within a bounding box.

        Args:
            ne_lat: North-east corner latitude.
            ne_lng: North-east corner longitude.
            sw_lat: South-west corner latitude.
            sw_lng: South-west corner longitude.
            networks: Comma-separated network names; defaults to all known networks.
            connector_types: Comma-separated connector types (default all).
            charging_levels: Comma-separated charging levels (default all).
            cards_accepted: Comma-separated payment cards required (e.g.
                ``"A,V,M,D"`` for AmEx/Visa/MC/Discover); defaults to no filter.
            access_code: ``"public"`` or ``"private"`` (default ``"public"``).
            limit: Maximum stations to return (default 200).
        """
        self._validate_coordinates(ne_lat, ne_lng)
        self._validate_coordinates(sw_lat, sw_lng)
        variables: dict[str, Any] = {
            "northEastLat": ne_lat,
            "northEastLng": ne_lng,
            "southWestLat": sw_lat,
            "southWestLng": sw_lng,
            "accessCode": access_code,
            "limit": limit,
        }
        if networks is not None:
            variables["networks"] = networks
        if connector_types is not None:
            variables["connectorTypes"] = connector_types
        if charging_levels is not None:
            variables["chargingLevels"] = charging_levels
        if cards_accepted is not None:
            variables["cardsAccepted"] = cards_accepted

        query: GraphQLQuery = {
            "operationName": "EvStationsByBounds",
            "query": EV_STATIONS_BOUNDS_QUERY,
            "variables": variables,
        }
        response = await self.process_request(query)
        _LOGGER.debug("ev_stations_by_bounds response: %s", response)
        if "error" in response:
            _LOGGER.error(
                "An error occurred attempting to retrieve EV station data: %s",
                response["error"],
            )
            _raise_library_error(response["error"])
        if "errors" in response:
            try:
                message = response["errors"][0]["message"]
            except (IndexError, KeyError, TypeError):
                message = "Server side error occurred."
            _LOGGER.error(
                "An error occurred attempting to retrieve EV station data: %s",
                message,
            )
            raise APIError
        ev_data = response["data"]["evStationsByBounds"]
        return {
            "stations": parse_ev_stations(ev_data["stations"] or []),
            "total": ev_data["total"],
        }

    @backoff.on_exception(backoff.expo, aiohttp.ClientError, max_tries=MAX_RETRIES)
    async def _get_headers(self) -> None:
        """Get required headers."""
        url = GB_HOME_URL
        method = "get"
        json_data: Any = {}

        if self._cache_manager is None:
            if self._cache_file:
                self._cache_manager = GasBuddyCache(self._cache_file)
            else:
                self._cache_manager = GasBuddyCache()

        if await self._cache_manager.cache_exists():
            _LOGGER.debug("Found cache file, reading...")
            cache_data = await self._cache_manager.read_cache()
            if isinstance(cache_data, dict) and TOKEN in cache_data:
                self._tag = cache_data[TOKEN]
            else:
                # Cache existed but didn't contain a usable token (corrupt
                # file, partial write, schema drift). Force a refresh so we
                # don't POST with an empty CSRF header — that would 403.
                self._tag = ""
                self._cf_last = False
        else:
            _LOGGER.debug("No cache file found, creating...")
            self._cf_last = False

        if self._solver:
            json_data["cmd"] = "request.get"
            json_data["url"] = url
            json_data["maxTimeout"] = self._timeout
            url = self._solver
            method = "post"

        if self._cf_last is None or self._cf_last:
            return

        _LOGGER.debug("Token invalid, getting a new one...")

        csrf_timeout = aiohttp.ClientTimeout(total=self._timeout / 1000)
        async with self._get_session() as session:
            http_method = getattr(session, method)
            _LOGGER.debug("Calling %s with data: %s", url, json_data)
            try:
                async with http_method(
                    url,
                    json=json_data,
                    headers=DEFAULT_HEADERS,
                    timeout=csrf_timeout,
                ) as response:
                    message: str = ""
                    message = await response.text()
                    if response.status != 200:
                        _LOGGER.error(
                            "An error retrieving data from the server, code: %s\nmessage: %s",  # noqa: E501
                            response.status,
                            message,
                        )
                        # Raise so callers know the token wasn't refreshed,
                        # rather than silently proceeding to POST with an
                        # empty/stale token (which would 403).
                        raise CSRFTokenMissing

                    if self._solver:
                        message = json.loads(message)["solution"]["response"]

                    found = CSRF_PATTERN.search(message)
                    if found is not None:
                        data: dict[str, str] = {}
                        self._tag = found.group(2)
                        data[TOKEN] = self._tag
                        encoded = json.dumps(data).encode("utf-8")
                        _LOGGER.debug("CSRF token found: %s", self._tag)
                        await self._cache_manager.write_cache(encoded)
                    else:
                        _LOGGER.error("CSRF token not found.")
                        raise CSRFTokenMissing

            except (TimeoutError, ServerTimeoutError):
                _LOGGER.error("%s: %s", CSRF_TIMEOUT, url)

    async def clear_cache(self) -> None:
        """Clear cache file."""
        if self._cache_manager is None:
            if self._cache_file:
                self._cache_manager = GasBuddyCache(self._cache_file)
            else:
                self._cache_manager = GasBuddyCache()
        await self._cache_manager.clear_cache()
