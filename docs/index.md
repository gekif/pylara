# PyLara Documentation

PyLara is a web framework for Python 3.9+ inspired by Laravel. It gives you routing, middleware,
controllers, an Eloquent-style ORM, migrations, a small template engine, validation and an
Artisan-style command line, using **only the standard library**.

If you know Laravel, the [Laravel cheat sheet](cheatsheet.md) maps the concepts one-to-one.
If you are new to both, start with *Installation* and follow the *Basics*.

## Getting Started
- [Installation](installation.md): install PyLara and create your first application
- [Configuration](configuration.md): `.env`, config files and debug mode
- [Directory Structure](structure.md): what every folder is for

## Architecture Concepts
- [Request Lifecycle](lifecycle.md): what happens between a request and a response
- [Service Container](container.md): bindings, singletons and dependency injection
- [Service Providers](providers.md): where your application is assembled

## The Basics
- [Routing](routing.md)
- [Middleware](middleware.md)
- [Controllers](controllers.md)
- [Requests](requests.md)
- [Responses](responses.md) (including static files)
- [Views](views.md): the template engine
- [Validation](validation.md)
- [Error Handling](errors.md)
- [Sessions](sessions.md): remembering visitors, flash messages, login
- [CSRF Protection](csrf.md)
- [File Uploads](uploads.md)

## Database
- [Getting Started](database.md): connections and raw SQL
- [Migrations](migrations.md)
- [Query Builder](query-builder.md)
- [ORM (Models)](orm.md): models, relationships, soft deletes

## Digging Deeper
- [Console (CLI)](console.md): `manage.py`, generators and custom commands
- [Helpers, Collections and Hashing](helpers.md)
- [Testing](testing.md)

## Going Live
- [Deployment](deployment.md)

## Appendix
- [Laravel cheat sheet](cheatsheet.md)
- [Limitations](limitations.md): read this before choosing PyLara for production
- [Contributing](contributing.md)
