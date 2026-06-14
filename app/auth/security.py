"""Password hashing (bcrypt).

Passwords are pre-hashed with SHA-256 and base64-encoded before bcrypt so they
are not silently truncated at bcrypt's 72-byte limit and contain no NUL bytes.
"""
from __future__ import annotations

import base64
import hashlib

import bcrypt


def _prep(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prep(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prep(password), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False
