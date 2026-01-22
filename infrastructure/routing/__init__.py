"""
Routing infrastructure - External routing service integration
"""
from .osrm_client import fetch_route, generate_mock_route

__all__ = ['fetch_route', 'generate_mock_route']
