"""Auth operations: bootstrap, login, logout, and user provisioning.

Login flow:
  1. ``keyfile.unlock`` derives the master key from username+password and opens
     the encrypted DB (binding the process engine).
  2. The DB ``users`` record is the authority for role/active — verify the bcrypt
     hash there too.
  3. A single active session is enforced (existing sessions are cleared).
"""
from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.config import get_settings
from app.crypto import keyfile
from app.db import engine_state
from app.models import User, UserSession
from app.models.base import UserRole
from app.services.audit import acting_as
from app.services.seed import initialize_database


class AuthError(Exception):
    pass


class BootstrapNotAllowed(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class InactiveUser(AuthError):
    pass


class UsernameTaken(AuthError):
    pass


def _norm(username: str) -> str:
    return username.strip().lower()


def needs_bootstrap() -> bool:
    """True on first run — no keyfile yet, so a first admin must be created."""
    return not keyfile.keyfile_exists(get_settings().keyfile_path)


def _bind_and_init(master_key: bytes) -> None:
    s = get_settings()
    engine = engine_state.bind(s.db_path, master_key)
    initialize_database(engine)


def _start_single_session(session: Session, user: User) -> str:
    """Clear any existing sessions (single active session) and create a new one."""
    session.query(UserSession).delete()
    token = secrets.token_urlsafe(32)
    session.add(UserSession(user_id=user.id, token=token))
    session.commit()
    return token


def bootstrap(username: str, password: str, full_name: str = "") -> tuple[User, str]:
    """First-run: create the keyfile + first admin, open the DB, return (user, token)."""
    if not needs_bootstrap():
        raise BootstrapNotAllowed("application already initialized")
    s = get_settings()
    s.ensure_data_dir()
    master_key = keyfile.create_keyfile(s.keyfile_path, username, password)
    _bind_and_init(master_key)

    assert engine_state.sessionmaker is not None
    with engine_state.sessionmaker() as session:
        with acting_as(None):
            user = User(
                username=_norm(username),
                full_name=full_name,
                role=UserRole.admin,
                password_hash=hash_password(password),
                is_active=True,
            )
            session.add(user)
            session.commit()
        token = _start_single_session(session, user)
        return user, token


def login(username: str, password: str) -> tuple[User, str]:
    if needs_bootstrap():
        raise BootstrapNotAllowed("not initialized")
    s = get_settings()
    try:
        master_key = keyfile.unlock(s.keyfile_path, username, password)
    except (keyfile.UnknownUser, keyfile.BadPassword) as exc:
        raise InvalidCredentials() from exc

    _bind_and_init(master_key)
    assert engine_state.sessionmaker is not None
    with engine_state.sessionmaker() as session:
        user = session.query(User).filter(User.username == _norm(username)).first()
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentials()
        if not user.is_active:
            raise InactiveUser()
        token = _start_single_session(session, user)
        return user, token


def logout(token: str) -> None:
    if engine_state.sessionmaker is None:
        return
    with engine_state.sessionmaker() as session:
        session.query(UserSession).filter(UserSession.token == token).delete()
        session.commit()


def create_user(
    session: Session,
    username: str,
    password: str,
    role: UserRole,
    full_name: str = "",
) -> User:
    """Provision a new user: wrap the master key for them + store a DB record.

    Requires the DB to be unlocked (``engine_state.master_key`` available).
    """
    if engine_state.master_key is None:
        raise AuthError("database is locked")
    uname = _norm(username)
    if session.query(User).filter(User.username == uname).first() is not None:
        raise UsernameTaken(uname)
    keyfile.add_or_update_user(
        get_settings().keyfile_path, engine_state.master_key, uname, password
    )
    user = User(
        username=uname,
        full_name=full_name,
        role=role,
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(user)
    session.commit()
    return user


def reset_password(session: Session, user: User, new_password: str) -> None:
    """Admin resets another user's password: re-wrap keyfile + update DB hash."""
    if engine_state.master_key is None:
        raise AuthError("database is locked")
    keyfile.add_or_update_user(
        get_settings().keyfile_path, engine_state.master_key, user.username, new_password
    )
    user.password_hash = hash_password(new_password)
    session.commit()
