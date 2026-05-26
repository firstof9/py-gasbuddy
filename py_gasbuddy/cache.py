"""Cache functions for py-gasbuddy."""

import asyncio
import json
import logging
import os
import uuid
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
            self._cache_file = Path.home() / ".cache" / "py_gasbuddy" / "token"
        else:
            self._cache_file = Path(cache_file)
        # Serialise cache mutations within a single process. The HA
        # coordinator + a parallel service call could otherwise race
        # both reading and writing the same token file.
        self._lock = asyncio.Lock()

    async def write_cache(self, data: Any) -> None:
        """Atomically write the cache file.

        Writes to a uniquely-named sibling tempfile and ``os.replace``s
        onto the final path, so concurrent writers can't produce a torn
        file. The asyncio lock further serialises in-process writers.
        """
        async with self._lock:
            # Create parent directories if they don't exist
            if not await aiofiles.os.path.exists(self._cache_file.parent):
                await aiofiles.os.makedirs(self._cache_file.parent)

            tmp_path = self._cache_file.with_name(
                f".{self._cache_file.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
            )
            try:
                async with aiofiles.open(tmp_path, mode="wb") as file:
                    await file.write(data)
                # os.replace is atomic on POSIX and Windows ≥Vista.
                await aiofiles.os.replace(tmp_path, self._cache_file)
            except Exception:
                # Best-effort cleanup of the tempfile on failure.
                try:
                    await aiofiles.os.remove(tmp_path)
                except OSError:
                    pass
                raise

    async def read_cache(self) -> Any:
        """Read cache file."""
        if await aiofiles.os.path.exists(self._cache_file):
            _LOGGER.debug("Attempting to read file: %s", self._cache_file)
            async with aiofiles.open(self._cache_file) as file:
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
        """Return True if cache file holds a valid token payload."""
        check = await aiofiles.os.path.isfile(self._cache_file)
        _LOGGER.debug("Cache file exists? %s", check)
        if not check:
            return False
        try:
            async with aiofiles.open(self._cache_file) as file:
                contents = await file.read()
            data = json.loads(contents)
        except (OSError, json.JSONDecodeError):
            _LOGGER.debug("Cache file unreadable or not valid JSON")
            return False
        return isinstance(data, dict) and bool(data.get("token"))

    async def clear_cache(self) -> None:
        """Remove cache file."""
        if await aiofiles.os.path.exists(self._cache_file):
            await aiofiles.os.remove(self._cache_file)
