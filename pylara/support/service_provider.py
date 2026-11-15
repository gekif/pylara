"""
ServiceProvider - Base service provider.
Inspired by Laravel's ServiceProvider.
"""


class ServiceProvider:
    """
    Base class for service providers.
    Override register() to bind things into the container.
    Override boot() to run code after all providers are registered.
    """

    def __init__(self, app):
        self.app = app

    def register(self):
        """Bind services into the container."""
        pass

    def boot(self):
        """Bootstrap any application services."""
        pass
