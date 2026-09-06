"""WSGI entry point — gunicorn tikotime.wsgi"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tikotime.settings")

application = get_wsgi_application()
