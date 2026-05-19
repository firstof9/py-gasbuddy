"""Library tests."""

import json
import logging

import aiofiles
import aiofiles.os
import aiohttp
import pytest
from aiohttp import RequestInfo
from aiohttp.client_exceptions import ContentTypeError, ServerTimeoutError
from yarl import URL

import py_gasbuddy
from tests.common import load_fixture

pytestmark = pytest.mark.asyncio

TEST_URL = "https://www.gasbuddy.com/graphql"
GB_URL = "https://www.gasbuddy.com/home"
SOLVER_URL = "http://solver.url"


@pytest.mark.parametrize(
    ("zipcode", "lat", "lon", "fixture", "expected_id"),
    [
        (12345, None, None, "location.json", "187725"),
        (None, 33.4654, -112.5051, "location.json", "187725"),
    ],
)
async def test_location_search(
    mock_aioclient, caplog, tmp_path, zipcode, lat, lon, fixture, expected_id
):
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
        body=load_fixture(fixture),
    )
    cache_file = str(tmp_path / "test_cache")
    manager = py_gasbuddy.GasBuddy(cache_file=cache_file)
    await manager.clear_cache()
    with caplog.at_level(logging.DEBUG):
        data = await manager.location_search(zipcode=zipcode, lat=lat, lon=lon)

    assert data["results"][0]["station_id"] == expected_id
    assert "CSRF token found:" in caplog.text
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
        manager = py_gasbuddy.GasBuddy()
        await manager.location_search(zipcode=12345)
    assert py_gasbuddy.ERROR_TIMEOUT in caplog.text
    await manager.clear_cache()


async def test_location_search_exception(mock_aioclient):
    """Test location_search function."""
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("location.json"),
    )
    with pytest.raises(py_gasbuddy.MissingSearchData):
        manager = py_gasbuddy.GasBuddy()
        await manager.location_search()
        await manager.clear_cache()


