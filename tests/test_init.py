"""Library tests."""

from aiohttp.client_exceptions import ServerTimeoutError
import gasbuddy
import logging
import pytest
from tests.common import load_fixture

pytestmark = pytest.mark.asyncio

TEST_URL = "https://www.gasbuddy.com/graphql"


async def test_location_search(mock_aioclient):
    """Test location_search function."""
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("location.json"),
    )
    data = await gasbuddy.GasBuddy().location_search(zipcode=12345)

    assert (
        data["data"]["locationBySearchTerm"]["stations"]["results"][0]["id"] == "187725"
    )


async def test_location_search_timeout(mock_aioclient, caplog):
    """Test server timeout exception handling."""
    mock_aioclient.post(
        TEST_URL,
        exception=ServerTimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        await gasbuddy.GasBuddy().location_search(zipcode=12345)
    assert gasbuddy.ERROR_TIMEOUT in caplog.text


async def test_location_search_exception(mock_aioclient):
    """Test location_search function."""
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("location.json"),
    )
    with pytest.raises(gasbuddy.MissingSearchData):
        await gasbuddy.GasBuddy().location_search()


async def test_price_lookup(mock_aioclient):
    """Test price_lookup function."""
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("station.json"),
    )
    data = await gasbuddy.GasBuddy(station_id=208656).price_lookup()

    assert data["station_id"] == "208656"
    assert data["regular_gas"]["price"] == 2.99
    assert data["regular_gas"]["credit"] == "Owner"
    assert data["regular_gas"]["last_updated"] == "2023-12-07T17:21:38.370Z"
    assert data["unit_of_measure"] == "dollars_per_gallon"
    assert data["currency"] == "USD"