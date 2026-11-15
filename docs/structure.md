# Directory Structure

`pylara new blog` creates:

```
blog/
├── app/
│   ├── controllers/        controller classes (one file per class, snake_case.py)
│   ├── middleware/         your middleware
│   ├── models/             ORM models
│   └── providers/          service providers
├── bootstrap/
│   └── app.py              builds the application: database, providers, routes
├── config/
│   └── app.json            JSON configuration
├── database/
│   └── migrations/         schema migrations
├── public/                 static files served at the site root
│   └── css/app.css
├── resources/
│   └── views/              HTML templates
├── routes/
│   ├── web.py              page routes
│   └── api.py              API routes
├── storage/                SQLite database and other runtime files (git-ignored)
├── tests/
├── .env                    machine-specific settings (never commit)
├── .env.example
├── manage.py               command line entry point (like artisan)
├── requirements.txt
└── wsgi.py                 entry point for production servers
```

## `bootstrap/app.py`: the heart of the app

This module creates the `app` object that everything else imports. In the generated project it:

1. creates `Application(base_path=BASE)` (which also loads `.env`),
2. opens the SQLite connection and registers it with `set_connection("default", connection)`,
3. registers service providers,
4. calls `register(app)` in `routes/web.py` and `routes/api.py`.

The variable **must be called `app`**: `manage.py` imports `bootstrap.app:app`, and `wsgi.py`
exposes it to production servers.

## `routes/`

Plain Python modules with a `register(app)` function. Add as many route files as you like and call
them from `bootstrap/app.py`. See [Routing](routing.md).

## `public/`

Files here are served directly. `public/css/app.css` is available at `/css/app.css`. See
[Responses](responses.md#static-files).

## `resources/views/`

Templates, referenced by dotted name: `view("admin.users.index")` renders
`resources/views/admin/users/index.html`. See [Views](views.md).

## `storage/`

Runtime files, never served to the web: the SQLite database (`storage/database.sqlite`), session files
(`storage/sessions/`) and a good place for private uploads (`storage/uploads/`). The folder is git-ignored.

## Why snake_case file names?

`make:controller PostController` writes `app/controllers/post_controller.py` and prints the import
line to use: `from app.controllers.post_controller import PostController`.
