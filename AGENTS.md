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
  visible immediately: Python changes reload via `uvicorn --reload`, and everything
  under `static/` is read from disk on request (reload the browser, no restart needed).
- **Dependencies install on container start** from `requirements.txt`, cached in the
  `lolzin-pip-cache` volume. The first boot takes ~20–30s before it serves traffic;
  the healthcheck allows 75s of startup grace for this.
- **`WATCHFILES_FORCE_POLLING=1` is required.** Bind mounts on Linux do not reliably
  emit inotify events, so without polling uvicorn's reloader silently misses edits.
- **Seeding is a one-shot service.** `seed` runs `python -m app.seed` after Postgres
  is healthy and exits; `api` starts only on `service_completed_successfully`. The
  seed is idempotent — it skips entirely when champions already exist.
- **Database credentials are local dev values** (`lolzin` / `lolzin_dev_password`),
  wired inline through compose `environment:`. They are not secrets.

## Schema changes need a volume reset

`app/seed.py` calls `Base.metadata.create_all`, which **creates missing tables but
never alters existing ones**. There is no migration tool. After changing a model,
recreate the database:

```bash
docker compose -f docker-compose.base44.yml down
docker volume rm lolzin-api_lolzin-db-data     # keeps lolzin-pip-cache
docker compose -f docker-compose.base44.yml up -d
```

This destroys stored matches. If real match data ever matters, replace this with
Alembic before the next schema change.

## Riot sync

`app/riot.py` pulls the latest matches for the Riot ID in the environment.

**Required settings** (declared in `.base44/environment.json`, delivered to
`/run/base44/app.env`, wired in compose as `env_file`):

| Name | Purpose |
| --- | --- |
| `RIOT_API_KEY` | Riot Games API key. **Development keys expire after 24 hours.** |
| `RIOT_ID` | Riot ID in the form `GameName#TAG`, e.g. `ShadowFox#BR1` |
| `RIOT_REGION` | Optional; platform routing. Defaults to `americas` (covers BR/NA/LAN/LAS/OCE). |

Neither is required at boot: without them the service starts normally and
`POST /api/sync/riot` returns **503** with a message naming the missing setting.
`GET /api/sync/status` reports whether the sync is configured, and deliberately does
not echo the Riot ID back to clients.

**How the sync works.** Riot ID → PUUID (`/riot/account/v1/...`) → recent match ids
(`/lol/match/v5/matches/by-puuid/...`) → each match (`/lol/match/v5/matches/{id}`),
keeping only the participant whose PUUID matches. Champion names, item names and item
costs come from **Data Dragon** (no key needed), cached in-process. Matches are keyed
by `riot_match_id`, so re-running the sync **skips what is already stored** — it is
safe to press repeatedly. Riot rate limits (429) are retried with backoff.

**Data provenance.** `Match.source` is `demo` for the bundled sample data and `riot`
for synced matches, and every stats endpoint accepts `?source=` so the two are never
silently mixed. Synced champions/items are created on demand; champions first seen
this way have NULL `role`/`region`/`difficulty`/`release_year` because Riot does not
expose them (the landing page renders those as "—").

## Verifying a change

```bash
curl -s localhost:3000/health
curl -s localhost:3000/api/sync/status
curl -s "localhost:3000/api/matches?limit=5"          # history, newest first
curl -s localhost:3000/api/stats/champions            # per-champion win rate
curl -s localhost:3000/api/stats/items                # per-item win rate
curl -s "localhost:3000/api/stats/timeline?champion_id=2"
curl -s -X POST localhost:3000/api/sync/riot          # 503 until credentials exist
```

The Data Dragon half of the sync and the champion/item upserts need no API key and
can be exercised directly inside the container, e.g.:

```bash
docker compose -f docker-compose.base44.yml exec -T api \
  python -c "from app.riot import _ddragon; c,i=_ddragon(); print(len(c), len(i))"
```

The authenticated half (match ids and match detail) can only be verified with a real
key pasted into the secrets card.
