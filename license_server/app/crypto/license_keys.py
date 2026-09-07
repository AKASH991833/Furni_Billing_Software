"""Cryptographically strong license key generation.

Format: FB-XXXX-XXXX-XXXX
  - FB = product prefix (Furniture Bill)
  - Each XXXX group = 4 chars from a non-ambiguous base32 alphabet

Keys are generated from secrets.choice for true randomness.
They are NEVER derived from customer name, mobile, date, or DB id.
"""
from __future__ import annotations

import secrets

# Base32 alphabet with ambiguous characters (0/O, 1/I/L) removed so keys are
# easy for a human to type correctly.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_DEFAULT_PREFIX = "FB"
_GROUP_LEN = 4
_N_GROUPS = 3

PRODUCT_PREFIX_MAP: dict[str, str] = {
    "furniture_bill": "FB",
    "furniture_billing": "FB",
    "ac_service": "AC",
    "future_product": "FP",
}


def get_product_prefix(product: str | None) -> str:
    """Return the 2-4 char uppercase prefix for a product identifier."""
    if not product:
        return _DEFAULT_PREFIX
    norm = product.strip().lower().replace("-", "_").replace(" ", "_")
    if norm in PRODUCT_PREFIX_MAP:
        return PRODUCT_PREFIX_MAP[norm]
    cleaned = "".join(c for c in product.upper() if c.isalnum())
    return cleaned[:4] if len(cleaned) >= 2 else _DEFAULT_PREFIX


def generate_license_key(product: str = "furniture_bill") -> str:
    """Generate a random license key string like 'FB-7K92-XP4M-LQ81' or 'AC-7K92-XP4M-LQ81'."""
    prefix = get_product_prefix(product)
    groups = []
    for _ in range(_N_GROUPS):
        group = "".join(secrets.choice(_ALPHABET) for _ in range(_GROUP_LEN))
        groups.append(group)
    return f"{prefix}-{'-'.join(groups)}"


def is_valid_format(key: str, product: str | None = None) -> bool:
    """Basic format check (does NOT validate against the DB)."""
    if not key or not isinstance(key, str):
        return False
    parts = key.strip().upper().split("-")
    if len(parts) != 1 + _N_GROUPS:
        return False
    prefix = parts[0]
    if len(prefix) < 2 or len(prefix) > 6 or not prefix.isalnum():
        return False
    if product:
        expected = get_product_prefix(product)
        if prefix != expected:
            return False
    for group in parts[1:]:
        if len(group) != _GROUP_LEN or any(c not in _ALPHABET for c in group):
            return False
    return True
