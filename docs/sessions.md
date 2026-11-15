# Sessions

HTTP is stateless; a **session** lets you remember a visitor between requests: who is logged in, a
shopping cart, a flash message after a redirect.

## How it works

The browser receives a cookie (`pylara_session`) containing a random **session id signed with
`APP_KEY`** (HMAC-SHA256). The data itself is stored on the server, in `storage/sessions/` (one JSON
file per session). A cookie that is missing, altered, or signed with another key is simply ignored and
the visitor gets a new, empty session. The cookie is `HttpOnly` and `SameSite=Lax`.

## Setup

New projects are ready: `.env` contains an `APP_KEY` and `routes/web.py` enables sessions for the web
routes. To enable them yourself:

```python
from pylara.middleware.session import SessionMiddleware

app.group({"middleware": [SessionMiddleware]}, lambda r: [
    r.get("/cart", [CartController, "show"]),
])
```

`SessionMiddleware` must come **before** `VerifyCsrfToken` and `RequireLogin` in the list.
If `APP_KEY` is missing the request fails with a message telling you to run:

```bash
python -m manage key:generate          # writes APP_KEY to .env
python -m manage key:generate --force  # replace it (logs everyone out)
python -m manage key:generate --show   # only print a key
```

Keep `APP_KEY` secret and **different in every environment**. Anyone who knows it can forge session
cookies.

### Settings (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `APP_KEY` | none (required) | secret used to sign the cookie |
| `SESSION_DRIVER` | `file` | `file` (`storage/sessions/`) or `memory` (one process, lost on restart; for tests) |
| `SESSION_LIFETIME` | `120` | minutes of inactivity before a session expires |
| `SESSION_SECURE` | `false` | set `true` when serving over HTTPS so the cookie is never sent over plain HTTP |

## Using the session

```python
def add(self, request):
    session = request.session

    session.put("cart", [1, 2, 3])          # store
    session.get("cart", [])                 # read, with default
    session.has("cart")                     # True / False
    session.pull("cart")                    # read and remove
    session.forget("cart")                  # remove
    session.all()                           # everything (without internal keys)
    session.id                              # the session id (do not show it to users)
```

Values must be **JSON-serialisable** (numbers, strings, booleans, lists, dicts). Store ids, not model
objects.

### Flash data

Data that survives **exactly one more request**, typically a message after a redirect:

```python
def store(self, request):
    ...
    request.session.flash("status", "Post saved!")
    return self.redirect("/posts")
```

On the next request it is available in templates as `flash`:

```html
{% if flash.status %}<div class="alert">{{ flash.status }}</div>{% endif %}
```

or in code with `request.session.flash_data()`. After that request it is gone.

## Logging users in

PyLara does not impose an authentication system. A session-based login is a few lines:

```python
from pylara import Controller
from pylara.support.hashing import Hash
from pylara.http.exceptions import ValidationException
from app.models.user import User


class AuthController(Controller):

    def login_form(self, request):
        return self.view("auth.login")

    def login(self, request):
        data = request.validate({"email": "required|email", "password": "required"})
        user = User.where("email", data["email"]).first()
        if user is None or not Hash.check(data["password"], user.password):
            request.session.flash("error", "Wrong email or password.")
            return self.redirect("/login")

        request.session.regenerate()                 # always, to prevent session fixation
        request.session.put("user_id", user.id)
        return self.redirect("/dashboard")

    def logout(self, request):
        request.session.invalidate()                 # forget everything, new session id
        return self.redirect("/")
```

Protect pages with `RequireLogin` (it checks for `user_id` in the session):

```python
from pylara.middleware.session import SessionMiddleware, VerifyCsrfToken, RequireLogin

app.group({"middleware": [SessionMiddleware, VerifyCsrfToken]}, lambda r: [
    r.get("/login", [AuthController, "login_form"]),
    r.post("/login", [AuthController, "login"]),
    r.post("/logout", [AuthController, "logout"]),
    r.get("/dashboard", [DashboardController, "index"]).with_middleware(RequireLogin),
])
```

Visitors who are not logged in are redirected to `/login`; JSON clients get a 401. Customise it:

```python
class Authenticated(RequireLogin):
    login_url = "/signin"
    session_key = "account_id"
```

To get the current user, load it from the id:

```python
user = User.find(request.session.get("user_id"))
```

Reminders: store passwords with `Hash.make()` ([Helpers](helpers.md#hashing-passwords)), call
`regenerate()` on login, `invalidate()` on logout.

## Things to know

- **Session files are shared by all worker processes on one machine**, so gunicorn with several workers
  works. Servers on **different machines** need shared storage (a network folder) or a custom store.
- Two requests of the same visitor running at the same time can overwrite each other's changes (the last
  write wins). Keep session data small and rarely written.
- Sessions that are never modified are not even sent a cookie, so static pages and APIs stay cookie-free.
  An unchanged session has its expiry refreshed at most once a minute.
- Expired files are cleaned up automatically from time to time.
- If a handler raises an error after changing the session, the changes are still saved.
- Changing `APP_KEY` invalidates every existing session.

## Testing

`TestClient` keeps cookies between requests, so a client behaves like one browser. See
[Testing](testing.md#cookies-and-sessions).
