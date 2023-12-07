"""Main functions for py-gasbuddy."""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp  # type: ignore
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError

from .consts import BASE_URL, DEFAULT_HEADERS, GAS_PRICE_QUERY, LOCATION_QUERY

ERROR_TIMEOUT = "Timeout while updating"
_LOGGER = logging.getLogger(__name__)

class GasBuddy:
    """Represent GasBuddy GraphQL calls."""

    def __init__(self, station_id: int) -> None:
        """Connect and request data from GasBuddy."""
        self._url = BASE_URL
        self._id = station_id

    async def process_request(self, query: str) -> dict[str, str] | dict[str, Any]:
        """Process API requests."""
        async with aiohttp.ClientSession(haders=DEFAULT_HEADERS) as session:
            try:
                async with session(self._url,data=query).post as response:
                    try:
                        message = await response.text()
                    except UnicodeDecodeError:
                        _LOGGER.debug("Decoding error.")
                        message = await response.read()
                        message = message.decode(errors="replace")

                    try:
                        message = json.loads(message)
                    except ValueError:
                        _LOGGER.warning("Non-JSON response: %s", message)
                    
                    if response.status != 200:
                        _LOGGER.error("An error reteiving data from the server, code: %s\nmessage: %s", response.status, message)

                    return message
            except (TimeoutError, ServerTimeoutError):
                _LOGGER.error("%s: %s", ERROR_TIMEOUT, self._url)
            
            await session.close()
            return message

    async def location_search(self, zip: int) -> dict[str, str] | dict[str, Any]:
        """Return result of location search."""
        query = {"operationName": "LocationBySearchTerm", 'query': LOCATION_QUERY, 'variables': {'fuel': 1, 'maxAge': 0, 'search': str(zip)}}

        return await self.process_request(query)
    
    async def price_lookup(self) -> dict[str, str] | dict[str, Any]:
        """Return gas price of station_id."""

        query = {"operationName": "GetStation", "query": GAS_PRICE_QUERY, "variables": {"id": str(self._id)}}
        
        return await self.process_request(query)
