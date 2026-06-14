"""Application settings (admin only).

Only a safe allow-list of keys is readable/writable here; internal keys such as
``schema_version``, ``master_pin_hash`` and session data are never exposed.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_db, require_admin
from app.models import User
from app.services.settings_store import get_setting, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])

EDITABLE_KEYS = {
    "employee_backdate_limit_days",
    "currency_symbol",
    "date_format",
    "backup_folder_path",
    "opening_cash_balance",
}


@router.get("")
def read_settings(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> dict:
    return {key: get_setting(db, key, "") for key in sorted(EDITABLE_KEYS)}


@router.put("")
def update_settings(
    payload: dict, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> dict:
    for key, value in payload.items():
        if key in EDITABLE_KEYS:
            set_setting(db, key, str(value))
    db.commit()
    return {key: get_setting(db, key, "") for key in sorted(EDITABLE_KEYS)}
