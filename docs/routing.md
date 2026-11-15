# Routing

Routes map a URL and an HTTP method to code. Define them in `routes/web.py` / `routes/api.py`
(or anywhere you can reach the `app`).

```python
def register(app):
    app.get("/", lambda request: "Hello")
```

## Basic routes

```python
app.get("/ping", lambda request: {"pong": True})      # dict/list  -> JSON
app.post("/users", [UserController, "store"])           # [Class, "method"]
app.put("/users/{id}", [UserController, "update"])
app.patch("/users/{id}", [UserController, "update"])
app.delete("/users/{id}", [UserController, "destroy"])
app.any("/webhook", handler)                            # every verb
app.router.match(["GET", "POST"], "/form", handler)     # chosen verbs
```

The action is either **any callable** or a **`[ControllerClass, "method_name"]`** pair. A route
action can also be registered with a decorator:

```python
@app.get("/status")
def status(request):
    return {"ok": True}
```

`GET` routes also answer `HEAD`. A trailing slash is ignored (`/users/` is `/users`).

### What an action may return

| Return value | Becomes |
|---|---|
| a `Response` (`JsonResponse`, `RedirectResponse`...) | itself |
| `dict` or `list` | a JSON response |
| `str` | an HTML response (status 200) |
| `None` | an empty 200 response |

## Route parameters

Placeholders in braces are passed to your action **by name**, after the request:

```python
app.get("/users/{id}", lambda request, id: {"id": id})
app.get("/posts/{post}/comments/{comment}", lambda request, post, comment: ...)
```

- Parameters are always **strings**. Convert them yourself: `int(id)`.
- The action's parameter **names must match** the placeholders. If you do not declare a parameter,
  read it from `request.route_params["id"]`.
- A placeholder matches one path segment (`[^/]+`).

### Optional parameters

```python
app.get("/posts/{page?}", lambda request, page=None: {"page": page or "1"})
```

Give the parameter a default value in your function, otherwise a request without it fails.
`/posts` and `/posts/2` both match.

## Named routes

```python
app.get("/users/{id}", [UserController, "show"]).named("users.show")

app.route("users.show", id=7)          # "/users/7"
from pylara.support.helpers import route
route("users.show", id=7)              # same, as a helper
```

Values are URL-encoded; a missing required parameter raises `ValueError`; an unknown name raises
`KeyError`. Names are shown in `python -m manage route:list`.

## Route groups

Share a URL prefix and/or middleware:

```python
app.group({"prefix": "/api", "middleware": [CorsMiddleware]}, lambda r: [
    r.get("/health", lambda request: {"ok": True}),
    r.group({"prefix": "/admin", "middleware": [AdminOnly]}, lambda r2: [
        r2.get("/stats", [StatsController, "index"]),     # /api/admin/stats
    ]),
])
```

The callback receives the router (`r`). It can be a lambda that returns a list (only for
readability: the return value is ignored) or a regular function with statements:

```python
def api(r):
    r.get("/health", health)
    r.post("/login", [AuthController, "login"])

app.group({"prefix": "/api"}, api)
```

Prefixes concatenate and middleware accumulates in nested groups.

## Resource routes

`resource()` registers the conventional CRUD routes for a controller:

```python
app.resource("posts", PostController)
```

| Method | URI | Controller method | Route name |
|---|---|---|---|
| GET | `/posts` | `index` | `posts.index` |
| GET | `/posts/create` | `create` | `posts.create` |
| POST | `/posts` | `store` | `posts.store` |
| GET | `/posts/{id}` | `show` | `posts.show` |
| GET | `/posts/{id}/edit` | `edit` | `posts.edit` |
| PUT, PATCH | `/posts/{id}` | `update` | `posts.update` |
| DELETE | `/posts/{id}` | `destroy` | `posts.destroy` |

Only methods that **exist on the controller** are routed, so an API controller without `create` and
`edit` simply gets five routes. Limit them explicitly with `only` or `except_`:

```python
app.resource("posts", PostController, only=["index", "show"])
app.resource("posts", PostController, except_=["destroy"])
```

## Route middleware

```python
app.get("/dashboard", [DashboardController, "index"]).with_middleware(AuthMiddleware)
```

See [Middleware](middleware.md) for the execution order.

## HTML form method spoofing

Browsers only send `GET` and `POST`. Include a `_method` field in a POST body and PyLara dispatches
it as that verb:

```html
<form method="POST" action="/posts/5">
  <input type="hidden" name="_method" value="DELETE">
</form>
```

Allowed values: `PUT`, `PATCH`, `DELETE`.

## Matching rules

- **The first registered route that matches wins.** Register static routes before parameterised
  ones: `/users/search` must come before `resource("users", ...)`, otherwise `search` is read as an
  `{id}`.
- If the path matches a route but not the method the response is **405**; if nothing matches it is
  **404**. Both are rendered by [error handling](errors.md).
- There are no regular-expression constraints on parameters; validate them in the action.

## Listing routes

```bash
python -m manage route:list
```
