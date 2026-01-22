"""
OSRM (Open Source Routing Machine) Client
Handles communication with external routing service
"""
import requests
import math
import random
from typing import Dict, List, Any

# Type definitions
Location = Dict[str, float]  # {"lat": float, "lng": float}
RouteResponse = Dict[str, Any]  # OSRM API response


def fetch_route(origin: Location, destination: Location) -> RouteResponse:
    """
    Fetch route data from OSRM service

    Args:
        origin: Starting location with lat/lng
        destination: Ending location with lat/lng

    Returns:
        OSRM route response data
    """
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{origin['lng']},{origin['lat']};"
        f"{destination['lng']},{destination['lat']}?"
        f"overview=full&geometries=geojson"
    )

    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        # Check if the route was found
        if data.get("code") != "Ok" or len(data.get("routes", [])) == 0:
            print(f"Warning: OSRM could not find a route. Using mock route instead.")
            return generate_mock_route(origin, destination)

        return data
    except Exception as e:
        print(f"Warning: Error fetching route from OSRM: {e}")
        print("Using mock route data instead.")
        return generate_mock_route(origin, destination)


def generate_mock_route(origin: Location, destination: Location, num_points: int = 50) -> RouteResponse:
    """
    Generate a mock route when the OSRM service is unavailable
    Creates a straight-line path with some random variation

    Args:
        origin: Starting location
        destination: Ending location
        num_points: Number of points to generate along the route

    Returns:
        Mock OSRM route response
    """
    # Create coordinates for a path between origin and destination
    lat1, lng1 = origin["lat"], origin["lng"]
    lat2, lng2 = destination["lat"], destination["lng"]

    # Calculate distance in kilometers (rough approximation)
    lat_diff = lat2 - lat1
    lng_diff = lng2 - lng1

    # Calculate straight-line distance using Haversine formula
    a = math.sin(math.radians(lat_diff)/2)**2 + (
        math.cos(math.radians(lat1)) *
        math.cos(math.radians(lat2)) *
        math.sin(math.radians(lng_diff)/2)**2
    )
    distance_km = 2 * 6371 * math.asin(math.sqrt(a))  # Earth radius is 6371 km

    # Handle very short distances or identical points
    if distance_km < 0.1:
        distance_km = 0.1

    # Estimate driving distance (usually longer than straight line)
    driving_distance_meters = distance_km * 1000 * 1.3  # 30% longer than straight line

    # Estimate duration (assuming average speed of 80 km/h)
    duration_seconds = (distance_km * 1.3) / 80 * 3600

    # Generate points along the path
    coordinates = []
    for i in range(num_points):
        progress = i / (num_points - 1)

        # Interpolate position
        lat = lat1 + lat_diff * progress
        lng = lng1 + lng_diff * progress

        # Add some randomness to make it look like a real route
        # but less randomness near the start and end points
        randomness = 0.01 * math.sin(progress * math.pi)
        if 0.1 < progress < 0.9:
            lat += random.uniform(-randomness, randomness)
            lng += random.uniform(-randomness, randomness)

        coordinates.append([lng, lat])  # GeoJSON format is [lng, lat]

    # Create a mock response
    return {
        "code": "Ok",
        "routes": [
            {
                "distance": driving_distance_meters,
                "duration": duration_seconds,
                "geometry": {
                    "coordinates": coordinates
                }
            }
        ],
        "message": None
    }
