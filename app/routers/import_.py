"""Historical-data import endpoints (admin only): template, validate, commit."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.deps import get_db, require_admin
from app.models import User
from app.services import import_data
from app.services.import_template import build_template

router = APIRouter(prefix="/api/import", tags=["import"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/template")
def download_template(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> Response:
    return Response(
        content=build_template(db),
        media_type=_XLSX,
        headers={"Content-Disposition": 'attachment; filename="khata-import-template.xlsx"'},
    )


async def _read_sheets(file: UploadFile) -> dict:
    try:
        return import_data.parse_workbook(await file.read())
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "could_not_read_workbook")


@router.post("/validate")
async def validate_upload(
    file: UploadFile, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> dict:
    sheets = await _read_sheets(file)
    return import_data.validate(db, sheets)


@router.post("/commit")
async def commit_upload(
    file: UploadFile, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> dict:
    sheets = await _read_sheets(file)
    report = import_data.validate(db, sheets)
    if not report["ok"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_failed")
    return import_data.commit(db, admin, sheets)
