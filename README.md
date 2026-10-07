# lolzin-api

A small **League of Legends stats API** built with FastAPI and PostgreSQL:
champions, items and match history, plus per-role win-rate aggregation.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | Liveness probe |
| GET | `/api/champions` | `?role=Mid`, `?limit=50` |
| GET | `/api/champions/{id}` | 404 when missing |
| GET | `/api/items` | `?category=Crit` |
| GET | `/api/matches` | `?champion_id=1&victory=true` |
| GET | `/api/stats/roles` | Win rate and average KDA per role |
| GET | `/docs` | Swagger UI |

`/` serves a browsable landing page that reads from the API.

## Run it

```bash
docker compose -f docker-compose.base44.yml up -d --build
```

The stack is then on <http://localhost:3000>.

## Layout

```
app/
  main.py       FastAPI app, routes, static landing page
  models.py     SQLAlchemy models (Champion, Item, Match)
  schemas.py    Pydantic response schemas
  database.py   Engine and session factory
  seed.py       One-shot schema creation + demo data
static/
  index.html    Landing page
```
