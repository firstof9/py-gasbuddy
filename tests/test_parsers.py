"""Tests for defensive parser behavior on malformed GraphQL payloads."""

from py_gasbuddy.parsers import (
    parse_cursor,
    parse_location_results,
    parse_results,
    parse_trends,
)


def test_parse_cursor_data_null() -> None:
    """parse_cursor returns None when data is null."""
    assert parse_cursor({"data": None}) is None


def test_parse_cursor_location_null() -> None:
    """parse_cursor returns None when locationBySearchTerm is null."""
    assert parse_cursor({"data": {"locationBySearchTerm": None}}) is None


def test_parse_cursor_stations_not_dict() -> None:
    """parse_cursor returns None when stations is a list (not a dict)."""
    payload = {"data": {"locationBySearchTerm": {"stations": []}}}
    assert parse_cursor(payload) is None


def test_parse_cursor_missing_cursor_key() -> None:
    """parse_cursor returns None when there is no cursor key."""
    payload = {"data": {"locationBySearchTerm": {"stations": {"results": []}}}}
    assert parse_cursor(payload) is None


def test_parse_cursor_cursor_not_dict() -> None:
    """parse_cursor returns None when cursor is not a dict."""
    payload = {"data": {"locationBySearchTerm": {"stations": {"cursor": None}}}}
    assert parse_cursor(payload) is None


def test_parse_location_results_empty() -> None:
    """parse_location_results returns an empty list when data is null."""
    result = parse_location_results({"data": None})
    assert result == {"results": [], "next_cursor": None}


def test_parse_location_results_results_not_list() -> None:
    """parse_location_results tolerates results not being a list."""
    payload = {"data": {"locationBySearchTerm": {"stations": {"results": None}}}}
    result = parse_location_results(payload)
    assert result == {"results": [], "next_cursor": None}


def test_parse_location_results_skips_malformed_entries() -> None:
    """Entries without an id are skipped, not raised."""
    payload = {
        "data": {
            "locationBySearchTerm": {
                "stations": {
                    "results": [
                        {"id": "1", "name": "Good"},
                        {"name": "no id"},
                        None,
                    ]
                }
            }
        }
    }
    result = parse_location_results(payload)
    assert len(result["results"]) == 1
    assert result["results"][0]["station_id"] == "1"


def test_parse_results_empty() -> None:
    """parse_results returns an empty list when data is null."""
    assert parse_results({"data": None}, limit=5) == []


def test_parse_results_results_not_list() -> None:
    """parse_results tolerates results not being a list."""
    payload = {"data": {"locationBySearchTerm": {"stations": {"results": "oops"}}}}
    assert parse_results(payload, limit=5) == []


def test_parse_trends_empty() -> None:
    """parse_trends returns an empty list when data is null."""
    assert parse_trends({"data": None}) == []


def test_parse_trends_trends_not_list() -> None:
    """parse_trends tolerates trends not being a list."""
    payload = {"data": {"locationBySearchTerm": {"trends": None}}}
    assert parse_trends(payload) == []


def test_parse_trends_skips_malformed_entries() -> None:
    """Trend entries missing required keys are skipped."""
    payload = {
        "data": {
            "locationBySearchTerm": {
                "trends": [
                    {"today": 3.5, "todayLow": 3.2, "areaName": "A"},
                    {"today": 3.5},  # missing keys
                ]
            }
        }
    }
    result = parse_trends(payload)
    assert len(result) == 1
    assert result[0]["area"] == "A"


def test_parse_location_results_results_truthy_non_list() -> None:
    """A truthy non-list 'results' is coerced to an empty list (not just None)."""
    payload = {"data": {"locationBySearchTerm": {"stations": {"results": "oops"}}}}
    result = parse_location_results(payload)
    assert result["results"] == []


def test_parse_trends_truthy_non_list() -> None:
    """A truthy non-list 'trends' returns an empty list (not just None)."""
    payload = {"data": {"locationBySearchTerm": {"trends": "oops"}}}
    assert parse_trends(payload) == []


