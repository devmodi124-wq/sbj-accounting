"""Customer CRUD + type-ahead search (delete guarded by linked records)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import CashEntry, Customer, OpeningBalance, Order
from app.models.base import EntityType
from app.routers._contacts import build_contact_router
from app.services.matching import search_customers


def _count_references(session: Session, customer_id: int) -> int:
    return (
        session.query(Order).filter(Order.customer_id == customer_id).count()
        + session.query(CashEntry).filter(CashEntry.customer_id == customer_id).count()
        + session.query(OpeningBalance)
        .filter(OpeningBalance.entity_type == EntityType.customer,
                OpeningBalance.entity_id == customer_id)
        .count()
    )


router = build_contact_router(
    "/api/customers", "customers", Customer, search_customers, _count_references
)
