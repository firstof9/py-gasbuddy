"""Data-parsing helpers for py-gasbuddy."""

from typing import Any, cast

from .models import (
    EvStation,
    LocationSearchResult,
    PriceNode,
    StationPrice,
    StationSummary,
    TrendData,
)


def parse_distance(value: Any) -> float | None:
    """Coerce distance to float, stripping any unit suffix (e.g. '0.37mi')."""
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    stripped = "".join(c for c in str(value) if c.isdigit() or c == ".")
    try:
        return float(stripped)
    except ValueError:
        return None


def build_discount_map(offers: list[Any]) -> dict[str, float]:
    """Return fuel product key to total pwgbDiscount mapping across all offers."""
    discount_map: dict[str, float] = {}
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        discounts = offer.get("discounts")
        if not isinstance(discounts, list):
            continue
        for disc in discounts:
            if not isinstance(disc, dict):
                continue
            raw = disc.get("pwgbDiscount")
            if raw is None:
                continue
            try:
                amount = float(raw)
            except (ValueError, TypeError):
                continue
            grades = disc.get("grades")
            if not isinstance(grades, list):
                continue
            for grade in grades:
                if not isinstance(grade, str):
                    continue
                discount_map[grade] = discount_map.get(grade, 0.0) + amount
    return discount_map


def format_price_node(
    price_node: dict[str, Any], deal_discount: float | None = None
) -> PriceNode:
    """Format a single price node."""
    credit_data = price_node.get("credit")
    if not isinstance(credit_data, dict):
        credit_data = {}
    cash_data = price_node.get("cash")
    if not isinstance(cash_data, dict):
        cash_data = {}

    credit_price = credit_data.get("price", 0)
    cash_price = cash_data.get("price", 0)

    effective_price = None if credit_price == 0 else credit_price
    deal_price: float | None = None
    if effective_price is not None and deal_discount is not None:
        deal_price = round(max(effective_price - deal_discount, 0.0), 2)

    return PriceNode(
        credit=credit_data.get("nickname"),
        cash_price=None if cash_price == 0 else cash_price,
        price=effective_price,
        last_updated=credit_data.get("postedTime"),
        formatted_price=credit_data.get("formattedPrice"),
        deal_price=deal_price,
    )


def _stations_block(response: dict[str, Any]) -> dict[str, Any]:
    """Return the ``stations`` dict from a locationBySearchTerm response.

    Defensive against the GraphQL spec's allowance of partial responses
    (``data: null``, missing keys, ``stations`` being null or a non-dict).
    Returns an empty dict when the expected shape isn't present so callers
    can downgrade to "no results" rather than crash.
    """
    data = response.get("data")
    if not isinstance(data, dict):
        return {}
    location = data.get("locationBySearchTerm")
    if not isinstance(location, dict):
        return {}
    stations = location.get("stations")
    return stations if isinstance(stations, dict) else {}


def parse_cursor(response: dict[str, Any]) -> str | None:
    """Extract the next-page cursor from a locationBySearchTerm response."""
    stations = _stations_block(response)
    cursor = stations.get("cursor")
    if not isinstance(cursor, dict):
        return None
    return cursor.get("next")


def parse_location_results(response: dict[str, Any]) -> LocationSearchResult:
    """Parse location search results into a LocationSearchResult."""
    stations = _stations_block(response)
    raw_results = stations.get("results") or []
    if not isinstance(raw_results, list):
        raw_results = []
    results = [
        cast(
            StationSummary,
            {
                "station_id": r["id"],
                "name": r.get("name") or "",
                "address": r.get("address") or {},
                "brands": r.get("brands") or [],
                "distance": parse_distance(r.get("distance")),
                "star_rating": r.get("starRating"),
                "ratings_count": r.get("ratingsCount"),
                "fuels": r.get("fuels") or [],
                "price_unit": r.get("priceUnit"),
            },
        )
        for r in raw_results
        if isinstance(r, dict) and "id" in r
    ]
    return cast(
        LocationSearchResult,
        {"results": results, "next_cursor": parse_cursor(response)},
    )


