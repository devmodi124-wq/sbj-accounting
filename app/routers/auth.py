"""Authentication endpoints: status, bootstrap, login, logout, me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.auth import SESSION_COOKIE, service
from app.auth.deps import get_current_user
from app.db import engine_state
from app.models import User, UserSession

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie lifetime — long-lived; single-session enforcement is the real control.
_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)


class BootstrapIn(Credentials):
    full_name: str = ""


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.value,
    }


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
    )


@router.get("/status")
def auth_status(request: Request) -> dict:
    if service.needs_bootstrap():
        return {"state": "needs_bootstrap", "authenticated": False, "user": None}
    if not engine_state.is_unlocked:
        return {"state": "locked", "authenticated": False, "user": None}

    user_out = None
    token = request.cookies.get(SESSION_COOKIE)
    if token and engine_state.sessionmaker is not None:
        with engine_state.sessionmaker() as session:
            us = session.query(UserSession).filter(UserSession.token == token).first()
            if us is not None:
                user = session.get(User, us.user_id)
                if user is not None and user.is_active:
                    user_out = _user_out(user)
    return {"state": "unlocked", "authenticated": user_out is not None, "user": user_out}


@router.post("/bootstrap")
def bootstrap(payload: BootstrapIn, response: Response) -> dict:
    try:
        user, token = service.bootstrap(payload.username, payload.password, payload.full_name)
    except service.BootstrapNotAllowed:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_initialized")
    _set_cookie(response, token)
    return {"user": _user_out(user)}


@router.post("/login")
def login(payload: Credentials, response: Response) -> dict:
    try:
        user, token = service.login(payload.username, payload.password)
    except service.BootstrapNotAllowed:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_initialized")
    except service.InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    except service.InactiveUser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "inactive_user")
    _set_cookie(response, token)
    return {"user": _user_out(user)}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        service.logout(token)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {"user": _user_out(user)}
