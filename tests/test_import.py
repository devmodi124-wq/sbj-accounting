"""Phase 8 — Excel import: template, validation, commit."""
from __future__ import annotations

import io

from openpyxl import Workbook, load_workbook

from app.services.import_template import SHEETS

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def make_xlsx(data: dict) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for title, headers in SHEETS.items():
        ws = wb.create_sheet(title)
        ws.append(headers)
        for row in data.get(title, []):
            ws.append([row.get(h, "") for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, url, content):
    return client.post(url, files={"file": ("import.xlsx", content, XLSX)})


GOOD = {
    "Customers": [{"name": "Imp Cust", "phone": "123"}],
    "Orders": [{"order_ref": "O1", "customer_name": "Imp Cust", "order_date": "2026-06-01",
                "item_category": "Ring", "item_name": "Ladies ring", "weight_type": "Normal",
                "supply_source": "On Order", "status": "delivered", "payment_received": "500"}],
    "Order Items": [
        {"order_ref": "O1", "component_type": "Round (RND)", "price": "1000", "purity": "22 KT"},
        {"order_ref": "O1", "component_type": "Labour", "price": "200"},
    ],
    "Cash Entries": [{"date": "2026-06-02", "person_name": "Imp Cust", "type": "received", "amount": "300"}],
    "Purchases": [{"date": "2026-06-03", "party_name": "Imp Supp", "amount": "5000", "amount_paid": "1000"}],
    "Opening Balances": [{"entity_type": "customer", "entity_name": "Imp Cust",
                          "as_of_date": "2026-01-01", "amount": "100", "direction": "debit"}],
}


def test_template_download(admin_client):
    r = admin_client.get("/api/import/template")
    assert r.status_code == 200
    wb = load_workbook(io.BytesIO(r.content))
    assert "Instructions" in wb.sheetnames
    assert "Order Items" in wb.sheetnames


def test_validate_good_file(admin_client):
    r = _upload(admin_client, "/api/import/validate", make_xlsx(GOOD))
    body = r.json()
    assert body["ok"] is True
    assert body["errors"] == []
    assert body["summary"]["Orders"] == 1


def test_validate_reports_errors(admin_client):
    bad = {
        "Orders": [{"order_ref": "O1", "customer_name": "", "order_date": "nope",
                    "item_name": "", "status": "weird", "payment_received": "x"}],
        "Order Items": [{"order_ref": "MISSING", "component_type": "Nope", "price": "abc"}],
    }
    body = _upload(admin_client, "/api/import/validate", make_xlsx(bad)).json()
    assert body["ok"] is False
    msgs = " ".join(e["message"] for e in body["errors"])
    assert "customer_name is required" in msgs
    assert "item_category is required" in msgs
    assert "order_date" in msgs
    assert "unknown component_type" in msgs
    assert "not found in Orders" in msgs


def test_commit_imports_everything(admin_client):
    r = _upload(admin_client, "/api/import/commit", make_xlsx(GOOD))
    assert r.status_code == 200
    imported = r.json()["imported"]
    assert imported["orders"] == 1
    assert imported["order_items"] == 2
    assert imported["purchases"] == 1

    # Order total recomputed from items (1000 + 200) and balance (1200 - 500).
    orders = admin_client.get("/api/orders").json()
    assert orders[0]["total_amount"] == "1200.00"
    assert orders[0]["balance"] == "700.00"

    # Customer ledger shows the opening balance and the order.
    cid = orders[0]["customer_id"]
    led = admin_client.get(f"/api/ledgers/customer/{cid}").json()
    assert led["entries"][0]["particulars"] == "Opening balance"


def test_commit_rejected_when_invalid(admin_client):
    bad = {"Orders": [{"order_ref": "O1", "customer_name": "", "order_date": "x", "item_name": ""}]}
    r = _upload(admin_client, "/api/import/commit", make_xlsx(bad))
    assert r.status_code == 422


def test_commit_reuses_existing_customer(admin_client):
    admin_client.post("/api/customers", json={"name": "Existing Cust"})
    data = {
        "Orders": [{"order_ref": "X1", "customer_name": "  existing cust ", "order_date": "2026-06-01",
                    "item_category": "Ring", "status": "pending", "payment_received": "0"}],
        "Order Items": [{"order_ref": "X1", "component_type": "Round (RND)", "price": "100"}],
    }
    _upload(admin_client, "/api/import/commit", make_xlsx(data))
    matches = admin_client.get("/api/customers", params={"q": "existing cust"}).json()
    assert len([c for c in matches if c["name"].lower() == "existing cust"]) == 1


def test_import_requires_admin(admin_client):
    from fastapi.testclient import TestClient

    from app.main import app

    admin_client.post("/api/users", json={"username": "emp", "password": "emp123"})
    emp = TestClient(app)
    emp.post("/auth/login", json={"username": "emp", "password": "emp123"})
    assert emp.get("/api/import/template").status_code == 403
