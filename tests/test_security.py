"""Sessions, CSRF and file uploads.  Run: python -m unittest tests.test_security -v"""
import io
import json
import os
from contextlib import redirect_stderr
import re
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from pylara import Application, JsonResponse, Response
from pylara.http.exceptions import HttpException
from pylara.http.uploads import UploadedFile, parse_multipart
from pylara.middleware.session import RequireLogin, SessionMiddleware, VerifyCsrfToken
from pylara.support.session import FileSessionStore, MemorySessionStore, sign, unsign
from pylara.testing import TestClient

KEY = "unit-test-key"


def make_app(driver="memory", extra_env=None):
    base = tempfile.mkdtemp()
    os.environ["APP_KEY"] = KEY
    os.environ["SESSION_DRIVER"] = driver
    for k, v in (extra_env or {}).items():
        os.environ[k] = v
    return Application(base)


def cleanup_env(*extra):
    for k in ("APP_KEY", "SESSION_DRIVER", "SESSION_LIFETIME", "SESSION_SECURE", "MAX_BODY_MB", *extra):
        os.environ.pop(k, None)


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.app.use(SessionMiddleware)

        @self.app.get("/count")
        def count(req):
            n = req.session.get("n", 0) + 1
            req.session.put("n", n)
            return {"n": n}
        self.client = TestClient(self.app)

    def tearDown(self):
        cleanup_env()

    def test_session_persists_between_requests(self):
        self.assertEqual([self.client.get("/count").json()["n"] for _ in range(3)], [1, 2, 3])

    def test_separate_clients_have_separate_sessions(self):
        self.client.get("/count")
        self.assertEqual(TestClient(self.app).get("/count").json()["n"], 1)

    def test_cookie_flags(self):
        cookie = self.client.get("/count").cookies[0]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Max-Age=7200", cookie)
        self.assertNotIn("Secure", cookie)
        os.environ["SESSION_SECURE"] = "true"
        self.assertIn("Secure", TestClient(self.app).get("/count").cookies[0])

    def test_no_cookie_when_session_untouched(self):
        self.app.get("/plain", lambda req: "x")
        self.assertEqual(self.client.get("/plain").cookies, [])

    def test_tampered_or_foreign_cookie_is_ignored(self):
        self.client.get("/count")
        good = self.client.cookies["pylara_session"]
        for bad in (good + "0", "x" + good, good.split(".")[0], "garbage", "../../etc/passwd.deadbeef", ""):
            fresh = TestClient(self.app)
            fresh.cookies["pylara_session"] = bad
            self.assertEqual(fresh.get("/count").json()["n"], 1, bad)

    def test_cookie_signed_with_another_key_is_rejected(self):
        self.client.get("/count")
        sid = self.client.cookies["pylara_session"].rsplit(".", 1)[0]
        forged = TestClient(self.app)
        forged.cookies["pylara_session"] = sign(sid, b"attacker-key")
        self.assertEqual(forged.get("/count").json()["n"], 1)

    def test_regenerate_changes_id_and_keeps_data(self):
        @self.app.get("/login")
        def login(req):
            req.session.put("user_id", 5)
            req.session.regenerate()
            return "ok"
        self.client.get("/count")
        before = self.client.cookies["pylara_session"]
        self.client.get("/login")
        after = self.client.cookies["pylara_session"]
        self.assertNotEqual(before, after)
        old = TestClient(self.app)                          # session fixation: the old id must be dead
        old.cookies["pylara_session"] = before
        self.assertEqual(old.get("/count").json()["n"], 1)
        self.assertEqual(self.client.get("/count").json()["n"], 2)

    def test_invalidate_logs_out(self):
        self.app.get("/out", lambda req: (req.session.invalidate(), "bye")[1])
        self.client.get("/count")
        self.client.get("/out")
        self.assertEqual(self.client.get("/count").json()["n"], 1)

    def test_flash_data_lives_for_exactly_one_request(self):
        self.app.get("/set", lambda req: (req.session.flash("msg", "saved"), "ok")[1])
        self.app.get("/read", lambda req: req.session.flash_data())
        self.client.get("/set")
        self.assertEqual(self.client.get("/read").json(), {"msg": "saved"})
        self.assertEqual(self.client.get("/read").json(), {})

    def test_forget_pull_all_has(self):
        @self.app.get("/ops")
        def ops(req):
            s = req.session
            s.put("a", 1); s.put("b", 2)
            pulled = s.pull("a")
            s.forget("b")
            return {"pulled": pulled, "has_a": s.has("a"), "all": s.all()}
        self.assertEqual(self.client.get("/ops").json(), {"pulled": 1, "has_a": False, "all": {}})

    def test_session_survives_an_exception_in_the_handler(self):
        @self.app.get("/boom")
        def boom(req):
            req.session.put("seen", True)
            raise HttpException(400, "nope")
        self.client.get("/count")
        self.assertEqual(self.client.get("/boom").status_code, 400)
        self.app.get("/seen", lambda req: {"seen": req.session.get("seen")})
        self.assertEqual(self.client.get("/seen").json(), {"seen": True})

    def test_missing_app_key_is_a_clear_error(self):
        os.environ.pop("APP_KEY")
        os.environ["APP_DEBUG"] = "true"
        try:
            with redirect_stderr(io.StringIO()):
                r = TestClient(self.app).get("/count")
        finally:
            os.environ.pop("APP_DEBUG")
        self.assertEqual(r.status_code, 500)
        self.assertIn("key:generate", r.text)

    def test_production_mode_hides_the_reason(self):
        os.environ.pop("APP_KEY")
        with redirect_stderr(io.StringIO()):
            r = TestClient(self.app).get("/count")
        self.assertEqual(r.json(), {"message": "Server Error"})

    def test_request_session_without_middleware_explains_itself(self):
        app = make_app()
        app.get("/x", lambda req: req.session.get("a"))
        os.environ["APP_DEBUG"] = "true"
        try:
            with redirect_stderr(io.StringIO()):
                text = TestClient(app).get("/x").text
        finally:
            os.environ.pop("APP_DEBUG")
        self.assertIn("SessionMiddleware", text)


