"""
Route Calculator for ELD Generator
Handles fetching and processing route data
"""
import requests
import math
import random
from typing import Dict, List, Tuple, Any, Optional

# Type definitions for better code documentation
Location = Dict[str, float]  # {"lat": float, "lng": float}
Coordinates = List[List[float]]  # [[lng, lat], [lng, lat], ...]
RouteSegment = Dict[str, Any]  # OSRM route segment data
RouteResponse = Dict[str, Any]  # OSRM API response
CombinedRoute = Dict[str, Any]  # Our processed route data

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

def calculate_multi_stop_route(locations: List[Location]) -> CombinedRoute:
    """
    Calculate a route with multiple stops
    
    Args:
        locations: List of locations in order [start, pickup, waypoint1, ..., dropoff]
        
    Returns:
        Combined route data with all segments
    """
    if len(locations) < 2:
        raise ValueError("At least 2 locations are required for a route")
    
    # Fetch routes between each pair of consecutive locations
    route_segments = []
    for i in range(len(locations) - 1):
        origin = locations[i]
        destination = locations[i + 1]
        route = fetch_route(origin, destination)
        route_segments.append(route)
    
    # Combine all route segments
    return combine_routes(route_segments)

def combine_routes(route_segments: List[RouteResponse]) -> CombinedRoute:
    """
    Combine multiple route segments into one route
    
    Args:
        route_segments: List of OSRM route responses
        
    Returns:
        Combined route with total distance, duration, and all coordinates
    """
    total_distance_miles = 0
    total_duration = 0
    all_coordinates = []
    
    for i, segment in enumerate(route_segments):
        # Skip segments with no routes
        if not segment.get("routes") or len(segment["routes"]) == 0:
            continue
            
        # Convert meters to miles
        distance_miles = (segment["routes"][0]["distance"] / 1000) * 0.621371
        total_distance_miles += distance_miles
        total_duration += segment["routes"][0]["duration"]
        
        # Add coordinates, skipping the first point for segments after the first
        # to avoid duplication
        segment_coords = segment["routes"][0]["geometry"]["coordinates"]
        if i == 0:
            all_coordinates.extend(segment_coords)
        else:
            all_coordinates.extend(segment_coords[1:])
    
    # Get pickup and dropoff coordinates (first and last segments)
    pickup_coordinates = []
    if route_segments and "routes" in route_segments[0] and route_segments[0]["routes"]:
        pickup_coordinates = route_segments[0]["routes"][0]["geometry"]["coordinates"][-1]
        
    dropoff_coordinates = []
    if route_segments and "routes" in route_segments[-1] and route_segments[-1]["routes"]:
        dropoff_coordinates = route_segments[-1]["routes"][0]["geometry"]["coordinates"][-1]
    
    return {
        "distance": total_distance_miles,
        "duration": total_duration,
        "coordinates": all_coordinates,
        "pickup_coordinates": pickup_coordinates,
        "dropoff_coordinates": dropoff_coordinates
    }

def interpolate_position(route: CombinedRoute, percentage: float) -> List[float]:
    """
    Find coordinates at given percentage of route
    
    Args:
        route: Combined route data
        percentage: Position along the route (0.0 to 1.0)
        
    Returns:
        [lng, lat] coordinates at that position
    """
    if not route["coordinates"]:
        # Safety check - return default coordinates if none exist
        return [0, 0]
        
    # Ensure percentage is between 0 and 1
    percentage = max(0, min(1, percentage))
    
    index = math.floor(percentage * len(route["coordinates"]))
    index = min(index, len(route["coordinates"]) - 1)
    index = max(0, index)  # Ensure index is not negative
    
    return route["coordinates"][index]