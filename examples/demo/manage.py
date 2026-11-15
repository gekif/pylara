#!/usr/bin/env python3
"""
manage.py - PyLara CLI (like Laravel's artisan)

Usage:
    python manage.py serve
    python manage.py serve --host 0.0.0.0 --port 8080
    python manage.py route:list
    python manage.py make:controller ProductController
    python manage.py make:model Product
    python manage.py make:middleware AuthMiddleware
    python manage.py make:migration create_products_table
    python manage.py migrate
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from pylara.console.console import console

if __name__ == "__main__":
    sys.exit(console.run())
