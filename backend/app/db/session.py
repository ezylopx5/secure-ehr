"""Engine/session factory. SQLite for development, PostgreSQL for production
(chosen purely by ``DATABASE_URL``); dev bootstraps schemas via create_all.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)
_settings = get_settings()

_connect_args = (
    {"check_same_thread": False}
    if _settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    _settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def reset_engine() -> None:
    """Rebind ``engine`` and ``SessionLocal`` to the current ``get_settings().DATABASE_URL``."""
    global engine, _connect_args
    settings = get_settings()
    _connect_args = (
        {"check_same_thread": False}
        if settings.DATABASE_URL.startswith("sqlite")
        else {}
    )
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=_connect_args,
        pool_pre_ping=True,
    )
    SessionLocal.configure(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables (dev) - production uses `alembic upgrade head`."""
    from app.db import models  # noqa: F401  (register mappers)
    from app.db.base import Base

    reset_engine()
    Base.metadata.create_all(bind=engine)
    log.info("Database schema ready (%s)", get_settings().DATABASE_URL.split("://")[0])
