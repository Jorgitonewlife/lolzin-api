# AGENTS.md

## Running the app

```bash
docker compose -f docker-compose.base44.yml up -d
```

Web entry point: **http://localhost:3000** (single FastAPI process serves both the
JSON API and the landing page). Swagger UI is at `/docs`.

## Non-obvious setup facts

- **Source is bind-mounted, not baked.** `api` and `seed` both use the plain
  `python:3.12-slim` image with `./:/app`. There is no app Dockerfile, so edits are
  visible immediately: Python changes reload via `uvicorn --reload`, and
  `static/index.html` is read from disk on every request (no restart needed).
- **Dependencies install on container start** from `requirements.txt`, cached in the
  `lolzin-pip-cache` volume. The first boot of each service takes ~20–30s before it
  serves traffic; the compose healthcheck allows 75s of startup grace for this.
- **`WATCHFILES_FORCE_POLLING=1` is required.** Bind mounts on Linux do not reliably
  emit inotify events, so without polling uvicorn's reloader silently misses edits.
- **Seeding is a one-shot service.** `seed` runs `python -m app.seed` after Postgres
  is healthy and exits; `api` starts only on `service_completed_successfully`. The
  seed is idempotent — it skips when champions already exist.
- **Database credentials are local dev values** (`lolzin` / `lolzin_dev_password`),
  wired inline through compose `environment:`. They are not secrets and are not
  user-configurable.

## No external secrets required

The API is self-contained: Postgres runs in compose and there is no third-party
integration. `.base44/environment.json` therefore has an empty `secrets` list.

If an external credential is added later, do **not** put it under compose
`environment:` — add `env_file: /run/base44/app.env` as the LAST entry of the
affected service so the user's dashboard value always wins.

## Resetting data

The seed only loads data into an empty schema. To start over:

```bash
docker compose -f docker-compose.base44.yml down -v   # drops lolzin-db-data
docker compose -f docker-compose.base44.yml up -d
```

## Verifying a change

```bash
curl -s localhost:3000/health
curl -s localhost:3000/api/champions | head -c 200
curl -s "localhost:3000/api/champions?role=mid"
curl -s localhost:3000/api/stats/roles
curl -s -o /dev/null -w '%{http_code}\n' localhost:3000/api/champions/9999   # expect 404
```

`static/index.html` calls `/api/champions` and `/api/stats/roles`; if the page shows
"Could not reach the API", those two endpoints are broken.
