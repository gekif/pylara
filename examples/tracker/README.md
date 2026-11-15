# Tracker: reference application

A complete PyLara application: registration, login/logout (sessions), per-user tasks with HTML forms,
CSRF protection, validation errors shown in the form, flash messages, file attachments, and
authorization (users cannot touch each other's tasks). Use it as a model for your own apps.

```bash
python -m pip install -e ../..          # install PyLara from this repository
python -m manage key:generate           # creates APP_KEY in .env (copy .env.example to .env first)
python -m manage migrate
python -m manage serve
python -m unittest discover -v          # 11 tests
```

Where to look: `routes/web.py` (middleware groups), `app/controllers/auth_controller.py` (login flow),
`app/controllers/task_controller.py` (ownership checks, uploads), `resources/views/` (forms with
`csrf_field`, errors, flash), `tests/test_tracker.py` (how to test form flows).
