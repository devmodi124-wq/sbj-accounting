"""Database engine wiring for the SQLCipher-encrypted SQLite database.

The DB is encrypted with a single random 32-byte *master key* (managed by the
keyfile envelope in :mod:`app.crypto.keyfile`, Phase 2). Here we just turn that
raw key into a working SQLAlchemy engine.

We use SQLCipher's *raw key* form (``PRAGMA key = "x'<hex>'"``) so the 32 random
bytes are used directly as the cipher key with no extra password derivation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

import sqlcipher3
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

MASTER_KEY_BYTES = 32

# Bumped when the schema changes; drives hand-written upgrade steps (see seed.py).
SCHEMA_VERSION = 1


class Base(DeclarativeBase):
    """Declarative base for all ORM models (defined in :mod:`app.models`)."""


def build_engine(db_path: Path, key: bytes, *, echo: bool = False) -> Engine:
    """Create an engine bound to ``db_path``, unlocked with raw ``key``.

    ``key`` must be the raw 32-byte master key. Each new DBAPI connection issues
    ``PRAGMA key`` (raw-key form) plus ``PRAGMA foreign_keys=ON``.
    """
    if len(key) != MASTER_KEY_BYTES:
        raise ValueError(f"master key must be {MASTER_KEY_BYTES} bytes, got {len(key)}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    hex_key = key.hex()

    engine = create_engine(
        f"sqlite:///{db_path}",
        module=sqlcipher3.dbapi2,
        echo=echo,
        # SQLite + single desktop user: keep one connection's semantics simple.
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _unlock(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute(f"PRAGMA key = \"x'{hex_key}'\"")
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    return engine


class EngineState:
    """Holds the live engine + sessionmaker once the DB is unlocked at login.

    Before unlock (locked screen / first run) ``engine`` is ``None``.
    """

    def __init__(self) -> None:
        self.engine: Optional[Engine] = None
        self.sessionmaker: Optional[sessionmaker[Session]] = None

    def bind(self, db_path: Path, key: bytes, *, echo: bool = False) -> Engine:
        self.dispose()
        self.engine = build_engine(db_path, key, echo=echo)
        self.sessionmaker = sessionmaker(bind=self.engine, expire_on_commit=False)
        return self.engine

    def dispose(self) -> None:
        if self.engine is not None:
            self.engine.dispose()
        self.engine = None
        self.sessionmaker = None

    @property
    def is_unlocked(self) -> bool:
        return self.sessionmaker is not None


# Process-wide engine state (single-user desktop app → one active DB at a time).
engine_state = EngineState()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session for the unlocked DB."""
    if engine_state.sessionmaker is None:
        raise RuntimeError("database is locked — no active session")
    session = engine_state.sessionmaker()
    try:
        yield session
    finally:
        session.close()
