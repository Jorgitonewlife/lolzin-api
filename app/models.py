"""SQLAlchemy models for the lolzin-api domain."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Items built during a match — many-to-many.
match_items = Table(
    "match_items",
    Base.metadata,
    Column("match_id", ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True),
    Column("item_id", ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
)


class Champion(Base):
    __tablename__ = "champions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(120), default="")
    # Curated detail. Populated for hand-seeded champions; NULL for champions
    # first seen through a Riot sync, since the Riot API does not expose them.
    role: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    region: Mapped[str | None] = mapped_column(String(60), nullable=True)
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    matches: Mapped[list["Match"]] = relationship(
        back_populates="champion", cascade="all, delete-orphan"
    )


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(String(240), nullable=True)
    # Riot's numeric item id, filled in for items resolved from Data Dragon.
    riot_item_id: Mapped[int | None] = mapped_column(
        Integer, unique=True, nullable=True
    )

    matches: Mapped[list["Match"]] = relationship(
        secondary=match_items, back_populates="items"
    )


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    champion_id: Mapped[int] = mapped_column(
        ForeignKey("champions.id", ondelete="CASCADE"), index=True
    )
    player: Mapped[str] = mapped_column(String(60))
    kills: Mapped[int] = mapped_column(Integer)
    deaths: Mapped[int] = mapped_column(Integer)
    assists: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    victory: Mapped[bool] = mapped_column(Boolean)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # "demo" for the bundled sample data, "riot" for matches pulled from the API.
    source: Mapped[str] = mapped_column(String(16), default="demo", index=True)
    # Riot's match id; keeps re-syncing idempotent. NULL for demo matches.
    riot_match_id: Mapped[str | None] = mapped_column(
        String(40), unique=True, nullable=True
    )

    champion: Mapped[Champion] = relationship(back_populates="matches")
    items: Mapped[list[Item]] = relationship(
        secondary=match_items, back_populates="matches"
    )

    @property
    def kda(self) -> float:
        """Kill/death/assist ratio, treating a deathless game as full value."""
        return round((self.kills + self.assists) / max(self.deaths, 1), 2)

    @property
    def champion_name(self) -> str:
        return self.champion.name

    @property
    def item_names(self) -> list[str]:
        return [item.name for item in self.items]
