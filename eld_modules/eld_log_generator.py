"""
ELD Log Generator Module
Generates Electronic Logging Device data based on calculated stops
"""
import datetime
import math
import random
import json
from typing import Dict, List, Tuple, Any, Optional, Union

# Import from other modules
from eld_modules.location_name import get_location_name

# Type definitions
Location = Dict[str, float]  # {"lat": float, "lng": float}
DutyStatus = Dict[str, Any]  # Status record
Remark = Dict[str, Any]  # Remark record
Violation = Dict[str, str]  # HOS Violation
ELDLogEntry = Dict[str, Any]  # Individual log entry
DailyLogSheet = Dict[str, Any]  # Complete daily log

# Constants for HOS regulations
MAX_DRIVING_HOURS = 11  # Maximum driving hours per day
MAX_ON_DUTY_HOURS = 14  # Maximum on-duty hours per day
REQUIRED_REST_HOURS = 10  # Required rest hours between duty periods
PRE_TRIP_START_HOUR = 6.5  # 6:30 AM
DRIVING_START_HOUR = 7.0   # 7:00 AM
DRIVING_END_HOUR = 17.5    # 5:30 PM
SLEEPER_START_HOUR = 19.0  # 7:00 PM
SLEEPER_END_HOUR = 6.5     # 6:30 AM

def format_coordinates(coordinates: List[float]) -> str:
    """Format coordinates to a readable string"""
    return f"{coordinates[1]:.4f}, {coordinates[0]:.4f}"

