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
        _seed_settings(session)
        session.commit()


# Columns added after v1 — backfilled onto an existing `orders` table. (create_all
# only creates missing *tables*, never alters existing ones.) New nullable FK
# columns; safe to add to a populated table. Note: an existing v1 DB keeps
# item_name NOT NULL — only relevant if a pre-v2 database is upgraded.
_V2_ORDER_COLUMNS = {
    "item_category_id": "INTEGER REFERENCES item_categories(id)",
    "weight_type_id": "INTEGER REFERENCES weight_types(id)",
    "supply_source_id": "INTEGER REFERENCES supply_sources(id)",
}


def _migrate_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(orders)")}
        for column, decl in _V2_ORDER_COLUMNS.items():
            if column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE orders ADD COLUMN {column} {decl}")
        # v3: soft-deactivate flag on customers/parties.
        for table in ("customers", "parties"):
            cols = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if "is_active" not in cols:
                conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
                )


def initialize_database(engine: Engine) -> None:
    """Create tables, migrate, seed defaults, and stamp the schema version.

    Idempotent — safe to call on every startup."""
    create_all(engine)
    _migrate_schema(engine)
    with Session(engine) as session:
        seed_defaults(session)
        with acting_as(None):
            set_setting(session, "schema_version", str(SCHEMA_VERSION))
            session.commit()
