"""Library tests."""

import json
import logging

import pytest
from aiohttp.client_exceptions import ServerTimeoutError

import aiofiles
import aiofiles.os
import gasbuddy
from tests.common import load_fixture

pytestmark = pytest.mark.asyncio

TEST_URL = "https://www.gasbuddy.com/graphql"
GB_URL = "https://www.gasbuddy.com/home"
SOLVER_URL = "http://solver.url"


async def test_location_search(mock_aioclient, caplog):
    """Test location_search function."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("location.json"),
    )
    with caplog.at_level(logging.DEBUG):
        manager = gasbuddy.GasBuddy()
        data = await manager.location_search(zipcode=12345)

    assert (
        data["data"]["locationBySearchTerm"]["stations"]["results"][0]["id"] == "187725"
    )
    assert "CSRF token found: 1.+Qw4hH/vdM0Kvscg" in caplog.text
    await manager.clear_cache()


async def test_location_search_timeout(mock_aioclient, caplog):
    """Test server timeout exception handling."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        exception=ServerTimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        manager = gasbuddy.GasBuddy()
        await manager.location_search(zipcode=12345)
    assert gasbuddy.ERROR_TIMEOUT in caplog.text
    await manager.clear_cache()


async def test_location_search_exception(mock_aioclient):
    """Test location_search function."""
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("location.json"),
    )
    with pytest.raises(gasbuddy.MissingSearchData):
        manager = gasbuddy.GasBuddy()
        await manager.location_search()
        await manager.clear_cache()


async def test_price_lookup(mock_aioclient, caplog):
    """Test price_lookup function."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("station.json"),
    )
    manager = gasbuddy.GasBuddy(station_id=205033)
    with caplog.at_level(logging.DEBUG):
        data = await manager.price_lookup()

        assert "No cache file found, creating..." in caplog.text

    assert data["station_id"] == "205033"
    assert data["regular_gas"]["price"] == 3.27
    assert data["regular_gas"]["cash_price"] == 3.17
    assert data["regular_gas"]["credit"] == "Flemmit"
    assert data["regular_gas"]["last_updated"] == "2024-09-06T09:54:05.489Z"
    assert data["unit_of_measure"] == "dollars_per_gallon"
    assert data["currency"] == "USD"
    assert not data["image_url"]
    assert not data["premium_gas"]["price"]
    assert not data["premium_gas"]["cash_price"]

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("station.json"),
    )

    with caplog.at_level(logging.DEBUG):
        await manager.price_lookup()
        assert "Found cache file, reading..." in caplog.text

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("station2.json"),
    )
    manager = gasbuddy.GasBuddy(station_id=197274,cache_file="cache/test_cache")
    data = await manager.price_lookup()

    assert data["station_id"] == "197274"
    assert data["regular_gas"]["price"] == 131.9
    assert not "cash_price" in data["regular_gas"]
    assert data["regular_gas"]["credit"] == "qjnw4hgzcn"
    assert data["regular_gas"]["last_updated"] == "2024-09-06T14:42:39.298Z"
    assert data["unit_of_measure"] == "cents_per_liter"
    assert data["currency"] == "CAD"
    assert data["latitude"] == 53.3066
    assert data["longitude"] == -113.5559
    assert data["image_url"] == "https://images.gasbuddy.io/b/117.png"

    await manager.clear_cache()


async def test_price_lookup_service(mock_aioclient, caplog):
    """Test price_lookup function."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("prices_gps.json"),
    )
    with caplog.at_level(logging.DEBUG):
        manager = gasbuddy.GasBuddy()
        data = await manager.price_lookup_service(lat=1234, lon=5678)

    assert isinstance(data, dict)
    assert data["results"][0] == {
        "station_id": "187725",
        "unit_of_measure": "dollars_per_gallon",
        "currency": "USD",
        "latitude": 33.465405037595,
        "longitude": -112.505053281784,
        "regular_gas": {
            "credit": "fred1129",
            "price": 3.28,
            "last_updated": "2024-11-18T21:58:38.859Z",
        },
        "midgrade_gas": {
            "credit": "fred1129",
            "price": 3.73,
            "last_updated": "2024-11-18T21:58:38.891Z",
        },
        "premium_gas": {
            "credit": "fred1129",
            "price": 4,
            "last_updated": "2024-11-18T21:58:38.915Z",
        },
        "diesel": {
            "credit": "fred1129",
            "price": 3.5,
            "last_updated": "2024-11-18T21:58:38.946Z",
        },
    }
    assert len(data["results"]) == 5
    assert data["trend"] == {
        "average_price": 3.33,
        "lowest_price": 2.59,
        "area": "Arizona",
    }
    assert len(data["trend"]) == 3
    await manager.clear_cache()

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("prices_gps.json"),
    )
    with caplog.at_level(logging.DEBUG):
        manager = gasbuddy.GasBuddy()
        data = await manager.price_lookup_service(zipcode=12345)

    assert isinstance(data, dict)
    assert data["results"][0] == {
        "station_id": "187725",
        "unit_of_measure": "dollars_per_gallon",
        "currency": "USD",
        "latitude": 33.465405037595,
        "longitude": -112.505053281784,
        "regular_gas": {
            "credit": "fred1129",
            "price": 3.28,
            "last_updated": "2024-11-18T21:58:38.859Z",
        },
        "midgrade_gas": {
            "credit": "fred1129",
            "price": 3.73,
            "last_updated": "2024-11-18T21:58:38.891Z",
        },
        "premium_gas": {
            "credit": "fred1129",
            "price": 4,
            "last_updated": "2024-11-18T21:58:38.915Z",
        },
        "diesel": {
            "credit": "fred1129",
            "price": 3.5,
            "last_updated": "2024-11-18T21:58:38.946Z",
        },
    }
    assert len(data["results"]) == 5
    assert data["trend"] == {
        "average_price": 3.33,
        "lowest_price": 2.59,
        "area": "Arizona",
    }
    assert len(data["trend"]) == 3
    await manager.clear_cache()

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body="[...]",
    )
    with pytest.raises(gasbuddy.exceptions.LibraryError):
        manager = gasbuddy.GasBuddy()
        data = await manager.price_lookup_service(lat=1234, lon=5678)

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=json.dumps({"errors": {"message": "Fake Error"}}),
    )
    with pytest.raises(gasbuddy.exceptions.APIError):
        data = await gasbuddy.GasBuddy().price_lookup_service(lat=1234, lon=5678)
    await manager.clear_cache()



