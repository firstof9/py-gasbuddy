"""Provide common pytest fixtures."""

import shutil
from pathlib import Path

import pytest
from aioresponses import aioresponses

TEST_URL = "https://www.gasbuddy.com/graphql"

_DEFAULT_CACHE = Path.home() / ".cache" / "py_gasbuddy" / "token"
_DEFAULT_CACHE_BAK = _DEFAULT_CACHE.with_suffix(".bak")


@pytest.fixture(autouse=True)
def clear_default_cache():
    """Move real cache aside before each test and restore it afterwards."""
    had_cache = _DEFAULT_CACHE.exists()
    if had_cache:
        shutil.move(str(_DEFAULT_CACHE), str(_DEFAULT_CACHE_BAK))
    else:
        _DEFAULT_CACHE.unlink(missing_ok=True)
    yield
    _DEFAULT_CACHE.unlink(missing_ok=True)
    if had_cache and _DEFAULT_CACHE_BAK.exists():
        shutil.move(str(_DEFAULT_CACHE_BAK), str(_DEFAULT_CACHE))


@pytest.fixture
def mock_aioclient():
    """Fixture to mock aioclient calls."""
    with aioresponses() as m:
        yield m
