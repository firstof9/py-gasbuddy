"""Find GasBuddy stations by ZIP code or coordinates."""

import argparse
import asyncio
import logging

from py_gasbuddy import GasBuddy, MissingSearchData
from py_gasbuddy.exceptions import APIError, LibraryError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search for GasBuddy stations")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--zipcode", type=int, help="ZIP code to search")
    group.add_argument("--lat", type=float, help="Latitude (requires --lon)")
    parser.add_argument("--lon", type=float, help="Longitude (requires --lat)")
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
    cursor = None

    for page in range(args.pages):
        try:
            if args.zipcode:
                result = await gb.location_search(
                    zipcode=args.zipcode,
                    brand_id=args.brand_id,
                    fuel=args.fuel,
                    cursor=cursor,
                )
            else:
                result = await gb.location_search(
                    lat=args.lat,
                    lon=args.lon,
                    brand_id=args.brand_id,
                    fuel=args.fuel,
                    cursor=cursor,
                )
        except MissingSearchData:
            raise SystemExit("No search parameters provided.")
        except (LibraryError, APIError) as e:
            raise SystemExit(f"Error fetching stations: {e}")

        all_stations.extend(result["results"])
        cursor = result.get("next_cursor")
        if not cursor:
            if page < args.pages - 1:
                print(f"(No more pages after page {page + 1})")
            break

    print(f"Found {len(all_stations)} station(s):\n")
    for s in all_stations:
        addr = s.get("address", {})
        city = addr.get("locality", "")
        region = addr.get("region", "")
        line1 = addr.get("line1", "")
        brands = s.get("brands", [])
        brand_name = brands[0]["name"] if brands else s.get("name", "")
        dist = s.get("distance")
        dist_str = f"  {dist:.1f} mi" if dist is not None else ""
        rating = s.get("star_rating")
        rating_str = f"  {rating}/5" if rating else ""
        fuels = ", ".join(s.get("fuels") or [])
        print(f"  [{s['station_id']}] {s['name']}{dist_str}{rating_str}")
        if brand_name and brand_name != s["name"]:
            print(f"    Brand   : {brand_name}")
        print(f"    Address : {line1}, {city}, {region}")
        if fuels:
            print(f"    Fuels   : {fuels}")
        print()

    if cursor:
        print(f"More results available. Next cursor: {cursor}")


if __name__ == "__main__":
    asyncio.run(main())
