"""Multi-item orders: weights×rates pricing, split payments, auto cash, audit."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app


def _category_id(client):
    return client.get("/api/item-categories").json()[0]["id"]


def _item(client, **overrides):
    # gross 5g, diamond 2.5ct@20000, metal 6800/g, labour 600/g
    # net = 5 − 2.5/5 = 4.5g; subtotal = 4.5*6800 + 2.5*20000 + 4.5*600 = 83300
    item = {
        "item_category_id": _category_id(client),
        "item_name": "Ring",
        "gross_weight": "5",
        "diamond_weight": "2.5",
        "diamond_rate": "20000",
        "metal_rate": "6800",
        "labour_rate": "600",
    }
    item.update(overrides)
    return item


def _order_payload(client, **overrides):
    payload = {
        "customer_name": "Malti Devi",
        "order_date": date.today().isoformat(),
        "status": "delivered",
        "payments": [{"mode": "cash", "amount": "10000"}],
        "items": [_item(client)],
    }
    payload.update(overrides)
    return payload


def test_create_order_computes_totals(admin_client):
    r = admin_client.post("/api/orders", json=_order_payload(admin_client))
    assert r.status_code == 201
    body = r.json()
    assert body["total_amount"] == "83300.00"
    assert body["balance"] == "73300.00"            # 83300 - 10000
    assert body["payment_received"] == "10000.00"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["net_weight"] == "4.500"            # 5 - 2.5/5
    assert item["subtotal"] == "83300.00"


def test_net_weight_clamped_and_metal_only(admin_client):
    # No stones, metal only: net == gross, subtotal = gross*metal_rate
    body = admin_client.post("/api/orders", json=_order_payload(admin_client, payments=[], items=[
        _item(admin_client, gross_weight="10", diamond_weight=None, diamond_rate=None,
              labour_rate=None, metal_rate="5000"),
    ])).json()
    assert body["items"][0]["net_weight"] == "10.000"
    assert body["items"][0]["subtotal"] == "50000.00"
    assert body["total_amount"] == "50000.00"
    assert body["balance"] == "50000.00"


def test_multi_item_order_sums_subtotals(admin_client):
    cat = _category_id(admin_client)
    payload = _order_payload(admin_client, payments=[], items=[
        {"item_category_id": cat, "gross_weight": "5", "metal_rate": "6800"},   # 34000
        {"item_category_id": cat, "gross_weight": "2", "metal_rate": "6800"},   # 13600
    ])
    body = admin_client.post("/api/orders", json=payload).json()
    assert len(body["items"]) == 2
    assert body["items"][0]["subtotal"] == "34000.00"
    assert body["items"][1]["subtotal"] == "13600.00"
    assert body["total_amount"] == "47600.00"


def test_split_payment_posts_cash_to_cash_in_hand(admin_client):
    payload = _order_payload(admin_client, payments=[
        {"mode": "cash", "amount": "5000"}, {"mode": "upi", "amount": "5000"}])
    body = admin_client.post("/api/orders", json=payload).json()
    assert body["payment_received"] == "10000.00"
    assert len(body["payments"]) == 2

    # Only the cash portion shows in the cash book / Cash-in-Hand.
    cash = admin_client.get("/api/cash").json()
    auto = [c for c in cash if c["amount"] == "5000.00" and c["entry_type"] == "received"]
    assert auto, "cash portion should create a cash-book entry"
    d = admin_client.get("/api/dashboard").json()
    assert d["cash_in_hand"] == "5000.00"


def test_edit_reconciles_auto_cash(admin_client):
    created = admin_client.post("/api/orders", json=_order_payload(admin_client, payments=[
        {"mode": "cash", "amount": "5000"}])).json()
    assert admin_client.get("/api/dashboard").json()["cash_in_hand"] == "5000.00"

    # Edit to remove the cash payment → the auto cash entry is dropped.
    upd = _order_payload(admin_client, payments=[{"mode": "upi", "amount": "5000"}])
    admin_client.put(f"/api/orders/{created['id']}", json=upd)
    assert admin_client.get("/api/dashboard").json()["cash_in_hand"] == "0.00"


def test_create_order_creates_customer_via_matching(admin_client):
    admin_client.post("/api/orders", json=_order_payload(admin_client, customer_name="New Person"))
    found = admin_client.get("/api/customers", params={"q": "new person"}).json()
    assert any(c["name"] == "New Person" for c in found)


def test_update_order_recomputes(admin_client):
    oid = admin_client.post("/api/orders", json=_order_payload(admin_client)).json()["id"]
    cat = _category_id(admin_client)
    upd = _order_payload(admin_client, payments=[], items=[
        {"item_category_id": cat, "gross_weight": "1", "metal_rate": "1000"}])
    body = admin_client.put(f"/api/orders/{oid}", json=upd).json()
    assert body["total_amount"] == "1000.00"
    assert body["balance"] == "1000.00"
    assert len(body["items"]) == 1


def test_employee_backdated_order_rejected(admin_client):
    admin_client.post("/api/users", json={"username": "ramesh", "password": "emp123"})
    emp = TestClient(app)
    emp.post("/auth/login", json={"username": "ramesh", "password": "emp123"})
    old = (date.today() - timedelta(days=30)).isoformat()
    r = emp.post("/api/orders", json=_order_payload(emp, order_date=old))
    assert r.status_code == 422


def test_admin_backdated_order_allowed(admin_client):
    old = (date.today() - timedelta(days=365)).isoformat()
    r = admin_client.post("/api/orders", json=_order_payload(admin_client, order_date=old))
    assert r.status_code == 201
    assert r.json()["is_backdated"] is True


def test_category_required(admin_client):
    payload = _order_payload(admin_client)
    del payload["items"][0]["item_category_id"]
    assert admin_client.post("/api/orders", json=payload).status_code == 422


def test_at_least_one_item_required(admin_client):
    assert admin_client.post("/api/orders", json=_order_payload(admin_client, items=[])).status_code == 422


def test_invalid_category_rejected(admin_client):
    payload = _order_payload(admin_client, items=[_item(admin_client, item_category_id=99999)])
    assert admin_client.post("/api/orders", json=payload).status_code == 422


def test_lookups_persisted(admin_client):
    cats = admin_client.get("/api/item-categories").json()
    weights = admin_client.get("/api/weight-types").json()
    supplies = admin_client.get("/api/supply-sources").json()
    purities = admin_client.get("/api/purity-types").json()
    item = admin_client.post("/api/orders", json=_order_payload(admin_client, items=[_item(
        admin_client, item_category_id=cats[0]["id"], weight_type_id=weights[0]["id"],
        supply_source_id=supplies[0]["id"], purity_type_id=purities[0]["id"],
    )])).json()["items"][0]
    assert item["item_category_id"] == cats[0]["id"]
    assert item["weight_type_id"] == weights[0]["id"]
    assert item["supply_source_id"] == supplies[0]["id"]
    assert item["purity_type_id"] == purities[0]["id"]


def test_item_name_optional(admin_client):
    payload = _order_payload(admin_client, items=[_item(admin_client, item_name=None)])
    r = admin_client.post("/api/orders", json=payload)
    assert r.status_code == 201
    assert r.json()["items"][0]["item_name"] is None


def test_reference_free_text_and_source(admin_client):
    sources = admin_client.get("/api/order-sources").json()
    assert sources, "order sources should be seeded"
    src_id = sources[0]["id"]
    body = admin_client.post("/api/orders", json=_order_payload(
        admin_client, reference="family", source_id=src_id)).json()
    assert body["reference"] == "family"
    assert body["source_id"] == src_id
    summary = [o for o in admin_client.get("/api/orders").json() if o["id"] == body["id"]][0]
    assert summary["source"] == sources[0]["name"]


def test_invalid_source_rejected(admin_client):
    r = admin_client.post("/api/orders", json=_order_payload(admin_client, source_id=99999))
    assert r.status_code == 422


PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000154a24f600000000049454e44ae426082"
)


def test_item_images_upload_list_get_delete(admin_client):
    created = admin_client.post("/api/orders", json=_order_payload(admin_client)).json()
    oid, iid = created["id"], created["items"][0]["id"]
    base = f"/api/orders/{oid}/items/{iid}/images"
    r = admin_client.post(base, files=[
        ("files", ("piece1.png", PNG, "image/png")),
        ("files", ("piece2.png", PNG, "image/png")),
    ])
    assert r.status_code == 201
    imgs = r.json()
    assert len(imgs) == 2
    assert len(admin_client.get(base).json()) == 2

    summary = [o for o in admin_client.get("/api/orders").json() if o["id"] == oid][0]
    assert summary["image_count"] == 2

    raw = admin_client.get(f"{base}/{imgs[0]['id']}")
    assert raw.status_code == 200
    assert raw.headers["content-type"] == "image/png"

    admin_client.delete(f"{base}/{imgs[0]['id']}")
    assert len(admin_client.get(base).json()) == 1


def test_update_preserves_images_on_existing_piece(admin_client):
    created = admin_client.post("/api/orders", json=_order_payload(admin_client)).json()
    oid, iid = created["id"], created["items"][0]["id"]
    base = f"/api/orders/{oid}/items/{iid}/images"
    admin_client.post(base, files=[("files", ("p.png", PNG, "image/png"))])

    cat = _category_id(admin_client)
    upd = _order_payload(admin_client, payments=[], items=[
        {"id": iid, "item_category_id": cat, "item_name": "Edited", "gross_weight": "1", "metal_rate": "999"}])
    body = admin_client.put(f"/api/orders/{oid}", json=upd).json()
    assert body["items"][0]["id"] == iid
    assert body["items"][0]["item_name"] == "Edited"
    assert len(admin_client.get(base).json()) == 1


def test_reject_non_image_upload(admin_client):
    created = admin_client.post("/api/orders", json=_order_payload(admin_client)).json()
    oid, iid = created["id"], created["items"][0]["id"]
    r = admin_client.post(
        f"/api/orders/{oid}/items/{iid}/images",
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    assert r.status_code == 400


def test_void_excludes_from_sales_and_cash_then_restores(admin_client):
    created = admin_client.post("/api/orders", json=_order_payload(admin_client, payments=[
        {"mode": "cash", "amount": "5000"}])).json()
    oid = created["id"]
    assert admin_client.get("/api/dashboard").json()["cash_in_hand"] == "5000.00"
    assert any(r["id"] == oid for r in admin_client.get("/api/reports/sales").json()["rows"])

    # Void → drops out of money (cash + sales total) but stays visible in the list.
    r = admin_client.post(f"/api/orders/{oid}/cancel", json={"cancelled": True})
    assert r.status_code == 200 and r.json()["is_cancelled"] is True
    assert admin_client.get("/api/dashboard").json()["cash_in_hand"] == "0.00"
    sales = admin_client.get("/api/reports/sales").json()["rows"]
    row = [r for r in sales if r["id"] == oid][0]
    assert row["is_cancelled"] is True and row["status"] == "cancelled"
    # excluded from receivables
    assert admin_client.get("/api/dashboard").json()["receivables"]["total"] == "0.00"

    # Restore → cash mirror comes back.
    admin_client.post(f"/api/orders/{oid}/cancel", json={"cancelled": False})
    assert admin_client.get("/api/dashboard").json()["cash_in_hand"] == "5000.00"


def test_delete_order_admin_only_and_removes_cash(admin_client):
    a = admin_client.post("/api/orders", json=_order_payload(admin_client, payments=[
        {"mode": "cash", "amount": "5000"}])).json()["id"]
    b = admin_client.post("/api/orders", json=_order_payload(admin_client, payments=[])).json()["id"]

    # admin delete removes the order and its mirrored cash entry
    assert admin_client.delete(f"/api/orders/{a}").status_code == 200
    assert admin_client.get(f"/api/orders/{a}").status_code == 404
    assert admin_client.get("/api/dashboard").json()["cash_in_hand"] == "0.00"

    # employee cannot delete (logging in as employee ends the admin session)
    admin_client.post("/api/users", json={"username": "emp", "password": "emp123"})
    emp = TestClient(app)
    emp.post("/auth/login", json={"username": "emp", "password": "emp123"})
    assert emp.delete(f"/api/orders/{b}").status_code == 403


def test_order_audited(admin_client):
    admin_client.post("/api/orders", json=_order_payload(admin_client))
    from app.db import engine_state
    from app.models import AuditLog

    with engine_state.sessionmaker() as s:
        tables = {row.table_name for row in s.query(AuditLog).all()}
    assert "orders" in tables
    assert "order_items" in tables        # pieces
    assert "order_payments" in tables      # split-payment lines
