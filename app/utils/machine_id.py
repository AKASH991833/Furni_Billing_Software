"""Machine fingerprint for offline license binding.

Produces a stable, privacy-conscious identifier from a composite of cheap
hardware/OS facts. Everything is hashed, so no raw identifiers ever leave the
machine in a readable form.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import sys
import uuid
from ctypes import wintypes

_SYSTEM_DRIVE = os.environ.get("SystemDrive", "C:\\")


def _volume_serial() -> str:
    """Windows volume serial of the system drive (stable across reboots)."""
    if not sys.platform.startswith("win"):
        return ""
    try:
        vol_name = ctypes.create_unicode_buffer(261)
        fs_name = ctypes.create_unicode_buffer(261)
        serial = wintypes.DWORD()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            wintypes.LPCWSTR(_SYSTEM_DRIVE),
            vol_name,
            len(vol_name),
            ctypes.byref(serial),
            None,
            None,
            fs_name,
            len(fs_name),
        )
        if ok:
            return str(serial.value)
    except Exception:  # noqa: BLE001, S110 - fingerprint must never crash the app
        pass
    return ""


def _hardware_parts() -> list[str]:
    """Collect composite hardware facts (lowercased strings)."""
    parts: list[str] = []

    cpu = platform.processor().strip() or os.environ.get("PROCESSOR_IDENTIFIER", "").strip()
    if cpu:
        parts.append(cpu.lower())

    machine = platform.machine().strip()
    if machine:
        parts.append(machine.lower())

    # MAC address as hex (without colons).
    mac = format(uuid.getnode(), "x").strip()
    if mac and mac != "0":
        parts.append(mac.lower())

    disk = _volume_serial().strip()
    if disk:
        parts.append(disk.lower())

    # Fallback mirror of the above that survives a missing volume serial:
    # a fingerprint switch alone (e.g. network interface replacement) keeps
    # this "stable enough" for a lifetime license.
    system = platform.system().strip()
    if system:
        parts.append(system.lower())

    return sorted(filter(bool, parts))


def get_machine_id(seed: str | None = None) -> str:
    """Return a stable 32-hex-char machine fingerprint."""
    parts = _hardware_parts()
    if seed:
        parts.append(seed.lower())
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]