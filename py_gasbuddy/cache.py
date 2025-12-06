"""Cache functions for py-gasbuddy."""

import json
import logging
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os

_LOGGER = logging.getLogger(__name__)


class GasBuddyCache:
    """Class for GasBuddy file cache."""

    def __init__(self, cache_file: str = "") -> None:
        """Initialize."""
        if not cache_file:
            # Use Path to get current file's directory
            self._cache_file = Path(__file__).parent / "gasbuddy_cache"
        else:
            self._cache_file = Path(cache_file)

    async def write_cache(self, data: Any) -> None:
        """Write cache file."""
        # Create parent directories if they don't exist
        if not await aiofiles.os.path.exists(self._cache_file.parent):
            await aiofiles.os.makedirs(self._cache_file.parent)

        async with aiofiles.open(self._cache_file, mode="wb") as file:
            await file.write(data)

    async def read_cache(self) -> Any:
        """Read cache file."""
        if await aiofiles.os.path.exists(self._cache_file):
            _LOGGER.debug("Attempting to read file: %s", self._cache_file)
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
            return bool(size > 30)
        return False

    async def clear_cache(self) -> None:
        """Remove cache file."""
        if await self.cache_exists():
            await aiofiles.os.remove(self._cache_file)
