"""
ELD Log Generator Module
Generates Electronic Logging Device data based on calculated stops
"""
import datetime
import math
import random
import json
from typing import Dict, List, Tuple, Any, Optional, Union

# Import domain services
from domain.location.services import get_location_name

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

def calculate_recap_data(daily_logs: List[Dict[str, Any]], current_day_index: int) -> Dict[str, Any]:
    """
    Calculate recap data for HOS compliance tracking

    Args:
        daily_logs: List of all daily log sheets
        current_day_index: Index of the current day (0-based)

    Returns:
        Dictionary with recap calculations for both 70-hour/8-day and 60-hour/7-day rules
    """
    # Get total on-duty hours for current day
    on_duty_hours_today = daily_logs[current_day_index].get("totalHours", 0)

    # Calculate hours for different lookback periods
    def sum_hours_for_period(days_back: int) -> float:
        """Sum on-duty hours for the last N days including today"""
        total_hours = 0
        start_index = max(0, current_day_index - days_back + 1)
        for i in range(start_index, current_day_index + 1):
            total_hours += daily_logs[i].get("totalHours", 0)
        return round(total_hours, 2)

    # 70-Hour/8-Day Rule calculations
    hours_last_7_days = sum_hours_for_period(7)  # Last 7 days including today
    hours_last_5_days = sum_hours_for_period(5)  # Last 5 days including today
    hours_available_70 = max(0, round(70 - hours_last_7_days, 2))

    # 60-Hour/7-Day Rule calculations
    hours_last_8_days = sum_hours_for_period(8)  # Last 8 days including today
    hours_last_7_days_60 = sum_hours_for_period(7)  # Last 7 days including today (for 60-hour rule)
    hours_available_60 = max(0, round(60 - hours_last_8_days, 2))

    return {
        "onDutyHoursToday": round(on_duty_hours_today, 2),
        "rule70Hour8Day": {
            "hoursLast7Days": hours_last_7_days,  # A: Total hours on duty last 7 days
            "hoursAvailableTomorrow": hours_available_70,  # B: 70 - A
            "hoursLast5Days": hours_last_5_days  # C: Total hours on duty last 5 days
        },
        "rule60Hour7Day": {
            "hoursLast8Days": hours_last_8_days,  # A: Total hours on duty last 8 days
            "hoursAvailableTomorrow": hours_available_60,  # B: 60 - A
            "hoursLast7Days": hours_last_7_days_60  # C: Total hours on duty last 7 days
        }
    }

