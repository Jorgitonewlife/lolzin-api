"""FastAPI application exposing League of Legends champions, items and matches."""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Champion, Item, Match
from app.schemas import ChampionOut, ItemOut, MatchOut

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="lolzin-api",
    description="A small League of Legends stats API: champions, items and match history.",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe used by the container healthcheck."""
    return {"status": "ok"}


@app.get("/api/champions", response_model=list[ChampionOut], tags=["champions"])
def list_champions(
    role: str | None = Query(None, description="Filter by role, e.g. Mid"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List champions, optionally filtered by role."""
    stmt = select(Champion)
    if role:
        stmt = stmt.where(func.lower(Champion.role) == role.lower())
    stmt = stmt.order_by(Champion.name).limit(limit)
    return db.scalars(stmt).all()


@app.get("/api/champions/{champion_id}", response_model=ChampionOut, tags=["champions"])
def get_champion(champion_id: int, db: Session = Depends(get_db)):
    """Fetch a single champion by id."""
    champion = db.get(Champion, champion_id)
    if champion is None:
        raise HTTPException(status_code=404, detail="Champion not found")
    return champion


@app.get("/api/items", response_model=list[ItemOut], tags=["items"])
def list_items(
    category: str | None = Query(None, description="Filter by category, e.g. Crit"),
    db: Session = Depends(get_db),
):
    """List items, optionally filtered by category."""
    stmt = select(Item)
    if category:
        stmt = stmt.where(func.lower(Item.category) == category.lower())
    return db.scalars(stmt.order_by(Item.cost.desc())).all()


@app.get("/api/matches", response_model=list[MatchOut], tags=["matches"])
def list_matches(
    champion_id: int | None = Query(None, description="Only matches on this champion"),
    victory: bool | None = Query(None, description="Only wins (true) or losses (false)"),
    db: Session = Depends(get_db),
):
    """List recent matches with filters."""
    stmt = select(Match)
    if champion_id is not None:
        stmt = stmt.where(Match.champion_id == champion_id)
    if victory is not None:
        stmt = stmt.where(Match.victory.is_(victory))
    return db.scalars(stmt.order_by(Match.id)).all()


@app.get("/api/stats/roles", tags=["stats"])
def role_stats(db: Session = Depends(get_db)):
    """Win rate and average KDA aggregated per role."""
    kda = (func.sum(Match.kills) + func.sum(Match.assists)) / func.greatest(
        func.sum(Match.deaths), 1
    )

    rows = db.execute(
        select(
            Champion.role,
            func.count(func.distinct(Champion.id)).label("champions"),
            func.count(Match.id).label("matches"),
            func.coalesce(
                func.sum(case((Match.victory.is_(True), 1), else_=0)), 0
            ).label("wins"),
            func.coalesce(kda, 0).label("avg_kda"),
        )
        .join(Match, Match.champion_id == Champion.id, isouter=True)
        .group_by(Champion.role)
        .order_by(Champion.role)
    ).all()

    return [
        {
            "role": row.role,
            "champions": row.champions,
            "matches": row.matches,
            "wins": row.wins,
            "win_rate": round(row.wins / row.matches * 100, 1) if row.matches else 0.0,
            "avg_kda": round(float(row.avg_kda), 2),
        }
        for row in rows
    ]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve the small browsable landing page."""
    return FileResponse(STATIC_DIR / "index.html")
