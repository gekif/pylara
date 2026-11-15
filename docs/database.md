# Database: Getting Started

PyLara talks to **SQLite** through Python's standard `sqlite3` module. This page covers
connections; migrations, the query builder and models have their own pages.

## Configuring the connection

A connection is registered once, usually in `bootstrap/app.py` (the generated project already does
this):

```python
import sqlite3
from pylara.orm.model import set_connection

connection = sqlite3.connect("storage/database.sqlite", check_same_thread=False)
connection.execute("PRAGMA foreign_keys = ON")      # SQLite ignores foreign keys unless enabled
set_connection("default", connection)
```

- The name `"default"` is what models use unless they say otherwise.
- `":memory:"` gives a throw-away database, which is ideal for tests.
- `check_same_thread=False` is needed because the WSGI server may handle requests on another
  thread than the one that created the connection. See [Deployment](deployment.md#threads-and-sqlite)
  for the consequences.

### Several connections

```python
set_connection("default", sqlite3.connect("storage/app.sqlite", check_same_thread=False))
set_connection("analytics", sqlite3.connect("storage/analytics.sqlite", check_same_thread=False))

class Event(Model):
    table = "events"
    connection = "analytics"
```

`get_connection(name="default")` returns a registered connection (or raises `RuntimeError`).

## Running raw SQL

For anything the query builder cannot express, use the connection directly. **Always pass values as
parameters** (`?`), never by string formatting:

```python
from pylara.orm.model import get_connection

db = get_connection()
rows = db.execute("SELECT name, COUNT(*) FROM posts GROUP BY name HAVING COUNT(*) > ?", [1]).fetchall()

db.execute("UPDATE posts SET views = views + 1 WHERE id = ?", [post_id])
db.commit()
```

## Transactions

Each `Model.save()`, `Model.delete()` and mass `update()`/`delete()` **commits immediately**. For
several statements that must succeed or fail together use the connection:

```python
db = get_connection()
try:
    db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", [50, 1])
    db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", [50, 2])
    db.commit()
except Exception:
    db.rollback()
    raise
```

Do not mix model calls (which commit) into such a block.

## Other databases

1.0 is written for SQLite: it uses the `?` parameter style, `AUTOINCREMENT` and `sqlite_master`.
PostgreSQL/MySQL drivers are not supported. See [Limitations](limitations.md).
