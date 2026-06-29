"""Schemas for orders, their pieces (items) and split payments.

Each item is priced from a weights×rates breakdown (net/metal weight is derived;
the item subtotal sums metal/diamond/stone/others/labour values). The order total
is the sum of item subtotals. Payment can be split across modes; the cash portion
is mirrored to the cash book by the service layer.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.base import OrderStatus, PaymentMode


class OrderImageMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    mime: str
    sort_order: int


class DiamondLineIn(BaseModel):
    # id present when editing; the service rebuilds diamond rows on every save.
    id: int | None = None
    diamond_type_id: int | None = None   # configurable diamond type (Chowki/Princess/…)
    carats: Decimal | None = None        # carats (5 ct = 1 g)
    rate: Decimal | None = None          # ₹ per carat


class DiamondLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    diamond_type_id: int | None
    carats: Decimal | None
    rate: Decimal | None
    sort_order: int


class OrderItemIn(BaseModel):
    # Present when editing an existing piece — lets the service preserve its
    # pictures across an update instead of recreating (and wiping) it.
    id: int | None = None
    item_category_id: int  # mandatory (configurable category: Ring/Necklace/…)
    item_name: str | None = Field(default=None, max_length=160)  # optional free-text
    weight_type_id: int | None = None
    supply_source_id: int | None = None
    purity_type_id: int | None = None
    # Weights — gross in grams; stone/others in carats.
    gross_weight: Decimal | None = None
    stone_weight: Decimal | None = None
    others_weight: Decimal | None = None
    # Repeatable diamond lines (preferred). For backward-compat / import, a single
    # untyped diamond can also be given via diamond_weight + diamond_rate below.
    diamonds: list[DiamondLineIn] = Field(default_factory=list)
    diamond_weight: Decimal | None = None   # legacy single-diamond shorthand
    diamond_rate: Decimal | None = None     # legacy single-diamond shorthand
    # Rates — metal/labour per gram of net weight; stone/others per carat.
    metal_rate: Decimal | None = None
    stone_rate: Decimal | None = None
    others_rate: Decimal | None = None
    labour_rate: Decimal | None = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_category_id: int | None
    item_name: str | None
    weight_type_id: int | None
    supply_source_id: int | None
    purity_type_id: int | None
    gross_weight: Decimal | None
    stone_weight: Decimal | None
    others_weight: Decimal | None
    net_weight: Decimal | None
    metal_rate: Decimal | None
    stone_rate: Decimal | None
    others_rate: Decimal | None
    labour_rate: Decimal | None
    diamonds: list[DiamondLineOut] = []
    subtotal: Decimal
    sort_order: int
    images: list[OrderImageMeta] = []


class OrderPaymentIn(BaseModel):
    mode: PaymentMode
    amount: Decimal = Decimal("0")


class OrderPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mode: PaymentMode
    amount: Decimal
    sort_order: int


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
    payments: list[OrderPaymentIn] = Field(default_factory=list)
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
    is_backdated: bool
    is_cancelled: bool
    items: list[OrderItemOut]
    payments: list[OrderPaymentOut]


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
    is_cancelled: bool = False
