"""Tests for the daily email backup service.

SMTP is always mocked — no real network calls.
"""
from datetime import datetime, timezone
from typing import ClassVar

import pytest

from app.services import email_backup_service


def _config(**overrides):
    return {
        "enabled": True,
        "address": "me@gmail.com",
        "password": "x" * 16,
        "time": "19:00",
        "last_sent": "",
        "last_success": "",
        "last_error": "",
        **overrides,
    }


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------

def test_config_round_trip(db):
    errors = email_backup_service.save_email_backup_config(
        enabled=True, address="me@gmail.com", password="x" * 16, time_str="21:30")
    assert errors == []
    cfg = email_backup_service.get_email_backup_config()
    assert cfg["enabled"] is True
    assert cfg["address"] == "me@gmail.com"
    assert cfg["password"] == "x" * 16
    assert cfg["time"] == "21:30"


def test_validation_errors(db):
    errors = email_backup_service.save_email_backup_config(
        enabled=True, address="plain", password="", time_str="xx:xx")
    assert any("Gmail" in e for e in errors)
    assert any("App Password" in e for e in errors)
    assert any("valid backup time" in e for e in errors)

    # Disabled → everything is allowed (user is just unpicking the checkbox)
    errors = email_backup_service.save_email_backup_config(
        enabled=False, address="", password="", time_str="19:00")
    assert errors == []

    # Persisted even when disabled, in case the user toggles it back on later
    cfg = email_backup_service.get_email_backup_config()
    assert cfg["enabled"] is False
    assert cfg["address"] == ""
    assert cfg["time"] == "19:00"


def test_needs_gmail_address(db):
    errors = email_backup_service.save_email_backup_config(
        enabled=True, address="me@outlook.com", password="x" * 16, time_str="19:00")
    assert any("Gmail" in e for e in errors)


# ---------------------------------------------------------------------------
# Schedule logic
# ---------------------------------------------------------------------------

def test_should_send_now_after_scheduled_time():
    now = datetime(2026, 9, 5, 20, 0, tzinfo=timezone.utc)
    assert email_backup_service.should_send_now(_config(), now) is True


def test_should_send_now_before_scheduled_time():
    now = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
    assert email_backup_service.should_send_now(_config(), now) is False


def test_should_send_only_once_per_day():
    cfg = _config(last_sent="2026-09-05")
    now = datetime(2026, 9, 5, 21, 0, tzinfo=timezone.utc)
    assert email_backup_service.should_send_now(cfg, now) is False

    # Next day it is due again
    now2 = datetime(2026, 9, 6, 21, 0, tzinfo=timezone.utc)
    assert email_backup_service.should_send_now(cfg, now2) is True


def test_should_send_requires_enable_and_config(monkeypatch):
    now = datetime(2026, 9, 5, 21, 0, tzinfo=timezone.utc)
    assert email_backup_service.should_send_now(_config(enabled=False), now) is False
    assert email_backup_service.should_send_now(_config(address=""), now) is False
    assert email_backup_service.should_send_now(_config(password=""), now) is False
    assert email_backup_service.should_send_now(_config(time=""), now) is False
    assert email_backup_service.should_send_now(_config(time="not-a-time"), now) is False


# ---------------------------------------------------------------------------
# Send flow (mocked SMTP)
# ---------------------------------------------------------------------------

class FakeSMTP:
    """Records the SMTP session and hands back an in-memory that can fail."""

    fail_on_send = False
    instances: ClassVar[list] = []

    @classmethod
    def reset(cls):
        cls.instances = []
        cls.fail_on_send = False

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.calls = []
        FakeSMTP.instances.append(self)

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, msg):
        if FakeSMTP.fail_on_send:
            raise ConnectionError("mail server rejected")
        self.calls.append(("send", msg))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture()
def fake_smtp(monkeypatch):
    FakeSMTP.reset()
    monkeypatch.setattr(email_backup_service.smtplib, "SMTP", FakeSMTP)
    yield FakeSMTP


def _fake_backup(tmp_path):
    b = tmp_path / "furniture_backup_20260905.db"
    b.write_bytes(b"SQLITE DATA")
    return b


def test_send_email_success(db, tmp_path, fake_smtp):
    backup = _fake_backup(tmp_path)
    import unittest.mock
    with unittest.mock.patch.object(
        email_backup_service, "create_backup", return_value=backup
    ):
        result = email_backup_service.send_email_backup(_config())

    assert fake_smtp.instances[0].host == "smtp.gmail.com"
    assert fake_smtp.instances[0].port == 587
    smtp = fake_smtp.instances[0]
    assert "starttls" in smtp.calls
    assert ("login", "me@gmail.com", "x" * 16) in smtp.calls
    send_call = next(c for c in smtp.calls if c[0] == "send")
    msg = send_call[1]
    assert msg["To"] == "me@gmail.com"
    atts = list(msg.iter_attachments())
    assert len(atts) == 1
    assert atts[0].get_payload(decode=True) == b"SQLITE DATA"

    # Local temp file removed after a successful send
    assert result == backup
    assert not backup.exists()

    cfg = email_backup_service.get_email_backup_config()
    assert cfg["last_sent"] == datetime.now(timezone.utc).date().isoformat()
    assert cfg["last_error"] == ""


def test_send_email_keeps_local_with_flag(db, tmp_path, fake_smtp):
    backup = _fake_backup(tmp_path)
    import unittest.mock
    with unittest.mock.patch.object(
        email_backup_service, "create_backup", return_value=backup
    ):
        email_backup_service.send_email_backup(_config(), keep_local=True)
    assert backup.exists()


def test_send_failure_records_error_and_cleans_up(db, tmp_path, fake_smtp):
    backup = _fake_backup(tmp_path)
    fake_smtp.fail_on_send = True
    import unittest.mock
    with (
        unittest.mock.patch.object(
            email_backup_service, "create_backup", return_value=backup
        ),
        pytest.raises(ConnectionError),
    ):
        email_backup_service.send_email_backup(_config())
    assert not backup.exists()
    cfg = email_backup_service.get_email_backup_config()
    assert cfg["last_error"]
    assert cfg["last_success"] == ""


def test_send_not_enabled_raises(db, fake_smtp):
    with pytest.raises(ValueError):
        email_backup_service.send_email_backup(_config(enabled=False))


def test_send_inflight_guard(db, fake_smtp):
    email_backup_service._inflight = True
    try:
        with pytest.raises(RuntimeError):
            email_backup_service.send_email_backup(_config())
    finally:
        email_backup_service._inflight = False