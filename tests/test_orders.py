"""Phase 4 / multi-item orders: totals, balance, customer create, backdating, audit."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app


def _component_ids(client):
    return [t["id"] for t in client.get("/api/component-types").json()]


def _category_id(client):
    return client.get("/api/item-categories").json()[0]["id"]


def _item(client, **overrides):
    comps = _component_ids(client)
    item = {
        "item_category_id": _category_id(client),
        "item_name": "Ring",
        "components": [
            {"component_type_id": comps[0], "weight": "4.055", "rate": "9900", "price": "35430"},
            {"component_type_id": comps[5], "price": "5440"},
        ],
    }
    item.update(overrides)
    return item


def _order_payload(client, **overrides):
    payload = {
        "customer_name": "Malti Devi",
        "order_date": date.today().isoformat(),
        "status": "delivered",
        "payment_received": "10000",
        "payment_mode": "cash",
        "items": [_item(client)],
    }
    payload.update(overrides)
    return payload


def test_create_order_computes_totals(admin_client):
    r = admin_client.post("/api/orders", json=_order_payload(admin_client))
    assert r.status_code == 201
    body = r.json()
    assert body["total_amount"] == "40870.00"          # 35430 + 5440
    assert body["balance"] == "30870.00"               # 40870 - 10000
    assert len(body["items"]) == 1
    assert len(body["items"][0]["components"]) == 2
    assert body["items"][0]["subtotal"] == "40870.00"


def test_multi_item_order_sums_subtotals(admin_client):
    comps = _component_ids(admin_client)
    cat = _category_id(admin_client)
    payload = _order_payload(admin_client, payment_received="0", items=[
        {"item_category_id": cat, "item_name": "Ring",
         "components": [{"component_type_id": comps[0], "price": "1000"}]},
        {"item_category_id": cat, "item_name": "Chain",
         "components": [{"component_type_id": comps[0], "price": "500"},
                        {"component_type_id": comps[5], "price": "200"}]},
    ])
    body = admin_client.post("/api/orders", json=payload).json()
    assert len(body["items"]) == 2
    assert body["total_amount"] == "1700.00"           # 1000 + (500+200)
    assert body["items"][0]["subtotal"] == "1000.00"
    assert body["items"][1]["subtotal"] == "700.00"


def test_create_order_creates_customer_via_matching(admin_client):
    admin_client.post("/api/orders", json=_order_payload(admin_client, customer_name="New Person"))
    found = admin_client.get("/api/customers", params={"q": "new person"}).json()
    assert any(c["name"] == "New Person" for c in found)


def test_create_reuses_existing_customer(admin_client):
    admin_client.post("/api/orders", json=_order_payload(admin_client, customer_name="Repeat Cust"))
    admin_client.post("/api/orders", json=_order_payload(admin_client, customer_name="  repeat cust "))
    matches = admin_client.get("/api/customers", params={"q": "repeat cust"}).json()
    assert len([c for c in matches if c["name"].lower() == "repeat cust"]) == 1


def test_update_order_recomputes(admin_client):
    oid = admin_client.post("/api/orders", json=_order_payload(admin_client)).json()["id"]
    comps = _component_ids(admin_client)
    cat = _category_id(admin_client)
    upd = _order_payload(admin_client, payment_received="0", items=[
        {"item_category_id": cat, "components": [{"component_type_id": comps[0], "price": "1000"}]},
    ])
    body = admin_client.put(f"/api/orders/{oid}", json=upd).json()
    assert body["total_amount"] == "1000.00"
    assert body["balance"] == "1000.00"
    assert len(body["items"]) == 1
    assert len(body["items"][0]["components"]) == 1


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
    r = admin_client.post("/api/orders", json=payload)
    assert r.status_code == 422  # pydantic: field required


def test_at_least_one_item_required(admin_client):
    payload = _order_payload(admin_client, items=[])
    r = admin_client.post("/api/orders", json=payload)
    assert r.status_code == 422


def test_invalid_category_rejected(admin_client):
    payload = _order_payload(admin_client, items=[_item(admin_client, item_category_id=99999)])
    r = admin_client.post("/api/orders", json=payload)
    assert r.status_code == 422


def test_category_weight_supply_persisted(admin_client):
    cats = admin_client.get("/api/item-categories").json()
    weights = admin_client.get("/api/weight-types").json()
    supplies = admin_client.get("/api/supply-sources").json()
    payload = _order_payload(admin_client, items=[_item(
        admin_client, item_category_id=cats[0]["id"],
        weight_type_id=weights[0]["id"], supply_source_id=supplies[0]["id"],
    )])
    item = admin_client.post("/api/orders", json=payload).json()["items"][0]
    assert item["item_category_id"] == cats[0]["id"]
    assert item["weight_type_id"] == weights[0]["id"]
    assert item["supply_source_id"] == supplies[0]["id"]


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
    # summary surfaces the source name
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

    # order list reports the total image count across pieces
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

    # Edit the order, sending the existing piece back by id → image survives.
    comps = _component_ids(admin_client)
    cat = _category_id(admin_client)
    upd = _order_payload(admin_client, payment_received="0", items=[
        {"id": iid, "item_category_id": cat, "item_name": "Edited",
         "components": [{"component_type_id": comps[0], "price": "999"}]},
    ])
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


def test_order_audited(admin_client):
    admin_client.post("/api/orders", json=_order_payload(admin_client))
    from app.db import engine_state
    from app.models import AuditLog

    with engine_state.sessionmaker() as s:
        tables = {row.table_name for row in s.query(AuditLog).all()}
    assert "orders" in tables
    assert "order_items" in tables        # pieces
    assert "order_components" in tables    # component breakdown
