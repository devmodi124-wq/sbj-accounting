"""Phase 0 encryption spike, as a permanent regression test.

Proves the SQLCipher + SQLAlchemy stack: data is encrypted at rest, the correct
master key reopens it, and a wrong key is rejected.
"""
from __future__ import annotations

import secrets
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.db import MASTER_KEY_BYTES, build_engine


def test_db_file_is_encrypted_at_rest(encrypted_engine, db_path: Path):
    with encrypted_engine.begin() as c:
        c.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
        c.execute(text("INSERT INTO t (v) VALUES ('secret')"))

    header = db_path.read_bytes()[:16]
    assert not header.startswith(b"SQLite format 3"), "DB must not be plaintext SQLite"


def test_correct_key_reopens(db_path: Path, master_key: bytes):
    e1 = build_engine(db_path, master_key)
    with e1.begin() as c:
        c.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
        c.execute(text("INSERT INTO t (v) VALUES ('hello')"))
    e1.dispose()

    e2 = build_engine(db_path, master_key)
    with e2.connect() as c:
        rows = c.execute(text("SELECT v FROM t")).fetchall()
    e2.dispose()
    assert rows == [("hello",)]


def test_wrong_key_rejected(db_path: Path, master_key: bytes):
    e1 = build_engine(db_path, master_key)
    with e1.begin() as c:
        c.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
    e1.dispose()

    wrong = secrets.token_bytes(MASTER_KEY_BYTES)
    e2 = build_engine(db_path, wrong)
    with pytest.raises(DatabaseError):
        with e2.connect() as c:
            c.execute(text("SELECT name FROM sqlite_master")).fetchall()
    e2.dispose()


def test_build_engine_rejects_bad_key_length(db_path: Path):
    with pytest.raises(ValueError):
        build_engine(db_path, b"too-short")
