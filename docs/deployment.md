# Deployment

The development server (`manage serve`) is single-threaded and for local use. In production run the
application with a **WSGI server**. The generated `wsgi.py` exposes `application`.

## Checklist

- [ ] `APP_DEBUG=false` (never show tracebacks to users)
- [ ] a **unique, secret `APP_KEY`** for the server (`python -m manage key:generate`); never reuse the development key
- [ ] `SESSION_SECURE=true` once you serve over HTTPS
- [ ] a production `.env` on the server (not committed), with the right `DB_DATABASE`
- [ ] `python -m manage migrate` run on every deploy
- [ ] a WSGI server behind a reverse proxy with HTTPS
- [ ] cookies set with `secure=True` once you serve over HTTPS
- [ ] a backup of the SQLite file

## WSGI servers

Both servers below were verified against a generated project.

### gunicorn (Linux / macOS)

```bash
python -m pip install gunicorn
python -m gunicorn wsgi:application --bind 127.0.0.1:8000 --workers 3
```

Use the default **sync** workers: each worker is a separate process with its own database
connection. Do **not** pass `--preload` (it would create the connection before forking and share it).

### waitress (Windows, or anywhere)

```bash
python -m pip install waitress
python -m waitress --listen=127.0.0.1:8000 --threads=1 wsgi:application
```

### Threads and SQLite

The connection created in `bootstrap/app.py` is shared by everything in that process. A threaded
server with several threads would let requests interleave on one connection, mixing their
transactions. Keep **one thread per process** (`--threads=1` for waitress, sync workers for
gunicorn) and scale with processes. For file databases, `bootstrap/app.py` enables
`PRAGMA journal_mode=WAL` so several processes can read while one writes.

## Reverse proxy (nginx)

```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Add `client_max_body_size 10m;` (matching `MAX_BODY_MB`) inside `server { }` if you accept uploads.
Setting `X-Forwarded-For` to `$remote_addr` (not appending) means `request.ip` cannot be spoofed by
clients. To let nginx serve static files, add `location /css/ { alias /srv/app/public/css/; }`.

## systemd service

```ini
[Unit]
Description=My PyLara app
After=network.target

[Service]
User=www-data
WorkingDirectory=/srv/app
ExecStart=/srv/app/.venv/bin/python -m gunicorn wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

## Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
ENV APP_DEBUG=false
CMD ["python", "-m", "gunicorn", "wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
```

Mount a volume for `storage/` so the SQLite file survives container restarts, and run
`python -m manage migrate` as a release step.

## Sessions in production

The file driver keeps sessions in `storage/sessions/`, shared by every worker **on that machine**
(verified with several gunicorn workers). Keep `storage/` on persistent disk (a Docker volume). Do not
use `SESSION_DRIVER=memory`: it is per process. Running the app on several machines needs the
session folder on shared storage or your own store. See [Sessions](sessions.md).

## Performance notes

Routes are matched in order, one by one; keep the number of routes reasonable. Templates are
cached; static files are read per request, so let the proxy serve `public/` when traffic grows.
For heavy, concurrent workloads consider a framework with async support; see
[Limitations](limitations.md).
