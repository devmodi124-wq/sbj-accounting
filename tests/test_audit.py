"""Phase 1 — automatic audit logging via session events."""
from __future__ import annotations

import json

from app.models import AuditLog, Customer, User
from app.models.base import AuditAction, UserRole
from app.services.audit import acting_as


def _logs_for(session, table):
    return (
        session.query(AuditLog)
        .filter(AuditLog.table_name == table)
        .order_by(AuditLog.id)
        .all()
    )


def test_insert_is_audited(session):
    session.add(Customer(name="Malti Devi", phone="98XXXXXX21"))
    session.commit()

    logs = _logs_for(session, "customers")
    assert len(logs) == 1
    assert logs[0].action == AuditAction.create
    new = json.loads(logs[0].new_value)
    assert new["name"] == "Malti Devi"
    assert logs[0].old_value is None


def test_update_records_old_and_new(session):
    c = Customer(name="Sunita", phone="111")
    session.add(c)
    session.commit()

    c.phone = "222"
    session.commit()

    update = [l for l in _logs_for(session, "customers") if l.action == AuditAction.update]
    assert len(update) == 1
    old = json.loads(update[0].old_value)
    new = json.loads(update[0].new_value)
    assert old["phone"] == "111"
    assert new["phone"] == "222"
    assert "name" not in new  # only changed columns recorded


def test_delete_is_audited(session):
    c = Customer(name="Temp")
    session.add(c)
    session.commit()
    session.delete(c)
    session.commit()

    deletes = [l for l in _logs_for(session, "customers") if l.action == AuditAction.delete]
    assert len(deletes) == 1
    assert deletes[0].new_value is None


def test_acting_user_recorded(session):
    user = User(username="ramesh", password_hash="x", role=UserRole.employee)
    session.add(user)
    session.commit()

    with acting_as(user.id):
        session.add(Customer(name="With User"))
        session.commit()
    log = _logs_for(session, "customers")[-1]
    assert log.user_id == user.id


def test_audit_log_is_not_self_audited(session):
    session.add(Customer(name="X"))
    session.commit()
    # No audit rows should exist describing the audit_log table itself.
    assert _logs_for(session, "audit_log") == []
