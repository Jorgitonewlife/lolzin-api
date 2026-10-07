# lolzin-api

A small **League of Legends stats API** built with FastAPI and PostgreSQL: match
history, champion and item performance, and a Riot API sync that pulls your own
recent games.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | Liveness probe |
| GET | `/api/champions` | `?role=Mid`, `?limit=50` |
| GET | `/api/champions/{id}` | 404 when missing |
| GET | `/api/items` | `?category=Crit` |
| GET | `/api/matches` | History, newest first. `?source=riot`, `?victory=true` |
| GET | `/api/stats/champions` | Games, win rate, avg KDA per champion |
| GET | `/api/stats/items` | Games, win rate, avg KDA per item |
| GET | `/api/stats/timeline` | Weekly trend. `?champion_id=`, `?item_id=` |
| GET | `/api/stats/roles` | Win rate and average KDA per role |
| GET | `/api/sync/status` | Whether the Riot sync is configured |
| POST | `/api/sync/riot` | Pull recent matches. `?count=20` |
| GET | `/docs` | Swagger UI |

`/` serves a browsable page with match history, performance tables and a sync button.

## Riot sync

Add your **Riot API key** (from <https://developer.riotgames.com>) and your
**Riot ID** (`GameName#TAG`) in the project secrets, then press *Sync now* on the
landing page — or:

```bash
curl -X POST localhost:3000/api/sync/riot
```

Development keys expire after 24 hours; a production key needs Riot's approval.
Already-stored matches are skipped, so the sync is safe to run repeatedly. Synced
data is tagged `source: "riot"` and the bundled sample data `source: "demo"`, so the
two can be viewed separately with the data-source filter.

## Run it

```bash
docker compose -f docker-compose.base44.yml up -d
```

The stack is then on <http://localhost:3000>.

## Layout

```
app/
  main.py       FastAPI app, routes, static landing page
  models.py     SQLAlchemy models (Champion, Item, Match, match_items)
  schemas.py    Pydantic response schemas
  database.py   Engine and session factory
  riot.py       Riot API client, Data Dragon lookup, match sync
  seed.py       One-shot schema creation + demo data
static/
  index.html    Landing page
  app.css       Styles
  app.js        Data loading and rendering
```
