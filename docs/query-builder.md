# Query Builder

Every model has a fluent query builder. Start with `Model.query()` (or `Model.where(...)`, which
returns one).

```python
posts = (Post.query()
         .where("published", 1)
         .where("title", "LIKE", "%python%")
         .order_by("created_at", "DESC")
         .limit(10)
         .get())
```

Results are **model instances**, not dictionaries (`post.title`, `post.to_dict()`).

## Retrieving

| Call | Returns |
|---|---|
| `.get()` | list of models |
| `.first()` | one model or `None` |
| `.find(id)` | model with that primary key, or `None` |
| `.count()` | integer |
| `.exists()` | bool |
| `.paginate(per_page=15, page=1)` | dict, see below |

## Where clauses

```python
.where("status", "active")                  # status = 'active'
.where("age", ">=", 18)                     # operators: = != <> < > <= >= LIKE "NOT LIKE"
.where_in("id", [1, 2, 3])                  # id IN (1, 2, 3)
.where("deleted_by", None)                  # deleted_by IS NULL      (also .where_null("deleted_by"))
.where("approved_by", "!=", None)           # approved_by IS NOT NULL (also .where_not_null(...))
```

Several `where` calls are combined with **AND**. There is no `OR`, `JOIN`, `GROUP BY` or
sub-query support in the builder; use [raw SQL](database.md#running-raw-sql) for those.

## Ordering and limits

```python
.order_by("name")                  # ASC
.order_by("created_at", "DESC")
.limit(20).offset(40)
```

`order_by` accepts one column per call (a later call replaces the earlier one).

## Pagination

```python
page = Post.query().order_by("id", "DESC").paginate(per_page=10, page=2)
page["data"]          # list of models
page["total"]         # total rows
page["per_page"]      # 10
page["current_page"]  # 2
page["last_page"]     # ceil(total / per_page), at least 1
```

## Mass update and delete

```python
Post.where("published", 0).update(published=1)     # returns the number of rows changed
Post.where("views", "<", 5).delete()               # returns the number of rows removed
```

`update()` also refreshes `updated_at` when the model uses timestamps. With
[soft deletes](orm.md#soft-deletes) `delete()` sets `deleted_at` instead of removing rows.
Neither runs model events or respects `fillable`: they are direct SQL, so pass only values you chose.

## Soft-deleted rows

```python
Post.query().with_trashed().get()      # include rows that are soft-deleted
```

## Safety

Values are always sent as SQL parameters, never interpolated. **Column names and operators are
validated** (letters, digits, `_`, one optional `table.column` dot; operators from a fixed list), and
a `ValueError` is raised otherwise, so user input cannot inject SQL through a column name. Even so,
choose column names from your own code, not from the request:

```python
allowed = {"name", "created_at"}
column = request.query("sort", "name")
Post.query().order_by(column if column in allowed else "name").get()
```
