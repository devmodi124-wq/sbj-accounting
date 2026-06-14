"""Shared test fixtures."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from app.db import MASTER_KEY_BYTES, build_engine


@pytest.fixture
def master_key() -> bytes:
    return secrets.token_bytes(MASTER_KEY_BYTES)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "khata-test.db"


@pytest.fixture
def encrypted_engine(db_path: Path, master_key: bytes) -> Engine:
    """A fresh, encrypted, empty SQLCipher DB engine for a single test."""
    engine = build_engine(db_path, master_key)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI TestClient with the data dir pointed at a throwaway location."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("KHATA_DATA_DIR", str(tmp_path / "data"))
    # config + main cache settings via lru_cache; clear so the env override is read.
    import app.config as config

    config.get_settings.cache_clear()
    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as c:
        yield c
    config.get_settings.cache_clear()
