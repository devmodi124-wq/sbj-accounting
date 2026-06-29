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

from app.models import Customer, Order, OrderImage, OrderItem, Party, Purchase
from app.models.base import OrderStatus
from app.services.orders import (
    categories_label,
    item_names_label,
    payment_modes_label,
)


def first_images(session: Session, order_ids: list[int]) -> dict[int, bytes]:
    """First picture (by item then image sort order) for each given order id."""
    if not order_ids:
        return {}
    rows = (
        session.query(OrderItem.order_id, OrderImage.data)
        .join(OrderImage, OrderImage.order_item_id == OrderItem.id)
        .filter(OrderItem.order_id.in_(order_ids))
        .order_by(OrderItem.order_id, OrderItem.sort_order, OrderImage.sort_order)
        .all()
    )
    out: dict[int, bytes] = {}
    for order_id, data in rows:
        if order_id not in out:
            out[order_id] = data
    return out

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


def to_csv(rows: list[dict], columns: list[tuple[str, str]],
           total_row: dict | None = None, sections: list | None = None) -> str:
    """Serialize ``rows`` to CSV using (key, header) ``columns``.

    Appends a TOTAL row when ``total_row`` is given, and any extra ``sections``
    (each ``(title, headers, rows)``) below — used for the sales breakdown."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([header for _, header in columns])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _ in columns])
    if total_row:
        writer.writerow([total_row.get(key, "") for key, _ in columns])
    for title, headers, srows in (sections or []):
        writer.writerow([])
        writer.writerow([title])
        writer.writerow(headers)
        for sr in srows:
            writer.writerow(sr)
    return buf.getvalue()


# ===== Sales report =====

def sales_report(
    session: Session,
    *,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    customer_id: Optional[int] = None,
    category_id: Optional[int] = None,
    weight_type_id: Optional[int] = None,
    source_id: Optional[int] = None,
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
    if source_id:
        q = q.filter(Order.source_id == source_id)
    if status:
        q = q.filter(Order.status == status)
    rows = []
    # Totals + breakdowns over the filtered, non-cancelled set (the real money).
    tot = {"count": 0, "total_amount": ZERO, "payment_received": ZERO, "balance": ZERO}
    by_cat: dict[str, list] = {}
    by_src: dict[str, list] = {}
    for o in q.all():
        # An order can span several categories/weights; filter on any matching piece.
        if category_id and not any(it.item_category_id == category_id for it in o.items):
            continue
        if weight_type_id and not any(it.weight_type_id == weight_type_id for it in o.items):
            continue
        rows.append({
            "id": o.id,
            "order_date": o.order_date.isoformat(),
            "customer_name": o.customer.name if o.customer else "",
            "item_category": categories_label(o),
            "item_name": item_names_label(o),
            "item_count": len(o.items),
            "source": o.source.name if o.source else "",
            "reference": o.reference or "",
            "total_amount": _money(o.total_amount),
            "payment_received": _money(o.payment_received),
            "payment_modes": payment_modes_label(o),
            "balance": _money(o.balance),
            "status": "cancelled" if o.is_cancelled else o.status.value,
            "is_cancelled": o.is_cancelled,
        })
        if o.is_cancelled:
            continue
        tot["count"] += 1
        tot["total_amount"] += Decimal(o.total_amount or 0)
        tot["payment_received"] += Decimal(o.payment_received or 0)
        tot["balance"] += Decimal(o.balance or 0)
        src = o.source.name if o.source else "—"
        bs = by_src.setdefault(src, [0, ZERO]); bs[0] += 1; bs[1] += Decimal(o.total_amount or 0)
        for it in o.items:
            name = it.item_category.name if it.item_category else "—"
            bc = by_cat.setdefault(name, [0, ZERO]); bc[0] += 1; bc[1] += Decimal(it.subtotal or 0)

    page, total = _paginate(rows, sort, direction, limit, offset)
    totals = {
        "count": tot["count"],
        "total_amount": _money(tot["total_amount"]),
        "payment_received": _money(tot["payment_received"]),
        "balance": _money(tot["balance"]),
    }
    breakdown = {
        "by_category": [{"name": n, "count": c, "amount": _money(a)}
                        for n, (c, a) in sorted(by_cat.items(), key=lambda kv: kv[1][1], reverse=True)],
        "by_source": [{"name": n, "count": c, "amount": _money(a)}
                      for n, (c, a) in sorted(by_src.items(), key=lambda kv: kv[1][1], reverse=True)],
    }
    return {"rows": page, "total": total, "totals": totals, "breakdown": breakdown}


# ===== Order / stock report =====

def order_stock_report(
    session: Session,
    *,
    status: Optional[OrderStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category_id: Optional[int] = None,
    sort: str = "order_date",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    today: Optional[date] = None,
) -> dict:
    today = today or date.today()
    q = session.query(Order).filter(Order.is_cancelled.is_(False))
    if status:
        q = q.filter(Order.status == status)
    if date_from:
        q = q.filter(Order.order_date >= date_from)
    if date_to:
        q = q.filter(Order.order_date <= date_to)
    rows = []
    for o in q.all():
        if category_id and not any(it.item_category_id == category_id for it in o.items):
            continue
        days_pending = (today - o.order_date).days if o.status == OrderStatus.pending else 0
        rows.append({
            "id": o.id,
            "order_date": o.order_date.isoformat(),
            "customer_name": o.customer.name if o.customer else "",
            "item_category": categories_label(o),
            "item_name": item_names_label(o),
            "item_count": len(o.items),
            "source": o.source.name if o.source else "",
            "reference": o.reference or "",
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
        .filter(Order.is_cancelled.is_(False))
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
            "party_id": p.party_id,
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
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    sort: str = "lifetime",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    # Date range (optional) scopes the per-customer aggregates to a period; with
    # no range it's the all-time lifetime view. Conditions go in the join's ON
    # clause so customers with no orders in the period still appear.
    join_cond = (Order.customer_id == Customer.id) & (Order.is_cancelled.is_(False))
    if date_from:
        join_cond = join_cond & (Order.order_date >= date_from)
    if date_to:
        join_cond = join_cond & (Order.order_date <= date_to)
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
        .outerjoin(Order, join_cond)
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
              ("item_name", "Item"), ("item_count", "Items"), ("source", "Source"),
              ("reference", "Reference"), ("total_amount", "Total"), ("payment_received", "Received"),
              ("payment_modes", "Modes"), ("balance", "Balance"), ("status", "Status")],
    "stock": [("order_date", "Date"), ("customer_name", "Customer"), ("item_category", "Category"),
              ("item_name", "Item"), ("item_count", "Items"), ("source", "Source"),
              ("reference", "Reference"), ("status", "Status"), ("days_pending", "Days pending")],
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

# Which row keys to total per report (summed into a trailing TOTAL row on export).
_TOTAL_COLUMNS = {
    "sales": {"int": ["item_count"], "money": ["total_amount", "payment_received", "balance"]},
    "stock": {"int": ["item_count"], "money": []},
    "debtors": {"int": [], "money": ["billed", "received", "balance"]},
    "creditors": {"int": [], "money": ["purchased", "paid", "balance"]},
    "purchases": {"int": [], "money": ["amount", "amount_paid", "balance"]},
    "customers": {"int": ["order_count"], "money": ["lifetime", "balance"]},
}


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value if value not in (None, "") else 0).replace(",", ""))
    except Exception:
        return ZERO


def totals_row(name: str, rows: list[dict]) -> dict | None:
    """Build a TOTAL row for ``name`` by summing its numeric columns over ``rows``.

    Cancelled sales rows carry a balance/total of 0 in the report, so they don't
    distort the totals here."""
    cfg = _TOTAL_COLUMNS.get(name)
    if cfg is None or not rows:
        return None
    first_key = CSV_COLUMNS[name][0][0]
    row: dict = {first_key: "TOTAL"}
    for key in cfg["int"]:
        row[key] = sum(int(_to_decimal(r.get(key))) for r in rows)
    for key in cfg["money"]:
        row[key] = _money(sum((_to_decimal(r.get(key)) for r in rows), ZERO))
    return row


def breakdown_sections(data: dict) -> list:
    """Extra export sections (title, headers, rows) for the sales breakdown."""
    bd = data.get("breakdown") or {}
    sections = []
    if bd.get("by_category"):
        sections.append(("Sales by category", ["Category", "Count", "Amount"],
                         [[c["name"], c["count"], c["amount"]] for c in bd["by_category"]]))
    if bd.get("by_source"):
        sections.append(("Sales by source", ["Source", "Count", "Amount"],
                         [[c["name"], c["count"], c["amount"]] for c in bd["by_source"]]))
    return sections
