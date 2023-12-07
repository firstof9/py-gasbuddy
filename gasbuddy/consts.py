"""Constants for the py-gasbuddy GraphQL library."""

BASE_URL = "https://www.gasbuddy.com/graphql"

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
}

GAS_PRICE_QUERY = "query GetStation($id: ID!) { station(id: $id) { prices { credit { nickname postedTime price } fuelProduct longName } priceUnit } }"
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
        badges {
          badgeId
          callToAction
          campaignId
          clickTrackingUrl
          description
          detailsImageUrl
          detailsImpressionTrackingUrls
          imageUrl
          impressionTrackingUrls
          targetUrl
          title
          __typename
        }
        brandings {
          brandId
          brandingType
          __typename
        }
        brands {
          brandId
          imageUrl
          name
          __typename
        }
        distance
        emergencyStatus {
          hasDiesel {
            nickname
            reportStatus
            updateDate
            __typename
          }
          hasGas {
            nickname
            reportStatus
            updateDate
            __typename
          }
          hasPower {
            nickname
            reportStatus
            updateDate
            __typename
          }
          __typename
        }
        enterprise
        fuels
        id
        name
        offers {
          discounts {
            grades
            highlight
            pwgbDiscount
            receiptDiscount
            __typename
          }
          highlight
          id
          types
          use
          __typename
        }
        payStatus {
          isPayAvailable
          __typename
        }
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
        ratingsCount
        starRating
        __typename
      }
      __typename
    }
    trends {
      areaName
      country
      today
      todayLow
      trend
      __typename
    }
    __typename
  }
}
"""
