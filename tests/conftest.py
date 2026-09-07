"""Shared pytest configuration — reusable DB fixtures for all service tests.

Uses ``StaticPool`` so every ``get_session()`` call from any service function
shares the same in-memory SQLite connection.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.models import Base


@pytest.fixture()
def db(tmp_path):
    """Yield a session against a fresh in-memory SQLite database.

    ``StaticPool`` ensures all connections hit the same in-memory DB.
    We patch ``_SessionLocal`` so every ``get_session()`` call creates
    sessions from our test engine.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestSession()

    import app.database.database as db_mod
    orig_engine = db_mod._engine
    orig_session_local = db_mod._SessionLocal

    db_mod._engine = engine
    db_mod._SessionLocal = TestSession

    from app.utils.cache import cache
    cache.clear()

    yield session

    db_mod._engine = orig_engine
    db_mod._SessionLocal = orig_session_local
    cache.clear()
    session.close()
    # Do NOT call engine.dispose() — StaticPool in-memory DB dies with the connection
