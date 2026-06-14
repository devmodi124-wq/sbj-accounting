"""Phase 5 — cash entries & purchases."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

TODAY = date.today().isoformat()


# ===== Cash =====

def test_create_and_list_cash(admin_client):
    r = admin_client.post("/api/cash", json={
        "entry_date": TODAY, "person_name": "Walk-in", "entry_type": "received", "amount": "5000",
    })
    assert r.status_code == 201
    assert r.json()["entry_type"] == "received"

    admin_client.post("/api/cash", json={
        "entry_date": TODAY, "person_name": "Supplier", "entry_type": "paid", "amount": "1200",
    })
    received = admin_client.get("/api/cash", params={"entry_type": "received"}).json()
    assert len(received) == 1


def test_cash_optional_links(admin_client):
    cid = admin_client.post("/api/customers", json={"name": "Linked Cust"}).json()["id"]
    r = admin_client.post("/api/cash", json={
        "entry_date": TODAY, "person_name": "Linked Cust", "customer_id": cid,
        "entry_type": "received", "amount": "999",
    })
    assert r.json()["customer_id"] == cid


def test_employee_cannot_backdate_cash(admin_client):
    admin_client.post("/api/users", json={"username": "emp", "password": "emp123"})
    emp = TestClient(app)
    emp.post("/auth/login", json={"username": "emp", "password": "emp123"})
    old = (date.today() - timedelta(days=20)).isoformat()
    r = emp.post("/api/cash", json={"entry_date": old, "entry_type": "paid", "amount": "10"})
    assert r.status_code == 422


# ===== Purchases =====

def test_create_purchase_derives_balance_and_status(admin_client):
    r = admin_client.post("/api/purchases", json={
        "purchase_date": TODAY, "party_name": "Mannu (Jaipur)",
        "details": "Diamonds", "entry_notes": "3 ct @ 6600", "amount": "20000", "amount_paid": "5000",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["balance"] == "15000.00"
    assert body["status"] == "pending"


def test_purchase_paid_status(admin_client):
    r = admin_client.post("/api/purchases", json={
        "purchase_date": TODAY, "party_name": "Paid Supplier", "amount": "1000", "amount_paid": "1000",
    })
    assert r.json()["status"] == "paid"
    assert r.json()["balance"] == "0.00"


def test_purchase_reuses_party(admin_client):
    admin_client.post("/api/purchases", json={"purchase_date": TODAY, "party_name": "Acme", "amount": "1"})
    admin_client.post("/api/purchases", json={"purchase_date": TODAY, "party_name": "  acme ", "amount": "2"})
    parties = admin_client.get("/api/parties", params={"q": "acme"}).json()
    assert len([p for p in parties if p["name"].lower() == "acme"]) == 1


def test_update_purchase_recomputes(admin_client):
    pid = admin_client.post("/api/purchases", json={
        "purchase_date": TODAY, "party_name": "Acme", "amount": "1000", "amount_paid": "0",
    }).json()["id"]
    body = admin_client.put(f"/api/purchases/{pid}", json={
        "purchase_date": TODAY, "party_name": "Acme", "amount": "1000", "amount_paid": "1000",
    }).json()
    assert body["status"] == "paid"


def test_purchases_list_resolves_party_name(admin_client):
    admin_client.post("/api/purchases", json={"purchase_date": TODAY, "party_name": "Visible Co", "amount": "5"})
    rows = admin_client.get("/api/purchases").json()
    assert any(p["party_name"] == "Visible Co" for p in rows)
