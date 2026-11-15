# ORM (Models)

PyLara's ORM follows the **Active Record** pattern like Laravel's Eloquent: each model class maps to
a table, and each instance is a row.

## Defining models

```bash
python -m manage make:model Post -m        # model + create_posts_table migration
```

```python
# app/models/post.py
from pylara import Model


class Post(Model):
    table = "posts"
    fillable = ["user_id", "title", "body"]
    hidden = []
    timestamps = True
```

### Model settings

| Attribute | Default | Meaning |
|---|---|---|
| `table` | class name in snake_case + `s` (`BlogPost` → `blog_posts`) | table name. Set it explicitly for irregular plurals (`Category` → `"categories"`). |
| `primary_key` | `"id"` | primary key column |
| `connection` | `"default"` | [connection](database.md) name |
| `fillable` | `[]` | columns that may be mass-assigned (whitelist) |
| `guarded` | `["*"]` | blacklist used when `fillable` is empty, see below |
| `timestamps` | `True` | maintain `created_at` / `updated_at` |
| `soft_deletes` | `False` | use `deleted_at` instead of really deleting |
| `hidden` | `[]` | columns left out of `to_dict()` / `to_json()` |
| `casts` | `{}` | `{"column": callable}` applied when a value is set or loaded |

## Mass assignment

`Post.create(**data)` and `post.fill(**data)` copy values into the model. Because `data` often comes
from a request, PyLara is **closed by default**: with `fillable = []` and `guarded = ["*"]`
nothing can be mass-assigned. Disallowed keys are **silently ignored**.

```python
class Post(Model):
    fillable = ["title", "body"]          # only these are accepted
```

Other modes:

```python
guarded = ["is_admin"]    # everything except is_admin (when fillable is empty)
guarded = []              # everything. Only for models that never see user input
```

`id` is never accepted through `fillable`. `force_fill(**attrs)` bypasses all checks on purpose.
`obj.attribute = value` (plain assignment) is also not checked, because it is explicit code.

> Always list `fillable`. A user who can send `{"is_admin": 1}` to an endpoint that calls
> `User.create(**request.all())` must not be able to promote themselves.

## Retrieving models

```python
Post.all()                          # list of every row
Post.find(1)                        # model or None
Post.find_or_fail(1)                # model or raises NotFoundException (HTTP 404)
Post.first()                        # first row or None
Post.where("title", "Hello").first()
Post.query().order_by("id", "DESC").limit(5).get()
```

More in the [Query Builder](query-builder.md).

## Creating and updating

```python
post = Post.create(title="Hi", body="...")        # INSERT, returns the model

post.title = "New title"                          # plain assignment
post.save()                                       # UPDATE (INSERT for a new instance)

post = Post(title="Draft")                        # build without saving
post.save()

Post.first_or_create({"title": "Hi"}, {"body": "x"})       # find by first dict, else create with both
Post.update_or_create({"title": "Hi"}, {"body": "y"})      # update the match (respecting fillable) or create
```

`post.fresh()` reloads the row as a new instance; `post.is_dirty()` tells whether attributes changed
since loading (`post.is_dirty("title")` checks specific ones).

## Deleting

```python
post.delete()                      # DELETE (or soft delete, see below)
Post.where("views", "<", 5).delete()
```

### Soft deletes

Add `t.soft_deletes()` to the migration and `soft_deletes = True` to the model:

```python
class Post(Model):
    soft_deletes = True

post.delete()          # sets deleted_at; the row stays
Post.all()             # excludes soft-deleted rows automatically
Post.query().with_trashed().get()     # includes them
post.restore()         # clears deleted_at
```

## Timestamps

With `timestamps = True` the table needs `created_at` and `updated_at` (`t.timestamps()`). They are
set on save as UTC ISO-8601 strings (`2026-11-14T10:30:15.123456`).

## Casting

```python
class Product(Model):
    casts = {"price": float, "active": lambda v: str(v).lower() in ("1", "true"), "stock": int}
```

Casts run when you set an attribute and when rows are loaded. `None` is never cast.

## Serialising

```python
post.to_dict()      # {"id": 1, "title": "Hi", ...}   (without hidden columns)
post.to_json()      # JSON string
```

`to_dict()` contains the row's columns only. Relationships are **not** included; add them yourself:

```python
data = post.to_dict()
data["comments"] = [c.to_dict() for c in post.comments()]
```

## Relationships

Define relationships as ordinary methods:

```python
class User(Model):
    fillable = ["name"]

    def posts(self):                                   # one-to-many
        return self.has_many(Post)

    def profile(self):                                 # one-to-one
        return self.has_one(Profile)

    def roles(self):                                   # many-to-many
        return self.belongs_to_many(Role, "role_user")


class Post(Model):
    def author(self):                                  # inverse
        return self.belongs_to(User, foreign_key="user_id")
```

Call them as methods: `user.posts()` returns a list of models, `post.author()` a model or `None`.

| Method | Signature | Default keys |
|---|---|---|
| `has_many(Related, foreign_key=None, local_key=None)` | list | foreign key: `<thisclass>_id` (lower-cased class name) on the related table |
| `has_one(Related, foreign_key=None, local_key=None)` | model/None | same |
| `belongs_to(Related, foreign_key=None, owner_key=None)` | model/None | foreign key on this table: `<relatedclass>_id`; owner key: related primary key |
| `belongs_to_many(Related, pivot_table, foreign_key=None, related_key=None)` | list | pivot columns `<thisclass>_id` and `<relatedclass>_id` |

> Default keys use the **lower-cased class name without underscores** (`BlogPost` → `blogpost_id`).
> For multi-word class names pass the key explicitly: `self.has_many(Comment, foreign_key="blog_post_id")`.

There is **no eager loading**: each relationship call runs its own query. Looping over many parents and
calling `post.author()` for each is the classic "N+1" problem; fetch related rows with a single
`where_in` instead:

```python
posts = Post.all()
authors = {u.id: u for u in User.query().where_in("id", [p.user_id for p in posts]).get()}
```

## Attribute access notes

- Columns are read and written as attributes: `post.title`, `post.title = "x"`.
- A method defined on the class always wins over a column of the same name. Do not name a column
  `save`, `delete`, `fill`, `fresh`, `table`, ...
- Reading a column that does not exist raises `AttributeError`.
