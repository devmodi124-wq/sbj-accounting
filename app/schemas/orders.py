"""Schemas for orders and their component line items."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.base import OrderStatus, PaymentMode


class OrderItemIn(BaseModel):
    component_type_id: int
    pcs: int | None = None
    weight: Decimal | None = None
    purity_type_id: int | None = None
    rate: Decimal | None = None
    price: Decimal = Decimal("0")


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    component_type_id: int
    pcs: int | None
    weight: Decimal | None
    purity_type_id: int | None
    rate: Decimal | None
    price: Decimal
    sort_order: int


class OrderIn(BaseModel):
    # Either an existing customer id, or a name to find-or-create.
    customer_id: int | None = None
    customer_name: str | None = None
    order_date: date
    item_name: str = Field(min_length=1, max_length=160)
    order_code: str | None = None
    notes: str | None = None
    status: OrderStatus = OrderStatus.pending
    payment_received: Decimal = Decimal("0")
    payment_mode: PaymentMode | None = None
    items: list[OrderItemIn] = []

    @model_validator(mode="after")
    def _need_customer(self):
        if self.customer_id is None and not (self.customer_name and self.customer_name.strip()):
            raise ValueError("customer_id or customer_name is required")
        return self


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    order_date: date
    item_name: str
    order_code: str | None
    notes: str | None
    status: OrderStatus
    total_amount: Decimal
    payment_received: Decimal
    balance: Decimal
    payment_mode: PaymentMode | None
    is_backdated: bool
    items: list[OrderItemOut]


class OrderSummary(BaseModel):
    """Lightweight row for lists (with the customer name resolved)."""

    id: int
    customer_id: int
    customer_name: str
    order_date: date
    item_name: str
    status: OrderStatus
    total_amount: Decimal
    payment_received: Decimal
    balance: Decimal
