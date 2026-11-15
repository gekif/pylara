# Controllers

Controllers group request-handling logic into classes.

## Generating a controller

```bash
python -m manage make:controller PostController              # one index() method
python -m manage make:controller PostController --resource   # CRUD methods
```

This writes `app/controllers/post_controller.py` and prints the import line to use.

## Writing controllers

```python
from pylara import Controller, Request
from app.models.post import Post


class PostController(Controller):

    def index(self, request: Request):
        return self.json([p.to_dict() for p in Post.all()])

    def show(self, request: Request, id: str):
        return self.json(Post.find_or_fail(int(id)).to_dict())

    def store(self, request: Request):
        data = request.validate({"title": "required|string|max:150", "body": "required"})
        return self.json(Post.create(**data).to_dict(), 201)
```

Every action receives the `request` first, followed by the route parameters it declares (by
name). Route them:

```python
app.get("/posts/{id}", [PostController, "show"])
app.resource("posts", PostController)
```

## What you can return

A `Response`, a `dict`/`list` (JSON), a `str` (HTML) or `None`. See
[Responses](responses.md).

## Helpers on the base class

| Method | Does |
|---|---|
| `self.json(data, status=200)` | JSON response |
| `self.view(name, data=None, status=200, **context)` | render a [view](views.md) |
| `self.response(content="", status=200)` | plain response |
| `self.redirect(url, status=302)` | redirect |
| `self.abort(status, message="")` | stop with an HTTP error |
| `self.not_found(message="Not Found")` | `abort(404)` |
| `self.unauthorized(message="Unauthorized")` | `abort(401)` |

## Dependency injection

Controllers are created through the [container](container.md), so type-hinted constructor
parameters that are bound in the container are injected:

```python
class ReportController(Controller):
    def __init__(self, mailer: Mailer):
        self.mailer = mailer
```

A new controller instance is built **for every request**.

## Resource controllers

Implement any of `index create store show edit update destroy` and call `app.resource(...)`. See
[Routing](routing.md#resource-routes). The controller may implement only the methods it needs.

## Single-action routes

Not every endpoint needs a class: a function or lambda is a perfectly good action.

```python
@app.post("/subscribe")
def subscribe(request):
    data = request.validate({"email": "required|email"})
    ...
    return {"subscribed": data["email"]}
```