def generate_eld_logs(stops: List, starting_odometer: int = None) -> List[DailyLogSheet]:
    """
    Generate ELD logs from a list of stops
    
    Args:
        stops: List of stops with type, coordinates, estimatedArrival
        starting_odometer: Starting odometer reading (defaults to random value)
        
    Returns:
        List of daily log sheets
    """
    if not stops:
        return []
    
    # Default starting odometer if not provided
    if starting_odometer is None:
        starting_odometer = random.randint(100000, 500000)
    
    # Group stops by day
    stops_by_day = {}
    
    for stop in stops:
        arrival_time = datetime.datetime.fromisoformat(stop["estimatedArrival"])
        day = arrival_time.date().isoformat()
        
        if day not in stops_by_day:
            stops_by_day[day] = []
            
        stops_by_day[day].append(stop)
    
    # Initialize daily logs
    daily_logs = []
    current_odometer = starting_odometer
    current_position = 0  # Track miles driven
    
    # Process each day
    for day_index, (day, day_stops) in enumerate(sorted(stops_by_day.items())):
        # Create daily log sheet
        daily_log = create_daily_log_sheet(day)
        
        # Set start location from first stop of the day
        first_stop = day_stops[0]
        first_stop_time = datetime.datetime.fromisoformat(first_stop["estimatedArrival"])
        daily_log["startTime"] = first_stop_time.isoformat()
        daily_log["startLocation"] = get_location_name(first_stop["coordinates"])
        daily_log["startOdometer"] = current_odometer
        
        # Track hours for HOS compliance
        driving_hours = 0
        on_duty_hours = 0
        
        # Generate duty status changes and remarks
        duty_statuses = []
        remarks = []
        
        # Determine if this is first day or later day
        is_first_day = (day_index == 0)
        is_last_day = (day_index == len(stops_by_day) - 1)
        
        # Check if this is a partial day (delivery before 17:30)
        last_stop_time = datetime.datetime.fromisoformat(day_stops[-1]["estimatedArrival"])
        last_stop_hour = last_stop_time.hour + (last_stop_time.minute / 60)
        is_early_completion = is_last_day and last_stop_hour < DRIVING_END_HOUR and day_stops[-1]["type"] == "dropoff"
        
        # Process stops to extract initial duty statuses from the generated stops
        for stop in day_stops:
            stop_time = datetime.datetime.fromisoformat(stop["estimatedArrival"])
            stop_hour = stop_time.hour + (stop_time.minute / 60)
            stop_type = stop["type"]
            
            # Map stop types to duty statuses
            if stop_type == "overnight":
                add_duty_status(duty_statuses, stop_hour, "sleeper-berth")
                add_remark(remarks, stop_hour, stop["name"])
            elif stop_type == "off-duty":
                add_duty_status(duty_statuses, stop_hour, "off-duty")
                add_remark(remarks, stop_hour, stop["name"])
            elif stop_type == "rest":
                add_duty_status(duty_statuses, stop_hour, "off-duty")
                add_remark(remarks, stop_hour, stop["name"])
            elif stop_type == "pretrip":
                add_duty_status(duty_statuses, stop_hour, "on-duty")
                add_remark(remarks, stop_hour, stop["name"])
            elif stop_type in ["pickup", "dropoff", "waypoint", "fuel"]:
                add_duty_status(duty_statuses, stop_hour, "on-duty")
                add_remark(remarks, stop_hour, stop["name"])
            elif stop_type == "start":
                add_duty_status(duty_statuses, stop_hour, "off-duty")
                add_remark(remarks, stop_hour, stop["name"])
        
        # Ensure early morning hours (midnight to 6:30 AM) are correctly set
        # Check if there are any status changes between midnight and 6:30 AM
        early_morning_statuses = [s for s in duty_statuses if 0 <= s["hour"] < SLEEPER_END_HOUR]
        
        if not early_morning_statuses:
            # No early morning statuses found, add them based on day
            if is_first_day:
                # First day: off-duty from midnight to 6:30 AM
                add_duty_status(duty_statuses, 0.0, "off-duty")
                add_remark(remarks, 0.0, "")
            else:
                # Subsequent days: sleeper-berth from midnight to 6:30 AM
                add_duty_status(duty_statuses, 0.0, "sleeper-berth")
                add_remark(remarks, 0.0, "")
        else:
            # There are some statuses already in early morning
            # Check if midnight is covered, if not add the appropriate status
            if not any(abs(s["hour"]) < 0.01 for s in duty_statuses):
                if is_first_day:
                    add_duty_status(duty_statuses, 0.0, "off-duty")
                    add_remark(remarks, 0.0, "")
                else:
                    add_duty_status(duty_statuses, 0.0, "sleeper-berth")
                    add_remark(remarks, 0.0, "")
        
        # Ensure transition at 6:30 AM if not already present
        if not any(abs(s["hour"] - SLEEPER_END_HOUR) < 0.01 for s in duty_statuses):
            add_duty_status(duty_statuses, SLEEPER_END_HOUR, "on-duty")
            add_remark(remarks, SLEEPER_END_HOUR, "End of Rest Period")
        
        # Always ensure we have the standard pattern for the start of each day
        # Even if the actual first stop is later than these times
        if is_first_day:
            # First day - check if we start before or after standard hours
            first_stop_hour = first_stop_time.hour + (first_stop_time.minute / 60)
            
            if first_stop_hour <= PRE_TRIP_START_HOUR:
                # Normal start - Add standard pattern
                add_duty_status(duty_statuses, PRE_TRIP_START_HOUR, "on-duty")
                add_remark(remarks, PRE_TRIP_START_HOUR, "Pre-trip Inspection")
                add_duty_status(duty_statuses, DRIVING_START_HOUR, "driving")
                add_remark(remarks, DRIVING_START_HOUR, "Start Driving")
            else:
                # Late start - Add standard on-duty at the actual start time
                add_duty_status(duty_statuses, first_stop_hour, "on-duty")
                add_remark(remarks, first_stop_hour, "Pre-trip Inspection")
                # Add driving 30 minutes after that
                driving_start = min(first_stop_hour + 0.5, 23.9)  # Cap at 23:54 to stay in same day
                add_duty_status(duty_statuses, driving_start, "driving")
                add_remark(remarks, driving_start, "Start Driving")
        else:
            # Not first day - assume continuation from sleeper berth
            # Add on-duty at 6:30 AM for pre-trip
            add_duty_status(duty_statuses, PRE_TRIP_START_HOUR, "on-duty")
            add_remark(remarks, PRE_TRIP_START_HOUR, "Pre-trip Inspection")
            
            # Add driving at 7:00 AM
            add_duty_status(duty_statuses, DRIVING_START_HOUR, "driving")
            add_remark(remarks, DRIVING_START_HOUR, "Start Driving")
        
        # Process each stop to collect the actual status changes during the day
        current_status = "driving"  # Assuming we start driving after pre-trip
        for i, stop in enumerate(day_stops):
            stop_time = datetime.datetime.fromisoformat(stop["estimatedArrival"])
            stop_hour = stop_time.hour + (stop_time.minute / 60)
            
            # Determine duty status based on stop type
            if stop["type"] == "start":
                next_status = "on-duty"
                add_remark(remarks, stop_hour, "Starting Location")
            elif stop["type"] == "pretrip":
                next_status = "on-duty"
                add_remark(remarks, stop_hour, "Pre-trip Inspection")
            elif stop["type"] == "rest":
                next_status = "off-duty"
                add_remark(remarks, stop_hour, "30-Minute Break")
            elif stop["type"] == "fuel":
                next_status = "on-duty"
                add_remark(remarks, stop_hour, "Fueling")
            elif stop["type"] == "off-duty":
                next_status = "off-duty"
                add_remark(remarks, stop_hour, "End of Driving Day")
            elif stop["type"] == "overnight":
                next_status = "sleeper-berth"
                add_remark(remarks, stop_hour, "10-Hour Rest")
            elif stop["type"] in ["pickup", "dropoff", "waypoint"]:
                next_status = "on-duty"
                add_remark(remarks, stop_hour, stop["name"])
            else:
                # Default for unknown stop types
                next_status = "on-duty"
            
            # Only add status change if it's different from current status
            if next_status != current_status:
                add_duty_status(duty_statuses, stop_hour, next_status)
                current_status = next_status
            
            # If this is not the last stop of the day, calculate driving segment to next stop
            if i < len(day_stops) - 1:
                next_stop = day_stops[i + 1]
                next_time = datetime.datetime.fromisoformat(next_stop["estimatedArrival"])
                
                # Check if there's driving between stops
                if next_stop["type"] not in ["off-duty", "overnight"] and stop["type"] not in ["off-duty", "overnight"]:
                    # Assume driving between stops
                    stop_duration = 0.5  # Default 30 minutes
                    driving_start = stop_time + datetime.timedelta(minutes=int(stop_duration * 60))
                    driving_start_hour = driving_start.hour + (driving_start.minute / 60)
                    
                    # Only add driving status if there's enough time between stops
                    time_diff = (next_time - driving_start).total_seconds() / 3600
                    
                    if time_diff > 0.25:  # More than 15 minutes driving
                        if current_status != "driving":
                            add_duty_status(duty_statuses, driving_start_hour, "driving")
                            current_status = "driving"
                        
                        # Estimate miles driven based on time (60 mph average)
                        miles_driven = time_diff * 60
                        current_odometer += round(miles_driven)
                        current_position += miles_driven
                        
                        # Track hours for HOS
                        driving_hours += time_diff
                        on_duty_hours += time_diff
        
        # Ensure standard end-of-day pattern (off-duty at 17:30, sleeper-berth at 19:00)
        # unless it's the last day with early completion
        if not is_early_completion:
            # Make sure we have off-duty at 17:30 for end of driving day
            if not any(abs(s["hour"] - DRIVING_END_HOUR) < 0.01 for s in duty_statuses):
                add_duty_status(duty_statuses, DRIVING_END_HOUR, "off-duty")
                add_remark(remarks, DRIVING_END_HOUR, "End of Driving Day")
            
            # Make sure we have sleeper-berth at 19:00
            if not any(abs(s["hour"] - SLEEPER_START_HOUR) < 0.01 for s in duty_statuses):
                add_duty_status(duty_statuses, SLEEPER_START_HOUR, "sleeper-berth")
                add_remark(remarks, SLEEPER_START_HOUR, "10-Hour Rest")
            
            # If it's not the last day, ensure continuity at midnight
            if not is_last_day:
                # Use 23.99 instead of 24.0 to stay within valid hour range (0-23)
                add_duty_status(duty_statuses, 23.99, "sleeper-berth")
                add_remark(remarks, 23.99, "")
                    
        # Set end location from last stop of the day
        last_stop = day_stops[-1]
        last_stop_time = datetime.datetime.fromisoformat(last_stop["estimatedArrival"])
        daily_log["endTime"] = last_stop_time.isoformat()
        daily_log["endLocation"] = get_location_name(last_stop["coordinates"])
        daily_log["endOdometer"] = current_odometer
        
        # Calculate total miles for the day
        daily_log["totalMiles"] = round(current_position)
        
        # Reset current position for next day
        current_position = 0
        
        # Sort duty statuses and remarks by hour
        duty_statuses.sort(key=lambda x: x["hour"])
        remarks.sort(key=lambda x: x["time"])
        
        # Set log data
        daily_log["graphData"] = {
            "hourData": duty_statuses,
            "remarks": remarks
        }
        
        # Generate detailed log entries
        daily_log["logs"] = generate_log_entries(duty_statuses, remarks, daily_log["startTime"], daily_log["endTime"], current_odometer)
        
        # Check for HOS violations
        if driving_hours > MAX_DRIVING_HOURS:
            daily_log["violations"].append({
                "type": "driving-limit",
                "description": f"Exceeded {MAX_DRIVING_HOURS}-hour driving limit ({driving_hours:.1f} hours)"
            })
        
        if on_duty_hours > MAX_ON_DUTY_HOURS:
            daily_log["violations"].append({
                "type": "on-duty-limit",
                "description": f"Exceeded {MAX_ON_DUTY_HOURS}-hour on-duty limit ({on_duty_hours:.1f} hours)"
            })
        
        # Add total hours
        daily_log["totalHours"] = on_duty_hours
        
        # Add to list of daily logs
        daily_logs.append(daily_log)
    
    # Add additional fields for better presentation
    for log in daily_logs:
        log["licensePlate"] = f"ABC-{random.randint(1000, 9999)} ({random.choice(['CA', 'TX', 'NY', 'FL'])})"
        log["shipperCommodity"] = f"{random.choice(['ABC', 'XYZ', 'Global', 'National'])} Shipping Co. - {random.choice(['Electronics', 'Produce', 'Furniture', 'Machinery'])}"
        log["remarks"] = "No issues reported"
        log["officeAddress"] = "1234 Business Rd, Suite 100, Dallas, TX 75201"
        log["homeAddress"] = "5678 Industrial Ave, Houston, TX 77001"
        
        # Add driving stats
        log["totalMilesDrivingToday"] = f"{log['totalMiles']} miles"
        log["totalMileageToday"] = f"{log['totalMiles']} miles"
    
    return daily_logs

