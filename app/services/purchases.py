"""Purchase creation/editing — balance derived, party find-or-create, audited."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Party, Purchase, User
from app.schemas.purchases import PurchaseIn
from app.services.backdating import assert_backdate_allowed, is_backdated
from app.services.matching import get_or_create_party

ZERO = Decimal("0")


class PurchaseNotFound(Exception):
    pass


class PartyNotFound(Exception):
    pass


def _resolve_party(session: Session, data: PurchaseIn, user: User) -> Party:
    if data.party_id is not None:
        party = session.get(Party, data.party_id)
        if party is None:
            raise PartyNotFound()
        return party
    party, _ = get_or_create_party(session, data.party_name, created_by=user.id)
    return party


def _populate(purchase: Purchase, data: PurchaseIn, party: Party, today: date) -> None:
    purchase.purchase_date = data.purchase_date
    purchase.party_id = party.id
    purchase.details = data.details
    purchase.entry_notes = data.entry_notes
    purchase.amount = data.amount or ZERO
    purchase.amount_paid = data.amount_paid or ZERO
    purchase.balance = purchase.amount - purchase.amount_paid
    purchase.is_backdated = is_backdated(data.purchase_date, today)


def create_purchase(
    session: Session, user: User, data: PurchaseIn, today: Optional[date] = None
) -> Purchase:
    today = today or date.today()
    assert_backdate_allowed(session, user, data.purchase_date, today)
    party = _resolve_party(session, data, user)
    purchase = Purchase(created_by=user.id)
    _populate(purchase, data, party, today)
    session.add(purchase)
    session.commit()
    session.refresh(purchase)
    return purchase


def update_purchase(
    session: Session, user: User, purchase_id: int, data: PurchaseIn, today: Optional[date] = None
) -> Purchase:
    today = today or date.today()
    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise PurchaseNotFound()
    assert_backdate_allowed(session, user, data.purchase_date, today)
    party = _resolve_party(session, data, user)
    _populate(purchase, data, party, today)
    session.commit()
    session.refresh(purchase)
    return purchase


def delete_purchase(session: Session, purchase_id: int) -> None:
    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise PurchaseNotFound()
    session.delete(purchase)
    session.commit()
