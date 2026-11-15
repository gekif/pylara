import os

# Tests use a throw-away in-memory database. This must run before bootstrap is imported.
os.environ["DB_DATABASE"] = ":memory:"
os.environ["SESSION_DRIVER"] = "memory"
os.environ.setdefault("APP_KEY", "test-key-not-for-production")
