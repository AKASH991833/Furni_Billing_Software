"""Application-wide path helpers.

Keeps all user data inside the OS app-data folder so nothing is hardcoded
and each install has its own independent data location.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _base_dir() -> Path:
    """Return directory that contains the project files (source or frozen)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def data_dir() -> Path:
    """Directory for mutable application data (DB, backup, logo cache)."""
    if os.environ.get("FURNITURE_BILL_DATA"):
        p = Path(os.environ["FURNITURE_BILL_DATA"])
    else:
        base = os.environ.get("APPDATA") or str(Path.home())
        p = Path(base) / "FurnitureBill" / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / "furniture.db"


def backup_dir() -> Path:
    p = data_dir() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resources_dir() -> Path:
    return _base_dir() / "app" / "resources"


def icons_dir() -> Path:
    return resources_dir() / "icons"
