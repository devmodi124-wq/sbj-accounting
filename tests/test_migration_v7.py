"""v7 migration: legacy single-diamond columns backfill into order_item_diamonds.

Pre-v7 a piece stored one diamond inline (``diamond_weight``/``diamond_rate``).
v7 introduces repeatable typed diamond rows; the upgrade must convert each
positive legacy diamond into one row of the "Other fancy" bucket — idempotently.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Customer, DiamondType, ItemCategory, OrderItemDiamond
from app.services.seed import initialize_database


def _seed_legacy_piece(engine, customer_id, category_id):
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO orders (id, customer_id, order_date, status, total_amount, "
            "payment_received, balance, is_backdated, is_cancelled, created_at, updated_at) "
            f"VALUES (1, {customer_id}, '2026-01-01', 'delivered', 100, 0, 100, 0, 0, "
            "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        )
        conn.exec_driver_sql(
            "INSERT INTO order_items (id, order_id, item_category_id, diamond_weight, "
            f"diamond_rate, subtotal, sort_order) VALUES (1, 1, {category_id}, 2.5, 20000, 100, 0)"
        )


def test_v7_diamond_backfill(encrypted_engine):
    engine = encrypted_engine
    initialize_database(engine)
    with Session(engine) as s:
        cust = Customer(name="Legacy Cust")
        s.add(cust)
        s.commit()
        customer_id = cust.id
        category_id = s.query(ItemCategory).first().id

    _seed_legacy_piece(engine, customer_id, category_id)
    initialize_database(engine)  # triggers the diamond backfill

    with Session(engine) as s:
        rows = s.query(OrderItemDiamond).filter_by(order_item_id=1).all()
        assert len(rows) == 1
        assert rows[0].carats == Decimal("2.5")
        assert rows[0].rate == Decimal("20000")
        legacy = s.query(DiamondType).filter(DiamondType.name == "Diamond (Other fancy)").first()
        assert rows[0].diamond_type_id == legacy.id

    # Idempotent: re-running the upgrade does not duplicate the row.
    initialize_database(engine)
    with Session(engine) as s:
        assert s.query(OrderItemDiamond).filter_by(order_item_id=1).count() == 1
