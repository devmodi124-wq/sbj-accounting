"""ORM models. Importing this package registers every table on ``Base.metadata``."""
from __future__ import annotations

from app.db import Base
from app.models.base import (
    AuditAction,
    BalanceDirection,
    CashEntryType,
    EntityType,
    OrderStatus,
    PaymentMode,
    UserRole,
)
from app.models.cash import CashEntry
from app.models.ledger import OpeningBalance
from app.models.masters import ComponentType, Customer, Party, PurityType
from app.models.order import Order, OrderItem
from app.models.purchase import Purchase
from app.models.system import AuditLog, Setting
from app.models.user import User

__all__ = [
    "Base",
    "AuditAction",
    "BalanceDirection",
    "CashEntryType",
    "EntityType",
    "OrderStatus",
    "PaymentMode",
    "UserRole",
    "CashEntry",
    "OpeningBalance",
    "ComponentType",
    "Customer",
    "Party",
    "PurityType",
    "Order",
    "OrderItem",
    "Purchase",
    "AuditLog",
    "Setting",
    "User",
]
