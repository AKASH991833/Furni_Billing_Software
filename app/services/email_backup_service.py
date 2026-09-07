"""Daily email backup service.

Automatically emails the SQLite database (via the existing backup API) to a
Gmail address using a Gmail App Password. Config is stored in the ``settings``
table so it survives app restarts and local backups.

SMTP specifics (Gmail App Password flow):
  * host smtp.gmail.com:587, STARTTLS, LOGIN auth.
  * The password must be a 16-character Gmail App Password, never the account
    main password.
"""
from __future__ import annotations

import smtplib
import threading
from datetime import datetime, time, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr
from pathlib import Path

from app.database.database import get_session
from app.models.models import Setting
from app.utils.validators import validate_email

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587

_PREF_KEYS = (
    "email_backup_enabled",
    "email_backup_address",
    "email_backup_password",
    "email_backup_time",
    "email_backup_last_sent",
    "email_backup_last_success",
    "email_backup_last_error",
)
_ENABLED_KEY = "email_backup_enabled"
_ADDRESS_KEY = "email_backup_address"
_PASSWORD_KEY = "email_backup_password"
_TIME_KEY = "email_backup_time"
_LAST_SENT_KEY = "email_backup_last_sent"
_LAST_SUCCESS_KEY = "email_backup_last_success"
_LAST_ERROR_KEY = "email_backup_last_error"

DEFAULT_TIME = "19:00"

# Guards against two timer ticks firing a send before the first finishes.
_inflight_lock = threading.Lock()
_inflight = False


def _get_all_settings() -> dict[str, str]:
    session = get_session()
    try:
        rows = session.query(Setting).filter(Setting.key.in_(_PREF_KEYS)).all()
        return {r.key: (r.value or "") for r in rows}
    finally:
        session.close()


def _set_setting(key: str, value: str) -> None:
    session = get_session()
    try:
        row = session.query(Setting).filter_by(key=key).first()
        if row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
        session.commit()
    finally:
        session.close()


def get_email_backup_config() -> dict:
    """Load the persisted email backup settings (safe defaults)."""
    raw = _get_all_settings()
    return {
        "enabled": raw.get(_ENABLED_KEY, "0") == "1",
        "address": raw.get(_ADDRESS_KEY, "").strip(),
        "password": raw.get(_PASSWORD_KEY, ""),
        "time": raw.get(_TIME_KEY, "") or DEFAULT_TIME,
        "last_sent": raw.get(_LAST_SENT_KEY, ""),
        "last_success": raw.get(_LAST_SUCCESS_KEY, ""),
        "last_error": raw.get(_LAST_ERROR_KEY, ""),
    }


def save_email_backup_config(enabled: bool, address: str, password: str,
                             time_str: str) -> list[str]:
    """Persist config, returning a list of validation errors (empty = OK)."""
    errors: list[str] = []
    address = (address or "").strip()
    time_str = (time_str or "").strip()

    if enabled:
        perr = validate_email(address)
        if perr:
            errors.append("Enter a valid Gmail address.")
        elif not address.lower().endswith("@gmail.com"):
            errors.append("Enter a valid Gmail address (name@gmail.com).")
        if not password:
            errors.append("Gmail App Password is required (16 characters).")
        elif len(password) < 8:
            errors.append("Gmail App Password looks too short (16 characters).")
        if _parse_time(time_str) is None:
            errors.append("Select a valid backup time.")

    _set_setting(_ENABLED_KEY, "1" if enabled else "0")
    _set_setting(_ADDRESS_KEY, address)
    _set_setting(_PASSWORD_KEY, password)
    _set_setting(_TIME_KEY, time_str or DEFAULT_TIME)
    return errors


def _parse_time(time_str: str):
    """Parse 'HH:MM' into a ``datetime.time`` object (or None if invalid)."""
    try:
        hh, mm = str(time_str or "").split(":", 1)
        return time(int(hh), int(mm))
    except (ValueError, TypeError):
        return None


def should_send_now(config: dict, now: datetime | None = None) -> bool:
    """``True`` when a daily backup is due (enabled, configured, time reached,
    and not already sent today)."""
    if not config.get("enabled"):
        return False
    if not config.get("address") or not config.get("password"):
        return False
    due_time = _parse_time(str(config.get("time") or ""))
    if due_time is None:
        return False
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    if config.get("last_sent") == today:
        return False
    # Send once per day: any time application is running at/after the chosen
    # daily slot. Catches the case where the app was closed at the exact minute.
    return now.time().replace(tzinfo=None) >= due_time


def _record_success() -> None:
    now = datetime.now(timezone.utc)
    _set_setting(_LAST_SENT_KEY, now.date().isoformat())
    _set_setting(_LAST_SUCCESS_KEY, f"{now.strftime('%d %b %Y, %H:%M')} UTC")
    _set_setting(_LAST_ERROR_KEY, "")


def _record_error(message: str) -> None:
    _set_setting(_LAST_ERROR_KEY, message[:500])
    _set_setting(_LAST_SUCCESS_KEY, "")


def _build_message(address: str, backup_file: Path, now: datetime) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Furniture Bill Backup ({now.strftime('%d %b %Y')})"
    msg["From"] = formataddr(("Furniture Bill", address))
    msg["To"] = address
    msg["Date"] = format_datetime(now)
    business = ""
    try:
        from app.services.business_service import get_profile
        profile = get_profile()
        if profile and profile.business_name:
            business = f"\nBusiness: {profile.business_name}"
    except Exception:  # noqa: BLE001
        business = ""
    msg.set_content(
        "Your Furniture Bill database backup is attached.\n"
        f"File: {backup_file.name}\n"
        f"Size: {backup_file.stat().st_size // 1024} KB\n"
        f"Created: {now.strftime('%d %b %Y, %H:%M UTC')}{business}\n\n"
        "Keep this email as a safety copy of your business data."
    )
    msg.add_attachment(
        backup_file.read_bytes(),
        maintype="application",
        subtype="octet-stream",
        filename=backup_file.name,
    )
    return msg


def send_email_backup(config: dict | None = None, keep_local: bool = False) -> Path:
    """Create a backup and email it to the configured Gmail address.

    Runs synchronously — call it from a background thread. Returns the local
    backup path on success (deleted afterwards unless ``keep_local``).

    Raises:
        ValueError: not configured / already sending.
        OSError/smtplib errors: network, auth or send failures.
    """
    global _inflight
    with _inflight_lock:
        if _inflight:
            raise RuntimeError("A backup email is already being sent.")
        _inflight = True
    try:
        config = config or get_email_backup_config()
        address = (config.get("address") or "").strip()
        password = config.get("password") or ""
        if not config.get("enabled"):
            raise ValueError("Daily email backup is not enabled.")
        if not address or not password:
            raise ValueError("Email backup is not configured.")

        backup_file = create_backup()
        now = datetime.now(timezone.utc)
        try:
            msg = _build_message(address, backup_file, now)
            with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(address, password)
                server.send_message(msg)
        except Exception:
            _record_error("Send failed — check the Gmail App Password.")
            raise
        finally:
            if not keep_local:
                try:
                    backup_file.unlink()
                except OSError:
                    pass
        _record_success()
        return backup_file
    finally:
        with _inflight_lock:
            _inflight = False


def create_backup():
    """Indirection over backup_service.create_backup for easy test mocking."""
    from app.services.backup_service import create_backup as _cb
    return _cb()