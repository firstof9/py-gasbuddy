![Codecov branch](https://img.shields.io/codecov/c/github/firstof9/py-gasbuddy/main?style=flat-square)
![GitHub commit activity (branch)](https://img.shields.io/github/commit-activity/m/firstof9/py-gasbuddy?style=flat-square)
![GitHub last commit](https://img.shields.io/github/last-commit/firstof9/py-gasbuddy?style=flat-square)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/firstof9/py-gasbuddy?style=flat-square)

# py-gasbuddy

Python async library for retrieving gas station data from the GasBuddy GraphQL API.

Provides three query methods covering single-station detail (prices, hours, amenities, offers), location-based station search, and a price-service query that returns prices plus regional trend data for nearby stations.

---

## Installation

```bash
pip install py-gasbuddy
```

---

## Quick Start

```python
import asyncio
from py_gasbuddy import GasBuddy

async def main():
    gb = GasBuddy(station_id=205033)
    data = await gb.price_lookup()
    print(data["name"], data["regular_gas"]["price"])

asyncio.run(main())
```

---

## GasBuddy Class

```python
GasBuddy(
    station_id: int | None = None,
    solver_url: str | None = None,
    cache_file: str = "",
    timeout: int = 60000,
    session: aiohttp.ClientSession | None = None,
)
```

| Parameter | Description |
|---|---|
| `station_id` | GasBuddy station ID — required for `price_lookup()` |
| `solver_url` | URL of a [FlareSolver](https://github.com/FlareSolverr/FlareSolverr) instance for Cloudflare bypass |
| `cache_file` | Path for the CSRF-token cache file (default: `py_gasbuddy/gasbuddy_cache`) |
| `timeout` | Request timeout in milliseconds (default: 60000) |
| `session` | Optional `aiohttp.ClientSession` to reuse — caller manages lifecycle |

### Cloudflare / FlareSolver

GasBuddy's homepage is protected by Cloudflare. The library extracts a CSRF token from the HTML before making GraphQL requests. If the direct fetch fails, pass a `solver_url` pointing to a running FlareSolver instance:

```python
gb = GasBuddy(station_id=205033, solver_url="http://localhost:8191/v1")
```

Tokens are cached on disk to avoid redundant solver calls across restarts.

---

## Methods

### `price_lookup() → StationPrice`

Returns full detail for a single station including prices, hours, amenities, brand, and offers. Requires `station_id` to be set at construction time.

```python
gb = GasBuddy(station_id=205033)
data = await gb.price_lookup()

# Station metadata
print(data["name"])           # "Wawa"
print(data["phone"])          # "610-555-0100"
print(data["open_status"])    # "open"
print(data["star_rating"])    # 4.2
print(data["ratings_count"])  # 38
print(data["pay_status"])     # True (GasBuddy Pay available)
print(data["fuels"])          # ["regular_gas", "midgrade_gas", "premium_gas"]

# Address
print(data["address"]["line1"])    # "123 Main St"
print(data["address"]["locality"]) # "Phoenixville"
print(data["address"]["region"])   # "PA"

# Brands
if data["brands"]:
    print(data["brands"][0]["name"])     # "Shell"
    print(data["brands"][0]["imageUrl"]) # logo URL

# Hours
print(data["hours"]["status"])       # "open"
print(data["hours"]["openingHours"]) # "24 Hours"

# Prices (credit and cash)
reg = data["regular_gas"]
print(reg["price"])           # 3.27  (credit price)
print(reg["cash_price"])      # 3.17  (None if not reported)
print(reg["formatted_price"]) # "$3.27"
print(reg["last_updated"])    # "2024-09-06T09:54:05Z"
print(reg["credit"])          # reporter nickname

# Emergency status (fuel/power outage reports)
print(data["emergency_status"]["hasGas"]["reportStatus"])  # None or "has_gas"

# Loyalty offers
for offer in data["offers"]:
    print(offer["id"], offer["types"], offer["use"])

# Amenities
for amenity in data["amenities"]:
    print(amenity["name"])  # "ATM", "Restrooms", etc.
```

**Fuel product keys** are dynamic and match whatever the station reports:
`regular_gas`, `midgrade_gas`, `premium_gas`, `diesel`, `e85`, `e15`, etc.

---

### `location_search(lat, lon, zipcode, brand_id, fuel, cursor) → LocationSearchResult`

Returns a dict with `results` (list of `StationSummary`) and optionally `next_cursor` for pagination. Pass either `lat`+`lon` or `zipcode`.

```python
# By ZIP code
result = await GasBuddy().location_search(zipcode=85396)

# By GPS coordinates
result = await GasBuddy().location_search(lat=33.465, lon=-112.505)

# Filter to diesel-only stations (fuel ID 4)
result = await GasBuddy().location_search(zipcode=85396, fuel=4)

# Filter to a specific brand (38 = Costco)
result = await GasBuddy().location_search(zipcode=85396, brand_id=38)

for s in result["results"]:
    print(s["station_id"], s["name"], s["distance"])
    print(s["address"]["locality"], s["address"]["region"])
    print(s["fuels"])

# Paginate
cursor = result.get("next_cursor")
if cursor:
    page2 = await GasBuddy().location_search(zipcode=85396, cursor=cursor)
```

**`StationSummary` fields:**

| Field | Type | Description |
|---|---|---|
| `station_id` | `str` | GasBuddy station identifier |
| `name` | `str` | Station/brand display name |
| `address` | `Address` | `line1`, `line2`, `locality`, `region`, `postalCode`, `country` |
| `brands` | `list[Brand]` | Brand name, `brandId`, logo `imageUrl` |
| `distance` | `float \| None` | Distance from search point (miles) |
| `star_rating` | `float \| None` | Community star rating |
| `ratings_count` | `int \| None` | Number of ratings |
| `fuels` | `list[str]` | Fuel products sold |
| `price_unit` | `str \| None` | `"dollars_per_gallon"` or `"cents_per_liter"` |

---

### `price_lookup_service(lat, lon, zipcode, limit, brand_id, fuel, cursor) → PriceServiceResult`

Returns prices for nearby stations plus regional trend data. Pass either `lat`+`lon` or `zipcode`. `limit` defaults to 5.

```python
result = await GasBuddy().price_lookup_service(zipcode=85396, limit=10)

for station in result["results"]:
    print(station["name"], station["distance"])
    if "regular_gas" in station:
        print(station["regular_gas"]["price"])
        print(station["regular_gas"]["formatted_price"])

# Regional trends
for trend in result.get("trend", []):
    print(trend["area"], trend["average_price"], trend["lowest_price"])

# Paginate
cursor = result.get("next_cursor")
if cursor:
    page2 = await GasBuddy().price_lookup_service(zipcode=85396, cursor=cursor)
```

Results have the same structure as `StationPrice` (see `price_lookup` above) minus station-only fields like `amenities`, `hours`, `offers`, and `pay_status`.

---

## Fuel Types

| Filter ID | Product key | Description |
|---|---|---|
| 1 | `regular_gas` | Regular (85-87 Octane) |
| 2 | `midgrade_gas` | Mid-Grade (89 Octane) |
| 3 | `premium_gas` | Premium (91-93 Octane) |
| 4 | `diesel` | Diesel |
| 5 | `e85` | E85 |
| 12 | `unl88` | Unleaded 88 (E15) |

The **filter ID** is the integer passed to the `fuel` parameter on `location_search` and `price_lookup_service`. The **product key** is the string used as a dictionary key in `StationPrice` results (e.g. `data["regular_gas"]`). Both are also available as `FUEL_FILTER_IDS` and `FUEL_PRODUCTS` in `py_gasbuddy.consts`.

---

## Data Models

All return types are `TypedDict` subclasses defined in `py_gasbuddy.models`.

### `PriceNode`

```python
class PriceNode(TypedDict):
    credit: str | None          # reporter nickname
    price: float | None         # credit price (None = not reported)
    cash_price: float | None    # cash price (None = not reported)
    last_updated: str | None    # ISO 8601 timestamp
    formatted_price: str | None # "$3.27" or "131.9¢"
    deal_price: float | None    # price after GasBuddy Pay discount (None if no offer or no price)
```

`deal_price` is computed from the `pwgbDiscount` field returned by the GasBuddy GraphQL API, which covers the Flash Deal and GasBuddy+ Member Savings components. The Card Savings Boost (available to GasBuddy+ members who select Fleet Card at the pump) is sourced from the mobile REST API and is not included here, so `deal_price` may be slightly higher than what the GasBuddy app displays for GasBuddy+ members.

### `TrendData`

```python
class TrendData(TypedDict):
    area: str            # "Arizona" or "United States"
    average_price: float # today's average
    lowest_price: float  # today's lowest (0 if not available)
```

---

## Error Handling

| Exception | Raised when |
|---|---|
| `MissingSearchData` | `location_search` or `price_lookup_service` called without coordinates or ZIP |
| `LibraryError` | Network or parse error; check logs for details |
| `APIError` | GasBuddy's GraphQL returned an errors field |

```python
from py_gasbuddy.exceptions import APIError, LibraryError, MissingSearchData

try:
    data = await gb.price_lookup()
except LibraryError:
    print("Network or token error")
except APIError:
    print("GasBuddy API error")
```

---

## Cache Management

```python
# Clear the cached CSRF token (forces a fresh fetch on next request)
await gb.clear_cache()
```

---

## Examples

See the [`examples/`](examples/) directory for runnable scripts:

| Script | Description |
|---|---|
| `price-lookup.py` | Full station detail by station ID |
| `price-lookup-service.py` | Nearby prices + trends by ZIP or GPS |
| `location-search.py` | Station list (no prices) by ZIP or GPS |
| `ev-chargers.py` | EV charger locations and status (CLI) |
