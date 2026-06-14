"""Per-customer / per-party ledgers with opening balance and running balance.

Customer (debtor) view: a debit is what they owe (an order), a credit is what they
paid. Running balance positive = customer owes the shop.

Party (creditor) view: a credit is what the shop owes (a purchase), a debit is what
the shop paid. Running balance positive = the shop owes the supplier.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import CashEntry, Customer, OpeningBalance, Order, Party, Purchase
from app.models.base import BalanceDirection, CashEntryType, EntityType

ZERO = Decimal("0")
_KIND_ORDER = {"opening": 0, "order": 1, "purchase": 1, "payment": 2, "cash": 2}


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def _opening_entries(session: Session, entity_type: EntityType, entity_id: int, debit_dir: BalanceDirection):
    rows = (
        session.query(OpeningBalance)
        .filter(OpeningBalance.entity_type == entity_type, OpeningBalance.entity_id == entity_id)
        .all()
    )
    entries = []
    for ob in rows:
        amount = Decimal(ob.amount or 0)
        is_debit = ob.direction == debit_dir
        entries.append({
            "date": ob.as_of_date, "kind": "opening", "particulars": "Opening balance",
            "debit": amount if is_debit else ZERO, "credit": ZERO if is_debit else amount,
        })
    return entries


def _finalize(entries: list[dict]) -> dict:
    entries.sort(key=lambda e: (e["date"], _KIND_ORDER.get(e["kind"], 9)))
    running = ZERO
    out = []
    for e in entries:
        running += e["debit"] - e["credit"]
        out.append({
            "date": e["date"].isoformat(),
            "particulars": e["particulars"],
            "debit": _money(e["debit"]),
            "credit": _money(e["credit"]),
            "balance": _money(running),
        })
    return {"entries": out, "closing_balance": _money(running)}


def customer_ledger(session: Session, customer_id: int) -> dict:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise LookupError("customer_not_found")
    entries = _opening_entries(session, EntityType.customer, customer_id, BalanceDirection.debit)

    for o in session.query(Order).filter(Order.customer_id == customer_id).all():
        entries.append({"date": o.order_date, "kind": "order",
                        "particulars": f"Order #{o.id} — {o.item_name}",
                        "debit": Decimal(o.total_amount or 0), "credit": ZERO})
        if o.payment_received:
            entries.append({"date": o.order_date, "kind": "payment",
                            "particulars": f"Payment received (order #{o.id})",
                            "debit": ZERO, "credit": Decimal(o.payment_received)})

    for c in session.query(CashEntry).filter(CashEntry.customer_id == customer_id).all():
        amount = Decimal(c.amount or 0)
        received = c.entry_type == CashEntryType.received
        entries.append({"date": c.entry_date, "kind": "cash",
                        "particulars": ("Cash received" if received else "Cash paid")
                        + (f" — {c.details}" if c.details else ""),
                        "debit": ZERO if received else amount,
                        "credit": amount if received else ZERO})

    result = _finalize(entries)
    result["entity"] = {"id": customer.id, "name": customer.name, "type": "customer"}
    return result


def party_ledger(session: Session, party_id: int) -> dict:
    party = session.get(Party, party_id)
    if party is None:
        raise LookupError("party_not_found")
    # For a party, "owe" grows on credit; flip the running sign by treating credit as debit.
    entries = _opening_entries(session, EntityType.party, party_id, BalanceDirection.credit)
    # Normalize so running = (amount we owe) - (we paid): map purchase->debit, payment->credit.
    for p in session.query(Purchase).filter(Purchase.party_id == party_id).all():
        entries.append({"date": p.purchase_date, "kind": "purchase",
                        "particulars": f"Purchase #{p.id}" + (f" — {p.details}" if p.details else ""),
                        "debit": Decimal(p.amount or 0), "credit": ZERO})
        if p.amount_paid:
            entries.append({"date": p.purchase_date, "kind": "payment",
                            "particulars": f"Paid (purchase #{p.id})",
                            "debit": ZERO, "credit": Decimal(p.amount_paid)})

    for c in session.query(CashEntry).filter(CashEntry.party_id == party_id).all():
        amount = Decimal(c.amount or 0)
        paid = c.entry_type == CashEntryType.paid
        entries.append({"date": c.entry_date, "kind": "cash",
                        "particulars": ("Cash paid" if paid else "Cash received")
                        + (f" — {c.details}" if c.details else ""),
                        "debit": ZERO if paid else amount,
                        "credit": amount if paid else ZERO})

    result = _finalize(entries)
    result["entity"] = {"id": party.id, "name": party.name, "type": "party"}
    return result


def set_opening_balance(
    session: Session,
    entity_type: EntityType,
    entity_id: int,
    as_of: date,
    amount: Decimal,
    direction: BalanceDirection,
    created_by: Optional[int] = None,
) -> OpeningBalance:
    """Replace any existing opening balance for the entity with a new one."""
    session.query(OpeningBalance).filter(
        OpeningBalance.entity_type == entity_type, OpeningBalance.entity_id == entity_id
    ).delete()
    ob = OpeningBalance(
        entity_type=entity_type, entity_id=entity_id, as_of_date=as_of,
        amount=amount, direction=direction, created_by=created_by,
    )
    session.add(ob)
    session.flush()
    return ob