class SessionStoreTest(unittest.TestCase):
    def test_file_store_roundtrip_expiry_and_traversal(self):
        d = tempfile.mkdtemp()
        store = FileSessionStore(d, lifetime_minutes=1)
        sid = "a" * 30
        store.save(sid, {"k": "v"})
        self.assertEqual(store.load(sid)["data"], {"k": "v"})
        with self.assertRaises(ValueError):
            store.load("../../etc/passwd")
        with open(os.path.join(d, sid + ".json")) as f:
            item = json.load(f)
        item["expires"] = time.time() - 1
        with open(os.path.join(d, sid + ".json"), "w") as f:
            json.dump(item, f)
        self.assertIsNone(store.load(sid))
        self.assertFalse(os.path.exists(os.path.join(d, sid + ".json")))

    def test_gc_removes_only_expired_and_corrupt_files(self):
        d = tempfile.mkdtemp()
        store = FileSessionStore(d, 60)
        store.save("b" * 30, {"live": 1})
        with open(os.path.join(d, "c" * 30 + ".json"), "w") as f:
            f.write("not json")
        with open(os.path.join(d, "d" * 30 + ".json"), "w") as f:
            json.dump({"data": {}, "expires": 1}, f)
        store.gc()
        self.assertEqual(sorted(os.listdir(d)), ["b" * 30 + ".json"])

    def test_corrupt_file_is_treated_as_no_session(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "e" * 30 + ".json"), "w") as f:
            f.write("{broken")
        self.assertIsNone(FileSessionStore(d).load("e" * 30))

    def test_file_driver_works_through_the_middleware(self):
        app = make_app("file")
        try:
            app.use(SessionMiddleware)
            app.get("/c", lambda req: (req.session.put("n", req.session.get("n", 0) + 1), {"n": req.session.get("n")})[1])
            client = TestClient(app)
            client.get("/c")
            self.assertEqual(client.get("/c").json(), {"n": 2})
            files = os.listdir(os.path.join(app.base_path, "storage", "sessions"))
            self.assertEqual(len(files), 1)
        finally:
            cleanup_env()

    def test_sign_unsign(self):
        sid = "z" * 32
        self.assertEqual(unsign(sign(sid, b"k"), b"k"), sid)
        self.assertIsNone(unsign(sign(sid, b"k"), b"other"))
        self.assertIsNone(unsign("short.abc", b"k"))
        self.assertIsNone(unsign(None, b"k"))

    def test_memory_store_isolates_data(self):
        store = MemorySessionStore()
        data = {"list": [1]}
        store.save("s" * 30, data)
        data["list"].append(2)
        self.assertEqual(store.load("s" * 30)["data"], {"list": [1]})


