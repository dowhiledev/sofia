import os
import requests
from typing import List, Literal, Optional

# from dotenv import load_dotenv

# load_dotenv(os.path.join(os.path.dirname(__file__), ".env.local"))

REPLIERS_API_KEY = os.getenv("REPLIERS_API_KEY")
assert (
    REPLIERS_API_KEY
), "REPLIERS-API-KEY must be set in the environment variables"
headers = {
    "REPLIERS-API-KEY": REPLIERS_API_KEY,
    "Content-Type": "application/json",
}
base_url = "https://api.repliers.io"
num_results_per_page = os.getenv("REPLIERS-API-NUM-RESULTS-PER-PAGE", 15)


# Allowed property types
PropertyType = Literal[
    "All",
    "Detached",
    "Semi-Detached",
    "Freehold Townhouse",
    "Condo Townhouse",
    "Condo Apt",
    "Multiplex",
    "Vacant Land",
]

# Basement types
BasementType = Literal["All", "Finished", "Walkout", "Seperate Entrance"]

# Listing status
Status = Literal["Active", "Sold", "All"]

# Period for sold/delisted status, e.g.: last 7 days, 90 days, etc.
Period = Literal["7D", "90D", "All"]

# Integer or the literal "5+" for upper bound filters
FivePlusInt = Literal[1, 2, 3, 4, "5+", "All"]

# Sort options for listings
SortBy = Literal[
    "Default", "Newest", "Oldest", "Price Low to High", "Price High to Low"
]

def simplify_listing_response(response: dict) -> dict:
    """Simplify the listing response to only include essential fields."""
    response_copy = response.copy()
    listing_id = response_copy.get("mlsNumber")
    board_id = response_copy.get("boardId")
    if not listing_id or not board_id:
        raise ValueError("Listing ID (mlsNumber) and Board ID (boardId) are required in the response.")
    response_copy["listing_id"] = listing_id
    response_copy["board_id"] = board_id
    for key in ["comparables", "images", "photoCount", "map", "resource", "openHouse", "timestamps", "mlsNumber", "boardId", "history"]:
        response_copy.pop(key, None)
    response_copy = remove_null_fields(response_copy)
    return response_copy

def remove_null_fields(data: dict) -> dict:
    """Recursively remove fields with null values from a dictionary, including nested dictionaries and lists."""
    if isinstance(data, dict):
        return {k: remove_null_fields(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [remove_null_fields(item) for item in data if item is not None]
    else:
        return data

def get_listings(
    area: Optional[str] = None,
    city: Optional[List[str]] = None,
    district: Optional[str] = None,
    property_types: Optional[list[PropertyType]] = None,
    status: Optional[Status] = None,
    # status_period: Optional[Period] = None,
    bedrooms: Optional[List[FivePlusInt]] = None,
    bathrooms: Optional[List[FivePlusInt]] = None,
    den: Optional[Literal["Yes", "No", "All"]] = None,
    parking: Optional[List[FivePlusInt]] = None,
    keyword: Optional[str] = None,
    basement: Optional[BasementType] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    max_maintenance_fee: Optional[int] = None,
    min_sqft: Optional[int] = None,
    max_sqft: Optional[int] = None,
    sort_by: Optional[SortBy] = None,
    page_num: int = 1,
) -> list[dict] | str:
    """Fetch listings."""

    try:
        # Build the query parameters based on the provided filters
        params = {
            "listings": "true",
            "operator": "AND",
            "resultsPerPage": 15,
            "pageNum": page_num,
        }
        if area:
            params["area"] = area
        if city:
            params["city"] = city
        if district:
            params["district"] = district
        if sort_by:
            if sort_by == "Newest":
                params["sortBy"] = "updatedOnDesc"
            elif sort_by == "Oldest":
                params["sortBy"] = "updatedOnAsc"
            elif sort_by == "Price Low to High":
                params["sortBy"] = "listPriceAsc"
            elif sort_by == "Price High to Low":
                params["sortBy"] = "listPriceDesc"
            else:
                params["sortBy"] = "updatedOnDesc"
        else:
            params["sortBy"] = "updatedOnDesc"
        if property_types and "All" not in property_types:
            params["propertyType"] = property_types
        if status and status != "All":
            params["status"] = (
                ["A"]
                if status == "Active"
                else ["U"] if status == "Sold" else ["A", "U"]
            )
        # if status_period and status_period != "All":
        #     params["statusPeriod"] = status_period
        if bedrooms and "All" not in bedrooms:
            if "5+" in bedrooms:
                params["minBedrooms"] = 5
            else:
                params["minBedrooms"] = min(bedrooms)
                params["maxBedrooms"] = max(bedrooms)
        if bathrooms and "All" not in bathrooms:
            if "5+" in bathrooms:
                params["minBathrooms"] = 5
            else:
                params["minBathrooms"] = min(bathrooms)
                params["maxBathrooms"] = max(bathrooms)
        if den and den != "All":
            params["den"] = den == "Yes"
        if parking and "All" not in parking:
            if "5+" in parking:
                params["minParking"] = 5
            else:
                params["minParking"] = min(parking)
                params["maxParking"] = max(parking)
        if keyword:
            params["search"] = keyword
        if basement and basement != "All":
            params["basement"] = basement
        if min_price is not None:
            params["minPrice"] = min_price
        if max_price is not None:
            params["maxPrice"] = max_price
        if max_maintenance_fee is not None:
            params["maxMaintenanceFee"] = max_maintenance_fee
        if min_sqft is not None:
            params["minSqft"] = min_sqft
        if max_sqft is not None:
            params["maxSqft"] = max_sqft

        # Make the API request
        response = requests.post(
            f"{base_url}/listings", headers=headers, params=params
        )
        response.raise_for_status()  # Raise an error for bad responses
        listings = response.json().get("listings", [])
        return [
            {
                "listing_id": listing.get("mlsNumber"),
                "price": listing.get("listPrice"),
                "board_id": listing.get("boardId"),
            }
            for listing in listings
        ]
    except Exception as e:
        return f"Error fetching listings: {str(e)}. Try again with different parameters."

def get_listing_details(listing_id: str, board_id: str) -> dict:
    """Fetch details for a specific listing by its ID."""
    try:
        response = requests.get(
            f"{base_url}/listings/{listing_id}",
            headers=headers,
            params={"boardId": board_id},
        )
        response.raise_for_status()  # Raise an error for bad responses
        return simplify_listing_response(response.json())
    except Exception as e:
        return {"error": f"Error fetching listing details: {str(e)}"}



# # Example usage
# result = get_listings(
#     property_types=["Detached", "Condo Apt"], bedrooms=[3]
# )
# print(result[0])
# # Example usage of get_listing_details
# listing_details = get_listing_details(result[0]["listing_id"], result[0]["board_id"])
# print(listing_details)

tools = [
    get_listings,
    get_listing_details,
]
