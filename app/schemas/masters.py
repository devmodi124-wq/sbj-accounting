"""Schemas for customers, parties, and lookup types."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ===== Customers / Parties (same shape) =====

class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = None
    notes: str | None = None


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str | None
    address: str | None
    notes: str | None
    is_active: bool = True


# ===== Lookup types (component_types, purity_types) =====

class LookupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class LookupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    is_active: bool | None = None
    sort_order: int | None = None


class LookupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    sort_order: int


class ReorderIn(BaseModel):
    ordered_ids: list[int]
