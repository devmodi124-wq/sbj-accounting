"""Orders and their line-item components."""
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
    from app.models.masters import Customer, ItemCategory, SupplySource, WeightType

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
    # Item Name is now optional free-text; Item Category (required at the API layer)
    # is the structured field. The FKs are nullable in the DB so older rows migrate
    # cleanly; the API/UI enforce category as mandatory for new/edited orders.
    item_name: Mapped[str | None] = mapped_column(String(160))
    item_category_id: Mapped[int | None] = mapped_column(ForeignKey("item_categories.id"))
    weight_type_id: Mapped[int | None] = mapped_column(ForeignKey("weight_types.id"))
    supply_source_id: Mapped[int | None] = mapped_column(ForeignKey("supply_sources.id"))
    order_code: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=16),
        default=OrderStatus.pending,
        nullable=False,
    )
    # Denormalized for performance; recomputed from items on every change.
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
    images: Mapped[list["OrderImage"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderImage.sort_order",
    )
    customer: Mapped["Customer"] = relationship(lazy="joined")
    item_category: Mapped["ItemCategory"] = relationship(lazy="joined")
    weight_type: Mapped["WeightType"] = relationship(lazy="joined")
    supply_source: Mapped["SupplySource"] = relationship(lazy="joined")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    component_type_id: Mapped[int] = mapped_column(
        ForeignKey("component_types.id"), nullable=False
    )
    pcs: Mapped[int | None] = mapped_column(Integer)
    weight: Mapped[Decimal | None] = mapped_column(Weight)
    purity_type_id: Mapped[int | None] = mapped_column(ForeignKey("purity_types.id"))
    rate: Mapped[Decimal | None] = mapped_column(Rate)
    # Always present — this is what sums into the order total.
    price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")


class OrderImage(Base):
    """A picture of the piece, stored inside the encrypted DB (multiple per order)."""

    __tablename__ = "order_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    mime: Mapped[str] = mapped_column(String(80), default="image/jpeg", nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="images")
