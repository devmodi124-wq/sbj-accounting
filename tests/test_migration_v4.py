"""v4 migration: a pre-v4 (single-piece) database upgrades to multi-item cleanly.

Pre-v4 the ``order_items`` table held *components* (FK order_id) and per-piece
fields lived on ``orders``. v4 makes ``order_items`` a *piece*, moves components
to ``order_components``, and moves images per-piece. The migration must turn each
legacy order into one piece without losing components or pictures.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Customer, ComponentType, ItemCategory, Order
from app.services.seed import initialize_database


def _downgrade_to_legacy(engine, customer_id, category_id, component_id):
    """Surgically rewrite the order tables into their pre-v4 shape, then seed
    one legacy order + component + image."""
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE order_images")
        conn.exec_driver_sql("DROP TABLE order_payments")
        conn.exec_driver_sql("DROP TABLE order_items")
        conn.exec_driver_sql(
            "CREATE TABLE order_items ("
            "id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, "
            "component_type_id INTEGER NOT NULL, pcs INTEGER, weight NUMERIC, "
            "purity_type_id INTEGER, rate NUMERIC, price NUMERIC NOT NULL, "
            "sort_order INTEGER NOT NULL DEFAULT 0)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE order_images ("
            "id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, "
            "filename VARCHAR NOT NULL DEFAULT '', mime VARCHAR NOT NULL DEFAULT 'image/jpeg', "
            "data BLOB NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0, created_at DATETIME)"
        )
        # Legacy per-piece columns live on orders pre-v4.
        for col, decl in [("item_name", "VARCHAR"), ("item_category_id", "INTEGER"),
                          ("weight_type_id", "INTEGER"), ("supply_source_id", "INTEGER")]:
            conn.exec_driver_sql(f"ALTER TABLE orders ADD COLUMN {col} {decl}")
        conn.exec_driver_sql(
            "INSERT INTO orders (id, customer_id, order_date, item_name, item_category_id, "
            "status, total_amount, payment_received, balance, is_backdated, is_cancelled, "
            "created_at, updated_at) "
            f"VALUES (1, {customer_id}, '2026-01-01', 'Old Ring', {category_id}, "
            "'delivered', 100, 40, 60, 0, 0, '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        )
        conn.exec_driver_sql(
            "INSERT INTO order_items (id, order_id, component_type_id, price, sort_order) "
            f"VALUES (1, 1, {component_id}, 100, 0)"
        )
        conn.exec_driver_sql(
            "INSERT INTO order_images (id, order_id, filename, mime, data, sort_order, created_at) "
            "VALUES (1, 1, 'p.png', 'image/png', X'89504e47', 0, '2026-01-01 00:00:00')"
        )


def test_v4_migration_preserves_order_data(encrypted_engine):
    engine = encrypted_engine
    # Start from a fully initialized v4 DB, grab some real lookup/customer ids.
    initialize_database(engine)
    with Session(engine) as s:
        cust = Customer(name="Legacy Cust")
        s.add(cust)
        s.commit()
        customer_id = cust.id
        category_id = s.query(ItemCategory).first().id
        component_id = s.query(ComponentType).first().id

    # Make the DB look pre-v4, then run the upgrade again.
    _downgrade_to_legacy(engine, customer_id, category_id, component_id)
    initialize_database(engine)

    with Session(engine) as s:
        order = s.get(Order, 1)
        assert order is not None
        assert len(order.items) == 1               # one piece per legacy order
        piece = order.items[0]
        assert piece.item_name == "Old Ring"
        assert piece.item_category_id == category_id
        assert piece.subtotal == Decimal("100")    # backfilled from order total
        assert len(piece.images) == 1
        assert piece.images[0].filename == "p.png"

    # Legacy component rows are preserved (orphaned) in `order_components`, and the
    # temporary tables are gone — re-running the upgrade is a no-op.
    from app.services.seed import _tables
    with engine.begin() as conn:
        tables = _tables(conn)
        assert "_legacy_order_items" not in tables
        assert "_legacy_order_images" not in tables
        assert "order_components" in tables
        (count,) = conn.exec_driver_sql("SELECT COUNT(*) FROM order_components").fetchone()
        assert count == 1
    initialize_database(engine)