def create_daily_log_sheet(date_str: str) -> DailyLogSheet:
    """
    Create a new daily log sheet
    
    Args:
        date_str: Date string in ISO format (YYYY-MM-DD)
        
    Returns:
        Initialized daily log sheet
    """
    return {
        "date": date_str,
        "driverName": "John Doe",
        "driverID": f"DL{random.randint(10000000, 99999999)}",
        "truckNumber": f"Truck-{random.randint(100, 999)}",
        "trailerNumber": f"Trailer-{random.randint(100, 999)}",
        "carrier": "Sample Carrier Inc.",
        "homeTerminal": "Dallas Terminal",
        "shippingDocNumber": f"BOL-{random.randint(100000, 999999)}",
        "startOdometer": 0,  # Will be set later
        "endOdometer": 0,  # Will be set later
        "startLocation": "",  # Will be set later
        "endLocation": "",  # Will be set later
        "startTime": "",  # Will be set later
        "endTime": "",  # Will be set later
        "totalMiles": 0,  # Will be calculated
        "totalHours": 0,  # Will be calculated
        "logs": [],  # Will be generated
        "certificationTime": "",  # Will be set later
        "certificationStatus": "Uncertified",
        "graphData": {
            "hourData": [],
            "remarks": []
        },
        "violations": []
    }