async def test_location_search_graphql_errors(mock_aioclient, caplog):
    """Test location_search returns empty result when response has GraphQL errors."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=json.dumps({"errors": [{"message": "Some GraphQL error"}]}),
    )
    with caplog.at_level(logging.ERROR):
        manager = py_gasbuddy.GasBuddy()
        result = await manager.location_search(zipcode=12345)
    assert result["results"] == []
    assert result["next_cursor"] is None
    assert "location_search: GraphQL errors returned" in caplog.text
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
    manager = py_gasbuddy.GasBuddy(station_id=205033)
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
    manager = py_gasbuddy.GasBuddy(station_id=197274, cache_file="cache/test_cache")
    data = await manager.price_lookup()

    assert data["station_id"] == "197274"
    assert data["regular_gas"]["price"] == 131.9
    assert data["regular_gas"]["cash_price"] is None
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
        manager = py_gasbuddy.GasBuddy()
        data = await manager.price_lookup_service(lat=33.465, lon=-112.505)

    assert isinstance(data, dict)
    first = data["results"][0]
    assert first["station_id"] == "187725"
    assert first["unit_of_measure"] == "dollars_per_gallon"
    assert first["currency"] == "USD"
    assert first["latitude"] == 33.465405037595
    assert first["longitude"] == -112.505053281784
    assert first["regular_gas"]["price"] == 3.28
    assert first["regular_gas"]["credit"] == "fred1129"
    assert first["regular_gas"]["cash_price"] is None
    assert first["regular_gas"]["last_updated"] == "2024-11-18T21:58:38.859Z"
    assert first["midgrade_gas"]["price"] == 3.73
    assert first["premium_gas"]["price"] == 4
    assert first["diesel"]["price"] == 3.5
    assert len(data["results"]) == 5
    assert data["trend"] == [
        {"average_price": 3.33, "lowest_price": 2.59, "area": "Arizona"},
        {"average_price": 3.11, "lowest_price": 0, "area": "United States"},
    ]
    assert len(data["trend"]) == 2
    await manager.clear_cache()

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=load_fixture("prices_gps.json"),
    )
    with caplog.at_level(logging.DEBUG):
        manager = py_gasbuddy.GasBuddy()
        data = await manager.price_lookup_service(zipcode=12345)

    assert isinstance(data, dict)
    first = data["results"][0]
    assert first["station_id"] == "187725"
    assert first["unit_of_measure"] == "dollars_per_gallon"
    assert first["currency"] == "USD"
    assert first["latitude"] == 33.465405037595
    assert first["longitude"] == -112.505053281784
    assert first["regular_gas"]["price"] == 3.28
    assert first["regular_gas"]["credit"] == "fred1129"
    assert first["regular_gas"]["cash_price"] is None
    assert first["regular_gas"]["last_updated"] == "2024-11-18T21:58:38.859Z"
    assert first["midgrade_gas"]["price"] == 3.73
    assert first["premium_gas"]["price"] == 4
    assert first["diesel"]["price"] == 3.5
    assert len(data["results"]) == 5
    assert data["trend"] == [
        {"average_price": 3.33, "lowest_price": 2.59, "area": "Arizona"},
        {"average_price": 3.11, "lowest_price": 0, "area": "United States"},
    ]
    assert len(data["trend"]) == 2
    await manager.clear_cache()

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body="[...]",
    )
    with pytest.raises(py_gasbuddy.exceptions.LibraryError):
        manager = py_gasbuddy.GasBuddy()
        data = await manager.price_lookup_service(lat=33.465, lon=-112.505)

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=json.dumps({"errors": {"message": "Fake Error"}}),
    )
    with pytest.raises(py_gasbuddy.exceptions.APIError):
        data = await py_gasbuddy.GasBuddy().price_lookup_service(
            lat=33.465, lon=-112.505
        )
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
    await py_gasbuddy.GasBuddy(station_id=205033).price_lookup()
    assert (
        "An error retrieving data from the server, code: 404\nmessage: Not Found"
        in caplog.text
    )
    mock_aioclient.get(
        GB_URL,
        status=404,
        exception=ServerTimeoutError,
    )
    with caplog.at_level(logging.DEBUG):
        manager = py_gasbuddy.GasBuddy(station_id=205033)
        await manager.price_lookup()
    assert (
        "Timeout while getting CSRF tokens: https://www.gasbuddy.com/home"
        in caplog.text
    )
    mock_aioclient.get(
        GB_URL,
        status=200,
        body="<html></html>",
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(py_gasbuddy.LibraryError):
            manager = py_gasbuddy.GasBuddy(station_id=205033)
            await manager.price_lookup()
    assert "CSRF token not found." in caplog.text
    assert "Skipping request due to missing token." in caplog.text
    await manager.clear_cache()


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
        body=(
            '<!DOCTYPE html><html lang="en-US"><head>'
            "<title>Just a moment...</title></html>"
        ),
        repeat=True,
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(py_gasbuddy.LibraryError):
            manager = py_gasbuddy.GasBuddy(station_id=205033)
            await manager.price_lookup()
    assert "Retrying request..." in caplog.text
    await manager.clear_cache()


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
        manager = py_gasbuddy.GasBuddy(solver_url=SOLVER_URL)
        data = await manager.location_search(zipcode=12345)

    assert data["results"][0]["station_id"] == "187725"
    assert "CSRF token found: 1.RiXH1tCtoqNhvBuo" in caplog.text
    await manager.clear_cache()


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
        with pytest.raises(py_gasbuddy.APIError):
            await py_gasbuddy.GasBuddy(station_id=205033).price_lookup()

    assert (
        "An error occurred attempting to retrieve the data: Published deal alerts not found"
        in caplog.text
    )

    mock_aioclient.post(
        TEST_URL,
        status=200,
        body='{"errors": "error"}',
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(py_gasbuddy.APIError):
            await py_gasbuddy.GasBuddy(station_id=205033).price_lookup()

    assert (
        "An error occurred attempting to retrieve the data: Server side error occurred."
        in caplog.text
    )

    mock_aioclient.post(
        TEST_URL,
        status=404,
        body="Not Found",
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(py_gasbuddy.LibraryError):
            manager = py_gasbuddy.GasBuddy(station_id=205033)
            await manager.price_lookup()

    assert (
        "An error occurred attempting to retrieve the data: {'error': 'Not Found'}"
        in caplog.text
    )
    await manager.clear_cache()


async def test_price_lookup_null_station(mock_aioclient, caplog):
    """Test price_lookup raises APIError when station payload is null/absent."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=json.dumps({"data": {"station": None}}),
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(py_gasbuddy.APIError):
            await py_gasbuddy.GasBuddy(station_id=205033).price_lookup()
    assert "station payload missing or null" in caplog.text


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
    manager = py_gasbuddy.GasBuddy(station_id=205033)
    await manager.price_lookup()
    await manager.clear_cache()


