"""Database initialization, default seeds, and schema-version handling.

``initialize_database`` is idempotent: safe to call on every startup. It creates
tables on first run, seeds the lookup types + default settings (without clobbering
admin-edited values), and records the schema version.
"""
from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import SCHEMA_VERSION, Base
from app.models import ComponentType, PurityType, Setting
from app.services.audit import acting_as

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
        _seed_settings(session)
        session.commit()


def initialize_database(engine: Engine) -> None:
    """Create tables + seed defaults. Safe to call on every startup."""
    create_all(engine)
    with Session(engine) as session:
        seed_defaults(session)
