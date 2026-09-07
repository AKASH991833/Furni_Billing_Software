"""CLI utility to generate an Ed25519 signing key pair.

Usage:
    python -m app.crypto.generate_keys

Prints the base64 private and public keys. Put the private key in the server's
.env (PRIVATE_SIGNING_KEY). Embed the PUBLIC key in the client application.

NEVER commit the private key.
"""
from __future__ import annotations

import sys

from app.crypto.ed25519 import (
    generate_key_pair,
    private_key_to_base64,
    public_key_to_base64,
)


def main() -> int:
    private_key, public_key = generate_key_pair()
    priv_b64 = private_key_to_base64(private_key)
    pub_b64 = public_key_to_base64(public_key)
    print("=" * 60)
    print("Ed25519 SIGNING KEY PAIR")
    print("=" * 60)
    print()
    print("PRIVATE_KEY (put in server .env -> PRIVATE_SIGNING_KEY, NEVER commit):")
    print(priv_b64)
    print()
    print("PUBLIC_KEY (embed in client app config, safe to commit):")
    print(pub_b64)
    print()
    print("=" * 60)
    print("Also compute your admin password hash:")
    print("  python -c \"import hashlib;print(hashlib.sha256(b'YOURPASSWORD').hexdigest())\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
