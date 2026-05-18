"""Get fuel prices for multiple stations near a location, with regional trends."""

import argparse
import asyncio
import logging

from py_gasbuddy import GasBuddy, MissingSearchData
from py_gasbuddy.consts import FUEL_FILTER_IDS
from py_gasbuddy.exceptions import APIError, LibraryError

FUEL_LABELS = {
    "regular_gas": "Regular",
    "midgrade_gas": "Midgrade",
    "premium_gas": "Premium",
    "diesel": "Diesel",
    "e85": "E85",
    "e15": "E15",
}

# Reverse map: integer fuel ID → fuel product key
FUEL_KEY_BY_ID = {v: k for k, v in FUEL_FILTER_IDS.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Get prices for multiple stations near a location"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--zipcode", type=int, help="ZIP code to search")
    group.add_argument("--lat", type=float, help="Latitude (requires --lon)")
    parser.add_argument("--lon", type=float, help="Longitude (requires --lat)")
    parser.add_argument(
        "--limit", type=int, default=5, help="Max stations per page (default: 5)"
    )
    parser.add_argument("--brand-id", type=int, help="Filter by GasBuddy brand ID")
    parser.add_argument(
        "--fuel",
        type=int,
        help="Fuel type ID: 1=Regular 2=Midgrade 3=Premium 4=Diesel 5=E85 12=UNL88",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="Number of result pages to fetch (default: 1, ~20 stations/page)",
    )
    parser.add_argument(
        "--sort",
        choices=["credit", "cash", "deal", "best"],
        help="Sort by cheapest price for --fuel (best=lowest of credit/cash/deal)",
    )
    parser.add_argument(
        "--solver-url", help="FlareSolver URL (e.g. http://10.0.30.8:8191/v1)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.lat is not None and args.lon is None:
        raise SystemExit("--lon is required when --lat is provided")

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    gb = GasBuddy(solver_url=args.solver_url)
    all_stations = []
    trends = []
    cursor = None

    for page in range(args.pages):
        try:
            if args.zipcode:
                result = await gb.price_lookup_service(
                    zipcode=args.zipcode,
                    limit=args.limit,
                    brand_id=args.brand_id,
                    fuel=args.fuel,
                    cursor=cursor,
                )
            else:
                result = await gb.price_lookup_service(
                    lat=args.lat,
                    lon=args.lon,
                    limit=args.limit,
                    brand_id=args.brand_id,
                    fuel=args.fuel,
                    cursor=cursor,
                )
        except MissingSearchData:
            raise SystemExit("No search parameters provided.")
        except (LibraryError, APIError) as e:
            raise SystemExit(f"Error fetching prices: {e}")

        all_stations.extend(result["results"])
        if not trends and "trend" in result:
            trends = result["trend"]
        cursor = result.get("next_cursor")
        if not cursor:
            if page < args.pages - 1:
                print(f"(No more pages after page {page + 1})")
            break

    effective_sort = args.sort or ("best" if args.fuel is not None else None)

    if effective_sort:
        if args.fuel is None:
            print("Warning: --sort requires --fuel; results shown in default order.\n")
        else:
            fuel_key = FUEL_KEY_BY_ID.get(args.fuel)
            if fuel_key:
                if effective_sort == "best":

                    def sort_key(s: dict) -> float:
                        node = s.get(fuel_key) or {}
                        candidates = [
                            node.get("deal_price"),
                            node.get("cash_price"),
                            node.get("price"),
                        ]
                        prices = [p for p in candidates if p is not None]
                        return min(prices) if prices else float("inf")
                elif effective_sort == "deal":

                    def sort_key(s: dict) -> float:
                        node = s.get(fuel_key) or {}
                        return (
                            node.get("deal_price")
                            or node.get("cash_price")
                            or node.get("price")
                            or float("inf")
                        )
                else:
                    price_field = {
                        "credit": "price",
                        "cash": "cash_price",
                    }[effective_sort]

                    def sort_key(s: dict) -> float:
                        return (s.get(fuel_key) or {}).get(price_field) or float("inf")

                all_stations.sort(key=sort_key)

    for i, station in enumerate(all_stations, 1):
        addr = station.get("address", {})
        city = addr.get("locality", "")
        region = addr.get("region", "")
        line1 = addr.get("line1", "")
        dist = station.get("distance")
        dist_str = f"  {dist:.1f} mi" if dist is not None else ""
        rating = station.get("star_rating")
        rating_str = f"  {rating}/5" if rating else ""

        print(
            f"Station {i}  [{station['station_id']}] {station.get('name', '')}"
            f"{dist_str}{rating_str}"
        )
        print(f"  Address  : {line1}, {city}, {region}")
        print(
            f"  Currency : {station['currency']}  |  Unit: {station['unit_of_measure']}"
        )

        for key, label in FUEL_LABELS.items():
            if key not in station:
                continue
            node = station[key]  # type: ignore[literal-required]
            price = node.get("price")
            cash = node.get("cash_price")
            raw_fmt = node.get("formatted_price") or ""
            fmt = raw_fmt.encode("ascii", "replace").decode()
            if price is None and cash is None:
                continue
            parts = []
            if price is not None:
                parts.append(f"credit {fmt or f'${price:.2f}'}")
            if cash is not None:
                parts.append(f"cash ${cash:.2f}")
            deal = node.get("deal_price")
            if deal is not None:
                parts.append(f"deal ${deal:.2f}")
            print(f"  {label:<12}: {' / '.join(parts)}")
        print()

    if trends:
        print("Regional Trends:")
        for trend in trends:
            print(f"  {trend['area']}")
            print(f"    Average : ${trend['average_price']:.3f}")
            if trend["lowest_price"]:
                print(f"    Lowest  : ${trend['lowest_price']:.3f}")
        print()

    if cursor:
        print(f"More results available. Next cursor: {cursor}")


if __name__ == "__main__":
    asyncio.run(main())
