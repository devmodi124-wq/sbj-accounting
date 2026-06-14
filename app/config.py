"""Runtime configuration.

The database and keyfile live OUTSIDE the repository so that real customer data
never enters git. By default they sit in a sibling ``khata-data/`` folder; override
with the ``KHATA_DATA_DIR`` environment variable (e.g. point it at a pendrive).
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

# Repo root = parent of the ``app`` package directory.
REPO_ROOT = Path(__file__).resolve().parent.parent

# App-level defaults (these are NOT secrets; per-shop settings live in the DB).
DB_FILENAME = "khata.db"
KEYFILE_FILENAME = "khata.keys"
SEALED_KEY_FILENAME = "khata.sealed"  # written by the kill-switch "Lock" action
DEFAULT_PORT = 8731


def _default_data_dir() -> Path:
    """Where the database + keyfile live by default.

    - Packaged exe (PyInstaller): a ``khata-data`` folder *next to the executable*,
      so the install is portable (copy the exe + its khata-data folder together).
      We must use ``sys.executable`` here, not ``__file__`` — a one-file exe unpacks
      its code to a temporary directory that is deleted on exit.
    - Development: a ``khata-data`` sibling of the repo (gitignored).
    """
    if getattr(sys, "frozen", False):
        return (Path(sys.executable).resolve().parent / "khata-data").resolve()
    return (REPO_ROOT.parent / "khata-data").resolve()


class Settings:
    """Resolved filesystem/runtime config. Cheap to construct; cached via ``get_settings``."""

    def __init__(self) -> None:
        env_dir = os.environ.get("KHATA_DATA_DIR")
        # KHATA_DATA_DIR overrides everything (e.g. point it at a pendrive).
        self.data_dir: Path = (
            Path(env_dir).expanduser().resolve() if env_dir else _default_data_dir()
        )
        self.port: int = int(os.environ.get("KHATA_PORT", DEFAULT_PORT))
        # Session-cookie signing key. Generated/persisted per install in Phase 2;
        # an env override is supported mainly for tests.
        self.secret_key: str = os.environ.get("KHATA_SECRET_KEY", "")

    @property
    def db_path(self) -> Path:
        return self.data_dir / DB_FILENAME

    @property
    def keyfile_path(self) -> Path:
        return self.data_dir / KEYFILE_FILENAME

    @property
    def sealed_key_path(self) -> Path:
        return self.data_dir / SEALED_KEY_FILENAME

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
