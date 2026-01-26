#!/usr/bin/env python
"""
Test script for recap calculations
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

print("=" * 80)
print("ELD API RECAP CALCULATIONS TEST")
print("=" * 80)

# Get current date at 6:00 AM for start time
start_datetime = datetime.datetime.now().replace(
    hour=6, minute=0, second=0, microsecond=0
)

# Calculate route
print(f"\nCalculating route from Dallas -> LA -> San Francisco...")
route = calculate_multi_stop_route(locations)
print(f"Total distance: {route['distance']:.1f} miles")
print(f"Total duration: {route['duration']:.1f} hours")

# Generate stops with cycle hours
print(f"\nGenerating stops with 0 cycle hours already used...")
stops = generate_stops(
    route,
    locations,
    start_datetime,
    0  # Starting with 0 cycle hours
)

print(f"Generated {len(stops)} stops")

# Generate ELD data
print(f"\nGenerating ELD logs...")
eld_data = create_eld_data(route, stops)
print(f"Generated {len(eld_data['eldLogs'])} daily log sheets")

# Display recap data for each day
print(f"\n{'=' * 80}")
print("RECAP DATA BY DAY")
print(f"{'=' * 80}")

for i, log in enumerate(eld_data['eldLogs']):
    print(f"\nDay {i+1}: {log['date']}")
    print(f"  On-Duty Hours Today: {log.get('totalHours', 0):.2f} hours")

    if 'recap' in log:
        recap = log['recap']
        print(f"\n  === 70-Hour/8-Day Rule ===")
        print(f"  A. Hours Last 7 Days (including today): {recap['rule70Hour8Day']['hoursLast7Days']:.2f}")
        print(f"  B. Hours Available Tomorrow (70 - A): {recap['rule70Hour8Day']['hoursAvailableTomorrow']:.2f}")
        print(f"  C. Hours Last 5 Days (including today): {recap['rule70Hour8Day']['hoursLast5Days']:.2f}")

        print(f"\n  === 60-Hour/7-Day Rule ===")
        print(f"  A. Hours Last 8 Days (including today): {recap['rule60Hour7Day']['hoursLast8Days']:.2f}")
        print(f"  B. Hours Available Tomorrow (60 - A): {recap['rule60Hour7Day']['hoursAvailableTomorrow']:.2f}")
        print(f"  C. Hours Last 7 Days (including today): {recap['rule60Hour7Day']['hoursLast7Days']:.2f}")

        # Check warnings
        if recap['rule70Hour8Day']['hoursAvailableTomorrow'] < 10:
            print(f"\n  ⚠️  WARNING: Less than 10 hours available under 70-hour rule!")
        if recap['rule60Hour7Day']['hoursAvailableTomorrow'] < 10:
            print(f"\n  ⚠️  WARNING: Less than 10 hours available under 60-hour rule!")
    else:
        print(f"  ⚠️  No recap data found!")

print(f"\n{'=' * 80}")
print("Test completed!")
print(f"{'=' * 80}")
