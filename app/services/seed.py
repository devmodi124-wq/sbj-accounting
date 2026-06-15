"""Database initialization, default seeds, and schema-version handling.

``initialize_database`` is idempotent: safe to call on every startup. It creates
tables on first run, seeds the lookup types + default settings (without clobbering
admin-edited values), and records the schema version.
"""
from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import SCHEMA_VERSION, Base
from app.models import (
    ComponentType,
    ItemCategory,
    OrderSource,
    PurityType,
    Setting,
    SupplySource,
    WeightType,
)
from app.services.audit import acting_as
from app.services.settings_store import set_setting

# Seeded on first run (admin can rename/deactivate/reorder afterwards).
DEFAULT_COMPONENT_TYPES = [
    "Round (RND)",
    "Stone",
    "Marquise (MRQ)",
    "Moti (Pearl)",
    "Chowk (CHK)",
    "Labour",
]

DEFAULT_PURITY_TYPES = ["14 KT", "18 KT", "22 KT", "916", "Silver"]

DEFAULT_ITEM_CATEGORIES = [
    "Ring", "Necklace", "Tops", "Bracelet", "Bangle", "Pendant", "Earrings", "Chain",
]
DEFAULT_WEIGHT_TYPES = ["Lightweight", "Normal", "Heavyweight"]
DEFAULT_SUPPLY_SOURCES = ["On Order", "Stock"]
DEFAULT_ORDER_SOURCES = ["Whatsapp", "Instagram", "Facebook", "Walk-in", "Other"]

# key -> default value. Only inserted when missing; never overwrites existing.
DEFAULT_SETTINGS = {
    "schema_version": str(SCHEMA_VERSION),
    "employee_backdate_limit_days": "7",
    "currency_symbol": "₹",  # ₹
    "date_format": "DD-MM-YYYY",
    "backup_folder_path": "",
    "opening_cash_balance": "0",
    "master_pin_hash": "",
}


