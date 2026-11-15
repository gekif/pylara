"""
Controller - Base controller class.
Inspired by Laravel's Illuminate.Routing.Controller.
"""

from pylara.http.response import Response, JsonResponse, RedirectResponse, redirect, abort


class Controller:
    """
    Base controller. All application controllers should extend this.
    Provides convenience helpers for common response patterns.
    """

    def response(self, content: str = "", status: int = 200) -> Response:
        return Response(content, status)

    def json(self, data, status: int = 200) -> JsonResponse:
        return JsonResponse(data, status)

    def view(self, name: str, data: dict = None, status: int = 200, **context) -> Response:
        from pylara.application import Application
        return Application.get_instance().view(name, data, status, **context)

    def redirect(self, url: str, status: int = 302) -> RedirectResponse:
        return redirect(url, status)

    def abort(self, status_code: int, message: str = ""):
        abort(status_code, message)

    def not_found(self, message: str = "Not Found"):
        abort(404, message)

    def unauthorized(self, message: str = "Unauthorized"):
        abort(401, message)
