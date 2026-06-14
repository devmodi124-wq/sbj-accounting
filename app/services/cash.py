"""Cash-book entry creation/editing (audited, backdate-enforced)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import CashEntry, User
from app.schemas.cash import CashEntryIn
from app.services.backdating import assert_backdate_allowed, is_backdated


class CashEntryNotFound(Exception):
    pass


def _populate(entry: CashEntry, data: CashEntryIn, today: date) -> None:
    entry.entry_date = data.entry_date
    entry.person_name = data.person_name or ""
    entry.customer_id = data.customer_id
    entry.party_id = data.party_id
    entry.details = data.details
    entry.entry_type = data.entry_type
    entry.amount = data.amount
    entry.is_backdated = is_backdated(data.entry_date, today)


def create_cash_entry(
    session: Session, user: User, data: CashEntryIn, today: Optional[date] = None
) -> CashEntry:
    today = today or date.today()
    assert_backdate_allowed(session, user, data.entry_date, today)
    entry = CashEntry(created_by=user.id)
    _populate(entry, data, today)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def update_cash_entry(
    session: Session, user: User, entry_id: int, data: CashEntryIn, today: Optional[date] = None
) -> CashEntry:
    today = today or date.today()
    entry = session.get(CashEntry, entry_id)
    if entry is None:
        raise CashEntryNotFound()
    assert_backdate_allowed(session, user, data.entry_date, today)
    _populate(entry, data, today)
    session.commit()
    session.refresh(entry)
    return entry
