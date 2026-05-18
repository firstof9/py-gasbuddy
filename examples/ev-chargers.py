"""Find EV charging stations near a location via ChargeBuddy."""

import argparse
import asyncio
import logging

from py_gasbuddy import GasBuddy
from py_gasbuddy.consts import EV_CHARGING_LEVELS, EV_CONNECTOR_TYPES
from py_gasbuddy.exceptions import APIError, LibraryError

CONNECTOR_LABELS = {
    "j1772_count": "J1772 (L2)",
    "ccs_count": "CCS",
    "chademo_count": "CHAdeMO",
    "nacs_count": "NACS/Tesla",
}

LEVEL_LABELS = {
    "level1_count": "L1",
    "level2_count": "L2",
    "dc_fast_count": "DC Fast",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find EV chargers near a location")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lat", type=float, help="Latitude (requires --lon)")
    group.add_argument(
        "--bounds",
        nargs=4,
        metavar=("NE_LAT", "NE_LNG", "SW_LAT", "SW_LNG"),
        type=float,
        help="Bounding box search: NE_LAT NE_LNG SW_LAT SW_LNG",
    )
    parser.add_argument("--lon", type=float, help="Longitude (requires --lat)")
    parser.add_argument(
        "--radius", type=float, default=25, help="Search radius in miles (default: 25)"
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Max stations to return (default: 50)"
    )
    parser.add_argument(
        "--networks", help="Comma-separated network filter (default: all networks)"
    )
    parser.add_argument(
        "--connectors",
        default=EV_CONNECTOR_TYPES,
        help=f"Connector types (default: {EV_CONNECTOR_TYPES})",
    )
    parser.add_argument(
        "--levels",
        default=EV_CHARGING_LEVELS,
        help=f"Charging levels (default: {EV_CHARGING_LEVELS})",
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
    try:
        if args.bounds:
            ne_lat, ne_lng, sw_lat, sw_lng = args.bounds
            result = await gb.ev_stations_by_bounds(
                ne_lat=ne_lat,
                ne_lng=ne_lng,
                sw_lat=sw_lat,
                sw_lng=sw_lng,
                networks=args.networks,
                connector_types=args.connectors,
                charging_levels=args.levels,
                limit=args.limit,
            )
        else:
            result = await gb.ev_stations_nearby(
                lat=args.lat,
                lon=args.lon,
                radius=args.radius,
                networks=args.networks,
                connector_types=args.connectors,
                charging_levels=args.levels,
                limit=args.limit,
            )
    except (LibraryError, APIError) as e:
        raise SystemExit(f"Error fetching EV stations: {e}")

    stations = result["stations"]
    print(f"Found {result['total']} station(s) - showing {len(stations)}:\n")

    for i, s in enumerate(stations, 1):
        dist = s.get("distance_miles")
        dist_str = f"  {dist:.1f} mi" if dist is not None else ""
        print(f"Station {i}  [{s['station_id']}] {s['name']}{dist_str}")
        print(f"  Network  : {s.get('network') or 'Unknown'}")
        addr_parts = [
            s.get("street_address"),
            s.get("city"),
            s.get("state"),
            s.get("zip"),
        ]
        print(f"  Address  : {', '.join(p for p in addr_parts if p)}")

        # Connector breakdown
        connectors = [
            f"{CONNECTOR_LABELS[k]}: {s.get(k)}" for k in CONNECTOR_LABELS if s.get(k)
        ]
        if connectors:
            print(f"  Ports    : {' | '.join(connectors)}")

        # Charger level totals
        levels = [f"{LEVEL_LABELS[k]}: {s.get(k)}" for k in LEVEL_LABELS if s.get(k)]
        if levels:
            print(f"  Levels   : {' | '.join(levels)}")

        if s.get("pricing"):
            print(f"  Pricing  : {s['pricing']}")
        if s.get("access_hours"):
            print(f"  Hours    : {s['access_hours']}")
        if s.get("phone"):
            print(f"  Phone    : {s['phone']}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
