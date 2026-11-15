# Contributing

Thank you for helping improve PyLara.

## Setup

```bash
git clone <your fork>
cd pylara
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/macOS: source .venv/bin/activate)
python -m pip install -e .
python -m tests
```

`python -m tests` runs both suites:

- `tests/test_framework.py` is the original script-style suite for the core (ORM, router, request,
  response, middleware, migrations, collections).
- `tests/test_features.py` is a `unittest` suite for 1.0 features, including integration tests that
  generate a project with `pylara new` and run it.

Run one file or test: `python -m unittest tests.test_features.RoutingTest -v`.

## Layout

```
pylara/
├── application.py        Application: container, env, static files, WSGI, dev server
├── cli.py / __main__.py  global `pylara` command (pylara new)
├── version.py            the only place the version is written
├── testing.py            TestClient
├── http/                 request, response, kernel (middleware + errors), controller, exceptions
├── routing/router.py     Route, Router
├── middleware/           Middleware base and built-ins
├── orm/model.py          QueryBuilder and Model
├── database/migration.py Blueprint, Schema, Migrator, discover
├── console/console.py    manage.py commands
├── support/              container, config, helpers/Collection, hashing, view engine, providers
└── stubs/project/        files copied by `pylara new` (*.stub; __UPPER__ tokens are replaced)
examples/demo/            a small users/posts/auth demo application
```

## Guidelines

- Keep PyLara **dependency-free** (standard library only).
- Every behaviour change needs a test, and the documentation in `docs/` must stay accurate: if you
  change an API, change its page.
- Be conservative with security: values are always SQL parameters, column names go through the
  identifier check, HTML output is escaped, static paths cannot leave `public/`.
- Run the suite with warnings as errors: `python -W error -m tests`.
- Files in `pylara/stubs/project` end with `.stub` so they are not treated as Python modules when
  the package is installed. New stub files are picked up automatically.

## Releasing

See [Publishing to PyPI](publishing.md).
