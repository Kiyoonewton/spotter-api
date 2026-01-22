"""
Stop Generator for ELD Data
Handles creating stops along a route based on HOS regulations
"""
import datetime
import math
import random
from typing import Dict, List, Tuple, Any, Optional, Union

# Import route calculator
from eld_modules.route_calculator import interpolate_position
from eld_modules.location_name import get_location_name

# Type definitions
Location = Dict[str, float]  # {"lat": float, "lng": float}
CombinedRoute = Dict[str, Any]  # From route_calculator
Stop = Dict[str, Any]  # A stop along the route

# Constants for HOS regulations and timing
PRE_TRIP_START_HOUR = 6.5  # 6:30 AM
DRIVING_START_HOUR = 7.0   # 7:00 AM
DRIVING_END_HOUR = 17.5    # 5:30 PM
SLEEPER_START_HOUR = 19.0  # 7:00 PM
SLEEPER_END_HOUR = 6.5     # 6:30 AM
FUEL_STOP_INTERVAL = 500   # Miles between fuel stops
PICKUP_DURATION = 0.5      # 30 minutes for pickup
DROPOFF_DURATION = 0.5     # 30 minutes for dropoff
WAYPOINT_DURATION = 0.5    # 30 minutes for waypoints
FUEL_DURATION = 0.5        # 30 minutes for fuel
BREAK_DURATION = 0.5       # 30 minutes for break
PREFERRED_BREAK_HOUR = 14.0  # 2:00 PM for breaks
AVG_SPEED_MPH = 60         # Average driving speed in mph

def format_duration(hours: float) -> str:
    """Format hours into a readable duration string"""
    if hours < 1:
        minutes = round(hours * 60)
        return f"{minutes} minutes"
    else:
        return f"{hours:.1f} hours"

def format_coordinates(coordinates: List[float]) -> str:
    """Format coordinates to a readable string"""
    return f"{coordinates[1]:.4f}, {coordinates[0]:.4f}"

def calculate_hours_until_end_of_driving_day(current_time: datetime.datetime) -> float:
    """
    Calculate hours remaining until the end of driving day
    
    Args:
        current_time: Current timestamp
        
    Returns:
        Hours remaining until driving end time
    """
    current_hour = current_time.hour + (current_time.minute / 60)
    if current_hour >= DRIVING_END_HOUR:
        return 0
    return DRIVING_END_HOUR - current_hour

def is_within_driving_hours(timestamp: datetime.datetime) -> bool:
    """
    Check if a timestamp is within allowed driving hours
    
    Args:
        timestamp: Time to check
        
    Returns:
        True if within driving hours, False otherwise
    """
    hour = timestamp.hour + (timestamp.minute / 60)
    return DRIVING_START_HOUR <= hour <= DRIVING_END_HOUR

def next_driving_start_time(timestamp: datetime.datetime) -> datetime.datetime:
    """
    Get the next available driving start time
    
    Args:
        timestamp: Current timestamp
        
    Returns:
        Next time when driving can begin
    """
    hour = timestamp.hour + (timestamp.minute / 60)
    
    if hour < DRIVING_START_HOUR:
        # Same day, just wait until driving start hour
        return timestamp.replace(
            hour=int(DRIVING_START_HOUR),
            minute=int((DRIVING_START_HOUR % 1) * 60),
            second=0
        )
    elif hour >= DRIVING_END_HOUR:
        # Need to go to next day
        next_day = timestamp + datetime.timedelta(days=1)
        return next_day.replace(
            hour=int(DRIVING_START_HOUR),
            minute=int((DRIVING_START_HOUR % 1) * 60),
            second=0
        )
    else:
        # Already in driving hours
        return timestamp

