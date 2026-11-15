"""
Response - HTTP response classes.
Inspired by Laravel's Illuminate.Http.Response.
"""

import json
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional


HTTP_PHRASES = {
    200: "OK", 201: "Created", 202: "Accepted", 204: "No Content",
    301: "Moved Permanently", 302: "Found", 303: "See Other", 304: "Not Modified",
    307: "Temporary Redirect", 308: "Permanent Redirect",
    400: "Bad Request", 401: "Unauthorized", 402: "Payment Required", 403: "Forbidden",
    404: "Not Found", 405: "Method Not Allowed", 409: "Conflict", 410: "Gone",
    413: "Payload Too Large", 415: "Unsupported Media Type", 419: "Page Expired", 422: "Unprocessable Entity",
    429: "Too Many Requests", 500: "Internal Server Error", 501: "Not Implemented",
    502: "Bad Gateway", 503: "Service Unavailable", 504: "Gateway Timeout",
}


class Response:
    """A standard HTTP response."""

    def __init__(
        self,
        content: Any = "",
        status_code: int = 200,
        headers: Dict[str, str] = None,
        content_type: str = "text/html; charset=utf-8",
    ):
        self.content = content if isinstance(content, (str, bytes)) else str(content)
        self.status_code = status_code
        self.headers: Dict[str, str] = {
            "Content-Type": content_type,
            **(headers or {}),
        }
        self.cookies: list = []

    @property
    def reason_phrase(self) -> str:
        return HTTP_PHRASES.get(self.status_code, "Unknown")

    def with_header(self, key: str, value: str) -> "Response":
        self.headers[key] = value
        return self

    def with_cookie(
        self,
        name: str,
        value: str,
        max_age: int = None,
        path: str = "/",
        http_only: bool = True,
        secure: bool = False,
        same_site: str = "Lax",
    ) -> "Response":
        """Queue a Set-Cookie header. Can be called several times."""
        jar = SimpleCookie()
        jar[name] = value
        morsel = jar[name]
        morsel["path"] = path
        if max_age is not None:
            morsel["max-age"] = max_age
        if http_only:
            morsel["httponly"] = True
        if secure:
            morsel["secure"] = True
        if same_site:
            morsel["samesite"] = same_site
        self.cookies.append(morsel.OutputString())
        return self

    def __repr__(self):
        return f"<Response [{self.status_code}]>"


class JsonResponse(Response):
    """A JSON HTTP response."""

    def __init__(self, data: Any, status_code: int = 200, headers: Dict[str, str] = None):
        content = json.dumps(data, default=str, ensure_ascii=False)
        super().__init__(content, status_code, headers, content_type="application/json")


class RedirectResponse(Response):
    """An HTTP redirect response."""

    def __init__(self, url: str, status_code: int = 302):
        super().__init__("", status_code, {"Location": url})


# ── Response factory helpers (like Laravel's response() helper) ─────────────

def response(content: Any = "", status: int = 200, headers: dict = None) -> Response:
    return Response(content, status, headers)


def json_response(data: Any, status: int = 200) -> JsonResponse:
    return JsonResponse(data, status)


def redirect(url: str, status: int = 302) -> RedirectResponse:
    return RedirectResponse(url, status)


def abort(status_code: int, message: str = ""):
    from pylara.http.exceptions import HttpException
    raise HttpException(status_code, message)
