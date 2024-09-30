"""Constants for the py-gasbuddy GraphQL library."""

# flake8: noqa
BASE_URL = "https://www.gasbuddy.com/graphql"

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
}
# pylint: disable-next=line-too-long
GAS_PRICE_QUERY = "query GetStation($id: ID!) { station(id: $id) { brands { imageUrl } prices { cash { nickname postedTime price } credit { nickname postedTime price } fuelProduct longName } priceUnit currency id latitude longitude } }"  # pylint: disable-next=line-too-long
LOCATION_QUERY = "query LocationBySearchTerm($brandId: Int, $cursor: String, $fuel: Int, $lat: Float, $lng: Float, $maxAge: Int, $search: String) { locationBySearchTerm(lat: $lat, lng: $lng, search: $search) { stations(brandId: $brandId cursor: $cursor fuel: $fuel lat: $lat lng: $lng maxAge: $maxAge) { count results { address { line1 } id name } } } }"
