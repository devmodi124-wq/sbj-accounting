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
def session(encrypted_engine: Engine):
    """A session on a fully initialized (created + seeded) encrypted DB."""
    from sqlalchemy.orm import Session

    from app.services.seed import initialize_database

    initialize_database(encrypted_engine)
    # Mirror the production sessionmaker (app.db.EngineState): keeping attributes
    # populated after commit lets the audit layer capture old values on update.
    with Session(encrypted_engine, expire_on_commit=False) as s:
        yield s


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI TestClient with the data dir pointed at a throwaway location."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("KHATA_DATA_DIR", str(tmp_path / "data"))
    # config caches settings via lru_cache; clear so the env override is read.
    import app.config as config
    from app.db import engine_state

    config.get_settings.cache_clear()
    engine_state.dispose()  # ensure a locked, unbound DB for each test

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as c:
        yield c

    engine_state.dispose()
    config.get_settings.cache_clear()


@pytest.fixture
def admin_client(client):
    """A client logged in as the bootstrapped admin."""
    client.post(
        "/auth/bootstrap",
        json={"username": "admin", "password": "pw1234", "full_name": "Owner"},
    )
    return client
