"""
Global `pylara` command (works anywhere, no project needed):

    pylara new myapp        create a new application
    pylara --version

Inside a project use `python -m manage <command>` instead.
"""

import argparse
import os
import re
import secrets
import sys
from datetime import datetime, timezone

from pylara.version import __version__

STUB_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stubs", "project")
_PROJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")

HELP = f"""
  PyLara Framework {__version__}

  Usage:
    pylara new <name> [--force]   Create a new PyLara application in ./<name>
    pylara --version              Show the version

  Inside a project, run commands with:  python -m manage <command>
"""


def new_project(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="pylara new", description="Create a new PyLara application.")
    parser.add_argument("name", help="project folder name, e.g. blog")
    parser.add_argument("--force", action="store_true", help="write into a non-empty folder")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if not _PROJECT_NAME.match(args.name):
        print(f"  ERROR: '{args.name}' is not a valid project name (letters, digits, '_', '-', '.').", file=sys.stderr)
        return 1
    target = os.path.abspath(args.name)
    if os.path.exists(target) and not os.path.isdir(target):
        print(f"  ERROR: {target} exists and is not a folder.", file=sys.stderr)
        return 1
    if os.path.isdir(target) and os.listdir(target) and not args.force:
        print(f"  ERROR: {target} is not empty. Use --force to write anyway.", file=sys.stderr)
        return 1

    tokens = {
        "__PROJECT_NAME__": args.name,
        "__PROJECT_TITLE__": re.sub(r"[-_.]+", " ", args.name).title(),
        "__APP_KEY__": secrets.token_hex(32),
        "__PYLARA_VERSION__": __version__,
        "__MIGRATION_TS__": datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S"),
    }

    def fill(text: str) -> str:
        for key, value in tokens.items():
            text = text.replace(key, value)
        return text

    created = 0
    for folder, _dirs, files in os.walk(STUB_ROOT):
        for filename in sorted(files):
            if not filename.endswith(".stub"):
                continue
            source = os.path.join(folder, filename)
            relative = fill(os.path.relpath(source, STUB_ROOT)[: -len(".stub")])
            destination = os.path.join(target, relative)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with open(source, encoding="utf-8") as f:
                content = fill(f.read())
            with open(destination, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            created += 1

    print(f"\n  Application created in {target} ({created} files)\n")
    print("  Next steps:\n")
    print(f"    cd {args.name}")
    print("    python -m venv .venv")
    print("    .venv\\Scripts\\activate          (Windows)   |   source .venv/bin/activate   (Linux/macOS)")
    print("    python -m pip install -r requirements.txt")
    print("    python -m manage migrate")
    print("    python -m manage serve\n")
    return 0


def main(argv: list = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0
    if argv[0] in ("-V", "--version", "version"):
        print(f"PyLara {__version__}")
        return 0
    if argv[0] == "new":
        return new_project(argv[1:])
    print(f"\n  Unknown command '{argv[0]}'.")
    print(HELP)
    return 1


if __name__ == "__main__":
    sys.exit(main())
