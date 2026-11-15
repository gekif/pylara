# Migrations

Migrations are version control for your database schema: small Python files that create or change
tables, run in order, and can be rolled back.

## Generating a migration

```bash
python -m manage make:migration create_posts_table
```

Creates `database/migrations/2026_11_14_103015_create_posts_table.py`. Files run in **file-name
order**, so the timestamp prefix keeps them chronological. A name of the form `create_<table>_table`
generates a ready-to-edit `Schema.create` body. `make:model Post -m` creates a model and its
migration together.

## Structure

```python
from pylara.database.migration import Migration, Schema


class CreatePostsTable(Migration):

    def up(self):
        return Schema.create("posts", lambda t: [
            t.id(),
            t.integer("user_id"),
            t.string("title"),
            t.text("body").nullable(),
            t.boolean("published").default(False),
            t.timestamps(),
            t.foreign("user_id").references("id").on("users"),
        ])

    def down(self):
        return Schema.drop("posts")
```

`up()` and `down()` return the list of SQL statements to execute. One migration class per file.

## Tables

```python
Schema.create("posts", callback)        # CREATE TABLE IF NOT EXISTS
Schema.table("posts", callback)         # add columns / indexes to an existing table
Schema.drop("posts")                    # DROP TABLE IF EXISTS
Schema.drop_if_exists("posts")
Schema.has_table("posts", connection)   # bool
```

`Schema.table` can only **add** columns (SQLite's `ALTER TABLE ... ADD COLUMN`). Renaming or dropping a
column needs a manual table rebuild.

## Columns

| Method | SQL type |
|---|---|
| `t.id(name="id")` | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| `t.string(name, length=255)` | `VARCHAR(length)` |
| `t.text(name)` | `TEXT` |
| `t.integer(name)` / `t.big_integer(name)` | `INTEGER` / `BIGINT` |
| `t.float(name)` | `REAL` |
| `t.decimal(name, precision=8, scale=2)` | `DECIMAL(p,s)` |
| `t.boolean(name)` | `BOOLEAN DEFAULT 0` |
| `t.json(name)` | `TEXT` (you encode/decode) |
| `t.timestamp(name)` | `TIMESTAMP` |
| `t.timestamps()` | `created_at` and `updated_at` |
| `t.soft_deletes()` | `deleted_at` (see [ORM](orm.md#soft-deletes)) |

### Modifiers (chain after a column)

```python
t.string("nickname").nullable()
t.string("role").not_null().default("member")
t.integer("score").default(0)
t.string("email").unique("email")       # also creates a unique index
```

- `default(value)` handles strings (safely quoted), numbers, `True`/`False` and `None`.
- `not_null()` adds `NOT NULL`. Columns are nullable by default.
- `unique(column=None)` and `index(column)` create indexes named `idx_<table>_<column>`.

### Foreign keys

```python
t.foreign("user_id").references("id").on("users")
```

SQLite enforces foreign keys only when `PRAGMA foreign_keys = ON`, which the generated
`bootstrap/app.py` sets.

### Adding a column later

```python
class AddSlugToPostsTable(Migration):
    def up(self):
        return Schema.table("posts", lambda t: [t.string("slug").nullable()])

    def down(self):
        return []      # SQLite cannot drop a column easily; leave empty or rebuild the table
```

## Running migrations

```bash
python -m manage migrate                     # run everything pending
python -m manage migrate:status              # Ran / Pending list
python -m manage migrate:rollback            # undo the last batch
python -m manage migrate:rollback --steps 2  # undo the last two batches
```

Every `migrate` run is one **batch**; `migrate:rollback` calls `down()` for each migration in the
latest batch, newest first. Applied migrations are recorded in a `migrations` table (created
automatically), so running `migrate` twice is safe.

### From code (tests, scripts)

```python
import os
from pylara.database.migration import Migrator, discover
from pylara.orm.model import get_connection

migrator = Migrator(get_connection())
migrations = discover(os.path.join(BASE, "database", "migrations"))
migrator.run(migrations)
migrator.status(migrations)        # [(name, has_run), ...]
migrator.rollback(dict(migrations), steps=1)
```
