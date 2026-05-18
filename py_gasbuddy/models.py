"""Type definitions for py-gasbuddy."""

from typing import Any, Required, TypedDict


class Address(TypedDict, total=False):
    """Station address."""

    line1: Required[str]
    line2: str | None
    locality: str
    region: str
    postalCode: str
    country: str


class Brand(TypedDict):
    """Station brand info."""

    brandId: int | str | None
    brandingType: str | None
    imageUrl: str | None
    name: str | None


class Amenity(TypedDict):
    """Station amenity."""

    amenityId: int
    imageUrl: str | None
    name: str


class HoursInterval(TypedDict):
    """A single open/close interval."""

    open: str | None
    close: str | None


class Hours(TypedDict, total=False):
    """Station operating hours."""

    openingHours: str | None
    status: str | None
    nextIntervals: list[HoursInterval]


class EmergencyReport(TypedDict, total=False):
    """Emergency fuel/power availability report."""

    nickname: str | None
    reportStatus: str | None
    updateDate: str | None
    stamp: str | None


class EmergencyStatus(TypedDict, total=False):
    """Emergency status for gas, diesel, and power."""

    hasGas: EmergencyReport
    hasPower: EmergencyReport
    hasDiesel: EmergencyReport


class Discount(TypedDict, total=False):
    """Price discount details."""

    grades: list[str]
    highlight: str | None
    pwgbDiscount: float | None
    receiptDiscount: float | None


class Offer(TypedDict, total=False):
    """Station offer/discount program."""

    discounts: list[Discount]
    highlight: str | None
    id: str
    types: list[str]
    use: list[str]


class PriceNode(TypedDict):
    """Price data for a single fuel type."""

    credit: str | None
    cash_price: float | None
    price: float | None
    last_updated: str | None
    formatted_price: str | None
    deal_price: float | None


class StationPrice(TypedDict, total=False):
    """Full station data including prices — returned by price_lookup()."""

    station_id: Required[str]
    name: Required[str]
    unit_of_measure: Required[str]
    currency: Required[str]
    latitude: Required[float]
    longitude: Required[float]
    image_url: Required[str | None]
    address: Address
    brands: list[Brand]
    amenities: list[Amenity]
    hours: Hours | None
    phone: str | None
    open_status: str | None
    fuels: list[str]
    star_rating: float | None
    ratings_count: int | None
    is_fuelman_site: bool
    has_active_outage: bool
    enterprise: bool
    emergency_status: EmergencyStatus | None
    offers: list[Offer]
    pay_status: bool
    regular_gas: PriceNode
    midgrade_gas: PriceNode
    premium_gas: PriceNode
    diesel: PriceNode
    # e85, e15, and other fuel types are dynamic keys


class StationSummary(TypedDict, total=False):
    """Station summary — returned by location_search() (no prices)."""

    station_id: Required[str]
    name: Required[str]
    address: Address
    brands: list[Brand]
    distance: float | None
    star_rating: float | None
    ratings_count: int | None
    fuels: list[str]
    price_unit: str | None


class TrendData(TypedDict):
    """Regional price trend data."""

    average_price: float
    lowest_price: float
    area: str


class LocationSearchResult(TypedDict, total=False):
    """Result from location_search()."""

    results: Required[list[StationSummary]]
    next_cursor: str | None


class PriceServiceResult(TypedDict, total=False):
    """Result from price_lookup_service."""

    results: Required[list[StationPrice]]
    trend: list[TrendData]
    next_cursor: str | None


class EvStation(TypedDict, total=False):
    """EV charging station — returned by ev_stations_nearby / ev_stations_by_bounds."""

    station_id: Required[str]
    name: Required[str]
    street_address: str | None
    city: str | None
    state: str | None
    zip: str | None
    latitude: float | None
    longitude: float | None
    distance_miles: float | None
    status_code: str | None
    network: str | None
    network_web: str | None
    level1_count: int | None
    level2_count: int | None
    dc_fast_count: int | None
    pricing: str | None
    j1772_count: int | None
    j1772_power: str | None
    ccs_count: int | None
    ccs_power: str | None
    chademo_count: int | None
    chademo_power: str | None
    nacs_count: int | None
    nacs_power: str | None
    phone: str | None
    access_hours: str | None
    access_code: str | None
    cards_accepted: str | None
    date_last_confirmed: str | None


class EvStationResult(TypedDict):
    """Result from ev_stations_nearby / ev_stations_by_bounds."""

    stations: list[EvStation]
    total: int


class GraphQLQuery(TypedDict):
    """GraphQL query payload."""

    operationName: str
    query: str
    variables: dict[str, Any]
