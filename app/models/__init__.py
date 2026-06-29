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
from app.models.auth import UserSession
from app.models.cash import CashEntry
from app.models.ledger import OpeningBalance
from app.models.masters import (
    ComponentType,
    Customer,
    DiamondType,
    ItemCategory,
    OrderSource,
    Party,
    PurityType,
    SupplySource,
    WeightType,
)
from app.models.order import (
    Order,
    OrderImage,
    OrderItem,
    OrderItemDiamond,
    OrderPayment,
)
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
    "UserSession",
    "CashEntry",
    "OpeningBalance",
    "ComponentType",
    "Customer",
    "DiamondType",
    "ItemCategory",
    "OrderSource",
    "Party",
    "PurityType",
    "SupplySource",
    "WeightType",
    "Order",
    "OrderImage",
    "OrderItem",
    "OrderItemDiamond",
    "OrderPayment",
    "Purchase",
    "AuditLog",
    "Setting",
    "User",
]
