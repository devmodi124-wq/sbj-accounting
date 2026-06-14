"""Cash-book endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_db
from app.models import CashEntry, User
from app.models.base import CashEntryType
from app.schemas.cash import CashEntryIn, CashEntryOut
from app.services import cash as cash_service
from app.services.backdating import BackdateNotAllowed

router = APIRouter(prefix="/api/cash", tags=["cash"])


@router.get("", response_model=list[CashEntryOut])
def list_cash(
    entry_type: Optional[CashEntryType] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = db.query(CashEntry)
    if entry_type is not None:
        q = q.filter(CashEntry.entry_type == entry_type)
    return q.order_by(CashEntry.entry_date.desc(), CashEntry.id.desc()).limit(limit).all()


@router.post("", response_model=CashEntryOut, status_code=status.HTTP_201_CREATED)
def create_cash(
    payload: CashEntryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        return cash_service.create_cash_entry(db, user, payload)
    except BackdateNotAllowed as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.put("/{entry_id}", response_model=CashEntryOut)
def update_cash(
    entry_id: int,
    payload: CashEntryIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return cash_service.update_cash_entry(db, user, entry_id, payload)
    except cash_service.CashEntryNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    except BackdateNotAllowed as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
