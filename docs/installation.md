# Installation

## Requirements

- Python **3.9 or newer** (developed and tested on 3.12)
- No third-party packages. PyLara depends only on the standard library.

## Installing PyLara

```bash
python -m pip install pylara
```

This installs the `pylara` package and a global `pylara` command. Check it:

```bash
pylara --version        # PyLara 1.0.0
python -m pylara --version   # same thing, works even if the script folder is not on PATH
```

## Creating an application

```bash
pylara new blog
cd blog
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Linux / macOS
python -m pip install -r requirements.txt
python -m manage migrate
python -m manage serve
```

Open <http://127.0.0.1:8000>. You should see the welcome page. Check the JSON API at
<http://127.0.0.1:8000/api/health>.

`pylara new <name>` creates a folder with a working application (see
[Directory Structure](structure.md)). Use `--force` to write into a folder that is not empty.
The project name may contain letters, digits, `_`, `-` and `.`.

> **Tip:** the global `pylara` command only creates projects. Inside a project you run
> everything else with `python -m manage <command>` (see [Console](console.md)).

## The development server

```bash
python -m manage serve                       # http://127.0.0.1:8000
python -m manage serve --host 0.0.0.0 --port 8080
```

The built-in server is **single-threaded and meant for development only**. For production use a
WSGI server, see [Deployment](deployment.md).

## Installing from source (contributors)

```bash
git clone <repository-url>
cd pylara
python -m pip install -e .
python -m tests
```

See [Contributing](contributing.md).

## Next steps

Read [Routing](routing.md), [Controllers](controllers.md) and [ORM](orm.md), or generate some code:

```bash
python -m manage make:model Post -m
python -m manage make:controller PostController --resource
```