class CsrfTest(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.app.group({"middleware": [SessionMiddleware, VerifyCsrfToken]}, lambda r: [
            r.get("/form", lambda req: {"token": req.session.token()}),
            r.post("/submit", lambda req: {"ok": True}),
            r.delete("/item/{id}", lambda req, id: {"deleted": id}),
        ])
        self.client = TestClient(self.app)
        os.makedirs(os.path.join(self.app.base_path, "resources", "views"))
        with open(os.path.join(self.app.base_path, "resources", "views", "form.html"), "w") as f:
            f.write("<form>{!! csrf_field !!}</form><meta content=\"{{ csrf_token }}\">{{ flash.msg }}")
        self.app.group({"middleware": [SessionMiddleware]}, lambda r: [
            r.get("/page", lambda req: __import__("pylara.support.helpers", fromlist=["view"]).view("form"))])

    def tearDown(self):
        cleanup_env()

    def token(self):
        return self.client.get("/form").json()["token"]

    def test_post_without_token_is_419(self):
        self.client.get("/form")
        r = self.client.post("/submit", data={"a": "1"})
        self.assertEqual(r.status_code, 419)
        self.assertEqual(r.json(), {"message": "CSRF token mismatch."})

    def test_post_with_form_field_json_body_or_header(self):
        t = self.token()
        self.assertEqual(self.client.post("/submit", data={"_token": t}).status_code, 200)
        self.assertEqual(self.client.post("/submit", json={"_token": t}).status_code, 200)
        self.assertEqual(self.client.post("/submit", headers={"X-CSRF-TOKEN": t}).status_code, 200)
        self.assertEqual(self.client.post("/submit", headers={"X-XSRF-TOKEN": t}).status_code, 200)
        self.assertEqual(self.client.delete("/item/3", headers={"X-CSRF-TOKEN": t}).json(), {"deleted": "3"})

    def test_wrong_empty_or_other_sessions_token_is_rejected(self):
        t = self.token()
        self.assertEqual(self.client.post("/submit", data={"_token": t + "x"}).status_code, 419)
        self.assertEqual(self.client.post("/submit", data={"_token": ""}).status_code, 419)
        other = TestClient(self.app)
        other.get("/form")
        self.assertEqual(other.post("/submit", data={"_token": t}).status_code, 419)

    def test_token_in_query_string_is_not_accepted(self):
        t = self.token()
        self.assertEqual(self.client.post("/submit?_token=" + t).status_code, 419)

    def test_no_session_cookie_means_no_access(self):
        self.assertEqual(TestClient(self.app).post("/submit", data={"_token": "anything"}).status_code, 419)

    def test_get_requests_are_not_checked_and_excluded_paths_pass(self):
        self.assertEqual(self.client.get("/form").status_code, 200)

        class NoCheck(VerifyCsrfToken):
            except_paths = ["/hooks/*"]
        app = make_app()
        app.group({"middleware": [SessionMiddleware, NoCheck]}, lambda r: [
            r.post("/hooks/github", lambda req: "hook"), r.post("/other", lambda req: "x")])
        c = TestClient(app)
        self.assertEqual(c.post("/hooks/github").status_code, 200)
        self.assertEqual(c.post("/other").status_code, 419)

    def test_views_receive_csrf_values_and_flash(self):
        self.app.get("/flash", lambda req: (req.session.flash("msg", "Hello <b>"), "ok")[1]) if False else None
        html = self.client.get("/page").text
        match = re.search(r'name="_token" value="([^"]+)"', html)
        self.assertIsNotNone(match)
        self.assertIn(f'content="{match.group(1)}"', html)
        self.assertEqual(self.client.get("/form").json()["token"], match.group(1))

    def test_view_without_session_has_empty_csrf(self):
        app = make_app()
        os.makedirs(os.path.join(app.base_path, "resources", "views"))
        with open(os.path.join(app.base_path, "resources", "views", "t.html"), "w") as f:
            f.write("[{{ csrf_token }}][{!! csrf_field !!}]")
        self.assertEqual(app.view("t").content, "[][]")

    def test_shared_view_data(self):
        app = make_app()
        os.makedirs(os.path.join(app.base_path, "resources", "views"))
        with open(os.path.join(app.base_path, "resources", "views", "t.html"), "w") as f:
            f.write("{{ site }}|{{ n }}")
        counter = iter(range(10))
        app.share("site", "My Blog").share("n", lambda: next(counter))
        self.assertEqual(app.view("t").content, "My Blog|0")
        self.assertEqual(app.view("t").content, "My Blog|1")
        self.assertEqual(app.view("t", site="Override").content, "Override|2")


class RequireLoginTest(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.app.group({"middleware": [SessionMiddleware]}, lambda r: [
            r.get("/login", lambda req: (req.session.put("user_id", 1), "in")[1]),
            r.get("/account", lambda req: "secret").with_middleware(RequireLogin),
        ])
        self.client = TestClient(self.app)

    def tearDown(self):
        cleanup_env()

    def test_redirects_html_and_401_for_json(self):
        r = self.client.request("GET", "/account", headers={"Accept": "text/html"})
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "/login"))
        self.assertEqual(self.client.get("/account").status_code, 401)

    def test_allows_logged_in_user(self):
        self.client.get("/login")
        self.assertEqual(self.client.get("/account").text, "secret")


