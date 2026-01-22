"""
Location Domain Services
Contains business logic for location name resolution with caching
"""
import json
import os
import random
from typing import List

from infrastructure.geocoding.nominatim_client import get_location_name_from_api, FALLBACK_CITIES

# Cache directory path
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def get_location_name(coordinates: List[float]) -> str:
    """
    Get actual location name for coordinates with caching

    Args:
        coordinates: [longitude, latitude] coordinates

    Returns:
        Location name string
    """
    # Remember that coordinates are [longitude, latitude] in our data
    # but Nominatim API expects latitude,longitude
    lat = coordinates[1]
    lon = coordinates[0]

    # Check if we have this location in cache
    cache_key = f"{lat:.5f}_{lon:.5f}"
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")

    # Check cache first
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
                return cached_data.get("name", f"Location ({lat:.4f}, {lon:.4f})")
        except Exception:
            # If anything goes wrong with cache, proceed to API
            pass

    # Use a random city as fallback in case API call fails
    fallback_name = random.choice(FALLBACK_CITIES)

    # Get location name from API
    location_name = get_location_name_from_api(lat, lon, fallback_name)

    # Cache the result
    try:
        with open(cache_file, 'w') as f:
            json.dump({"name": location_name}, f)
    except Exception:
        # If caching fails, just continue
        pass

    return location_name