def calculate_time_restricted_arrival(start_time: datetime.datetime, driving_hours: float) -> datetime.datetime:
    """
    Calculate arrival time respecting driving hour restrictions
    
    Args:
        start_time: Starting timestamp
        driving_hours: Hours of driving needed
        
    Returns:
        Timestamp for arrival respecting driving hours
    """
    if driving_hours <= 0:
        return start_time
    
    # Make sure we're starting during driving hours
    current_time = next_driving_start_time(start_time)
    
    # Calculate how many hours we can drive today
    hours_until_end = calculate_hours_until_end_of_driving_day(current_time)
    
    if driving_hours <= hours_until_end:
        # We can complete the drive today
        return current_time + datetime.timedelta(hours=driving_hours)
    else:
        # We need to split across days
        
        # Drive until end of day
        end_of_day = current_time.replace(
            hour=int(DRIVING_END_HOUR),
            minute=int((DRIVING_END_HOUR % 1) * 60),
            second=0
        )
        
        # Calculate remaining driving hours
        remaining_hours = driving_hours - hours_until_end
        
        # Move to next driving day
        next_day = end_of_day + datetime.timedelta(days=1)
        next_start = next_day.replace(
            hour=int(DRIVING_START_HOUR),
            minute=int((DRIVING_START_HOUR % 1) * 60),
            second=0
        )
        
        # Recursively calculate with remaining hours
        return calculate_time_restricted_arrival(next_start, remaining_hours)

def plan_break_time(current_time: datetime.datetime, driving_hours: float) -> Tuple[datetime.datetime, float, float]:
    """
    Plan when to take a break during a driving segment
    
    Args:
        current_time: Current timestamp
        driving_hours: Total driving hours for this segment
        
    Returns:
        Tuple of (break_time, hours_before_break, hours_after_break)
    """
    # Default to no break (if driving_hours < 8)
    if driving_hours < 8:
        return None, driving_hours, 0
    
    # Calculate the time when we would arrive at break location if driving 7 hours
    hours_before_break = 7.0  # Take break after 7 hours of driving
    break_time_raw = current_time + datetime.timedelta(hours=hours_before_break)
    
    # Check if break will be during driving hours
    if not is_within_driving_hours(break_time_raw):
        # If we'd reach break after driving hours, split at end of day
        hours_until_end = calculate_hours_until_end_of_driving_day(current_time)
        break_time = current_time + datetime.timedelta(hours=hours_until_end)
        return break_time, hours_until_end, driving_hours - hours_until_end
    
    # Try to align break close to preferred time (2 PM / 14:00)
    break_hour = break_time_raw.hour + (break_time_raw.minute / 60)
    day_start = break_time_raw.replace(hour=0, minute=0, second=0, microsecond=0)
    
    preferred_time = day_start + datetime.timedelta(hours=PREFERRED_BREAK_HOUR)
    
    # If we're within 2 hours of preferred break time, adjust
    time_diff = abs(break_time_raw.timestamp() - preferred_time.timestamp()) / 3600
    
    if time_diff <= 2:
        # Adjust break time to preferred time
        hours_before_break = (preferred_time - current_time).total_seconds() / 3600
        # Ensure we're not driving more than 8 hours before break
        hours_before_break = min(hours_before_break, 8.0)
        # Ensure it's not negative
        hours_before_break = max(hours_before_break, 4.0)
    
    break_time = current_time + datetime.timedelta(hours=hours_before_break)
    hours_after_break = driving_hours - hours_before_break
    
    return break_time, hours_before_break, hours_after_break

def align_break_time(break_time: datetime.datetime) -> datetime.datetime:
    """
    Try to align breaks to standard break times (around 2:00 PM / 14:00)
    
    Args:
        break_time: Calculated break time
        
    Returns:
        Adjusted break time
    """
    # Get the day start
    day_start = break_time.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Create target time at 2:00 PM (14:00)
    target_time = day_start + datetime.timedelta(hours=PREFERRED_BREAK_HOUR)
    
    # Current hour
    current_hour = break_time.hour + (break_time.minute / 60)
    
    # If it's already past 14:00, keep the original time
    if current_hour > PREFERRED_BREAK_HOUR:
        return break_time
    
    # If it's between 12:00 and 14:00, try to push to 14:00 if within driving hours
    if 12.0 <= current_hour < PREFERRED_BREAK_HOUR:
        # Check if target is within driving hours
        if is_within_driving_hours(target_time):
            return target_time
    
    # Otherwise return original time
    return break_time

