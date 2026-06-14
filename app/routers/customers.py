"""Customer CRUD + type-ahead search."""
from __future__ import annotations

from app.models import Customer
from app.routers._contacts import build_contact_router
from app.services.matching import search_customers

router = build_contact_router("/api/customers", "customers", Customer, search_customers)
