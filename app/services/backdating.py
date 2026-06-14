"""Backdating policy: employees cannot enter records older than a configurable limit.

Admins are exempt. The limit (days) is the ``employee_backdate_limit_days`` setting.
Used by orders, cash entries, and purchases when creating/editing dated records.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import User
from app.models.base import UserRole
from app.services.settings_store import get_int_setting

DEFAULT_LIMIT_DAYS = 7


class BackdateNotAllowed(Exception):
    """Raised when an employee tries to enter a date earlier than allowed."""

    def __init__(self, entry_date: date, earliest: date) -> None:
        self.entry_date = entry_date
        self.earliest = earliest
        super().__init__(
            f"Date {entry_date.isoformat()} is older than the allowed limit "
            f"(earliest {earliest.isoformat()}). Ask an admin to enter it."
        )


def earliest_allowed(session: Session, today: Optional[date] = None) -> date:
    today = today or date.today()
    limit = get_int_setting(session, "employee_backdate_limit_days", DEFAULT_LIMIT_DAYS)
    return today - timedelta(days=limit)


def is_backdated(entry_date: date, today: Optional[date] = None) -> bool:
    return entry_date < (today or date.today())


def assert_backdate_allowed(
    session: Session, user: User, entry_date: date, today: Optional[date] = None
) -> None:
    """Raise :class:`BackdateNotAllowed` if ``user`` may not use ``entry_date``."""
    if user.role == UserRole.admin:
        return
    earliest = earliest_allowed(session, today)
    if entry_date < earliest:
        raise BackdateNotAllowed(entry_date, earliest)