def add_duty_status(statuses: List[DutyStatus], hour: float, status: str) -> None:
    """
    Add a duty status record to the list
    
    Args:
        statuses: List of duty status records
        hour: Hour of day (decimal, e.g., 14.5 for 2:30 PM)
        status: Status type ('driving', 'on-duty', 'off-duty', 'sleeper-berth')
    """
    # First check if this exact hour already has a status
    for existing in statuses:
        if abs(existing["hour"] - hour) < 0.001:  # Check within a small tolerance
            # Update the existing record instead of adding a new one
            existing["status"] = status
            return
    
    # Add a new status record if no existing one at this hour
    statuses.append({
        "hour": hour,
        "status": status
    })

def add_remark(remarks: List[Remark], hour: float, location: str) -> None:
    """
    Add a remark to the list
    
    Args:
        remarks: List of remarks
        hour: Hour of day (decimal, e.g., 14.5 for 2:30 PM)
        location: Remark text or location
    """
    # Check if a remark already exists at this hour
    for existing in remarks:
        if abs(existing["time"] - hour) < 0.001:  # Check within a small tolerance
            # Update the existing remark instead of adding a new one
            existing["location"] = location
            return
    
    # Add a new remark if no existing one at this hour
    remarks.append({
        "time": hour,
        "location": location
    })

