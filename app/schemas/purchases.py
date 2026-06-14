"""Schemas for purchases (from suppliers/parties)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PurchaseIn(BaseModel):
    purchase_date: date
    party_id: int | None = None
    party_name: str | None = None
    details: str | None = None
    entry_notes: str | None = None
    amount: Decimal = Decimal("0")
    amount_paid: Decimal = Decimal("0")

    @model_validator(mode="after")
    def _need_party(self):
        if self.party_id is None and not (self.party_name and self.party_name.strip()):
            raise ValueError("party_id or party_name is required")
        return self


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purchase_date: date
    party_id: int
    details: str | None
    entry_notes: str | None
    amount: Decimal
    amount_paid: Decimal
    balance: Decimal
    status: str
    is_backdated: bool


class PurchaseSummary(BaseModel):
    id: int
    purchase_date: date
    party_id: int
    party_name: str
    details: str | None
    amount: Decimal
    amount_paid: Decimal
    balance: Decimal
    status: str
