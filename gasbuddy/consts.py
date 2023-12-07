"""Constants for the py-gasbuddy GraphQL library."""
# flake8: noqa
BASE_URL = "https://www.gasbuddy.com/graphql"

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
}
# pylint: disable-next=line-too-long
GAS_PRICE_QUERY = "query GetStation($id: ID!) { station(id: $id) { prices { credit { nickname postedTime price } fuelProduct longName } priceUnit } }"  # pylint: disable-next=line-too-long
LOCATION_QUERY = """
query LocationBySearchTerm($brandId: Int, $cursor: String, $fuel: Int, $lat: Float, $lng: Float, $maxAge: Int, $search: String) {
  locationBySearchTerm(lat: $lat, lng: $lng, search: $search) {
    countryCode
    displayName
    latitude
    longitude
    regionCode
    stations(
      brandId: $brandId
      cursor: $cursor
      fuel: $fuel
      lat: $lat
      lng: $lng
      maxAge: $maxAge
    ) {
      count
      cursor {
        next
        __typename
      }
      results {
        address {
          country
          line1
          line2
          locality
          postalCode
          region
          __typename
        }
        distance
        enterprise
        fuels
        id
        name
        prices {
          cash {
            nickname
            postedTime
            price
            formattedPrice
            __typename
          }
          credit {
            nickname
            postedTime
            price
            formattedPrice
            __typename
          }
          discount
          fuelProduct
          __typename
        }
        priceUnit
        __typename
      }
      __typename
    }
    __typename
  }
}
"""
