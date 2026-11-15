"""
Router - URL routing engine.
Inspired by Illuminate.Routing.Router.

Supports verbs (get/post/put/patch/delete/any/match), decorators, named routes,
required and optional parameters, groups (prefix + middleware), resource
routes, and per-route middleware.
"""

import inspect
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

from pylara.http.exceptions import HttpException, NotFoundException
from pylara.http.request import Request
from pylara.http.response import JsonResponse, Response


class Route:
    """A single registered route."""

    def __init__(self, methods, uri, action, name=None, middleware=None, router=None):
        self.methods = [m.upper() for m in methods]
        self.uri = uri
        self.action = action
        self.name = name
        self.middleware: List = list(middleware or [])
        self._router = router
        self._pattern, self._param_names = self._compile(uri)

    @staticmethod
    def _compile(uri: str) -> Tuple["re.Pattern", List[str]]:
        names: List[str] = []
        out = []
        for part in re.split(r"(/\{\w+\?\}|\{\w+\})", uri):
            optional = re.fullmatch(r"/\{(\w+)\?\}", part)
            required = re.fullmatch(r"\{(\w+)\}", part)
            if optional:
                names.append(optional.group(1))
                out.append(f"(?:/(?P<{optional.group(1)}>[^/]+))?")
            elif required:
                names.append(required.group(1))
                out.append(f"(?P<{required.group(1)}>[^/]+)")
            else:
                out.append(re.escape(part))
        return re.compile("^" + "".join(out) + "$"), names

    def matches(self, method: str, path: str) -> Optional[Dict[str, str]]:
        if method.upper() not in self.methods:
            return None
        m = self._pattern.match(path)
        if not m:
            return None
        return {k: v for k, v in m.groupdict().items() if v is not None}

    def url(self, **params) -> str:
        uri = self.uri
        for key, value in params.items():
            encoded = quote(str(value), safe="")
            uri = uri.replace("{%s?}" % key, encoded).replace("{%s}" % key, encoded)
        uri = re.sub(r"/\{\w+\?\}", "", uri)
        missing = re.findall(r"\{(\w+)\}", uri)
        if missing:
            raise ValueError(f"Missing route parameter(s): {', '.join(missing)}")
        return uri or "/"

    # fluent API ------------------------------------------------------------

    def named(self, name: str) -> "Route":
        """Give the route a name: app.get("/x", h).named("x.show")"""
        self.name = name
        if self._router is not None:
            self._router._named[name] = self
        return self

    def with_middleware(self, *middleware) -> "Route":
        """Attach middleware (classes or instances) to this route only."""
        self.middleware.extend(middleware)
        return self

    def middleware_stack(self) -> List:
        return self.middleware


class RouteGroup:
    def __init__(self, prefix: str = "", middleware: List = None):
        self.prefix = prefix
        self.middleware = middleware or []


