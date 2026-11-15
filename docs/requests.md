# Requests

Every action receives a `Request` (`from pylara import Request`).

## Basics

```python
request.method         # "GET", "POST", ...
request.path           # "/users/5"   (no query string)
request.ip             # client address (first X-Forwarded-For value, else REMOTE_ADDR)
request.route_params   # {"id": "5"}
```

## Retrieving input

PyLara merges the **query string** and the **body** (JSON or `application/x-www-form-urlencoded`).
Body values win over query values with the same name.

```python
request.all()                      # {"q": "x", "name": "Ana"}
request.input("name", "guest")     # one value, with default
request.get("name")                # alias of input()
request.has("name")                # bool
request.only("name", "email")      # only these keys (when present)
request.except_("password")        # everything except these keys
request.query("page", "1")         # query string only
request.json()                     # parsed JSON body ({} if absent or invalid)
request.json("user")               # one key of the JSON body
```

JSON values keep their types (`{"age": 30}` → `30`); form and query values are strings.

`multipart/form-data` forms are parsed too: text fields join `request.all()` and files are available
through `request.files` / `request.file("name")`. See [File Uploads](uploads.md). Bodies larger than
`MAX_BODY_MB` (default 10) are refused with HTTP 413.

## Headers, cookies and tokens

```python
request.header("Accept")          # case-insensitive lookup, default None
request.headers["Content-Type"]   # dict; keys are Title-Cased ("X-Forwarded-For")
request.bearer_token()            # from "Authorization: Bearer <token>", else ""
request.cookie("session", None)   # a cookie value
```

## Content negotiation

```python
request.is_json       # Content-Type is application/json
request.wants_json    # Accept contains application/json
```

Error pages use these to decide between JSON and HTML. See [Error Handling](errors.md).

## The session

```python
request.session.get("cart", [])
request.session.put("user_id", 7)
```

Available when `SessionMiddleware` is active; see [Sessions](sessions.md).

## Request attributes

Middleware can attach data for later layers:

```python
request.set_attribute("user", user)
request.attribute("user")            # None if missing
```

## Validation

`request.validate(rules)` returns the validated data or raises a 422. See
[Validation](validation.md).

## Method spoofing

A `_method` field in a POST body (`PUT`, `PATCH` or `DELETE`) changes the dispatched verb. See
[Routing](routing.md#html-form-method-spoofing).