async def test_cache_json_error(mock_aioclient, caplog, tmp_path):
    """Test JSON error in cache read."""
    cache_file = str(tmp_path / "bad_cache")
    async with aiofiles.open(cache_file, mode="w") as file:
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
        manager = py_gasbuddy.GasBuddy(station_id=205033, cache_file=cache_file)
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
    manager = py_gasbuddy.GasBuddy(station_id=205033)
    with caplog.at_level(logging.DEBUG):
        manager._cache_manager = py_gasbuddy.cache.GasBuddyCache()
        data = await manager._cache_manager.read_cache()
        assert data == {}


async def test_content_type_error(mock_aioclient, caplog):
    """Test ContentTypeError handling in process_request."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )

    # Construct a real ContentTypeError to mimic aiohttp behavior
    req_info = RequestInfo(
        url=URL(TEST_URL), method="POST", headers={}, real_url=URL(TEST_URL)
    )
    exc = ContentTypeError(req_info, (), message="Invalid content type")

    mock_aioclient.post(TEST_URL, exception=exc)

    manager = py_gasbuddy.GasBuddy()
    with caplog.at_level(logging.ERROR):
        # We expect a return value containing the error, which price_lookup_service
        # processes. If it returns {"error": ...}, price_lookup_service raises
        # LibraryError. But here checking the low-level process_request response
        # via the public method.
        res = await manager.process_request({})

    assert res == {"error": exc}
    assert "Invalid content type" in caplog.text


async def test_non_json_response_error(mock_aioclient, caplog):
    """Test non-JSON response with error status (e.g. Gateway Timeout)."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )

    # Return plain text with 504
    mock_aioclient.post(TEST_URL, status=504, body="Gateway Timeout")

    manager = py_gasbuddy.GasBuddy()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(py_gasbuddy.LibraryError):
            await manager.price_lookup_service(zipcode=12345)

    assert "Non-JSON response: Gateway Timeout" in caplog.text
    assert "An error retrieving data from the server, code: 504" in caplog.text


async def test_malformed_price_node(mock_aioclient):
    """Test price lookup with null/missing price fields."""
    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )

    malformed_data = {
        "data": {
            "station": {
                "id": "123",
                "priceUnit": "usd",
                "currency": "USD",
                "latitude": 0,
                "longitude": 0,
                "brands": [],
                "prices": [
                    {"fuelProduct": "regular_gas", "credit": None, "cash": {"price": 0}}
                ],
            }
        }
    }

    mock_aioclient.post(TEST_URL, status=200, body=json.dumps(malformed_data))

    manager = py_gasbuddy.GasBuddy(station_id=123)
    data = await manager.price_lookup()

    # Ensure robust handling (converts 0/None to None)
    assert data["regular_gas"]["price"] is None
    assert data["regular_gas"]["cash_price"] is None
    assert data["regular_gas"]["credit"] is None


