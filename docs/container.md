# Service Container

The service container is a registry that knows how to build objects. The `Application` **is** a
container, so `app.bind(...)`, `app.make(...)` and friends are all available.

## Binding

```python
class Mailer:
    def __init__(self, host): self.host = host

# A factory that runs every time make() is called
app.bind("mailer", lambda: Mailer("smtp.example.com"))

# A factory that runs once; the result is reused
app.singleton("mailer", lambda: Mailer("smtp.example.com"))

# An object you already built
app.instance("mailer", Mailer("smtp.example.com"))
```

**Factory contract.** A factory that accepts a parameter receives the container; a factory with no
parameters is called bare:

```python
app.singleton("mailer", lambda app: Mailer(app.env("MAIL_HOST", "localhost")))
```

You may bind by name (`"mailer"`) or by class. Classes are stored under their class name:

```python
app.singleton(Mailer, lambda app: Mailer(app.env("MAIL_HOST")))
app.make(Mailer)          # same as app.make("Mailer")
```

## Resolving

```python
mailer = app.make("mailer")       # KeyError if nothing is bound
app.bound("mailer")               # True / False
app["mailer"]                     # shorthand for make()
```

`app.make("app")`, `app.make("router")` and `app.make("config")` are pre-registered.

## Automatic injection

`app.build(SomeClass)` instantiates a class and fills its constructor from **type hints**: each
annotated parameter whose type is bound in the container is resolved. Parameters with a default
value use it. Anything else raises a `KeyError` that names the parameter.

```python
class Reports:
    def __init__(self, mailer: Mailer, limit: int = 10):
        self.mailer, self.limit = mailer, limit

reports = app.build(Reports)
```

Controllers get this treatment automatically: the router builds them with `app.build`.

```python
class ReportController(Controller):
    def __init__(self, mailer: Mailer):
        self.mailer = mailer

    def send(self, request):
        ...
```

Register `Mailer` in a [service provider](providers.md) and the controller receives it.

## Binding is not global state

Everything is attached to the application object you create, so tests can build a fresh
`Application`, bind fakes, and run against it:

```python
app.instance("mailer", FakeMailer())
```
