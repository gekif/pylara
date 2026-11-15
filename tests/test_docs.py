"""Keep the documentation honest: links resolve and documented behaviour is real.
Run: python -m unittest tests.test_docs -v"""
import os
import re
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
DOCS = os.path.join(ROOT, "docs")

from pylara import Application, Controller, JsonResponse, Model
from pylara.orm.model import set_connection
from pylara.testing import TestClient


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def slug(heading: str) -> str:
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s", "-", text)


def anchors(path):
    found = set()
    in_code = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("```"):
                in_code = not in_code
            elif not in_code and line.startswith("#"):
                found.add(slug(line.lstrip("#")))
    return found


class DocLinksTest(unittest.TestCase):
    def test_every_page_is_listed_in_the_index(self):
        index = read(os.path.join(DOCS, "index.md"))
        for name in os.listdir(DOCS):
            if name.endswith(".md") and name != "index.md":
                self.assertIn(f"({name})", index, f"{name} missing from docs/index.md")

    def test_relative_links_and_anchors_resolve(self):
        problems = []
        for name in sorted(os.listdir(DOCS)):
            if not name.endswith(".md"):
                continue
            text = read(os.path.join(DOCS, name))
            text = re.sub(r"```.*?```", "", text, flags=re.S)
            for target in re.findall(r"\]\(([^)\s]+)\)", text):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                page, _, anchor = target.partition("#")
                path = os.path.join(DOCS, page) if page else os.path.join(DOCS, name)
                if not os.path.isfile(path):
                    problems.append(f"{name}: missing file {target}")
                elif anchor and anchor not in anchors(path):
                    problems.append(f"{name}: missing anchor {target}")
        self.assertEqual(problems, [])

    def test_python_code_blocks_are_valid_syntax(self):
        """Every ```python block must compile, as a module or as the body of a function.
        Method-chain fragments that start with '.' are skipped; '...' stands for omitted code."""
        import textwrap
        bad = []
        for name in sorted(os.listdir(DOCS)):
            if not name.endswith(".md"):
                continue
            text = read(os.path.join(DOCS, name))
            for i, block in enumerate(re.findall(r"```python\n(.*?)```", text, flags=re.S)):
                code = block.replace("...", "None")
                first = next((l.strip() for l in code.splitlines() if l.strip() and not l.strip().startswith("#")), "")
                if first.startswith("."):
                    continue
                try:
                    compile(code, f"{name}#{i}", "exec")
                    continue
                except SyntaxError:
                    pass
                try:
                    compile("def _f():\n" + textwrap.indent(textwrap.dedent(code), "    "), f"{name}#{i}", "exec")
                except SyntaxError as exc:
                    bad.append(f"{name} block {i}: {exc.msg} (line {exc.lineno}): {block.strip().splitlines()[0][:60]}")
        self.assertEqual(bad, [], "\n".join(bad))


