"""Phase 7 — reports, ledgers, CSV export."""
from __future__ import annotations

from datetime import date, timedelta

from app.services.reports import ageing_bucket

TODAY = date.today()
TODAY_S = TODAY.isoformat()


def _comp(client):
    return [t["id"] for t in client.get("/api/component-types").json()]


# ===== Ageing buckets (unit) =====

def test_ageing_buckets():
    assert ageing_bucket(TODAY, TODAY) == "0-30"
    assert ageing_bucket(TODAY, TODAY - timedelta(days=30)) == "0-30"
    assert ageing_bucket(TODAY, TODAY - timedelta(days=31)) == "31-60"
    assert ageing_bucket(TODAY, TODAY - timedelta(days=60)) == "31-60"
    assert ageing_bucket(TODAY, TODAY - timedelta(days=61)) == "61-90"
    assert ageing_bucket(TODAY, TODAY - timedelta(days=91)) == "90+"
    assert ageing_bucket(TODAY, None) == "—"


# ===== Sales report =====

def test_sales_report_filter_by_status(admin_client):
    comps = _comp(admin_client)
    admin_client.post("/api/orders", json={"customer_name": "A", "order_date": TODAY_S,
        "status": "delivered", "payment_received": "0",
        "items": [{"item_category_id": 1, "item_name": "Ring",
                   "components": [{"component_type_id": comps[0], "price": "1000"}]}]})
    admin_client.post("/api/orders", json={"customer_name": "B", "order_date": TODAY_S,
        "status": "pending", "payment_received": "0",
        "items": [{"item_category_id": 1, "item_name": "Chain",
                   "components": [{"component_type_id": comps[0], "price": "2000"}]}]})
    delivered = admin_client.get("/api/reports/sales", params={"status": "delivered"}).json()
    assert delivered["total"] == 1
    assert delivered["rows"][0]["item_name"] == "Ring"


def test_sales_report_has_category_and_filters(admin_client):
    cats = admin_client.get("/api/item-categories").json()
    ring, necklace = cats[0]["id"], cats[1]["id"]
    comps = _comp(admin_client)
    admin_client.post("/api/orders", json={"customer_name": "A", "order_date": TODAY_S,
        "payment_received": "0",
        "items": [{"item_category_id": ring, "item_name": "R",
                   "components": [{"component_type_id": comps[0], "price": "100"}]}]})
    admin_client.post("/api/orders", json={"customer_name": "B", "order_date": TODAY_S,
        "payment_received": "0",
        "items": [{"item_category_id": necklace, "item_name": "N",
                   "components": [{"component_type_id": comps[0], "price": "200"}]}]})

    allrows = admin_client.get("/api/reports/sales").json()["rows"]
    assert {r["item_category"] for r in allrows} == {cats[0]["name"], cats[1]["name"]}

    filtered = admin_client.get("/api/reports/sales", params={"category_id": ring}).json()
    assert filtered["total"] == 1
    assert filtered["rows"][0]["item_category"] == cats[0]["name"]


def test_sales_csv_export(admin_client):
    comps = _comp(admin_client)
    admin_client.post("/api/orders", json={"customer_name": "CsvCust", "order_date": TODAY_S,
        "status": "delivered", "payment_received": "500",
        "items": [{"item_category_id": 1, "item_name": "Ring",
                   "components": [{"component_type_id": comps[0], "price": "1000"}]}]})
    r = admin_client.get("/api/reports/sales", params={"format": "csv"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0] == "Date,Customer,Category,Item,Items,Total,Received,Balance,Status"
    assert "CsvCust" in lines[1]


# ===== Debtors / creditors =====

def test_debtors_report(admin_client):
    comps = _comp(admin_client)
    admin_client.post("/api/orders", json={"customer_name": "Owes Money", "order_date": TODAY_S,
        "payment_received": "300",
        "items": [{"item_category_id": 1, "item_name": "Ring",
                   "components": [{"component_type_id": comps[0], "price": "1000"}]}]})
    admin_client.post("/api/orders", json={"customer_name": "Paid Up", "order_date": TODAY_S,
        "payment_received": "1000",
        "items": [{"item_category_id": 1, "item_name": "Ring",
                   "components": [{"component_type_id": comps[0], "price": "1000"}]}]})
    d = admin_client.get("/api/reports/debtors").json()
    names = [r["name"] for r in d["rows"]]
    assert "Owes Money" in names
    assert "Paid Up" not in names           # zero balance excluded
    assert d["total_outstanding"] == "700.00"
    assert d["rows"][0]["ageing"] == "0-30"


def test_creditors_report(admin_client):
    admin_client.post("/api/purchases", json={"purchase_date": TODAY_S, "party_name": "Owed Supp",
        "amount": "5000", "amount_paid": "1000"})
    c = admin_client.get("/api/reports/creditors").json()
    assert c["rows"][0]["name"] == "Owed Supp"
    assert c["rows"][0]["balance"] == "4000.00"
    assert c["total_outstanding"] == "4000.00"


# ===== Customer report =====

def test_customer_report_avg(admin_client):
    comps = _comp(admin_client)
    for price in ("1000", "3000"):
        admin_client.post("/api/orders", json={"customer_name": "Avg Cust", "order_date": TODAY_S,
            "payment_received": "0",
            "items": [{"item_category_id": 1, "item_name": "Ring",
                       "components": [{"component_type_id": comps[0], "price": price}]}]})
    rep = admin_client.get("/api/reports/customers", params={"search": "avg cust"}).json()
    row = rep["rows"][0]
    assert row["order_count"] == 2
    assert row["lifetime"] == "4000.00"
    assert row["avg_order_value"] == "2000.00"


# ===== Ledger =====

def test_customer_ledger_running_balance(admin_client):
    comps = _comp(admin_client)
    cid = admin_client.post("/api/customers", json={"name": "Ledger Cust"}).json()["id"]
    # opening debit 1000
    admin_client.post("/api/ledgers/opening-balance", json={"entity_type": "customer",
        "entity_id": cid, "as_of_date": "2020-01-01", "amount": "1000", "direction": "debit"})
    # order total 5000, paid 2000
    admin_client.post("/api/orders", json={"customer_id": cid, "order_date": TODAY_S,
        "payment_received": "2000",
        "items": [{"item_category_id": 1, "item_name": "Ring",
                   "components": [{"component_type_id": comps[0], "price": "5000"}]}]})
    led = admin_client.get(f"/api/ledgers/customer/{cid}").json()
    balances = [e["balance"] for e in led["entries"]]
    assert balances == ["1000.00", "6000.00", "4000.00"]
    assert led["closing_balance"] == "4000.00"


def test_ledger_csv(admin_client):
    cid = admin_client.post("/api/customers", json={"name": "L2"}).json()["id"]
    admin_client.post("/api/ledgers/opening-balance", json={"entity_type": "customer",
        "entity_id": cid, "as_of_date": "2020-01-01", "amount": "500", "direction": "debit"})
    r = admin_client.get(f"/api/ledgers/customer/{cid}", params={"format": "csv"})
    assert r.status_code == 200
    assert r.text.splitlines()[0] == "Date,Particulars,Debit,Credit,Balance"
