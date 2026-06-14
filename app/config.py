"""Runtime configuration.

The database and keyfile live OUTSIDE the repository/exe-temp so that real customer
data never enters git and is not lost when a packaged exe exits. The storage
location is resolved with this precedence (highest first):

  1. ``KHATA_DATA_DIR`` environment variable
  2. ``data_dir`` in the config file ``khata.config.json`` (next to the exe)
  3. default — a ``khata-data`` folder next to the exe (packaged) or beside the repo (dev)

The config file lets a non-technical user point storage at a pendrive/network drive
without environment variables; it can also be edited from the admin Settings screen.
"""
from __future__ import annotations

import json
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
CONFIG_FILENAME = "khata.config.json"
DEFAULT_PORT = 8731


def _base_dir() -> Path:
    """The folder the app treats as 'home': the exe's dir when packaged, else the repo.

    Must use ``sys.executable`` when frozen — a one-file exe unpacks code to a temp
    dir (``__file__``) that is deleted on exit.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return REPO_ROOT


def config_file_path() -> Path:
    """Location of the optional ``khata.config.json`` (overridable for tests)."""
    override = os.environ.get("KHATA_CONFIG_FILE")
    return Path(override).expanduser() if override else (_base_dir() / CONFIG_FILENAME)


def load_config_file() -> dict:
    path = config_file_path()
    if path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except (ValueError, OSError):
            return {}
    return {}


def write_config_file(updates: dict) -> Path:
    """Merge ``updates`` into the config file and write it (creating it if needed)."""
    path = config_file_path()
    data = load_config_file()
    data.update(updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), "utf-8")
    return path


def _default_data_dir() -> Path:
    """Default storage: ``khata-data`` next to the exe (packaged) or beside the repo (dev)."""
    if getattr(sys, "frozen", False):
        return (_base_dir() / "khata-data").resolve()
    return (REPO_ROOT.parent / "khata-data").resolve()


class Settings:
    """Resolved filesystem/runtime config. Cheap to construct; cached via ``get_settings``."""

    def __init__(self) -> None:
        config = load_config_file()
        env_dir = os.environ.get("KHATA_DATA_DIR")
        if env_dir:
            self.data_dir = Path(env_dir).expanduser().resolve()
        elif config.get("data_dir"):
            self.data_dir = Path(config["data_dir"]).expanduser().resolve()
        else:
            self.data_dir = _default_data_dir()
        self.port: int = int(os.environ.get("KHATA_PORT", config.get("port", DEFAULT_PORT)))
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
