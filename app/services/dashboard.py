"""Dashboard aggregations."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    CashEntry,
    ComponentType,
    Customer,
    Order,
    OrderItem,
    Purchase,
)
from app.models.base import CashEntryType, OrderStatus
from app.services.dateranges import last_n_months, resolve_range
from app.services.settings_store import get_setting

ZERO = Decimal("0")


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def period_sales(session: Session, start: date, end: date) -> Decimal:
    total = (
        session.query(func.coalesce(func.sum(Order.total_amount), 0))
        .filter(Order.order_date >= start, Order.order_date <= end)
        .scalar()
    )
    return Decimal(total or 0)


def outstanding_receivables(session: Session) -> tuple[Decimal, int]:
    rows = session.query(Order.customer_id, Order.balance).filter(Order.balance > 0).all()
    total = sum((r.balance for r in rows), ZERO)
    customers = len({r.customer_id for r in rows})
    return total, customers


def outstanding_payables(session: Session) -> tuple[Decimal, int]:
    rows = session.query(Purchase.party_id, Purchase.balance).filter(Purchase.balance > 0).all()
    total = sum((r.balance for r in rows), ZERO)
    parties = len({r.party_id for r in rows})
    return total, parties


def cash_in_hand(session: Session) -> Decimal:
    received = session.query(func.coalesce(func.sum(CashEntry.amount), 0)).filter(
        CashEntry.entry_type == CashEntryType.received
    ).scalar()
    paid = session.query(func.coalesce(func.sum(CashEntry.amount), 0)).filter(
        CashEntry.entry_type == CashEntryType.paid
    ).scalar()
    opening = get_setting(session, "opening_cash_balance", "0") or "0"
    try:
        opening_dec = Decimal(opening)
    except Exception:
        opening_dec = ZERO
    return Decimal(received or 0) - Decimal(paid or 0) + opening_dec


def sales_trend(session: Session, today: Optional[date] = None) -> list[dict]:
    months = last_n_months(12, today)
    rows = (
        session.query(
            func.strftime("%Y-%m", Order.order_date).label("ym"),
            func.coalesce(func.sum(Order.total_amount), 0).label("total"),
        )
        .group_by("ym")
        .all()
    )
    by_month = {r.ym: Decimal(r.total or 0) for r in rows}
    out = []
    for year, month in months:
        key = f"{year:04d}-{month:02d}"
        out.append({"month": key, "total": _money(by_month.get(key, ZERO))})
    return out


def pending_orders(session: Session, limit: int = 10) -> list[dict]:
    rows = (
        session.query(Order)
        .filter(Order.status == OrderStatus.pending)
        .order_by(Order.order_date.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": o.id,
            "customer_name": o.customer.name if o.customer else "",
            "item_name": o.item_name,
            "order_date": o.order_date.isoformat(),
        }
        for o in rows
    ]


def top_customers(session: Session, start: date, end: date, limit: int = 5) -> list[dict]:
    rows = (
        session.query(
            Customer.id,
            Customer.name,
            func.coalesce(func.sum(Order.total_amount), 0).label("billed"),
            func.coalesce(func.sum(Order.balance), 0).label("balance"),
        )
        .join(Order, Order.customer_id == Customer.id)
        .filter(Order.order_date >= start, Order.order_date <= end)
        .group_by(Customer.id, Customer.name)
        .order_by(func.sum(Order.total_amount).desc())
        .limit(limit)
        .all()
    )
    return [
        {"customer_id": r.id, "name": r.name, "billed": _money(r.billed), "balance": _money(r.balance)}
        for r in rows
    ]


def sales_by_component(session: Session, start: date, end: date) -> list[dict]:
    rows = (
        session.query(
            ComponentType.name,
            func.coalesce(func.sum(OrderItem.price), 0).label("total"),
        )
        .join(OrderItem, OrderItem.component_type_id == ComponentType.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.order_date >= start, Order.order_date <= end)
        .group_by(ComponentType.name)
        .order_by(func.sum(OrderItem.price).desc())
        .all()
    )
    return [{"name": r.name, "total": _money(r.total)} for r in rows]


def build_dashboard(
    session: Session,
    preset: str = "this_month",
    custom_from: Optional[date] = None,
    custom_to: Optional[date] = None,
    today: Optional[date] = None,
) -> dict:
    today = today or date.today()
    start, end = resolve_range(preset, today, custom_from, custom_to)
    recv_total, recv_count = outstanding_receivables(session)
    pay_total, pay_count = outstanding_payables(session)
    return {
        "range": {"preset": preset, "start": start.isoformat(), "end": end.isoformat()},
        "sales": _money(period_sales(session, start, end)),
        "receivables": {"total": _money(recv_total), "customers": recv_count},
        "payables": {"total": _money(pay_total), "parties": pay_count},
        "cash_in_hand": _money(cash_in_hand(session)),
        "sales_trend": sales_trend(session, today),
        "pending_orders": pending_orders(session),
        "top_customers": top_customers(session, start, end),
        "sales_by_component": sales_by_component(session, start, end),
    }
