"""Opening balances for customer/party ledgers (needed for migrated history)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import BalanceDirection, EntityType, Money, TimestampMixin


class OpeningBalance(TimestampMixin, Base):
    """A dated starting balance for a customer or party ledger.

    ``entity_id`` references customers.id or parties.id depending on ``entity_type``
    (kept as a plain int so one table can serve both; FK enforced in service logic).
    """

    __tablename__ = "opening_balances"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, native_enum=False, length=16), nullable=False
    )
    entity_id: Mapped[int] = mapped_column(nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    direction: Mapped[BalanceDirection] = mapped_column(
        Enum(BalanceDirection, native_enum=False, length=16), nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(default=None)
