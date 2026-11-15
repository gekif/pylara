import os
import re
import shutil
import unittest

from pylara.database.migration import Migrator, discover
from pylara.orm.model import get_connection
from pylara.testing import TestClient

from bootstrap.app import BASE, app


def token_from(html):
    return re.search(r'name="_token" value="([^"]+)"', html).group(1)


class TrackerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Migrator(get_connection()).run(discover(os.path.join(BASE, "database", "migrations")))

    def setUp(self):
        db = get_connection()
        db.execute("DELETE FROM tasks")
        db.execute("DELETE FROM users")
        db.commit()
        shutil.rmtree(os.path.join(BASE, "storage", "uploads"), ignore_errors=True)
        self.client = TestClient(app)

    def form(self, path):
        return self.client.request("GET", path, headers={"Accept": "text/html"})

    def post(self, path, **kw):
        token = token_from(self.form("/login").text if "token" not in kw else "")
        data = dict(kw.pop("data", {}), _token=token)
        return self.client.request("POST", path, data=data, headers={"Accept": "text/html"}, **kw)

    def register(self, client=None, email="ana@example.com"):
        client = client or self.client
        token = token_from(client.request("GET", "/register", headers={"Accept": "text/html"}).text)
        return client.request("POST", "/register", headers={"Accept": "text/html"}, data={
            "_token": token, "name": "Ana", "email": email, "password": "secret123", "password_confirmation": "secret123"})

    def test_pages_require_login(self):
        r = self.form("/tasks")
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "/login"))

    def test_registration_validation_errors_are_shown_and_values_kept(self):
        token = token_from(self.form("/register").text)
        r = self.client.request("POST", "/register", headers={"Accept": "text/html"}, data={
            "_token": token, "name": "A", "email": "nope", "password": "short"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("must be at least 2 characters", r.text)
        self.assertIn('value="nope"', r.text)
        self.assertIn("valid email", r.text)

    def test_register_login_logout_flow(self):
        r = self.register()
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "/tasks"))
        page = self.form("/tasks")
        self.assertIn("Ana's tasks", page.text)
        self.assertIn("No tasks yet.", page.text)
        token = token_from(page.text)
        self.client.request("POST", "/logout", data={"_token": token}, headers={"Accept": "text/html"})
        self.assertEqual(self.form("/tasks").status_code, 302)
        r = self.client.request("POST", "/login", headers={"Accept": "text/html"},
                                data={"_token": token_from(self.form("/login").text),
                                      "email": "ana@example.com", "password": "wrong"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("Wrong email or password.", r.text)

    def test_duplicate_email_rejected(self):
        self.register()
        other = TestClient(app)
        r = self.register(other)
        self.assertEqual(r.status_code, 422)
        self.assertIn("already registered", r.text)

    def test_task_crud_with_flash_and_upload(self):
        self.register()
        token = token_from(self.form("/tasks").text)
        h = {"Accept": "text/html"}
        r = self.client.request("POST", "/tasks", headers=h, data={"_token": token, "title": "ab"})
        self.assertEqual(r.status_code, 422)
        self.assertIn("at least 3 characters", r.text)
        r = self.client.request("POST", "/tasks", headers=h, data={"_token": token, "title": "Write docs"},
                                files={"attachment": ("spec.pdf", b"%PDF-1.4 test", "application/pdf")})
        self.assertEqual(r.status_code, 302)
        page = self.form("/tasks").text
        self.assertIn("Task added.", page)                       # flash
        self.assertNotIn("Task added.", self.form("/tasks").text)  # ...only once
        self.assertIn("Write docs", page)
        self.assertEqual(len(os.listdir(os.path.join(BASE, "storage", "uploads"))), 1)
        r = self.client.request("POST", "/tasks", headers=h, data={"_token": token, "title": "Bad file"},
                                files={"attachment": ("x.exe", b"MZ", "application/octet-stream")})
        self.assertEqual(r.status_code, 422)
        self.assertIn("must be a file of type", r.text)
        task_id = re.search(r"/tasks/(\d+)/toggle", page).group(1)
        self.client.request("POST", f"/tasks/{task_id}/toggle", data={"_token": token}, headers=h)
        self.assertIn("[x]", self.form("/tasks").text)
        r = self.client.request("POST", f"/tasks/{task_id}", data={"_token": token, "_method": "DELETE"}, headers=h)
        self.assertEqual(r.status_code, 302)
        self.assertIn("No tasks yet.", self.form("/tasks").text)

    def test_users_cannot_touch_each_others_tasks_and_csrf_is_enforced(self):
        self.register()
        token = token_from(self.form("/tasks").text)
        self.client.request("POST", "/tasks", data={"_token": token, "title": "Private"}, headers={"Accept": "text/html"})
        task_id = re.search(r"/tasks/(\d+)/toggle", self.form("/tasks").text).group(1)

        mallory = TestClient(app)
        self.register(mallory, email="mallory@example.com")
        mtoken = token_from(mallory.request("GET", "/tasks", headers={"Accept": "text/html"}).text)
        r = mallory.request("POST", f"/tasks/{task_id}/toggle", data={"_token": mtoken}, headers={"Accept": "text/html"})
        self.assertEqual(r.status_code, 404)
        r = mallory.request("POST", f"/tasks/{task_id}", data={"_token": mtoken, "_method": "DELETE"}, headers={"Accept": "text/html"})
        self.assertEqual(r.status_code, 404)
        self.assertNotIn("Private", mallory.request("GET", "/tasks", headers={"Accept": "text/html"}).text)

        r = self.client.request("POST", f"/tasks/{task_id}/toggle", headers={"Accept": "text/html"})   # no token
        self.assertEqual(r.status_code, 419)

    def test_html_in_titles_is_escaped(self):
        self.register()
        token = token_from(self.form("/tasks").text)
        self.client.request("POST", "/tasks", data={"_token": token, "title": "<script>alert(1)</script>"},
                            headers={"Accept": "text/html"})
        page = self.form("/tasks").text
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
