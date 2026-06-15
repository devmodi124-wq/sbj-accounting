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
from app.services import report_export, reports

router = APIRouter(prefix="/api/reports", tags=["reports"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _csv(name: str, rows: list[dict]) -> Response:
    body = reports.to_csv(rows, reports.CSV_COLUMNS[name])
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


def _xlsx(name: str, rows: list[dict], thumbnails: dict | None = None) -> Response:
    body = report_export.build_xlsx(name.title(), reports.CSV_COLUMNS[name], rows, thumbnails)
    return Response(
        content=body,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'},
    )


def _export(name: str, fmt: str, rows: list[dict], db: Session | None = None,
            with_thumbnails: bool = False) -> Response:
    """Render ``rows`` as CSV or XLSX. XLSX optionally embeds product thumbnails."""
    if fmt == "csv":
        return _csv(name, rows)
    thumbnails = None
    if with_thumbnails and db is not None:
        thumbnails = reports.first_images(db, [r["id"] for r in rows if r.get("id")])
    return _xlsx(name, rows, thumbnails)


def _is_file(fmt) -> bool:
    return fmt in ("csv", "xlsx")


@router.get("/sales")
def sales(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    customer_id: Optional[int] = None,
    category_id: Optional[int] = None,
    weight_type_id: Optional[int] = None,
    source_id: Optional[int] = None,
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
        db, date_from=date_from, date_to=date_to, customer_id=customer_id,
        category_id=category_id, weight_type_id=weight_type_id, source_id=source_id,
        status=status, sort=sort, direction=direction,
        limit=(100000 if _is_file(format) else limit), offset=offset,
    )
    if _is_file(format):
        return _export("sales", format, data["rows"], db, with_thumbnails=True)
    return data


@router.get("/stock")
def stock(
    status: Optional[OrderStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    category_id: Optional[int] = None,
    sort: str = "order_date",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    format: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    data = reports.order_stock_report(
        db, status=status, date_from=date_from, date_to=date_to, category_id=category_id,
        sort=sort, direction=direction,
        limit=(100000 if _is_file(format) else limit), offset=offset,
    )
    if _is_file(format):
        return _export("stock", format, data["rows"], db, with_thumbnails=True)
    return data


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
        limit=(100000 if _is_file(format) else limit), offset=offset,
    )
    return _export("debtors", format, data["rows"]) if _is_file(format) else data


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
        limit=(100000 if _is_file(format) else limit), offset=offset,
    )
    return _export("creditors", format, data["rows"]) if _is_file(format) else data


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
        sort=sort, direction=direction, limit=(100000 if _is_file(format) else limit), offset=offset,
    )
    return _export("purchases", format, data["rows"]) if _is_file(format) else data


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
        limit=(100000 if _is_file(format) else limit), offset=offset,
    )
    return _export("customers", format, data["rows"]) if _is_file(format) else data