def generate_stops(
    route: CombinedRoute,
    locations: List[Location],
    start_time: Optional[datetime.datetime] = None,
    current_cycle_used: float = 0
) -> List[Stop]:
    """
    Generate stops along a route based on HOS regulations
    
    Args:
        route: Combined route data
        locations: List of locations [origin, pickup, waypoint1, ..., dropoff]
        start_time: Start timestamp (default: today at 6:00 AM)
        current_cycle_used: Hours already used in current driving cycle
        
    Returns:
        List of stops along the route
    """
    # Initialize with default start time if not provided
    if start_time is None:
        start_time = datetime.datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    
    # Initialize variables
    stops = []
    current_timestamp = start_time
    current_position = 0  # miles into journey
    miles_since_last_fuel = 0
    hours_of_driving_since_last_break = current_cycle_used
    total_distance = route["distance"]
    days_on_road = 0
    
    # Add starting point (always off-duty at the beginning)
    stops.append({
        "type": "start",
        "name": "Starting Location",
        "coordinates": [locations[0]["lng"], locations[0]["lat"]],
        "duration": "0 hours",
        "estimatedArrival": current_timestamp.isoformat()
    })

    # Handle early morning hours (midnight to 6:30 AM)
    current_hour = current_timestamp.hour + (current_timestamp.minute / 60)
    if current_hour < SLEEPER_END_HOUR:
        # First day uses off-duty for early morning
        stops.append({
            "type": "off-duty",  # First day uses off-duty instead of sleeper-berth
            "name": "Early Morning Rest (Off-Duty)",
            "coordinates": [locations[0]["lng"], locations[0]["lat"]],
            "duration": format_duration(SLEEPER_END_HOUR - current_hour),
            "estimatedArrival": current_timestamp.isoformat()
        })
        
        # Update time to 6:30 AM
        current_timestamp = current_timestamp.replace(
            hour=int(SLEEPER_END_HOUR),
            minute=int((SLEEPER_END_HOUR % 1) * 60),
            second=0
        )
    
    # Add pre-trip inspection if at appropriate time
    current_hour = current_timestamp.hour + (current_timestamp.minute / 60)
    if current_hour >= PRE_TRIP_START_HOUR and current_hour < DRIVING_START_HOUR:
        # Add pre-trip inspection
        stops.append({
            "type": "pretrip",
            "name": "Pre-trip Inspection",
            "coordinates": [locations[0]["lng"], locations[0]["lat"]],
            "duration": format_duration(DRIVING_START_HOUR - PRE_TRIP_START_HOUR),
            "estimatedArrival": current_timestamp.isoformat()
        })
        
        # Update time
        pretrip_time = DRIVING_START_HOUR - current_hour
        current_timestamp += datetime.timedelta(hours=pretrip_time)
    
    # Ensure we start at or after driving start hour
    current_timestamp = next_driving_start_time(current_timestamp)
    
    # Process each stop location
    for i in range(1, len(locations)):
        # Calculate approximate distance to next location
        location_percent = i / (len(locations) - 1)
        next_position = total_distance * location_percent
        distance_to_next = next_position - current_position
        
        # Process driving to this location
        driving_hours = distance_to_next / AVG_SPEED_MPH
        miles_to_next_fuel = FUEL_STOP_INTERVAL - miles_since_last_fuel
        
        # Split long segments into manageable parts
        remaining_drive = driving_hours
        segment_position = current_position
        
        while remaining_drive > 0:
            # Check if we need to stop for the day
            hours_until_end = calculate_hours_until_end_of_driving_day(current_timestamp)
            
            if hours_until_end <= 0:
                # Already past driving hours, add overnight stop
                overnight_coordinates = interpolate_position(route, segment_position / total_distance)
                
                # If it's between end of driving and sleeper time, wait until sleeper time
                current_hour = current_timestamp.hour + (current_timestamp.minute / 60)
                
                if DRIVING_END_HOUR <= current_hour < SLEEPER_START_HOUR:
                    # Add off-duty period until sleeper time
                    off_duty_hours = SLEEPER_START_HOUR - current_hour
                    
                    stops.append({
                        "type": "off-duty",
                        "name": "End of Driving Day",
                        "coordinates": overnight_coordinates,
                        "duration": format_duration(off_duty_hours),
                        "estimatedArrival": current_timestamp.isoformat()
                    })
                    
                    # Update to sleeper time
                    sleeper_time = current_timestamp.replace(
                        hour=int(SLEEPER_START_HOUR),
                        minute=int((SLEEPER_START_HOUR % 1) * 60),
                        second=0
                    )
                    current_timestamp = sleeper_time
                
                # Add overnight rest
                stops.append({
                    "type": "overnight",
                    "name": "Required 10-Hour Rest",
                    "coordinates": overnight_coordinates,
                    "duration": "10 hours",
                    "estimatedArrival": current_timestamp.isoformat()
                })
                
                # Move to next morning
                current_timestamp = current_timestamp + datetime.timedelta(hours=10)
                
                # Handle early morning for subsequent days
                next_day_hour = current_timestamp.hour + (current_timestamp.minute / 60)
                if next_day_hour < SLEEPER_END_HOUR:
                    # For subsequent days, always use sleeper-berth for early morning hours
                    stops.append({
                        "type": "overnight",  # Use overnight type for sleeper-berth status
                        "name": "Early Morning Rest (Sleeper Berth)",
                        "coordinates": overnight_coordinates,
                        "duration": format_duration(SLEEPER_END_HOUR - next_day_hour),
                        "estimatedArrival": current_timestamp.isoformat()
                    })
                    
                    # Update to 6:30 AM
                    current_timestamp = current_timestamp.replace(
                        hour=int(SLEEPER_END_HOUR),
                        minute=int((SLEEPER_END_HOUR % 1) * 60),
                        second=0
                    )
                
                current_timestamp = next_driving_start_time(current_timestamp)
                hours_of_driving_since_last_break = 0
                days_on_road += 1
                continue
            
            # Check if we need a mandatory break first
            if hours_of_driving_since_last_break >= 8:
                # Need to take a break first
                break_coordinates = interpolate_position(route, segment_position / total_distance)
                
                # Try to time the break around 2 PM if possible
                break_time = align_break_time(current_timestamp)
                
                stops.append({
                    "type": "rest",
                    "name": "30-Minute Break",
                    "coordinates": break_coordinates,
                    "duration": format_duration(BREAK_DURATION),
                    "estimatedArrival": break_time.isoformat()
                })
                
                # Reset driving hours and update time
                hours_of_driving_since_last_break = 0
                current_timestamp = break_time + datetime.timedelta(hours=BREAK_DURATION)
                continue
            
            # Determine how far we can drive in remaining day
            hours_left_before_break = max(0, 8 - hours_of_driving_since_last_break)
            drivable_hours = min(remaining_drive, hours_until_end, hours_left_before_break)
            
            # If we can't drive (need a break), skip to the next iteration
            if drivable_hours <= 0:
                # We need a break - force a break now
                break_coordinates = interpolate_position(route, segment_position / total_distance)
                
                # Try to time the break around 2 PM if possible
                break_time = align_break_time(current_timestamp)
                
                stops.append({
                    "type": "rest",
                    "name": "30-Minute Break (Required)",
                    "coordinates": break_coordinates,
                    "duration": format_duration(BREAK_DURATION),
                    "estimatedArrival": break_time.isoformat()
                })
                
                # Reset driving hours and update time
                hours_of_driving_since_last_break = 0
                current_timestamp = break_time + datetime.timedelta(hours=BREAK_DURATION)
                continue
            
            # Check if fuel stop needed during this segment
            drivable_miles = drivable_hours * AVG_SPEED_MPH
            need_fuel = drivable_miles >= miles_to_next_fuel and miles_to_next_fuel > 0
            
            if need_fuel:
                # Add fuel stop
                fuel_position = segment_position + miles_to_next_fuel
                fuel_percent = fuel_position / total_distance
                try:
                    fuel_coordinates = interpolate_position(route, fuel_percent)
                except (IndexError, ZeroDivisionError):
                    # Handle potential errors in interpolation
                    fuel_coordinates = interpolate_position(route, 0)
                
                driving_hours_to_fuel = miles_to_next_fuel / AVG_SPEED_MPH
                fuel_arrival = calculate_time_restricted_arrival(current_timestamp, driving_hours_to_fuel)
                
                stops.append({
                    "type": "fuel",
                    "name": "Fuel Stop",
                    "coordinates": fuel_coordinates,
                    "duration": format_duration(FUEL_DURATION),
                    "estimatedArrival": fuel_arrival.isoformat()
                })
                
                # Update position and time
                segment_position = fuel_position
                current_timestamp = fuel_arrival + datetime.timedelta(hours=FUEL_DURATION)
                hours_of_driving_since_last_break += driving_hours_to_fuel
                miles_to_next_fuel = FUEL_STOP_INTERVAL
                remaining_drive -= driving_hours_to_fuel
                
                # Check if we need a break after fueling
                if hours_of_driving_since_last_break >= 7:
                    break_coordinates = fuel_coordinates
                    
                    # Try to time the break around 2 PM if possible
                    break_time = align_break_time(current_timestamp)
                    
                    stops.append({
                        "type": "rest",
                        "name": "30-Minute Break",
                        "coordinates": break_coordinates,
                        "duration": format_duration(BREAK_DURATION),
                        "estimatedArrival": break_time.isoformat()
                    })
                    
                    # Reset driving hours and update time
                    hours_of_driving_since_last_break = 0
                    current_timestamp = break_time + datetime.timedelta(hours=BREAK_DURATION)
                
                continue
            
            # Check if we need a break during this segment
            if hours_of_driving_since_last_break + drivable_hours >= 8:
                # Need a break during this segment
                hours_until_break_needed = 8 - hours_of_driving_since_last_break
                
                if hours_until_break_needed > 0:
                    # Drive until we need a break
                    pre_break_position = segment_position + (hours_until_break_needed * AVG_SPEED_MPH)
                    pre_break_percent = pre_break_position / total_distance
                    try:
                        break_coordinates = interpolate_position(route, pre_break_percent)
                    except (IndexError, ZeroDivisionError):
                        # Handle potential errors in interpolation
                        break_coordinates = interpolate_position(route, 0)
                    
                    # Calculate time of arrival at break location
                    pre_break_arrival = calculate_time_restricted_arrival(
                        current_timestamp, hours_until_break_needed)
                    
                    # Try to time the break around 2 PM if possible
                    break_time = align_break_time(pre_break_arrival)
                    
                    stops.append({
                        "type": "rest",
                        "name": "30-Minute Break",
                        "coordinates": break_coordinates,
                        "duration": format_duration(BREAK_DURATION),
                        "estimatedArrival": break_time.isoformat()
                    })
                    
                    # Update position and time
                    segment_position = pre_break_position
                    current_timestamp = break_time + datetime.timedelta(hours=BREAK_DURATION)
                    remaining_drive -= hours_until_break_needed
                    miles_to_next_fuel -= hours_until_break_needed * AVG_SPEED_MPH
                    hours_of_driving_since_last_break = 0
                    
                    continue
            
            # Drive as far as we can in this segment
            drive_position = segment_position + (drivable_hours * AVG_SPEED_MPH)
            arrival_time = calculate_time_restricted_arrival(current_timestamp, drivable_hours)
            
            # Update position and time
            segment_position = drive_position
            current_timestamp = arrival_time
            remaining_drive -= drivable_hours
            miles_to_next_fuel -= drivable_hours * AVG_SPEED_MPH
            hours_of_driving_since_last_break += drivable_hours
            
            # If we're at end of day, add overnight stop
            hours_until_end = calculate_hours_until_end_of_driving_day(current_timestamp)
            if hours_until_end <= 0 and remaining_drive > 0:
                try:
                    overnight_coordinates = interpolate_position(route, segment_position / total_distance)
                except (IndexError, ZeroDivisionError):
                    # Handle potential errors in interpolation
                    overnight_coordinates = interpolate_position(route, 0)
                
                # Add off-duty period
                off_duty_start = current_timestamp.replace(
                    hour=int(DRIVING_END_HOUR),
                    minute=int((DRIVING_END_HOUR % 1) * 60),
                    second=0
                )
                
                stops.append({
                    "type": "off-duty",
                    "name": "End of Driving Day",
                    "coordinates": overnight_coordinates,
                    "duration": format_duration(SLEEPER_START_HOUR - DRIVING_END_HOUR),
                    "estimatedArrival": off_duty_start.isoformat()
                })
                
                # Add overnight rest at sleeper time
                sleeper_time = off_duty_start.replace(
                    hour=int(SLEEPER_START_HOUR),
                    minute=int((SLEEPER_START_HOUR % 1) * 60),
                    second=0
                )
                
                stops.append({
                    "type": "overnight",
                    "name": "Required 10-Hour Rest",
                    "coordinates": overnight_coordinates,
                    "duration": "10 hours",
                    "estimatedArrival": sleeper_time.isoformat()
                })
                
                # Move to next morning
                current_timestamp = sleeper_time + datetime.timedelta(hours=10)
                
                # Handle early morning for subsequent days
                next_day_hour = current_timestamp.hour + (current_timestamp.minute / 60)
                if next_day_hour < SLEEPER_END_HOUR:
                    # For subsequent days, always use sleeper-berth for early morning hours
                    stops.append({
                        "type": "overnight",  # Use overnight type for sleeper-berth status
                        "name": "Early Morning Rest (Sleeper Berth)",
                        "coordinates": overnight_coordinates,
                        "duration": format_duration(SLEEPER_END_HOUR - next_day_hour),
                        "estimatedArrival": current_timestamp.isoformat()
                    })
                    
                    # Update to 6:30 AM
                    current_timestamp = current_timestamp.replace(
                        hour=int(SLEEPER_END_HOUR),
                        minute=int((SLEEPER_END_HOUR % 1) * 60),
                        second=0
                    )
                
                current_timestamp = next_driving_start_time(current_timestamp)
                hours_of_driving_since_last_break = 0
                days_on_road += 1
        
        # We've completed driving to this location
        current_position = next_position
        miles_since_last_fuel += distance_to_next
        
        # Determine stop type and duration
        stop_type = "waypoint"
        stop_duration = WAYPOINT_DURATION
        if i == 1:
            stop_type = "pickup"
            stop_duration = PICKUP_DURATION
        elif i == len(locations) - 1:
            stop_type = "dropoff"
            stop_duration = DROPOFF_DURATION
        
        # Get the location name
        try:
            location_coordinates = [locations[i]["lng"], locations[i]["lat"]]
            location_name = f"{stop_type.capitalize()} at {get_location_name(location_coordinates)}"
        except Exception:
            # Fallback if location name service fails
            location_name = f"{stop_type.capitalize()} Location"
        
        stops.append({
            "type": stop_type,
            "name": location_name,
            "coordinates": [locations[i]["lng"], locations[i]["lat"]],
            "duration": format_duration(stop_duration),
            "estimatedArrival": current_timestamp.isoformat()
        })
        
        # Update time after stop
        current_timestamp += datetime.timedelta(hours=stop_duration)
    
    # Sort stops by arrival time
    stops.sort(key=lambda s: s["estimatedArrival"])
    
    return stops