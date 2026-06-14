"""Shared customer/party name matching.

One canonical place for "does this name already exist?" so manual entry (New Order)
and bulk Import behave identically: matching is case-insensitive and trimmed.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Customer, Party

_WS = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Trim, collapse internal whitespace, and lowercase for comparison."""
    return _WS.sub(" ", (name or "").strip()).lower()


def _find_match(session: Session, model, name: str):
    norm = (name or "").strip().lower()
    if not norm:
        return None
    return (
        session.query(model)
        .filter(func.lower(func.trim(model.name)) == norm)
        .first()
    )


def _search(session: Session, model, query: str, limit: int, include_inactive: bool = False):
    q = (query or "").strip().lower()
    stmt = session.query(model)
    if not include_inactive:
        stmt = stmt.filter(model.is_active.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.filter(func.lower(model.name).like(like))
        # Prefix matches first, then alphabetical.
        prefix = func.lower(model.name).like(f"{q}%")
        return stmt.order_by(prefix.desc(), model.name).limit(limit).all()
    return stmt.order_by(model.name).limit(limit).all()


# ===== Customers =====

def find_customer_match(session: Session, name: str) -> Optional[Customer]:
    return _find_match(session, Customer, name)


def search_customers(
    session: Session, query: str, limit: int = 10, include_inactive: bool = False
) -> list[Customer]:
    return _search(session, Customer, query, limit, include_inactive)


def get_or_create_customer(
    session: Session, name: str, created_by: Optional[int] = None, **extra
) -> tuple[Customer, bool]:
    """Return (customer, created). Reuses an existing match before creating."""
    existing = find_customer_match(session, name)
    if existing is not None:
        return existing, False
    customer = Customer(name=name.strip(), created_by=created_by, **extra)
    session.add(customer)
    session.flush()
    return customer, True


# ===== Parties =====

def find_party_match(session: Session, name: str) -> Optional[Party]:
    return _find_match(session, Party, name)


def search_parties(
    session: Session, query: str, limit: int = 10, include_inactive: bool = False
) -> list[Party]:
    return _search(session, Party, query, limit, include_inactive)


def get_or_create_party(
    session: Session, name: str, created_by: Optional[int] = None, **extra
) -> tuple[Party, bool]:
    existing = find_party_match(session, name)
    if existing is not None:
        return existing, False
    party = Party(name=name.strip(), created_by=created_by, **extra)
    session.add(party)
    session.flush()
    return party, True
