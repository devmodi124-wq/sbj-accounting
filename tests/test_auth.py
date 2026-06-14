"""Phase 2 — auth HTTP flow: bootstrap, login, single-session, roles."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth.deps import require_admin
from app.models import User
from app.models.base import UserRole


def test_status_needs_bootstrap_initially(client):
    r = client.get("/auth/status")
    assert r.status_code == 200
    assert r.json()["state"] == "needs_bootstrap"


def test_bootstrap_then_authenticated(client):
    r = client.post("/auth/bootstrap", json={"username": "admin", "password": "pw", "full_name": "Owner"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "admin"

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "admin"

    st = client.get("/auth/status")
    assert st.json()["state"] == "unlocked"
    assert st.json()["authenticated"] is True


def test_bootstrap_only_once(client):
    client.post("/auth/bootstrap", json={"username": "admin", "password": "pw"})
    r = client.post("/auth/bootstrap", json={"username": "x", "password": "y"})
    assert r.status_code == 409


def test_logout_clears_session(client):
    client.post("/auth/bootstrap", json={"username": "admin", "password": "pw"})
    assert client.get("/auth/me").status_code == 200
    client.post("/auth/logout")
    assert client.get("/auth/me").status_code == 401


def test_login_wrong_password(client):
    client.post("/auth/bootstrap", json={"username": "admin", "password": "right"})
    client.post("/auth/logout")
    r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_single_active_session(client):
    from fastapi.testclient import TestClient

    from app.main import app

    client.post("/auth/bootstrap", json={"username": "admin", "password": "pw"})
    assert client.get("/auth/me").status_code == 200

    # A second client logs in as the same user -> first session invalidated.
    other = TestClient(app)
    assert other.post("/auth/login", json={"username": "admin", "password": "pw"}).status_code == 200
    assert other.get("/auth/me").status_code == 200

    r = client.get("/auth/me")
    assert r.status_code == 401
    assert r.json()["detail"] == "session_invalid"


def test_require_admin_blocks_employee():
    employee = User(username="emp", password_hash="x", role=UserRole.employee)
    with pytest.raises(HTTPException) as exc:
        require_admin(employee)
    assert exc.value.status_code == 403


def test_require_admin_allows_admin():
    admin = User(username="admin", password_hash="x", role=UserRole.admin)
    assert require_admin(admin) is admin
