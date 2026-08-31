"""Database engine and session management.

Uses SQLAlchemy with an SQLite backend. WAL mode is enabled for fast,
concurrent reads and a short startup time. Each instance owns its own DB
file under the OS app-data directory.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.utils.paths import db_path

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def init_db(db_file: Path | None = None) -> Engine:
    """Create the engine; must be called once at startup."""
    global _engine, _SessionLocal
    target = db_file or db_path()

    _engine = create_engine(
        f"sqlite:///{target}",
        connect_args={"check_same_thread": False, "timeout": 15},
        echo=False,
    )

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()

    _SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        return init_db()
    return _engine


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    s: Session = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session() -> Session:
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()


def close_db() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
