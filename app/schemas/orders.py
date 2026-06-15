"""Schemas for orders, their pieces (items), and component line items.

An order has one or more **items** (pieces); each item has its own
category/weight/supplied-from and a list of **components** whose prices sum to
the item subtotal. The order total is the sum of all item subtotals.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.base import OrderStatus, PaymentMode


class OrderComponentIn(BaseModel):
    component_type_id: int
    pcs: int | None = None
    weight: Decimal | None = None
    purity_type_id: int | None = None
    rate: Decimal | None = None
    price: Decimal = Decimal("0")


class OrderComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    component_type_id: int
    pcs: int | None
    weight: Decimal | None
    purity_type_id: int | None
    rate: Decimal | None
    price: Decimal
    sort_order: int


class OrderImageMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    mime: str
    sort_order: int


class OrderItemIn(BaseModel):
    # Present when editing an existing piece — lets the service preserve its
    # pictures across an update instead of recreating (and wiping) it.
    id: int | None = None
    item_category_id: int  # mandatory (configurable category: Ring/Necklace/…)
    item_name: str | None = Field(default=None, max_length=160)  # optional free-text
    weight_type_id: int | None = None
    supply_source_id: int | None = None
    components: list[OrderComponentIn] = []


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_category_id: int | None
    item_name: str | None
    weight_type_id: int | None
    supply_source_id: int | None
    subtotal: Decimal
    sort_order: int
    components: list[OrderComponentOut]
    images: list[OrderImageMeta] = []


class OrderIn(BaseModel):
    # Either an existing customer id, or a name to find-or-create.
    customer_id: int | None = None
    customer_name: str | None = None
    order_date: date
    order_code: str | None = None
    notes: str | None = None
    reference: str | None = None       # free text (friends / family / referral)
    source_id: int | None = None       # configurable order source (Whatsapp/…)
    status: OrderStatus = OrderStatus.pending
    payment_received: Decimal = Decimal("0")
    payment_mode: PaymentMode | None = None
    items: list[OrderItemIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self):
        if self.customer_id is None and not (self.customer_name and self.customer_name.strip()):
            raise ValueError("customer_id or customer_name is required")
        if not self.items:
            raise ValueError("at least one item is required")
        return self


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    order_date: date
    order_code: str | None
    notes: str | None
    reference: str | None
    source_id: int | None
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
    item_summary: str          # categories across the order, e.g. "Ring, Necklace"
    item_name: str             # item names joined (may be empty)
    item_count: int
    status: OrderStatus
    total_amount: Decimal
    payment_received: Decimal
    balance: Decimal
    image_count: int = 0
    source: str | None = None
