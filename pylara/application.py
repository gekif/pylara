"""
Application - the IoC container and application bootstrapper.
Inspired by Illuminate.Foundation.Application.
"""

import mimetypes
import os
from typing import Any, Callable, Dict, Optional
from wsgiref.simple_server import make_server

from pylara.http import context
from pylara.http.exceptions import HttpException
from pylara.http.kernel import HttpKernel
from pylara.http.request import Request
from pylara.http.response import Response
from pylara.routing.router import Router
from pylara.support.config import Config
from pylara.support.service_container import ServiceContainer
from pylara.version import __version__


class Application(ServiceContainer):
    """Boots the framework and turns WSGI requests into responses."""

    VERSION = __version__
    _instance: Optional["Application"] = None

    def __init__(self, base_path: str = "."):
        super().__init__()
        self.base_path = os.path.abspath(base_path)
        self.public_path = os.path.join(self.base_path, "public")
        self.views_path = os.path.join(self.base_path, "resources", "views")
        self.router = Router(self)
        self.config = Config(os.path.join(self.base_path, "config"))
        self.global_middleware: list = []
        self._exception_handlers: list = []
        self._booted = False
        self._boot_callbacks: list = []
        self._service_providers: list = []
        self._views = None
        self._shared: Dict[str, Any] = {}
        self._session_store = None

        self.instance("app", self)
        self.instance("router", self.router)
        self.instance("config", self.config)

        self._load_env()
        self.max_body_size = int(float(self.env("MAX_BODY_MB", 10)) * 1024 * 1024)
        Application._instance = self

    @classmethod
    def get_instance(cls) -> "Application":
        """The most recently created application (used by helpers such as view())."""
        if cls._instance is None:
            raise RuntimeError("No PyLara application has been created yet.")
        return cls._instance

    # ── environment ─────────────────────────────────────────────────────────

    def _load_env(self):
        """Load `.env`. Real environment variables always win over the file."""
        path = os.path.join(self.base_path, ".env")
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                value = value.strip()
                if value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) >= 2:
                    value = value[1:-1]
                else:
                    value = value.split(" #", 1)[0].strip()
                os.environ.setdefault(key.strip(), value)

    def env(self, key: str, default: Any = None) -> Any:
        """
        Read an environment variable. The strings true/false/null/empty
        are converted to True/False/None/"" like Laravel's env().
        """
        raw = os.environ.get(key)
        if raw is None:
            return default
        lowered = raw.lower()
        if lowered in ("true", "(true)"):
            return True
        if lowered in ("false", "(false)"):
            return False
        if lowered in ("null", "(null)"):
            return None
        if lowered in ("empty", "(empty)"):
            return ""
        return raw

    # ── providers / lifecycle ───────────────────────────────────────────────

    def register(self, provider_class):
        provider = provider_class(self)
        provider.register()
        self._service_providers.append(provider)
        if self._booted:
            provider.boot()
        return provider

    def boot(self):
        if self._booted:
            return
        self._booted = True
        for provider in self._service_providers:
            provider.boot()
        for callback in self._boot_callbacks:
            callback(self)

    def booted(self, callback: Callable):
        self._boot_callbacks.append(callback)

    # ── middleware, errors, views, URLs ─────────────────────────────────────

    def use(self, middleware) -> "Application":
        """Register global middleware (a class or an instance)."""
        self.global_middleware.append(middleware)
        return self

    def exception_handler(self, exc_class):
        """
        Decorator: handle an exception type.

            @app.exception_handler(PaymentError)
            def render(request, exc): return JsonResponse({"error": str(exc)}, 402)
        """
        def decorator(fn):
            self._exception_handlers.append((exc_class, fn))
            return fn
        return decorator

    @property
    def views(self):
        if self._views is None:
            from pylara.support.view import ViewFactory
            self._views = ViewFactory(self.views_path)
        return self._views

    def share(self, key: str, value) -> "Application":
        """
        Make a value available in every view. A callable is called (without arguments)
        each time a view is rendered.

            app.share("site_name", "My Blog")
            app.share("year", lambda: datetime.now().year)
        """
        self._shared[key] = value
        return self

    def _view_defaults(self) -> dict:
        defaults = {k: (v() if callable(v) else v) for k, v in self._shared.items()}
        request = context.get_request()
        session = request._attributes.get("session") if request is not None else None
        token = session.token() if session is not None else ""
        defaults["csrf_token"] = token
        defaults["csrf_field"] = f'<input type="hidden" name="_token" value="{token}">' if token else ""
        defaults["flash"] = session.flash_data() if session is not None else {}
        return defaults

    def view(self, name: str, data: dict = None, status: int = 200, **context_data) -> Response:
        """
        Render resources/views/<name>.html (dots are folders) into a Response.
        Views also receive `csrf_token`, `csrf_field` (raw HTML) and `flash` when a session is active.
        """
        merged = self._view_defaults()
        merged.update(data or {})
        merged.update(context_data)
        return Response(self.views.render(name, merged), status)

    # ── sessions ────────────────────────────────────────────────────────────

    def app_key(self) -> bytes:
        """The secret used to sign session cookies (APP_KEY)."""
        key = self.env("APP_KEY")
        if not key or not isinstance(key, str):
            raise RuntimeError("APP_KEY is not set. Run:  python -m manage key:generate")
        return key.encode("utf-8")

    def session_store(self):
        """Session storage from SESSION_DRIVER (file|memory) and SESSION_LIFETIME (minutes)."""
        if self._session_store is None:
            from pylara.support.session import FileSessionStore, MemorySessionStore
            lifetime = int(self.env("SESSION_LIFETIME", 120))
            driver = str(self.env("SESSION_DRIVER", "file")).lower()
            if driver == "memory":
                self._session_store = MemorySessionStore(lifetime)
            elif driver == "file":
                self._session_store = FileSessionStore(os.path.join(self.base_path, "storage", "sessions"), lifetime)
            else:
                raise RuntimeError(f"Unknown SESSION_DRIVER {driver!r} (use 'file' or 'memory').")
        return self._session_store

    def route(self, name: str, **params) -> str:
        """URL of a named route."""
        return self.router.route(name, **params)

    # ── routing shortcuts ───────────────────────────────────────────────────

    def get(self, uri: str, action=None):
        return self.router.get(uri, action)

    def post(self, uri: str, action=None):
        return self.router.post(uri, action)

    def put(self, uri: str, action=None):
        return self.router.put(uri, action)

    def patch(self, uri: str, action=None):
        return self.router.patch(uri, action)

    def delete(self, uri: str, action=None):
        return self.router.delete(uri, action)

    def any(self, uri: str, action=None):
        return self.router.any(uri, action)

    def group(self, attributes: dict, callback: Callable):
        return self.router.group(attributes, callback)

    def resource(self, name: str, controller_class, **kwargs):
        return self.router.resource(name, controller_class, **kwargs)

    # ── request handling ────────────────────────────────────────────────────

    def handle(self, environ: dict) -> Response:
        """Turn a WSGI environ into a Response."""
        self.boot()
        try:
            request = Request.from_environ(environ, self.max_body_size)
        except HttpException as exc:                     # body too large
            return Response(f"<h1>{exc.status_code} {exc.message}</h1>", exc.status_code)
        except ValueError:
            return Response("<h1>400 Bad Request</h1>", 400)
        static = self._static_response(request)
        if static is not None:
            return static
        return HttpKernel(self).handle(request)

    def _static_response(self, request: Request) -> Optional[Response]:
        """Serve files from `public/` (GET/HEAD only, never outside the folder)."""
        if request.method not in ("GET", "HEAD") or not os.path.isdir(self.public_path):
            return None
        relative = request.path.lstrip("/")
        if not relative or any(part.startswith(".") for part in relative.split("/")):
            return None
        root = os.path.realpath(self.public_path)
        full = os.path.realpath(os.path.join(root, relative))
        try:
            inside = os.path.commonpath([root, full]) == root
        except ValueError:                      # different drive on Windows
            return None
        if not inside or not os.path.isfile(full):
            return None
        with open(full, "rb") as f:
            data = f.read()
        content_type = mimetypes.guess_type(full)[0] or "application/octet-stream"
        return Response(data, 200, content_type=content_type)

    def __call__(self, environ: dict, start_response: Callable):
        """WSGI entry point (gunicorn, waitress, uWSGI...)."""
        response = self.handle(environ)
        body = response.content.encode("utf-8") if isinstance(response.content, str) else response.content
        headers = list(response.headers.items())
        if not any(k.lower() == "content-length" for k, _ in headers):
            headers.append(("Content-Length", str(len(body))))
        headers.extend(("Set-Cookie", c) for c in response.cookies)
        start_response(f"{response.status_code} {response.reason_phrase}", headers)
        return [b""] if environ.get("REQUEST_METHOD") == "HEAD" else [body]

    # ── development server ──────────────────────────────────────────────────

    def serve(self, host: str = "127.0.0.1", port: int = 8000):
        """Start the single-threaded development server (not for production)."""
        self.boot()
        self._say(f"\n  PyLara v{self.VERSION} development server")
        self._say(f"  -> http://{host}:{port}   (Ctrl+C to stop)\n")
        httpd = make_server(host, port, self)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            self._say("\n  Server stopped.")
        finally:
            httpd.server_close()

    @staticmethod
    def _say(text: str):
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode("ascii", "replace").decode())
