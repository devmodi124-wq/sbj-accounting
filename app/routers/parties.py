"""Party (supplier) CRUD + type-ahead search (delete guarded by linked records)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import CashEntry, OpeningBalance, Party, Purchase
from app.models.base import EntityType
from app.routers._contacts import build_contact_router
from app.services.matching import search_parties


def _count_references(session: Session, party_id: int) -> int:
    return (
        session.query(Purchase).filter(Purchase.party_id == party_id).count()
        + session.query(CashEntry).filter(CashEntry.party_id == party_id).count()
        + session.query(OpeningBalance)
        .filter(OpeningBalance.entity_type == EntityType.party,
                OpeningBalance.entity_id == party_id)
        .count()
    )


router = build_contact_router(
    "/api/parties", "parties", Party, search_parties, _count_references
)
