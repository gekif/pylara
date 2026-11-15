# Middleware

Middleware inspects and filters HTTP requests: authentication, CORS, rate limiting, logging.

## Writing middleware

```bash
python -m manage make:middleware EnsureJson
```

```python
# app/middleware/ensure_json.py
from pylara.middleware.middleware import Middleware
from pylara.http.exceptions import HttpException


class EnsureJson(Middleware):

    def handle(self, request, next):
        if request.method in ("POST", "PUT", "PATCH") and not request.is_json:
            raise HttpException(415, "Send JSON")        # stop here
        response = next()                                 # continue inwards
        response.headers["X-Checked"] = "1"               # work on the way out
        return response
```

`next()` calls the rest of the pipeline and returns a `Response`. Do work **before** it to act on
the request, **after** it to act on the response, or return/raise instead of calling it to stop
the request. A middleware may return a `dict` or `str`; it is converted to a response.

You do not have to subclass `Middleware`; any object with `handle(request, next)` works.

## Registering middleware

```python
# Global: runs on every request, in the order registered
app.use(EnsureJson)

# Groups
app.group({"prefix": "/api", "middleware": [EnsureJson, Throttle]}, lambda r: [...])

# One route
app.get("/admin", handler).with_middleware(AdminOnly)
```

### Classes vs instances

- Passing a **class** creates a new instance for every request (no constructor arguments).
- Passing an **instance** shares it between requests. Use this to configure middleware, and keep it
  free of per-request state:

```python
app.use(MyMiddleware(option=True))
```

### Execution order

```
global middleware (in order of app.use)
  → group middleware (outermost group first)
    → route middleware (with_middleware, in order)
      → your action
    ← ...and back out in reverse
```

## Built-in middleware

Import from `pylara.middleware.middleware`.

### `CorsMiddleware`

Adds CORS headers and answers `OPTIONS` pre-flight requests with `204`. Configure by subclassing:

```python
class Cors(CorsMiddleware):
    allowed_origins = ["https://app.example.com", "https://admin.example.com"]
    allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allowed_headers = ["Content-Type", "Authorization"]
```

`["*"]` (the default) allows every origin. With a list, the request's `Origin` is echoed back only
if it is in the list (plus `Vary: Origin`); other origins get no CORS header.

### `AuthMiddleware`

Bearer-token authentication. Override `authenticate(token)` to return the user (any object) or
`None` for a 401:

```python
class TokenAuth(AuthMiddleware):
    def authenticate(self, token):
        return User.where("api_token", token).first() if token else None

app.get("/me", lambda request: request.attribute("user").to_dict()).with_middleware(TokenAuth)
```

The returned user is stored with `request.set_attribute("user", user)` and read back with
`request.attribute("user")`.

### `ThrottleMiddleware`

A simple in-memory rate limiter per client IP: `max_requests` (default 60) per `window_seconds`
(default 60), then HTTP 429.

```python
class Limit(ThrottleMiddleware):
    _counts = {}            # give each subclass its own counter
    max_requests = 10
    window_seconds = 60
```

The counters live in the process memory: they reset on restart and are **not shared between
worker processes**. Behind a reverse proxy make sure the proxy sets `X-Forwarded-For`; PyLara uses
its first value as the client address.

### `SessionMiddleware`, `VerifyCsrfToken`, `RequireLogin`

Imported from `pylara.middleware.session`. They provide [sessions](sessions.md),
[CSRF protection](csrf.md) and login-only pages. Order matters: `SessionMiddleware` first.

### `JsonResponseMiddleware`

Forces a JSON content type on responses when the client sends `Accept: application/json`.
