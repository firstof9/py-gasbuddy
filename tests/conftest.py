"""Provide common pytest fixtures."""

import json

import pytest
from aioresponses import aioresponses

from tests.common import load_fixture

TEST_URL = "https://www.gasbuddy.com/graphql"


@pytest.fixture
def mock_aioclient():
    """Fixture to mock aioclient calls."""
    with aioresponses() as m:
        yield m
