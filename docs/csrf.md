# CSRF Protection

Cross-site request forgery tricks a logged-in user's browser into sending an unwanted request to your site
(for example from a malicious page). PyLara protects against it with a per-session secret **token** that
forms must send back.

## Enabling it

```python
from pylara.middleware.session import SessionMiddleware, VerifyCsrfToken

app.group({"middleware": [SessionMiddleware, VerifyCsrfToken]}, lambda r: [
    r.post("/posts", [PostController, "store"]),
])
```

`VerifyCsrfToken` checks every `POST`, `PUT`, `PATCH` and `DELETE`. `GET`, `HEAD` and `OPTIONS` are not
checked, so **never change data in a GET route**. Without a valid token the response is
**HTTP 419** "CSRF token mismatch.".

The generated project enables this for the web routes (`routes/web.py`) and not for the JSON API
(`routes/api.py`), which normally authenticates with tokens instead of cookies.

## HTML forms

Every view receives the token. Put the ready-made hidden field in your forms:

```html
<form method="POST" action="/posts">
  {!! csrf_field !!}
  <input name="title">
  <button>Save</button>
</form>
```

`csrf_field` renders `<input type="hidden" name="_token" value="...">`. `{!! !!}` (raw output) is right
here because PyLara generated the HTML. You can also use the bare value: `{{ csrf_token }}`.

Forms that fake `PUT`/`PATCH`/`DELETE` with `_method` ([Routing](routing.md#html-form-method-spoofing))
simply include both hidden fields.

## JavaScript and AJAX

Expose the token in your layout and send it as a header:

```html
<meta name="csrf-token" content="{{ csrf_token }}">
```

```javascript
const token = document.querySelector('meta[name="csrf-token"]').content;

fetch("/posts", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": token },
  body: JSON.stringify({ title: "Hello" }),
});
```

PyLara accepts the token in:

1. the **request body** field `_token` (form, multipart or JSON),
2. the `X-CSRF-TOKEN` header,
3. the `X-XSRF-TOKEN` header.

A token placed in the **URL query string is not accepted** (URLs leak into logs and referrers).

## Excluding routes

Webhooks from other services cannot send your token. Exclude them with a subclass (patterns use
`fnmatch` wildcards):

```python
class VerifyCsrf(VerifyCsrfToken):
    except_paths = ["/webhooks/*", "/api/*"]

app.group({"middleware": [SessionMiddleware, VerifyCsrf]}, ...)
```

Or simply register those routes in a group **without** `VerifyCsrfToken`. Then authenticate them another
way (a shared secret, a signature).

## A friendlier 419 page

```python
from pylara.http.exceptions import HttpException

@app.exception_handler(HttpException)
def expired_page(request, exc):
    if exc.status_code == 419:
        request.session.flash("error", "Your page expired. Please try again.")
        return RedirectResponse(request.header("Referer") or "/")
    return None                       # not a 419: let the default handling render it
```

Returning `None` declines the exception, see [Error Handling](errors.md#custom-exception-handlers).

## How the token is checked

The token is a random value stored in the session (`request.session.token()`); comparison is
constant-time. Because it lives in the session, it needs `SessionMiddleware` before it, and a
visitor needs a session cookie first (visit a page that renders a form).
`regenerate()` on login keeps the token.

## Testing

```python
token = client.get("/form-page").text           # a route that returns request.session.token()
client.post("/posts", data={"_token": token, "title": "x"})
```

or send `headers={"X-CSRF-TOKEN": token}`. The client keeps the session cookie for you.
