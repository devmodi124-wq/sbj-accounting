"""Phase 3 — shared customer/party matching."""
from __future__ import annotations

from app.models import Customer
from app.services.matching import (
    find_customer_match,
    get_or_create_customer,
    normalize_name,
    search_customers,
)


def test_normalize_name():
    assert normalize_name("  Malti   Devi ") == "malti devi"


def test_match_is_case_insensitive_and_trimmed(session):
    session.add(Customer(name="Malti Devi"))
    session.commit()
    assert find_customer_match(session, "  malti devi ") is not None
    assert find_customer_match(session, "MALTI DEVI") is not None
    assert find_customer_match(session, "Malti") is None


def test_get_or_create_reuses_existing(session):
    c1, created1 = get_or_create_customer(session, "Sunita Bindal")
    session.commit()
    c2, created2 = get_or_create_customer(session, "  sunita bindal ")
    assert created1 is True
    assert created2 is False
    assert c1.id == c2.id


def test_search_prefix_ranked_first(session):
    for name in ["Ravi Kumar", "Devi Lal", "Malti Devi"]:
        session.add(Customer(name=name))
    session.commit()
    results = [c.name for c in search_customers(session, "devi")]
    assert results[0] == "Devi Lal"  # prefix match ranked above substring match
    assert "Malti Devi" in results
