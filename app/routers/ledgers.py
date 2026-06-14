"""Ledger endpoints + opening-balance management."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_db, require_admin
from app.models import User
from app.models.base import BalanceDirection, EntityType
from app.services import ledger as ledger_service
from app.services.reports import to_csv

router = APIRouter(prefix="/api/ledgers", tags=["ledgers"])

_LEDGER_CSV = [("date", "Date"), ("particulars", "Particulars"),
               ("debit", "Debit"), ("credit", "Credit"), ("balance", "Balance")]


class OpeningBalanceIn(BaseModel):
    entity_type: EntityType
    entity_id: int
    as_of_date: date
    amount: Decimal
    direction: BalanceDirection


def _maybe_csv(name: str, data: dict, fmt: str | None):
    if fmt == "csv":
        return Response(
            content=to_csv(data["entries"], _LEDGER_CSV),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="ledger-{name}.csv"'},
        )
    return data


@router.get("/customer/{customer_id}")
def customer_ledger(
    customer_id: int,
    format: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    try:
        data = ledger_service.customer_ledger(db, customer_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return _maybe_csv(f"customer-{customer_id}", data, format)


@router.get("/party/{party_id}")
def party_ledger(
    party_id: int,
    format: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    try:
        data = ledger_service.party_ledger(db, party_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return _maybe_csv(f"party-{party_id}", data, format)


@router.post("/opening-balance")
def set_opening_balance(
    payload: OpeningBalanceIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ledger_service.set_opening_balance(
        db, payload.entity_type, payload.entity_id, payload.as_of_date,
        payload.amount, payload.direction, created_by=admin.id,
    )
    db.commit()
    return {"ok": True}
