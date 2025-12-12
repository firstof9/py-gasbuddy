"""Main functions for py-gasbuddy."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Collection

import aiohttp
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
import backoff

from .cache import GasBuddyCache
from .consts import (
    BASE_URL,
    DEFAULT_HEADERS,
    GAS_PRICE_QUERY,
    GB_HOME_URL,
    LOCATION_QUERY,
    LOCATION_QUERY_PRICES,
    TOKEN,
)
from .exceptions import APIError, CSRFTokenMissing, LibraryError, MissingSearchData

ERROR_TIMEOUT = "Timeout while updating"
CSRF_TIMEOUT = "Timeout wile getting CSRF tokens"
MAX_RETRIES = 5
_LOGGER = logging.getLogger(__name__)
CSRF_PATTERN = re.compile(r'window\.gbcsrf\s*=\s*(["])(.*?)\1')


class GasBuddy:
    """Represent GasBuddy GraphQL calls."""

    def __init__(
        self,
        station_id: int | None = None,
        solver_url: str | None = None,
        cache_file: str = "",
        timeout: int = 60000,
    ) -> None:
        """Connect and request data from GasBuddy."""
        self._url = BASE_URL
        self._id = station_id
        self._solver = solver_url
        self._tag = ""
        self._cf_last: bool | None = None
        self._cache_file = cache_file
        self._cache_manager: GasBuddyCache | None = None
        self._timeout = timeout

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_time=60, max_tries=MAX_RETRIES
    )
    async def process_request(
        self, query: dict[str, Collection[str]]
    ) -> dict[str, Any]:
        """Process API requests."""
        headers = DEFAULT_HEADERS
        try:
            await self._get_headers()
        except CSRFTokenMissing:
            _LOGGER.error("Skipping request due to missing token.")
            return {"error": "Missing Token"}

        headers["gbcsrf"] = self._tag

        async with aiohttp.ClientSession(headers=headers) as session:
            json_query: str = json.dumps(query)
            _LOGGER.debug("URL: %s\nQuery: %s", self._url, json_query)
            try:
                async with session.post(self._url, data=json_query) as response:
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
                        _LOGGER.warning("Non-JSON response: %s", message)
                        message = {"error": message}
                        self._cf_last = False
                    if response.status == 403:
                        _LOGGER.debug("Retrying request...")
                        self._cf_last = False
                    elif response.status != 200:
                        _LOGGER.error(  # pylint: disable-next=line-too-long
                            "An error reteiving data from the server, code: %s\nmessage: %s",  # noqa: E501
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

            await session.close()
            return message

    async def location_search(
        self,
        lat: float | None = None,
        lon: float | None = None,
        zipcode: int | None = None,
    ) -> dict[str, str] | dict[str, Any]:
        """Return result of location search."""
        variables: dict[str, Any] = {}
        if lat is not None and lon is not None:
            variables = {"maxAge": 0, "lat": lat, "lng": lon}
        elif zipcode is not None:
            variables = {"maxAge": 0, "search": str(zipcode)}
        else:
            _LOGGER.error("Missing search data.")
            raise MissingSearchData

        query = {
            "operationName": "LocationBySearchTerm",
            "query": LOCATION_QUERY,
            "variables": variables,
        }

        return await self.process_request(query)

    async def price_lookup(self) -> dict[str, Any] | None:
        """Return gas price of station_id."""
        query = {
            "operationName": "GetStation",
            "query": GAS_PRICE_QUERY,
            "variables": {"id": str(self._id)},
        }

        # Parse and format data into easy to use dict
        response = await self.process_request(query)

        _LOGGER.debug("price_lookup response: %s", response)

        if "error" in response.keys():
            message = response["error"]
            _LOGGER.error(
                "An error occured attempting to retrieve the data: %s",
                message,
            )
            raise LibraryError
        if "errors" in response.keys():
            try:
                message = response["errors"]["message"]
            except (ValueError, TypeError):
                try:
                    message = response["errors"][0]["message"]
                except (IndexError, ValueError, TypeError):
                    message = "Server side error occured."
            _LOGGER.error(
                "An error occured attempting to retrieve the data: %s",
                message,
            )
            raise APIError

        data = {}

        data["station_id"] = response["data"]["station"]["id"]
        data["unit_of_measure"] = response["data"]["station"]["priceUnit"]
        data["currency"] = response["data"]["station"]["currency"]
        data["latitude"] = response["data"]["station"]["latitude"]
        data["longitude"] = response["data"]["station"]["longitude"]
        data["image_url"] = None

        if len(response["data"]["station"]["brands"]) > 0:
            data["image_url"] = response["data"]["station"]["brands"][0]["imageUrl"]

        _LOGGER.debug("pre-price data: %s", data)

        prices = response["data"]["station"]["prices"]
        for price in prices:
            index = price["fuelProduct"]
            data[index] = self._format_price_node(price)

        _LOGGER.debug("final data: %s", data)

        return data

    async def price_lookup_service(
        self,
        lat: float | None = None,
        lon: float | None = None,
        zipcode: int | None = None,
        limit: int = 5,
    ) -> dict[str, Any] | None:
        """Return gas price of station_id."""
        variables: dict[str, Any] = {}
        if lat is not None and lon is not None:
            variables = {"maxAge": 0, "lat": lat, "lng": lon}
        elif zipcode is not None:
            variables = {"maxAge": 0, "search": str(zipcode)}
        query = {
            "operationName": "LocationBySearchTerm",
            "query": LOCATION_QUERY_PRICES,
            "variables": variables,
        }

        # Parse and format data into easy to use dict
        response = await self.process_request(query)

        _LOGGER.debug("price_lookup_service response: %s", response)

        if "error" in response.keys():
            message = response["error"]
            _LOGGER.error(
                "An error occured attempting to retrieve the data: %s",
                message,
            )
            raise LibraryError
        if "errors" in response.keys():
            message = response["errors"]["message"]
            _LOGGER.error(
                "An error occured attempting to retrieve the data: %s",
                message,
            )
            raise APIError

        result_list = await self._parse_results(response, limit)
        _LOGGER.debug("result data: %s", result_list)
        value: dict[Any, Any] = {}
        value["results"] = result_list
        trend_data = await self._parse_trends(response)
        if trend_data:
            value["trend"] = trend_data
            _LOGGER.debug("trend data: %s", trend_data)
        return value

    async def _parse_trends(self, response: dict) -> list | None:
        """Parse API results and return trend dict."""
        trend_data: list = []
        for trend in response["data"]["locationBySearchTerm"]["trends"]:
            current_trend: dict[str, Any] = {}
            current_trend["average_price"] = trend["today"]
            current_trend["lowest_price"] = trend["todayLow"]
            current_trend["area"] = trend["areaName"]
            trend_data.append(current_trend)
        return trend_data

    async def _parse_results(self, response: dict, limit: int) -> list:
        """Parse API results and return price data list."""
        result_list = []
        results = response["data"]["locationBySearchTerm"]["stations"]["results"]

        for result in results[:limit]:
            price_data = {}
            price_data["station_id"] = result["id"]
            price_data["unit_of_measure"] = result["priceUnit"]
            price_data["currency"] = result["currency"]
            price_data["latitude"] = result["latitude"]
            price_data["longitude"] = result["longitude"]

            for price in result["prices"]:
                index = price["fuelProduct"]
                price_data[index] = self._format_price_node(price)
            result_list.append(price_data)
        return result_list

    @backoff.on_exception(backoff.expo, aiohttp.ClientError, max_tries=MAX_RETRIES)
    async def _get_headers(self) -> None:
        """Get required headers."""
        url = GB_HOME_URL
        method = "get"
        json_data: Any = {}

        if self._cache_file and self._cache_manager is None:
            self._cache_manager = GasBuddyCache(self._cache_file)
        else:
            self._cache_manager = GasBuddyCache()

        if await self._cache_manager.cache_exists():
            _LOGGER.debug("Found cache file, reading...")
            cache_data = await self._cache_manager.read_cache()
            if isinstance(cache_data, dict) and TOKEN in cache_data:
                self._tag = cache_data[TOKEN]
            else:
                self._tag = ""
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

        async with aiohttp.ClientSession() as session:
            http_method = getattr(session, method)
            _LOGGER.debug("Calling %s with data: %s", url, json_data)
            try:
                async with http_method(url, json=json_data) as response:
                    message: str = ""
                    message = await response.text()
                    if response.status != 200:
                        _LOGGER.error(  # pylint: disable-next=line-too-long
                            "An error reteiving data from the server, code: %s\nmessage: %s",  # noqa: E501
                            response.status,
                            message,
                        )
                        return

                    # If we're using the solver parse the JSON response
                    if self._solver:
                        message = json.loads(message)["solution"]["response"]

                    found = CSRF_PATTERN.search(message)
                    if found is not None:
                        data = {}
                        self._tag = found.group(2)
                        data[TOKEN] = self._tag
                        json_data = json.dumps(data).encode("utf-8")
                        _LOGGER.debug("CSRF token found: %s", self._tag)
                        await self._cache_manager.write_cache(json_data)
                    else:
                        _LOGGER.error("CSRF token not found.")
                        raise CSRFTokenMissing

            except (TimeoutError, ServerTimeoutError):
                _LOGGER.error("%s: %s", CSRF_TIMEOUT, url)
            await session.close()

    async def clear_cache(self) -> None:
        """Clear cache file."""
        if self._cache_manager:
            await self._cache_manager.clear_cache()

    def _format_price_node(self, price_node: dict) -> dict:
        """Format a single price node."""
        # Use 'or {}' to handle cases where the key exists but the value is None
        credit_data = price_node.get("credit") or {}
        cash_data = price_node.get("cash") or {}

        # Safe extraction helpers
        credit_price = credit_data.get("price", 0)
        cash_price = cash_data.get("price", 0)

        return {
            "credit": credit_data.get("nickname"),
            "cash_price": None if cash_price == 0 else cash_price,
            "price": None if credit_price == 0 else credit_price,
            "last_updated": credit_data.get("postedTime"),
        }
