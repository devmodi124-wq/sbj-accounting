"""Orders, their pieces (items), and each piece's component breakdown.

An order can contain multiple **items** (physical pieces — a ring, a chain, …).
Each item carries its own name/category/weight/supplied-from, a set of
**components** (Round/Stone/Labour…) whose prices sum to the item subtotal, and
its own pictures. The order total is the sum of all item subtotals.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.masters import Customer, ItemCategory, OrderSource, SupplySource, WeightType

from app.db import Base
from app.models.base import (
    Money,
    OrderStatus,
    PaymentMode,
    Rate,
    TimestampMixin,
    Weight,
    utcnow,
)


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    order_code: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    # Free-text reference (e.g. "friends", "family", referred-by). Not a lookup.
    reference: Mapped[str | None] = mapped_column(Text)
    # Where the order came in from (Whatsapp / Instagram / …) — configurable lookup.
    source_id: Mapped[int | None] = mapped_column(ForeignKey("order_sources.id"))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=16),
        default=OrderStatus.pending,
        nullable=False,
    )
    # Denormalized for performance; recomputed from item subtotals on every change.
    total_amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    payment_received: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    balance: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    payment_mode: Mapped[PaymentMode | None] = mapped_column(
        Enum(PaymentMode, native_enum=False, length=20)
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
    is_backdated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.sort_order",
    )
    customer: Mapped["Customer"] = relationship(lazy="joined")
    source: Mapped["OrderSource"] = relationship(lazy="joined")


class OrderItem(Base):
    """A single piece within an order (the user-facing "item")."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    # Item Name is optional free-text; Item Category (required at the API layer)
    # is the structured field. FKs are nullable so legacy rows migrate cleanly.
    item_name: Mapped[str | None] = mapped_column(String(160))
    item_category_id: Mapped[int | None] = mapped_column(ForeignKey("item_categories.id"))
    weight_type_id: Mapped[int | None] = mapped_column(ForeignKey("weight_types.id"))
    supply_source_id: Mapped[int | None] = mapped_column(ForeignKey("supply_sources.id"))
    # Sum of this piece's component prices (denormalized).
    subtotal: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    components: Mapped[list["OrderComponent"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="OrderComponent.sort_order",
    )
    images: Mapped[list["OrderImage"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="OrderImage.sort_order",
    )
    item_category: Mapped["ItemCategory"] = relationship(lazy="joined")
    weight_type: Mapped["WeightType"] = relationship(lazy="joined")
    supply_source: Mapped["SupplySource"] = relationship(lazy="joined")


class OrderComponent(Base):
    """A component line (Round/Stone/Labour…) inside a piece; price sums into the subtotal."""

    __tablename__ = "order_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False
    )
    component_type_id: Mapped[int] = mapped_column(
        ForeignKey("component_types.id"), nullable=False
    )
    pcs: Mapped[int | None] = mapped_column(Integer)
    weight: Mapped[Decimal | None] = mapped_column(Weight)
    purity_type_id: Mapped[int | None] = mapped_column(ForeignKey("purity_types.id"))
    rate: Mapped[Decimal | None] = mapped_column(Rate)
    # Always present — this is what sums into the item subtotal.
    price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    item: Mapped["OrderItem"] = relationship(back_populates="components")


class OrderImage(Base):
    """A picture of a piece, stored inside the encrypted DB (multiple per item)."""

    __tablename__ = "order_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    mime: Mapped[str] = mapped_column(String(80), default="image/jpeg", nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    item: Mapped["OrderItem"] = relationship(back_populates="images")
