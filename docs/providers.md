# Service Providers

Service providers are the central place to assemble your application: bind services into the
[container](container.md), register listeners, do start-up work.

## Writing a provider

```python
# app/providers/app_service_provider.py
from pylara.support.service_provider import ServiceProvider


class AppServiceProvider(ServiceProvider):

    def register(self):
        """Only bind things here. Other services may not exist yet."""
        self.app.singleton("mailer", lambda app: Mailer(app.env("MAIL_HOST", "localhost")))

    def boot(self):
        """Runs after every provider has registered. Safe to use other services."""
        self.app.make("mailer").connect()
```

`self.app` is the application.

## Registering providers

In `bootstrap/app.py`:

```python
from app.providers.app_service_provider import AppServiceProvider
app.register(AppServiceProvider)
```

Order of events:

1. `app.register(Provider)` creates the provider and calls its `register()` immediately.
2. The first request (or an explicit `app.boot()`) calls every provider's `boot()` once, in
   registration order.
3. A provider registered **after** boot has its `boot()` called straight away.

## Boot callbacks

```python
app.booted(lambda app: print("ready"))
```

Callbacks run after all providers have booted.

## What belongs where

| Put it in `register()` | Put it in `boot()` |
|---|---|
| `bind`, `singleton`, `instance` | Reading other services |
| Nothing that depends on other providers | Opening connections, warming caches |