async def test_external_session(mock_aioclient, tmp_path):
    """Test that an externally-provided session is reused and not closed."""
    from unittest.mock import patch

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
        repeat=True,
    )
    cache_file = str(tmp_path / "test_cache")

    async with aiohttp.ClientSession() as external_session:
        original_post = external_session.post
        with patch.object(external_session, "post", wraps=original_post) as mock_post:
            manager = py_gasbuddy.GasBuddy(
                station_id=205033, cache_file=cache_file, session=external_session
            )
            data = await manager.price_lookup()

            # Confirm the injected session's post() was actually invoked
            mock_post.assert_called_once_with(
                py_gasbuddy.BASE_URL,
                data=mock_post.call_args.kwargs["data"],
                headers=mock_post.call_args.kwargs["headers"],
            )

        # Session must still be open (not closed by the library)
        assert not external_session.closed
        assert data["station_id"] == "205033"

    await manager.clear_cache()


async def test_cache_small_file(mock_aioclient, tmp_path, caplog):
    """Test that a cache file smaller than validation size is ignored."""
    # Create a small cache file (< 30 bytes)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "test_cache"
    cache_file.write_text("short_invalid_token")

    manager = py_gasbuddy.GasBuddy(station_id=123, cache_file=str(cache_file))

    mock_aioclient.get(
        GB_URL,
        status=200,
        body=load_fixture("index.html"),
        repeat=True,
    )
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("station.json"))

    with caplog.at_level(logging.DEBUG):
        await manager.price_lookup()

    assert "Checking cache file size: 19" in caplog.text
    assert "No cache file found, creating..." in caplog.text


async def test_price_lookup_new_fields(mock_aioclient, caplog):
    """Test price_lookup returns enriched station metadata fields."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("station.json"))
    manager = py_gasbuddy.GasBuddy(station_id=205033)
    data = await manager.price_lookup()

    assert data["name"] == "Wawa"
    assert data["phone"] == "610-555-0100"
    assert data["open_status"] == "open"
    assert data["address"]["locality"] == "Phoenixville"
    assert data["address"]["region"] == "PA"
    assert data["hours"]["status"] == "open"
    assert data["star_rating"] == 4.2
    assert data["ratings_count"] == 38
    assert not data["is_fuelman_site"]
    assert not data["has_active_outage"]
    assert not data["enterprise"]
    assert data["pay_status"] is True
    assert len(data["offers"]) == 1
    assert data["offers"][0]["id"] == "offer_001"
    assert data["fuels"] == ["regular_gas", "midgrade_gas", "premium_gas"]
    assert data["amenities"][0]["name"] == "ATM"
    await manager.clear_cache()


async def test_price_lookup_formatted_price(mock_aioclient):
    """Test that PriceNode includes formatted_price and deal_price."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("station.json"))
    manager = py_gasbuddy.GasBuddy(station_id=205033)
    data = await manager.price_lookup()

    assert data["regular_gas"]["formatted_price"] == "$3.27"
    assert data["midgrade_gas"]["formatted_price"] == "$3.59"
    assert data["premium_gas"]["formatted_price"] is None
    # deal_price: credit price minus pwgbDiscount from offers
    assert data["regular_gas"]["deal_price"] == pytest.approx(3.22, abs=0.01)
    assert data["midgrade_gas"]["deal_price"] == pytest.approx(3.51, abs=0.01)
    assert data["premium_gas"]["deal_price"] is None  # price is None
    await manager.clear_cache()


