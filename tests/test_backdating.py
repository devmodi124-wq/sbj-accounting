"""Phase 2 — backdating enforcement (employees limited, admins exempt)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models import User
from app.models.base import UserRole
from app.services.backdating import (
    BackdateNotAllowed,
    assert_backdate_allowed,
    is_backdated,
)
from app.services.settings_store import set_setting

TODAY = date(2026, 6, 14)


def _user(role: UserRole) -> User:
    return User(username="u", password_hash="x", role=role)


def test_admin_is_exempt(session):
    admin = _user(UserRole.admin)
    # Far in the past — still fine for an admin.
    assert_backdate_allowed(session, admin, date(2020, 1, 1), today=TODAY)


def test_employee_within_limit_ok(session):
    emp = _user(UserRole.employee)  # default limit 7 days
    assert_backdate_allowed(session, emp, TODAY - timedelta(days=7), today=TODAY)
    assert_backdate_allowed(session, emp, TODAY, today=TODAY)


def test_employee_beyond_limit_rejected(session):
    emp = _user(UserRole.employee)
    with pytest.raises(BackdateNotAllowed):
        assert_backdate_allowed(session, emp, TODAY - timedelta(days=8), today=TODAY)


def test_limit_is_configurable(session):
    set_setting(session, "employee_backdate_limit_days", "0")
    session.commit()
    emp = _user(UserRole.employee)
    assert_backdate_allowed(session, emp, TODAY, today=TODAY)
    with pytest.raises(BackdateNotAllowed):
        assert_backdate_allowed(session, emp, TODAY - timedelta(days=1), today=TODAY)


def test_is_backdated_helper():
    assert is_backdated(TODAY - timedelta(days=1), today=TODAY) is True
    assert is_backdated(TODAY, today=TODAY) is False
