"""Purchase endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_db
from app.models import Purchase, User
from app.schemas.purchases import PurchaseIn, PurchaseOut, PurchaseSummary
from app.services import purchases as purchase_service
from app.services.backdating import BackdateNotAllowed

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


def _summary(p: Purchase) -> PurchaseSummary:
    return PurchaseSummary(
        id=p.id,
        purchase_date=p.purchase_date,
        party_id=p.party_id,
        party_name=p.party.name if p.party else "",
        details=p.details,
        amount=p.amount,
        amount_paid=p.amount_paid,
        balance=p.balance,
        status=p.status,
    )


@router.get("", response_model=list[PurchaseSummary])
def list_purchases(
    limit: int = 200, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    rows = (
        db.query(Purchase)
        .order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
        .limit(limit)
        .all()
    )
    return [_summary(p) for p in rows]


@router.post("", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def create_purchase(
    payload: PurchaseIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        return purchase_service.create_purchase(db, user, payload)
    except purchase_service.PartyNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "party_not_found")
    except BackdateNotAllowed as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.put("/{purchase_id}", response_model=PurchaseOut)
def update_purchase(
    purchase_id: int,
    payload: PurchaseIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return purchase_service.update_purchase(db, user, purchase_id, payload)
    except purchase_service.PurchaseNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    except purchase_service.PartyNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "party_not_found")
    except BackdateNotAllowed as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.delete("/{purchase_id}")
def delete_purchase(
    purchase_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> dict:
    try:
        purchase_service.delete_purchase(db, purchase_id)
    except purchase_service.PurchaseNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return {"ok": True}
