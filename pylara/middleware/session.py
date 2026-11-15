"""
Session, CSRF and login middleware.

    app.group({"middleware": [SessionMiddleware, VerifyCsrfToken]}, lambda r: [...])
    app.get("/account", handler).with_middleware(RequireLogin)

SessionMiddleware must come BEFORE VerifyCsrfToken / RequireLogin.
"""

import fnmatch
import hmac

from pylara.http.exceptions import HttpException, UnauthorizedException
from pylara.http.response import RedirectResponse
from pylara.middleware.middleware import Middleware
from pylara.support.session import Session, new_id, sign, unsign


class SessionMiddleware(Middleware):
    """Loads request.session from the signed cookie and saves it after the response."""

    cookie_name = "pylara_session"

    def handle(self, request, next):
        from pylara.application import Application
        app = Application.get_instance()
        store, key = app.session_store(), app.app_key()

        session_id = unsign(request.cookie(self.cookie_name) or "", key)
        loaded = store.load(session_id) if session_id else None
        if loaded is None:
            session = Session(store, new_id(), None)
        else:
            session = Session(store, session_id, loaded["data"], loaded["touched"])
        request.set_attribute("session", session)

        try:
            response = next()
        except Exception:
            if session.needs_save() and session.id == session._original_id:
                store.save(session.id, session.payload())        # keep changes, cookie already exists
            raise

        if session.needs_save():
            store.save(session.id, session.payload())
            response.with_cookie(
                self.cookie_name, sign(session.id, key),
                max_age=store.lifetime,
                http_only=True,
                secure=bool(app.env("SESSION_SECURE", False)),
                same_site="Lax",
            )
        return response


class VerifyCsrfToken(Middleware):
    """
    Rejects POST/PUT/PATCH/DELETE requests that do not carry the session's CSRF token
    (HTTP 419). The token is read from the request BODY field `_token`, or from the
    X-CSRF-TOKEN / X-XSRF-TOKEN header.

    Skip paths (webhooks) by subclassing:  except_paths = ["/webhooks/*"]
    """

    except_paths: list = []
    safe_methods = ("GET", "HEAD", "OPTIONS")

    def handle(self, request, next):
        if request.method not in self.safe_methods and not self._is_excluded(request.path):
            sent = (request._parse_body().get("_token")
                    or request.header("X-CSRF-TOKEN")
                    or request.header("X-XSRF-TOKEN") or "")
            expected = request.session.token()
            if not hmac.compare_digest(str(sent), expected):
                raise HttpException(419, "CSRF token mismatch.")
        return next()

    def _is_excluded(self, path: str) -> bool:
        return any(fnmatch.fnmatch(path, pattern) for pattern in self.except_paths)


class RequireLogin(Middleware):
    """Lets only logged-in users through (a user id stored in the session)."""

    session_key = "user_id"
    login_url = "/login"

    def handle(self, request, next):
        if request.session.get(self.session_key) is None:
            if request.wants_json or request.is_json:
                raise UnauthorizedException()
            return RedirectResponse(self.login_url)
        return next()
