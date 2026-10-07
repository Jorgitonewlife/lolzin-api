"""Pydantic response schemas."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ChampionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    title: str
    role: str | None
    region: str | None
    difficulty: int | None
    release_year: int | None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str | None
    cost: int | None
    description: str | None


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    champion_id: int
    champion_name: str
    player: str
    kills: int
    deaths: int
    assists: int
    duration_minutes: int
    victory: bool
    played_at: datetime
    source: str
    kda: float
    item_names: list[str]


class ChampionPerformance(BaseModel):
    champion_id: int
    name: str
    role: str | None
    games: int
    wins: int
    win_rate: float
    avg_kda: float
    last_played: datetime


class ItemPerformance(BaseModel):
    item_id: int
    name: str
    category: str | None
    games: int
    wins: int
    win_rate: float
    avg_kda: float


class TimelinePoint(BaseModel):
    period: date
    games: int
    wins: int
    win_rate: float
    avg_kda: float


class SyncResult(BaseModel):
    synced: int
    skipped: int
    match_ids: list[str]
