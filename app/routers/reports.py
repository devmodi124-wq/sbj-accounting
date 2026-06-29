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
from app.services.dateranges import resolve_range

router = APIRouter(prefix="/api/reports", tags=["reports"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _range_dates(range_: Optional[str], date_from: Optional[date], date_to: Optional[date]):
    """Resolve a preset into (date_from, date_to). 'all_time'/'custom'/None keep
    the explicit dates as given; named presets override them."""
    if not range_ or range_ in ("all_time", "custom"):
        return date_from, date_to
    return resolve_range(range_)


def _export(name: str, fmt: str, data: dict, db: Session | None = None,
            with_thumbnails: bool = False) -> Response:
    """Render a report ``data`` as CSV or XLSX, with a trailing TOTAL row (and the
    sales category/source breakdown). XLSX optionally embeds product thumbnails."""
    rows = data["rows"]
    columns = reports.CSV_COLUMNS[name]
    total_row = reports.totals_row(name, rows)
    sections = reports.breakdown_sections(data) if name == "sales" else None

    if fmt == "csv":
        body = reports.to_csv(rows, columns, total_row=total_row, sections=sections)
        media_type, ext = "text/csv", "csv"
    else:
        thumbnails = None
        if with_thumbnails and db is not None:
            thumbnails = reports.first_images(db, [r["id"] for r in rows if r.get("id")])
        body = report_export.build_xlsx(
            name.title(), columns, rows, thumbnails, total_row=total_row, sections=sections)
        media_type, ext = XLSX_MIME, "xlsx"
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{name}.{ext}"'},
    )


def _is_file(fmt) -> bool:
    return fmt in ("csv", "xlsx")


@router.get("/sales")
def sales(
    range: Optional[str] = None,
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
    date_from, date_to = _range_dates(range, date_from, date_to)
    data = reports.sales_report(
        db, date_from=date_from, date_to=date_to, customer_id=customer_id,
        category_id=category_id, weight_type_id=weight_type_id, source_id=source_id,
        status=status, sort=sort, direction=direction,
        limit=(100000 if _is_file(format) else limit), offset=offset,
    )
    if _is_file(format):
        return _export("sales", format, data, db, with_thumbnails=True)
    return data


@router.get("/stock")
def stock(
    status: Optional[OrderStatus] = None,
    range: Optional[str] = None,
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
    date_from, date_to = _range_dates(range, date_from, date_to)
    data = reports.order_stock_report(
        db, status=status, date_from=date_from, date_to=date_to, category_id=category_id,
        sort=sort, direction=direction,
        limit=(100000 if _is_file(format) else limit), offset=offset,
    )
    if _is_file(format):
        return _export("stock", format, data, db, with_thumbnails=True)
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
    return _export("debtors", format, data) if _is_file(format) else data


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
    return _export("creditors", format, data) if _is_file(format) else data


@router.get("/purchases")
def purchases(
    range: Optional[str] = None,
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
    date_from, date_to = _range_dates(range, date_from, date_to)
    data = reports.purchase_report(
        db, date_from=date_from, date_to=date_to, party_id=party_id, status=status,
        sort=sort, direction=direction, limit=(100000 if _is_file(format) else limit), offset=offset,
    )
    return _export("purchases", format, data) if _is_file(format) else data


@router.get("/customers")
def customers(
    search: str = "",
    range: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    sort: str = "lifetime",
    direction: str = "desc",
    limit: int = 50,
    offset: int = 0,
    format: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    date_from, date_to = _range_dates(range, date_from, date_to)
    data = reports.customer_report(
        db, search=search, date_from=date_from, date_to=date_to, sort=sort, direction=direction,
        limit=(100000 if _is_file(format) else limit), offset=offset,
    )
    return _export("customers", format, data) if _is_file(format) else data
