"""Authentication service — PIN-based login for desktop app.

Provides:
  - PIN hashing (SHA-256 with salt)
  - Login / logout
  - Session management (in-memory, not persisted)
  - Failed attempt tracking with lockout
  - PIN change
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 minutes
SESSION_TIMEOUT_SECONDS = 300  # 5 minutes auto-lock


# ---------------------------------------------------------------------------
# Session state (in-memory, not persisted)
# ---------------------------------------------------------------------------

@dataclass
class _Session:
    user_id: int | None = None
    username: str | None = None
    full_name: str | None = None
    last_activity: float = 0.0
    logged_in: bool = False


_session = _Session()

# Failed attempts: {username: {"count": int, "locked_until": float}}
_failed_attempts: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# PIN hashing
# ---------------------------------------------------------------------------

def _hash_pin(pin: str, salt: str = "furniturebill") -> str:
    """Hash a PIN with a salt using SHA-256."""
    return hashlib.sha256(f"{salt}:{pin}".encode()).hexdigest()


def verify_pin(pin: str, stored_hash: str, salt: str = "furniturebill") -> bool:
    """Verify a PIN against a stored hash."""
    return _hash_pin(pin, salt) == stored_hash


# ---------------------------------------------------------------------------
# Failed attempt tracking
# ---------------------------------------------------------------------------

def _check_lockout(username: str) -> float:
    """Check if username is locked out. Returns seconds remaining (0 = not locked)."""
    record = _failed_attempts.get(username)
    if not record:
        return 0.0
    if record["count"] < MAX_FAILED_ATTEMPTS:
        return 0.0
    remaining = record["locked_until"] - time.time()
    if remaining <= 0:
        # Lockout expired — reset
        _failed_attempts.pop(username, None)
        return 0.0
    return remaining


def _record_failed_attempt(username: str) -> None:
    """Record a failed login attempt. Locks out after MAX_FAILED_ATTEMPTS."""
    record = _failed_attempts.get(username, {"count": 0, "locked_until": 0.0})
    record["count"] = record.get("count", 0) + 1
    if record["count"] >= MAX_FAILED_ATTEMPTS:
        record["locked_until"] = time.time() + LOCKOUT_SECONDS
    _failed_attempts[username] = record


def _clear_failed_attempts(username: str) -> None:
    """Clear failed attempts on successful login."""
    _failed_attempts.pop(username, None)


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------

def login(pin: str) -> tuple[bool, str]:
    """Attempt login with PIN only (single admin user).

    Returns (success: bool, message: str).
    On success, the global session is activated.
    """
    from app.database.database import get_session
    from app.models.models import User

    pin = pin.strip()
    username = "admin"  # Single admin user

    if not pin:
        return False, "PIN is required."

    # Check lockout
    lockout_remaining = _check_lockout(username)
    if lockout_remaining > 0:
        minutes = int(lockout_remaining // 60) + 1
        return False, f"Account locked. Try again in {minutes} minute(s)."

    # Look up user
    session = get_session()
    try:
        user = session.query(User).filter_by(username=username, is_active=True).first()
        if user is None:
            _record_failed_attempt(username)
            return False, "Invalid PIN."

        # Verify PIN
        stored_hash = user.password_hash or ""
        if not stored_hash or not verify_pin(pin, stored_hash):
            _record_failed_attempt(username)
            remaining = _check_lockout(username)
            if remaining > 0:
                minutes = int(remaining // 60) + 1
                return False, f"Too many failed attempts. Locked for {minutes} min."
            return False, "Invalid PIN."

        # Success
        _clear_failed_attempts(username)
        _session.user_id = user.id
        _session.username = user.username
        _session.full_name = user.full_name
        _session.last_activity = time.time()
        _session.logged_in = True

        # Update last_login timestamp
        from datetime import datetime, timezone
        user.last_login = datetime.now(timezone.utc)
        session.commit()

        return True, "Login successful."
    finally:
        session.close()


def logout() -> None:
    """Log out the current user."""
    _session.user_id = None
    _session.username = None
    _session.full_name = None
    _session.logged_in = False


def is_logged_in() -> bool:
    """Check if a user is currently logged in."""
    if not _session.logged_in:
        return False
    # Check session timeout
    if time.time() - _session.last_activity > SESSION_TIMEOUT_SECONDS:
        logout()
        return False
    return True


def touch() -> None:
    """Update last activity timestamp (call on user interaction)."""
    if _session.logged_in:
        _session.last_activity = time.time()


def current_user() -> dict | None:
    """Return current user info or None if not logged in."""
    if not is_logged_in():
        return None
    return {
        "user_id": _session.user_id,
        "username": _session.username,
        "full_name": _session.full_name,
    }


# ---------------------------------------------------------------------------
# PIN Management
# ---------------------------------------------------------------------------

def change_pin(old_pin: str, new_pin: str) -> tuple[bool, str]:
    """Change the PIN for admin user.

    Returns (success, message).
    """
    old_pin = old_pin.strip()
    new_pin = new_pin.strip()

    if not old_pin or not new_pin:
        return False, "Both old and new PIN are required."

    if len(new_pin) < 4 or len(new_pin) > 6:
        return False, "PIN must be 4-6 digits."

    if not new_pin.isdigit():
        return False, "PIN must contain only digits."

    from app.database.database import get_session
    from app.models.models import User

    session = get_session()
    try:
        user = session.query(User).filter_by(username="admin", is_active=True).first()
        if user is None:
            return False, "User not found."

        # Verify old PIN
        stored_hash = user.password_hash or ""
        if not stored_hash or not verify_pin(old_pin, stored_hash):
            return False, "Current PIN is incorrect."

        # Set new PIN
        user.password_hash = _hash_pin(new_pin)
        session.commit()

        return True, "PIN changed successfully."
    finally:
        session.close()


def setup_pin(username: str, pin: str) -> tuple[bool, str]:
    """Set PIN for a user (first-time setup or reset).

    Returns (success, message).
    """
    username = username.strip().lower()
    pin = pin.strip()

    if not pin:
        return False, "PIN is required."

    if len(pin) < 4 or len(pin) > 6:
        return False, "PIN must be 4-6 digits."

    if not pin.isdigit():
        return False, "PIN must contain only digits."

    from app.database.database import get_session
    from app.models.models import User

    session = get_session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if user is None:
            return False, "User not found."

        user.password_hash = _hash_pin(pin)
        session.commit()

        return True, "PIN set successfully."
    finally:
        session.close()


# ---------------------------------------------------------------------------
# PIN Recovery (Forgot PIN)
# ---------------------------------------------------------------------------

# Temporary storage for verified recovery (in-memory, not persisted)
_recovery_verified: bool = False


def recover_pin(mobile: str, first_name: str) -> tuple[bool, str]:
    """Verify identity using mobile number + first name from business profile.

    Both are compared in lowercase against the business profile.
    Returns (success, message).
    """
    global _recovery_verified
    from app.services.business_service import get_profile

    profile = get_profile()
    if profile is None:
        return False, "Business profile not found."

    # Get stored values (lowercase)
    stored_mobile = (profile.mobile or "").lower().strip()
    stored_name = (profile.owner_name or "").lower().strip()

    # Clean input
    raw = mobile.lower().strip()  # mobile param holds the combined input
    first_name = first_name.lower().strip()

    # Parse combined input: extract digits (mobile) and letters (name)
    digits = "".join(c for c in raw if c.isdigit())
    letters = "".join(c for c in raw if c.isalpha())

    # Use extracted mobile if digits found, otherwise use original
    mobile = digits[-10:] if len(digits) >= 10 else digits
    # Use extracted name if letters found, otherwise use original first_name
    name = letters if letters else first_name

    # Extract first name from owner_name (skip titles like mr/mrs/ms/dr)
    _titles = {"mr", "mrs", "ms", "dr", "shri", "smt", "miss"}
    name_parts = stored_name.split()
    stored_first = ""
    for part in name_parts:
        if part not in _titles:
            stored_first = part
            break

    # Check mobile match (last 10 digits)
    mobile_match = stored_mobile[-10:] == mobile[-10:] if len(mobile) >= 10 and len(stored_mobile) >= 10 else stored_mobile == mobile

    # Check name match (first name only)
    name_match = stored_first == name

    if mobile_match and name_match:
        _recovery_verified = True
        return True, "Identity verified!"
    else:
        return False, "Verification failed. Please check your information and try again."


def set_new_pin(pin: str) -> tuple[bool, str]:
    """Set a new PIN after successful recovery.

    Must call recover_pin() first to verify identity.
    """
    global _recovery_verified

    if not _recovery_verified:
        return False, "Please verify your identity first."

    pin = pin.strip()
    if not pin:
        return False, "PIN is required."

    if len(pin) < 4 or len(pin) > 6:
        return False, "PIN must be 4-6 digits."

    if not pin.isdigit():
        return False, "PIN must contain only digits."

    from app.database.database import get_session
    from app.models.models import User

    session = get_session()
    try:
        user = session.query(User).filter_by(username="admin", is_active=True).first()
        if user is None:
            return False, "User not found."

        user.password_hash = _hash_pin(pin)
        session.commit()
        _recovery_verified = False  # Reset after use

        return True, "PIN reset successfully!"
    finally:
        session.close()
