"""Main functions for py-gasbuddy."""
from __future__ import annotations

import json
import logging
from typing import Any, Collection

import aiohttp  # type: ignore
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError

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
    ) -> dict[str, str] | dict[str, Any]:
        """Process API requests."""
        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
            try:
                async with session.post(self._url, data=query) as response:
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
                message = {"msg": ERROR_TIMEOUT}
            except ContentTypeError as err:
                _LOGGER.error("%s", err)
                message = {"msg": err}

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

    async def price_lookup(self) -> dict[str, str] | dict[str, Any]:
        """Return gas price of station_id."""
        query = {
            "operationName": "GetStation",
            "query": GAS_PRICE_QUERY,
            "variables": {"id": str(self._id)},
        }

        return await self.process_request(query)


class MissingSearchData(Exception):
    """Exception for missing search data variable."""
