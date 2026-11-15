"""
Console - the Artisan-style command runner used by a project's manage.py.

    python -m manage serve
    python -m manage make:controller UserController --resource
    python -m manage migrate

Add your own commands: subclass Command and call console.register(MyCommand()).
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from typing import Dict

from pylara.version import __version__

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
if _COLOR and os.name == "nt":
    os.system("")          # enables ANSI escape sequences in Windows terminals


def _paint(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def camel(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_") if part)


class CommandError(Exception):
    """Raise inside Command.handle() to print a clean error and exit with code 1."""


def load_app():
    """Import the project's application (bootstrap/app.py) from the current directory."""
    sys.path.insert(0, os.getcwd())
    try:
        from bootstrap.app import app
    except ModuleNotFoundError as exc:
        if exc.name in ("bootstrap", "bootstrap.app"):
            raise CommandError("Run this command from the root of a PyLara project (bootstrap/app.py not found).")
        raise
    return app


def _check_name(name: str) -> str:
    if not _NAME.match(name):
        raise CommandError(f"'{name}' is not a valid name. Use letters, digits and underscores only.")
    return name


def _write_new_file(path: str, content: str):
    if os.path.exists(path):
        raise CommandError(f"{path} already exists.")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


class Command:
    name: str = ""
    description: str = ""

    def configure(self, parser: argparse.ArgumentParser):
        """Declare arguments/options on the argparse parser."""

    def handle(self, args) -> int:
        raise NotImplementedError

    def info(self, message: str):
        print("  " + _paint("32", message))

    def warn(self, message: str):
        print("  " + _paint("33", message))

    def error(self, message: str):
        print("  " + _paint("31", "ERROR: " + message), file=sys.stderr)

    def line(self, message: str = ""):
        print("  " + message)


# ── runtime ─────────────────────────────────────────────────────────────────

class ServeCommand(Command):
    name = "serve"
    description = "Start the development server"

    def configure(self, parser):
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", default=8000, type=int)

    def handle(self, args):
        load_app().serve(args.host, args.port)
        return 0


class RouteListCommand(Command):
    name = "route:list"
    description = "List all registered routes"

    def handle(self, args):
        routes = load_app().router.routes()
        if not routes:
            self.warn("No routes registered.")
            return 0
        print()
        print(f"  {'METHOD':<14}{'URI':<38}{'NAME':<22}ACTION")
        print("  " + "-" * 100)
        for r in routes:
            methods = "|".join(m for m in r.methods if m != "HEAD")
            action = r.action
            if isinstance(action, (list, tuple)):
                label = f"{action[0].__name__}@{action[1]}"
            else:
                label = getattr(action, "__name__", str(action))
            print(f"  {_paint('32', f'{methods:<14}')}{r.uri:<38}{(r.name or ''):<22}{label}")
        print()
        return 0


class KeyGenerateCommand(Command):
    name = "key:generate"
    description = "Set a new random APP_KEY in .env (used to sign session cookies)"

    def configure(self, parser):
        parser.add_argument("--show", action="store_true", help="print the key instead of writing it")
        parser.add_argument("--force", action="store_true", help="replace an existing key (logs everyone out)")

    def handle(self, args):
        import secrets
        key = secrets.token_hex(32)
        if args.show:
            print(key)
            return 0
        path = os.path.join(os.getcwd(), ".env")
        lines = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        current = next((l.split("=", 1)[1].strip() for l in lines if l.startswith("APP_KEY=")), "")
        if current and not args.force:
            raise CommandError("APP_KEY is already set. Use --force to replace it (this invalidates all sessions).")
        if any(l.startswith("APP_KEY=") for l in lines):
            lines = [f"APP_KEY={key}" if l.startswith("APP_KEY=") else l for l in lines]
        else:
            lines.append(f"APP_KEY={key}")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        self.info("Application key set.")
        return 0


# ── generators ──────────────────────────────────────────────────────────────

class MakeControllerCommand(Command):
    name = "make:controller"
    description = "Create a controller (use --resource for CRUD methods)"

    def configure(self, parser):
        parser.add_argument("name")
        parser.add_argument("--resource", action="store_true", help="include CRUD methods")

    def handle(self, args):
        name = _check_name(args.name)
        if not name.endswith("Controller"):
            name += "Controller"
        path = os.path.join("app", "controllers", f"{snake(name)}.py")
        _write_new_file(path, self._resource(name) if args.resource else self._plain(name))
        self.info(f"Controller created: {path}")
        self.line(f"from app.controllers.{snake(name)} import {name}")
        return 0

    @staticmethod
    def _plain(name):
        return f'''from pylara import Controller, Request


class {name}(Controller):

    def index(self, request: Request):
        return self.json({{"message": "Hello from {name}"}})
'''

    @staticmethod
    def _resource(name):
        return f'''from pylara import Controller, Request


class {name}(Controller):

    def index(self, request: Request):
        return self.json([])

    def show(self, request: Request, id: str):
        return self.json({{"id": id}})

    def store(self, request: Request):
        data = request.validate({{"name": "required|string|max:255"}})
        return self.json(data, 201)

    def update(self, request: Request, id: str):
        return self.json({{"id": id, "updated": True}})

    def destroy(self, request: Request, id: str):
        return self.json({{"id": id, "deleted": True}})
'''


