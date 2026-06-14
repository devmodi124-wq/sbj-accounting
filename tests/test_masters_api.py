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


def test_delete_unreferenced_customer(admin_client):
    cid = admin_client.post("/api/customers", json={"name": "Deletable"}).json()["id"]
    assert admin_client.delete(f"/api/customers/{cid}").status_code == 200
    assert admin_client.get(f"/api/customers/{cid}").status_code == 404


def test_delete_customer_with_orders_blocked(admin_client):
    comps = [t["id"] for t in admin_client.get("/api/component-types").json()]
    cat = admin_client.get("/api/item-categories").json()[0]["id"]
    cid = admin_client.post("/api/customers", json={"name": "Has Order"}).json()["id"]
    admin_client.post("/api/orders", json={
        "customer_id": cid, "order_date": "2026-06-14", "item_category_id": cat,
        "payment_received": "0", "items": [{"component_type_id": comps[0], "price": "100"}],
    })
    r = admin_client.delete(f"/api/customers/{cid}")
    assert r.status_code == 409
    assert r.json()["detail"] == "has_references"


def test_delete_party_with_purchase_blocked(admin_client):
    pid = admin_client.post("/api/parties", json={"name": "Has Purchase"}).json()["id"]
    admin_client.post("/api/purchases", json={
        "purchase_date": "2026-06-14", "party_id": pid, "amount": "500", "amount_paid": "0",
    })
    assert admin_client.delete(f"/api/parties/{pid}").status_code == 409


def test_delete_requires_admin(admin_client):
    cid = admin_client.post("/api/customers", json={"name": "Temp"}).json()["id"]
    emp = _login_employee(admin_client)
    assert emp.delete(f"/api/customers/{cid}").status_code == 403


def test_deactivate_hides_from_search_but_keeps_record(admin_client):
    cid = admin_client.post("/api/customers", json={"name": "Old Customer"}).json()["id"]
    # deactivate
    r = admin_client.post(f"/api/customers/{cid}/active", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False

    # default search (New Order type-ahead) excludes inactive
    active = admin_client.get("/api/customers", params={"q": "old customer"}).json()
    assert all(c["id"] != cid for c in active)

    # management view includes inactive
    allrows = admin_client.get("/api/customers", params={"q": "old customer", "include_inactive": True}).json()
    assert any(c["id"] == cid for c in allrows)

    # record still fetchable, and reactivation works
    assert admin_client.get(f"/api/customers/{cid}").status_code == 200
    admin_client.post(f"/api/customers/{cid}/active", json={"is_active": True})
    reactivated = admin_client.get("/api/customers", params={"q": "old customer"}).json()
    assert any(c["id"] == cid for c in reactivated)


def test_party_deactivate(admin_client):
    pid = admin_client.post("/api/parties", json={"name": "Old Supp"}).json()["id"]
    admin_client.post(f"/api/parties/{pid}/active", json={"is_active": False})
    assert all(p["id"] != pid for p in admin_client.get("/api/parties", params={"q": "old supp"}).json())


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