class DocumentedBehaviourTest(unittest.TestCase):
    def setUp(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript("""
            CREATE TABLE blog_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, views INTEGER,
                deleted_at TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE comments (id INTEGER PRIMARY KEY AUTOINCREMENT, blogpost_id INTEGER, body TEXT,
                created_at TEXT, updated_at TEXT);
        """)
        set_connection("default", conn)
        self.app = Application(tempfile.mkdtemp())
        self.client = TestClient(self.app)

    def test_table_derivation_and_relationship_default_keys(self):
        class Comment(Model):
            fillable = ["blogpost_id", "body"]

        class BlogPost(Model):
            fillable = ["title", "views"]
            soft_deletes = True

            def comments(self):
                return self.has_many(Comment)
        self.assertEqual(BlogPost.table, "blog_posts")
        self.assertEqual(Comment.table, "comments")
        post = BlogPost.create(title="t", views=1)
        Comment.create(blogpost_id=post.id, body="c")
        self.assertEqual(len(post.comments()), 1)       # key is lower-cased class name + _id

    def test_soft_delete_flow_from_orm_doc(self):
        class BlogPost(Model):
            fillable = ["title"]
            soft_deletes = True
        post = BlogPost.create(title="x")
        post.delete()
        self.assertEqual(BlogPost.all(), [])
        self.assertEqual(len(BlogPost.query().with_trashed().get()), 1)
        post.restore()
        self.assertEqual(len(BlogPost.all()), 1)

    def test_pagination_keys_and_mass_update(self):
        class BlogPost(Model):
            fillable = ["title", "views"]
        for i in range(25):
            BlogPost.create(title=f"p{i}", views=i)
        page = BlogPost.query().order_by("id", "DESC").paginate(per_page=10, page=3)
        self.assertEqual((page["total"], page["per_page"], page["current_page"], page["last_page"]), (25, 10, 3, 3))
        self.assertEqual(len(page["data"]), 5)
        self.assertEqual(BlogPost.where("views", "<", 5).update(views=0), 5)
        self.assertEqual(BlogPost.where("views", "<", 3).delete(), 5)

    def test_hidden_casts_and_where_in_n_plus_one_example(self):
        class BlogPost(Model):
            fillable = ["title", "views"]
            hidden = ["views"]
            casts = {"views": float}
        a = BlogPost.create(title="a", views="2")
        self.assertEqual(BlogPost.find(a.id).views, 2.0)
        self.assertNotIn("views", a.to_dict())
        found = BlogPost.query().where_in("id", [a.id]).get()
        self.assertEqual(len(found), 1)

    def test_testclient_header_helpers_from_testing_doc(self):
        self.app.get("/h", lambda req: {"c": req.header("X-Custom"), "t": req.bearer_token()})
        r = self.client.with_headers(X_Custom="1").with_token("tok").get("/h")
        self.assertEqual(r.json(), {"c": "1", "t": "tok"})

    def test_view_status_keyword_and_form_errors_example(self):
        from pylara.http.exceptions import ValidationException
        base = self.app.base_path
        os.makedirs(os.path.join(base, "resources", "views", "tasks"))
        with open(os.path.join(base, "resources", "views", "tasks", "create.html"), "w") as f:
            f.write('<input value="{{ old.title }}">{% for m in errors.title %}<p>{{ m }}</p>{% endfor %}')

        class C(Controller):
            def store(self, request):
                try:
                    request.validate({"title": "required|min:3"})
                except ValidationException as exc:
                    return self.view("tasks.create", errors=exc.errors, old=request.all(), status=422)
                return self.redirect("/tasks")
        self.app.post("/tasks", [C, "store"])
        r = self.client.post("/tasks", data={"title": "ab"})
        self.assertEqual(r.status_code, 422)
        self.assertIn('value="ab"', r.text)
        self.assertIn("at least 3 characters", r.text)
        self.assertEqual(self.client.post("/tasks", data={"title": "abc"}).status_code, 302)

    def test_catch_all_exception_handler_order_from_errors_doc(self):
        from pylara.http.exceptions import HttpException, NotFoundException

        @self.app.exception_handler(NotFoundException)
        def specific(request, exc):
            return JsonResponse({"message": "custom 404"}, 404)

        @self.app.exception_handler(Exception)
        def general(request, exc):
            if isinstance(exc, HttpException):
                return JsonResponse({"message": exc.message}, exc.status_code)
            return JsonResponse({"message": "Server Error"}, 500)

        @self.app.get("/teapot")
        def teapot(req):
            raise HttpException(418, "short and stout")

        @self.app.get("/boom")
        def boom(req):
            raise RuntimeError("x")
        self.assertEqual(self.client.get("/nowhere").json(), {"message": "custom 404"})
        self.assertEqual(self.client.get("/teapot").json(), {"message": "short and stout"})
        self.assertEqual(self.client.get("/boom").status_code, 500)

    def test_helpers_and_collection_table(self):
        from pylara.support.helpers import collect, str_slug, str_snake, str_camel, str_pascal
        self.assertEqual(str_slug("Hello World!"), "hello-world")
        self.assertEqual(str_snake("BlogPost"), "blog_post")
        self.assertEqual((str_camel("blog_post"), str_pascal("blog_post")), ("blogPost", "BlogPost"))
        c = collect([{"n": 1, "r": "a"}, {"n": 3, "r": "b"}, {"n": 3, "r": "a"}])
        self.assertEqual((c.sum("n"), c.min("n"), c.max("n")), (7, 1, 3))
        self.assertEqual(c.pluck("r").unique().all(), ["a", "b"])
        self.assertEqual(len(c.chunk(2)), 2)
        self.assertTrue(c.contains("r", "b"))
        self.assertEqual(c.sort_by("n", reverse=True).first()["n"], 3)
        self.assertEqual(list(c.group_by("r")), ["a", "b"])

    def test_container_class_binding_and_route_helper(self):
        class Mailer:
            pass
        self.app.singleton(Mailer, lambda app: Mailer())
        self.assertIs(self.app.make("Mailer"), self.app.make(Mailer))
        self.app.get("/u/{id}", lambda req, id: id).named("u.show")
        from pylara.support.helpers import route
        self.assertEqual(route("u.show", id=7), "/u/7")


if __name__ == "__main__":
    unittest.main()
