"""
Location Name Service for ELD Data
Retrieves location names from coordinates using OpenStreetMap Nominatim API
"""
import requests
import time
import json
import os
import random
from typing import List, Dict, Any

# Create a cache directory if it doesn't exist
CACHE_DIR = "location_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Sample city names as fallback if API fails
FALLBACK_CITIES = [
    "Chicago, IL", "Houston, TX", "Phoenix, AZ", "Philadelphia, PA", "San Antonio, TX",
    "San Diego, CA", "Dallas, TX", "San Jose, CA", "Austin, TX", "Jacksonville, FL",
    "Fort Worth, TX", "Columbus, OH", "Charlotte, NC", "Indianapolis, IN", "San Francisco, CA",
    "Seattle, WA", "Denver, CO", "Boston, MA", "Nashville, TN", "Portland, OR",
    "Las Vegas, NV", "Detroit, MI", "Memphis, TN", "Louisville, KY", "Milwaukee, WI"
]

def get_location_name(coordinates: List[float]) -> str:
    """
    Get actual location name for coordinates using OpenStreetMap Nominatim API
    
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
                location_name = data.get("display_name", fallback_name)
        else:
            location_name = data.get("display_name", fallback_name)
        
        # Cache the result
        try:
            with open(cache_file, 'w') as f:
                json.dump({"name": location_name}, f)
        except Exception:
            # If caching fails, just continue
            pass
            
        return location_name
        
    except Exception as e:
        print(f"Warning: Error getting location name: {e}")
        # Fall back to a random city name
        return fallback_name
    
    finally:
        # Be nice to the Nominatim API by adding a small delay
        # Their usage policy requests max 1 request per second
        time.sleep(1)