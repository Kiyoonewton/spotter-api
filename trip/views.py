import traceback
import logging
logger = logging.getLogger(__name__)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import datetime
import json

# Import ELD modules for processing
from eld_modules.route_calculator import calculate_multi_stop_route
from eld_modules.stop_generator import generate_stops
from eld_modules.eld_log_generator import generate_eld_logs, create_eld_data

class TripELDView(APIView):
    """
    API endpoint that processes trip information and returns ELD data
    """
    def post(self, request, format=None):
        try:
            # Parse input data
            trip_data = request.data.get("trip", {})
            
            # Extract locations
            current_location = {
                "lat": trip_data.get("currentLocation", {}).get("coordinates", {}).get("latitude"),
                "lng": trip_data.get("currentLocation", {}).get("coordinates", {}).get("longitude")
            }
            
            pickup_location = {
                "lat": trip_data.get("pickupLocation", {}).get("coordinates", {}).get("latitude"),
                "lng": trip_data.get("pickupLocation", {}).get("coordinates", {}).get("longitude")
            }
            
            dropoff_location = {
                "lat": trip_data.get("dropoffLocation", {}).get("coordinates", {}).get("latitude"),
                "lng": trip_data.get("dropoffLocation", {}).get("coordinates", {}).get("longitude")
            }
            
            # Validate locations
            for location in [current_location, pickup_location, dropoff_location]:
                if not location["lat"] or not location["lng"]:
                    return Response(
                        {"error": "Missing or invalid coordinates in trip data"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Extract cycle used
            cycle_used = trip_data.get("currentCycleUsed", 0)
            
            # Build location list
            locations = [current_location, pickup_location, dropoff_location]
            
            # Get current date at 6:00 AM for start time
            start_datetime = datetime.datetime.now().replace(
                hour=6, minute=0, second=0, microsecond=0
            )
            
            # Calculate route
            route = calculate_multi_stop_route(locations)
            
            # Generate stops
            stops = generate_stops(
                route, 
                locations, 
                start_datetime, 
                cycle_used
            )
            
            # Generate ELD data
            eld_data = create_eld_data(route, stops)
            
            return Response(eld_data)
            
        except KeyError as e:
            return Response(
                {"error": f"Missing required field: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Error processing request: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )