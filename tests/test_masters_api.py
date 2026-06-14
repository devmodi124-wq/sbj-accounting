"""Phase 3 — masters CRUD, lookups, users, settings via HTTP."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _login_employee(admin_client, username="ramesh", password="emp123"):
    """Create an employee (as admin) and return a client logged in as them."""
    admin_client.post(
        "/api/users",
        json={"username": username, "password": password, "role": "employee", "full_name": "Ramesh"},
    )
    emp = TestClient(app)
    emp.post("/auth/login", json={"username": username, "password": password})
    return emp


# ===== Customers =====

def test_customer_crud_and_search(admin_client):
    r = admin_client.post("/api/customers", json={"name": "Malti Devi", "phone": "98XX"})
    assert r.status_code == 201
    cid = r.json()["id"]

    assert admin_client.get(f"/api/customers/{cid}").json()["name"] == "Malti Devi"

    admin_client.put(f"/api/customers/{cid}", json={"name": "Malti Devi", "phone": "99YY"})
    assert admin_client.get(f"/api/customers/{cid}").json()["phone"] == "99YY"

    found = admin_client.get("/api/customers", params={"q": "malti"}).json()
    assert any(c["id"] == cid for c in found)


def test_customers_require_auth(client):
    assert client.get("/api/customers").status_code == 401


# ===== Lookups =====

def test_component_types_seeded_and_active_filter(admin_client):
    all_types = admin_client.get("/api/component-types").json()
    assert len(all_types) == 6
    # deactivate one, then active_only should drop it
    first_id = all_types[0]["id"]
    admin_client.put(f"/api/component-types/{first_id}", json={"is_active": False})
    active = admin_client.get("/api/component-types", params={"active_only": True}).json()
    assert all(t["is_active"] for t in active)
    assert len(active) == 5


def test_create_duplicate_component_type_conflicts(admin_client):
    admin_client.post("/api/component-types", json={"name": "Enamel"})
    r = admin_client.post("/api/component-types", json={"name": "enamel"})
    assert r.status_code == 409


def test_reorder_component_types(admin_client):
    types = admin_client.get("/api/component-types").json()
    ids = [t["id"] for t in types]
    reversed_ids = list(reversed(ids))
    admin_client.post("/api/component-types/reorder", json={"ordered_ids": reversed_ids})
    after = admin_client.get("/api/component-types").json()
    assert [t["id"] for t in after] == reversed_ids


def test_employee_cannot_manage_lookups(admin_client):
    emp = _login_employee(admin_client)
    assert emp.get("/api/component-types").status_code == 200  # read ok
    assert emp.post("/api/component-types", json={"name": "X"}).status_code == 403


# ===== Users =====

def test_admin_creates_employee_who_can_login(admin_client):
    emp = _login_employee(admin_client)
    assert emp.get("/auth/me").json()["user"]["role"] == "employee"


def test_username_taken(admin_client):
    admin_client.post("/api/users", json={"username": "dup", "password": "pw123"})
    r = admin_client.post("/api/users", json={"username": "dup", "password": "pw123"})
    assert r.status_code == 409


def test_admin_cannot_deactivate_self(admin_client):
    me = admin_client.get("/auth/me").json()["user"]
    r = admin_client.put(f"/api/users/{me['id']}", json={"is_active": False})
    assert r.status_code == 400


def test_password_reset_changes_login(admin_client):
    admin_client.post("/api/users", json={"username": "ramesh", "password": "old123"})
    users = admin_client.get("/api/users").json()
    uid = next(u["id"] for u in users if u["username"] == "ramesh")
    admin_client.post(f"/api/users/{uid}/reset-password", json={"password": "new123"})

    c = TestClient(app)
    assert c.post("/auth/login", json={"username": "ramesh", "password": "old123"}).status_code == 401
    assert c.post("/auth/login", json={"username": "ramesh", "password": "new123"}).status_code == 200


def test_employee_cannot_list_users(admin_client):
    emp = _login_employee(admin_client)
    assert emp.get("/api/users").status_code == 403


# ===== Settings =====

def test_settings_get_and_update(admin_client):
    settings = admin_client.get("/api/settings").json()
    assert settings["employee_backdate_limit_days"] == "7"
    admin_client.put("/api/settings", json={"employee_backdate_limit_days": "14", "bogus": "x"})
    assert admin_client.get("/api/settings").json()["employee_backdate_limit_days"] == "14"


def test_employee_cannot_read_settings(admin_client):
    emp = _login_employee(admin_client)
    assert emp.get("/api/settings").status_code == 403