async def test_header_errors(mock_aioclient, caplog):
    """Test price_lookup function."""
    mock_aioclient.get(GB_URL, status=404, body="Not Found")
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("station.json"),
        repeat=True,
    )
    await gasbuddy.GasBuddy(station_id=205033).price_lookup()
    assert (
        "An error reteiving data from the server, code: 404\nmessage: Not Found"
        in caplog.text
    )
    mock_aioclient.get(
        GB_URL,
        status=404,
        exception=ServerTimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        await gasbuddy.GasBuddy(station_id=205033).price_lookup()
    assert (
        "Timeout wile getting CSRF tokens: https://www.gasbuddy.com/home" in caplog.text
    )
    mock_aioclient.get(
        GB_URL,
        status=200,
        body="<html></html>",
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(gasbuddy.LibraryError):
            await gasbuddy.GasBuddy(station_id=205033).price_lookup()
    assert "CSRF token not found." in caplog.text
    assert "Skipping request due to missing token." in caplog.text


async def test_retry_logic(mock_aioclient, caplog):
    """Test retry logic."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=403,
        body='<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title></html>',
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(gasbuddy.LibraryError):
            await gasbuddy.GasBuddy(station_id=205033).price_lookup()
    assert "Retrying request..." in caplog.text


async def test_solver(mock_aioclient, caplog):
    """Test location_search function."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("location.json"),
    )
    mock_aioclient.post(
        SOLVER_URL,
        status=200,
        body=load_fixture("solver_response.json"),
    )
    with caplog.at_level(logging.DEBUG):
        data = await gasbuddy.GasBuddy(solver_url=SOLVER_URL).location_search(
            zipcode=12345
        )

    assert (
        data["data"]["locationBySearchTerm"]["stations"]["results"][0]["id"] == "187725"
    )
    assert "CSRF token found: 1.RiXH1tCtoqNhvBuo" in caplog.text


async def test_price_lookup_api_error(mock_aioclient, caplog):
    """Test price_lookup function."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("server_error.json"),
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(gasbuddy.APIError):
            await gasbuddy.GasBuddy(station_id=205033).price_lookup()

    assert (
        "An error occured attempting to retrieve the data: Published deal alerts not found"
        in caplog.text
    )

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body='{"errors": "error"}',
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(gasbuddy.APIError):
            await gasbuddy.GasBuddy(station_id=205033).price_lookup()

    assert (
        "An error occured attempting to retrieve the data: Server side error occured."
        in caplog.text
    )

    mock_aioclient.post(
        TEST_URL,
        status=404,
        body="Not Found",
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(gasbuddy.LibraryError):
            await gasbuddy.GasBuddy(station_id=205033).price_lookup()

    assert (
        "An error occured attempting to retrieve the data: {'error': 'Not Found'}"
        in caplog.text
    )

async def test_clear_cache(mock_aioclient, caplog):
    """Test clear_cache function."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("station.json"),
    )
    manager = gasbuddy.GasBuddy(station_id=205033)
    await manager.price_lookup()
    await manager.clear_cache()

async def test_cache_json_error(mock_aioclient, caplog):
    """Test JSON error in cache read."""
    # Setup invalid cache file
    file_name = "gasbuddy/gasbuddy_cache"
    async with aiofiles.open(file_name, mode="w") as file:
        await file.write("lajdhfo98423hrujrna;ldifuhp8h4r984h32ioufhahudfhi2h398rhudn")    

    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("station.json"),
    )
    with caplog.at_level(logging.DEBUG):
        manager = gasbuddy.GasBuddy(station_id=205033)
        await manager.price_lookup()
        assert "Invalid JSON data" in caplog.text
    await manager.clear_cache()
    
async def test_read_no_file(mock_aioclient, caplog):
    """Test clear_cache function."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("station.json"),
    )
    manager = gasbuddy.GasBuddy(station_id=205033)
    with caplog.at_level(logging.DEBUG):
        manager._cache_manager = gasbuddy.cache.GasBuddyCache()
        data = await manager._cache_manager.read_cache()
        assert data == {}
