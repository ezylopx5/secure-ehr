"""Application configuration via pydantic-settings.

All secrets flow from a single 256-bit master key (env ``MASTER_KEY_B64`` or a
dev-generated file). Derived keys are produced by :mod:`app.crypto.key_manager`
using HKDF-SHA256, so no secret other than the master key needs configuration.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
IS_VERCEL = bool(os.environ.get("VERCEL"))


class Settings(BaseSettings):
    """Central, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- application ---
    APP_NAME: str = "AegisEHR Clinical Platform"
    ENV: str = "dev"  # dev | prod
    DATABASE_URL: str = "sqlite:////tmp/ehr.db" if IS_VERCEL else "sqlite:///./ehr.db"

    # --- cryptography ---
    MASTER_KEY_B64: str = (
        "QWVnaXNFSFItVmVyY2VsLU1hc3Rlci1LZXktMjAyNiE="
        if IS_VERCEL
        else ""
    )  # empty => dev key file is used/created
    SECRETS_DIR: str = "/tmp/.secrets" if IS_VERCEL else str(BACKEND_DIR / ".secrets")

    # --- auth ---
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS: int = 7

    # --- API hardening ---
    RATE_LIMIT_RPS: float = 20.0
    RATE_LIMIT_BURST: float = 40.0
    TRUSTED_HOSTS: str = "*" if IS_VERCEL else "localhost,127.0.0.1"
    CORS_ORIGINS: str = (
        "*"
        if IS_VERCEL
        else "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    )

    # --- AI stack ---
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # --- ML ---
    MODELS_DIR: str = str(BACKEND_DIR / "models")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.TRUSTED_HOSTS.split(",") if h.strip()]

    @property
    def is_dev(self) -> bool:
        return self.ENV.lower() == "dev"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (import this everywhere)."""
    return Settings()
