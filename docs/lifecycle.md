# Request Lifecycle

Understanding the path of a request makes everything else easier to reason about.

```
WSGI server (gunicorn / waitress / manage serve)
        │  environ
        ▼
Application.__call__ ──► Application.handle(environ)
        │
        ├─ boot()                       providers' boot() run once, on the first request
        ├─ Request.from_environ()       400 Bad Request if Content-Length is invalid
        ├─ static file?                 GET/HEAD for a real file in public/ → file response
        ▼
HttpKernel.handle(request)
        │  global middleware            (kernel defaults, then app.use(...) in order)
        ▼
Router.dispatch(request)                first matching route wins; 404 / 405 otherwise
        │  group middleware → route middleware
        ▼
controller / callable                   built by the container (constructor injection)
        │
        ▼  return value → Response      dict/list → JSON, str → HTML, None → empty
        ▲
        │  any exception
HttpKernel._render_exception            your exception handlers → HttpException → 422 → 500
        │
        ▼
start_response(status, headers) + body (+ one Set-Cookie header per cookie)
```

## Things worth knowing

- **Static files are checked before routes.** A file `public/about` shadows a route `/about`.
- **Middleware runs in an onion**: global → group → route → handler, and back out in reverse.
- **Return values are normalised at every layer**, so a middleware may also return a dict or a
  string.
- **Exceptions never escape** the kernel. They become responses, either through a handler you
  registered ([Error Handling](errors.md)) or the defaults.
- **Controllers are created per request** through the [container](container.md), so constructor
  arguments can be injected and no state is shared between requests.
- `HEAD` requests are answered by `GET` routes; the body is dropped.
