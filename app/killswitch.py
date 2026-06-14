"""Kill switch — Lock and Destroy.

Kept as a self-contained module with a small, clean interface so v2 features
(remote trigger, USB-key presence, duress codes) can extend it without touching
the rest of the app.

- **Lock**: rekeys the SQLCipher database to a brand-new random master key, writes
  that key to a separate *sealed* file (the admin must move/secure it elsewhere),
  and clears all keyfile entries so no current password can open the DB. Recovery
  is possible only via the sealed key.

- **Destroy**: securely overwrites and deletes the local database, keyfile, sealed
  key, and any backups located *inside the local data dir*. It deliberately does
  NOT touch a backup folder configured to an external path (e.g. a pendrive) — the
  Settings UI documents this so the admin understands the implication.

Note: secure overwrite is best-effort. On SSDs/flash with wear-levelling, physical
erasure is not guaranteed; treat external backups as the real exposure surface.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from sqlalchemy import text

from app.config import get_settings
from app.crypto import keyfile
from app.db import MASTER_KEY_BYTES, engine_state
from app.services.backup import BACKUP_PREFIX


class KillSwitchError(Exception):
    pass


def lock() -> dict:
    """Rekey the DB to a new master key, seal that key, and lock everyone out."""
    s = get_settings()
    if not engine_state.is_unlocked or engine_state.engine is None:
        raise KillSwitchError("database is locked")

    new_key = secrets.token_bytes(MASTER_KEY_BYTES)
    with engine_state.engine.begin() as conn:
        conn.execute(text(f"PRAGMA rekey = \"x'{new_key.hex()}'\""))

    s.sealed_key_path.write_text(new_key.hex(), encoding="utf-8")
    keyfile.lock_keyfile(s.keyfile_path)
    engine_state.dispose()
    return {"sealed_key_path": str(s.sealed_key_path)}


def _secure_delete(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        for child in path.iterdir():
            _secure_delete(child)
        path.rmdir()
        return
    try:
        size = path.stat().st_size
        with open(path, "r+b", buffering=0) as fh:
            fh.write(secrets.token_bytes(size))
            fh.flush()
            os.fsync(fh.fileno())
    except OSError:
        pass
    path.unlink(missing_ok=True)


def destroy() -> dict:
    """Securely delete local DB, keyfile, sealed key, and in-data-dir backups."""
    s = get_settings()
    engine_state.dispose()

    targets = [s.db_path, s.keyfile_path, s.sealed_key_path]
    # Local backups that live inside the data dir (external backup folders are spared).
    local_backups = s.data_dir / "backups"
    if local_backups.exists():
        targets.append(local_backups)
    targets += list(s.data_dir.glob(f"{BACKUP_PREFIX}*"))

    deleted = []
    for target in targets:
        if target.exists():
            _secure_delete(target)
            deleted.append(str(target))
    return {"deleted": deleted}
