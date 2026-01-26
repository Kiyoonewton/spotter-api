#!/usr/bin/env python
"""
Test script for cycle hours calculation
"""
import sys
import os
import django
import datetime

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# Import services
from domain.route.services import calculate_multi_stop_route
from domain.stop.services import generate_stops
from domain.eld_log.services import create_eld_data

# Test locations
current_location = {"lat": 32.7767, "lng": -96.7970}  # Dallas, TX
pickup_location = {"lat": 34.0522, "lng": -118.2437}  # Los Angeles, CA
dropoff_location = {"lat": 37.7749, "lng": -122.4194}  # San Francisco, CA

locations = [current_location, pickup_location, dropoff_location]

# Test with different cycle hours
test_cases = [
    {"name": "Low cycle hours (0)", "cycle_used": 0},
    {"name": "Medium cycle hours (35)", "cycle_used": 35},
    {"name": "High cycle hours (60)", "cycle_used": 60},
    {"name": "Very high cycle hours (68)", "cycle_used": 68},
]

for test_case in test_cases:
    print(f"\n{'=' * 80}")
    print(f"TEST: {test_case['name']}")
    print(f"{'=' * 80}")

    # Get current date at 6:00 AM for start time
    start_datetime = datetime.datetime.now().replace(
        hour=6, minute=0, second=0, microsecond=0
    )

    # Calculate route
    print(f"Calculating route from Dallas -> LA -> San Francisco...")
    route = calculate_multi_stop_route(locations)
    print(f"Total distance: {route['distance']:.1f} miles")
    print(f"Total duration: {route['duration']:.1f} hours")

    # Generate stops
    print(f"\nGenerating stops with {test_case['cycle_used']} cycle hours already used...")
    stops = generate_stops(
        route,
        locations,
        start_datetime,
        test_case['cycle_used']
    )

    print(f"Generated {len(stops)} stops")

    # Display cycle hours information
    if stops and "cycleHoursUsed" in stops[0]:
        print(f"\n--- CYCLE HOURS SUMMARY ---")
        print(f"Cycle hours used: {stops[0]['cycleHoursUsed']:.1f}")
        print(f"Cycle hours remaining: {stops[0]['cycleHoursRemaining']:.1f}")
        print(f"Cycle hours available: {stops[0]['cycleHoursAvailable']}")

        if "cycleWarning" in stops[0]:
            print(f"\n⚠️  WARNING: {stops[0]['cycleWarning']}")
    else:
        print("\n⚠️  No cycle hours information found in stops!")

    # Display first few stops
    print(f"\n--- FIRST 5 STOPS ---")
    for i, stop in enumerate(stops[:5]):
        print(f"{i+1}. {stop['type']}: {stop['name']}")
        print(f"   Arrival: {stop['estimatedArrival']}")
        print(f"   Duration: {stop['duration']}")

    # Generate ELD data
    print(f"\nGenerating ELD logs...")
    eld_data = create_eld_data(route, stops)
    print(f"Generated {len(eld_data['eldLogs'])} daily log sheets")

    # Display ELD log cycle hours
    if eld_data['eldLogs']:
        first_log = eld_data['eldLogs'][0]
        if "cycleHoursUsed" in first_log:
            print(f"\n--- ELD LOG CYCLE INFO ---")
            print(f"Cycle hours used: {first_log['cycleHoursUsed']:.1f}")
            print(f"Cycle hours remaining: {first_log['cycleHoursRemaining']:.1f}")
            if "cycleWarning" in first_log:
                print(f"Warning: {first_log['cycleWarning']}")

print(f"\n{'=' * 80}")
print("All tests completed!")
print(f"{'=' * 80}")
