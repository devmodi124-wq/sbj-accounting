"""Phase 1 — schema creation + idempotent seeding."""
from __future__ import annotations

from app.db import SCHEMA_VERSION
from app.models import ComponentType, PurityType, Setting
from app.services.seed import (
    DEFAULT_COMPONENT_TYPES,
    DEFAULT_PURITY_TYPES,
    seed_defaults,
)


def test_component_and_purity_types_seeded(session):
    comps = session.query(ComponentType).order_by(ComponentType.sort_order).all()
    assert [c.name for c in comps] == DEFAULT_COMPONENT_TYPES
    assert all(c.is_active for c in comps)

    purities = session.query(PurityType).order_by(PurityType.sort_order).all()
    assert [p.name for p in purities] == DEFAULT_PURITY_TYPES


def test_schema_version_recorded(session):
    sv = session.get(Setting, "schema_version")
    assert sv is not None and sv.value == str(SCHEMA_VERSION)


def test_default_settings_present(session):
    assert session.get(Setting, "employee_backdate_limit_days").value == "7"
    assert session.get(Setting, "currency_symbol").value == "₹"
    assert session.get(Setting, "date_format").value == "DD-MM-YYYY"


def test_seed_is_idempotent(session):
    seed_defaults(session)  # run a second time
    seed_defaults(session)  # and a third
    assert session.query(ComponentType).count() == len(DEFAULT_COMPONENT_TYPES)
    assert session.query(PurityType).count() == len(DEFAULT_PURITY_TYPES)


def test_seed_does_not_clobber_edited_settings(session):
    s = session.get(Setting, "employee_backdate_limit_days")
    s.value = "14"
    session.commit()
    seed_defaults(session)
    assert session.get(Setting, "employee_backdate_limit_days").value == "14"
