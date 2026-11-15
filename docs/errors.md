# Error Handling

All exceptions are caught by the HTTP kernel and turned into responses. Your code can raise
exceptions freely.

## Raising HTTP errors

```python
from pylara.http.response import abort
from pylara.http.exceptions import HttpException, NotFoundException, ForbiddenException, UnauthorizedException

abort(404)
abort(403, "Admins only")
raise HttpException(409, "Already exists")
raise NotFoundException("No such post")        # 404
raise UnauthorizedException()                  # 401
raise ForbiddenException()                     # 403
```

`Model.find_or_fail(id)` raises `NotFoundException`, so it produces a 404 automatically.

## Default rendering

| Exception | Response |
|---|---|
| `HttpException` (and subclasses) | its status code and message |
| `ValidationException` | 422 with `{"message", "errors"}` JSON |
| route not found / method not allowed | 404 / 405 |
| anything else | 500 |

The format is chosen from the request: if it **sends JSON** (`Content-Type: application/json`) or
**asks for JSON** (`Accept: application/json`) the body is `{"message": "..."}`; otherwise a small
HTML page. All messages inserted into HTML are escaped.

### Debug mode

With `APP_DEBUG=true`, a 500 shows the exception and traceback. With `APP_DEBUG=false` (production)
the client sees only "Server Error". Either way the **traceback is written to stderr**.

## Custom exception handlers

Register a handler for any exception class:

```python
class PaymentError(Exception):
    pass

@app.exception_handler(PaymentError)
def payment_failed(request, exc):
    return JsonResponse({"error": str(exc)}, 402)
```

A handler receives `(request, exception)` and returns anything an action can return. Handlers are
tried in registration order and the **first whose class matches** (`isinstance`) wins, so register
specific classes before general ones.

**Return `None` to decline**: the next matching handler (and finally the default rendering) takes over.
This lets a handler deal with only some cases:

```python
@app.exception_handler(HttpException)
def expired_pages(request, exc):
    if exc.status_code == 419:
        return RedirectResponse("/login")
    return None                       # everything else: default handling
```

A handler that itself raises produces a 500.

### Custom 404 page

```python
from pylara.http.exceptions import NotFoundException

@app.exception_handler(NotFoundException)
def not_found(request, exc):
    if request.wants_json:
        return JsonResponse({"message": "Not found"}, 404)
    return app.view("errors.404", status=404)
```

### Reporting to an external service

Wrap or replace the default behaviour by handling `Exception`:

```python
@app.exception_handler(Exception)
def everything_else(request, exc):
    report_to_sentry(exc)                      # your code
    return JsonResponse({"message": "Server Error"}, 500)
```

Register this one **last**; it matches every exception, including `HttpException`, so check
`isinstance(exc, HttpException)` first if you still want their status codes:

```python
    if isinstance(exc, HttpException):
        return JsonResponse({"message": exc.message}, exc.status_code)
```
