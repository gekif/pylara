"""
bootstrap/app.py - Merakit aplikasi: app, database, seed demo, dan route.
"""

import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from pylara import Application
from pylara.orm.model import set_connection
from pylara.support.hashing import Hash

app = Application(base_path=BASE)

# Database demo di memori. Ganti ke file untuk data yang awet, mis.
# sqlite3.connect(os.path.join(BASE, "storage", "app.sqlite"), check_same_thread=False)
conn = sqlite3.connect(":memory:", check_same_thread=False)
set_connection("default", conn)

conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(255),
        email VARCHAR(255) UNIQUE,
        password VARCHAR(255),
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title VARCHAR(255),
        body TEXT,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    );
""")

from app.models.post import Post  # noqa: E402
from app.models.user import User  # noqa: E402

if User.query().count() == 0:
    alice = User.create(name="Alice", email="alice@example.com", password=Hash.make("secret"))
    bob = User.create(name="Bob", email="bob@example.com", password=Hash.make("secret"))
    Post.create(user_id=alice.id, title="Hello World", body="Postingan pertama!")
    Post.create(user_id=alice.id, title="Post Kedua", body="Hari yang lain.")
    Post.create(user_id=bob.id, title="Pemikiran Bob", body="Berpikir dalam.")

from routes.web import register_routes  # noqa: E402
register_routes(app)
