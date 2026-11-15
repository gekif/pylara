"""
Middleware - Base middleware class and built-in middleware.
Inspired by Laravel's middleware system.
"""

from pylara.http.request import Request
from pylara.http.response import Response


class Middleware:
    """
    Base middleware class. Subclass and implement handle().
    
    def handle(self, request: Request, next) -> Response:
        # do something before
        response = next()
        # do something after
        return response
    """

    def handle(self, request: Request, next) -> Response:
        return next()


# ── Built-in middleware ─────────────────────────────────────────────────────

class CorsMiddleware(Middleware):
    """Adds CORS headers to every response."""

    allowed_origins = ["*"]
    allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allowed_headers = ["Content-Type", "Authorization", "X-Requested-With"]

    def handle(self, request: Request, next) -> Response:
        response = Response("", 204) if request.method == "OPTIONS" else next()

        origin = request.header("Origin")
        if "*" in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif origin and origin in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin   # must be a single origin
            response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
        response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
        return response


class JsonResponseMiddleware(Middleware):
    """Forces JSON content-type on responses when request wants JSON."""

    def handle(self, request: Request, next) -> Response:
        response = next()
        if request.wants_json and "application/json" not in response.headers.get("Content-Type", ""):
            response.headers["Content-Type"] = "application/json"
        return response


class AuthMiddleware(Middleware):
    """
    Simple Bearer token authentication middleware.
    Override authenticate() to implement custom logic.
    """

    def handle(self, request: Request, next) -> Response:
        token = self._extract_token(request)
        user = self.authenticate(token)
        if user is None:
            from pylara.http.exceptions import UnauthorizedException
            raise UnauthorizedException()
        request.set_attribute("user", user)
        return next()

    def _extract_token(self, request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return ""

    def authenticate(self, token: str):
        """Override this to validate the token. Return user object or None."""
        return None


class ThrottleMiddleware(Middleware):
    """
    Very simple in-memory rate limiter.
    Default: 60 requests per minute per IP.
    """

    _counts: dict = {}
    max_requests = 60
    window_seconds = 60

    def handle(self, request: Request, next) -> Response:
        import time
        ip = request.ip
        now = time.time()
        bucket = self._counts.get(ip)
        if bucket is None or now - bucket["start"] > self.window_seconds:
            self._counts[ip] = {"start": now, "count": 1}
        else:
            self._counts[ip]["count"] += 1
            if self._counts[ip]["count"] > self.max_requests:
                from pylara.http.exceptions import HttpException
                raise HttpException(429, "Too Many Requests")
        return next()
