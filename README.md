# ELD API

A simple Django REST API for generating Electronic Logging Device (ELD) data for truck routes based on trip information.

## Overview

This API accepts trip information including origin, pickup, and dropoff locations, then generates realistic ELD data including:

- Route data with GPS coordinates
- Stops (start, pickup, dropoff, rest, fuel, overnight)
- Duty status changes (driving, on-duty, off-duty, sleeper-berth)
- Daily log sheets with all required ELD information

## Installation

### Prerequisites

- Python 3.7 or higher
- Django 3.2 or higher
- Django REST Framework
- Required packages: `requests`

### Setup

1. Clone the repository
   ```bash
   git clone https://github.com/your-username/eld-api.git
   cd eld-api
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install django djangorestframework requests
   ```

4. Run migrations
   ```bash
   python manage.py migrate
   ```

5. Start the development server
   ```bash
   python manage.py runserver
   ```

## API Usage

### Generate ELD Data

**Endpoint:** `POST /api/trip/`

**Request Format:**
```json
{
  "trip": {
    "currentLocation": {
      "coordinates": {
        "latitude": 34.053691,
        "longitude": -118.242766
      }
    },
    "pickupLocation": {
      "coordinates": {
        "latitude": 41.875562,
        "longitude": -87.624421
      }
    },
    "dropoffLocation": {
      "coordinates": {
        "latitude": 40.712728,
        "longitude": -74.006015
      }
    },
    "currentCycleUsed": 0
  }
}
```

**Response:**
```json
{
  "coordinates": [...],  // Array of [longitude, latitude] coordinates along the route
  "stops": [
    {
      "type": "start|pickup|dropoff|fuel|rest|overnight|off-duty",
      "name": "Stop name",
      "coordinates": [longitude, latitude],
      "duration": "Duration string",
      "estimatedArrival": "ISO datetime string"
    },
    ...
  ],
  "totalDistance": 2937.5,  // Total distance in miles
  "totalDuration": 176250,  // Total duration in seconds
  "eldLogs": [
    {
      "date": "2025-03-10",
      "driverName": "John Doe",
      "driverID": "DL12345678",
      "truckNumber": "Truck-123",
      "startLocation": "Los Angeles, CA",
      "endLocation": "Denver, CO",
      ...
    },
    ...
  ]
}
```

## Example Curl Request

```bash
curl -X POST http://127.0.0.1:8000/api/trip/ \
  -H "Content-Type: application/json" \
  -d '{
    "trip": {
      "currentLocation": {
        "coordinates": {
          "latitude": 34.053691,
          "longitude": -118.242766
        }
      },
      "pickupLocation": {
        "coordinates": {
          "latitude": 41.875562,
          "longitude": -87.624421
        }
      },
      "dropoffLocation": {
        "coordinates": {
          "latitude": 40.712728,
          "longitude": -74.006015
        }
      },
      "currentCycleUsed": 0
    }
  }'
```

## Notes

- The API uses the Open Source Routing Machine (OSRM) service for route calculations. If the service is unavailable, it will generate a mock route.
- Location names are retrieved using the OpenStreetMap Nominatim API, with fallbacks to random city names if the service is unavailable.
- No database is used - all data is generated on-the-fly based on the input trip information.
- The API follows Hours of Service (HOS) regulations for generating realistic driver logs.

## Deployment

For production deployment, consider:

1. Using a production-grade web server like Gunicorn or uWSGI
2. Setting up proper logging
3. Configuring a static files server
4. Setting `DEBUG = False` in settings.py
5. Updating `ALLOWED_HOSTS` in settings.py
6. Using environment variables for sensitive settings

Example with Gunicorn:

```bash
pip install gunicorn
gunicorn eld_api.wsgi:application --bind 0.0.0.0:8000
```# eld_api
# spotter-api
