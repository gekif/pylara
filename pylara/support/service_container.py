"""
ServiceContainer - IoC / dependency injection container.
Inspired by Illuminate.Container.Container.

Resolver contract: a binding's `concrete` is a callable. If it accepts at least
one positional parameter it receives the container; otherwise it is called bare.
"""

import inspect
from typing import Any, Callable, Dict, Type


def _key(abstract) -> str:
    return abstract.__name__ if isinstance(abstract, type) else str(abstract)


class ServiceContainer:

    def __init__(self):
        self._bindings: Dict[str, dict] = {}
        self._singletons: Dict[str, Any] = {}
        self._instances: Dict[str, Any] = {}

    # ── registration ────────────────────────────────────────────────────────

    def bind(self, abstract, concrete: Callable, singleton: bool = False):
        """Register a factory. It runs on every make() unless singleton=True."""
        self._bindings[_key(abstract)] = {"concrete": concrete, "singleton": singleton}

    def singleton(self, abstract, concrete: Callable):
        """Register a factory whose result is created once and then reused."""
        self.bind(abstract, concrete, singleton=True)

    def instance(self, abstract, instance: Any):
        """Register an already-built object."""
        self._instances[_key(abstract)] = instance

    def bound(self, abstract) -> bool:
        k = _key(abstract)
        return k in self._instances or k in self._bindings

    # ── resolution ──────────────────────────────────────────────────────────

    def make(self, abstract, parameters: dict = None) -> Any:
        k = _key(abstract)
        if k in self._instances:
            return self._instances[k]
        if k in self._singletons:
            return self._singletons[k]
        if k not in self._bindings:
            raise KeyError(f"[Container] No binding found for '{k}'")

        binding = self._bindings[k]
        instance = self._call(binding["concrete"], parameters)
        if binding["singleton"]:
            self._singletons[k] = instance
        return instance

    def _call(self, concrete: Callable, parameters: dict = None):
        try:
            sig = inspect.signature(concrete)
            takes_container = any(
                p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL)
                for p in sig.parameters.values()
            )
        except (TypeError, ValueError):
            takes_container = True
        if takes_container:
            return concrete(self, **(parameters or {}))
        return concrete(**(parameters or {}))

    def build(self, concrete: Type, parameters: dict = None) -> Any:
        """
        Instantiate a class, resolving constructor arguments from their type hints
        (looked up by class name in the container).
        """
        if concrete.__init__ is object.__init__:
            return concrete()
        sig = inspect.signature(concrete.__init__)
        deps = {}
        for name, param in sig.parameters.items():
            if name == "self" or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue
            if parameters and name in parameters:
                deps[name] = parameters[name]
                continue
            annotation = param.annotation
            if annotation is not inspect.Parameter.empty and self.bound(annotation):
                deps[name] = self.make(annotation)
            elif param.default is not inspect.Parameter.empty:
                deps[name] = param.default
            else:
                raise KeyError(
                    f"[Container] Cannot resolve parameter '{name}' of {concrete.__name__}: "
                    f"add a type hint that is bound in the container, or give it a default."
                )
        return concrete(**deps)

    def __getitem__(self, abstract) -> Any:
        return self.make(abstract)
