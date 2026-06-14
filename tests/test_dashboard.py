"""Phase 6 — dashboard aggregations."""
from __future__ import annotations

from datetime import date

from app.services.dateranges import last_n_months, resolve_range

TODAY = date.today().isoformat()


def _comp(client):
    return [t["id"] for t in client.get("/api/component-types").json()]


def _seed(client):
    comps = _comp(client)
    cat = client.get("/api/item-categories").json()[0]["id"]
    # Order 1: total 40000, received 10000 -> balance 30000 (customer A)
    client.post("/api/orders", json={
        "customer_name": "Cust A", "order_date": TODAY, "item_category_id": cat, "item_name": "Ring",
        "status": "delivered", "payment_received": "10000",
        "items": [{"component_type_id": comps[0], "price": "40000"}],
    })
    # Order 2: total 20000, received 20000 -> balance 0 (customer B), pending status
    client.post("/api/orders", json={
        "customer_name": "Cust B", "order_date": TODAY, "item_category_id": cat, "item_name": "Chain",
        "status": "pending", "payment_received": "20000",
        "items": [{"component_type_id": comps[1], "price": "20000"}],
    })
    # Cash: +5000 received, -2000 paid
    client.post("/api/cash", json={"entry_date": TODAY, "entry_type": "received", "amount": "5000"})
    client.post("/api/cash", json={"entry_date": TODAY, "entry_type": "paid", "amount": "2000"})
    # Purchase: 10000, paid 3000 -> payable 7000
    client.post("/api/purchases", json={"purchase_date": TODAY, "party_name": "Supp", "amount": "10000", "amount_paid": "3000"})


# ===== Date range unit tests =====

def test_resolve_today():
    t = date(2026, 6, 14)
    assert resolve_range("today", t) == (t, t)


def test_resolve_this_month():
    t = date(2026, 6, 14)
    assert resolve_range("this_month", t) == (date(2026, 6, 1), date(2026, 6, 30))


def test_resolve_quarter():
    t = date(2026, 5, 10)
    assert resolve_range("this_quarter", t) == (date(2026, 4, 1), date(2026, 6, 30))


def test_last_12_months():
    months = last_n_months(12, date(2026, 6, 14))
    assert len(months) == 12
    assert months[-1] == (2026, 6)
    assert months[0] == (2025, 7)


# ===== Aggregations =====

def test_dashboard_stats(admin_client):
    _seed(admin_client)
    d = admin_client.get("/api/dashboard", params={"range": "this_month"}).json()
    assert d["sales"] == "60000.00"                  # 40000 + 20000
    assert d["receivables"]["total"] == "30000.00"   # only order 1 has balance
    assert d["receivables"]["customers"] == 1
    assert d["payables"]["total"] == "7000.00"
    assert d["payables"]["parties"] == 1
    assert d["cash_in_hand"] == "3000.00"            # 5000 - 2000 + 0 opening


def test_dashboard_pending_and_breakdowns(admin_client):
    _seed(admin_client)
    d = admin_client.get("/api/dashboard").json()
    assert len(d["pending_orders"]) == 1
    assert d["pending_orders"][0]["item_name"] == "Chain"
    assert len(d["sales_trend"]) == 12
    names = [c["name"] for c in d["top_customers"]]
    assert names[0] == "Cust A"  # highest billed first
    comp_total = {c["name"]: c["total"] for c in d["sales_by_component"]}
    assert comp_total  # has component breakdown


def test_cash_in_hand_includes_opening_balance(admin_client):
    admin_client.put("/api/settings", json={"opening_cash_balance": "100000"})
    _seed(admin_client)
    d = admin_client.get("/api/dashboard").json()
    assert d["cash_in_hand"] == "103000.00"  # 100000 + 5000 - 2000
