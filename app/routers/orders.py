"""Order endpoints (create/list/get/update)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, get_db
from app.models import Order, OrderImage, User
from app.models.base import OrderStatus
from app.schemas.orders import OrderIn, OrderOut, OrderSummary
from app.services import orders as order_service
from app.services.backdating import BackdateNotAllowed

router = APIRouter(prefix="/api/orders", tags=["orders"])

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB per picture


def _summary(order: Order) -> OrderSummary:
    return OrderSummary(
        id=order.id,
        customer_id=order.customer_id,
        customer_name=order.customer.name if order.customer else "",
        order_date=order.order_date,
        item_category=order.item_category.name if order.item_category else "",
        item_name=order.item_name,
        status=order.status,
        total_amount=order.total_amount,
        payment_received=order.payment_received,
        balance=order.balance,
        image_count=len(order.images),
    )


@router.get("", response_model=list[OrderSummary])
def list_orders(
    status_filter: Optional[OrderStatus] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    q = db.query(Order)
    if status_filter is not None:
        q = q.filter(Order.status == status_filter)
    orders = q.order_by(Order.order_date.desc(), Order.id.desc()).limit(limit).all()
    return [_summary(o) for o in orders]


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        return order_service.create_order(db, user, payload)
    except order_service.CustomerNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "customer_not_found")
    except order_service.LookupInvalid as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except BackdateNotAllowed as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return order


@router.put("/{order_id}", response_model=OrderOut)
def update_order(
    order_id: int,
    payload: OrderIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return order_service.update_order(db, user, order_id, payload)
    except order_service.OrderNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    except order_service.CustomerNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "customer_not_found")
    except order_service.LookupInvalid as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except BackdateNotAllowed as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


# ===== Order images (stored in the encrypted DB; multiple per order) =====

def _require_order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return order


def _image_meta(img: OrderImage) -> dict:
    return {"id": img.id, "filename": img.filename, "mime": img.mime, "sort_order": img.sort_order}


@router.get("/{order_id}/images")
def list_images(
    order_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[dict]:
    order = _require_order(db, order_id)
    return [_image_meta(img) for img in order.images]


@router.post("/{order_id}/images", status_code=status.HTTP_201_CREATED)
async def upload_images(
    order_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[dict]:
    order = _require_order(db, order_id)
    start = len(order.images)
    for offset, upload in enumerate(files):
        content = await upload.read()
        if not (upload.content_type or "").startswith("image/"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "not_an_image")
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "image_too_large")
        db.add(OrderImage(
            order_id=order.id,
            filename=upload.filename or "image",
            mime=upload.content_type or "image/jpeg",
            data=content,
            sort_order=start + offset,
        ))
    db.commit()
    db.refresh(order)
    return [_image_meta(img) for img in order.images]


@router.get("/{order_id}/images/{image_id}")
def get_image(
    order_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Response:
    img = db.get(OrderImage, image_id)
    if img is None or img.order_id != order_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return Response(content=img.data, media_type=img.mime)


@router.delete("/{order_id}/images/{image_id}")
def delete_image(
    order_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    img = db.get(OrderImage, image_id)
    if img is None or img.order_id != order_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    db.delete(img)
    db.commit()
    return {"ok": True}
