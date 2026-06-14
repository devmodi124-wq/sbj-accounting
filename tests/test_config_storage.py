"""Configurable data-storage location (config file + admin endpoint)."""
from __future__ import annotations

import json

import app.config as config


def test_config_file_sets_data_dir_and_port(tmp_path, monkeypatch):
    monkeypatch.delenv("KHATA_DATA_DIR", raising=False)
    monkeypatch.delenv("KHATA_PORT", raising=False)
    cfg = tmp_path / "khata.config.json"
    cfg.write_text(json.dumps({"data_dir": str(tmp_path / "mydata"), "port": 9999}))
    monkeypatch.setenv("KHATA_CONFIG_FILE", str(cfg))

    config.get_settings.cache_clear()
    try:
        s = config.get_settings()
        assert s.data_dir == (tmp_path / "mydata").resolve()
        assert s.port == 9999
    finally:
        config.get_settings.cache_clear()


def test_env_var_overrides_config_file(tmp_path, monkeypatch):
    cfg = tmp_path / "khata.config.json"
    cfg.write_text(json.dumps({"data_dir": str(tmp_path / "fromfile")}))
    monkeypatch.setenv("KHATA_CONFIG_FILE", str(cfg))
    monkeypatch.setenv("KHATA_DATA_DIR", str(tmp_path / "fromenv"))

    config.get_settings.cache_clear()
    try:
        assert config.get_settings().data_dir == (tmp_path / "fromenv").resolve()
    finally:
        config.get_settings.cache_clear()


def test_storage_endpoints(admin_client, tmp_path):
    r = admin_client.get("/api/system/storage").json()
    assert r["current"]  # resolved location
    assert r["configured"] is None  # nothing written yet

    target = tmp_path / "relocated"
    put = admin_client.put("/api/system/storage", json={"data_dir": str(target)})
    assert put.status_code == 200
    assert put.json()["configured"] == str(target)
    assert target.exists()  # created during validation

    after = admin_client.get("/api/system/storage").json()
    assert after["configured"] == str(target)


def test_storage_rejects_empty(admin_client):
    assert admin_client.put("/api/system/storage", json={"data_dir": "  "}).status_code == 400


def test_storage_requires_admin(admin_client):
    from fastapi.testclient import TestClient

    from app.main import app

    admin_client.post("/api/users", json={"username": "emp", "password": "emp123"})
    emp = TestClient(app)
    emp.post("/auth/login", json={"username": "emp", "password": "emp123"})
    assert emp.get("/api/system/storage").status_code == 403
