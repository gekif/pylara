"""
Request - Represents an incoming HTTP request.
Inspired by Laravel's Illuminate.Http.Request.
"""

import json
import re
import urllib.parse
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Request:
    """Wraps a WSGI environ into a convenient HTTP request object."""

    def __init__(
        self,
        method: str,
        path: str,
        query_params: Dict[str, Any] = None,
        body: bytes = b"",
        headers: Dict[str, str] = None,
        environ: dict = None,
    ):
        self.method = method.upper()
        self.path = path
        self._query_params = query_params or {}
        self._body = body
        self.headers = headers or {}
        self.environ = environ or {}
        self._json_cache = None
        self._form_cache = None
        self._files: Dict[str, Any] = {}
        self.route_params: Dict[str, str] = {}   # filled by router
        self._attributes: Dict[str, Any] = {}    # arbitrary data (middleware etc.)

    @classmethod
    def from_environ(cls, environ: dict, max_body: int = None) -> "Request":
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
        qs = environ.get("QUERY_STRING", "")
        query_params = dict(urllib.parse.parse_qsl(qs))

        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length < 0:
            raise ValueError("negative Content-Length")
        if max_body is not None and content_length > max_body:
            from pylara.http.exceptions import HttpException
            raise HttpException(413, "Request body too large.")
        body = environ["wsgi.input"].read(content_length) if content_length else b""

        headers = {
            key[5:].replace("_", "-").title(): value
            for key, value in environ.items()
            if key.startswith("HTTP_")
        }
        if "CONTENT_TYPE" in environ:
            headers["Content-Type"] = environ["CONTENT_TYPE"]
        if "CONTENT_LENGTH" in environ:
            headers["Content-Length"] = environ["CONTENT_LENGTH"]

        return cls(method, path, query_params, body, headers, environ)

    # ── Input helpers ───────────────────────────────────────────────────────

    def input(self, key: str, default: Any = None) -> Any:
        """Get a value from POST body or query string."""
        return self.all().get(key, default)

    def query(self, key: str, default: Any = None) -> Any:
        return self._query_params.get(key, default)

    def all(self) -> Dict[str, Any]:
        """Merge query params and body data."""
        data = dict(self._query_params)
        data.update(self._parse_body())
        return data

    def only(self, *keys) -> Dict[str, Any]:
        all_data = self.all()
        return {k: all_data[k] for k in keys if k in all_data}

    def except_(self, *keys) -> Dict[str, Any]:
        all_data = self.all()
        return {k: v for k, v in all_data.items() if k not in keys}

    def has(self, key: str) -> bool:
        return key in self.all()

    def get(self, key: str, default: Any = None) -> Any:
        return self.all().get(key, default)

    def json(self, key: str = None, default: Any = None) -> Any:
        if self._json_cache is None:
            try:
                self._json_cache = json.loads(self._body) if self._body else {}
            except (json.JSONDecodeError, ValueError):
                self._json_cache = {}
        if key is None:
            return self._json_cache
        if not isinstance(self._json_cache, dict):
            return default
        return self._json_cache.get(key, default)

    def _parse_body(self) -> dict:
        if self._form_cache is not None:
            return self._form_cache
        ct = self.headers.get("Content-Type", "")
        if "application/json" in ct:
            body = self.json()
            self._form_cache = body if isinstance(body, dict) else {}
        elif "multipart/form-data" in ct:
            from pylara.http.uploads import parse_multipart
            fields, self._files = parse_multipart(ct, self._body)
            self._form_cache = fields
        elif "application/x-www-form-urlencoded" in ct:
            self._form_cache = dict(urllib.parse.parse_qsl(self._body.decode("utf-8", errors="replace")))
        else:
            self._form_cache = {}
        return self._form_cache

    # ── Uploaded files ──────────────────────────────────────────────────────

    @property
    def files(self) -> Dict[str, Any]:
        """Uploaded files by field name (UploadedFile objects)."""
        self._parse_body()
        return self._files

    def file(self, name: str, default: Any = None) -> Any:
        return self.files.get(name, default)

    @property
    def session(self):
        """The session. Requires SessionMiddleware on the route."""
        session = self._attributes.get("session")
        if session is None:
            raise RuntimeError("No session: add SessionMiddleware to this route or group.")
        return session

    # ── Validation ──────────────────────────────────────────────────────────

    def validate(self, rules: Dict[str, str]) -> Dict[str, Any]:
        """
        Validate input against pipe-separated rules and return the validated data.

        Rules: required, string, integer, numeric, boolean, email,
               min:N, max:N (length), in:a,b,c, confirmed,
               file, mimes:jpg,png, max_kb:N (for uploaded files).
        Raises ValidationException (HTTP 422) on failure.
        """
        from pylara.http.exceptions import ValidationException
        from pylara.http.uploads import UploadedFile
        data = self.all()
        files = self.files
        errors: Dict[str, list] = {}

        for field, rule_string in rules.items():
            value = files[field] if field in files else data.get(field)
            if isinstance(value, UploadedFile):
                present = value.size > 0
            else:
                present = value is not None and value != ""
            field_errors = []

            for rule in (r.strip() for r in rule_string.split("|") if r.strip()):
                name, _, arg = rule.partition(":")
                if name == "required":
                    if not present:
                        field_errors.append(f"The {field} field is required.")
                    continue
                if not present:
                    continue                     # other rules only apply to filled fields
                if name == "file":
                    if not isinstance(value, UploadedFile):
                        field_errors.append(f"The {field} must be a file.")
                elif name == "mimes":
                    allowed = [a.strip().lower() for a in arg.split(",")]
                    if not isinstance(value, UploadedFile) or value.extension not in allowed:
                        field_errors.append(f"The {field} must be a file of type: {', '.join(allowed)}.")
                elif name == "max_kb":
                    if not isinstance(value, UploadedFile) or value.size > int(arg) * 1024:
                        field_errors.append(f"The {field} may not be greater than {arg} kilobytes.")
                elif isinstance(value, UploadedFile):
                    continue                     # text rules do not apply to files
                elif name == "string" and not isinstance(value, str):
                    field_errors.append(f"The {field} must be a string.")
                elif name == "integer":
                    try:
                        if isinstance(value, bool) or (isinstance(value, float) and value != int(value)):
                            raise ValueError
                        int(value)
                    except (ValueError, TypeError):
                        field_errors.append(f"The {field} must be an integer.")
                elif name == "numeric":
                    try:
                        if isinstance(value, bool):
                            raise ValueError
                        float(value)
                    except (ValueError, TypeError):
                        field_errors.append(f"The {field} must be a number.")
                elif name == "boolean" and str(value).lower() not in ("true", "false", "1", "0", "yes", "no"):
                    field_errors.append(f"The {field} field must be true or false.")
                elif name == "email" and not _EMAIL.match(str(value)):
                    field_errors.append(f"The {field} must be a valid email address.")
                elif name == "min" and len(str(value)) < int(arg):
                    field_errors.append(f"The {field} must be at least {arg} characters.")
                elif name == "max" and len(str(value)) > int(arg):
                    field_errors.append(f"The {field} may not be greater than {arg} characters.")
                elif name == "in" and str(value) not in arg.split(","):
                    field_errors.append(f"The selected {field} is invalid.")
                elif name == "confirmed" and value != data.get(f"{field}_confirmation"):
                    field_errors.append(f"The {field} confirmation does not match.")

            if field_errors:
                errors[field] = field_errors

        if errors:
            raise ValidationException(errors)

        return {field: (files[field] if field in files else data.get(field)) for field in rules}

    # ── Attributes (set by middleware) ──────────────────────────────────────

    def set_attribute(self, key: str, value: Any):
        self._attributes[key] = value

    def attribute(self, key: str, default: Any = None) -> Any:
        return self._attributes.get(key, default)

    # ── Meta ────────────────────────────────────────────────────────────────

    @property
    def is_json(self) -> bool:
        return "application/json" in self.headers.get("Content-Type", "")

    @property
    def wants_json(self) -> bool:
        return "application/json" in self.headers.get("Accept", "")

    @property
    def ip(self) -> str:
        """Client IP. X-Forwarded-For is trusted only if you run behind a proxy you control."""
        forwarded = self.headers.get("X-Forwarded-For", "")
        return forwarded.split(",")[0].strip() or self.environ.get("REMOTE_ADDR", "")

    def header(self, name: str, default: Any = None) -> Any:
        """Case-insensitive header lookup."""
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return default

    def bearer_token(self) -> str:
        auth = self.header("Authorization", "")
        return auth[7:].strip() if auth.lower().startswith("bearer ") else ""

    def cookie(self, name: str, default: Any = None) -> Any:
        jar = SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except Exception:
            return default
        return jar[name].value if name in jar else default

    def __repr__(self):
        return f"<Request [{self.method}] {self.path}>"