def create_all(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def _seed_lookup(session: Session, model, names: list[str]) -> None:
    existing = {name for (name,) in session.query(model.name).all()}
    for order, name in enumerate(names):
        if name not in existing:
            session.add(model(name=name, sort_order=order, is_active=True))


def _seed_settings(session: Session) -> None:
    existing = {key for (key,) in session.query(Setting.key).all()}
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing:
            session.add(Setting(key=key, value=value))


def seed_defaults(session: Session) -> None:
    """Idempotently insert lookup types and default settings (system action)."""
    with acting_as(None):
        _seed_lookup(session, ComponentType, DEFAULT_COMPONENT_TYPES)
        _seed_lookup(session, PurityType, DEFAULT_PURITY_TYPES)
        _seed_lookup(session, ItemCategory, DEFAULT_ITEM_CATEGORIES)
        _seed_lookup(session, WeightType, DEFAULT_WEIGHT_TYPES)
        _seed_lookup(session, SupplySource, DEFAULT_SUPPLY_SOURCES)
        _seed_lookup(session, OrderSource, DEFAULT_ORDER_SOURCES)
        _seed_settings(session)
        session.commit()


def _tables(conn) -> set[str]:
    return {row[0] for row in conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}


def _add_column(conn, table: str, name: str, decl: str) -> None:
    if name not in _columns(conn, table):
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def _is_legacy_orders(conn) -> bool:
    """True when ``order_items`` is still the pre-v4 *components* table.

    Pre-v4, ``order_items`` held the component rows (with ``component_type_id``).
    In v4 it becomes the *piece* table and components live in ``order_components``.
    """
    if "order_items" not in _tables(conn):
        return False
    return "component_type_id" in _columns(conn, "order_items")


def _migrate_pre_create(engine: Engine) -> None:
    """Idempotent schema fixes that must happen *before* ``create_all``.

    Adds late-added columns to pre-existing tables and, for a pre-v4 database,
    moves the legacy ``order_items`` / ``order_images`` tables aside so
    ``create_all`` can build the v4 schema in their place. The backfill that
    re-populates the new tables runs in :func:`_migrate_post_create`.
    """
    with engine.begin() as conn:
        tables = _tables(conn)
        # v3: soft-deactivate flag on customers/parties (no-op on fresh DBs).
        for table in ("customers", "parties"):
            if table in tables:
                _add_column(conn, table, "is_active", "BOOLEAN NOT NULL DEFAULT 1")
        if "orders" in tables:
            # v4 order-level columns (fresh DBs get these from create_all).
            _add_column(conn, "orders", "reference", "TEXT")
            _add_column(conn, "orders", "source_id", "INTEGER")
        if "order_items" in tables and not _is_legacy_orders(conn):
            # v5 per-item weights×rates pricing columns (skip a legacy components
            # table — that is renamed aside below and rebuilt by create_all).
            for col in ("gross_weight", "diamond_weight", "stone_weight",
                        "others_weight", "net_weight", "metal_rate", "diamond_rate",
                        "stone_rate", "others_rate", "labour_rate"):
                _add_column(conn, "order_items", col, "NUMERIC")
            _add_column(conn, "order_items", "purity_type_id", "INTEGER")
        if "cash_entries" in tables:
            # v5 cash-book mirroring of a sale's cash payment.
            _add_column(conn, "cash_entries", "order_id", "INTEGER")
            _add_column(conn, "cash_entries", "auto_generated", "BOOLEAN NOT NULL DEFAULT 0")
        if _is_legacy_orders(conn):
            # Ensure the legacy per-piece columns exist so the backfill can read
            # them (a pre-v2 database never had them).
            _add_column(conn, "orders", "item_name", "VARCHAR(160)")
            _add_column(conn, "orders", "item_category_id", "INTEGER")
            _add_column(conn, "orders", "weight_type_id", "INTEGER")
            _add_column(conn, "orders", "supply_source_id", "INTEGER")
            conn.exec_driver_sql("ALTER TABLE order_items RENAME TO _legacy_order_items")
            if "order_images" in _tables(conn):
                conn.exec_driver_sql("ALTER TABLE order_images RENAME TO _legacy_order_images")


def _migrate_post_create(engine: Engine) -> None:
    """Backfill the v4 multi-item tables from the moved-aside legacy tables.

    Atomic: runs in one transaction and drops the legacy tables at the end, so a
    crash before completion leaves the legacy data intact for a retry on the next
    startup. Each pre-v4 order becomes a single piece carrying its item fields.
    """
    with engine.begin() as conn:
        tables = _tables(conn)
        if "_legacy_order_items" not in tables:
            return
        # One piece per legacy order, carrying its item fields; the per-item
        # weights×rates (v5) start empty and the subtotal preserves the order total.
        conn.exec_driver_sql(
            "INSERT INTO order_items "
            "(order_id, item_name, item_category_id, weight_type_id, supply_source_id, subtotal, sort_order) "
            "SELECT id, item_name, item_category_id, weight_type_id, supply_source_id, total_amount, 0 "
            "FROM orders WHERE id NOT IN (SELECT order_id FROM order_items)"
        )
        if "_legacy_order_images" in tables:
            conn.exec_driver_sql(
                "INSERT INTO order_images "
                "(order_item_id, filename, mime, data, sort_order, created_at) "
                "SELECT p.id, i.filename, i.mime, i.data, i.sort_order, i.created_at "
                "FROM _legacy_order_images i JOIN order_items p ON p.order_id = i.order_id"
            )
            conn.exec_driver_sql("DROP TABLE _legacy_order_images")
        # The pre-v4 component rows are no longer modelled (pricing moved to the
        # weights×rates panel). Preserve them as an orphan `order_components` table
        # for record rather than discarding the data.
        if "order_components" not in tables:
            conn.exec_driver_sql("ALTER TABLE _legacy_order_items RENAME TO order_components")
        else:
            conn.exec_driver_sql("DROP TABLE _legacy_order_items")
    _migrate_payments_backfill(engine)


def _migrate_payments_backfill(engine: Engine) -> None:
    """v5: seed one payment line per legacy order from its amount + mode."""
    with engine.begin() as conn:
        if "order_payments" not in _tables(conn) or "orders" not in _tables(conn):
            return
        conn.exec_driver_sql(
            "INSERT INTO order_payments (order_id, mode, amount, sort_order) "
            "SELECT id, COALESCE(payment_mode, 'cash'), payment_received, 0 FROM orders "
            "WHERE payment_received > 0 AND id NOT IN (SELECT order_id FROM order_payments)"
        )


def initialize_database(engine: Engine) -> None:
    """Create tables, migrate, seed defaults, and stamp the schema version.

    Idempotent — safe to call on every startup."""
    _migrate_pre_create(engine)
    create_all(engine)
    _migrate_post_create(engine)
    with Session(engine) as session:
        seed_defaults(session)
        with acting_as(None):
            set_setting(session, "schema_version", str(SCHEMA_VERSION))
            session.commit()