def generate_eld_logs(stops: List, starting_odometer: int = None, total_route_distance: float = None) -> List[DailyLogSheet]:
    """
    Generate ELD logs from a list of stops

    Args:
        stops: List of stops with type, coordinates, estimatedArrival
        starting_odometer: Starting odometer reading (defaults to random value)
        total_route_distance: Total distance of the route in miles (for accurate distribution)

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
    
    # Calculate total driving hours across all days for proportional distance distribution
    total_driving_hours = 0
    daily_driving_hours_list = []

    if total_route_distance:
        # First pass: calculate driving hours for each day
        for day, day_stops in sorted(stops_by_day.items()):
            day_driving_hours = 0

            for i in range(len(day_stops) - 1):
                stop = day_stops[i]
                next_stop = day_stops[i + 1]

                # Skip overnight and off-duty stops
                if next_stop["type"] in ["off-duty", "overnight"] or stop["type"] in ["off-duty", "overnight"]:
                    continue

                stop_time = datetime.datetime.fromisoformat(stop["estimatedArrival"])
                next_time = datetime.datetime.fromisoformat(next_stop["estimatedArrival"])

                # Determine stop duration based on type
                stop_duration = 0.5  # Default 30 minutes
                if stop["type"] == "pickup":
                    stop_duration = 1.0
                elif stop["type"] == "dropoff":
                    stop_duration = 1.0
                elif stop["type"] == "fuel":
                    stop_duration = 0.5
                elif stop["type"] == "waypoint":
                    stop_duration = 0.5

                driving_start = stop_time + datetime.timedelta(minutes=int(stop_duration * 60))
                time_diff = (next_time - driving_start).total_seconds() / 3600

                # Cap at 11 hours max driving per day
                remaining_hours = max(0, 11.0 - day_driving_hours)
                time_diff = min(time_diff, remaining_hours, 11.0)

                if time_diff > 0.25:  # More than 15 minutes
                    day_driving_hours += time_diff

            daily_driving_hours_list.append(day_driving_hours)
            total_driving_hours += day_driving_hours

        # Avoid division by zero
        if total_driving_hours == 0:
            total_driving_hours = 1

    # Initialize daily logs
    daily_logs = []
    current_odometer = starting_odometer
    current_position = 0  # Track miles driven
    cumulative_miles = 0  # Track cumulative mileage across all days

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

        # Track daily mileage from stops
        daily_miles = 0

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
        # NOTE: Removed the old mileage calculation from distanceFromPrevious
        # This was causing unrealistic daily mileage calculations (1000+ miles/day)
        # Mileage is now calculated accurately from actual driving time later in the code

        for stop in day_stops:
            stop_time = datetime.datetime.fromisoformat(stop["estimatedArrival"])
            stop_hour = stop_time.hour + (stop_time.minute / 60)
            stop_type = stop["type"]

            # REMOVED: This was adding incorrect mileage
            # if "distanceFromPrevious" in stop:
            #     daily_miles += stop["distanceFromPrevious"]

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
            # Get location name for all stops
            stop_location = get_location_name(stop["coordinates"])

            if stop["type"] == "start":
                next_status = "on-duty"
                add_remark(remarks, stop_hour, stop_location)
            elif stop["type"] == "pretrip":
                next_status = "on-duty"
                add_remark(remarks, stop_hour, stop_location)
            elif stop["type"] == "rest":
                next_status = "off-duty"
                add_remark(remarks, stop_hour, stop_location)
            elif stop["type"] == "fuel":
                next_status = "on-duty"
                add_remark(remarks, stop_hour, stop_location)
            elif stop["type"] == "off-duty":
                next_status = "off-duty"
                add_remark(remarks, stop_hour, stop_location)
            elif stop["type"] == "overnight":
                next_status = "sleeper-berth"
                add_remark(remarks, stop_hour, stop_location)
            elif stop["type"] in ["pickup", "dropoff", "waypoint"]:
                next_status = "on-duty"
                add_remark(remarks, stop_hour, stop_location)
            else:
                # Default for unknown stop types
                next_status = "on-duty"
                add_remark(remarks, stop_hour, stop_location)
            
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
                    # Determine stop duration based on type
                    stop_duration = 0.5  # Default 30 minutes
                    if stop["type"] == "pickup":
                        stop_duration = 1.0  # 1 hour for pickup
                    elif stop["type"] == "dropoff":
                        stop_duration = 1.0  # 1 hour for dropoff
                    elif stop["type"] == "fuel":
                        stop_duration = 0.5  # 30 minutes for fuel
                    elif stop["type"] == "waypoint":
                        stop_duration = 0.5  # 30 minutes for waypoint

                    driving_start = stop_time + datetime.timedelta(minutes=int(stop_duration * 60))
                    driving_start_hour = driving_start.hour + (driving_start.minute / 60)
                    
                    # Only add driving status if there's enough time between stops
                    time_diff = (next_time - driving_start).total_seconds() / 3600

                    # Cap driving time at maximum daily driving limit
                    # This prevents unrealistic mileage calculations when stops span long periods
                    max_driving_remaining = MAX_DRIVING_HOURS - driving_hours
                    time_diff = min(time_diff, max_driving_remaining, 11.0)  # Never exceed 11 hours

                    if time_diff > 0.25:  # More than 15 minutes driving
                        if current_status != "driving":
                            add_duty_status(duty_statuses, driving_start_hour, "driving")
                            current_status = "driving"

                        # Track hours for HOS
                        driving_hours += time_diff
                        on_duty_hours += time_diff

        # After processing all stops, calculate daily mileage
        # Use time-based calculation (60 mph average)
        daily_miles = driving_hours * 60

        # Cap at realistic daily maximum based on HOS regulations
        # Max 11 hours driving at 60 mph = 660 miles, but typically 480-550 miles
        daily_miles = min(daily_miles, 660)
        
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

        # Update cumulative miles and odometer
        cumulative_miles += daily_miles
        current_odometer += round(daily_miles)
        daily_log["endOdometer"] = current_odometer

        # Calculate total miles for the day
        daily_log["totalMiles"] = round(daily_miles)
        daily_log["cumulativeMiles"] = round(cumulative_miles)

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

        # Calculate total on-duty hours from duty status graph
        total_on_duty_hours = 0
        sorted_statuses = sorted(duty_statuses, key=lambda x: x["hour"])

        for i in range(len(sorted_statuses) - 1):
            current_status = sorted_statuses[i]["status"]
            if current_status in ["driving", "on-duty"]:
                next_hour = sorted_statuses[i + 1]["hour"]
                current_hour = sorted_statuses[i]["hour"]
                segment_hours = next_hour - current_hour
                total_on_duty_hours += segment_hours

        # Handle last segment
        if sorted_statuses and sorted_statuses[-1]["status"] in ["driving", "on-duty"]:
            # Extend to end of day or last stop time
            last_stop_hour = last_stop_time.hour + (last_stop_time.minute / 60)
            # Only add hours until the last stop or end of standard driving day
            remaining_hours = min(24, last_stop_hour) - sorted_statuses[-1]["hour"]
            if remaining_hours > 0:
                total_on_duty_hours += remaining_hours

        daily_log["totalHours"] = round(total_on_duty_hours, 2)

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
        log["totalMileageToday"] = f"{log['cumulativeMiles']} miles"

    # Add cycle hours information if available from stops
    if stops and len(stops) > 0 and "cycleHoursUsed" in stops[0]:
        for log in daily_logs:
            log["cycleHoursUsed"] = stops[0]["cycleHoursUsed"]
            log["cycleHoursRemaining"] = stops[0]["cycleHoursRemaining"]
            log["cycleHoursAvailable"] = stops[0]["cycleHoursAvailable"]
            if "cycleWarning" in stops[0]:
                log["cycleWarning"] = stops[0]["cycleWarning"]

    # Post-process: Adjust mileage distribution if total route distance is provided
    if total_route_distance:
        # Calculate total miles accumulated across all days
        total_accumulated_miles = sum(log["totalMiles"] for log in daily_logs)

        # If there's a significant discrepancy, redistribute proportionally
        if abs(total_accumulated_miles - total_route_distance) > 10:  # More than 10 miles difference
            # Calculate total on-duty hours across all days (from graph data)
            total_on_duty_hours = sum(log.get("totalHours", 0) for log in daily_logs)

            if total_on_duty_hours > 0:
                # Redistribute mileage proportionally based on on-duty hours
                current_odometer = daily_logs[0]["startOdometer"]
                cumulative_miles = 0

                for log in daily_logs:
                    day_hours = log.get("totalHours", 0)
                    if day_hours > 0:
                        # Proportional share of total distance
                        proportional_miles = (day_hours / total_on_duty_hours) * total_route_distance
                        # Cap at 660 miles per day (11 hours × 60 mph)
                        daily_miles = min(proportional_miles, 660)
                    else:
                        daily_miles = 0

                    # Update mileage fields
                    log["totalMiles"] = round(daily_miles)
                    cumulative_miles += daily_miles
                    log["cumulativeMiles"] = round(cumulative_miles)
                    log["totalMilesDrivingToday"] = f"{round(daily_miles)} miles"
                    log["totalMileageToday"] = f"{round(cumulative_miles)} miles"

                    # Update odometer
                    current_odometer += round(daily_miles)
                    log["endOdometer"] = current_odometer

    # Calculate recap data for each day
    for day_index, log in enumerate(daily_logs):
        recap = calculate_recap_data(daily_logs, day_index)
        log["recap"] = recap

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
    
    total_on_duty_hours = 0
    
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
    # Generate daily logs with total route distance for accurate mileage distribution
    eld_logs = generate_eld_logs(stops, starting_odometer, route["distance"])
    
    # Create the final data structure
    eld_data = {
        "coordinates": route["coordinates"],
        "stops": stops,
        "totalDistance": route["distance"],
        "totalDuration": route["duration"],
        "eldLogs": eld_logs
    }
    
    return eld_data