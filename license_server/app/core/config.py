"""License server configuration.

Reads settings from environment variables / .env file.
All production secrets come from environment variables, NOT committed code.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Location of the .env file relative to this module
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    database_url: str = "postgresql+psycopg2://license_user:CHANGE_ME@localhost:5432/license_server"

    # --- Security ---
    admin_username: str = "admin"
    admin_password_hash: str = ""          # SHA-256 of the admin password
    secret_key: str = "CHANGE_ME_RANDOM_64_CHARS"

    # --- Signing keys ---
    private_signing_key: str = ""          # base64 Ed25519 private key

    # --- Rate limiting ---
    rate_limit_activation_per_min: int = 10

    # --- Server ---
    environment: str = "development"

    def admin_password_ok(self, password: str) -> bool:
        """Check a plaintext admin password against the stored hash."""
        if not self.admin_password_hash:
            return False
        return hashlib.sha256(password.encode()).hexdigest() == self.admin_password_hash


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
