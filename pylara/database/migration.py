"""
Migration - Database schema migration system.
Inspired by Laravel's Migration system.
"""

import importlib.util
import os
import re
import sqlite3
from typing import List, Tuple


def _sql_literal(value) -> str:
    """Render a Python value as a safe SQL literal for DEFAULT clauses."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


class Blueprint:
    """
    Defines a table schema within a migration.
    Supports common column types and modifiers.
    """

    def __init__(self, table: str, mode: str = "create"):
        self.table = table
        self.mode = mode  # "create" or "alter"
        self._columns: List[str] = []
        self._indexes: List[str] = []
        self._foreign_keys: List[str] = []

    def id(self, name: str = "id"):
        self._columns.append(f"{name} INTEGER PRIMARY KEY AUTOINCREMENT")
        return self

    def string(self, name: str, length: int = 255):
        self._columns.append(f"{name} VARCHAR({length})")
        return self

    def text(self, name: str):
        self._columns.append(f"{name} TEXT")
        return self

    def integer(self, name: str):
        self._columns.append(f"{name} INTEGER")
        return self

    def big_integer(self, name: str):
        self._columns.append(f"{name} BIGINT")
        return self

    def float(self, name: str):
        self._columns.append(f"{name} REAL")
        return self

    def decimal(self, name: str, precision: int = 8, scale: int = 2):
        self._columns.append(f"{name} DECIMAL({precision},{scale})")
        return self

    def boolean(self, name: str):
        self._columns.append(f"{name} BOOLEAN DEFAULT 0")
        return self

    def json(self, name: str):
        self._columns.append(f"{name} TEXT")
        return self

    def timestamp(self, name: str):
        self._columns.append(f"{name} TIMESTAMP")
        return self

    def timestamps(self):
        self._columns.append("created_at TIMESTAMP")
        self._columns.append("updated_at TIMESTAMP")
        return self

    def soft_deletes(self):
        self._columns.append("deleted_at TIMESTAMP NULL")
        return self

    def nullable(self):
        """Append NULL to last column."""
        if self._columns:
            self._columns[-1] += " NULL"
        return self

    def not_null(self):
        """Mark the last column NOT NULL."""
        if self._columns:
            self._columns[-1] += " NOT NULL"
        return self

    def default(self, value):
        """Set the column DEFAULT (replaces any previous default)."""
        if self._columns:
            column = re.sub(r"\s+DEFAULT\s+(?:'(?:[^']|'')*'|\S+)", "", self._columns[-1])
            self._columns[-1] = f"{column} DEFAULT {_sql_literal(value)}"
        return self

    def unique(self, column: str = None):
        if column:
            self._indexes.append(f"CREATE UNIQUE INDEX idx_{self.table}_{column} ON {self.table}({column})")
        elif self._columns:
            col_name = self._columns[-1].split()[0]
            self._indexes.append(
                f"CREATE UNIQUE INDEX idx_{self.table}_{col_name} ON {self.table}({col_name})"
            )
        return self

    def index(self, column: str):
        self._indexes.append(f"CREATE INDEX idx_{self.table}_{column} ON {self.table}({column})")
        return self

    def foreign(self, column: str):
        self._current_foreign = column
        return self

    def references(self, column: str):
        self._ref_column = column
        return self

    def on(self, table: str):
        if hasattr(self, "_current_foreign"):
            self._foreign_keys.append(
                f"FOREIGN KEY({self._current_foreign}) REFERENCES {table}({self._ref_column})"
            )
        return self

    def to_sql(self) -> List[str]:
        statements = []
        if self.mode == "create":
            cols = self._columns + self._foreign_keys
            create_sql = f"CREATE TABLE IF NOT EXISTS {self.table} (\n  "
            create_sql += ",\n  ".join(cols)
            create_sql += "\n)"
            statements.append(create_sql)
        elif self.mode == "alter":
            for col in self._columns:
                statements.append(f"ALTER TABLE {self.table} ADD COLUMN {col}")
        statements.extend(self._indexes)
        return statements


class Schema:
    """Fluent schema builder — Schema.create(), Schema.table(), Schema.drop()"""

    @staticmethod
    def create(table: str, callback) -> List[str]:
        bp = Blueprint(table, "create")
        callback(bp)
        return bp.to_sql()

    @staticmethod
    def table(table: str, callback) -> List[str]:
        bp = Blueprint(table, "alter")
        callback(bp)
        return bp.to_sql()

    @staticmethod
    def drop(table: str) -> List[str]:
        return [f"DROP TABLE IF EXISTS {table}"]

    @staticmethod
    def drop_if_exists(table: str) -> List[str]:
        return [f"DROP TABLE IF EXISTS {table}"]

    @staticmethod
    def has_table(table: str, connection) -> bool:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", [table]
        )
        return cursor.fetchone() is not None


class Migration:
    """
    Base migration class. Subclass and implement up() and down().
    
    class CreateUsersTable(Migration):
        def up(self):
            return Schema.create("users", lambda t: (
                t.id(),
                t.string("name"),
                t.string("email").unique("email"),
                t.timestamps(),
            ))
        
        def down(self):
            return Schema.drop("users")
    """

    def up(self) -> List[str]:
        raise NotImplementedError

    def down(self) -> List[str]:
        return []


class Migrator:
    """Runs and tracks migrations."""

    def __init__(self, connection, migrations_path: str = "database/migrations"):
        self.conn = connection
        self.path = migrations_path
        self._ensure_migrations_table()

    def _ensure_migrations_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration VARCHAR(255) NOT NULL,
                batch INTEGER NOT NULL,
                ran_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def _ran(self) -> List[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT migration FROM migrations")
        return [row[0] for row in cursor.fetchall()]

    def run(self, migrations: List[tuple]):
        """
        Run pending migrations.
        migrations: list of (name, MigrationClass) tuples
        """
        ran = self._ran()
        cursor = self.conn.cursor()
        cursor.execute("SELECT MAX(batch) FROM migrations")
        row = cursor.fetchone()
        batch = (row[0] or 0) + 1

        for name, migration_class in migrations:
            if name in ran:
                print(f"  Skipping (already ran): {name}")
                continue
            print(f"  Migrating: {name}")
            m = migration_class()
            stmts = m.up()
            if isinstance(stmts, list):
                for sql in stmts:
                    self.conn.execute(sql)
            self.conn.execute(
                "INSERT INTO migrations (migration, batch) VALUES (?, ?)",
                [name, batch]
            )
            self.conn.commit()
            print(f"  Migrated:  {name} ✓")

    def rollback(self, migrations_map: dict, steps: int = 1):
        """Roll back the last N batches."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT MAX(batch) FROM migrations")
        max_batch = cursor.fetchone()[0] or 0

        for batch_num in range(max_batch, max_batch - steps, -1):
            cursor.execute(
                "SELECT migration FROM migrations WHERE batch = ? ORDER BY id DESC",
                [batch_num]
            )
            rows = cursor.fetchall()
            for (name,) in rows:
                if name in migrations_map:
                    print(f"  Rolling back: {name}")
                    m = migrations_map[name]()
                    for sql in m.down():
                        self.conn.execute(sql)
                    self.conn.execute("DELETE FROM migrations WHERE migration = ?", [name])
                    self.conn.commit()
                    print(f"  Rolled back: {name} ✓")


    def status(self, migrations: List[tuple]) -> List[Tuple[str, bool]]:
        """Return [(name, has_run)] for the given (name, class) migrations."""
        ran = set(self._ran())
        return [(name, name in ran) for name, _ in migrations]


def discover(directory: str) -> List[tuple]:
    """
    Load every migration file in `directory` (sorted by file name).
    Returns a list of (name, MigrationClass).
    """
    found = []
    if not os.path.isdir(directory):
        return found
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue
        name = filename[:-3]
        spec = importlib.util.spec_from_file_location(f"_migration_{name}", os.path.join(directory, filename))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for obj in vars(module).values():
            if isinstance(obj, type) and issubclass(obj, Migration) and obj is not Migration:
                found.append((name, obj))
                break
    return found
