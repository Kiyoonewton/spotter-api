"""
Nominatim (OpenStreetMap) Geocoding Client
Handles reverse geocoding - converting coordinates to location names
"""
import requests
import time
from typing import List

# Sample city names as fallback if API fails
FALLBACK_CITIES = [
    "Chicago, IL", "Houston, TX", "Phoenix, AZ", "Philadelphia, PA", "San Antonio, TX",
    "San Diego, CA", "Dallas, TX", "San Jose, CA", "Austin, TX", "Jacksonville, FL",
    "Fort Worth, TX", "Columbus, OH", "Charlotte, NC", "Indianapolis, IN", "San Francisco, CA",
    "Seattle, WA", "Denver, CO", "Boston, MA", "Nashville, TN", "Portland, OR",
    "Las Vegas, NV", "Detroit, MI", "Memphis, TN", "Louisville, KY", "Milwaukee, WI"
]


def get_location_name_from_api(lat: float, lon: float, fallback_city: str) -> str:
    """
    Get location name from Nominatim API

    Args:
        lat: Latitude
        lon: Longitude
        fallback_city: Fallback city name if API fails

    Returns:
        Location name string
    """
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"

        # Add user-agent to comply with Nominatim usage policy
        headers = {"User-Agent": "ELDGenerator/1.0"}

        # Make request to Nominatim API
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()

        # Extract location information
        location_name = f"Location ({lat:.4f}, {lon:.4f})"

        if "address" in data:
            # Try to construct a meaningful location name
            address = data["address"]

            # Different combinations depending on what's available
            if "city" in address:
                if "state" in address:
                    location_name = f"{address['city']}, {address['state']}"
                else:
                    location_name = address['city']
            elif "town" in address:
                if "state" in address:
                    location_name = f"{address['town']}, {address['state']}"
                else:
                    location_name = address['town']
            elif "village" in address:
                if "state" in address:
                    location_name = f"{address['village']}, {address['state']}"
                else:
                    location_name = address['village']
            elif "county" in address and "state" in address:
                location_name = f"{address['county']}, {address['state']}"
            elif "road" in address and "state" in address:
                location_name = f"{address['road']}, {address['state']}"
            else:
                # Fallback to display_name if we couldn't construct a good name
                location_name = data.get("display_name", fallback_city)
        else:
            location_name = data.get("display_name", fallback_city)

        return location_name

    except Exception as e:
        print(f"Warning: Error getting location name: {e}")
        # Fall back to provided fallback city
        return fallback_city

    finally:
        # Be nice to the Nominatim API by adding a small delay
        # Their usage policy requests max 1 request per second
        time.sleep(1)