class Router:
    """
        router.get("/users/{id}", [UserController, "show"])
        router.resource("articles", ArticleController)
    """

    def __init__(self, app):
        self.app = app
        self._routes: List[Route] = []
        self._named: Dict[str, Route] = {}
        self._group_stack: List[RouteGroup] = []
        self.current_route: Optional[Route] = None

    # ── Verbs (direct call or decorator) ────────────────────────────────────

    def _register(self, methods, uri, action):
        if action is None:
            def decorator(fn):
                self._add_route(methods, uri, fn)
                return fn
            return decorator
        return self._add_route(methods, uri, action)

    def get(self, uri: str, action=None):
        return self._register(["GET", "HEAD"], uri, action)

    def post(self, uri: str, action=None):
        return self._register(["POST"], uri, action)

    def put(self, uri: str, action=None):
        return self._register(["PUT"], uri, action)

    def patch(self, uri: str, action=None):
        return self._register(["PATCH"], uri, action)

    def delete(self, uri: str, action=None):
        return self._register(["DELETE"], uri, action)

    def any(self, uri: str, action=None):
        return self._register(["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"], uri, action)

    def match(self, methods: List[str], uri: str, action=None):
        return self._register(methods, uri, action)

    # ── Groups ──────────────────────────────────────────────────────────────

    def group(self, attributes: dict, callback: Callable):
        """Group routes under a shared `prefix` and/or `middleware`."""
        group = RouteGroup(
            prefix=attributes.get("prefix", ""),
            middleware=self._listify(attributes.get("middleware", [])),
        )
        self._group_stack.append(group)
        try:
            callback(self)
        finally:
            self._group_stack.pop()

    # ── Resource ────────────────────────────────────────────────────────────

    def resource(self, name: str, controller_class, only: List[str] = None, except_: List[str] = None):
        """
        Register RESTful routes. Only methods that exist on the controller are routed.

        index    GET    /name
        create   GET    /name/create
        store    POST   /name
        show     GET    /name/{id}
        edit     GET    /name/{id}/edit
        update   PUT|PATCH /name/{id}
        destroy  DELETE /name/{id}
        """
        table = [
            ("GET", f"/{name}", "index"),
            ("GET", f"/{name}/create", "create"),
            ("POST", f"/{name}", "store"),
            ("GET", f"/{name}/{{id}}", "show"),
            ("GET", f"/{name}/{{id}}/edit", "edit"),
            ("PUT", f"/{name}/{{id}}", "update"),
            ("PATCH", f"/{name}/{{id}}", "update"),
            ("DELETE", f"/{name}/{{id}}", "destroy"),
        ]
        for method, uri, action_name in table:
            if only and action_name not in only:
                continue
            if except_ and action_name in except_:
                continue
            if not hasattr(controller_class, action_name):
                continue
            route = self._add_route([method], uri, [controller_class, action_name])
            if method != "PATCH":                     # PUT owns the name
                route.named(f"{name}.{action_name}")

    # ── Naming / URL generation ─────────────────────────────────────────────

    def name(self, route: Route, name: str) -> Route:
        return route.named(name)

    def route(self, name: str, **params) -> str:
        """Generate the URL for a named route."""
        if name not in self._named:
            raise KeyError(f"Route '{name}' not found.")
        return self._named[name].url(**params)

    # ── Dispatch ────────────────────────────────────────────────────────────

    def dispatch(self, request: Request) -> Response:
        path = request.path.rstrip("/") or "/"
        method = request.method

        if method == "POST":                          # HTML-form method spoofing
            override = str(request.input("_method", "")).upper()
            if override in ("PUT", "PATCH", "DELETE"):
                method = override

        allowed = set()
        for route in self._routes:
            params = route.matches(method, path)
            if params is not None:
                request.route_params = params
                self.current_route = route
                return self._run_route(route, request)
            if route._pattern.match(path):
                allowed.update(route.methods)

        if allowed:
            raise HttpException(405, f"Method {method} not allowed.")
        raise NotFoundException(f"No route found for [{method}] {path}")

    def _run_route(self, route: Route, request: Request) -> Response:
        def final():
            return self._to_response(self._call_action(route.action, request))

        handler = final
        for mw in reversed(route.middleware_stack()):
            instance = mw() if isinstance(mw, type) else mw

            def make_handler(middleware, nxt):
                def _h():
                    return self._to_response(middleware.handle(request, nxt))
                return _h

            handler = make_handler(instance, handler)

        return handler()

    def _call_action(self, action, request: Request):
        """Run a route action: [Controller, "method"] or any callable(request, *params)."""
        if isinstance(action, (list, tuple)) and len(action) == 2:
            controller_class, method_name = action
            controller = self.app.build(controller_class)
            method = getattr(controller, method_name)
            names = [p for p in inspect.signature(method).parameters]
            args = [request] + [request.route_params[p] for p in names[1:] if p in request.route_params]
            return method(*args)

        if callable(action):
            names = list(inspect.signature(action).parameters)
            args = [request] + [request.route_params[p] for p in names[1:] if p in request.route_params]
            return action(*args)

        raise ValueError(f"Invalid route action: {action!r}")

    @staticmethod
    def _to_response(result) -> Response:
        if isinstance(result, Response):
            return result
        if isinstance(result, (dict, list)):
            return JsonResponse(result)
        return Response("" if result is None else str(result))

    # ── Internals ───────────────────────────────────────────────────────────

    def _add_route(self, methods: List[str], uri: str, action) -> Route:
        full = self._prefix() + ("/" + uri.lstrip("/") if uri != "/" else "")
        full = full.rstrip("/") or "/"
        route = Route(methods, full, action, middleware=self._current_middleware(), router=self)
        self._routes.append(route)
        return route

    def _prefix(self) -> str:
        parts = [g.prefix.strip("/") for g in self._group_stack if g.prefix.strip("/")]
        return "/" + "/".join(parts) if parts else ""

    def _current_middleware(self) -> List:
        mw: List = []
        for g in self._group_stack:
            mw.extend(g.middleware)
        return mw

    @staticmethod
    def _listify(value) -> List:
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value] if value else []

    def routes(self) -> List[Route]:
        return list(self._routes)
