"""Main functions for py-gasbuddy."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Collection

import aiohttp  # type: ignore
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
import backoff

from .consts import (
    BASE_URL,
    DEFAULT_HEADERS,
    GAS_PRICE_QUERY,
    LOCATION_QUERY,
    LOCATION_QUERY_PRICES,
)
from .exceptions import APIError, CSRFTokenMissing, LibraryError, MissingSearchData

ERROR_TIMEOUT = "Timeout while updating"
CSRF_TIMEOUT = "Timeout wile getting CSRF tokens"
MAX_RETRIES = 5
_LOGGER = logging.getLogger(__name__)


class GasBuddy:
    """Represent GasBuddy GraphQL calls."""

    def __init__(self, station_id: int | None = None) -> None:
        """Connect and request data from GasBuddy."""
        self._url = BASE_URL
        self._id = station_id
        self._tag = ""

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_time=60, max_tries=MAX_RETRIES
    )
    async def process_request(
        self, query: dict[str, Collection[str]]
    ) -> dict[str, Any]:
        """Process API requests."""
        headers = DEFAULT_HEADERS
        await self._get_headers()
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
                    except ValueError:
                        _LOGGER.warning("Non-JSON response: %s", message)
                        message = {"error": message}
                    if response.status == 403:
                        _LOGGER.debug("Retrying request...")
                    elif response.status != 200:
                        _LOGGER.error(  # pylint: disable-next=line-too-long
                            "An error reteiving data from the server, code: %s\nmessage: %s",  # noqa: E501
                            response.status,
                            message,
                        )
                        message = {"error": message}
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
            message = response["errors"]["message"]
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
            if price["cash"]:
                data[index] = {
                    "credit": price["credit"]["nickname"],
                    "cash_price": (
                        None
                        if price.get("cash", {}).get("price", 0) == 0
                        else price["cash"]["price"]
                    ),
                    "price": (
                        None
                        if price.get("credit", {}).get("price", 0) == 0
                        else price["credit"]["price"]
                    ),
                    "last_updated": price["credit"]["postedTime"],
                }
            else:
                data[index] = {
                    "credit": price["credit"]["nickname"],
                    "price": (
                        None
                        if price.get("credit", {}).get("price", 0) == 0
                        else price["credit"]["price"]
                    ),
                    "last_updated": price["credit"]["postedTime"],
                }

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

    async def _parse_trends(self, response: dict) -> dict | None:
        """Parse API results and return trend dict."""
        trend_data: dict[str, Any] = {}
        if response["data"]["locationBySearchTerm"]["trends"][0]:
            result = response["data"]["locationBySearchTerm"]["trends"][0]
            trend_data["average_price"] = result["today"]
            trend_data["lowest_price"] = result["todayLow"]
            trend_data["area"] = result["areaName"]
        return trend_data

    async def _parse_results(self, response: dict, limit: int) -> list:
        """Parse API results and return price data list."""
        result_list = []
        for result in response["data"]["locationBySearchTerm"]["stations"]["results"]:
            if limit <= 0:
                break
            limit -= 1
            # parse the prices
            price_data = {}
            price_data["station_id"] = result["id"]
            price_data["unit_of_measure"] = result["priceUnit"]
            price_data["currency"] = result["currency"]
            price_data["latitude"] = result["latitude"]
            price_data["longitude"] = result["longitude"]

            for price in result["prices"]:
                index = price["fuelProduct"]
                if price["cash"]:
                    price_data[index] = {
                        "credit": price["credit"]["nickname"],
                        "cash_price": (
                            None
                            if price.get("cash", {}).get("price", 0) == 0
                            else price["cash"]["price"]
                        ),
                        "price": (
                            None
                            if price.get("credit", {}).get("price", 0) == 0
                            else price["credit"]["price"]
                        ),
                        "last_updated": price["credit"]["postedTime"],
                    }
                else:
                    price_data[index] = {
                        "credit": price["credit"]["nickname"],
                        "price": (
                            None
                            if price.get("credit", {}).get("price", 0) == 0
                            else price["credit"]["price"]
                        ),
                        "last_updated": price["credit"]["postedTime"],
                    }
            result_list.append(price_data)
        return result_list

    @backoff.on_exception(
        backoff.expo, aiohttp.ClientError, max_time=60, max_tries=MAX_RETRIES
    )
    async def _get_headers(self) -> None:
        """Get required headers."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
            "apollo-require-preflight": "true",
            "Origin": "https://www.gasbuddy.com",
            "Referer": "https://www.gasbuddy.com/home",
        }
        url = "https://www.gasbuddy.com/home"

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url) as response:
                    message: str = ""
                    message = await response.text()
                    if response.status != 200:
                        _LOGGER.error(  # pylint: disable-next=line-too-long
                            "An error reteiving data from the server, code: %s\nmessage: %s",  # noqa: E501
                            response.status,
                            message,
                        )
                        return

                    pattern = re.compile(r'window\.gbcsrf\s*=\s*(["])(.*?)\1')
                    found = pattern.search(message)
                    if found is not None:
                        self._tag = found.group(2)
                        _LOGGER.debug("CSRF token found: %s", self._tag)
                    else:
                        _LOGGER.error("CSRF token not found.")
                        raise CSRFTokenMissing

            except (TimeoutError, ServerTimeoutError):
                _LOGGER.error("%s: %s", CSRF_TIMEOUT, url)
            await session.close()
