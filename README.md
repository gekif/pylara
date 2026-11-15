# PyLara

A Laravel-inspired web framework for Python. Routing, an Eloquent-style ORM, middleware,
migrations, a small template engine, validation, sessions, CSRF protection, file uploads, and an
Artisan-style CLI, with **no dependencies** beyond the standard library.

```bash
python -m pip install pylara
pylara new blog
cd blog
python -m manage migrate
python -m manage serve
```

Open http://127.0.0.1:8000.

> **Status:** 1.0 is the first release. PyLara is synchronous (WSGI), targets SQLite, and is
> best suited to learning, prototypes, internal tools and small APIs. Read
> [Limitations](https://github.com/gekif/pylara/blob/main/docs/limitations.md) before choosing it for production.

## A taste of PyLara

```python
from pylara import Application, Controller, Model

class Task(Model):
    table = "tasks"
    fillable = ["title", "done"]

class TaskController(Controller):
    def index(self, request):
        return self.json([t.to_dict() for t in Task.where("done", 0).order_by("id", "DESC").get()])

    def store(self, request):
        data = request.validate({"title": "required|string|min:3|max:150"})
        return self.json(Task.create(title=data["title"], done=0).to_dict(), 201)

app = Application()
app.group({"prefix": "/api"}, lambda r: [r.resource("tasks", TaskController)])
```

## Documentation

Start at **[docs/index.md](https://github.com/gekif/pylara/blob/main/docs/index.md)**: installation, configuration, routing, controllers,
requests, responses, views, validation, the database layer and ORM, testing, and deployment.

## Development

```bash
git clone https://github.com/gekif/pylara.git && cd pylara
python -m pip install -e .
python -m tests                      # run the whole test suite
```

## License

MIT. See [LICENSE](https://github.com/gekif/pylara/blob/main/LICENSE).
