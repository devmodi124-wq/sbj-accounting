"""Purchases from suppliers (parties)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import Money, TimestampMixin

if TYPE_CHECKING:
    from app.models.masters import Party


class Purchase(TimestampMixin, Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    entry_notes: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    # Denormalized; status (paid/pending) is derived from balance.
    balance: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    is_backdated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    party: Mapped["Party"] = relationship(lazy="joined")

    @property
    def status(self) -> str:
        return "paid" if self.balance == 0 else "pending"
