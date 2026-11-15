from pylara import Controller, Request
from pylara.http.exceptions import ValidationException
from pylara.support.hashing import Hash

from app.models.user import User


class AuthController(Controller):

    def register_form(self, request: Request):
        return self.view("auth.register", errors={}, old={})

    def register(self, request: Request):
        try:
            data = request.validate({"name": "required|min:2", "email": "required|email",
                                     "password": "required|min:8|confirmed"})
            if User.where("email", data["email"]).first():
                raise ValidationException({"email": ["That email is already registered."]})
        except ValidationException as exc:
            return self.view("auth.register", errors=exc.errors, old=request.only("name", "email"), status=422)
        user = User.create(name=data["name"], email=data["email"], password=Hash.make(data["password"]))
        request.session.regenerate()
        request.session.put("user_id", user.id)
        return self.redirect("/tasks")

    def login_form(self, request: Request):
        return self.view("auth.login", errors={}, old={})

    def login(self, request: Request):
        data = request.only("email", "password")
        user = User.where("email", data.get("email", "")).first()
        if user is None or not Hash.check(data.get("password", ""), user.password):
            return self.view("auth.login", errors={"email": ["Wrong email or password."]},
                             old={"email": data.get("email", "")}, status=422)
        request.session.regenerate()
        request.session.put("user_id", user.id)
        return self.redirect("/tasks")

    def logout(self, request: Request):
        request.session.invalidate()
        return self.redirect("/login")
