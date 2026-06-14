"""Component-type & purity-type management (admin writes, all-user reads)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_db, require_admin
from app.models import ComponentType, PurityType, User
from app.schemas.masters import LookupIn, LookupOut, LookupUpdate, ReorderIn


def build_lookup_router(prefix: str, tag: str, model) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("", response_model=list[LookupOut])
    def list_items(
        active_only: bool = False,
        db: Session = Depends(get_db),
        _user: User = Depends(get_current_user),
    ):
        q = db.query(model)
        if active_only:
            q = q.filter(model.is_active.is_(True))
        return q.order_by(model.sort_order, model.name).all()

    @router.post(
        "",
        response_model=LookupOut,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_admin)],
    )
    def create_item(payload: LookupIn, db: Session = Depends(get_db)):
        if db.query(model).filter(func.lower(model.name) == payload.name.strip().lower()).first():
            raise HTTPException(status.HTTP_409_CONFLICT, "name_exists")
        max_order = db.query(func.max(model.sort_order)).scalar() or 0
        obj = model(name=payload.name.strip(), sort_order=max_order + 1, is_active=True)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @router.put("/{obj_id}", response_model=LookupOut, dependencies=[Depends(require_admin)])
    def update_item(obj_id: int, payload: LookupUpdate, db: Session = Depends(get_db)):
        obj = db.get(model, obj_id)
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        data = payload.model_dump(exclude_unset=True)
        if "name" in data:
            obj.name = data["name"].strip()
        if "is_active" in data:
            obj.is_active = data["is_active"]
        if "sort_order" in data:
            obj.sort_order = data["sort_order"]
        db.commit()
        db.refresh(obj)
        return obj

    @router.post("/reorder", dependencies=[Depends(require_admin)])
    def reorder(payload: ReorderIn, db: Session = Depends(get_db)):
        for index, obj_id in enumerate(payload.ordered_ids):
            obj = db.get(model, obj_id)
            if obj is not None:
                obj.sort_order = index
        db.commit()
        return {"ok": True}

    return router


component_types = build_lookup_router("/api/component-types", "component-types", ComponentType)
purity_types = build_lookup_router("/api/purity-types", "purity-types", PurityType)
