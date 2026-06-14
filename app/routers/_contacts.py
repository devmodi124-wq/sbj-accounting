"""Factory for the near-identical customer/party CRUD + search routers."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_db
from app.models import User
from app.schemas.masters import ContactIn, ContactOut


def build_contact_router(prefix: str, tag: str, model, search_fn: Callable) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("", response_model=list[ContactOut])
    def list_contacts(
        q: str = "",
        limit: int = 20,
        db: Session = Depends(get_db),
        _user: User = Depends(get_current_user),
    ):
        return search_fn(db, q, limit)

    @router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
    def create_contact(
        payload: ContactIn,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ):
        obj = model(**payload.model_dump(), created_by=user.id)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @router.get("/{obj_id}", response_model=ContactOut)
    def get_contact(
        obj_id: int,
        db: Session = Depends(get_db),
        _user: User = Depends(get_current_user),
    ):
        obj = db.get(model, obj_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        return obj

    @router.put("/{obj_id}", response_model=ContactOut)
    def update_contact(
        obj_id: int,
        payload: ContactIn,
        db: Session = Depends(get_db),
        _user: User = Depends(get_current_user),
    ):
        obj = db.get(model, obj_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        for key, value in payload.model_dump().items():
            setattr(obj, key, value)
        db.commit()
        db.refresh(obj)
        return obj

    return router
