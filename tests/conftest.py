"""Provide common pytest fixtures."""

from pathlib import Path

import pytest
from aioresponses import aioresponses

TEST_URL = "https://www.gasbuddy.com/graphql"

_DEFAULT_CACHE = Path.home() / ".cache" / "py_gasbuddy" / "token"


@pytest.fixture(autouse=True)
def clear_default_cache():
    """Delete the default cache file before and after each test for isolation."""
    _DEFAULT_CACHE.unlink(missing_ok=True)
    yield
    _DEFAULT_CACHE.unlink(missing_ok=True)


@pytest.fixture
def mock_aioclient():
    """Fixture to mock aioclient calls."""
    with aioresponses() as m:
        yield m
