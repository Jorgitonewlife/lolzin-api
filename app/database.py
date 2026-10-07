"""Database engine and session management."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Local infrastructure: the values are wired by docker-compose, not secrets.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://lolzin:lolzin_dev_password@db:5432/lolzin",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def get_db():
    """FastAPI dependency that yields a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
