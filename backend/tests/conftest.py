"""Shared pytest fixtures: isolated secrets dir + temp SQLite database."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


@pytest.fixture()
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point every secrets/db path at a temp dir so tests never touch real
    key material, and reset the singletons between tests."""
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    monkeypatch.setenv("SECRETS_DIR", str(secrets))
    monkeypatch.setenv("MODELS_DIR", str(models_dir))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("ENV", "dev")

    from app.core import config

    config.get_settings.cache_clear()
    from app.crypto import key_manager

    key_manager.KeyManager._instance = None
    from app.crypto import abe

    abe._AUTHORITY = None
    from app.crypto import he_ckks

    he_ckks._STORE = None
    from app.ml import models as ml_models

    ml_models._CACHE.clear()
    from app.db import session as db_session

    db_session.reset_engine()
    yield tmp_path
    config.get_settings.cache_clear()
    key_manager.KeyManager._instance = None
    abe._AUTHORITY = None
    he_ckks._STORE = None
    ml_models._CACHE.clear()
