"""
ASGI config for eld_api project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eld_api.settings')
application = get_asgi_application()