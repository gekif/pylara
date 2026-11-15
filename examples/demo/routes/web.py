"""
routes/web.py - Definisi route aplikasi demo.
Setara routes/web.php + routes/api.php di Laravel.
"""

from pylara import Application, Response
from pylara.middleware.middleware import CorsMiddleware
from app.controllers.auth_controller import AuthController, TokenAuthMiddleware
from app.controllers.post_controller import PostController
from app.controllers.user_controller import UserController
from app.models.user import User

WELCOME = """<!DOCTYPE html>
<html lang="id"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PyLara</title>
<style>
  body{font-family:system-ui,sans-serif;background:#0f0f0f;color:#e5e5e5;display:flex;
       align-items:center;justify-content:center;min-height:100vh;margin:0}
  .card{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:16px;padding:40px;
        max-width:560px;width:90%;text-align:center}
  h1{color:#63ffb4;margin:8px 0}
  p{color:#999}
  code{background:#111;padding:2px 8px;border-radius:6px}
</style></head>
<body><div class="card">
  <div style="font-size:3rem">&#128013;</div>
  <h1>PyLara</h1>
  <p>Framework Python bergaya Laravel. Server berjalan.</p>
  <p>Coba <code>GET /api/health</code></p>
</div></body></html>"""


def register_routes(app: Application):

    @app.get("/")
    def welcome(request):
        return Response(WELCOME)

    # ── Publik: auth ─────────────────────────────────────────────────────────
    app.group({"prefix": "/api/auth"}, lambda r: [
        r.post("/register", [AuthController, "register"]),
        r.post("/login", [AuthController, "login"]),
    ])

    # ── Wajib login ──────────────────────────────────────────────────────────
    app.group({"prefix": "/api/auth", "middleware": [TokenAuthMiddleware]}, lambda r: [
        r.get("/me", [AuthController, "me"]),
        r.post("/logout", [AuthController, "logout"]),
    ])

    # ── API publik (read-only + CORS) ────────────────────────────────────────
    # Catatan: route statis (/users/search) harus didaftarkan SEBELUM
    # resource, kalau tidak "search" akan dianggap sebagai {id}.
    app.group({"prefix": "/api", "middleware": [CorsMiddleware]}, lambda r: [
        r.get("/health", lambda req: {"status": "ok", "framework": "PyLara"}),
        r.get("/users/search", lambda req: [
            u.to_dict() for u in User.where("name", "LIKE", f"%{req.query('q', '')}%").get()
        ]),
        r.resource("users", UserController),
        r.resource("posts", PostController),
    ])
