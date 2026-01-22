from django.urls import path
from .views import TripELDView

urlpatterns = [
    path('trip/', TripELDView.as_view(), name='trip-eld'),
]