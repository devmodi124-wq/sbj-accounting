"""Automatic audit logging.

Every mutating write to a mapped table (except ``audit_log`` itself) produces an
``AuditLog`` row, captured via SQLAlchemy ``Session`` events. Route handlers and
services never log manually — they only set the acting user for the request via
:func:`acting_as` (or the ``current_user_id`` contextvar set by middleware).
"""
from __future__ import annotations

import enum
import json
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator, Optional

from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.orm import Session

from app.models.base import AuditAction
from app.models.system import AuditLog

# Set per-request (middleware) or per-operation (acting_as). None = system action.
current_user_id: ContextVar[Optional[int]] = ContextVar("current_user_id", default=None)

# Never audit the audit log itself (recursion), nor the churny session table.
_EXCLUDED_TABLES = {"audit_log", "sessions"}

_PENDING_KEY = "_audit_pending"


@contextmanager
def acting_as(user_id: Optional[int]) -> Iterator[None]:
    """Temporarily set the acting user (e.g. for seeding/bootstrap or scripts)."""
    token = current_user_id.set(user_id)
    try:
        yield
    finally:
        current_user_id.reset(token)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    return value


def _skip(obj: Any) -> bool:
    return getattr(obj, "__tablename__", None) in _EXCLUDED_TABLES


def _pk_str(obj: Any) -> str:
    mapper = sa_inspect(obj).mapper
    return ":".join(str(getattr(obj, col.key)) for col in mapper.primary_key)


def _column_values(obj: Any) -> dict[str, Any]:
    mapper = sa_inspect(obj).mapper
    return {attr.key: _json_safe(getattr(obj, attr.key)) for attr in mapper.column_attrs}


def _changes(obj: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (old, new) dicts containing only changed columns."""
    state = sa_inspect(obj)
    old: dict[str, Any] = {}
    new: dict[str, Any] = {}
    for attr in state.mapper.column_attrs:
        hist = state.attrs[attr.key].history
        if hist.has_changes():
            old[attr.key] = _json_safe(hist.deleted[0]) if hist.deleted else None
            new[attr.key] = _json_safe(hist.added[0]) if hist.added else None
    return old, new


def _record(action: AuditAction, obj: Any, old: Optional[dict], new: Optional[dict],
            user_id: Optional[int]) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "action": action,
        "table_name": obj.__tablename__,
        "record_id": _pk_str(obj),
        "old_value": json.dumps(old) if old else None,
        "new_value": json.dumps(new) if new else None,
    }


@event.listens_for(Session, "after_flush")
def _collect_changes(session: Session, _flush_context) -> None:
    pending: list[dict] = session.info.setdefault(_PENDING_KEY, [])
    user_id = current_user_id.get()

    for obj in session.new:
        if _skip(obj):
            continue
        pending.append(_record(AuditAction.create, obj, None, _column_values(obj), user_id))

    for obj in session.dirty:
        if _skip(obj) or not session.is_modified(obj, include_collections=False):
            continue
        old, new = _changes(obj)
        if not old and not new:
            continue
        pending.append(_record(AuditAction.update, obj, old, new, user_id))

    for obj in session.deleted:
        if _skip(obj):
            continue
        pending.append(_record(AuditAction.delete, obj, _column_values(obj), None, user_id))


@event.listens_for(Session, "before_commit")
def _write_audit(session: Session) -> None:
    # Force any pending user changes to flush first, so after_flush has collected
    # their records (commit's own flush would otherwise run *after* this hook).
    session.flush()
    pending = session.info.pop(_PENDING_KEY, None)
    if not pending:
        return
    session.add_all([AuditLog(**rec) for rec in pending])
    # Flush the audit rows into the same transaction. This re-enters after_flush,
    # but those AuditLog objects are skipped (excluded table).
    session.flush()
