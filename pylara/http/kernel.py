"""
HttpKernel - sends a request through global middleware, the router, and the
exception handlers. Inspired by Illuminate.Foundation.Http.Kernel.
"""

import html
import sys
import traceback

from pylara.http import context
from pylara.http.exceptions import HttpException, ValidationException
from pylara.http.request import Request
from pylara.http.response import JsonResponse, Response


class HttpKernel:

    global_middleware = []   # class-level defaults; app.use() adds more

    def __init__(self, app):
        self.app = app

    def handle(self, request: Request) -> Response:
        context.set_request(request)
        try:
            return self._build_pipeline(request)()
        except Exception as exc:                      # noqa: BLE001 - kernel is the last line of defence
            return self._render_exception(request, exc)
        finally:
            context.clear_request()

    def _build_pipeline(self, request: Request):
        from pylara.routing.router import Router

        def final():
            return self.app.router.dispatch(request)

        handler = final
        stack = list(self.global_middleware) + list(getattr(self.app, "global_middleware", []))
        for mw in reversed(stack):
            instance = mw() if isinstance(mw, type) else mw

            def make_handler(middleware, nxt):
                def _h():
                    return Router._to_response(middleware.handle(request, nxt))
                return _h

            handler = make_handler(instance, handler)
        return handler

    # ── exceptions ──────────────────────────────────────────────────────────

    def _render_exception(self, request: Request, exc: Exception) -> Response:
        from pylara.routing.router import Router

        for exc_class, handler in getattr(self.app, "_exception_handlers", []):
            if isinstance(exc, exc_class):
                try:
                    result = handler(request, exc)
                except Exception as inner:            # noqa: BLE001
                    return self._server_error(request, inner)
                if result is None:                    # the handler declined: try the next / defaults
                    continue
                return Router._to_response(result)

        if isinstance(exc, HttpException):
            return self._http_error(request, exc)
        if isinstance(exc, ValidationException):
            return JsonResponse({"message": "Validation failed", "errors": exc.errors}, 422)
        return self._server_error(request, exc)

    def _http_error(self, request: Request, exc: HttpException) -> Response:
        if request.wants_json or request.is_json:
            return JsonResponse({"message": exc.message}, exc.status_code)
        body = f"<h1>{exc.status_code} {html.escape(exc.message)}</h1>"
        return Response(body, exc.status_code)

    def _server_error(self, request: Request, exc: Exception) -> Response:
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        debug = bool(self.app.env("APP_DEBUG", False))
        if request.wants_json or request.is_json:
            return JsonResponse({"message": str(exc) if debug else "Server Error"}, 500)
        if debug:
            detail = html.escape("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
            return Response(f"<h1>500 {html.escape(type(exc).__name__)}</h1><pre>{detail}</pre>", 500)
        return Response("<h1>500 Server Error</h1>", 500)
