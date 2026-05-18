"""Get current fuel prices and station detail for a specific GasBuddy station."""

import argparse
import asyncio
import logging

from py_gasbuddy import GasBuddy
from py_gasbuddy.exceptions import APIError, LibraryError

FUEL_LABELS = {
    "regular_gas": "Regular",
    "midgrade_gas": "Midgrade",
    "premium_gas": "Premium",
    "diesel": "Diesel",
    "e85": "E85",
    "e15": "E15",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Look up fuel prices for a station")
    parser.add_argument(
        "--station-id", type=int, required=True, help="GasBuddy station ID"
    )
    parser.add_argument(
        "--solver-url", help="FlareSolver URL (e.g. http://10.0.30.8:8191/v1)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    gb = GasBuddy(station_id=args.station_id, solver_url=args.solver_url)
    try:
        data = await gb.price_lookup()
    except (LibraryError, APIError) as e:
        raise SystemExit(f"Error fetching prices: {e}")

    # Station identity
    addr = data.get("address", {})
    city = addr.get("locality", "")
    region = addr.get("region", "")
    line1 = addr.get("line1", "")
    brands = data.get("brands", [])
    brand_name = brands[0]["name"] if brands else ""

    print(f"Station    : {data['name']}  (ID: {data['station_id']})")
    if brand_name and brand_name != data["name"]:
        print(f"Brand      : {brand_name}")
    if data.get("phone"):
        print(f"Phone      : {data['phone']}")
    print(f"Address    : {line1}, {city}, {region}")
    print(f"GPS        : {data['latitude']}, {data['longitude']}")
    print(f"Currency   : {data['currency']}  |  Unit: {data['unit_of_measure']}")

    # Hours / status
    hours = data.get("hours") or {}
    open_status = data.get("open_status", "unknown")
    opening_hours = hours.get("openingHours", "")
    print(f"Status     : {open_status}  ({opening_hours})")

    # Ratings
    rating = data.get("star_rating")
    count = data.get("ratings_count")
    if rating is not None:
        print(f"Rating     : {rating}/5  ({count} reviews)")

    # GasBuddy Pay
    if data.get("pay_status"):
        print("GasBuddy Pay: available")

    # Amenities
    amenities = [a["name"] for a in (data.get("amenities") or [])]
    if amenities:
        print(f"Amenities  : {', '.join(amenities)}")

    print()

    # Fuel prices
    for key, label in FUEL_LABELS.items():
        if key not in data:
            continue
        node = data[key]  # type: ignore[literal-required]
        price = node.get("price")
        cash = node.get("cash_price")
        fmt = (node.get("formatted_price") or "").encode("ascii", "replace").decode()
        updated = node.get("last_updated", "unknown")
        if price is None and cash is None:
            continue
        print(f"  {label}")
        if price is not None:
            print(f"    Credit : {fmt or f'{price:.3f}'}")
        if cash is not None:
            cash_fmt = f"${cash:.3f}"
            print(f"    Cash   : {cash_fmt}")
        deal = node.get("deal_price")
        if deal is not None:
            print(f"    Deal   : ${deal:.2f}  (after GasBuddy Pay discount)")
        print(f"    Updated: {updated}")
        print()

    # Loyalty offers
    offers = data.get("offers") or []
    if offers:
        print("Offers:")
        for offer in offers:
            types = ", ".join(offer.get("types") or [])
            use = offer.get("use", "")
            for disc in offer.get("discounts") or []:
                grades = ", ".join(disc.get("grades") or [])
                discount = disc.get("pwgbDiscount")
                if discount:
                    print(f"  {types} ({use}): ${float(discount):.2f}/gal off {grades}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
