"""Report endpoints (JSON + CSV export)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_db
from app.models import User
from app.models.base import OrderStatus
from app.services import reports

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _csv(name: str, rows: list[dict]) -> Response:
    body = reports.to_csv(rows, reports.CSV_COLUMNS[name])
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


@router.get("/sales")
def sales(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    customer_id: Optional[int] = None,
    status: Optional[OrderStatus] = None,
    sort: str = "order_date",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    format: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = reports.sales_report(
        db, date_from=date_from, date_to=date_to, customer_id=customer_id, status=status,
        sort=sort, direction=direction, limit=(100000 if format == "csv" else limit), offset=offset,
    )
    return _csv("sales", data["rows"]) if format == "csv" else data


@router.get("/stock")
def stock(
    status: Optional[OrderStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    sort: str = "order_date",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    format: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = reports.order_stock_report(
        db, status=status, date_from=date_from, date_to=date_to, sort=sort, direction=direction,
        limit=(100000 if format == "csv" else limit), offset=offset,
    )
    return _csv("stock", data["rows"]) if format == "csv" else data


@router.get("/debtors")
def debtors(
    search: str = "",
    ageing: Optional[str] = None,
    sort: str = "balance",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    format: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = reports.debtors_report(
        db, search=search, ageing=ageing, sort=sort, direction=direction,
        limit=(100000 if format == "csv" else limit), offset=offset,
    )
    return _csv("debtors", data["rows"]) if format == "csv" else data


@router.get("/creditors")
def creditors(
    search: str = "",
    ageing: Optional[str] = None,
    sort: str = "balance",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    format: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = reports.creditors_report(
        db, search=search, ageing=ageing, sort=sort, direction=direction,
        limit=(100000 if format == "csv" else limit), offset=offset,
    )
    return _csv("creditors", data["rows"]) if format == "csv" else data


@router.get("/purchases")
def purchases(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    party_id: Optional[int] = None,
    status: Optional[str] = None,
    sort: str = "purchase_date",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    format: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = reports.purchase_report(
        db, date_from=date_from, date_to=date_to, party_id=party_id, status=status,
        sort=sort, direction=direction, limit=(100000 if format == "csv" else limit), offset=offset,
    )
    return _csv("purchases", data["rows"]) if format == "csv" else data


@router.get("/customers")
def customers(
    search: str = "",
    sort: str = "lifetime",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    format: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = reports.customer_report(
        db, search=search, sort=sort, direction=direction,
        limit=(100000 if format == "csv" else limit), offset=offset,
    )
    return _csv("customers", data["rows"]) if format == "csv" else data
