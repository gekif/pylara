"""Builds the application: environment, database, providers and routes."""
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from pylara import Application
from pylara.orm.model import set_connection

app = Application(base_path=BASE)

# ── Database ────────────────────────────────────────────────────────────────
database = app.env("DB_DATABASE", "storage/database.sqlite")
if database != ":memory:":
    if not os.path.isabs(database):
        database = os.path.join(BASE, database)
    os.makedirs(os.path.dirname(database), exist_ok=True)

connection = sqlite3.connect(database, check_same_thread=False)
connection.execute("PRAGMA foreign_keys = ON")
if database != ":memory:":
    connection.execute("PRAGMA journal_mode=WAL")       # lets several processes read while one writes
set_connection("default", connection)

# ── Providers and routes ────────────────────────────────────────────────────
from app.providers.app_service_provider import AppServiceProvider  # noqa: E402
from routes import api, web  # noqa: E402

app.register(AppServiceProvider)
web.register(app)
api.register(app)
