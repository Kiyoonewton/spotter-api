"""
Geocoding infrastructure - External geocoding service integration
"""
from .nominatim_client import get_location_name_from_api

__all__ = ['get_location_name_from_api']
