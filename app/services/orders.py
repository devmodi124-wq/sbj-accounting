"""Order creation/editing — the single place order totals & balances are computed.

Totals are derived from item prices and stored denormalized on the order; the
balance is total − payment_received. Backdating is enforced and ``is_backdated``
recorded. All writes go through the session, so the audit layer logs them.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Customer, Order, OrderItem, User
from app.schemas.orders import OrderIn
from app.services.backdating import assert_backdate_allowed, is_backdated
from app.services.matching import get_or_create_customer

ZERO = Decimal("0")


class OrderError(Exception):
    pass


class OrderNotFound(OrderError):
    pass


class CustomerNotFound(OrderError):
    pass


def _resolve_customer(session: Session, data: OrderIn, user: User) -> Customer:
    if data.customer_id is not None:
        customer = session.get(Customer, data.customer_id)
        if customer is None:
            raise CustomerNotFound()
        return customer
    customer, _ = get_or_create_customer(session, data.customer_name, created_by=user.id)
    return customer


def _apply_items(session: Session, order: Order, items) -> Decimal:
    order.items.clear()  # delete-orphan removes any previous rows
    session.flush()
    total = ZERO
    for index, item in enumerate(items):
        price = item.price or ZERO
        order.items.append(
            OrderItem(
                component_type_id=item.component_type_id,
                pcs=item.pcs,
                weight=item.weight,
                purity_type_id=item.purity_type_id,
                rate=item.rate,
                price=price,
                sort_order=index,
            )
        )
        total += price
    return total


def _populate(order: Order, data: OrderIn, customer: Customer, today: date) -> None:
    order.customer_id = customer.id
    order.order_date = data.order_date
    order.item_name = data.item_name
    order.order_code = data.order_code
    order.notes = data.notes
    order.status = data.status
    order.payment_received = data.payment_received or ZERO
    order.payment_mode = data.payment_mode
    order.is_backdated = is_backdated(data.order_date, today)


def create_order(session: Session, user: User, data: OrderIn, today: Optional[date] = None) -> Order:
    today = today or date.today()
    assert_backdate_allowed(session, user, data.order_date, today)
    customer = _resolve_customer(session, data, user)

    order = Order(created_by=user.id)
    _populate(order, data, customer, today)
    session.add(order)
    session.flush()

    total = _apply_items(session, order, data.items)
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
    customer = _resolve_customer(session, data, user)

    _populate(order, data, customer, today)
    total = _apply_items(session, order, data.items)
    order.total_amount = total
    order.balance = total - order.payment_received
    session.commit()
    session.refresh(order)
    return order
