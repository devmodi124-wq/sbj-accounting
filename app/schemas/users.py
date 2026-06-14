"""Schemas for user management."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.base import UserRole


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=4)
    role: UserRole = UserRole.employee
    full_name: str = ""


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=4)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: UserRole
    is_active: bool
