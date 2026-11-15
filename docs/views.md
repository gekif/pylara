# Views

Views are HTML templates in `resources/views/`. PyLara ships a small, safe template engine with
Blade/Jinja-like syntax. It **never calls `eval()`**, and output is HTML-escaped by default.

## Rendering a view

```python
class PageController(Controller):
    def home(self, request):
        return self.view("welcome", title="Home", tasks=Task.all())
```

`view(name, data=None, status=200, **context)` accepts a dict, keyword arguments, or both. It also
exists as `app.view(...)` and as a helper:

```python
from pylara.support.helpers import view
return view("welcome", {"title": "Home"}, status=200)
```

**View names use dots for folders**: `admin.users.index` is `resources/views/admin/users/index.html`.
Names may contain only letters, digits, `_` and `-` per segment, so templates cannot be read from
outside the views folder.

## Displaying data

```html
<h1>{{ title }}</h1>
<p>{{ user.name }} / {{ user.address.city }} / {{ items.0 }}</p>
<div>{!! trusted_html !!}</div>
```

- `{{ ... }}` is **escaped** (`<` becomes `&lt;`).
- `{!! ... !!}` is **raw**. Only use it for HTML you generated and trust.
- Dotted lookup depends on the object: a dictionary is read by key, a list or tuple by index
  (`items.0`), anything else by attribute. Models work: `{{ post.title }}`.
- A missing value renders as an empty string, never an error.
- **Callables are never invoked** from a template, and names starting with `_` are hidden. Compute
  things in the controller and pass the result.

## Variables every view receives

| Variable | Value |
|---|---|
| `csrf_token` | the session's CSRF token (empty without a session) |
| `csrf_field` | ready-made hidden input `<input type="hidden" name="_token" ...>`: use it raw, `{!! csrf_field !!}` |
| `flash` | values flashed during the previous request, e.g. `{{ flash.status }}` |

Your own data wins when a name clashes. Add data for **all** views with `share()`:

```python
app.share("site_name", "My Blog")
app.share("year", lambda: datetime.now().year)     # a callable is called at every render
```

See [Sessions](sessions.md) and [CSRF Protection](csrf.md).

## Comments

```html
{# This comment never reaches the browser. It may span lines and contain {{ tags }}. #}
```

## Conditionals

```html
{% if user.is_admin %}
  Admin
{% elif user.age >= 18 %}
  Adult
{% else %}
  Minor
{% endif %}
```

A condition is a value (`user`), a negation (`not user`) or **one** comparison with `==`, `!=`,
`>`, `<`, `>=`, `<=`. Operands are values, quoted strings, numbers, `true`, `false` or `none`:

```html
{% if status == "active" %}...{% endif %}
{% if count != 0 %}...{% endif %}
```

`and` / `or` are not supported; nest `if` blocks or compute a flag in your controller.

## Loops

```html
<ul>
{% for task in tasks %}
  <li class="{% if loop.first %}first{% endif %}">{{ loop.index }}. {{ task.title }}</li>
{% else %}
  <li>No tasks.</li>
{% endfor %}
</ul>
```

Inside a loop `loop` provides `index` (1-based), `index0`, `first`, `last` and `length`. The `else`
branch runs when the list is empty. You can loop over lists, tuples, sets and dict keys.

## Layouts and blocks

`resources/views/layouts/app.html`
```html
<!DOCTYPE html>
<html>
<head><title>{% block title %}My Site{% endblock %}</title></head>
<body>
  {% include "partials.nav" %}
  {% block content %}{% endblock %}
</body>
</html>
```

`resources/views/tasks/index.html`
```html
{% extends "layouts.app" %}

{% block title %}Tasks{% endblock %}

{% block content %}
  <h1>Tasks</h1>
{% endblock %}
```

- `{% extends "name" %}` makes the page fill the blocks of its parent. Content outside blocks in a
  child template is ignored. Layouts can extend other layouts.
- A block in the parent holds the default content; the child replaces it.
- `{% include "partials.nav" %}` inserts another template and shares the current data.

## Forms with validation errors

```python
from pylara.http.exceptions import ValidationException

def store(self, request):
    try:
        data = request.validate({"title": "required|min:3"})
    except ValidationException as exc:
        return self.view("tasks.create", errors=exc.errors, old=request.all(), status=422)
    Task.create(**data)
    return self.redirect("/tasks")
```

```html
<input name="title" value="{{ old.title }}">
{% for message in errors.title %}<p class="error">{{ message }}</p>{% endfor %}
```

## Caching and errors

Parsed templates are cached in memory and reloaded when the file's modification time changes, so
editing a template needs no restart. A missing view or a syntax error raises `ViewError`, which
becomes a 500 (with details when `APP_DEBUG=true`).

## What is not included

No filters (`{{ x|upper }}`), no variable assignment, no macros, no `and`/`or`, no automatic CSRF
tokens. See [Limitations](limitations.md).
