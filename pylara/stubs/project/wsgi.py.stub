"""WSGI entry point for production servers.

    python -m pip install gunicorn            # Linux / macOS
    python -m gunicorn wsgi:application

    python -m pip install waitress            # Windows
    python -m waitress --listen=0.0.0.0:8000 wsgi:application
"""
from bootstrap.app import app

application = app
