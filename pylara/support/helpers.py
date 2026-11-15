"""
helpers.py - Global helper functions.
Inspired by Laravel's helpers.php.
"""

import json as _json
from pylara.http.response import Response, JsonResponse, RedirectResponse


def response(content="", status=200, headers=None) -> Response:
    """Create a new HTTP response."""
    return Response(content, status, headers)


def json(data, status=200) -> JsonResponse:
    """Create a JSON response."""
    return JsonResponse(data, status)


def redirect(url: str, status=302) -> RedirectResponse:
    """Create a redirect response."""
    return RedirectResponse(url, status)


def abort(status_code: int, message: str = ""):
    """Throw an HTTP exception."""
    from pylara.http.exceptions import HttpException
    raise HttpException(status_code, message)


def collect(items: list):
    """Create a Collection from a list."""
    return Collection(items)


def env(key: str, default=None):
    """Get an environment variable (true/false/null are converted)."""
    from pylara.application import Application
    return Application.get_instance().env(key, default)


def config(key: str, default=None):
    """Get a config value using dot notation, e.g. config("app.name")."""
    from pylara.application import Application
    return Application.get_instance().config.get(key, default)


def view(name: str, data: dict = None, status: int = 200, **context):
    """Render a template into a Response."""
    from pylara.application import Application
    return Application.get_instance().view(name, data, status, **context)


def route(name: str, **params) -> str:
    """URL of a named route."""
    from pylara.application import Application
    return Application.get_instance().route(name, **params)


def now():
    """Get the current UTC datetime."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)


def str_slug(text: str, separator: str = "-") -> str:
    """Convert a string to a URL-friendly slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", separator, text)
    return text.strip(separator)


def str_camel(text: str) -> str:
    """Convert snake_case to camelCase."""
    parts = text.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def str_pascal(text: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(p.capitalize() for p in text.split("_"))


def str_snake(text: str) -> str:
    """Convert PascalCase/camelCase to snake_case."""
    import re
    return re.sub(r"(?<!^)(?=[A-Z])", "_", text).lower()


class Collection:
    """
    A fluent wrapper around a list.
    Inspired by Laravel's Collection class.
    """

    def __init__(self, items: list):
        self._items = list(items)

    def all(self) -> list:
        return self._items

    def count(self) -> int:
        return len(self._items)

    def first(self, default=None):
        return self._items[0] if self._items else default

    def last(self, default=None):
        return self._items[-1] if self._items else default

    def filter(self, callback=None) -> "Collection":
        if callback is None:
            return Collection([x for x in self._items if x])
        return Collection([x for x in self._items if callback(x)])

    def map(self, callback) -> "Collection":
        return Collection([callback(x) for x in self._items])

    def each(self, callback) -> "Collection":
        for item in self._items:
            callback(item)
        return self

    def pluck(self, key: str) -> "Collection":
        result = []
        for item in self._items:
            if isinstance(item, dict):
                result.append(item.get(key))
            else:
                result.append(getattr(item, key, None))
        return Collection(result)

    def where(self, key: str, value) -> "Collection":
        def match(item):
            val = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
            return val == value
        return self.filter(match)

    def unique(self, key: str = None) -> "Collection":
        seen = set()
        result = []
        for item in self._items:
            k = (item.get(key) if isinstance(item, dict) else getattr(item, key)) if key else item
            if k not in seen:
                seen.add(k)
                result.append(item)
        return Collection(result)

    def sort_by(self, key: str, reverse: bool = False) -> "Collection":
        return Collection(sorted(
            self._items,
            key=lambda x: x.get(key) if isinstance(x, dict) else getattr(x, key),
            reverse=reverse
        ))

    def group_by(self, key: str) -> dict:
        result = {}
        for item in self._items:
            k = item.get(key) if isinstance(item, dict) else getattr(item, key)
            result.setdefault(k, []).append(item)
        return result

    def chunk(self, size: int) -> "Collection":
        chunks = [self._items[i:i+size] for i in range(0, len(self._items), size)]
        return Collection(chunks)

    def sum(self, key: str = None):
        if key:
            return sum(
                (x.get(key) if isinstance(x, dict) else getattr(x, key, 0))
                for x in self._items
            )
        return sum(self._items)

    def avg(self, key: str = None):
        total = self.sum(key)
        return total / len(self._items) if self._items else 0

    def max(self, key: str = None):
        if key:
            return max(
                (x.get(key) if isinstance(x, dict) else getattr(x, key))
                for x in self._items
            )
        return max(self._items)

    def min(self, key: str = None):
        if key:
            return min(
                (x.get(key) if isinstance(x, dict) else getattr(x, key))
                for x in self._items
            )
        return min(self._items)

    def to_json(self) -> str:
        return _json.dumps(self._items, default=str)

    def is_empty(self) -> bool:
        return len(self._items) == 0

    def contains(self, key, value=None) -> bool:
        if value is None:
            return key in self._items
        return any(
            (x.get(key) if isinstance(x, dict) else getattr(x, key)) == value
            for x in self._items
        )

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __repr__(self):
        return f"Collection({self._items!r})"
