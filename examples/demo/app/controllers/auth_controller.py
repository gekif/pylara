import secrets

from pylara import Controller, Request
from pylara.support.hashing import Hash
from app.models.user import User

# Penyimpanan token di memori: cukup untuk demo.
# Untuk produksi, simpan di database atau Redis (dengan masa berlaku).
_tokens: dict = {}


def _bearer(request: Request) -> str:
    return request.headers.get("Authorization", "").replace("Bearer ", "", 1)


class AuthController(Controller):

    def register(self, request: Request):
        data = request.validate({
            "name": "required|string|max:255",
            "email": "required|email",
            "password": "required|min:6",
        })
        if User.where("email", data["email"]).first():
            return self.json({"message": "Email sudah dipakai."}, 422)

        user = User.create(name=data["name"], email=data["email"], password=Hash.make(data["password"]))
        token = secrets.token_hex(32)
        _tokens[token] = user.id
        return self.json({"token": token, "user": user.to_dict()}, 201)

    def login(self, request: Request):
        data = request.validate({"email": "required|email", "password": "required"})
        user = User.where("email", data["email"]).first()
        if not user or not Hash.check(data["password"], user._attributes.get("password", "")):
            return self.json({"message": "Email atau password salah."}, 401)

        token = secrets.token_hex(32)
        _tokens[token] = user.id
        return self.json({"token": token, "user": user.to_dict()})

    def me(self, request: Request):
        return self.json(request.attribute("user").to_dict())

    def logout(self, request: Request):
        _tokens.pop(_bearer(request), None)
        return self.json({"message": "Berhasil keluar."})


class TokenAuthMiddleware:
    """Wajib login: validasi Bearer token dan pasang user ke request."""

    def handle(self, request, next):
        user_id = _tokens.get(_bearer(request))
        user = User.find(user_id) if user_id else None
        if user is None:
            from pylara.http.exceptions import UnauthorizedException
            raise UnauthorizedException("Silakan login terlebih dahulu.")
        request.set_attribute("user", user)
        return next()
