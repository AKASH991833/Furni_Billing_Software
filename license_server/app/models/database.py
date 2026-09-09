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
    # Fix Render's postgres:// to postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # Fallback to local SQLite if unconfigured or pointing to localhost default
    if not database_url or "CHANGE_ME@localhost" in database_url:
        from pathlib import Path
        db_file = Path("license_server.db").resolve()
        database_url = f"sqlite:///{db_file}"

    if database_url.startswith("sqlite"):
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            return create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
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
    _seed_default_products()


def _seed_default_products() -> None:
    """Pre-populate initial catalog if empty."""
    from sqlalchemy import select
    from app.models.models import Product

    session = get_session()
    try:
        existing = session.execute(select(Product)).first()
        if existing is None:
            defaults = [
                Product(
                    code="furniture_bill",
                    name="Furniture Billing Suite",
                    prefix="FB",
                    description="Commercial Desktop Furniture Billing & Estimation System",
                    is_active=True,
                    default_device_limit=1,
                ),
                Product(
                    code="ac_service",
                    name="AC Service & HVAC Manager",
                    prefix="AC",
                    description="AC Service, Maintenance & Invoicing Software",
                    is_active=True,
                    default_device_limit=1,
                ),
                Product(
                    code="general_billing",
                    name="General Commercial Billing",
                    prefix="GB",
                    description="Multi-Purpose Retail & Commercial Invoicing Software",
                    is_active=True,
                    default_device_limit=1,
                ),
            ]
            session.add_all(defaults)
            session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


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
