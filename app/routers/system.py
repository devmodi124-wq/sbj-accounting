"""System endpoints: backups and the kill switch (Danger Zone). Admin only.

Lock/Destroy require the admin to re-enter their own password plus type an exact
confirmation phrase.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pathlib import Path

from app import killswitch
from app.auth.deps import get_db, require_admin
from app.auth.security import verify_password
from app.config import config_file_path, get_settings, load_config_file, write_config_file
from app.models import User
from app.services import backup as backup_service

router = APIRouter(prefix="/api/system", tags=["system"])


class DangerIn(BaseModel):
    password: str
    confirm: str


class StorageIn(BaseModel):
    data_dir: str


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


@router.get("/storage")
def get_storage(_admin: User = Depends(require_admin)) -> dict:
    """Current data location, the value written in the config file, and its path."""
    return {
        "current": str(get_settings().data_dir),
        "configured": load_config_file().get("data_dir"),
        "config_file": str(config_file_path()),
    }


@router.put("/storage")
def set_storage(payload: StorageIn, _admin: User = Depends(require_admin)) -> dict:
    """Write the desired data folder to the config file. Applies on next restart.

    Existing data is NOT moved automatically — the admin copies the khata-data
    folder to the new location (documented in the UI).
    """
    target = payload.data_dir.strip()
    if not target:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty_path")
    resolved = Path(target).expanduser()
    try:
        resolved.mkdir(parents=True, exist_ok=True)  # validate it's creatable/writable
    except OSError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "path_not_writable")
    write_config_file({"data_dir": str(resolved)})
    return {"configured": str(resolved), "applies": "on_restart"}


@router.post("/lock")
def lock(payload: DangerIn, _db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> dict:
    _verify(admin, payload.password, payload.confirm, "LOCK")
    return killswitch.lock()


@router.post("/destroy")
def destroy(payload: DangerIn, _db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> dict:
    _verify(admin, payload.password, payload.confirm, "DESTROY")
    return killswitch.destroy()
