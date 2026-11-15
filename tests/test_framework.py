"""
tests/test_framework.py - Full test suite for PyLara.
Run with: python -m pytest tests/ -v
  or:     python tests/test_framework.py
"""

import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Setup test DB ─────────────────────────────────────────────────────────────
from pylara.orm.model import set_connection, Model

test_conn = sqlite3.connect(":memory:", check_same_thread=False)
test_conn.executescript("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(255),
        email VARCHAR(255),
        password VARCHAR(255),
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    );
    CREATE TABLE posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title VARCHAR(255),
        body TEXT,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    );
""")
set_connection("default", test_conn)


# ── Models ────────────────────────────────────────────────────────────────────
class Post(Model):
    table = "posts"
    fillable = ["user_id", "title", "body"]

    def author(self):
        return self.belongs_to(User, foreign_key="user_id")


class User(Model):
    table = "users"
    fillable = ["name", "email", "password"]
    hidden = ["password"]

    def posts(self):
        return self.has_many(Post)


# ── Test helpers ──────────────────────────────────────────────────────────────
_passed = 0
_failed = 0


def test(name: str, fn):
    global _passed, _failed
    try:
        fn()
        print(f"  \033[32m✓\033[0m {name}")
        _passed += 1
    except Exception as e:
        print(f"  \033[31m✗\033[0m {name}")
        print(f"      → {type(e).__name__}: {e}")
        _failed += 1


def assert_eq(a, b):
    assert a == b, f"Expected {b!r}, got {a!r}"


def assert_true(expr, msg=""):
    assert expr, msg or f"Expected True, got {expr!r}"


def assert_none(val):
    assert val is None, f"Expected None, got {val!r}"


# ─────────────────────────────────────────────────────────────────────────────
# 1. ORM Tests
# ─────────────────────────────────────────────────────────────────────────────
print("\n\033[1m[1] ORM / Model\033[0m")

def test_create_user():
    u = User.create(name="Alice", email="alice@test.com", password="secret")
    assert_true(u.id is not None)
    assert_eq(u.name, "Alice")

test("User.create()", test_create_user)

def test_find_user():
    u = User.find(1)
    assert_true(u is not None)
    assert_eq(u.email, "alice@test.com")

test("User.find(id)", test_find_user)

def test_all():
    User.create(name="Bob", email="bob@test.com", password="pass")
    users = User.all()
    assert_true(len(users) >= 2)

test("User.all()", test_all)

def test_where():
    users = User.where("name", "Alice").get()
    assert_eq(len(users), 1)
    assert_eq(users[0].name, "Alice")

test("User.where().get()", test_where)

def test_update():
    u = User.find(1)
    u.name = "Alice Updated"
    u.save()
    fresh = User.find(1)
    assert_eq(fresh.name, "Alice Updated")

test("model.save() update", test_update)

def test_to_dict_hides_password():
    u = User.find(1)
    d = u.to_dict()
    assert_true("password" not in d, "password should be hidden")

test("hidden fields excluded from to_dict()", test_to_dict_hides_password)

def test_relationship():
    u = User.find(1)
    Post.create(user_id=u.id, title="Hello", body="World")
    posts = u.posts()
    assert_true(len(posts) >= 1)

test("has_many relationship", test_relationship)

def test_belongs_to():
    post = Post.where("title", "Hello").first()
    author = post.author()
    assert_true(author is not None)
    assert_eq(author.id, post.user_id)

test("belongs_to relationship", test_belongs_to)

def test_find_or_fail_raises():
    from pylara.http.exceptions import NotFoundException
    try:
        User.find_or_fail(9999)
        assert False, "Should have raised"
    except NotFoundException:
        pass

test("find_or_fail() raises NotFoundException", test_find_or_fail_raises)

def test_paginate():
    result = User.query().paginate(per_page=1, page=1)
    assert_true("data" in result)
    assert_true("total" in result)
    assert_eq(result["per_page"], 1)

test("QueryBuilder.paginate()", test_paginate)

def test_first_or_create():
    u = User.first_or_create({"email": "firstorcreate@test.com"}, {"name": "FoC", "password": "x"})
    u2 = User.first_or_create({"email": "firstorcreate@test.com"}, {"name": "FoC", "password": "x"})
    assert_eq(u.id, u2.id)

test("first_or_create()", test_first_or_create)


# ─────────────────────────────────────────────────────────────────────────────
# 2. HTTP Request Tests
# ─────────────────────────────────────────────────────────────────────────────
print("\n\033[1m[2] HTTP Request\033[0m")

from pylara.http.request import Request

def test_request_from_environ():
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/users/42",
        "QUERY_STRING": "page=2&sort=name",
        "wsgi.input": __import__("io").BytesIO(b""),
    }
    req = Request.from_environ(environ)
    assert_eq(req.method, "GET")
    assert_eq(req.path, "/users/42")
    assert_eq(req.query("page"), "2")

test("Request.from_environ()", test_request_from_environ)

def test_request_json_body():
    import io
    body = json.dumps({"name": "Test", "age": 30}).encode()
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/users",
        "QUERY_STRING": "",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
        "HTTP_ACCEPT": "application/json",
    }
    req = Request.from_environ(environ)
    assert_eq(req.json("name"), "Test")
    assert_eq(req.input("age"), 30)

test("Request JSON body parsing", test_request_json_body)

def test_request_form_body():
    import io
    body = b"name=FormUser&email=form@test.com"
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/login",
        "QUERY_STRING": "",
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    req = Request.from_environ(environ)
    assert_eq(req.input("name"), "FormUser")

test("Request form body parsing", test_request_form_body)

def test_request_validate_ok():
    import io
    body = json.dumps({"name": "Valid", "email": "valid@test.com"}).encode()
    environ = {
        "REQUEST_METHOD": "POST", "PATH_INFO": "/",
        "QUERY_STRING": "",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    req = Request.from_environ(environ)
    data = req.validate({"name": "required|string", "email": "required|email"})
    assert_eq(data["name"], "Valid")

test("Request.validate() passes", test_request_validate_ok)

def test_request_validate_fails():
    import io
    from pylara.http.exceptions import ValidationException
    body = json.dumps({"name": ""}).encode()
    environ = {
        "REQUEST_METHOD": "POST", "PATH_INFO": "/",
        "QUERY_STRING": "", "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    req = Request.from_environ(environ)
    try:
        req.validate({"name": "required", "email": "required|email"})
        assert False
    except ValidationException as e:
        assert_true("name" in e.errors or "email" in e.errors)

test("Request.validate() raises ValidationException", test_request_validate_fails)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Router Tests
# ─────────────────────────────────────────────────────────────────────────────
print("\n\033[1m[3] Router\033[0m")

from pylara import Application
from pylara.http.request import Request as R
import io

def make_req(method, path, body=b"", content_type="application/json"):
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
        "HTTP_ACCEPT": "application/json",
    }
    return R.from_environ(environ)

def test_basic_routing():
    app = Application()
    app.get("/hello", lambda req: "world")
    resp = app.router.dispatch(make_req("GET", "/hello"))
    assert_eq(resp.content, "world")

test("Basic GET route", test_basic_routing)

def test_route_params():
    app = Application()
    app.get("/users/{id}", lambda req, id: f"user:{id}")
    resp = app.router.dispatch(make_req("GET", "/users/42"))
    assert_eq(resp.content, "user:42")

test("Route with {id} parameter", test_route_params)

def test_route_json_response():
    from pylara.http.response import JsonResponse
    app = Application()
    app.get("/api", lambda req: {"ok": True})
    resp = app.router.dispatch(make_req("GET", "/api"))
    assert_true(isinstance(resp, JsonResponse))
    assert_eq(json.loads(resp.content), {"ok": True})

test("Route returning dict → JsonResponse", test_route_json_response)

def test_route_404():
    from pylara.http.exceptions import NotFoundException
    app = Application()
    try:
        app.router.dispatch(make_req("GET", "/nope"))
        assert False
    except NotFoundException:
        pass

test("Missing route raises NotFoundException", test_route_404)

def test_route_group_prefix():
    app = Application()
    app.group({"prefix": "/api/v1"}, lambda r: [
        r.get("/ping", lambda req: "pong")
    ])
    resp = app.router.dispatch(make_req("GET", "/api/v1/ping"))
    assert_eq(resp.content, "pong")

test("Route group with prefix", test_route_group_prefix)

def test_resource_routes():
    app = Application()
    from pylara import Controller
    class ItemController(Controller):
        def index(self, req): return {"items": []}
        def show(self, req, id): return {"id": id}
        def store(self, req): return {"created": True}
        def update(self, req, id): return {"updated": id}
        def destroy(self, req, id): return {"deleted": id}
    app.resource("items", ItemController)
    resp = app.router.dispatch(make_req("GET", "/items"))
    assert_eq(json.loads(resp.content), {"items": []})
    resp2 = app.router.dispatch(make_req("GET", "/items/7"))
    assert_eq(json.loads(resp2.content)["id"], "7")

test("Resource routes (index + show)", test_resource_routes)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Response Tests
# ─────────────────────────────────────────────────────────────────────────────
print("\n\033[1m[4] Response\033[0m")

from pylara.http.response import Response, JsonResponse, RedirectResponse

def test_response_basic():
    r = Response("Hello", 200)
    assert_eq(r.content, "Hello")
    assert_eq(r.status_code, 200)
    assert_eq(r.reason_phrase, "OK")

test("Response basic", test_response_basic)

def test_json_response():
    r = JsonResponse({"key": "value"}, 201)
    assert_eq(r.status_code, 201)
    assert_eq(json.loads(r.content), {"key": "value"})
    assert_true("application/json" in r.headers["Content-Type"])

test("JsonResponse", test_json_response)

def test_redirect_response():
    r = RedirectResponse("/login", 302)
    assert_eq(r.status_code, 302)
    assert_eq(r.headers["Location"], "/login")

test("RedirectResponse", test_redirect_response)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Middleware Tests
# ─────────────────────────────────────────────────────────────────────────────
print("\n\033[1m[5] Middleware\033[0m")

from pylara.middleware.middleware import CorsMiddleware, ThrottleMiddleware

def test_cors_middleware():
    app = Application()
    app.get("/cors-test", lambda req: "ok")
    req = make_req("GET", "/cors-test")

    from pylara.http.kernel import HttpKernel
    class KernelWithCors(HttpKernel):
        global_middleware = [CorsMiddleware]
    kernel = KernelWithCors(app)
    resp = kernel.handle(req)
    assert_true("Access-Control-Allow-Origin" in resp.headers)

test("CorsMiddleware adds CORS headers", test_cors_middleware)

def test_middleware_pipeline():
    from pylara.middleware.middleware import Middleware
    log = []
    class LogMiddleware(Middleware):
        def handle(self, request, next):
            log.append("before")
            resp = next()
            log.append("after")
            return resp
    app = Application()
    app.group({"middleware": [LogMiddleware]}, lambda r: [
        r.get("/mw-test", lambda req: "done")
    ])
    app.router.dispatch(make_req("GET", "/mw-test"))
    assert_eq(log, ["before", "after"])

test("Middleware before/after pipeline", test_middleware_pipeline)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Collection Tests
# ─────────────────────────────────────────────────────────────────────────────
print("\n\033[1m[6] Collection\033[0m")

from pylara.support.helpers import collect

def test_collection_map_filter():
    c = collect([1, 2, 3, 4, 5])
    result = c.filter(lambda x: x % 2 == 0).map(lambda x: x * 10).all()
    assert_eq(result, [20, 40])

test("Collection.filter().map()", test_collection_map_filter)

def test_collection_pluck():
    c = collect([{"name": "Alice"}, {"name": "Bob"}])
    assert_eq(c.pluck("name").all(), ["Alice", "Bob"])

test("Collection.pluck()", test_collection_pluck)

def test_collection_sum_avg():
    c = collect([10, 20, 30])
    assert_eq(c.sum(), 60)
    assert_eq(c.avg(), 20.0)

test("Collection.sum() / avg()", test_collection_sum_avg)

def test_collection_group_by():
    c = collect([
        {"role": "admin", "name": "Alice"},
        {"role": "user", "name": "Bob"},
        {"role": "admin", "name": "Charlie"},
    ])
    grouped = c.group_by("role")
    assert_eq(len(grouped["admin"]), 2)
    assert_eq(len(grouped["user"]), 1)

test("Collection.group_by()", test_collection_group_by)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Schema / Migration Tests
# ─────────────────────────────────────────────────────────────────────────────
print("\n\033[1m[7] Schema & Migration\033[0m")

from pylara.database.migration import Schema, Migration, Migrator

def test_schema_create_sql():
    stmts = Schema.create("products", lambda t: [
        t.id(),
        t.string("name"),
        t.decimal("price"),
        t.integer("stock"),
        t.timestamps(),
    ])
    assert_true(len(stmts) > 0)
    assert_true("CREATE TABLE" in stmts[0])
    assert_true("products" in stmts[0])

test("Schema.create() generates SQL", test_schema_create_sql)

def test_migration_run():
    conn2 = sqlite3.connect(":memory:")

    class CreateProductsTable(Migration):
        def up(self):
            return Schema.create("products", lambda t: [
                t.id(),
                t.string("name"),
                t.timestamps(),
            ])
        def down(self):
            return Schema.drop("products")

    migrator = Migrator(conn2)
    migrator.run([("create_products_table", CreateProductsTable)])
    assert_true(Schema.has_table("products", conn2))
    migrator.rollback({"create_products_table": CreateProductsTable})
    assert_true(not Schema.has_table("products", conn2))

test("Migration run + rollback", test_migration_run)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Regresi PyLara 1.1 (perbaikan setelah audit)
# ─────────────────────────────────────────────────────────────────────────────
print("\n\033[1m[8] Regresi PyLara 1.1\033[0m")

def test_dict_through_route_middleware():
    from pylara.http.response import JsonResponse as J
    app = Application()
    app.group({"middleware": [CorsMiddleware]}, lambda r: [r.get("/h", lambda req: {"ok": 1})])
    resp = app.router.dispatch(make_req("GET", "/h"))
    assert_true(isinstance(resp, J))
    assert_true("Access-Control-Allow-Origin" in resp.headers)

test("Action return dict + middleware route", test_dict_through_route_middleware)

def test_decorator_routes():
    app = Application()

    @app.get("/dekor")
    def dekor(req):
        return "ok"

    @app.router.post("/kirim")
    def kirim(req):
        return {"sent": True}

    assert_eq(app.router.dispatch(make_req("GET", "/dekor")).content, "ok")
    assert_eq(json.loads(app.router.dispatch(make_req("POST", "/kirim")).content), {"sent": True})
    assert_true(callable(dekor))

test("Route lewat decorator @app.get()", test_decorator_routes)

def test_sql_identifier_rejected():
    for bad in ("name; DROP TABLE users", "name) OR (1=1", "a b"):
        try:
            User.where(bad, "x")
            assert False, "kolom berbahaya lolos"
        except ValueError:
            pass
    try:
        User.query().order_by("name; DROP TABLE users")
        assert False
    except ValueError:
        pass
    try:
        User.query().order_by("name", "ASC; DROP")
        assert False
    except ValueError:
        pass
    try:
        User.where("name", "; DROP", "x")
        assert False
    except ValueError:
        pass

test("Nama kolom/operator berbahaya ditolak", test_sql_identifier_rejected)

def test_mass_assignment_injection_blocked():
    class Open(Model):          # guarded = [] -> semua key lolos fill()
        table = "users"
        guarded = []
    try:
        Open.create(**{"name": "x", "email) VALUES ('h'); --": "y"})
        assert False, "kolom berbahaya lolos di INSERT"
    except ValueError:
        pass

test("INSERT dengan nama kolom berbahaya ditolak", test_mass_assignment_injection_blocked)

def test_hash():
    from pylara.support.hashing import Hash
    h = Hash.make("rahasia")
    assert_true(h.startswith("pbkdf2_sha256$"))
    assert_true(Hash.check("rahasia", h))
    assert_true(not Hash.check("salah", h))
    assert_true(not Hash.check("rahasia", "bukan-hash"))
    assert_true(Hash.make("rahasia") != h, "salt harus acak")

test("Hash.make() / Hash.check()", test_hash)

def test_demo_app_end_to_end():
    import importlib
    demo_dir = os.path.join(os.path.dirname(__file__), "..", "examples", "demo")
    sys.path.insert(0, os.path.abspath(demo_dir))
    boot = importlib.import_module("bootstrap.app")      # app demo + seed + route
    from pylara.orm.model import set_connection as sc
    demo = boot.app

    def call(method, path, body=None, token=None):
        raw = json.dumps(body).encode() if body is not None else b""
        path, _, qs = path.partition("?")
        env = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": qs,
               "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(raw)),
               "wsgi.input": io.BytesIO(raw), "HTTP_ACCEPT": "application/json"}
        if token:
            env["HTTP_AUTHORIZATION"] = "Bearer " + token
        r = demo.handle(env)
        try:
            return r.status_code, json.loads(r.content)
        except ValueError:
            return r.status_code, r.content

    code, body = call("GET", "/")
    assert_eq(code, 200)
    assert_eq(call("GET", "/api/health")[1]["framework"], "PyLara")
    code, found = call("GET", "/api/users/search?q=Ali")          # tidak boleh tertelan {id}
    assert_eq((code, [u["name"] for u in found]), (200, ["Alice"]))
    assert_eq(call("GET", "/api/auth/me")[0], 401)                # tanpa token
    code, login = call("POST", "/api/auth/login", {"email": "alice@example.com", "password": "secret"})
    assert_eq(code, 200)
    assert_true("password" not in login["user"])
    assert_eq(call("POST", "/api/auth/login", {"email": "alice@example.com", "password": "salah"})[0], 401)
    code, me = call("GET", "/api/auth/me", token=login["token"])
    assert_eq((code, me["email"]), (200, "alice@example.com"))
    code, reg = call("POST", "/api/auth/register", {"name": "Citra", "email": "c@x.com", "password": "abcdef"})
    assert_eq(code, 201)
    stored = boot.User.find(reg["user"]["id"])._attributes["password"]
    assert_true(stored.startswith("pbkdf2_sha256$"), "password harus di-hash")
    assert_eq(call("POST", "/api/users", {"name": "Dedi", "email": "d@x.com", "password": "abcdef"})[0], 201)
    assert_true(boot.User.where("email", "d@x.com").first()._attributes["password"].startswith("pbkdf2_sha256$"))
    sc("default", test_conn)                                      # kembalikan koneksi tes

test("Aplikasi demo end-to-end (auth, search, hash)", test_demo_app_end_to_end)


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
total = _passed + _failed
print(f"\n  {'─'*40}")
print(f"  Tests: {total}  \033[32mPassed: {_passed}\033[0m  \033[31mFailed: {_failed}\033[0m\n")
sys.exit(0 if _failed == 0 else 1)