def generate_log_entries(
    duty_statuses: List[DutyStatus],
    remarks: List[Remark],
    start_time_str: str,
    end_time_str: str,
    odometer: int
) -> List[ELDLogEntry]:
    """
    Generate detailed log entries from duty status changes
    
    Args:
        duty_statuses: List of duty status records
        remarks: List of remarks
        start_time_str: Start time ISO string
        end_time_str: End time ISO string
        odometer: Current odometer reading
        
    Returns:
        List of log entries
    """
    if not duty_statuses:
        return []
    
    # Convert strings to datetime
    day_start = datetime.datetime.fromisoformat(start_time_str)
    day_end = datetime.datetime.fromisoformat(end_time_str)
    day_date = day_start.date().isoformat()
    
    # Sort duty statuses by hour
    sorted_statuses = sorted(duty_statuses, key=lambda x: x["hour"])
    
    # Create log entries
    entries = []
    miles_by_status = {"driving": 0, "on-duty": 0, "off-duty": 0, "sleeper-berth": 0}
    
    for i in range(len(sorted_statuses)):
        current = sorted_statuses[i]
        
        # Get timestamp for this status change
        current_hour = current["hour"]
        current_time = day_start.replace(
            hour=int(current_hour),
            minute=int((current_hour % 1) * 60),
            second=0
        )
        
        # If the hour would be the next day, adjust
        if current_time.hour < day_start.hour and current_hour < 12:
            current_time = current_time + datetime.timedelta(days=1)
        
        # Determine end time and location
        if i < len(sorted_statuses) - 1:
            next_status = sorted_statuses[i + 1]
            next_hour = next_status["hour"]
            next_time = day_start.replace(
                hour=int(next_hour),
                minute=int((next_hour % 1) * 60),
                second=0
            )
            
            # If the hour would be the next day, adjust
            if next_time.hour < current_time.hour and next_hour < 12:
                next_time = next_time + datetime.timedelta(days=1)
        else:
            next_time = day_end
        
        # Find the closest remark to this status change
        location = "Unknown Location"
        closest_diff = float('inf')
        
        for remark in remarks:
            time_diff = abs(remark["time"] - current_hour)
            if time_diff < closest_diff:
                closest_diff = time_diff
                location = remark["location"]
        
        # Calculate miles for this segment
        if current["status"] == "driving":
            # Estimate miles based on time (60 mph)
            time_diff = (next_time - current_time).total_seconds() / 3600
            miles = round(time_diff * 60)
        else:
            miles = 0
        
        # Update miles by status
        miles_by_status[current["status"]] += miles
        
        # Add log entry
        entries.append({
            "date": day_date,
            "startTime": current_time.isoformat(),
            "endTime": next_time.isoformat(),
            "status": current["status"],
            "location": location,
            "miles": miles
        })
    
    return entries

def create_eld_data(route, stops, starting_odometer=None):
    """
    Create a complete ELD data structure from route and stops
    
    Args:
        route: Route data with coordinates
        stops: List of stops
        starting_odometer: Starting odometer reading
        
    Returns:
        Complete ELD data structure
    """
    # Generate daily logs
    eld_logs = generate_eld_logs(stops, starting_odometer)
    
    # Create the final data structure
    eld_data = {
        "coordinates": route["coordinates"],
        "stops": stops,
        "totalDistance": route["distance"],
        "totalDuration": route["duration"],
        "eldLogs": eld_logs
    }
    
    return eld_data