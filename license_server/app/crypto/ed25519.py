"""Ed25519 signing utility for license verification.

The server holds the PRIVATE signing key.
The client application embeds only the corresponding PUBLIC key so it can
verify license authenticity offline without trusting arbitrary local data.
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

logger = logging.getLogger(__name__)


def generate_key_pair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate a fresh Ed25519 key pair (for first-time setup)."""
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def private_key_to_base64(key: Ed25519PrivateKey) -> str:
    raw = key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    return base64.b64encode(raw).decode()


def public_key_to_base64(key: Ed25519PublicKey) -> str:
    raw = key.public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode()


def private_key_from_base64(b64: str) -> Ed25519PrivateKey:
    raw = base64.b64decode(b64)
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_key_from_base64(b64: str) -> Ed25519PublicKey:
    raw = base64.b64decode(b64)
    return Ed25519PublicKey.from_public_bytes(raw)


def serialize_payload(payload: dict[str, Any]) -> str:
    """Canonical JSON serialization so signatures are stable across machines."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sign_payload(private_key: Ed25519PrivateKey, payload: dict[str, Any]) -> str:
    """Sign a JSON-serializable payload, returning a base64 signature."""
    canonical = serialize_payload(payload).encode()
    signature = private_key.sign(canonical)
    return base64.b64encode(signature).decode()


def verify_payload(public_key: Ed25519PublicKey, payload: dict[str, Any], signature_b64: str) -> bool:
    """Verify a signature against a payload. Returns True if valid."""
    try:
        canonical = serialize_payload(payload).encode()
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, canonical)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
