from pylara.middleware.middleware import CorsMiddleware

from app.models.user import User


def register(app):
    app.group({"prefix": "/api", "middleware": [CorsMiddleware]}, lambda r: [
        r.get("/health", lambda request: {"status": "ok"}),
        r.get("/users", lambda request: [u.to_dict() for u in User.all()]),
    ])
