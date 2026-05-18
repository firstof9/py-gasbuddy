"""Provide common pytest fixtures."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from aioresponses import aioresponses

TEST_URL = "https://www.gasbuddy.com/graphql"

_DEFAULT_CACHE = Path.home() / ".cache" / "py_gasbuddy" / "token"


@pytest.fixture(autouse=True)
def clear_default_cache():
    """Move real cache aside before each test and restore it afterwards."""
    had_cache = _DEFAULT_CACHE.exists()
    backup: str | None = None
    if had_cache:
        fd, backup = tempfile.mkstemp(dir=_DEFAULT_CACHE.parent, prefix="token_bak_")
        os.close(fd)
        os.unlink(backup)
        shutil.move(str(_DEFAULT_CACHE), backup)
    else:
        _DEFAULT_CACHE.unlink(missing_ok=True)
    yield
    _DEFAULT_CACHE.unlink(missing_ok=True)
    if had_cache and backup and Path(backup).exists():
        shutil.move(backup, str(_DEFAULT_CACHE))


@pytest.fixture
def mock_aioclient():
    """Fixture to mock aioclient calls."""
    with aioresponses() as m:
        yield m
