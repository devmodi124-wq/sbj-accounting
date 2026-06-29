"""Master records: customers, suppliers (parties), and lookup types."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Party(TimestampMixin, Base):
    """Supplier / creditor."""

    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class ComponentType(Base):
    """Jewellery component category (Round, Stone, Labour, …). Admin-managed."""

    __tablename__ = "component_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PurityType(Base):
    """Metal purity (14 KT, 22 KT, 916, Silver, …). Admin-managed."""

    __tablename__ = "purity_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class _Lookup:
    """Common shape for simple admin-managed dropdown lookups."""

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ItemCategory(_Lookup, Base):
    """Order item category (Ring, Necklace, Tops, Bracelet, …). Admin-managed."""

    __tablename__ = "item_categories"


class WeightType(_Lookup, Base):
    """Weight class (Lightweight, Normal, Heavyweight). Admin-managed."""

    __tablename__ = "weight_types"


class SupplySource(_Lookup, Base):
    """Where an order is supplied from (On Order, Stock). Admin-managed."""

    __tablename__ = "supply_sources"


class OrderSource(_Lookup, Base):
    """Where an order came in from (Whatsapp, Instagram, Facebook, …). Admin-managed."""

    __tablename__ = "order_sources"


class DiamondType(_Lookup, Base):
    """Diamond cut/kind (Chowki, Princess, Marquise, fancy, lab-grown). Admin-managed."""

    __tablename__ = "diamond_types"