def parse_results(response: dict[str, Any], limit: int) -> list[StationPrice]:
    """Parse price-service API results into a StationPrice list."""
    result_list: list[StationPrice] = []
    raw_results = _stations_block(response).get("results") or []
    if not isinstance(raw_results, list):
        raw_results = []
    required_station_keys = {"id", "priceUnit", "currency", "latitude", "longitude"}
    results = [
        r
        for r in raw_results
        if isinstance(r, dict) and required_station_keys.issubset(r)
    ]

    for result in results[:limit]:
        raw: dict[str, Any] = {
            "station_id": result["id"],
            "name": result.get("name") or "",
            "unit_of_measure": result["priceUnit"],
            "currency": result["currency"],
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "image_url": result["brands"][0].get("imageUrl")
            if isinstance(result.get("brands"), list) and result["brands"]
            else None,
            "address": result.get("address") or {},
            "brands": result.get("brands") or [],
            "distance": parse_distance(result.get("distance")),
            "star_rating": result.get("starRating"),
            "ratings_count": result.get("ratingsCount"),
            "fuels": result.get("fuels") or [],
            "amenities": result.get("amenities") or [],
            "has_active_outage": bool(result.get("hasActiveOutage", False)),
            "hours": result.get("hours"),
            "open_status": result.get("openStatus"),
            "phone": result.get("phone") or None,
        }
        pay_status_obj = result.get("payStatus")
        is_pay_available = (pay_status_obj is None) or (
            isinstance(pay_status_obj, dict)
            and bool(pay_status_obj.get("isPayAvailable", False))
        )
        raw["pay_status"] = is_pay_available
        offers = [o for o in (result.get("offers") or []) if isinstance(o, dict)]
        discount_map = build_discount_map(offers) if is_pay_available else {}
        for price in result.get("prices") or []:
            if not isinstance(price, dict) or "fuelProduct" not in price:
                continue
            fuel_key = price["fuelProduct"]
            raw[fuel_key] = format_price_node(price, discount_map.get(fuel_key))
        result_list.append(cast(StationPrice, raw))
    return result_list


def parse_ev_stations(stations_data: Any) -> list[EvStation]:
    """Parse raw EV station dicts into EvStation list."""
    if not isinstance(stations_data, list):
        return []
    return [
        cast(
            EvStation,
            {
                "station_id": s["id"],
                "name": s.get("stationName") or "",
                "street_address": s.get("streetAddress"),
                "city": s.get("city"),
                "state": s.get("state"),
                "zip": s.get("zip"),
                "latitude": s.get("latitude"),
                "longitude": s.get("longitude"),
                "distance_miles": s.get("distanceMiles"),
                "status_code": s.get("statusCode"),
                "network": s.get("evNetwork"),
                "network_web": s.get("evNetworkWeb"),
                "level1_count": s.get("evLevel1EvseNum"),
                "level2_count": s.get("evLevel2EvseNum"),
                "dc_fast_count": s.get("evDcFastNum"),
                "pricing": s.get("evPricing"),
                "j1772_count": s.get("evJ1772ConnectorCount"),
                "j1772_power": s.get("evJ1772PowerOutput"),
                "ccs_count": s.get("evCcsConnectorCount"),
                "ccs_power": s.get("evCcsPowerOutput"),
                "chademo_count": s.get("evChademoConnectorCount"),
                "chademo_power": s.get("evChademoPowerOutput"),
                "nacs_count": s.get("evJ3400ConnectorCount"),
                "nacs_power": s.get("evJ3400PowerOutput"),
                "phone": s.get("stationPhone"),
                "access_hours": s.get("accessDaysTime"),
                "access_code": s.get("accessCode"),
                "cards_accepted": s.get("cardsAccepted"),
                "date_last_confirmed": s.get("dateLastConfirmed"),
            },
        )
        for s in stations_data
        if isinstance(s, dict) and "id" in s
    ]


def parse_trends(response: dict[str, Any]) -> list[TrendData]:
    """Parse price-service API results into a TrendData list."""
    data = response.get("data")
    if not isinstance(data, dict):
        return []
    location = data.get("locationBySearchTerm")
    if not isinstance(location, dict):
        return []
    trends = location.get("trends") or []
    if not isinstance(trends, list):
        return []
    return [
        TrendData(
            average_price=trend["today"],
            lowest_price=trend["todayLow"],
            area=trend["areaName"],
        )
        for trend in trends
        if isinstance(trend, dict)
        and "today" in trend
        and "todayLow" in trend
        and "areaName" in trend
    ]
