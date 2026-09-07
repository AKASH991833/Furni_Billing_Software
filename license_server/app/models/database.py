"""Database engine and session management for the license server."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.models import Base

_engine = None
_SessionLocal: sessionmaker | None = None


def _build_engine(database_url: str):
    """Create the engine; in-memory SQLite needs a shared StaticPool."""
    if database_url in ("sqlite://", "sqlite:///:memory:"):
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(database_url, pool_pre_ping=True)


def init_db() -> None:
    """Create the engine and session factory; create tables if needed."""
    global _engine, _SessionLocal
    settings = get_settings()
    _engine = _build_engine(settings.database_url)
    _SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    Base.metadata.create_all(bind=_engine)


def get_session() -> Session:
    """Return a new session (caller must close it)."""
    if _SessionLocal is None:
        init_db()
    assert _SessionLocal is not None
    return _SessionLocal()


def close_db() -> None:
    """Dispose the engine (used in tests)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
