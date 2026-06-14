"""Encrypted-database backups.

A backup is a timestamped copy of the encrypted DB file plus the keyfile (both are
needed to restore). Because the DB is encrypted at rest, copies are safe to place
on a pendrive / external drive via the configured ``backup_folder_path``.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.services.settings_store import get_setting

BACKUP_PREFIX = "khata-backup-"


class BackupError(Exception):
    pass


def _resolve_folder(session) -> Path:
    configured = get_setting(session, "backup_folder_path", "") or ""
    if configured.strip():
        return Path(configured).expanduser()
    # Default: a 'backups' folder inside the data dir.
    return get_settings().data_dir / "backups"


def backup_now(session) -> dict:
    s = get_settings()
    if not s.db_path.exists():
        raise BackupError("no database to back up")
    folder = _resolve_folder(session)
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / (BACKUP_PREFIX + time.strftime("%Y%m%d-%H%M%S"))
    out.mkdir()
    shutil.copy2(s.db_path, out / s.db_path.name)
    if s.keyfile_path.exists():
        shutil.copy2(s.keyfile_path, out / s.keyfile_path.name)
    return {"path": str(out), "folder": str(folder)}


def list_backups(session) -> list[dict]:
    folder = _resolve_folder(session)
    if not folder.exists():
        return []
    items = []
    for p in sorted(folder.glob(f"{BACKUP_PREFIX}*"), reverse=True):
        if p.is_dir():
            items.append({"name": p.name, "path": str(p)})
    return items
