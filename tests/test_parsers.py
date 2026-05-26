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
    payload = {
        "data": {"locationBySearchTerm": {"stations": {"cursor": None}}}
    }
    assert parse_cursor(payload) is None


def test_parse_location_results_empty() -> None:
    """parse_location_results returns an empty list when data is null."""
    result = parse_location_results({"data": None})
    assert result == {"results": [], "next_cursor": None}


def test_parse_location_results_results_not_list() -> None:
    """parse_location_results tolerates results not being a list."""
    payload = {
        "data": {"locationBySearchTerm": {"stations": {"results": None}}}
    }
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
    payload = {
        "data": {"locationBySearchTerm": {"stations": {"results": "oops"}}}
    }
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
