"""Pydantic response schemas."""

from pydantic import BaseModel, ConfigDict


class ChampionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    title: str
    role: str
    region: str
    difficulty: int
    release_year: int


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    cost: int
    description: str


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    champion_id: int
    player: str
    kills: int
    deaths: int
    assists: int
    duration_minutes: int
    victory: bool
    kda: float
