"""Report queries (sales, stock, debtors, creditors, purchases, customers).

Each report returns a list of plain dicts so the same rows serve both the JSON API
and CSV export. Sorting/pagination are applied in Python after aggregation (data
volumes for a single shop are small).
"""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Customer, Order, Party, Purchase
from app.models.base import OrderStatus
from app.services.orders import (
    categories_label,
    component_count,
    item_names_label,
)

ZERO = Decimal("0")


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def ageing_bucket(ref_date: date, txn_date: Optional[date]) -> str:
    if txn_date is None:
        return "—"
    days = (ref_date - txn_date).days
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


def _paginate(rows: list, sort: Optional[str], direction: str, limit: int, offset: int):
    total = len(rows)
    if sort:
        rows = sorted(
            rows,
            key=lambda r: (r.get(sort) is None, _sort_key(r.get(sort))),
            reverse=(direction == "desc"),
        )
    return rows[offset : offset + limit], total


def _sort_key(value):
    # Numeric strings sort numerically; everything else as lowercase string.
    if isinstance(value, (int, float, Decimal)):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return str(value).lower()


def to_csv(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    """Serialize ``rows`` to CSV using (key, header) ``columns``."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([header for _, header in columns])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _ in columns])
    return buf.getvalue()


# ===== Sales report =====

def sales_report(
    session: Session,
    *,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    customer_id: Optional[int] = None,
    category_id: Optional[int] = None,
    status: Optional[OrderStatus] = None,
    sort: str = "order_date",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    q = session.query(Order)
    if date_from:
        q = q.filter(Order.order_date >= date_from)
    if date_to:
        q = q.filter(Order.order_date <= date_to)
    if customer_id:
        q = q.filter(Order.customer_id == customer_id)
    if status:
        q = q.filter(Order.status == status)
    rows = []
    for o in q.all():
        # An order can span several categories; filter on any matching piece.
        if category_id and not any(it.item_category_id == category_id for it in o.items):
            continue
        rows.append({
            "id": o.id,
            "order_date": o.order_date.isoformat(),
            "customer_name": o.customer.name if o.customer else "",
            "item_category": categories_label(o),
            "item_name": item_names_label(o),
            "item_count": len(o.items),
            "total_amount": _money(o.total_amount),
            "payment_received": _money(o.payment_received),
            "balance": _money(o.balance),
            "status": o.status.value,
        })
    page, total = _paginate(rows, sort, direction, limit, offset)
    return {"rows": page, "total": total}


# ===== Order / stock report =====

def order_stock_report(
    session: Session,
    *,
    status: Optional[OrderStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    sort: str = "order_date",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    today: Optional[date] = None,
) -> dict:
    today = today or date.today()
    q = session.query(Order)
    if status:
        q = q.filter(Order.status == status)
    if date_from:
        q = q.filter(Order.order_date >= date_from)
    if date_to:
        q = q.filter(Order.order_date <= date_to)
    rows = []
    for o in q.all():
        days_pending = (today - o.order_date).days if o.status == OrderStatus.pending else 0
        rows.append({
            "id": o.id,
            "order_date": o.order_date.isoformat(),
            "customer_name": o.customer.name if o.customer else "",
            "item_category": categories_label(o),
            "item_name": item_names_label(o),
            "item_count": len(o.items),
            "components": component_count(o),
            "status": o.status.value,
            "days_pending": days_pending,
        })
    page, total = _paginate(rows, sort, direction, limit, offset)
    return {"rows": page, "total": total}


# ===== Debtors report =====

def debtors_report(
    session: Session,
    *,
    search: str = "",
    ageing: Optional[str] = None,
    sort: str = "balance",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    today: Optional[date] = None,
) -> dict:
    today = today or date.today()
    q = (
        session.query(
            Customer.id,
            Customer.name,
            Customer.phone,
            func.coalesce(func.sum(Order.total_amount), 0).label("billed"),
            func.coalesce(func.sum(Order.payment_received), 0).label("received"),
            func.coalesce(func.sum(Order.balance), 0).label("balance"),
            func.max(Order.order_date).label("last_txn"),
        )
        .join(Order, Order.customer_id == Customer.id)
        .group_by(Customer.id, Customer.name, Customer.phone)
        .having(func.sum(Order.balance) > 0)
    )
    if search:
        q = q.filter(func.lower(Customer.name).like(f"%{search.lower()}%"))

    rows = []
    total_outstanding = ZERO
    for r in q.all():
        bucket = ageing_bucket(today, r.last_txn)
        if ageing and bucket != ageing:
            continue
        total_outstanding += Decimal(r.balance or 0)
        rows.append({
            "customer_id": r.id,
            "name": r.name,
            "phone": r.phone or "",
            "billed": _money(r.billed),
            "received": _money(r.received),
            "balance": _money(r.balance),
            "last_txn": r.last_txn.isoformat() if r.last_txn else "",
            "ageing": bucket,
        })
    page, total = _paginate(rows, sort, direction, limit, offset)
    return {"rows": page, "total": total, "total_outstanding": _money(total_outstanding)}


# ===== Creditors report (mirror of debtors, via purchases) =====

def creditors_report(
    session: Session,
    *,
    search: str = "",
    ageing: Optional[str] = None,
    sort: str = "balance",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    today: Optional[date] = None,
) -> dict:
    today = today or date.today()
    q = (
        session.query(
            Party.id,
            Party.name,
            Party.phone,
            func.coalesce(func.sum(Purchase.amount), 0).label("purchased"),
            func.coalesce(func.sum(Purchase.amount_paid), 0).label("paid"),
            func.coalesce(func.sum(Purchase.balance), 0).label("balance"),
            func.max(Purchase.purchase_date).label("last_txn"),
        )
        .join(Purchase, Purchase.party_id == Party.id)
        .group_by(Party.id, Party.name, Party.phone)
        .having(func.sum(Purchase.balance) > 0)
    )
    if search:
        q = q.filter(func.lower(Party.name).like(f"%{search.lower()}%"))

    rows = []
    total_outstanding = ZERO
    for r in q.all():
        bucket = ageing_bucket(today, r.last_txn)
        if ageing and bucket != ageing:
            continue
        total_outstanding += Decimal(r.balance or 0)
        rows.append({
            "party_id": r.id,
            "name": r.name,
            "phone": r.phone or "",
            "purchased": _money(r.purchased),
            "paid": _money(r.paid),
            "balance": _money(r.balance),
            "last_txn": r.last_txn.isoformat() if r.last_txn else "",
            "ageing": bucket,
        })
    page, total = _paginate(rows, sort, direction, limit, offset)
    return {"rows": page, "total": total, "total_outstanding": _money(total_outstanding)}


# ===== Purchase report =====

def purchase_report(
    session: Session,
    *,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    party_id: Optional[int] = None,
    status: Optional[str] = None,
    sort: str = "purchase_date",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    q = session.query(Purchase)
    if date_from:
        q = q.filter(Purchase.purchase_date >= date_from)
    if date_to:
        q = q.filter(Purchase.purchase_date <= date_to)
    if party_id:
        q = q.filter(Purchase.party_id == party_id)
    rows = []
    for p in q.all():
        if status and p.status != status:
            continue
        rows.append({
            "id": p.id,
            "purchase_date": p.purchase_date.isoformat(),
            "party_name": p.party.name if p.party else "",
            "details": p.details or "",
            "amount": _money(p.amount),
            "amount_paid": _money(p.amount_paid),
            "balance": _money(p.balance),
            "status": p.status,
        })
    page, total = _paginate(rows, sort, direction, limit, offset)
    return {"rows": page, "total": total}


# ===== Customer report =====

def customer_report(
    session: Session,
    *,
    search: str = "",
    sort: str = "lifetime",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    q = (
        session.query(
            Customer.id,
            Customer.name,
            Customer.phone,
            func.coalesce(func.sum(Order.total_amount), 0).label("lifetime"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.balance), 0).label("balance"),
            func.max(Order.order_date).label("last_visit"),
        )
        .outerjoin(Order, Order.customer_id == Customer.id)
        .group_by(Customer.id, Customer.name, Customer.phone)
    )
    if search:
        q = q.filter(func.lower(Customer.name).like(f"%{search.lower()}%"))

    rows = []
    for r in q.all():
        count = r.order_count or 0
        avg = (Decimal(r.lifetime or 0) / count) if count else ZERO
        rows.append({
            "customer_id": r.id,
            "name": r.name,
            "phone": r.phone or "",
            "lifetime": _money(r.lifetime),
            "order_count": count,
            "avg_order_value": _money(avg),
            "balance": _money(r.balance),
            "last_visit": r.last_visit.isoformat() if r.last_visit else "",
        })
    page, total = _paginate(rows, sort, direction, limit, offset)
    return {"rows": page, "total": total}


# Column definitions for CSV export, keyed by report name.
CSV_COLUMNS = {
    "sales": [("order_date", "Date"), ("customer_name", "Customer"), ("item_category", "Category"),
              ("item_name", "Item"), ("item_count", "Items"), ("total_amount", "Total"),
              ("payment_received", "Received"), ("balance", "Balance"), ("status", "Status")],
    "stock": [("order_date", "Date"), ("customer_name", "Customer"), ("item_category", "Category"),
              ("item_name", "Item"), ("item_count", "Items"), ("components", "Components"),
              ("status", "Status"), ("days_pending", "Days pending")],
    "debtors": [("name", "Customer"), ("phone", "Phone"), ("billed", "Total billed"),
                ("received", "Received"), ("balance", "Balance"), ("last_txn", "Last txn"),
                ("ageing", "Ageing")],
    "creditors": [("name", "Supplier"), ("phone", "Phone"), ("purchased", "Total purchased"),
                  ("paid", "Paid"), ("balance", "Balance"), ("last_txn", "Last txn"),
                  ("ageing", "Ageing")],
    "purchases": [("purchase_date", "Date"), ("party_name", "Supplier"), ("details", "Details"),
                  ("amount", "Amount"), ("amount_paid", "Paid"), ("balance", "Balance"),
                  ("status", "Status")],
    "customers": [("name", "Customer"), ("phone", "Phone"), ("lifetime", "Lifetime"),
                  ("order_count", "Orders"), ("avg_order_value", "Avg order"),
                  ("balance", "Balance"), ("last_visit", "Last visit")],
}
