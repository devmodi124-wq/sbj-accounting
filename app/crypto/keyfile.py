"""Keyfile envelope — how the encrypted database gets unlocked.

A single random 32-byte *master key* encrypts the SQLCipher database. That master
key is never stored directly. Instead, a small JSON *keyfile* (next to the DB,
gitignored) stores — per user — the master key encrypted ("wrapped") under a key
derived from that user's password:

    derive KEK = scrypt(password, per-user salt)
    wrapped    = AES-GCM(KEK).encrypt(master_key)

So:
- Any valid user can unlock the DB (each has their own wrapped copy).
- Resetting/adding a user only re-wraps the master key — the DB is not rekeyed.
- Losing one password doesn't lock out others. If *all* entries are lost the DB
  is unrecoverable (an acknowledged, documented dead end).

AES-GCM authenticates on decrypt, so a wrong password raises ``BadPassword``
rather than silently returning garbage.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MASTER_KEY_BYTES = 32
SALT_BYTES = 16
NONCE_BYTES = 12

# scrypt cost parameters (n must be a power of two). Tuned for desktop login latency.
_KDF = {"n": 2**14, "r": 8, "p": 1, "length": MASTER_KEY_BYTES}


class KeyfileError(Exception):
    """Base class for keyfile problems."""


class KeyfileExists(KeyfileError):
    pass


class UnknownUser(KeyfileError):
    pass


class BadPassword(KeyfileError):
    pass


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def _norm(username: str) -> str:
    return username.strip().lower()


def _derive_kek(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=_KDF["length"], n=_KDF["n"], r=_KDF["r"], p=_KDF["p"])
    return kdf.derive(password.encode("utf-8"))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text("utf-8"))


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), "utf-8")
    os.replace(tmp, path)


def _wrap_entry(password: str, master_key: bytes) -> dict[str, str]:
    salt = secrets.token_bytes(SALT_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    kek = _derive_kek(password, salt)
    wrapped = AESGCM(kek).encrypt(nonce, master_key, None)
    return {"salt": _b64e(salt), "nonce": _b64e(nonce), "wrapped_key": _b64e(wrapped)}


def keyfile_exists(path: Path) -> bool:
    return path.exists()


def create_keyfile(path: Path, username: str, password: str) -> bytes:
    """Create a brand-new keyfile with one user; return the fresh master key."""
    if path.exists():
        raise KeyfileExists(f"keyfile already exists at {path}")
    master_key = secrets.token_bytes(MASTER_KEY_BYTES)
    data = {"version": 1, "kdf": dict(_KDF), "users": {}}
    data["users"][_norm(username)] = _wrap_entry(password, master_key)
    _atomic_write(path, data)
    return master_key


def unlock(path: Path, username: str, password: str) -> bytes:
    """Return the master key for ``username``/``password`` or raise."""
    if not path.exists():
        raise KeyfileError(f"no keyfile at {path}")
    data = _load(path)
    entry = data.get("users", {}).get(_norm(username))
    if entry is None:
        raise UnknownUser(username)
    kek = _derive_kek(password, _b64d(entry["salt"]))
    try:
        return AESGCM(kek).decrypt(_b64d(entry["nonce"]), _b64d(entry["wrapped_key"]), None)
    except InvalidTag as exc:
        raise BadPassword(username) from exc


def add_or_update_user(path: Path, master_key: bytes, username: str, password: str) -> None:
    """Wrap ``master_key`` for a (new or existing) user. Caller must already hold
    the master key (i.e. be an unlocked admin). Used for create-user and reset."""
    data = _load(path)
    data.setdefault("users", {})[_norm(username)] = _wrap_entry(password, master_key)
    _atomic_write(path, data)


def remove_user(path: Path, username: str) -> None:
    data = _load(path)
    data.get("users", {}).pop(_norm(username), None)
    _atomic_write(path, data)


def has_user(path: Path, username: str) -> bool:
    if not path.exists():
        return False
    return _norm(username) in _load(path).get("users", {})
