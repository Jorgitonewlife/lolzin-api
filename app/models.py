"""SQLAlchemy models for the lolzin-api domain."""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Champion(Base):
    __tablename__ = "champions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(30), index=True)
    region: Mapped[str] = mapped_column(String(60))
    difficulty: Mapped[int] = mapped_column(Integer)
    release_year: Mapped[int] = mapped_column(Integer)

    matches: Mapped[list["Match"]] = relationship(
        back_populates="champion", cascade="all, delete-orphan"
    )


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    cost: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(240))


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

    champion: Mapped[Champion] = relationship(back_populates="matches")

    @property
    def kda(self) -> float:
        """Kill/death/assist ratio, treating a deathless game as full value."""
        return round((self.kills + self.assists) / max(self.deaths, 1), 2)
