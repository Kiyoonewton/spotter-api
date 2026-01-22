"""
Route Domain Services
Contains business logic for route calculation and processing
"""
import math
from typing import Dict, List, Any

from infrastructure.routing.osrm_client import fetch_route

# Type definitions
Location = Dict[str, float]  # {"lat": float, "lng": float}
Coordinates = List[List[float]]  # [[lng, lat], [lng, lat], ...]
RouteResponse = Dict[str, Any]  # OSRM API response
CombinedRoute = Dict[str, Any]  # Our processed route data


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
