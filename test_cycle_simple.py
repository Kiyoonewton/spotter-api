#!/usr/bin/env python
"""
Simple test for cycle hours calculation without external API calls
"""
import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test the constants and functions directly
from domain.stop.services import (
    MAX_CYCLE_HOURS,
    MAX_DAILY_DRIVING,
    MAX_DAILY_ON_DUTY,
    FUEL_STOP_INTERVAL,
    PICKUP_DURATION,
    DROPOFF_DURATION
)

print("=" * 80)
print("ELD API CYCLE HOURS CONFIGURATION TEST")
print("=" * 80)

print("\n--- HOS REGULATION CONSTANTS ---")
print(f"Max cycle hours (70-hour/8-day rule): {MAX_CYCLE_HOURS} hours")
print(f"Max daily driving hours: {MAX_DAILY_DRIVING} hours")
print(f"Max daily on-duty hours: {MAX_DAILY_ON_DUTY} hours")

print("\n--- STOP DURATION CONSTANTS ---")
print(f"Fuel stop interval: {FUEL_STOP_INTERVAL} miles (should be 1000)")
print(f"Pickup duration: {PICKUP_DURATION} hours (should be 1.0)")
print(f"Dropoff duration: {DROPOFF_DURATION} hours (should be 1.0)")

print("\n--- VALIDATION ---")
errors = []

if FUEL_STOP_INTERVAL != 1000:
    errors.append(f"❌ FUEL_STOP_INTERVAL is {FUEL_STOP_INTERVAL}, expected 1000")
else:
    print("✅ Fuel stop interval is correct (1000 miles)")

if PICKUP_DURATION != 1.0:
    errors.append(f"❌ PICKUP_DURATION is {PICKUP_DURATION}, expected 1.0")
else:
    print("✅ Pickup duration is correct (1 hour)")

if DROPOFF_DURATION != 1.0:
    errors.append(f"❌ DROPOFF_DURATION is {DROPOFF_DURATION}, expected 1.0")
else:
    print("✅ Dropoff duration is correct (1 hour)")

if MAX_CYCLE_HOURS != 70:
    errors.append(f"❌ MAX_CYCLE_HOURS is {MAX_CYCLE_HOURS}, expected 70")
else:
    print("✅ Max cycle hours is correct (70 hours)")

if MAX_DAILY_DRIVING != 11:
    errors.append(f"❌ MAX_DAILY_DRIVING is {MAX_DAILY_DRIVING}, expected 11")
else:
    print("✅ Max daily driving hours is correct (11 hours)")

if MAX_DAILY_ON_DUTY != 14:
    errors.append(f"❌ MAX_DAILY_ON_DUTY is {MAX_DAILY_ON_DUTY}, expected 14")
else:
    print("✅ Max daily on-duty hours is correct (14 hours)")

print("\n" + "=" * 80)
if errors:
    print("VALIDATION FAILED")
    for error in errors:
        print(error)
else:
    print("ALL VALIDATIONS PASSED! ✅")
print("=" * 80)