async def test_price_lookup_service_name_address(mock_aioclient):
    """Test price_lookup_service results include name, address, brands, and formatted_price."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("prices_gps.json"))
    manager = py_gasbuddy.GasBuddy()
    data = await manager.price_lookup_service(lat=33.465, lon=-112.505)

    first = data["results"][0]
    assert first["name"] == "Shell"
    assert first["address"]["locality"] == "Buckeye"
    assert first["address"]["region"] == "AZ"
    assert first["brands"][0]["name"] == "Shell"
    assert first["distance"] == 0.4
    assert first["star_rating"] == 4.1
    assert first["ratings_count"] == 21
    assert first["regular_gas"]["formatted_price"] == "$3.28"
    # deal_price: 3.28 - 0.10 discount from offers
    assert first["regular_gas"]["deal_price"] == pytest.approx(3.18)
    await manager.clear_cache()


async def test_unicode_decode_error(mock_aioclient, caplog):
    """Test UnicodeDecodeError fallback path in process_request."""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, MagicMock, patch

    manager = py_gasbuddy.GasBuddy()

    async def fake_get_headers() -> None:
        manager._tag = "fake-csrf-token"

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text.side_effect = UnicodeDecodeError(
        "utf-8", b"\xff", 0, 1, "invalid start byte"
    )
    mock_response.read.return_value = b'{"data": {}}'
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post.return_value = mock_response

    @asynccontextmanager
    async def fake_get_session():
        yield mock_session

    with patch.object(manager, "_get_headers", fake_get_headers):
        with patch.object(manager, "_get_session", fake_get_session):
            with caplog.at_level(logging.DEBUG):
                await manager.process_request({})

    assert "Decoding error." in caplog.text


async def test_location_search_filters(mock_aioclient):
    """Test location_search passes brand_id and fuel filter variables."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("location.json"))
    manager = py_gasbuddy.GasBuddy()
    data = await manager.location_search(zipcode=12345, brand_id=38, fuel=1)
    assert data["results"][0]["station_id"] == "187725"
    await manager.clear_cache()


async def test_price_lookup_service_missing_data(mock_aioclient):
    """Test price_lookup_service raises MissingSearchData when no location given."""
    with pytest.raises(py_gasbuddy.MissingSearchData):
        await py_gasbuddy.GasBuddy().price_lookup_service()


async def test_price_lookup_service_filters(mock_aioclient):
    """Test price_lookup_service passes brand_id and fuel filter variables."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("prices_gps.json"))
    manager = py_gasbuddy.GasBuddy()
    data = await manager.price_lookup_service(
        lat=33.465, lon=-112.505, brand_id=23, fuel=1
    )
    assert isinstance(data, dict)
    await manager.clear_cache()


async def test_price_lookup_service_api_error_list(mock_aioclient, caplog):
    """Test price_lookup_service raises APIError when errors is a list of dicts."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=json.dumps({"errors": [{"message": "List-style error"}]}),
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(py_gasbuddy.exceptions.APIError):
            await py_gasbuddy.GasBuddy().price_lookup_service(lat=33.465, lon=-112.505)
    assert "List-style error" in caplog.text


