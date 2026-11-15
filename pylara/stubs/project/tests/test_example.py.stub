import os
import unittest

from pylara.database.migration import Migrator, discover
from pylara.orm.model import get_connection
from pylara.testing import TestClient

from bootstrap.app import BASE, app


class ExampleTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Migrator(get_connection()).run(discover(os.path.join(BASE, "database", "migrations")))
        cls.client = TestClient(app)

    def test_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("PyLara", response.text)

    def test_session_counts_visits(self):
        client = TestClient(app)                      # a fresh client has its own cookies
        client.get("/")
        self.assertIn("visits in this session: 2", client.get("/").text)

    def test_health_endpoint(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})

    def test_unknown_route_is_404(self):
        self.assertEqual(self.client.get("/does-not-exist").status_code, 404)


if __name__ == "__main__":
    unittest.main()