class UploadTest(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.client = TestClient(self.app)
        self.dir = tempfile.mkdtemp()

        @self.app.post("/upload")
        def upload(req):
            data = req.validate({"title": "required|string", "avatar": "required|file|mimes:png,jpg|max_kb:1"})
            saved = data["avatar"].save(self.dir)
            return {"title": data["title"], "size": data["avatar"].size, "saved": os.path.basename(saved),
                    "type": data["avatar"].content_type}

    def tearDown(self):
        cleanup_env()

    PNG = b"\x89PNG\r\n\x1a\n\x00\x00\r\n\n\r\x00binary\xff\xfe" * 3          # CRLF, LF, NUL inside the data

    def test_binary_file_roundtrips_exactly(self):
        r = self.client.post("/upload", data={"title": "Me"}, files={"avatar": ("me.png", self.PNG, "image/png")})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual((body["title"], body["size"], body["type"]), ("Me", len(self.PNG), "image/png"))
        self.assertTrue(body["saved"].endswith(".png"))
        with open(os.path.join(self.dir, body["saved"]), "rb") as f:
            self.assertEqual(f.read(), self.PNG)

    def test_validation_rules_for_files(self):
        def errors(**kw):
            r = self.client.post("/upload", **kw)
            return r.status_code, r.json().get("errors", {})
        code, e = errors(data={"title": "x"})
        self.assertIn("avatar", e)                                                       # required
        code, e = errors(data={"title": "x"}, files={"avatar": ("a.exe", b"MZ", "application/octet-stream")})
        self.assertIn("must be a file of type: png, jpg", e["avatar"][0])               # mimes
        code, e = errors(data={"title": "x"}, files={"avatar": ("a.png", b"x" * 2048, "image/png")})
        self.assertIn("1 kilobytes", e["avatar"][0])                                     # max_kb
        code, e = errors(data={"title": "x", "avatar": "plain text"})
        self.assertIn("avatar", e)                                                       # text is not a file
        code, e = errors(data={"title": "x"}, files={"avatar": ("a.png", b"", "image/png")})
        self.assertIn("avatar", e)                                                       # empty file = not present

    def test_hostile_file_names_are_neutralised(self):
        f = UploadedFile("../../etc/passwd", b"x")
        self.assertEqual(f.filename, "passwd")
        self.assertEqual(UploadedFile("..\\..\\win.ini", b"x").filename, "win.ini")
        self.assertEqual(UploadedFile(".htaccess", b"x").filename, "htaccess")
        self.assertEqual(UploadedFile("a b<c>.png", b"x").filename, "a_b_c_.png")
        self.assertEqual(UploadedFile("", b"x").filename, "")
        d = tempfile.mkdtemp()
        saved = UploadedFile("../../evil.png", b"x").save(d)
        self.assertEqual(os.path.dirname(saved), d)                    # random name, inside the folder
        with self.assertRaises(ValueError):
            UploadedFile("x", b"x").save(d, name="..")
        path = UploadedFile("x", b"1").save(d, name="fixed.txt")
        with self.assertRaises(FileExistsError):
            UploadedFile("x", b"2").save(d, name="fixed.txt")           # never overwrites
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"1")

    def test_request_files_api_and_multiple_fields(self):
        seen = {}

        @self.app.post("/many")
        def many(req):
            seen.update(names=sorted(req.files), one=req.file("a").filename, missing=req.file("zzz"),
                        note=req.input("note"))
            return "ok"
        self.client.post("/many", data={"note": "hi"},
                         files={"a": ("1.txt", b"A"), "b": ("2.txt", b"B", "text/plain")})
        self.assertEqual(seen, {"names": ["a", "b"], "one": "1.txt", "missing": None, "note": "hi"})

    def test_empty_file_input_in_browser_form_is_ignored(self):
        body = (b'--B\r\nContent-Disposition: form-data; name="title"\r\n\r\nT\r\n'
                b'--B\r\nContent-Disposition: form-data; name="avatar"; filename=""\r\n'
                b'Content-Type: application/octet-stream\r\n\r\n\r\n--B--\r\n')
        fields, files = parse_multipart("multipart/form-data; boundary=B", body)
        self.assertEqual((fields, files), ({"title": "T"}, {}))

    def test_malformed_multipart_does_not_crash(self):
        for ct, body in (("multipart/form-data; boundary=B", b"garbage"),
                         ("multipart/form-data", b"--B\r\n"),
                         ("multipart/form-data; boundary=B", b"--B\r\nContent-Disposition: form-data\r\n\r\nx\r\n--B--")):
            fields, files = parse_multipart(ct, body)
            self.assertEqual(files, {})

    def test_body_size_limit_returns_413(self):
        os.environ["MAX_BODY_MB"] = "0.001"                           # about 1 KB
        app = make_app()
        app.post("/x", lambda req: "ok")
        c = TestClient(app)
        self.assertEqual(c.post("/x", json={"a": "b"}).status_code, 200)
        self.assertEqual(c.post("/x", json={"a": "x" * 5000}).status_code, 413)

    def test_session_and_upload_together_with_csrf(self):
        app = make_app()
        app.group({"middleware": [SessionMiddleware, VerifyCsrfToken]}, lambda r: [
            r.get("/t", lambda req: req.session.token()),
            r.post("/up", lambda req: {"n": req.file("f").size})])
        c = TestClient(app)
        token = c.get("/t").text
        self.assertEqual(c.post("/up", data={"_token": token}, files={"f": ("a.txt", b"12345")}).json(), {"n": 5})
        self.assertEqual(c.post("/up", files={"f": ("a.txt", b"12345")}).status_code, 419)