async def test_price_lookup_service_api_error_fallback(mock_aioclient, caplog):
    """Test price_lookup_service raises APIError with fallback message for unexpected errors shape."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=json.dumps({"errors": ["bad"]}),
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(py_gasbuddy.exceptions.APIError):
            await py_gasbuddy.GasBuddy().price_lookup_service(lat=33.465, lon=-112.505)
    assert "Server side error occurred." in caplog.text


async def test_parse_distance():
    """Test parse_distance covers all branches."""
    from py_gasbuddy.parsers import parse_distance

    assert parse_distance(None) is None
    assert parse_distance(1.5) == pytest.approx(1.5)
    assert parse_distance(2) == pytest.approx(2.0)
    assert parse_distance("0.37mi") == pytest.approx(0.37)
    assert parse_distance("abc") is None


async def test_build_discount_map():
    """Test build_discount_map handles None and unconvertible pwgbDiscount values."""
    from py_gasbuddy.parsers import build_discount_map

    # None pwgbDiscount is skipped
    result = build_discount_map(
        [{"discounts": [{"grades": ["regular_gas"], "pwgbDiscount": None}]}]
    )
    assert result == {}

    # Non-numeric string is skipped gracefully
    result = build_discount_map(
        [{"discounts": [{"grades": ["regular_gas"], "pwgbDiscount": "bad"}]}]
    )
    assert result == {}

    # Valid string discount is summed
    result = build_discount_map(
        [{"discounts": [{"grades": ["regular_gas"], "pwgbDiscount": "0.10"}]}]
    )
    assert result == {"regular_gas": pytest.approx(0.10)}


async def test_clear_cache_default_path():
    """Test clear_cache uses GasBuddyCache() default path when no cache_file is set."""
    manager = py_gasbuddy.GasBuddy()
    assert manager._cache_manager is None
    await manager.clear_cache()
    assert manager._cache_manager is not None


async def test_validate_coordinates(mock_aioclient):
    """Test that out-of-range lat/lon raises ValueError before any network call."""
    manager = py_gasbuddy.GasBuddy()

    with pytest.raises(ValueError, match="lat must be between"):
        await manager.location_search(lat=91.0, lon=0.0)

    with pytest.raises(ValueError, match="lon must be between"):
        await manager.location_search(lat=0.0, lon=181.0)

    with pytest.raises(ValueError, match="lat must be between"):
        await manager.price_lookup_service(lat=-91.0, lon=0.0)

    with pytest.raises(ValueError, match="lon must be between"):
        await manager.price_lookup_service(lat=0.0, lon=-181.0)


async def test_ev_stations_nearby(mock_aioclient):
    """Test ev_stations_nearby returns parsed EvStationResult."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("ev_nearby.json"))
    manager = py_gasbuddy.GasBuddy()
    result = await manager.ev_stations_nearby(lat=43.045, lon=-76.308)

    assert result["total"] == 2
    assert len(result["stations"]) == 2

    s = result["stations"][0]
    assert s["station_id"] == "EV_001"
    assert s["name"] == "Electrify America - Walmart"
    assert s["network"] == "Electrify_America"
    assert s["dc_fast_count"] == 6
    assert s["ccs_count"] == 6
    assert s["ccs_power"] == "350kW"
    assert s["pricing"] == "$0.48/kWh"
    assert s["distance_miles"] == pytest.approx(0.5)
    assert s["level1_count"] == 0
    assert s["nacs_count"] == 0
    assert s["phone"] == "1-833-632-2778"
    assert s["access_hours"] == "24 hours daily"

    post_req = None
    for key, reqs in mock_aioclient.requests.items():
        if key[0] == "POST" and str(key[1]) == TEST_URL:
            post_req = reqs[0]
            break
    assert post_req is not None
    req_body = json.loads(post_req.kwargs["data"])
    variables = req_body["variables"]
    assert variables["latitude"] == 43.045
    assert variables["longitude"] == -76.308
    assert "networks" not in variables
    assert "connectorTypes" not in variables
    assert "chargingLevels" not in variables

    await manager.clear_cache()


async def test_ev_stations_nearby_with_filters(mock_aioclient):
    """Test ev_stations_nearby with explicit networks, connector types, and charging levels."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("ev_nearby.json"))
    manager = py_gasbuddy.GasBuddy()
    result = await manager.ev_stations_nearby(
        lat=43.045,
        lon=-76.308,
        networks="Tesla,ChargePoint",
        connector_types="CHADEMO,TESLA",
        charging_levels="DCFast,Level2",
    )

    assert result["total"] == 2

    post_req = None
    for key, reqs in mock_aioclient.requests.items():
        if key[0] == "POST" and str(key[1]) == TEST_URL:
            post_req = reqs[0]
            break
    assert post_req is not None
    req_body = json.loads(post_req.kwargs["data"])
    variables = req_body["variables"]
    assert variables["latitude"] == 43.045
    assert variables["longitude"] == -76.308
    assert variables["networks"] == "Tesla,ChargePoint"
    assert variables["connectorTypes"] == "CHADEMO,TESLA"
    assert variables["chargingLevels"] == "DCFast,Level2"

    await manager.clear_cache()


async def test_ev_stations_nearby_error(mock_aioclient):
    """Test ev_stations_nearby raises LibraryError on error response."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body="[...]")
    with pytest.raises(py_gasbuddy.LibraryError):
        await py_gasbuddy.GasBuddy().ev_stations_nearby(lat=43.045, lon=-76.308)


