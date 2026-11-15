"""
Testing helpers: drive an Application without starting a server.

    from pylara.testing import TestClient
    client = TestClient(app)
    response = client.post("/api/tasks", json={"title": "Write docs"})
    assert response.status_code == 201
    assert response.json()["title"] == "Write docs"
"""

import io
import json as _json
import secrets
import urllib.parse
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional

__test__ = False   # keep test runners from collecting this module


class TestResponse:
    __test__ = False

    def __init__(self, response):
        self._response = response
        self.status_code: int = response.status_code
        self.headers: Dict[str, str] = dict(response.headers)
        self.cookies = list(response.cookies)
        content = response.content
        self.body: bytes = content.encode("utf-8") if isinstance(content, str) else content

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return _json.loads(self.text)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def __repr__(self):
        return f"<TestResponse [{self.status_code}]>"


class TestClient:
    __test__ = False

    def __init__(self, app, headers: Optional[Dict[str, str]] = None, cookies: Optional[Dict[str, str]] = None):
        self.app = app
        self.default_headers = dict(headers or {})
        self.cookies: Dict[str, str] = cookies if cookies is not None else {}   # kept between requests

    def with_headers(self, **headers) -> "TestClient":
        """New client (sharing the same cookies) with extra headers, e.g. with_headers(Authorization="Bearer x")."""
        merged = {**self.default_headers, **{k.replace("_", "-"): v for k, v in headers.items()}}
        return TestClient(self.app, merged, self.cookies)

    def _remember_cookies(self, response: "TestResponse"):
        for raw in response.cookies:
            jar = SimpleCookie()
            jar.load(raw)
            for name, morsel in jar.items():
                if morsel["max-age"] == "0" or morsel.value == "":
                    self.cookies.pop(name, None)
                else:
                    self.cookies[name] = morsel.value

    @staticmethod
    def _multipart(data: Optional[dict], files: dict):
        boundary = "----pylara" + secrets.token_hex(8)
        out = bytearray()
        for name, value in (data or {}).items():
            out += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, spec in files.items():
            filename, content = spec[0], spec[1]
            ctype = spec[2] if len(spec) > 2 else "application/octet-stream"
            out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                    f'Content-Type: {ctype}\r\n\r\n').encode()
            out += content if isinstance(content, bytes) else str(content).encode()
            out += b"\r\n"
        out += f"--{boundary}--\r\n".encode()
        return bytes(out), f"multipart/form-data; boundary={boundary}"

    def with_token(self, token: str) -> "TestClient":
        return self.with_headers(Authorization=f"Bearer {token}")

    def request(self, method: str, path: str, json: Any = None, data: Optional[dict] = None,
                headers: Optional[dict] = None, query: Optional[dict] = None,
                files: Optional[dict] = None) -> TestResponse:
        """files={"avatar": ("me.png", b"...", "image/png")} sends multipart/form-data (with `data` as text fields)."""
        path, _, qs = path.partition("?")
        if query:
            qs = urllib.parse.urlencode(query) if not qs else qs + "&" + urllib.parse.urlencode(query)

        body, content_type = b"", ""
        if files:
            body, content_type = self._multipart(data, files)
        elif json is not None:
            body, content_type = _json.dumps(json).encode("utf-8"), "application/json"
        elif data is not None:
            body, content_type = urllib.parse.urlencode(data).encode("utf-8"), "application/x-www-form-urlencoded"

        environ = {
            "REQUEST_METHOD": method.upper(),
            "PATH_INFO": path,
            "QUERY_STRING": qs,
            "CONTENT_LENGTH": str(len(body)),
            "REMOTE_ADDR": "127.0.0.1",
            "wsgi.input": io.BytesIO(body),
            "HTTP_ACCEPT": "application/json",
        }
        if content_type:
            environ["CONTENT_TYPE"] = content_type
        for key, value in {**self.default_headers, **(headers or {})}.items():
            name = key.upper().replace("-", "_")
            if name in ("CONTENT_TYPE", "CONTENT_LENGTH"):
                environ[name] = value
            else:
                environ["HTTP_" + name] = value
        if self.cookies and "HTTP_COOKIE" not in environ:
            environ["HTTP_COOKIE"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        response = TestResponse(self.app.handle(environ))
        self._remember_cookies(response)
        return response

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)

    def put(self, path, **kw):
        return self.request("PUT", path, **kw)

    def patch(self, path, **kw):
        return self.request("PATCH", path, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)
