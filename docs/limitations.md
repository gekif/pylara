# Limitations

PyLara 1.0 is a **first release**, small by design. It is a good fit for learning, prototypes, internal
tools and small APIs. Know these limits before choosing it for something bigger.

## Architecture

- **Synchronous only.** It is a WSGI application; there is no `async`/`await` support.
- **One database connection per process**, shared by all requests in it. Run one thread per process
  (see [Deployment](deployment.md#threads-and-sqlite)).
- **Routes are matched linearly**, in registration order.
- The built-in development server is single-threaded. It is not for production.

## Database

- **SQLite only.** SQL uses the `?` parameter style, `AUTOINCREMENT` and `sqlite_master`; PostgreSQL
  and MySQL drivers are not supported.
- The query builder has **no `OR`, joins, grouping or sub-queries**, and no eager loading of
  relationships (use [`where_in`](orm.md#relationships) to avoid N+1 queries).
- Migrations can create and drop tables and **add** columns; renaming or dropping columns needs a
  manual table rebuild. There is no `migrate:fresh` or seeder system.
- No model events/observers, no model factories, and no transaction helper (use the connection,
  see [Database](database.md#transactions)).
- Default relationship keys use the lower-cased class name (`blogpost_id`); pass explicit keys for
  multi-word model names.

## HTTP

- **Sessions and CSRF exist, but authentication is not built in.** You write the login controller
  ([example](sessions.md#logging-users-in)); there is no ready-made registration, password reset,
  email verification, "remember me", or roles/permissions system.
- **Sessions are stored in files**, shared by worker processes on one machine only. Concurrent requests
  of one visitor can overwrite each other's session changes (last write wins).
- **Uploads are held in memory** and limited by `MAX_BODY_MB` (default 10); `mimes` checks the file
  *extension* only; there is no image processing or cloud storage.
- No route constraints (regex on parameters), no implicit model binding, no route caching.
- `ThrottleMiddleware` keeps counters in memory, per process.

## Views

A deliberately small template engine: no filters, no variable assignment, no macros, no `and`/`or`
in conditions, no automatic CSRF tokens.

## Validation

Fixed English messages, no nested array rules, and no database-backed rules such as `unique`/`exists`.
`min`/`max` measure text length, also for numbers.

## Not included

Queues, scheduler, events, mail, cache, file storage, localisation, broadcasting, notifications, and an
admin panel. For these, use ordinary Python libraries inside your controllers and providers.

## Maturity

First release; tested on Python 3.12 (supported: 3.9+). The API may change in minor versions until it
settles; pin your version (`pylara==1.0.0`). If you need a battle-tested framework today, use
**Django** or **FastAPI**; PyLara's concepts will carry over.
