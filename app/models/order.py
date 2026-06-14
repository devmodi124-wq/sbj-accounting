"""Orders and their line-item components."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    item_name: Mapped[str] = mapped_column(String(160), nullable=False)
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
