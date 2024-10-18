"""Main functions for py-gasbuddy."""

from __future__ import annotations

import json
import logging
from typing import Any, Collection

import aiohttp  # type: ignore
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError

from .exceptions import APIError, LibraryError, MissingSearchData
from .consts import BASE_URL, DEFAULT_HEADERS, GAS_PRICE_QUERY, LOCATION_QUERY

ERROR_TIMEOUT = "Timeout while updating"
_LOGGER = logging.getLogger(__name__)


class GasBuddy:
    """Represent GasBuddy GraphQL calls."""

    def __init__(self, station_id: int | None = None) -> None:
        """Connect and request data from GasBuddy."""
        self._url = BASE_URL
        self._id = station_id

    async def process_request(
        self, query: dict[str, Collection[str]]
    ) -> dict[str, Any]:
        """Process API requests."""
        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
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

                    if response.status != 200:
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
                    "cash_price": price["cash"]["price"],
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
