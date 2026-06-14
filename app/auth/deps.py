"""FastAPI dependencies for authentication / authorization.

``get_current_user`` also sets the audit contextvar so every write made during
the request is attributed to the acting user.
"""
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE
from app.db import engine_state, get_session
from app.models import User, UserSession
from app.models.base import UserRole
from app.services.audit import current_user_id


def get_db() -> Iterator[Session]:
    if not engine_state.is_unlocked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "locked")
    yield from get_session()


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> Iterator[User]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    us = db.query(UserSession).filter(UserSession.token == token).first()
    if us is None:
        # Either never logged in, or this session was invalidated by a newer login.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session_invalid")
    user = db.get(User, us.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session_invalid")

    # NOTE: a generator dependency's setup and teardown can run in different
    # contexts under FastAPI, so Token.reset() raises. Restore by value instead.
    previous = current_user_id.get()
    current_user_id.set(user.id)
    try:
        yield user
    finally:
        current_user_id.set(previous)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin_required")
    return user
