# File Uploads

PyLara parses `multipart/form-data`, the encoding browsers use for forms with files.

## The form

```html
<form method="POST" action="/avatar" enctype="multipart/form-data">
  {!! csrf_field !!}
  <input name="name">
  <input type="file" name="avatar">
  <button>Upload</button>
</form>
```

`enctype="multipart/form-data"` is mandatory; without it the browser sends only the file's name.
Text fields of the form are available as usual (`request.input("name")`).

## Receiving files

```python
def store(self, request):
    data = request.validate({
        "name":   "required|string|max:100",
        "avatar": "required|file|mimes:png,jpg,jpeg|max_kb:2048",
    })
    saved_path = data["avatar"].save("storage/uploads")      # returns the full path
    return self.json({"stored": os.path.basename(saved_path)}, 201)
```

Without validation:

```python
request.files               # {"avatar": <UploadedFile>, ...}
request.file("avatar")      # one UploadedFile, or None
```

An empty file input (the user chose nothing) is ignored, so the field is simply absent.

## `UploadedFile`

| Attribute / method | Meaning |
|---|---|
| `filename` | the name **after cleaning** (no folders, unsafe characters replaced by `_`, no leading dot) |
| `original_name` | the name the browser sent. Never trust it. |
| `extension` | lower-case extension of the cleaned name, without the dot (`"png"`) |
| `content_type` | the type the browser claims. Never trust it. |
| `size` | bytes |
| `content` | the file as `bytes` |
| `save(directory, name=None)` | write into `directory`, return the full path |

### Saving

`save()` is safe by default:

- Without `name`, it picks a **random name** (`3f9c...e1.png`) with the original extension, so uploads
  cannot collide or overwrite each other and the user does not choose the path.
- With `name`, the name is cleaned the same way; an empty result raises `ValueError`.
- An **existing file is never overwritten**: `FileExistsError`.
- The directory is created when missing.

Store the *generated* name in your database if you need to find the file again.

## Validation rules

| Rule | Passes when |
|---|---|
| `required` | a non-empty file was sent |
| `file` | the field is an uploaded file (not plain text) |
| `mimes:png,jpg` | the file's **extension** is one of the list |
| `max_kb:N` | size is at most N kilobytes |

Other rules (`string`, `min`, ...) do not apply to files. Failures give the usual 422 response; see
[Validation](validation.md).

> `mimes` looks at the **file name extension**, which the sender controls. It stops mistakes, not
> attackers. For images that you will process, also open them with an image library, and **never serve
> user uploads as HTML or scripts**.

## Limits

- The whole body is read **into memory**. The default maximum is **10 MB**; larger requests get
  `413 Payload Too Large` before they are read. Change it in `.env`: `MAX_BODY_MB=25`.
- Set the same limit on your reverse proxy (nginx: `client_max_body_size 25m;`).
- Not suitable for very large files (videos, archives): use direct-to-storage uploads for those.

## Where to store files

| Place | Use for |
|---|---|
| `storage/uploads/` (not web-accessible) | private files; serve through a controller that checks permissions |
| `public/uploads/` | files that anyone may download, e.g. avatars. They are then served at `/uploads/<name>` |

Serving a private file through a controller:

```python
def download(self, request, name: str):
    safe = UploadedFile.clean_name(name)                       # also blocks ../
    path = os.path.join("storage", "uploads", safe)
    if not os.path.isfile(path):
        self.not_found()
    with open(path, "rb") as f:
        return Response(f.read(), 200, content_type="application/octet-stream").with_header(
            "Content-Disposition", f'attachment; filename="{safe}"')
```

(`from pylara.http.uploads import UploadedFile`.)

## Testing

```python
response = client.post(
    "/avatar",
    data={"name": "Ana"},                                   # text fields
    files={"avatar": ("me.png", b"\x89PNG...", "image/png")},
)
```

`files` maps a field name to `(filename, content)` or `(filename, content, content_type)`.
