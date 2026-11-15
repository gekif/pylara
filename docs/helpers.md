# Helpers, Collections and Hashing

## Global helpers

Import from `pylara.support.helpers`.

```python
from pylara.support.helpers import (
    env, config, view, route, response, json, redirect, abort,
    collect, now, str_slug, str_snake, str_camel, str_pascal,
)
```

| Helper | Does |
|---|---|
| `env(key, default=None)` | environment value, see [Configuration](configuration.md#reading-values) |
| `config("file.key", default=None)` | value from `config/<file>.json` |
| `view(name, data=None, status=200, **context)` | render a [view](views.md) |
| `route(name, **params)` | URL of a [named route](routing.md#named-routes) |
| `response(content, status, headers)` / `json(data, status)` / `redirect(url, status)` | build responses |
| `abort(status, message="")` | raise an HTTP error |
| `now()` | current UTC `datetime` (naive) |
| `str_slug("Hello World!")` | `"hello-world"` |
| `str_snake("BlogPost")` | `"blog_post"` |
| `str_camel("blog_post")` / `str_pascal("blog_post")` | `"blogPost"` / `"BlogPost"` |

`env`, `config`, `view` and `route` use the **most recently created** `Application`, which is the
one your project builds in `bootstrap/app.py`.

## Collections

`collect(items)` wraps a list in a `Collection` with a fluent API:

```python
from pylara.support.helpers import collect

users = collect(User.all())
names = users.filter(lambda u: u.active).map(lambda u: u.name).all()
by_role = users.group_by("role")          # {"admin": [...], "user": [...]}
total = collect(orders).sum("total")
```

Items may be dictionaries or objects (models); keys are read either way.

| Method | Returns |
|---|---|
| `all()` | the underlying list |
| `count()` / `len(c)` | number of items |
| `first(default=None)` / `last(default=None)` | one item |
| `is_empty()` | bool |
| `filter(callback=None)` | new collection (without a callback: truthy items) |
| `map(callback)` | new collection |
| `each(callback)` | the same collection (runs the callback for side effects) |
| `pluck(key)` | collection of that key/attribute |
| `where(key, value)` | items whose key equals `value` |
| `unique(key=None)` | without duplicates |
| `sort_by(key, reverse=False)` | sorted |
| `group_by(key)` | dict of lists |
| `chunk(size)` | collection of lists |
| `sum(key=None)` / `avg(key=None)` / `min(key=None)` / `max(key=None)` | aggregates |
| `contains(key, value=None)` | bool |
| `to_json()` | JSON string |

## Hashing passwords

Never store passwords as plain text. `Hash` uses PBKDF2-HMAC-SHA256 with a random salt and 260,000
iterations, from the standard library only:

```python
from pylara.support.hashing import Hash

hashed = Hash.make("secret")              # "pbkdf2_sha256$260000$<salt>$<hash>"
Hash.check("secret", hashed)              # True
Hash.check("wrong", hashed)               # False
Hash.check("secret", "not a hash")        # False (never raises)
```

The comparison is constant-time. Store the whole string in a `VARCHAR(255)` column (`t.string("password")`).

```python
user = User.create(name="Ana", email="ana@example.com", password=Hash.make(data["password"]))

if user and Hash.check(request.input("password"), user.password):
    ...
```

Add `"password"` to the model's `hidden` list so it never appears in JSON.
