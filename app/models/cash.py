"""Cash book entries (money in/out)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import CashEntryType, Money, TimestampMixin


class CashEntry(TimestampMixin, Base):
    __tablename__ = "cash_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Free-text name; optionally linked to a master record for ledger rollups.
    person_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"))
    details: Mapped[str | None] = mapped_column(Text)
    entry_type: Mapped[CashEntryType] = mapped_column(
        Enum(CashEntryType, native_enum=False, length=16), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    is_backdated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
