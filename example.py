# gasbuddy_example.py
# make sure to run pip install -f requirements_example.txt before running this

import asyncio
import gasbuddy


async def main():
    """
    This script demonstrates basic usage of the gasbuddy library.
    It retrieves stations for a specified zip code,
    and prints the results.
    """

    try:
        # Specify the zip code to search for
        zip_code = "90210"  # Example zip code - Beverly Hills, CA

        # Initialize the GasBuddy API client
        gb = gasbuddy.GasBuddy()

        # Initialize the GasBuddy API client
        stations = await gb.location_search(zipcode=zip_code)

        if stations:
            print(f"Stations for Zip Code {zip_code}:")
            for station in stations["data"]["locationBySearchTerm"]["stations"][
                "results"
            ]:
                print(f"  - Station: {station["name"]}")
                print(f"    Address: {station["address"]["line1"]}")
                print(f"    ID: {station["id"]}")
                print("-" * 20)
        else:
            print(f"No stations found for zip code {zip_code}.")

    except gasbuddy.MissingSearchData as e:
        print(f"An error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
