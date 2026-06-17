"""Order creation/editing — the single place totals, balances and the cash-book
mirror are computed.

Each order holds one or more *items* (pieces). An item is priced from a
weights×rates breakdown: net (metal) weight = gross − (diamond+stone+others)/5
(carats→grams at 5 ct = 1 g), and the item subtotal sums the metal, diamond,
stone, others and labour values. The order total is the sum of item subtotals;
balance = total − payments. Cash-mode payment lines are mirrored into one
auto-generated cash-book entry so they show in Cash-in-Hand.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    CashEntry,
    Customer,
    ItemCategory,
    Order,
    OrderItem,
    OrderPayment,
    OrderSource,
    PurityType,
    SupplySource,
    User,
    WeightType,
)
from app.models.base import CashEntryType, PaymentMode
from app.schemas.orders import OrderIn, OrderItemIn
from app.services.backdating import assert_backdate_allowed, is_backdated
from app.services.matching import get_or_create_customer

ZERO = Decimal("0")
FIVE = Decimal("5")  # 5 carat = 1 gram


class OrderError(Exception):
    pass


class OrderNotFound(OrderError):
    pass


class CustomerNotFound(OrderError):
    pass


class LookupInvalid(OrderError):
    """A referenced category / weight / supply / purity / source does not exist."""

    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"invalid {field}")


def _d(value) -> Decimal:
    return value if value is not None else ZERO


def compute_net_weight(item: OrderItemIn) -> Decimal:
    """Net (metal) weight in grams = gross − (diamond+stone+others carats)/5."""
    stones = _d(item.diamond_weight) + _d(item.stone_weight) + _d(item.others_weight)
    net = _d(item.gross_weight) - stones / FIVE
    return net if net > ZERO else ZERO


def compute_subtotal(item: OrderItemIn, net: Decimal) -> Decimal:
    """Item price = metal + diamond + stone + others + labour values."""
    metal = net * _d(item.metal_rate)
    diamond = _d(item.diamond_weight) * _d(item.diamond_rate)
    stone = _d(item.stone_weight) * _d(item.stone_rate)
    others = _d(item.others_weight) * _d(item.others_rate)
    labour = net * _d(item.labour_rate)
    return metal + diamond + stone + others + labour


def _validate_lookups(session: Session, data: OrderIn) -> None:
    if data.source_id is not None and session.get(OrderSource, data.source_id) is None:
        raise LookupInvalid("source")
    for item in data.items:
        if session.get(ItemCategory, item.item_category_id) is None:
            raise LookupInvalid("item_category")
        if item.weight_type_id is not None and session.get(WeightType, item.weight_type_id) is None:
            raise LookupInvalid("weight_type")
        if item.supply_source_id is not None and session.get(SupplySource, item.supply_source_id) is None:
            raise LookupInvalid("supply_source")
        if item.purity_type_id is not None and session.get(PurityType, item.purity_type_id) is None:
            raise LookupInvalid("purity")


def _resolve_customer(session: Session, data: OrderIn, user: User) -> Customer:
    if data.customer_id is not None:
        customer = session.get(Customer, data.customer_id)
        if customer is None:
            raise CustomerNotFound()
        return customer
    customer, _ = get_or_create_customer(session, data.customer_name, created_by=user.id)
    return customer


def _populate_order(order: Order, data: OrderIn, customer: Customer, today: date) -> None:
    order.customer_id = customer.id
    order.order_date = data.order_date
    order.order_code = data.order_code
    order.notes = data.notes
    order.reference = data.reference
    order.source_id = data.source_id
    order.status = data.status
    order.is_backdated = is_backdated(data.order_date, today)


def _apply_item(piece: OrderItem, item: OrderItemIn, index: int) -> None:
    piece.item_name = item.item_name
    piece.item_category_id = item.item_category_id
    piece.weight_type_id = item.weight_type_id
    piece.supply_source_id = item.supply_source_id
    piece.purity_type_id = item.purity_type_id
    piece.gross_weight = item.gross_weight
    piece.diamond_weight = item.diamond_weight
    piece.stone_weight = item.stone_weight
    piece.others_weight = item.others_weight
    piece.metal_rate = item.metal_rate
    piece.diamond_rate = item.diamond_rate
    piece.stone_rate = item.stone_rate
    piece.others_rate = item.others_rate
    piece.labour_rate = item.labour_rate
    net = compute_net_weight(item)
    piece.net_weight = net
    piece.subtotal = compute_subtotal(item, net)
    piece.sort_order = index


def _apply_payments(session: Session, order: Order, data: OrderIn) -> None:
    order.payments.clear()
    session.flush()  # delete old payment lines before re-adding
    total = ZERO
    for index, p in enumerate(data.payments):
        amount = p.amount or ZERO
        order.payments.append(OrderPayment(mode=p.mode, amount=amount, sort_order=index))
        total += amount
    order.payment_received = total
    # Keep the legacy single-mode column meaningful where there's exactly one line.
    order.payment_mode = data.payments[0].mode if len(data.payments) == 1 else None


def _sync_auto_cash(session: Session, order: Order, customer: Customer, today: date) -> None:
    """Mirror the order's cash-mode payments into one auto cash-book entry.

    A cancelled order contributes no cash (its mirror is removed)."""
    cash_total = ZERO if order.is_cancelled else sum(
        (p.amount or ZERO for p in order.payments if p.mode == PaymentMode.cash), ZERO
    )
    existing = (
        session.query(CashEntry)
        .filter(CashEntry.order_id == order.id, CashEntry.auto_generated.is_(True))
        .one_or_none()
    )
    if cash_total > ZERO:
        if existing is None:
            existing = CashEntry(order_id=order.id, auto_generated=True, created_by=order.created_by)
            session.add(existing)
        existing.entry_date = order.order_date
        existing.person_name = customer.name
        existing.customer_id = customer.id
        existing.party_id = None
        existing.details = f"Sale order #{order.id} (cash, auto)"
        existing.entry_type = CashEntryType.received
        existing.amount = cash_total
        existing.is_backdated = is_backdated(order.order_date, today)
    elif existing is not None:
        session.delete(existing)


def create_order(session: Session, user: User, data: OrderIn, today: Optional[date] = None) -> Order:
    today = today or date.today()
    assert_backdate_allowed(session, user, data.order_date, today)
    _validate_lookups(session, data)
    customer = _resolve_customer(session, data, user)

    order = Order(created_by=user.id)
    _populate_order(order, data, customer, today)
    session.add(order)
    session.flush()

    total = ZERO
    for index, item in enumerate(data.items):
        piece = OrderItem(order_id=order.id)
        _apply_item(piece, item, index)
        order.items.append(piece)
        total += piece.subtotal

    _apply_payments(session, order, data)
    order.total_amount = total
    order.balance = total - order.payment_received
    _sync_auto_cash(session, order, customer, today)
    session.commit()
    session.refresh(order)
    return order


def update_order(
    session: Session, user: User, order_id: int, data: OrderIn, today: Optional[date] = None
) -> Order:
    today = today or date.today()
    order = session.get(Order, order_id)
    if order is None:
        raise OrderNotFound()
    assert_backdate_allowed(session, user, data.order_date, today)
    _validate_lookups(session, data)
    customer = _resolve_customer(session, data, user)

    _populate_order(order, data, customer, today)

    # Diff pieces by id so existing pieces keep their pictures; only pieces the
    # user removed are deleted (cascading their images).
    existing = {p.id: p for p in order.items}
    kept_ids: set[int] = set()
    total = ZERO
    for index, item in enumerate(data.items):
        piece = existing.get(item.id) if item.id else None
        if piece is None:
            piece = OrderItem(order_id=order.id)
            order.items.append(piece)
        _apply_item(piece, item, index)
        total += piece.subtotal
        if piece.id:
            kept_ids.add(piece.id)

    for pid, piece in existing.items():
        if pid not in kept_ids:
            order.items.remove(piece)

    _apply_payments(session, order, data)
    order.total_amount = total
    order.balance = total - order.payment_received
    _sync_auto_cash(session, order, customer, today)
    session.commit()
    session.refresh(order)
    return order


def set_cancelled(
    session: Session, user: User, order_id: int, cancelled: bool, today: Optional[date] = None
) -> Order:
    """Soft-void (or restore) an order; reconcile its cash-book mirror."""
    today = today or date.today()
    order = session.get(Order, order_id)
    if order is None:
        raise OrderNotFound()
    order.is_cancelled = cancelled
    customer = order.customer or session.get(Customer, order.customer_id)
    _sync_auto_cash(session, order, customer, today)
    session.commit()
    session.refresh(order)
    return order


def delete_order(session: Session, order_id: int) -> None:
    """Permanently delete an order (cascades items/payments/pictures) and remove
    its mirrored cash entry."""
    order = session.get(Order, order_id)
    if order is None:
        raise OrderNotFound()
    for ce in (
        session.query(CashEntry)
        .filter(CashEntry.order_id == order_id, CashEntry.auto_generated.is_(True))
        .all()
    ):
        session.delete(ce)
    session.delete(order)
    session.commit()


# ===== Read-side helpers (used by lists/reports/dashboard) =====

def categories_label(order: Order) -> str:
    """Distinct item categories across the order, e.g. ``"Ring, Necklace"``."""
    out: list[str] = []
    for it in order.items:
        name = it.item_category.name if it.item_category else None
        if name and name not in out:
            out.append(name)
    return ", ".join(out)


def item_names_label(order: Order) -> str:
    """Non-empty item names across the order, joined."""
    return ", ".join(it.item_name for it in order.items if it.item_name)


def payment_modes_label(order: Order) -> str:
    """Payment modes used, e.g. ``"cash, upi"`` (for reports/exports)."""
    seen: list[str] = []
    for p in order.payments:
        m = p.mode.value if p.mode else None
        if m and m not in seen:
            seen.append(m)
    return ", ".join(seen)


def image_count(order: Order) -> int:
    return sum(len(it.images) for it in order.items)
