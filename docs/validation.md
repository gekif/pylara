# Validation

```python
data = request.validate({
    "name":     "required|string|min:2|max:100",
    "email":    "required|email",
    "age":      "integer",
    "role":     "in:admin,editor,viewer",
    "password": "required|min:8|confirmed",
})
```

`validate()` returns a dict with **only the validated fields**. If validation fails it raises
`ValidationException`, which becomes an HTTP **422** response:

```json
{
  "message": "Validation failed",
  "errors": {
    "email": ["The email must be a valid email address."],
    "name": ["The name field is required."]
  }
}
```

## Available rules

Rules are separated by `|`. Rules other than `required` are skipped when the field is empty
(missing, `null` or `""`), so a field without `required` is optional. `0` and `false` are *not* empty.

| Rule | Passes when |
|---|---|
| `required` | the field is present and not empty |
| `string` | the value is a string |
| `integer` | the value is a whole number (`5`, `"5"`; not `1.5`, not `true`) |
| `numeric` | the value is a number (`5`, `1.5`, `"1.5"`; not `true`) |
| `boolean` | `true`, `false`, `1`, `0`, `"yes"`, `"no"` |
| `email` | looks like `name@host.tld` |
| `min:N` | the value's **length** is at least N characters |
| `max:N` | the value's **length** is at most N characters |
| `in:a,b,c` | the value is one of the listed values |
| `confirmed` | equals the field named `<field>_confirmation` |
| `file` | the field is an uploaded file |
| `mimes:png,jpg` | the uploaded file's **extension** is in the list |
| `max_kb:N` | the uploaded file is at most N kilobytes |

The three file rules are explained in [File Uploads](uploads.md#validation-rules). `validate()` returns
the `UploadedFile` object for file fields.

> `min` and `max` measure the **length of the text**, also for numbers. To bound a number, check it
> in your code after validating `integer`/`numeric`.

## Handling failures yourself

```python
from pylara.http.exceptions import ValidationException

try:
    data = request.validate({"title": "required"})
except ValidationException as exc:
    exc.errors            # {"title": ["The title field is required."]}
```

For HTML forms, re-render the page with the errors, see [Views](views.md#forms-with-validation-errors).

## Custom checks

Do domain checks in code and raise the same exception so the client gets the same format:

```python
if User.where("email", data["email"]).first():
    raise ValidationException({"email": ["That email is already registered."]})
```

## Limitations

Messages are fixed English strings, nested arrays (`items.*.name`) are not supported, and there is
no database-backed `unique` rule: check it as shown above.
