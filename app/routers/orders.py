"""Order endpoints (create/list/get/update)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_db
from app.models import Order, User
from app.models.base import OrderStatus
from app.schemas.orders import OrderIn, OrderOut, OrderSummary
from app.services import orders as order_service
from app.services.backdating import BackdateNotAllowed

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _summary(order: Order) -> OrderSummary:
    return OrderSummary(
        id=order.id,
        customer_id=order.customer_id,
        customer_name=order.customer.name if order.customer else "",
        order_date=order.order_date,
        item_name=order.item_name,
        status=order.status,
        total_amount=order.total_amount,
        payment_received=order.payment_received,
        balance=order.balance,
    )


@router.get("", response_model=list[OrderSummary])
def list_orders(
    status_filter: Optional[OrderStatus] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = db.query(Order)
    if status_filter is not None:
        q = q.filter(Order.status == status_filter)
    orders = q.order_by(Order.order_date.desc(), Order.id.desc()).limit(limit).all()
    return [_summary(o) for o in orders]


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        return order_service.create_order(db, user, payload)
    except order_service.CustomerNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "customer_not_found")
    except BackdateNotAllowed as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return order


@router.put("/{order_id}", response_model=OrderOut)
def update_order(
    order_id: int,
    payload: OrderIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return order_service.update_order(db, user, order_id, payload)
    except order_service.OrderNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    except order_service.CustomerNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "customer_not_found")
    except BackdateNotAllowed as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
