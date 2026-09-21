"""Database engine and session management.

Uses SQLAlchemy with an SQLite backend. WAL mode is enabled for fast,
concurrent reads and a short startup time. Each instance owns its own DB
file under the OS app-data directory.

Performance PRAGMAs applied at connection time:
  - WAL journal mode (concurrent readers, fast writes)
  - synchronous=NORMAL (fast writes with WAL safety)
  - cache_size=-64000 (64 MB page cache)
  - mmap_size=268435456 (256 MB memory-mapped I/O)
  - temp_store=MEMORY (temp tables in RAM)
  - foreign_keys=ON (referential integrity)
  - busy_timeout=15000 (avoid lock errors under contention)
"""
from __future__ import annotations

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
        pool_pre_ping=False,
    )

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # Performance: WAL mode allows concurrent reads during writes
        cursor.execute("PRAGMA journal_mode=WAL")
        # Performance: NORMAL is fast; FULL is only needed without WAL
        cursor.execute("PRAGMA synchronous=NORMAL")
        # Performance: 64 MB page cache (default is 2 MB)
        cursor.execute("PRAGMA cache_size=-64000")
        # Performance: 256 MB memory-mapped I/O for faster reads
        cursor.execute("PRAGMA mmap_size=268435456")
        # Performance: store temp tables in memory
        cursor.execute("PRAGMA temp_store=MEMORY")
        # Integrity: enforce foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON")
        # Reliability: 15s busy timeout avoids lock errors
        cursor.execute("PRAGMA busy_timeout=15000")
        # Performance: multi-threaded query execution
        cursor.execute("PRAGMA threads=4")
        # Performance: store user_version for lightweight migration checks
        cursor.execute("PRAGMA user_version=2")
        cursor.close()

    _SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        return init_db()
    return _engine


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
