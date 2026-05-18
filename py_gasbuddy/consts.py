"""Constants for the py-gasbuddy GraphQL library."""

BASE_URL = "https://www.gasbuddy.com/graphql"
GB_HOME_URL = "https://www.gasbuddy.com/home"

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Sec-Fetch-Dest": "",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Priority": "u=0",
    "apollo-require-preflight": "true",
    "Origin": "https://www.gasbuddy.com",
    "Referer": GB_HOME_URL,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
}

TOKEN = "token"
TOKEN_SKIP = "Already have token and last call was successful. Skipping token search."

# Fuel product keys returned by the API in the `fuels` list and as PriceNode keys.
FUEL_PRODUCTS: dict[str, str] = {
    "regular_gas": "Regular (85-87 Octane)",
    "midgrade_gas": "Mid-Grade (89 Octane)",
    "premium_gas": "Premium (91-93 Octane)",
    "diesel": "Diesel",
    "e85": "E85",
    "unl88": "Unleaded 88 (E15)",
}

# Integer IDs used by the `fuel` filter variable in LocationBySearchTerm.
# Values sourced from GasBuddy's searchFuelType HTML select element.
FUEL_FILTER_IDS: dict[str, int] = {
    "regular_gas": 1,
    "midgrade_gas": 2,
    "premium_gas": 3,
    "diesel": 4,
    "e85": 5,
    "unl88": 12,
}

EV_ALL_NETWORKS = (
    "7Charge,ABM,AmpedUp_Networks,AmpUp,applegreen_electric,Autel,BC_Hydro,Blink,"
    "bp_pulse,Chaevi,ChargeLab,ChargeNet,ChargePoint,ChargeSmart_EV,ChargeUP,Chargie,"
    "CircleK_Charge,CircleK_Couche_Tard_Recharge,Circuit_electrique,DirtRoad,"
    "eCharge_Network,Electric_Era,Electrify_America,Electrify_Canada,Enel_X_Way,"
    "EnviroSpark,Epic_Charging,EVBOLT,EV_Connect,EVCS,EvGateway,EVgo,EVIUM_Charging,"
    "EVmatch,Evoke_Systems,EVPassport,eVPower,EV_Range,EVXY,ezVOLTz,FLASH,Flipturn,"
    "Flitway,FLO,Ford_Charge,FPL_EVolution,Francis_Energy,GO_TO_U,Graviti_Energy,"
    "Gravity_Charging_Center,HoneyBadger_Charging,Hwisel,Hyperfuel,InCharge,IONNA,"
    "Ivy,Jule,Kwik_Charge,Lakeland_EV_CHARGING,Loop,Matcha_Electric,Mercedes_Benz_HPC,"
    "Non_Networked,Noodoe,OBE_Power,On_the_Run_EV,OpConnect,Petro_Canada,PowerCharge,"
    "PowerFlex,PowerPort_EVC,PowerPump,QuickCharge,Red_E_Charge,Revel,"
    "Revitalize_Charging,Rivian_Adventure_Network,Rivian_Waypoints,Rove,SemaConnect,"
    "Shell_Recharge,Stay_N_Charge,Sun_Country_Highway,SWTCH_Energy,Tesla,"
    "Tesla_Destination,TurnOnGreen,Universal_EV_Chargers,ViaLynk,Volta,Walmart,"
    "WattEV,WAVE,Xeal_EV_Charging,ZEF_Network"
)

EV_CONNECTOR_TYPES = "J1772,J1772COMBO,CHADEMO,TESLA"

EV_CHARGING_LEVELS = "DCFast,Level2,Level1"

EV_STATIONS_NEARBY_QUERY = """
query EvStationsSearch(
  $latitude: Float!
  $longitude: Float!
  $radius: Float
  $networks: String
  $connectorTypes: String
  $chargingLevels: String
  $cardsAccepted: String
  $accessCode: String
  $limit: Int
) {
  evStationsNearby(
    latitude: $latitude
    longitude: $longitude
    radius: $radius
    networks: $networks
    connectorTypes: $connectorTypes
    chargingLevels: $chargingLevels
    cardsAccepted: $cardsAccepted
    accessCode: $accessCode
    limit: $limit
  ) {
    stations {
      id
      stationName
      streetAddress
      city
      state
      zip
      latitude
      longitude
      distanceMiles
      statusCode
      evNetwork
      evNetworkWeb
      evLevel1EvseNum
      evLevel2EvseNum
      evDcFastNum
      evPricing
      evJ1772ConnectorCount
      evJ1772PowerOutput
      evCcsConnectorCount
      evCcsPowerOutput
      evChademoConnectorCount
      evChademoPowerOutput
      evJ3400ConnectorCount
      evJ3400PowerOutput
      stationPhone
      accessDaysTime
      accessCode
      cardsAccepted
      dateLastConfirmed
    }
    total
    limit
  }
}
""".strip()

