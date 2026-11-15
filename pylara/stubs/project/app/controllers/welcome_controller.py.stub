from pylara import Controller, Request, __version__
from pylara.support.helpers import env


class WelcomeController(Controller):

    def index(self, request: Request):
        visits = request.session.get("visits", 0) + 1       # a tiny session demo
        request.session.put("visits", visits)
        return self.view("welcome", app_name=env("APP_NAME", "PyLara"), version=__version__, visits=visits)
