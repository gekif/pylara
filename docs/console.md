# Console (Command Line)

PyLara has two command line entry points.

| Command | Where | Purpose |
|---|---|---|
| `pylara new <name>` | anywhere | create a new application |
| `python -m manage <command>` | inside a project | everything else (the equivalent of `php artisan`) |

`python -m pylara ...` is the same as `pylara ...` and works even when the scripts folder is not on
your `PATH`.

## Built-in commands

Run `python -m manage` (or `python -m manage help`) to list them.

| Command | Description |
|---|---|
| `serve [--host H] [--port P]` | development server (default 127.0.0.1:8000) |
| `key:generate [--force] [--show]` | create `APP_KEY` in `.env` (signs session cookies) |
| `route:list` | table of methods, URIs, route names and actions |
| `make:controller Name [--resource]` | create `app/controllers/<name>.py` |
| `make:model Name [-m]` | create `app/models/<name>.py` (and a migration with `-m`) |
| `make:middleware Name` | create `app/middleware/<name>.py` |
| `make:migration name` | create a timestamped file in `database/migrations/` |
| `migrate` | run pending migrations |
| `migrate:status` | list migrations as Ran / Pending |
| `migrate:rollback [--steps N]` | undo the last N batches (default 1) |

Generators refuse to overwrite an existing file, and names must be plain identifiers (letters,
digits, `_`), so `make:controller ../x` is rejected. Exit codes: `0` success, `1` error.

## Custom commands

```python
# app/commands/greet.py
from pylara.console.console import Command, CommandError, load_app


class GreetCommand(Command):
    name = "greet"
    description = "Say hello"

    def configure(self, parser):                  # an argparse.ArgumentParser
        parser.add_argument("name")
        parser.add_argument("--shout", action="store_true")

    def handle(self, args):
        if not args.name.strip():
            raise CommandError("Name must not be empty")    # prints an error, exit code 1
        text = f"Hello, {args.name}!"
        self.info(text.upper() if args.shout else text)
        return 0
```

Register it in `manage.py`:

```python
from app.commands.greet import GreetCommand
console.register(GreetCommand())
```

```bash
python -m manage greet Ana --shout
```

Output helpers on `Command`: `info()` (green), `warn()` (yellow), `error()` (red, stderr), `line()`.
Colors are used only on a terminal and are disabled when `NO_COLOR` is set.

### Using the application inside a command

```python
def handle(self, args):
    app = load_app()          # imports bootstrap.app from the current directory
    ...                       # models are ready to use, the database is connected
```

`load_app()` raises a friendly `CommandError` outside a project.

## Running the console from code

```python
from pylara.console.console import Console
exit_code = Console().run(["migrate:status"])
```