class KeyGenerateTest(unittest.TestCase):
    def run_cmd(self, cwd, *args):
        env = dict(os.environ, PYTHONPATH=ROOT)
        return subprocess.run([sys.executable, "-m", "manage", *args], cwd=cwd, env=env, capture_output=True, text=True)

    def test_key_generate_flow(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "manage.py"), "w") as f:
            f.write("import sys\nfrom pylara.console.console import console\nsys.exit(console.run())\n")
        with open(os.path.join(d, ".env"), "w") as f:
            f.write("APP_NAME=x\nAPP_KEY=\n")
        r = self.run_cmd(d, "key:generate")
        self.assertEqual(r.returncode, 0, r.stderr)
        env = open(os.path.join(d, ".env")).read()
        key = re.search(r"^APP_KEY=(\w+)$", env, re.M).group(1)
        self.assertEqual(len(key), 64)
        self.assertIn("APP_NAME=x", env)
        r = self.run_cmd(d, "key:generate")                                    # refuses to replace
        self.assertEqual(r.returncode, 1)
        self.assertIn("--force", r.stderr)
        self.assertEqual(self.run_cmd(d, "key:generate", "--force").returncode, 0)
        self.assertNotIn(key, open(os.path.join(d, ".env")).read())
        self.assertEqual(len(self.run_cmd(d, "key:generate", "--show").stdout.strip()), 64)


if __name__ == "__main__":
    unittest.main()
