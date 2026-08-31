"""Backup / restore service.

Backups the whole SQLite file (all business data) with a safe copy.
Restore swaps the active DB after closing all connections.
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from app.database import database
from app.utils.paths import backup_dir, data_dir, db_path


def create_backup(destination: Path | None = None) -> Path:
    src = db_path()
    if not src.exists():
        raise FileNotFoundError("Database not found yet.")
    if destination is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = backup_dir() / f"furniture_backup_{stamp}.db"

    # Use SQLite backup API for a consistent snapshot.
    dst = sqlite3.connect(str(destination))
    src_con = sqlite3.connect(str(src))
    try:
        src_con.backup(dst)
    finally:
        dst.close()
        src_con.close()
    return destination


def list_backups() -> list[Path]:
    d = backup_dir()
    if not d.exists():
        return []
    return sorted(d.glob("furniture_backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)


def restore_backup(source: Path) -> Path:
    """Restore the active DB from a backup file (must not be running editor)."""
    src = Path(source)
    if not src.exists():
        raise FileNotFoundError("Backup file not found.")

    database.close_db()
    target = db_path()

    # Swap to a temp file then replace to avoid corruption.
    tmp = data_dir() / "furniture_restore_tmp.db"
    shutil.copyfile(src, tmp)

    if target.exists():
        target.unlink()
    shutil.move(str(tmp), str(target))

    # clear WAL/shm
    for suffix in ("-wal", "-shm"):
        p = Path(str(target) + suffix)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    database.init_db()
    return target
