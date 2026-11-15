from pylara.middleware.session import RequireLogin, SessionMiddleware, VerifyCsrfToken

from app.controllers.auth_controller import AuthController
from app.controllers.task_controller import TaskController
from app.controllers.welcome_controller import WelcomeController


def register(app):
    def pages(r):
        r.get("/", [WelcomeController, "index"]).named("home")
        r.get("/register", [AuthController, "register_form"])
        r.post("/register", [AuthController, "register"])
        r.get("/login", [AuthController, "login_form"])
        r.post("/login", [AuthController, "login"])
        r.post("/logout", [AuthController, "logout"])
        r.get("/tasks", [TaskController, "index"]).with_middleware(RequireLogin)
        r.post("/tasks", [TaskController, "store"]).with_middleware(RequireLogin)
        r.post("/tasks/{id}/toggle", [TaskController, "toggle"]).with_middleware(RequireLogin)
        r.delete("/tasks/{id}", [TaskController, "destroy"]).with_middleware(RequireLogin)

    app.group({"middleware": [SessionMiddleware, VerifyCsrfToken]}, pages)
