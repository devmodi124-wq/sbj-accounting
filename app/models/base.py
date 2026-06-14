"""Shared model building blocks: enums, column types, mixins."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column

# Column type aliases (decimal-backed to avoid float rounding on money/weights).
Money = Numeric(14, 2)
Rate = Numeric(14, 2)
Weight = Numeric(12, 3)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


# ===== Enumerations (stored as VARCHAR + CHECK via native_enum=False) =====


class UserRole(str, enum.Enum):
    admin = "admin"
    employee = "employee"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    delivered = "delivered"


class PaymentMode(str, enum.Enum):
    cash = "cash"
    upi = "upi"
    bank_transfer = "bank_transfer"
    old_gold_exchange = "old_gold_exchange"
    other = "other"


class CashEntryType(str, enum.Enum):
    received = "received"
    paid = "paid"


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"


class EntityType(str, enum.Enum):
    customer = "customer"
    party = "party"


class BalanceDirection(str, enum.Enum):
    debit = "debit"
    credit = "credit"
