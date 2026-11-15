# Responses

## Creating responses

Usually you simply return a value (see [Routing](routing.md#what-an-action-may-return)). For
control, build a response object:

```python
from pylara import Response, JsonResponse, RedirectResponse

Response("<h1>Hi</h1>", 200)
Response("created", 201, headers={"X-Thing": "1"})
Response(b"\x89PNG...", 200, content_type="image/png")
JsonResponse({"ok": True}, 201)
RedirectResponse("/login")            # 302 by default
RedirectResponse("/new-home", 301)
```

Signatures:

```python
Response(content="", status_code=200, headers=None, content_type="text/html; charset=utf-8")
JsonResponse(data, status_code=200, headers=None)
RedirectResponse(url, status_code=302)
```

`JsonResponse` serialises with `ensure_ascii=False`, and converts values JSON does not know
(dates, ...) with `str()`.

Inside controllers use the shortcuts: `self.json(...)`, `self.view(...)`, `self.redirect(...)`.
Module-level equivalents live in `pylara.http.response`: `response()`, `json_response()`,
`redirect()`, `abort()`.

## Headers and cookies

```python
response = Response("ok")
response.headers["Cache-Control"] = "no-store"
response.with_header("X-Thing", "1")                       # chainable
response.with_cookie("theme", "dark", max_age=86400)      # chainable, call it several times
response.with_cookie("sid", token, secure=True, same_site="Strict")
```

`with_cookie(name, value, max_age=None, path="/", http_only=True, secure=False, same_site="Lax")`.
Cookies are `HttpOnly` and `SameSite=Lax` by default; set `secure=True` when you serve over HTTPS.
Each cookie becomes its own `Set-Cookie` header.

## Status codes

`response.status_code` is a plain integer. The reason phrase (`"Not Found"`) is looked up from a
table of common codes.

## Stopping with an error

```python
from pylara.http.response import abort
abort(404)                      # "Not Found"
abort(403, "Admins only")
```

`abort` raises `HttpException`. See [Error Handling](errors.md).

## Static files

Anything inside `public/` is served directly, with the right `Content-Type`:

```
public/css/app.css   ->  /css/app.css
public/img/logo.png  ->  /img/logo.png
```

Rules:

- Only `GET` and `HEAD` requests.
- Files are checked **before routes**, so a file shadows a route with the same path.
- Paths cannot escape `public/` (`..` and symlinks leaving the folder are rejected), and any path
  segment starting with `.` is refused (no `.env`, no `.git`).
- The built-in server and WSGI servers read files into memory per request. For heavy traffic let your
  front-end web server (nginx, Caddy) serve `public/` directly.

## Downloads

Return the bytes with the right headers:

```python
@app.get("/report.csv")
def report(request):
    data = "a,b\n1,2\n"
    return Response(data, 200, content_type="text/csv").with_header(
        "Content-Disposition", 'attachment; filename="report.csv"')
```
