"""Feature and integration tests for PyLara 1.0.  Run: python -m unittest tests.test_features -v"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout, redirect_stderr

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from pylara import Application, Controller, JsonResponse, Model, Response, __version__
from pylara.http.exceptions import HttpException
from pylara.middleware.middleware import Middleware
from pylara.testing import TestClient


def read(path, encoding="utf-8"):
    with open(path, encoding=encoding) as f:
        return f.read()


@contextmanager
def chdir(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def quiet(fn, *a, **kw):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        result = fn(*a, **kw)
    return result, out.getvalue(), err.getvalue()


class VersionTest(unittest.TestCase):
    def test_single_source_of_truth(self):
        from pylara.version import __version__ as v
        self.assertEqual(v, "1.0.0")
        self.assertEqual(Application.VERSION, v)
        self.assertEqual(__version__, v)

    def test_pyproject_reads_version_dynamically(self):
        text = read(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8")
        self.assertIn('dynamic = ["version"]', text)
        self.assertIn("pylara.version.__version__", text)


class RoutingTest(unittest.TestCase):
    def setUp(self):
        self.app = Application(tempfile.mkdtemp())
        self.client = TestClient(self.app)

    def test_optional_parameter(self):
        self.app.get("/posts/{id?}", lambda req, id=None: {"id": id})
        self.assertEqual(self.client.get("/posts").json(), {"id": None})
        self.assertEqual(self.client.get("/posts/7").json(), {"id": "7"})

    def test_literal_dot_is_not_a_wildcard(self):
        self.app.get("/file.json", lambda req: "ok")
        self.assertEqual(self.client.get("/file.json").status_code, 200)
        self.assertEqual(self.client.get("/fileXjson").status_code, 404)

    def test_named_routes_and_url_generation(self):
        self.app.get("/users/{id}/posts/{slug?}", lambda req, id, slug=None: "x").named("user.posts")
        self.assertEqual(self.app.route("user.posts", id=3), "/users/3/posts")
        self.assertEqual(self.app.route("user.posts", id=3, slug="a b"), "/users/3/posts/a%20b")
        with self.assertRaises(ValueError):
            self.app.route("user.posts")
        with self.assertRaises(KeyError):
            self.app.route("nope")

    def test_resource_route_names(self):
        class C(Controller):
            def index(self, request): return []
            def show(self, request, id): return {"id": id}
        self.app.resource("things", C)
        self.assertEqual(self.app.route("things.show", id=5), "/things/5")
        self.assertEqual(self.app.route("things.index"), "/things")

    def test_405_vs_404(self):
        self.app.get("/only-get", lambda req: "x")
        self.assertEqual(self.client.post("/only-get").status_code, 405)
        self.assertEqual(self.client.get("/missing").status_code, 404)

    def test_form_method_spoofing(self):
        self.app.delete("/items/{id}", lambda req, id: {"deleted": id})
        r = self.client.post("/items/9", data={"_method": "DELETE"})
        self.assertEqual(r.json(), {"deleted": "9"})

    def test_route_middleware_and_group_order(self):
        order = []

        class Tag(Middleware):
            def __init__(self, label="t"): self.label = label
            def handle(self, request, next):
                order.append(self.label)
                return next()

        self.app.group({"prefix": "/g", "middleware": [Tag("group")]},
                       lambda r: r.get("/x", lambda req: "ok").with_middleware(Tag("route")))
        self.assertEqual(self.client.get("/g/x").text, "ok")
        self.assertEqual(order, ["group", "route"])

    def test_global_middleware_via_use(self):
        class Stamp(Middleware):
            def handle(self, request, next):
                response = next()
                response.headers["X-Stamp"] = "1"
                return response
        self.app.use(Stamp)
        self.app.get("/", lambda req: "hi")
        self.assertEqual(self.client.get("/").headers["X-Stamp"], "1")

    def test_middleware_can_return_plain_dict(self):
        class Short(Middleware):
            def handle(self, request, next):
                return {"blocked": True}
        self.app.use(Short)
        self.assertEqual(self.client.get("/anything").json(), {"blocked": True})


class ErrorHandlingTest(unittest.TestCase):
    def setUp(self):
        self.app = Application(tempfile.mkdtemp())
        self.client = TestClient(self.app)

    def test_custom_exception_handler(self):
        class PaymentError(Exception): pass

        @self.app.exception_handler(PaymentError)
        def handle(request, exc):
            return JsonResponse({"error": str(exc)}, 402)

        @self.app.get("/pay")
        def pay(req):
            raise PaymentError("card declined")
        r = self.client.get("/pay")
        self.assertEqual((r.status_code, r.json()), (402, {"error": "card declined"}))

    def test_handler_returning_none_defers_to_next_handler_and_defaults(self):
        from pylara.http.exceptions import HttpException
        calls = []

        @self.app.exception_handler(HttpException)
        def only_teapots(request, exc):
            calls.append(exc.status_code)
            if exc.status_code == 418:
                return JsonResponse({"custom": True}, 418)
            return None                                   # decline everything else

        @self.app.get("/teapot")
        def teapot(req):
            raise HttpException(418, "tea")
        self.assertEqual(self.client.get("/teapot").json(), {"custom": True})
        r = self.client.get("/missing")                   # declined -> default 404 JSON
        self.assertEqual((r.status_code, r.json()["message"].startswith("No route")), (404, True))
        self.assertEqual(calls, [418, 404])

    def test_html_error_page_escapes_user_input(self):
        r = TestClient(self.app).request("GET", "/<script>alert(1)</script>", headers={"Accept": "text/html"})
        self.assertEqual(r.status_code, 404)
        self.assertNotIn("<script>", r.text)
        self.assertIn("&lt;script&gt;", r.text)

    def test_abort_and_validation_errors(self):
        from pylara.http.response import abort

        @self.app.get("/secret")
        def secret(req):
            abort(403, "No way")

        @self.app.post("/v")
        def v(req):
            req.validate({"n": "required|integer"})
        self.assertEqual(self.client.get("/secret").json(), {"message": "No way"})
        r = self.client.post("/v", json={"n": "abc"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("n", r.json()["errors"])

    def test_server_error_hides_details_when_not_debug(self):
        os.environ["APP_DEBUG"] = "false"
        try:
            @self.app.get("/boom")
            def boom(req):
                raise RuntimeError("secret internals")
            r, _, _ = quiet(self.client.get, "/boom")
            self.assertEqual(r.status_code, 500)
            self.assertNotIn("secret internals", r.text)
        finally:
            del os.environ["APP_DEBUG"]

    def test_server_error_shows_details_in_debug(self):
        os.environ["APP_DEBUG"] = "true"
        try:
            @self.app.get("/boom")
            def boom(req):
                raise RuntimeError("visible")
            r, _, _ = quiet(self.client.get, "/boom")
            self.assertIn("visible", r.text)
        finally:
            del os.environ["APP_DEBUG"]


class ContainerAndEnvTest(unittest.TestCase):
    def setUp(self):
        self.app = Application(tempfile.mkdtemp())

    def test_bind_forms_and_singleton(self):
        self.app.bind("a", lambda: "bare")
        self.app.bind("b", lambda container: container.make("a") + "+container")
        self.assertEqual(self.app.make("a"), "bare")
        self.assertEqual(self.app.make("b"), "bare+container")
        self.app.singleton("s", lambda: object())
        self.assertIs(self.app.make("s"), self.app.make("s"))
        self.assertIs(self.app.make("app"), self.app)

    def test_autowiring_by_type_hint(self):
        class Mailer: pass
        class Service:
            def __init__(self, mailer: Mailer, retries: int = 3):
                self.mailer, self.retries = mailer, retries
        self.app.singleton(Mailer, lambda: Mailer())
        service = self.app.build(Service)
        self.assertIs(service.mailer, self.app.make(Mailer))
        self.assertEqual(service.retries, 3)

    def test_controller_constructor_injection(self):
        class Greeter:
            def hello(self): return "hi"
        self.app.singleton(Greeter, lambda: Greeter())

        class C(Controller):
            def __init__(self, greeter: Greeter): self.greeter = greeter
            def index(self, request): return {"msg": self.greeter.hello()}
        self.app.get("/", [C, "index"])
        self.assertEqual(TestClient(self.app).get("/").json(), {"msg": "hi"})

    def test_unresolvable_dependency_is_a_clear_error(self):
        class NeedsX:
            def __init__(self, x): pass
        with self.assertRaises(KeyError):
            self.app.build(NeedsX)

    def test_env_conversion_and_dotenv(self):
        base = tempfile.mkdtemp()
        with open(os.path.join(base, ".env"), "w") as f:
            f.write('PYL_A=true\nPYL_B="quoted value"\nPYL_C=plain # comment\nPYL_D=null\n# PYL_E=no\n')
        keys = ["PYL_A", "PYL_B", "PYL_C", "PYL_D", "PYL_E"]
        try:
            app = Application(base)
            self.assertIs(app.env("PYL_A"), True)
            self.assertEqual(app.env("PYL_B"), "quoted value")
            self.assertEqual(app.env("PYL_C"), "plain")
            self.assertIsNone(app.env("PYL_D", "x"))
            self.assertEqual(app.env("PYL_E", "default"), "default")
        finally:
            for k in keys:
                os.environ.pop(k, None)

    def test_real_environment_beats_dotenv(self):
        base = tempfile.mkdtemp()
        with open(os.path.join(base, ".env"), "w") as f:
            f.write("PYL_WIN=from_file\n")
        os.environ["PYL_WIN"] = "from_os"
        try:
            self.assertEqual(Application(base).env("PYL_WIN"), "from_os")
        finally:
            del os.environ["PYL_WIN"]

    def test_config_dot_notation(self):
        base = tempfile.mkdtemp()
        os.makedirs(os.path.join(base, "config"))
        with open(os.path.join(base, "config", "app.json"), "w") as f:
            json.dump({"name": "X", "mail": {"host": "h"}}, f)
        app = Application(base)
        self.assertEqual(app.config.get("app.mail.host"), "h")
        self.assertEqual(app.config.get("app.nope", "d"), "d")

    def test_service_provider_lifecycle(self):
        from pylara.support.service_provider import ServiceProvider
        calls = []

        class P(ServiceProvider):
            def register(self): calls.append("register")
            def boot(self): calls.append("boot")
        self.app.register(P)
        self.assertEqual(calls, ["register"])
        self.app.boot()
        self.app.boot()
        self.assertEqual(calls, ["register", "boot"])


class StaticFilesAndViewsTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.base, "public", "css"))
        os.makedirs(os.path.join(self.base, "resources", "views", "layouts"))
        with open(os.path.join(self.base, "public", "css", "a.css"), "w") as f:
            f.write("body{}")
        with open(os.path.join(self.base, "public", ".hidden"), "w") as f:
            f.write("secret")
        with open(os.path.join(self.base, "secret.txt"), "w") as f:
            f.write("outside")
        self.app = Application(self.base)
        self.client = TestClient(self.app)

    def test_static_file_served_with_mime_type(self):
        r = self.client.get("/css/a.css")
        self.assertEqual((r.status_code, r.text), (200, "body{}"))
        self.assertTrue(r.headers["Content-Type"].startswith("text/css"))

    def test_static_cannot_escape_public_or_read_dotfiles(self):
        for path in ("/../secret.txt", "/css/../../secret.txt", "/.hidden", "/%2e%2e/secret.txt"):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_static_does_not_shadow_routes_without_files(self):
        self.app.get("/css/live", lambda req: "route")
        self.assertEqual(self.client.get("/css/live").text, "route")

    def test_views_render_from_controller_and_helper(self):
        views = os.path.join(self.base, "resources", "views")
        with open(os.path.join(views, "layouts", "main.html"), "w") as f:
            f.write("<h1>{% block t %}-{% endblock %}</h1>")
        with open(os.path.join(views, "page.html"), "w") as f:
            f.write('{% extends "layouts.main" %}{% block t %}{{ title }}{% endblock %}')

        class C(Controller):
            def index(self, request): return self.view("page", title="<Hello>")
        self.app.get("/", [C, "index"])
        self.assertEqual(self.client.get("/").text, "<h1>&lt;Hello&gt;</h1>")

        from pylara.support.helpers import view
        self.assertEqual(view("page", {"title": "A"}).content, "<h1>A</h1>")

    def test_view_errors(self):
        from pylara.support.view import ViewError
        with self.assertRaises(ViewError):
            self.app.views.render("missing")
        with self.assertRaises(ViewError):
            self.app.views.render("../secret")


class TemplateCommentTest(unittest.TestCase):
    def test_comments_render_nothing_and_may_hide_tags(self):
        from pylara.support.view import ViewFactory
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "c.html"), "w") as f:
            f.write("A{# note #}B{# {{ secret }} {% if x %} #}C{#\nmulti\nline\n#}D")
        self.assertEqual(ViewFactory(d).render("c", {"secret": "LEAK", "x": 1}), "ABCD")


class ValidationAndRequestTest(unittest.TestCase):
    def setUp(self):
        self.app = Application(tempfile.mkdtemp())
        self.client = TestClient(self.app)
        self.app.post("/v", lambda req: req.validate({
            "name": "required|string|min:2|max:5",
            "age": "integer",
            "price": "numeric",
            "role": "in:admin,user",
            "email": "email",
            "active": "boolean",
            "password": "confirmed",
        }))

    def errors(self, payload):
        r = self.client.post("/v", json=payload)
        return r.status_code, r.json().get("errors", {})

    def test_valid_payload_returns_validated_data_only(self):
        r = self.client.post("/v", json={"name": "Ann", "age": 5, "role": "user", "extra": "x"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["name"], "Ann")
        self.assertNotIn("extra", r.json())

    def test_each_rule_fails(self):
        code, e = self.errors({"name": "A", "age": "x", "price": "abc", "role": "root",
                               "email": "no-at", "active": "maybe", "password": "a"})
        self.assertEqual(code, 422)
        self.assertEqual(set(e), {"name", "age", "price", "role", "email", "active", "password"})

    def test_max_and_required(self):
        self.assertIn("name", self.errors({"name": "toolong"})[1])
        self.assertIn("name", self.errors({})[1])

    def test_integer_rejects_booleans_and_fractions(self):
        self.assertIn("age", self.errors({"name": "Ann", "age": True})[1])
        self.assertIn("age", self.errors({"name": "Ann", "age": 1.5})[1])

    def test_confirmed_passes_when_matching(self):
        code, _ = self.errors({"name": "Ann", "password": "x", "password_confirmation": "x"})
        self.assertEqual(code, 200)

    def test_request_helpers(self):
        seen = {}

        @self.app.get("/h")
        def h(req):
            seen.update(token=req.bearer_token(), cookie=req.cookie("sid"), ip=req.ip,
                        header=req.header("x-custom"), q=req.query("a"))
            return "ok"
        self.client.get("/h", query={"a": "1"}, headers={
            "Authorization": "Bearer tok", "Cookie": "sid=abc; other=1",
            "X-Forwarded-For": "9.9.9.9, 1.1.1.1", "X-Custom": "v"})
        self.assertEqual(seen, {"token": "tok", "cookie": "abc", "ip": "9.9.9.9", "header": "v", "q": "1"})


class ResponseAndWsgiTest(unittest.TestCase):
    def setUp(self):
        self.app = Application(tempfile.mkdtemp())

    def call(self, method="GET", path="/"):
        captured = {}

        def start_response(status, headers):
            captured["status"], captured["headers"] = status, headers
        environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "",
                   "wsgi.input": io.BytesIO(b"")}
        body = b"".join(self.app(environ, start_response))
        return captured, body

    def test_multiple_cookies_and_content_length(self):
        self.app.get("/", lambda req: Response("héllo").with_cookie("a", "1").with_cookie("b", "2", max_age=60, secure=True))
        captured, body = self.call()
        headers = captured["headers"]
        cookies = [v for k, v in headers if k == "Set-Cookie"]
        self.assertEqual(len(cookies), 2)
        self.assertIn("HttpOnly", cookies[0])
        self.assertIn("Secure", cookies[1])
        self.assertIn(("Content-Length", str(len("héllo".encode()))), headers)
        self.assertEqual(captured["status"], "200 OK")
        self.assertEqual(body.decode(), "héllo")

    def test_head_request_has_no_body(self):
        self.app.get("/", lambda req: "body")
        captured, body = self.call("HEAD")
        self.assertEqual(body, b"")
        self.assertIn(("Content-Length", "4"), captured["headers"])


class OrmAndMigrationTest(unittest.TestCase):
    def test_cast_ignores_null(self):
        import sqlite3
        from pylara.orm.model import set_connection
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE gadgets (id INTEGER PRIMARY KEY AUTOINCREMENT, qty INTEGER, created_at TEXT, updated_at TEXT)")
        set_connection("default", conn)

        class Gadget(Model):
            table = "gadgets"
            fillable = ["qty"]
            casts = {"qty": int}
        g = Gadget.create(qty=None)
        self.assertIsNone(Gadget.find(g.id).qty)
        self.assertEqual(Gadget.create(qty="5").qty, 5)

    def test_discover_status_and_rollback(self):
        import sqlite3
        from pylara.database.migration import Migrator, discover, Schema
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "2026_01_01_000000_create_a_table.py"), "w") as f:
            f.write("from pylara.database.migration import Migration, Schema\n"
                    "class CreateATable(Migration):\n"
                    "    def up(self): return Schema.create('a', lambda t: [t.id(), t.boolean('x').default(True)])\n"
                    "    def down(self): return Schema.drop('a')\n")
        conn = sqlite3.connect(":memory:")
        migrations = discover(d)
        self.assertEqual([n for n, _ in migrations], ["2026_01_01_000000_create_a_table"])
        m = Migrator(conn)
        self.assertEqual(m.status(migrations), [("2026_01_01_000000_create_a_table", False)])
        quiet(m.run, migrations)
        self.assertEqual(m.status(migrations)[0][1], True)
        self.assertTrue(Schema.has_table("a", conn))
        quiet(m.rollback, dict(migrations))
        self.assertFalse(Schema.has_table("a", conn))

    def test_default_literals_are_escaped(self):
        sql = Schema_create = None
        from pylara.database.migration import Schema
        sql = Schema.create("t", lambda t: [t.string("s").default("it's"), t.boolean("b").default(False)])[0]
        self.assertIn("DEFAULT 'it''s'", sql)
        self.assertIn("DEFAULT 0", sql)
        self.assertEqual(sql.count("DEFAULT"), 2)


class MiddlewareBuiltinsTest(unittest.TestCase):
    def setUp(self):
        self.app = Application(tempfile.mkdtemp())
        self.app.get("/x", lambda req: "ok")

    def cors(self, origins, origin=None, method="GET"):
        from pylara.middleware.middleware import CorsMiddleware

        class C(CorsMiddleware):
            allowed_origins = origins
        app = Application(tempfile.mkdtemp())
        app.use(C)
        app.get("/x", lambda req: "ok")
        headers = {"Origin": origin} if origin else {}
        return TestClient(app).request(method, "/x", headers=headers)

    def test_cors_wildcard_single_origin_and_preflight(self):
        self.assertEqual(self.cors(["*"]).headers["Access-Control-Allow-Origin"], "*")
        allowed = ["https://a.com", "https://b.com"]
        r = self.cors(allowed, "https://b.com")
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "https://b.com")   # one origin, never a list
        self.assertEqual(r.headers["Vary"], "Origin")
        self.assertNotIn("Access-Control-Allow-Origin", self.cors(allowed, "https://evil.com").headers)
        pre = self.cors(["*"], method="OPTIONS")
        self.assertEqual(pre.status_code, 204)

    def test_throttle_blocks_after_limit(self):
        from pylara.middleware.middleware import ThrottleMiddleware

        class Tiny(ThrottleMiddleware):
            _counts = {}
            max_requests = 2
        self.app.use(Tiny)
        client = TestClient(self.app)
        self.assertEqual([client.get("/x").status_code for _ in range(3)], [200, 200, 429])

    def test_auth_middleware_subclass(self):
        from pylara.middleware.middleware import AuthMiddleware

        class Tokens(AuthMiddleware):
            def authenticate(self, token):
                return {"id": 1} if token == "good" else None
        self.app.get("/me", lambda req: req.attribute("user")).with_middleware(Tokens)
        client = TestClient(self.app)
        self.assertEqual(client.get("/me").status_code, 401)
        self.assertEqual(client.with_token("good").get("/me").json(), {"id": 1})

    def test_not_null_and_status_phrases(self):
        from pylara.database.migration import Schema
        self.assertIn("name VARCHAR(255) NOT NULL", Schema.create("t", lambda t: [t.string("name").not_null()])[0])
        self.assertEqual(Response("", 409).reason_phrase, "Conflict")
        self.assertEqual(Response("", 503).reason_phrase, "Service Unavailable")

    def test_where_rejects_in_operator(self):
        import sqlite3
        from pylara.orm.model import set_connection

        class Thing(Model):
            table = "things"
        set_connection("default", sqlite3.connect(":memory:"))
        with self.assertRaises(ValueError):
            Thing.where("id", "IN", [1, 2])


class MassAssignmentTest(unittest.TestCase):
    def setUp(self):
        import sqlite3
        from pylara.orm.model import set_connection
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE members (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, is_admin INTEGER,"
                     " created_at TEXT, updated_at TEXT)")
        set_connection("default", conn)

    def test_nothing_is_assignable_by_default(self):
        class Member(Model):
            table = "members"
        m = Member.create(name="x", is_admin=1)
        self.assertIsNone(m.to_dict().get("name"))
        self.assertIsNone(m.to_dict().get("is_admin"))

    def test_fillable_is_a_strict_whitelist_and_never_includes_id(self):
        class Member(Model):
            table = "members"
            fillable = ["name"]
        m = Member.create(name="a", is_admin=1, id=99)
        self.assertEqual(m.name, "a")
        self.assertNotEqual(m.id, 99)
        self.assertIsNone(Member.find(m.id).to_dict().get("is_admin"))

    def test_guarded_empty_list_opts_into_everything(self):
        class Member(Model):
            table = "members"
            guarded = []
        self.assertEqual(Member.create(name="a", is_admin=1).is_admin, 1)

    def test_guarded_blacklist(self):
        class Member(Model):
            table = "members"
            guarded = ["is_admin"]
        m = Member.create(name="a", is_admin=1)
        self.assertEqual(m.name, "a")
        self.assertIsNone(Member.find(m.id).to_dict().get("is_admin"))

    def test_update_or_create_respects_fillable(self):
        class Member(Model):
            table = "members"
            fillable = ["name"]
        m = Member.create(name="a")
        Member.update_or_create({"name": "a"}, {"name": "b", "is_admin": 1})
        fresh = Member.find(m.id)
        self.assertEqual(fresh.name, "b")
        self.assertIsNone(fresh.to_dict().get("is_admin"))

    def test_force_fill_bypasses_on_purpose(self):
        class Member(Model):
            table = "members"
        m = Member().force_fill(name="forced")
        m.save()
        self.assertEqual(Member.find(m.id).name, "forced")


class QueryBuilderNullTest(unittest.TestCase):
    def test_null_comparisons(self):
        import sqlite3
        from pylara.orm.model import set_connection
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT,"
                     " created_at TEXT, updated_at TEXT)")
        set_connection("default", conn)

        class Note(Model):
            table = "notes"
            fillable = ["title", "body"]
        Note.create(title="a", body=None)
        Note.create(title="b", body="text")
        self.assertEqual([n.title for n in Note.where("body", None).get()], ["a"])
        self.assertEqual([n.title for n in Note.where("body", "=", None).get()], ["a"])
        self.assertEqual([n.title for n in Note.where("body", "!=", None).get()], ["b"])
        self.assertEqual([n.title for n in Note.query().where_null("body").get()], ["a"])
        self.assertEqual([n.title for n in Note.query().where_not_null("body").get()], ["b"])
        self.assertEqual(Note.where("title", "=", "a").count(), 1)
        self.assertEqual(Note.where("body", None).update(body="filled"), 1)
        with self.assertRaises(ValueError):
            Note.where("body", ">", None)


class TestClientTest(unittest.TestCase):
    def test_json_form_query_and_token(self):
        app = Application(tempfile.mkdtemp())
        app.post("/echo", lambda req: {"all": req.all(), "token": req.bearer_token()})
        client = TestClient(app)
        r = client.post("/echo", json={"a": 1}, query={"q": "x"})
        self.assertEqual(r.json()["all"], {"q": "x", "a": 1})
        r = client.with_token("T").post("/echo", data={"f": "v"})
        self.assertEqual((r.json()["all"], r.json()["token"]), ({"f": "v"}, "T"))
        self.assertTrue(r.ok)


class CliTest(unittest.TestCase):
    def test_new_project_validation(self):
        from pylara.cli import main
        d = tempfile.mkdtemp()
        with chdir(d):
            self.assertEqual(quiet(main, ["new", "../escape"])[0], 1)
            self.assertEqual(quiet(main, ["new", "bad name"])[0], 1)
            os.makedirs("full"); open("full/x", "w").close()
            self.assertEqual(quiet(main, ["new", "full"])[0], 1)
            self.assertEqual(quiet(main, ["new", "full", "--force"])[0], 0)
        self.assertEqual(quiet(main, ["--version"])[1].strip(), f"PyLara {__version__}")

    def test_generator_commands_and_name_safety(self):
        from pylara.console.console import Console
        d = tempfile.mkdtemp()
        with chdir(d):
            c = Console()
            self.assertEqual(quiet(c.run, ["make:controller", "PostController", "--resource"])[0], 0)
            self.assertTrue(os.path.isfile("app/controllers/post_controller.py"))
            self.assertEqual(quiet(c.run, ["make:model", "BlogPost", "-m"])[0], 0)
            self.assertTrue(os.path.isfile("app/models/blog_post.py"))
            self.assertEqual(len(os.listdir("database/migrations")), 1)
            self.assertIn('"blog_posts"', read("app/models/blog_post.py"))
            self.assertEqual(quiet(c.run, ["make:controller", "../evil"])[0], 1)
            self.assertEqual(quiet(c.run, ["make:controller", "PostController"])[0], 1)   # exists
            self.assertEqual(quiet(c.run, ["nope"])[0], 1)
            self.assertEqual(quiet(c.run, ["serve"])[0], 1)      # not inside a project
            for f in ("app/controllers/post_controller.py", "app/models/blog_post.py"):
                compile(read(f), f, "exec")                # generated code is valid Python


class GeneratedProjectIntegrationTest(unittest.TestCase):
    """Create a project with `pylara new`, then use it like a real user would."""

    def run_cmd(self, cwd, *args):
        env = dict(os.environ, PYTHONPATH=ROOT)
        env.pop("DB_DATABASE", None)
        return subprocess.run([sys.executable, *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=120)

    def test_new_project_migrates_serves_and_passes_its_own_tests(self):
        d = tempfile.mkdtemp()
        r = self.run_cmd(d, "-m", "pylara", "new", "shop")
        self.assertEqual(r.returncode, 0, r.stderr)
        project = os.path.join(d, "shop")
        for must_exist in (".env", "manage.py", "wsgi.py", "bootstrap/app.py", "routes/web.py",
                           "resources/views/welcome.html", "public/css/app.css", "tests/test_example.py"):
            self.assertTrue(os.path.exists(os.path.join(project, must_exist)), must_exist)
        env_text = read(os.path.join(project, ".env"))
        self.assertIn('APP_NAME="Shop"', env_text)
        self.assertNotIn("__", env_text)
        key = [l for l in env_text.splitlines() if l.startswith("APP_KEY=")][0].split("=", 1)[1]
        self.assertEqual(len(key), 64)                  # random key generated for the project
        self.assertEqual(read(os.path.join(project, ".env.example")).count("APP_KEY=\n"), 1)   # blank in the example
        self.assertEqual(read(os.path.join(project, "requirements.txt")).strip(), f"pylara>={__version__}")

        r = self.run_cmd(project, "-m", "manage", "migrate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(project, "storage", "database.sqlite")))
        r = self.run_cmd(project, "-m", "manage", "make:model", "Post", "-m")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.run_cmd(project, "-m", "manage", "migrate:status")
        self.assertEqual(r.stdout.count("Pending"), 1)
        self.assertEqual(r.stdout.count("Ran"), 1)
        r = self.run_cmd(project, "-m", "manage", "migrate:rollback")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.run_cmd(project, "-m", "manage", "route:list")
        self.assertIn("WelcomeController@index", r.stdout)
        r = self.run_cmd(project, "-W", "error", "-m", "unittest", "discover")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class ReferenceAppTest(unittest.TestCase):
    """examples/tracker is a full app (login, CSRF, forms, uploads); its own tests must pass."""

    def test_tracker_example_passes_its_tests(self):
        import shutil
        d = os.path.join(tempfile.mkdtemp(), "tracker")
        shutil.copytree(os.path.join(ROOT, "examples", "tracker"), d)
        env = dict(os.environ, PYTHONPATH=ROOT)
        for key in ("DB_DATABASE", "SESSION_DRIVER", "APP_KEY"):
            env.pop(key, None)
        r = subprocess.run([sys.executable, "-W", "error", "-m", "unittest", "discover"], cwd=d, env=env,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Ran 11 tests", r.stderr)


if __name__ == "__main__":
    unittest.main()
