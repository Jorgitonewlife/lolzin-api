"""FastAPI application exposing League of Legends champions, items and matches."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Champion, Item, Match, match_items
from app.riot import (
    DEFAULT_REGION,
    RiotError,
    RiotNotConfigured,
    riot_configured,
    sync_matches,
)
from app.schemas import (
    ChampionOut,
    ChampionPerformance,
    ItemOut,
    ItemPerformance,
    MatchOut,
    SyncResult,
    TimelinePoint,
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="lolzin-api",
    description="A small League of Legends stats API: champions, items and match history.",
    version="0.2.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _wins():
    return func.sum(case((Match.victory.is_(True), 1), else_=0))


def _avg_kda():
    return (func.sum(Match.kills) + func.sum(Match.assists)) / func.greatest(
        func.sum(Match.deaths), 1
    )


def _win_rate(wins: int, games: int) -> float:
    return round(wins / games * 100, 1) if games else 0.0


def _cutoff(days: int | None) -> datetime | None:
    """The oldest moment to include, or None when no time filter applies."""
    if not days:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe used by the container healthcheck."""
    return {"status": "ok"}


# --- Reference data ---------------------------------------------------------


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
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List items, optionally filtered by category."""
    stmt = select(Item)
    if category:
        stmt = stmt.where(func.lower(Item.category) == category.lower())
    return db.scalars(stmt.order_by(Item.cost.desc().nullslast()).limit(limit)).all()


# --- Match history ----------------------------------------------------------


@app.get("/api/matches", response_model=list[MatchOut], tags=["matches"])
def list_matches(
    champion_id: int | None = Query(None, description="Only matches on this champion"),
    victory: bool | None = Query(None, description="Only wins (true) or losses (false)"),
    source: str | None = Query(None, description="demo or riot"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Recent matches, newest first, with the items that were built."""
    stmt = (
        select(Match)
        .options(selectinload(Match.champion), selectinload(Match.items))
        .order_by(Match.played_at.desc(), Match.id.desc())
        .limit(limit)
    )
    if champion_id is not None:
        stmt = stmt.where(Match.champion_id == champion_id)
    if victory is not None:
        stmt = stmt.where(Match.victory.is_(victory))
    if source:
        stmt = stmt.where(Match.source == source)
    return db.scalars(stmt).all()


# --- Performance over time --------------------------------------------------


