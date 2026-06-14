"""User management (admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import get_db, require_admin
from app.models import User
from app.models.base import UserRole
from app.schemas.users import PasswordReset, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return db.query(User).order_by(User.username).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    try:
        return service.create_user(
            db, payload.username, payload.password, payload.role, payload.full_name
        )
    except service.UsernameTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "username_taken")


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")

    data = payload.model_dump(exclude_unset=True)
    # Guard against self-lockout: an admin cannot deactivate or demote themselves.
    if user.id == admin.id:
        if data.get("is_active") is False:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_deactivate_self")
        if data.get("role") == UserRole.employee:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_demote_self")

    for key in ("full_name", "role", "is_active"):
        if key in data:
            setattr(user, key, data[key])
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: PasswordReset,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    service.reset_password(db, user, payload.password)
    return {"ok": True}
