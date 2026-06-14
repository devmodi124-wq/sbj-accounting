"""System endpoints: backups and the kill switch (Danger Zone). Admin only.

Lock/Destroy require the admin to re-enter their own password plus type an exact
confirmation phrase.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import killswitch
from app.auth.deps import get_db, require_admin
from app.auth.security import verify_password
from app.models import User
from app.services import backup as backup_service

router = APIRouter(prefix="/api/system", tags=["system"])


class DangerIn(BaseModel):
    password: str
    confirm: str


def _verify(admin: User, password: str, phrase: str, expected: str) -> None:
    if not verify_password(password, admin.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bad_password")
    if phrase != expected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "confirmation_mismatch")


@router.post("/backup")
def backup_now(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> dict:
    try:
        return backup_service.backup_now(db)
    except backup_service.BackupError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/backups")
def list_backups(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> list[dict]:
    return backup_service.list_backups(db)


@router.post("/lock")
def lock(payload: DangerIn, _db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> dict:
    _verify(admin, payload.password, payload.confirm, "LOCK")
    return killswitch.lock()


@router.post("/destroy")
def destroy(payload: DangerIn, _db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> dict:
    _verify(admin, payload.password, payload.confirm, "DESTROY")
    return killswitch.destroy()
