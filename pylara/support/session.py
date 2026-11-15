"""
Sessions: server-side data keyed by a signed cookie.

The cookie holds only a random session id signed with APP_KEY (HMAC-SHA256); the data lives in
storage/sessions/ (file driver, shared by all worker processes on one machine) or in memory
(memory driver: tests only). Session data must be JSON-serialisable.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from typing import Any, Dict, Optional

_SID = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
TOUCH_AFTER = 60          # seconds: refresh the expiry of an unchanged session at most this often


def new_id() -> str:
    return secrets.token_urlsafe(32)


def sign(session_id: str, key: bytes) -> str:
    return session_id + "." + hmac.new(key, session_id.encode(), hashlib.sha256).hexdigest()


def unsign(value: str, key: bytes) -> Optional[str]:
    """Return the session id if the signature is valid, else None."""
    if not value or "." not in value:
        return None
    session_id, _, signature = value.rpartition(".")
    expected = hmac.new(key, session_id.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected) or not _SID.match(session_id):
        return None
    return session_id


class MemorySessionStore:
    """Process-local store. For tests and quick experiments; lost on restart."""

    def __init__(self, lifetime_minutes: int = 120):
        self.lifetime = lifetime_minutes * 60
        self._items: Dict[str, dict] = {}

    def load(self, session_id: str) -> Optional[dict]:
        item = self._items.get(session_id)
        if item is None:
            return None
        if item["expires"] < time.time():
            self._items.pop(session_id, None)
            return None
        return {"data": json.loads(json.dumps(item["data"])), "touched": item["touched"]}

    def save(self, session_id: str, data: dict):
        now = time.time()
        self._items[session_id] = {"data": json.loads(json.dumps(data)), "expires": now + self.lifetime, "touched": now}

    def delete(self, session_id: str):
        self._items.pop(session_id, None)


class FileSessionStore:
    """One JSON file per session, written atomically."""

    def __init__(self, directory: str, lifetime_minutes: int = 120):
        self.directory = directory
        self.lifetime = lifetime_minutes * 60

    def _path(self, session_id: str) -> str:
        if not _SID.match(session_id):
            raise ValueError("Invalid session id")
        return os.path.join(self.directory, session_id + ".json")

    def load(self, session_id: str) -> Optional[dict]:
        path = self._path(session_id)
        try:
            with open(path, encoding="utf-8") as f:
                item = json.load(f)
        except (OSError, ValueError):
            return None
        if item.get("expires", 0) < time.time():
            self.delete(session_id)
            return None
        return {"data": item.get("data", {}), "touched": item.get("touched", 0)}

    def save(self, session_id: str, data: dict):
        os.makedirs(self.directory, exist_ok=True)
        path = self._path(session_id)
        now = time.time()
        tmp = f"{path}.{secrets.token_hex(4)}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"data": data, "expires": now + self.lifetime, "touched": now}, f)
        os.replace(tmp, path)
        if secrets.randbelow(50) == 0:
            self.gc()

    def delete(self, session_id: str):
        try:
            os.remove(self._path(session_id))
        except OSError:
            pass

    def gc(self):
        """Remove expired session files."""
        try:
            names = os.listdir(self.directory)
        except OSError:
            return
        now = time.time()
        for name in names:
            if not name.endswith(".json"):
                continue
            path = os.path.join(self.directory, name)
            try:
                with open(path, encoding="utf-8") as f:
                    expired = json.load(f).get("expires", 0) < now
            except (OSError, ValueError):
                expired = True
            if expired:
                try:
                    os.remove(path)
                except OSError:
                    pass


class Session:
    """The session of the current request: request.session."""

    def __init__(self, store, session_id: str, data: Optional[dict], touched: Optional[float] = None):
        self._store = store
        self.id = session_id
        self._original_id = session_id
        self._is_new = data is None
        self._data: Dict[str, Any] = dict(data or {})
        self._old_flash: Dict[str, Any] = self._data.pop("_flash", {})
        self._new_flash: Dict[str, Any] = {}
        self._touched = touched
        self._dirty = bool(self._old_flash)       # the old flash must be removed after this request

    # reading / writing -------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def has(self, key: str) -> bool:
        return key in self._data

    def put(self, key: str, value: Any):
        self._data[key] = value
        self._dirty = True

    def forget(self, key: str):
        if key in self._data:
            del self._data[key]
            self._dirty = True

    def pull(self, key: str, default: Any = None) -> Any:
        value = self._data.pop(key, default)
        self._dirty = True
        return value

    def all(self) -> Dict[str, Any]:
        return {k: v for k, v in self._data.items() if not k.startswith("_")}

    # flash data: available during the NEXT request only ----------------------
    def flash(self, key: str, value: Any):
        self._new_flash[key] = value
        self._dirty = True

    def flash_data(self) -> Dict[str, Any]:
        """Values flashed during the previous request."""
        return dict(self._old_flash)

    # security ----------------------------------------------------------------
    def token(self) -> str:
        """The CSRF token of this session (created on first use)."""
        if "_token" not in self._data:
            self._data["_token"] = secrets.token_urlsafe(32)
            self._dirty = True
        return self._data["_token"]

    def regenerate(self):
        """New session id, same data. Call it after login to prevent session fixation."""
        self._store.delete(self.id)
        self.id = new_id()
        self._dirty = True

    def invalidate(self):
        """Forget everything and start a new session (logout)."""
        self._data.clear()
        self._new_flash.clear()
        self.regenerate()

    # persistence -------------------------------------------------------------
    def needs_save(self) -> bool:
        if self._dirty or self.id != self._original_id:
            return True
        return self._touched is not None and time.time() - self._touched > TOUCH_AFTER

    def payload(self) -> dict:
        data = dict(self._data)
        if self._new_flash:
            data["_flash"] = self._new_flash
        return data