async def test_ev_stations_nearby_api_error(mock_aioclient, caplog):
    """Test ev_stations_nearby raises APIError on GraphQL errors."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=json.dumps({"errors": [{"message": "EV service unavailable"}]}),
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(py_gasbuddy.exceptions.APIError):
            await py_gasbuddy.GasBuddy().ev_stations_nearby(lat=43.045, lon=-76.308)
    assert "EV service unavailable" in caplog.text


async def test_ev_stations_by_bounds(mock_aioclient):
    """Test ev_stations_by_bounds returns parsed EvStationResult."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("ev_bounds.json"))
    manager = py_gasbuddy.GasBuddy()
    result = await manager.ev_stations_by_bounds(
        ne_lat=43.85, ne_lng=-81.68, sw_lat=35.55, sw_lng=-115.48
    )

    assert result["total"] == 1
    s = result["stations"][0]
    assert s["station_id"] == "EV_003"
    assert s["name"] == "Tesla Supercharger - Camillus"
    assert s["network"] == "Tesla"
    assert s["nacs_count"] == 8
    assert s["nacs_power"] == "250kW"
    assert s["dc_fast_count"] == 8
    assert s["ccs_count"] == 0
    assert s["pricing"] == "$0.37/kWh"

    post_req = None
    for key, reqs in mock_aioclient.requests.items():
        if key[0] == "POST" and str(key[1]) == TEST_URL:
            post_req = reqs[0]
            break
    assert post_req is not None
    req_body = json.loads(post_req.kwargs["data"])
    variables = req_body["variables"]
    assert variables["northEastLat"] == 43.85
    assert variables["northEastLng"] == -81.68
    assert variables["southWestLat"] == 35.55
    assert variables["southWestLng"] == -115.48
    assert "networks" not in variables
    assert "connectorTypes" not in variables
    assert "chargingLevels" not in variables

    await manager.clear_cache()


async def test_ev_stations_by_bounds_with_filters(mock_aioclient):
    """Test ev_stations_by_bounds with explicit networks, connector types, and charging levels."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("ev_bounds.json"))
    manager = py_gasbuddy.GasBuddy()
    result = await manager.ev_stations_by_bounds(
        ne_lat=43.85,
        ne_lng=-81.68,
        sw_lat=35.55,
        sw_lng=-115.48,
        networks="Tesla,ChargePoint",
        connector_types="CHADEMO,TESLA",
        charging_levels="DCFast,Level2",
    )

    assert result["total"] == 1

    post_req = None
    for key, reqs in mock_aioclient.requests.items():
        if key[0] == "POST" and str(key[1]) == TEST_URL:
            post_req = reqs[0]
            break
    assert post_req is not None
    req_body = json.loads(post_req.kwargs["data"])
    variables = req_body["variables"]
    assert variables["northEastLat"] == 43.85
    assert variables["northEastLng"] == -81.68
    assert variables["southWestLat"] == 35.55
    assert variables["southWestLng"] == -115.48
    assert variables["networks"] == "Tesla,ChargePoint"
    assert variables["connectorTypes"] == "CHADEMO,TESLA"
    assert variables["chargingLevels"] == "DCFast,Level2"

    await manager.clear_cache()


async def test_ev_stations_by_bounds_error(mock_aioclient):
    """Test ev_stations_by_bounds raises LibraryError on error response."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body="[...]")
    with pytest.raises(py_gasbuddy.LibraryError):
        await py_gasbuddy.GasBuddy().ev_stations_by_bounds(
            ne_lat=43.85, ne_lng=-81.68, sw_lat=35.55, sw_lng=-115.48
        )


