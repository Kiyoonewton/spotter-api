"""URL configuration for eld_api project."""
from django.urls import path, include

urlpatterns = [
    path('api/', include('trip.urls')),
]