@app.get(
    "/api/stats/champions",
    response_model=list[ChampionPerformance],
    tags=["stats"],
)
def champion_performance(
    days: int | None = Query(None, ge=1, le=3650, description="Only the last N days"),
    source: str | None = Query(None, description="demo or riot"),
    min_games: int = Query(1, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Games, win rate and average KDA per champion."""
    games = func.count(Match.id)
    wins = _wins()

    stmt = (
        select(
            Champion.id,
            Champion.name,
            Champion.role,
            games.label("games"),
            wins.label("wins"),
            _avg_kda().label("avg_kda"),
            func.max(Match.played_at).label("last_played"),
        )
        .join(Match, Match.champion_id == Champion.id)
        .where(Match.played_at >= _cutoff(days) if days else True)
        .group_by(Champion.id, Champion.name, Champion.role)
        .having(games >= min_games)
        .order_by(games.desc(), Champion.name)
    )
    if source:
        stmt = stmt.where(Match.source == source)

    return [
        {
            "champion_id": row.id,
            "name": row.name,
            "role": row.role,
            "games": row.games,
            "wins": row.wins,
            "win_rate": _win_rate(row.wins, row.games),
            "avg_kda": round(float(row.avg_kda), 2),
            "last_played": row.last_played,
        }
        for row in db.execute(stmt)
    ]


@app.get("/api/stats/items", response_model=list[ItemPerformance], tags=["stats"])
def item_performance(
    days: int | None = Query(None, ge=1, le=3650, description="Only the last N days"),
    source: str | None = Query(None, description="demo or riot"),
    min_games: int = Query(1, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Games, win rate and average KDA per item, across every match it was built in."""
    games = func.count(Match.id)
    wins = _wins()

    stmt = (
        select(
            Item.id,
            Item.name,
            Item.category,
            games.label("games"),
            wins.label("wins"),
            _avg_kda().label("avg_kda"),
        )
        .join(match_items, match_items.c.item_id == Item.id)
        .join(Match, Match.id == match_items.c.match_id)
        .where(Match.played_at >= _cutoff(days) if days else True)
        .group_by(Item.id, Item.name, Item.category)
        .having(games >= min_games)
        .order_by(games.desc(), Item.name)
    )
    if source:
        stmt = stmt.where(Match.source == source)

    return [
        {
            "item_id": row.id,
            "name": row.name,
            "category": row.category,
            "games": row.games,
            "wins": row.wins,
            "win_rate": _win_rate(row.wins, row.games),
            "avg_kda": round(float(row.avg_kda), 2),
        }
        for row in db.execute(stmt)
    ]


@app.get("/api/stats/timeline", response_model=list[TimelinePoint], tags=["stats"])
def performance_timeline(
    champion_id: int | None = Query(None, description="Trend a single champion"),
    item_id: int | None = Query(None, description="Trend a single item"),
    source: str | None = Query(None, description="demo or riot"),
    weeks: int = Query(12, ge=1, le=104),
    db: Session = Depends(get_db),
):
    """Weekly win rate and average KDA, overall or for one champion/item."""
    period = func.date_trunc("week", Match.played_at).label("period")
    games = func.count(Match.id)
    wins = _wins()

    stmt = select(
        period,
        games.label("games"),
        wins.label("wins"),
        _avg_kda().label("avg_kda"),
    ).select_from(Match)

    if item_id is not None:
        stmt = stmt.join(match_items, match_items.c.match_id == Match.id)
    stmt = stmt.where(Match.played_at >= _cutoff(days=weeks * 7))
    if champion_id is not None:
        stmt = stmt.where(Match.champion_id == champion_id)
    if item_id is not None:
        stmt = stmt.where(match_items.c.item_id == item_id)
    if source:
        stmt = stmt.where(Match.source == source)

    stmt = stmt.group_by(period).order_by(period)

    return [
        {
            "period": row.period.date(),
            "games": row.games,
            "wins": row.wins,
            "win_rate": _win_rate(row.wins, row.games),
            "avg_kda": round(float(row.avg_kda), 2),
        }
        for row in db.execute(stmt)
    ]


@app.get("/api/stats/roles", tags=["stats"])
def role_stats(db: Session = Depends(get_db)):
    """Win rate and average KDA aggregated per role."""
    role = func.coalesce(Champion.role, "Unknown").label("role")
    games = func.count(Match.id)
    wins = _wins()

    rows = db.execute(
        select(
            role,
            func.count(func.distinct(Champion.id)).label("champions"),
            games.label("games"),
            func.coalesce(wins, 0).label("wins"),
            func.coalesce(_avg_kda(), 0).label("avg_kda"),
        )
        .join(Match, Match.champion_id == Champion.id, isouter=True)
        .group_by(role)
        .order_by(role)
    ).all()

    return [
        {
            "role": row.role,
            "champions": row.champions,
            "matches": row.games,
            "wins": row.wins,
            "win_rate": _win_rate(row.wins, row.games),
            "avg_kda": round(float(row.avg_kda), 2),
        }
        for row in rows
    ]


# --- Riot sync --------------------------------------------------------------


@app.get("/api/sync/status", tags=["sync"])
def sync_status():
    """Whether the Riot sync has the settings it needs.

    Deliberately does not echo the configured Riot ID: it lives in the
    platform-managed secret file and is never read back out to clients.
    """
    return {
        "configured": riot_configured(),
        "region": os.getenv("RIOT_REGION", "").strip() or DEFAULT_REGION,
    }


@app.post("/api/sync/riot", response_model=SyncResult, tags=["sync"])
def sync_from_riot(
    count: int = Query(20, ge=1, le=100, description="How many recent matches to pull"),
    db: Session = Depends(get_db),
):
    """Pull the most recent matches for the configured Riot ID.

    Already-stored matches are skipped, so this is safe to run repeatedly.
    """
    try:
        return sync_matches(db, count=count)
    except RiotNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RiotError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve the small browsable landing page."""
    return FileResponse(STATIC_DIR / "index.html")
