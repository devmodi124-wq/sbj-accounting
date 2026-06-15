"""Order creation/editing — the single place order totals & balances are computed.

An order holds one or more *items* (pieces); each item has a list of components
whose prices sum to the item subtotal, and the order total is the sum of all
subtotals. The balance is total − payment_received. Backdating is enforced and
``is_backdated`` recorded. All writes go through the session, so the audit layer
logs them.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    Customer,
    ItemCategory,
    Order,
    OrderComponent,
    OrderItem,
    OrderSource,
    SupplySource,
    User,
    WeightType,
)
from app.schemas.orders import OrderIn, OrderItemIn
from app.services.backdating import assert_backdate_allowed, is_backdated
from app.services.matching import get_or_create_customer

ZERO = Decimal("0")


class OrderError(Exception):
    pass


class OrderNotFound(OrderError):
    pass


class CustomerNotFound(OrderError):
    pass


class LookupInvalid(OrderError):
    """A referenced category / weight type / supply source / source does not exist."""

    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"invalid {field}")


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
    order.payment_received = data.payment_received or ZERO
    order.payment_mode = data.payment_mode
    order.is_backdated = is_backdated(data.order_date, today)


def _build_components(item: OrderItemIn) -> tuple[list[OrderComponent], Decimal]:
    components: list[OrderComponent] = []
    subtotal = ZERO
    for index, c in enumerate(item.components):
        price = c.price or ZERO
        components.append(OrderComponent(
            component_type_id=c.component_type_id,
            pcs=c.pcs,
            weight=c.weight,
            purity_type_id=c.purity_type_id,
            rate=c.rate,
            price=price,
            sort_order=index,
        ))
        subtotal += price
    return components, subtotal


def _apply_fields(piece: OrderItem, item: OrderItemIn, index: int) -> None:
    piece.item_name = item.item_name
    piece.item_category_id = item.item_category_id
    piece.weight_type_id = item.weight_type_id
    piece.supply_source_id = item.supply_source_id
    piece.sort_order = index


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
        _apply_fields(piece, item, index)
        components, subtotal = _build_components(item)
        piece.components.extend(components)
        piece.subtotal = subtotal
        order.items.append(piece)
        total += subtotal

    order.total_amount = total
    order.balance = total - order.payment_received
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
        _apply_fields(piece, item, index)
        piece.components.clear()
        session.flush()  # delete the old components before re-adding
        components, subtotal = _build_components(item)
        piece.components.extend(components)
        piece.subtotal = subtotal
        total += subtotal
        if piece.id:
            kept_ids.add(piece.id)

    for pid, piece in existing.items():
        if pid not in kept_ids:
            order.items.remove(piece)

    order.total_amount = total
    order.balance = total - order.payment_received
    session.commit()
    session.refresh(order)
    return order


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


def image_count(order: Order) -> int:
    return sum(len(it.images) for it in order.items)


def component_count(order: Order) -> int:
    return sum(len(it.components) for it in order.items)
