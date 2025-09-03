""" Cache functions for py-gasbuddy."""

import json
import logging
from os.path import dirname, exists, join, split
from typing import Any

import aiofiles
import aiofiles.os

_LOGGER = logging.getLogger(__name__)


class GasBuddyCache:
    """Represent py-gasbuddy Cache manager."""

    def __init__(self, cache_file: str = "") -> None:
        """Initialize."""
        if not cache_file:
            cache_file = join(dirname(__file__), "gasbuddy_cache")
        self._cache_file = cache_file
        self._directory, self._filename = split(cache_file)

    async def write_cache(self, data: Any) -> None:
        """Write cache file."""
        if self._directory != "" and not exists(self._directory):
            _LOGGER.debug("Directory missing creating: %s", self._directory)
            await aiofiles.os.makedirs(self._directory)
        async with aiofiles.open(self._cache_file, mode="wb") as file:
            _LOGGER.debug("Writing file: %s", self._cache_file)
            await file.write(data)

    async def read_cache(self) -> Any:
        """Read cache file."""
        _LOGGER.debug("Attempting to read file: %s", self._cache_file)
        if exists(self._cache_file):
            async with aiofiles.open(self._cache_file, mode="r") as file:
                _LOGGER.debug("Reading file: %s", self._cache_file)
                value = await file.read()

                try:
                    verify = json.loads(value)
                    return verify
                except json.decoder.JSONDecodeError:
                    _LOGGER.info("Invalid JSON data")
                return {}
        return {}

    async def cache_exists(self) -> bool:
        """Return bool if cache exists and contains data."""
        check = await aiofiles.os.path.isfile(self._cache_file)
        _LOGGER.debug("Cache file exists? %s", check)
        if check:
            size = await aiofiles.os.path.getsize(self._cache_file)
            _LOGGER.debug("Checking cache file size: %s", size)
            return size > 194
        return False

    async def clear_cache(self) -> None:
        """Remove cache file."""
        if await self.cache_exists():
            await aiofiles.os.remove(self._cache_file)
