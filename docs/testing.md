# Testing

PyLara tests are plain `unittest` tests; `pylara.testing.TestClient` calls your application
**in-process**, with no server or sockets.

## A first test

```python
# tests/test_tasks.py
import unittest
from pylara.testing import TestClient
from bootstrap.app import app


class TaskApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
```

```bash
python -m unittest discover -v
```

Run it from the project root. (`python -m unittest discover -s tests` skips
`tests/__init__.py`, which the generated project uses to select the test database.)

## Making requests

```python
client.get("/posts", query={"page": 2})
client.post("/posts", json={"title": "Hi"})          # JSON body
client.post("/login", data={"email": "a@b.c"})       # form body
client.put("/posts/1", json={...})
client.patch(...) / client.delete(...)
client.request("GET", "/x", headers={"Accept": "text/html"})
```

Authentication headers:

```python
auth = client.with_token("my-token")                  # sends Authorization: Bearer my-token
auth.get("/api/me")
client.with_headers(X_Custom="1").get("/")            # underscores become dashes
```

`TestClient` sends `Accept: application/json` by default, so errors come back as JSON; override it
to test HTML pages.

## Cookies and sessions

A `TestClient` keeps the cookies it receives and sends them back, so one client is one browser:

```python
client = TestClient(app)
client.get("/")                       # receives the session cookie
client.get("/")                       # sends it again: same session
other = TestClient(app)               # a new browser, new session
```

`with_token()` / `with_headers()` return a client that **shares** the same cookies. Generated projects set
`SESSION_DRIVER=memory` and a test `APP_KEY` in `tests/__init__.py`, so tests never write session files.
To test a CSRF-protected form, fetch a token first, see [CSRF Protection](csrf.md#testing).

## Uploading files in tests

```python
client.post("/avatar", data={"name": "Ana"}, files={"avatar": ("me.png", b"\x89PNG...", "image/png")})
```

## Reading responses

```python
response.status_code      # int
response.headers          # dict
response.text             # body as str
response.body             # body as bytes
response.json()           # parsed JSON
response.ok               # True for 2xx
response.cookies          # list of Set-Cookie header values
```

## Databases in tests

The generated project's `tests/__init__.py` sets `DB_DATABASE=:memory:` **before** `bootstrap.app`
is imported, so tests never touch your real database. Create the schema once per test class:

```python
import os
from pylara.database.migration import Migrator, discover
from pylara.orm.model import get_connection
from bootstrap.app import BASE


class PostTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Migrator(get_connection()).run(discover(os.path.join(BASE, "database", "migrations")))
        cls.client = TestClient(app)

    def setUp(self):
        get_connection().execute("DELETE FROM posts")       # clean slate for each test
```

Test models directly:

```python
def test_soft_delete(self):
    post = Post.create(title="x", body="y")
    post.delete()
    self.assertIsNone(Post.find(post.id))
    self.assertIsNotNone(Post.query().with_trashed().find(post.id))
```

## Testing with fakes

Because services live in the [container](container.md), swap them per test:

```python
app.instance("mailer", FakeMailer())
```

## Testing the framework itself

```bash
python -m tests          # runs tests/test_framework.py and tests/test_features.py
```

## pytest

`unittest`-style tests also run under pytest (`python -m pip install pytest`, `python -m pytest`).
