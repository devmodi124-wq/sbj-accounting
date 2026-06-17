"""Schemas for cash-book entries."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.base import CashEntryType


class CashEntryIn(BaseModel):
    entry_date: date
    person_name: str = Field(default="", max_length=160)
    customer_id: int | None = None
    party_id: int | None = None
    details: str | None = None
    entry_type: CashEntryType
    amount: Decimal


class CashEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: date
    person_name: str
    customer_id: int | None
    party_id: int | None
    details: str | None
    entry_type: CashEntryType
    amount: Decimal
    is_backdated: bool
    auto_generated: bool = False
    order_id: int | None = None
