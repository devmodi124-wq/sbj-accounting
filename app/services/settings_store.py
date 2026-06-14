"""Typed helpers for the key/value ``settings`` table."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Setting


def get_setting(session: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    row = session.get(Setting, key)
    return row.value if row is not None else default


def get_int_setting(session: Session, key: str, default: int) -> int:
    raw = get_setting(session, key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
