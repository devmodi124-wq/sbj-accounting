"""Party (supplier) CRUD + type-ahead search."""
from __future__ import annotations

from app.models import Party
from app.routers._contacts import build_contact_router
from app.services.matching import search_parties

router = build_contact_router("/api/parties", "parties", Party, search_parties)
