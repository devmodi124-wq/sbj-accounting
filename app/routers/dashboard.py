"""Dashboard endpoint."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_db
from app.models import User
from app.services.dashboard import build_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(
    range: str = "this_month",
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    return build_dashboard(db, range, date_from, date_to)
