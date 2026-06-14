"""Phase 9 — backups and the kill switch (Lock / Destroy)."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app import killswitch
from app.config import get_settings
from app.db import build_engine, engine_state


def _data():
    s = get_settings()
    return s.db_path, s.keyfile_path, s.sealed_key_path


# ===== Backups =====

def test_backup_creates_copy(admin_client):
    r = admin_client.post("/api/system/backup")
    assert r.status_code == 200
    out = Path(r.json()["path"])
    assert (out / "khata.db").exists()
    assert (out / "khata.keys").exists()
    listed = admin_client.get("/api/system/backups").json()
    assert any(b["path"] == str(out) for b in listed)


def test_backup_requires_admin(admin_client):
    from fastapi.testclient import TestClient
    from app.main import app

    admin_client.post("/api/users", json={"username": "emp", "password": "emp123"})
    emp = TestClient(app)
    emp.post("/auth/login", json={"username": "emp", "password": "emp123"})
    assert emp.post("/api/system/backup").status_code == 403


# ===== Lock (Danger Zone gating + behaviour) =====

def test_lock_requires_correct_password(admin_client):
    r = admin_client.post("/api/system/lock", json={"password": "wrong", "confirm": "LOCK"})
    assert r.status_code == 403


def test_lock_requires_confirmation_phrase(admin_client):
    r = admin_client.post("/api/system/lock", json={"password": "pw1234", "confirm": "nope"})
    assert r.status_code == 400


def test_lock_rekeys_and_locks_out(admin_client):
    db_path, keyfile_path, sealed_path = _data()
    r = admin_client.post("/api/system/lock", json={"password": "pw1234", "confirm": "LOCK"})
    assert r.status_code == 200

    # Sealed key written; DB opens with it, and old credentials no longer work.
    new_key = bytes.fromhex(sealed_path.read_text())
    eng = build_engine(db_path, new_key)
    with eng.connect() as c:
        c.execute(text("SELECT 1")).fetchall()
    eng.dispose()

    # Keyfile emptied -> no user can log in anymore.
    assert admin_client.post("/auth/login", json={"username": "admin", "password": "pw1234"}).status_code == 401


# ===== Destroy =====

def test_destroy_removes_local_files_but_spares_external(admin_client, tmp_path):
    db_path, keyfile_path, sealed_path = _data()
    # Simulate an external backup (outside the data dir) — must survive.
    external = tmp_path / "external-backup"
    external.mkdir()
    (external / "khata.db").write_bytes(b"external copy")

    # A local backup inside the data dir — must be destroyed.
    admin_client.post("/api/system/backup")  # default folder = data_dir/backups
    assert (get_settings().data_dir / "backups").exists()

    r = admin_client.post("/api/system/destroy", json={"password": "pw1234", "confirm": "DESTROY"})
    assert r.status_code == 200

    assert not db_path.exists()
    assert not keyfile_path.exists()
    assert not (get_settings().data_dir / "backups").exists()
    assert (external / "khata.db").exists()  # external survives


def test_destroy_requires_password(admin_client):
    r = admin_client.post("/api/system/destroy", json={"password": "wrong", "confirm": "DESTROY"})
    assert r.status_code == 403
