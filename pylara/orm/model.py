"""
Model - Active Record ORM.
Inspired by Laravel's Eloquent ORM.

Supports:
- SQLite, PostgreSQL, MySQL (via Python's DB-API)
- find, all, where, first, create, save, delete
- Relationships: has_many, belongs_to, has_one
- Scopes
- Timestamps (created_at, updated_at)
- Soft deletes
- Mass assignment (fillable/guarded)
"""

import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar

T = TypeVar("T", bound="Model")

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")
_OPERATORS = {"=", "!=", "<>", "<", ">", "<=", ">=", "LIKE", "NOT LIKE"}


_MISSING = object()     # distinguishes where(col, x) from where(col, op, None)


def _ident(name):
    """Tolak nama kolom yang tidak aman (mencegah SQL injection lewat identifier)."""
    if not _IDENT.match(str(name)):
        raise ValueError(f"Nama kolom tidak valid: {name!r}")
    return name


def _now() -> str:
    """Waktu UTC (naive, ISO) tanpa datetime.utcnow() yang deprecated."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


# Global connection registry
_connections: Dict[str, Any] = {}


def set_connection(name: str, connection):
    """Register a DB connection globally."""
    _connections[name] = connection


def get_connection(name: str = "default"):
    if name not in _connections:
        raise RuntimeError(f"No DB connection registered under '{name}'. Call set_connection() first.")
    return _connections[name]


class QueryBuilder:
    """
    Fluent query builder — wraps raw SQL construction.
    Inspired by Laravel's Builder.
    """

    def __init__(self, model_class: Type["Model"]):
        self._model = model_class
        self._wheres: List[tuple] = []
        self._order: Optional[str] = None
        self._limit_val: Optional[int] = None
        self._offset_val: Optional[int] = None
        self._with_trashed = False

    def where(self, column: str, op_or_value=None, value=_MISSING) -> "QueryBuilder":
        """
        where("a", 1)             a = 1
        where("a", ">", 1)        a > 1
        where("a", None)          a IS NULL        (also: where("a", "=", None))
        where("a", "!=", None)    a IS NOT NULL
        """
        _ident(column)
        if value is _MISSING:
            op, val = "=", op_or_value
        else:
            op, val = str(op_or_value).upper(), value
            if op not in _OPERATORS:
                raise ValueError(f"Invalid operator: {op_or_value!r}")
        if val is None:
            if op == "=":
                self._wheres.append((column, "IS", None))
            elif op in ("!=", "<>"):
                self._wheres.append((column, "IS NOT", None))
            else:
                raise ValueError("NULL can only be compared with = or !=")
        else:
            self._wheres.append((column, op, val))
        return self

    def where_null(self, column: str) -> "QueryBuilder":
        return self.where(column, "=", None)

    def where_not_null(self, column: str) -> "QueryBuilder":
        return self.where(column, "!=", None)

    def where_in(self, column: str, values: list) -> "QueryBuilder":
        _ident(column)
        placeholders = ", ".join(["?"] * len(values))
        self._wheres.append((column, "IN", values, placeholders))
        return self

    def order_by(self, column: str, direction: str = "ASC") -> "QueryBuilder":
        if direction.upper() not in ("ASC", "DESC"):
            raise ValueError(f"Arah order tidak valid: {direction!r}")
        self._order = f"{_ident(column)} {direction.upper()}"
        return self

    def limit(self, n: int) -> "QueryBuilder":
        self._limit_val = n
        return self

    def offset(self, n: int) -> "QueryBuilder":
        self._offset_val = n
        return self

    def with_trashed(self) -> "QueryBuilder":
        self._with_trashed = True
        return self

    def _build(self):
        table = self._model.table
        sql = f"SELECT * FROM {table}"
        params = []
        conditions = []

        # Soft delete filter
        if self._model.soft_deletes and not self._with_trashed:
            conditions.append("deleted_at IS NULL")

        for item in self._wheres:
            if len(item) == 4:
                col, op, vals, ph = item
                conditions.append(f"{col} {op} ({ph})")
                params.extend(vals)
            else:
                col, op, val = item
                conditions.append(f"{col} {op} ?")
                params.append(val)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        if self._order:
            sql += f" ORDER BY {self._order}"
        if self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"
        if self._offset_val is not None:
            sql += f" OFFSET {self._offset_val}"

        return sql, params

    def get(self) -> List["Model"]:
        sql, params = self._build()
        conn = get_connection(self._model.connection)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        return [self._model._from_row(dict(zip(columns, row))) for row in rows]

    def first(self) -> Optional["Model"]:
        self._limit_val = 1
        results = self.get()
        return results[0] if results else None

    def find(self, pk) -> Optional["Model"]:
        return self.where(self._model.primary_key, pk).first()

    def count(self) -> int:
        sql, params = self._build()
        sql = sql.replace("SELECT *", "SELECT COUNT(*)", 1)
        conn = get_connection(self._model.connection)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()[0]

    def exists(self) -> bool:
        return self.count() > 0

    def update(self, **values) -> int:
        table = self._model.table
        if self._model.timestamps:
            values["updated_at"] = _now()
        set_clause = ", ".join([f"{_ident(k)} = ?" for k in values])
        sql = f"UPDATE {table} SET {set_clause}"
        params = list(values.values())

        _, where_params = self._build()
        # Rebuild just the WHERE part
        conditions = []
        extra_params = []
        if self._model.soft_deletes and not self._with_trashed:
            conditions.append("deleted_at IS NULL")
        for item in self._wheres:
            if len(item) == 4:
                col, op, vals, ph = item
                conditions.append(f"{col} {op} ({ph})")
                extra_params.extend(vals)
            else:
                col, op, val = item
                conditions.append(f"{col} {op} ?")
                extra_params.append(val)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        params.extend(extra_params)

        conn = get_connection(self._model.connection)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount

    def delete(self) -> int:
        table = self._model.table
        if self._model.soft_deletes:
            return self.update(deleted_at=_now())
        sql = f"DELETE FROM {table}"
        params = []
        conditions = []
        for item in self._wheres:
            if len(item) == 4:
                col, op, vals, ph = item
                conditions.append(f"{col} {op} ({ph})")
                params.extend(vals)
            else:
                col, op, val = item
                conditions.append(f"{col} {op} ?")
                params.append(val)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        conn = get_connection(self._model.connection)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount

    def paginate(self, per_page: int = 15, page: int = 1) -> Dict:
        total = self.count()
        items = self.offset((page - 1) * per_page).limit(per_page).get()
        return {
            "data": items,
            "total": total,
            "per_page": per_page,
            "current_page": page,
            "last_page": max(1, -(-total // per_page)),  # ceiling div
        }


class ModelMeta(type):
    """Metaclass that gives each Model subclass its own query builder."""
    pass


class Model(metaclass=ModelMeta):
    """
    Base Active Record model.
    
    class User(Model):
        table = "users"
        fillable = ["name", "email", "password"]
    """

    # ── Class-level configuration ───────────────────────────────────────────
    table: str = ""
    primary_key: str = "id"
    connection: str = "default"
    fillable: List[str] = []        # whitelist
    guarded: List[str] = ["*"]      # "*" = nothing is mass-assignable unless listed in fillable; [] = everything is
    timestamps: bool = True
    soft_deletes: bool = False
    hidden: List[str] = []          # excluded from to_dict()
    casts: Dict[str, type] = {}     # automatic type casting

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.table:
            # Auto-derive table name (PascalCase → snake_case + 's')
            import re
            name = cls.__name__
            snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
            cls.table = snake + "s"

    def __init__(self, **attributes):
        self._attributes: Dict[str, Any] = {}
        self._original: Dict[str, Any] = {}
        self._exists: bool = False
        self.fill(**attributes)

    def fill(self, **attributes) -> "Model":
        for key, value in attributes.items():
            if self._is_fillable(key):
                self._set_attribute(key, value)
        return self

    def force_fill(self, **attributes) -> "Model":
        for key, value in attributes.items():
            self._set_attribute(key, value)
        return self

    def _is_fillable(self, key: str) -> bool:
        if self.fillable:
            return key in self.fillable
        if "*" in self.guarded:
            return False
        return key not in self.guarded

    def _set_attribute(self, key: str, value: Any):
        if key in self.casts and value is not None:
            value = self.casts[key](value)
        self._attributes[key] = value

    # ── Static/class query API ──────────────────────────────────────────────

    @classmethod
    def query(cls: Type[T]) -> QueryBuilder:
        return QueryBuilder(cls)

    @classmethod
    def all(cls: Type[T]) -> List[T]:
        return cls.query().get()

    @classmethod
    def find(cls: Type[T], pk) -> Optional[T]:
        return cls.query().find(pk)

    @classmethod
    def find_or_fail(cls: Type[T], pk) -> T:
        model = cls.find(pk)
        if model is None:
            from pylara.http.exceptions import NotFoundException
            raise NotFoundException(f"{cls.__name__} [{pk}] not found.")
        return model

    @classmethod
    def where(cls: Type[T], column: str, op_or_value=None, value=_MISSING) -> QueryBuilder:
        return cls.query().where(column, op_or_value, value)

    @classmethod
    def first(cls: Type[T]) -> Optional[T]:
        return cls.query().first()

    @classmethod
    def create(cls: Type[T], **attributes) -> T:
        instance = cls(**attributes)
        instance.save()
        return instance

    @classmethod
    def first_or_create(cls: Type[T], search: dict, attributes: dict = None) -> T:
        qb = cls.query()
        for k, v in search.items():
            qb.where(k, v)
        instance = qb.first()
        if instance:
            return instance
        return cls.create(**{**search, **(attributes or {})})

    @classmethod
    def update_or_create(cls: Type[T], search: dict, attributes: dict = None) -> T:
        qb = cls.query()
        for k, v in search.items():
            qb.where(k, v)
        instance = qb.first()
        if instance:
            instance.fill(**(attributes or {}))
            instance.save()
            return instance
        return cls.create(**{**search, **(attributes or {})})

    # ── Instance persistence ────────────────────────────────────────────────

    def save(self) -> bool:
        conn = get_connection(self.connection)
        cursor = conn.cursor()
        if self.timestamps:
            now = _now()
            if not self._exists:
                self._attributes.setdefault("created_at", now)
            self._attributes["updated_at"] = now

        if self._exists:
            pk_val = self._attributes.get(self.primary_key)
            data = {k: v for k, v in self._attributes.items() if k != self.primary_key}
            set_clause = ", ".join([f"{_ident(k)} = ?" for k in data])
            sql = f"UPDATE {self.table} SET {set_clause} WHERE {self.primary_key} = ?"
            cursor.execute(sql, list(data.values()) + [pk_val])
        else:
            cols = [_ident(c) for c in self._attributes.keys()]
            placeholders = ", ".join(["?"] * len(cols))
            sql = f"INSERT INTO {self.table} ({', '.join(cols)}) VALUES ({placeholders})"
            cursor.execute(sql, list(self._attributes.values()))
            self._attributes[self.primary_key] = cursor.lastrowid
            self._exists = True

        conn.commit()
        self._original = dict(self._attributes)
        return True

    def delete(self) -> bool:
        if self.soft_deletes:
            self._set_attribute("deleted_at", _now())
            return self.save()
        conn = get_connection(self.connection)
        cursor = conn.cursor()
        pk_val = self._attributes[self.primary_key]
        cursor.execute(f"DELETE FROM {self.table} WHERE {self.primary_key} = ?", [pk_val])
        conn.commit()
        self._exists = False
        return True

    def restore(self) -> bool:
        """Restore a soft-deleted model."""
        self._set_attribute("deleted_at", None)
        return self.save()

    def fresh(self: T) -> T:
        """Reload the model from the database."""
        return self.__class__.find(self._attributes[self.primary_key])

    def is_dirty(self, *keys) -> bool:
        if not keys:
            return self._attributes != self._original
        return any(self._attributes.get(k) != self._original.get(k) for k in keys)

    # ── Relationships ───────────────────────────────────────────────────────

    def has_many(self, related_class: Type[T], foreign_key: str = None, local_key: str = None) -> List[T]:
        fk = foreign_key or f"{self.__class__.__name__.lower()}_id"
        lk = local_key or self.primary_key
        return related_class.where(fk, self._attributes[lk]).get()

    def has_one(self, related_class: Type[T], foreign_key: str = None, local_key: str = None) -> Optional[T]:
        fk = foreign_key or f"{self.__class__.__name__.lower()}_id"
        lk = local_key or self.primary_key
        return related_class.where(fk, self._attributes[lk]).first()

    def belongs_to(self, related_class: Type[T], foreign_key: str = None, owner_key: str = None) -> Optional[T]:
        fk = foreign_key or f"{related_class.__name__.lower()}_id"
        ok = owner_key or related_class.primary_key
        return related_class.where(ok, self._attributes.get(fk)).first()

    def belongs_to_many(
        self,
        related_class: Type[T],
        pivot_table: str,
        foreign_key: str = None,
        related_key: str = None,
    ) -> List[T]:
        fk = foreign_key or f"{self.__class__.__name__.lower()}_id"
        rk = related_key or f"{related_class.__name__.lower()}_id"
        conn = get_connection(self.connection)
        cursor = conn.cursor()
        pk_val = self._attributes[self.primary_key]
        cursor.execute(f"SELECT {rk} FROM {pivot_table} WHERE {fk} = ?", [pk_val])
        ids = [row[0] for row in cursor.fetchall()]
        if not ids:
            return []
        return related_class.query().where_in(related_class.primary_key, ids).get()

    # ── Serialization ───────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self._attributes.items() if k not in self.hidden}

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def _from_row(cls: Type[T], row: dict) -> T:
        instance = cls.__new__(cls)
        instance._attributes = {}
        instance._original = {}
        instance._exists = True
        for key, value in row.items():
            instance._set_attribute(key, value)
        instance._original = dict(instance._attributes)
        return instance

    # ── Magic methods ───────────────────────────────────────────────────────

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        # Check if it's a real method/descriptor defined on the subclass
        # before falling through to the DB _attributes dict.
        for klass in type(self).__mro__:
            if name in klass.__dict__:
                obj = klass.__dict__[name]
                if callable(obj) or isinstance(obj, (classmethod, staticmethod, property)):
                    return obj.__get__(self, type(self))
        # Fall through to column attributes
        try:
            attrs = object.__getattribute__(self, "_attributes")
        except AttributeError:
            raise AttributeError(name)
        if name in attrs:
            return attrs[name]
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any):
        if name.startswith("_") or name in ("table", "primary_key", "connection",
                                             "fillable", "guarded", "timestamps",
                                             "soft_deletes", "hidden", "casts"):
            object.__setattr__(self, name, value)
        else:
            self._set_attribute(name, value)

    def __repr__(self):
        pk = self._attributes.get(self.primary_key, "?")
        return f"<{self.__class__.__name__} {self.primary_key}={pk}>"
