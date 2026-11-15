# PyLara demo

A small users / posts / token-auth API that exercises most of the framework. Run it from the
repository root after `python -m pip install -e .`:

```bash
cd examples/demo
python -m manage serve
python -m manage route:list
```

Demo account: `alice@example.com` / `secret`. The database is in memory and re-seeded on every start.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login -ContentType "application/json" -Body '{"email":"alice@example.com","password":"secret"}'
```

For a new project use `pylara new <name>` instead; this folder is only a reference.