def test_parse_results_skips_partially_malformed_entries() -> None:
    """parse_results skips entries that lack required keys, or contain non-dict nested lists."""
    payload = {
        "data": {
            "locationBySearchTerm": {
                "stations": {
                    "results": [
                        # 1. Valid station
                        {
                            "id": "1",
                            "priceUnit": "gallon",
                            "currency": "USD",
                            "latitude": 45.0,
                            "longitude": -90.0,
                            "name": "Good Station",
                            "prices": [
                                {
                                    "fuelProduct": "regular",
                                    "credit": {"price": 3.10},
                                }
                            ],
                        },
                        # 2. Missing required key (priceUnit)
                        {
                            "id": "2",
                            "currency": "USD",
                            "latitude": 45.0,
                            "longitude": -90.0,
                            "name": "Bad Station 1",
                        },
                        # 3. Non-dict prices
                        {
                            "id": "3",
                            "priceUnit": "gallon",
                            "currency": "USD",
                            "latitude": 45.0,
                            "longitude": -90.0,
                            "name": "Bad Station 2",
                            "prices": ["not-a-dict"],
                        },
                        # 4. None/Null entry
                        None,
                    ]
                }
            }
        }
    }
    results = parse_results(payload, limit=5)
    assert len(results) == 2  # Good Station + Bad Station 2
    assert results[0]["station_id"] == "1"
    assert "regular" in results[0]
    assert results[1]["station_id"] == "3"
    assert "regular" not in results[1]  # skipped the malformed price


def test_parsers_truthy_non_dict_guards() -> None:
    """_stations_block and parse_trends return empty values when data or locationBySearchTerm is a truthy non-dict."""
    # 1. data is a string "oops"
    payload_str_data = {"data": "oops"}
    assert parse_cursor(payload_str_data) is None
    assert parse_location_results(payload_str_data) == {
        "results": [],
        "next_cursor": None,
    }
    assert parse_results(payload_str_data, limit=5) == []
    assert parse_trends(payload_str_data) == []

    # 2. locationBySearchTerm is a boolean True
    payload_bool_loc = {"data": {"locationBySearchTerm": True}}
    assert parse_cursor(payload_bool_loc) is None
    assert parse_location_results(payload_bool_loc) == {
        "results": [],
        "next_cursor": None,
    }
    assert parse_results(payload_bool_loc, limit=5) == []
    assert parse_trends(payload_bool_loc) == []


def test_build_discount_map_non_string_grades() -> None:
    """build_discount_map ignores non-string grade items gracefully."""
    from py_gasbuddy.parsers import build_discount_map

    offers = [
        {"discounts": [{"pwgbDiscount": "0.05", "grades": ["regular", 123, None, {}]}]}
    ]
    discount_map = build_discount_map(offers)
    assert discount_map == {"regular": 0.05}


def test_build_discount_map_defensive_coverage() -> None:
    """build_discount_map covers defensive type check branches."""
    from py_gasbuddy.parsers import build_discount_map

    offers = [
        # 1. Non-dict offer (line 33)
        "not-a-dict",
        # 2. Non-list discounts (line 36)
        {"discounts": "not-a-list"},
        # 3. Non-dict disc in discounts (line 39)
        {"discounts": ["not-a-dict-disc"]},
        # 4. Non-list grades in disc (line 49)
        {
            "discounts": [
                {
                    "pwgbDiscount": "0.05",
                    "grades": "not-a-list-grades",
                }
            ]
        },
        # 5. Valid offer to verify it keeps working
        {
            "discounts": [
                {
                    "pwgbDiscount": "0.10",
                    "grades": ["regular"],
                }
            ]
        },
    ]

    result = build_discount_map(offers)
    assert result == {"regular": 0.10}


def test_parse_ev_stations_non_list_coverage() -> None:
    """parse_ev_stations returns empty list when stations_data is not a list (line 199)."""
    from py_gasbuddy.parsers import parse_ev_stations

    assert parse_ev_stations("not-a-list") == []
    assert parse_ev_stations(None) == []
