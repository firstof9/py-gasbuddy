"""Provide common pytest fixtures."""

import pytest
from aioresponses import aioresponses

TEST_URL = "https://www.gasbuddy.com/graphql"


@pytest.fixture
def mock_aioclient():
    """Fixture to mock aioclient calls."""
    with aioresponses() as m:
        yield m