EV_STATIONS_BOUNDS_QUERY = """
query EvStationsByBounds(
  $northEastLat: Float!
  $northEastLng: Float!
  $southWestLat: Float!
  $southWestLng: Float!
  $networks: String
  $connectorTypes: String
  $chargingLevels: String
  $cardsAccepted: String
  $accessCode: String
  $limit: Int
) {
  evStationsByBounds(
    northEastLat: $northEastLat
    northEastLng: $northEastLng
    southWestLat: $southWestLat
    southWestLng: $southWestLng
    networks: $networks
    connectorTypes: $connectorTypes
    chargingLevels: $chargingLevels
    cardsAccepted: $cardsAccepted
    accessCode: $accessCode
    limit: $limit
  ) {
    stations {
      id
      stationName
      streetAddress
      city
      state
      zip
      latitude
      longitude
      distanceMiles
      statusCode
      evNetwork
      evNetworkWeb
      evLevel1EvseNum
      evLevel2EvseNum
      evDcFastNum
      evPricing
      evJ1772ConnectorCount
      evJ1772PowerOutput
      evCcsConnectorCount
      evCcsPowerOutput
      evChademoConnectorCount
      evChademoPowerOutput
      evJ3400ConnectorCount
      evJ3400PowerOutput
      stationPhone
      accessDaysTime
      accessCode
      cardsAccepted
      dateLastConfirmed
    }
    total
    limit
  }
}
""".strip()

GAS_PRICE_QUERY = """
query GetStation($id: ID!) {
  station(id: $id) {
    id
    name
    phone
    openStatus
    priceUnit
    currency
    latitude
    longitude
    enterprise
    fuels
    hasActiveOutage
    isFuelmanSite
    starRating
    ratingsCount
    address {
      country
      line1
      line2
      locality
      postalCode
      region
    }
    brands {
      brandId
      brandingType
      imageUrl
      name
    }
    amenities {
      amenityId
      imageUrl
      name
    }
    hours {
      openingHours
      status
      nextIntervals {
        close
        open
      }
    }
    emergencyStatus {
      hasGas {
        nickname
        reportStatus
        updateDate
        stamp
      }
      hasPower {
        nickname
        reportStatus
        updateDate
        stamp
      }
      hasDiesel {
        nickname
        reportStatus
        updateDate
        stamp
      }
    }
    prices {
      cash {
        nickname
        postedTime
        price
        formattedPrice
      }
      credit {
        nickname
        postedTime
        price
        formattedPrice
      }
      fuelProduct
      longName
    }
    offers {
      discounts {
        grades
        highlight
        pwgbDiscount
        receiptDiscount
      }
      highlight
      id
      types
      use
    }
    payStatus {
      isPayAvailable
    }
  }
}
""".strip()

LOCATION_QUERY = """
query LocationBySearchTerm(
  $brandId: Int
  $cursor: String
  $fuel: Int
  $lat: Float
  $lng: Float
  $maxAge: Int
  $search: String
) {
  locationBySearchTerm(
    lat: $lat
    lng: $lng
    search: $search
    priority: "locality"
  ) {
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
      priority: "locality"
    ) {
      count
      cursor {
        next
      }
      results {
        address {
          country
          line1
          line2
          locality
          postalCode
          region
        }
        brands {
          brandId
          brandingType
          imageUrl
          name
        }
        distance
        fuels
        id
        name
        priceUnit
        ratingsCount
        starRating
      }
    }
  }
}
""".strip()

LOCATION_QUERY_PRICES = """
query LocationBySearchTerm(
  $brandId: Int
  $cursor: String
  $fuel: Int
  $lat: Float
  $lng: Float
  $maxAge: Int
  $search: String
) {
  locationBySearchTerm(
    lat: $lat
    lng: $lng
    search: $search
    priority: "locality"
  ) {
    stations(
      brandId: $brandId
      cursor: $cursor
      fuel: $fuel
      lat: $lat
      lng: $lng
      maxAge: $maxAge
      priority: "locality"
    ) {
      cursor {
        next
      }
      results {
        address {
          country
          line1
          line2
          locality
          postalCode
          region
        }
        brands {
          brandId
          brandingType
          imageUrl
          name
        }
        distance
        fuels
        id
        latitude
        longitude
        name
        priceUnit
        currency
        ratingsCount
        starRating
        prices {
          cash {
            nickname
            postedTime
            price
            formattedPrice
          }
          credit {
            nickname
            postedTime
            price
            formattedPrice
          }
          fuelProduct
          longName
        }
        offers {
          discounts {
            grades
            highlight
            pwgbDiscount
            receiptDiscount
          }
          highlight
          id
          types
          use
        }
      }
    }
    trends {
      areaName
      country
      today
      todayLow
      trend
    }
  }
}
""".strip()