class MakeModelCommand(Command):
    name = "make:model"
    description = "Create a model"

    def configure(self, parser):
        parser.add_argument("name")
        parser.add_argument("-m", "--migration", action="store_true", help="also create a create_<table>_table migration")

    def handle(self, args):
        name = _check_name(args.name)
        table = snake(name) + "s"
        path = os.path.join("app", "models", f"{snake(name)}.py")
        _write_new_file(path, f'''from pylara import Model


class {name}(Model):
    table = "{table}"
    fillable = []          # columns allowed in create()/fill(); nothing is assignable until you list it
    hidden = []            # columns left out of to_dict()/JSON
    timestamps = True
''')
        self.info(f"Model created: {path}")
        self.line(f"from app.models.{snake(name)} import {name}")
        if args.migration:
            MakeMigrationCommand().create(f"create_{table}_table", self)
        return 0


class MakeMiddlewareCommand(Command):
    name = "make:middleware"
    description = "Create a middleware"

    def configure(self, parser):
        parser.add_argument("name")

    def handle(self, args):
        name = _check_name(args.name)
        path = os.path.join("app", "middleware", f"{snake(name)}.py")
        _write_new_file(path, f'''from pylara.middleware.middleware import Middleware


class {name}(Middleware):

    def handle(self, request, next):
        # before the request is handled
        response = next()
        # after the request is handled
        return response
''')
        self.info(f"Middleware created: {path}")
        self.line(f"from app.middleware.{snake(name)} import {name}")
        return 0


class MakeMigrationCommand(Command):
    name = "make:migration"
    description = "Create a migration (e.g. create_posts_table)"

    def configure(self, parser):
        parser.add_argument("name")

    def handle(self, args):
        self.create(_check_name(args.name), self)
        return 0

    def create(self, name: str, out: Command):
        stamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")
        path = os.path.join("database", "migrations", f"{stamp}_{name}.py")
        create = re.match(r"^create_(\w+)_table$", name)
        table = create.group(1) if create else None
        if table:
            body = f'''    def up(self):
        return Schema.create("{table}", lambda t: [
            t.id(),
            # t.string("name"),
            t.timestamps(),
        ])

    def down(self):
        return Schema.drop("{table}")
'''
        else:
            body = '''    def up(self):
        # return Schema.table("table_name", lambda t: [t.string("new_column").nullable()])
        return []

    def down(self):
        return []
'''
        _write_new_file(path, f'''from pylara.database.migration import Migration, Schema


class {camel(name)}(Migration):

{body}''')
        out.info(f"Migration created: {path}")


# ── database ────────────────────────────────────────────────────────────────

def _migration_context():
    from pylara.database.migration import Migrator, discover
    from pylara.orm.model import get_connection
    load_app()
    try:
        connection = get_connection()
    except RuntimeError as exc:
        raise CommandError(str(exc))
    migrations = discover(os.path.join(os.getcwd(), "database", "migrations"))
    return Migrator(connection), migrations


class MigrateCommand(Command):
    name = "migrate"
    description = "Run pending database migrations"

    def handle(self, args):
        migrator, migrations = _migration_context()
        if not migrations:
            self.warn("No migration files found in database/migrations.")
            return 0
        print()
        migrator.run(migrations)
        self.info("Done.")
        print()
        return 0


class MigrateRollbackCommand(Command):
    name = "migrate:rollback"
    description = "Roll back the last batch of migrations (--steps N for more)"

    def configure(self, parser):
        parser.add_argument("--steps", type=int, default=1)

    def handle(self, args):
        migrator, migrations = _migration_context()
        print()
        migrator.rollback(dict(migrations), steps=max(1, args.steps))
        print()
        return 0


class MigrateStatusCommand(Command):
    name = "migrate:status"
    description = "Show which migrations have run"

    def handle(self, args):
        migrator, migrations = _migration_context()
        print()
        for name, ran in migrator.status(migrations):
            print(f"  {_paint('32', 'Ran    ') if ran else _paint('33', 'Pending')}  {name}")
        if not migrations:
            self.warn("No migration files found.")
        print()
        return 0


# ── runner ──────────────────────────────────────────────────────────────────

class Console:

    def __init__(self):
        self._commands: Dict[str, Command] = {}
        for cls in (ServeCommand, RouteListCommand, KeyGenerateCommand, MakeControllerCommand, MakeModelCommand,
                    MakeMiddlewareCommand, MakeMigrationCommand, MigrateCommand,
                    MigrateRollbackCommand, MigrateStatusCommand):
            self.register(cls())

    def register(self, command: Command):
        self._commands[command.name] = command

    def run(self, argv: list = None) -> int:
        argv = list(sys.argv[1:] if argv is None else argv)
        if not argv or argv[0] in ("-h", "--help", "help", "list"):
            self._print_help()
            return 0
        name = argv[0]
        if name not in self._commands:
            print(f"\n  {_paint('31', f'Command {name!r} not found.')}")
            self._print_help()
            return 1
        command = self._commands[name]
        parser = argparse.ArgumentParser(prog=f"manage {name}", description=command.description)
        command.configure(parser)
        try:
            args = parser.parse_args(argv[1:])
        except SystemExit as exc:
            return int(exc.code or 0)
        try:
            return int(command.handle(args) or 0)
        except CommandError as exc:
            command.error(str(exc))
            return 1

    def _print_help(self):
        print(f"\n  PyLara Framework {__version__}\n")
        print("  Usage:  python -m manage <command> [options]\n")
        print("  Available commands:")
        for name, cmd in sorted(self._commands.items()):
            print(f"    {_paint('32', f'{name:<20}')} {cmd.description}")
        print()


console = Console()