async def test_ev_stations_nearby_api_error_fallback(mock_aioclient, caplog):
    """Test ev_stations_nearby APIError fallback when errors shape is unexpected."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=json.dumps({"errors": ["bad"]}))
    with caplog.at_level(logging.ERROR):
        with pytest.raises(py_gasbuddy.exceptions.APIError):
            await py_gasbuddy.GasBuddy().ev_stations_nearby(lat=43.045, lon=-76.308)
    assert "Server side error occurred." in caplog.text


async def test_ev_stations_by_bounds_api_error(mock_aioclient, caplog):
    """Test ev_stations_by_bounds raises APIError on GraphQL errors."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(
        TEST_URL,
        status=200,
        body=json.dumps({"errors": [{"message": "Bounds error"}]}),
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(py_gasbuddy.exceptions.APIError):
            await py_gasbuddy.GasBuddy().ev_stations_by_bounds(
                ne_lat=43.85, ne_lng=-81.68, sw_lat=35.55, sw_lng=-115.48
            )
    assert "Bounds error" in caplog.text


async def test_ev_stations_by_bounds_api_error_fallback(mock_aioclient, caplog):
    """Test ev_stations_by_bounds APIError fallback when errors shape is unexpected."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    mock_aioclient.post(TEST_URL, status=200, body=json.dumps({"errors": ["bad"]}))
    with caplog.at_level(logging.ERROR):
        with pytest.raises(py_gasbuddy.exceptions.APIError):
            await py_gasbuddy.GasBuddy().ev_stations_by_bounds(
                ne_lat=43.85, ne_lng=-81.68, sw_lat=35.55, sw_lng=-115.48
            )
    assert "Server side error occurred." in caplog.text


async def test_cache_makedirs(tmp_path):
    """Test GasBuddyCache.write_cache creates parent directories when they don't exist."""
    nested_path = tmp_path / "deep" / "nested" / "cache"
    cache = py_gasbuddy.cache.GasBuddyCache(str(nested_path))
    await cache.write_cache(b'{"token": "test"}')
    assert nested_path.exists()


async def test_price_lookup_service_pagination(mock_aioclient):
    """Test that next_cursor is returned and accepted as a cursor parameter."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)

    # Page 1 — response has a next cursor
    mock_aioclient.post(
        TEST_URL, status=200, body=load_fixture("prices_gps_has_more.json")
    )
    manager = py_gasbuddy.GasBuddy()
    page1 = await manager.price_lookup_service(zipcode=12345)
    assert page1["next_cursor"] == "eyJjdXJzb3IiOiAyMH0="

    # Page 2 — pass the cursor; response has null cursor (last page)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("prices_gps.json"))
    page2 = await manager.price_lookup_service(
        zipcode=12345, cursor=page1["next_cursor"]
    )
    assert "next_cursor" not in page2
    assert page2["results"][0]["station_id"] == "187725"
    await manager.clear_cache()


async def test_location_search_pagination(mock_aioclient, caplog, tmp_path):
    """Test location_search returns next_cursor and accepts a cursor parameter."""
    mock_aioclient.get(GB_URL, status=200, body=load_fixture("index.html"), repeat=True)
    cache_file = str(tmp_path / "test_cache")

    # Null cursor (last page) — fixture has "next": null
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("location.json"))
    manager = py_gasbuddy.GasBuddy(cache_file=cache_file)
    result = await manager.location_search(zipcode=12345)
    assert result["next_cursor"] is None
    assert result["results"][0]["station_id"] == "187725"

    # Passing a cursor token — verify it's accepted (same fixture, null cursor response)
    mock_aioclient.post(TEST_URL, status=200, body=load_fixture("location.json"))
    result_page2 = await manager.location_search(zipcode=12345, cursor="page2_token")
    assert result_page2["results"][0]["station_id"] == "187725"

    # Error path returns empty results with null cursor
    mock_aioclient.post(TEST_URL, status=200, body="[...]")
    result_err = await manager.location_search(zipcode=12345)
    assert result_err["results"] == []
    assert result_err["next_cursor"] is None
