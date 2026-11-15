# Configuration

PyLara has two configuration mechanisms: **environment variables** (`.env`) for things that
change between machines, and **JSON config files** in `config/` for everything else.

## Environment configuration

When the `Application` is created it loads `.env` from the project root (the `base_path`).

```dotenv
APP_NAME="Blog"
APP_ENV=local
APP_DEBUG=true
DB_DATABASE=storage/database.sqlite
```

Rules:

- Lines starting with `#` are comments. A value may be quoted (`"two words"`). An unquoted value
  may end with ` # comment`.
- **Real environment variables always win** over `.env`. `DB_DATABASE=:memory: python -m manage migrate`
  overrides the file.
- Never commit `.env`; commit `.env.example` instead. New projects already contain both, and
  `.env` is in `.gitignore`.

### Reading values

```python
app.env("APP_NAME", "PyLara")        # on the application
from pylara.support.helpers import env
env("APP_DEBUG", False)              # helper (uses the most recently created application)
```

`env()` converts the strings `true`, `false`, `null` and `empty` (also `(true)`, `(false)`,
`(null)`, `(empty)`) into `True`, `False`, `None` and `""`, like Laravel. Everything else is
returned as a string, so convert numbers yourself: `int(env("WORKERS", 2))`.

### Variables PyLara itself understands

| Variable | Used by | Meaning |
|---|---|---|
| `APP_DEBUG` | error handling | `true` shows tracebacks in the browser. **Must be `false` in production.** |
| `DB_DATABASE` | `bootstrap/app.py` (generated project) | SQLite file path, or `:memory:` |
| `APP_KEY` | [sessions](sessions.md) | secret that signs session cookies. Create it with `python -m manage key:generate`. |
| `SESSION_DRIVER` | sessions | `file` (default) or `memory` |
| `SESSION_LIFETIME` | sessions | minutes of inactivity before a session expires (default `120`) |
| `SESSION_SECURE` | sessions | `true` on HTTPS: the cookie is never sent over plain HTTP |
| `MAX_BODY_MB` | requests | largest accepted request body in megabytes (default `10`); larger requests get 413 |
| `APP_NAME`, `APP_ENV` | your code | Free to use. The welcome page shows `APP_NAME`. |

Add your own freely (`MAIL_HOST`, `STRIPE_KEY`, ...).

## Configuration files

Every `config/<file>.json` is loaded on demand and read with **dot notation**: the first segment
is the file name.

`config/app.json`
```json
{ "name": "Blog", "per_page": 15, "mail": { "host": "smtp.example.com" } }
```

```python
app.config.get("app.per_page")             # 15
app.config.get("app.mail.host")            # "smtp.example.com"
app.config.get("app.missing", "fallback")  # "fallback"
app.config.set("app.per_page", 25)         # runtime override (in memory only)

from pylara.support.helpers import config
config("app.name")
```

JSON files cannot read the environment. If a value depends on the machine, use `env()` in
`bootstrap/app.py` or a provider instead.

## Debug mode

With `APP_DEBUG=true` an unhandled exception renders a page with the traceback, and JSON requests
receive the exception message. With `APP_DEBUG=false` users only see a generic "Server Error".
**In both modes the traceback is printed to stderr**, so your server log always has it.

## Database configuration

The database connection is created in `bootstrap/app.py`; see [Database](database.md).
