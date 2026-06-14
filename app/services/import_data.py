"""Parse, validate, and commit a filled import template.

Validation runs first and reports every problem (with sheet + row) so the admin
can fix the file before anything is written. Commit applies all sheets in a single
transaction — any error rolls back the whole import. Customer/party names reuse the
same matching as manual entry (:mod:`app.services.matching`).
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models import (
    CashEntry,
    ComponentType,
    ItemCategory,
    Order,
    OrderItem,
    Purchase,
    PurityType,
    SupplySource,
    User,
    WeightType,
)
from app.models.base import (
    BalanceDirection,
    CashEntryType,
    EntityType,
    OrderStatus,
    PaymentMode,
)
from app.services.import_template import SHEETS
from app.services.ledger import set_opening_balance
from app.services.matching import (
    find_customer_match,
    find_party_match,
    get_or_create_customer,
    get_or_create_party,
)

VALID_STATUS = {s.value for s in OrderStatus}
VALID_PAYMENT = {m.value for m in PaymentMode}
VALID_CASH = {t.value for t in CashEntryType}
VALID_ENTITY = {e.value for e in EntityType}
VALID_DIRECTION = {d.value for d in BalanceDirection}


def _s(value) -> str:
    return "" if value is None else str(value).strip()


def _parse_date(value) -> Optional[date]:
    if value is None or _s(value) == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(_s(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_decimal(value) -> Optional[Decimal]:
    if value is None or _s(value) == "":
        return Decimal("0")
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def parse_workbook(data: bytes) -> dict[str, list[dict]]:
    wb = load_workbook(io.BytesIO(data), data_only=True)
    out: dict[str, list[dict]] = {}
    for title, headers in SHEETS.items():
        rows: list[dict] = []
        if title in wb.sheetnames:
            ws = wb[title]
            for raw in ws.iter_rows(min_row=2, values_only=True):
                if raw is None or all(c is None or _s(c) == "" for c in raw):
                    continue
                rows.append({headers[i]: (raw[i] if i < len(raw) else None) for i in range(len(headers))})
        out[title] = rows
    return out


def validate(session: Session, sheets: dict[str, list[dict]]) -> dict:
    errors: list[dict] = []

    def err(sheet, row, msg):
        errors.append({"sheet": sheet, "row": row, "message": msg})

    components = {c.name.strip().lower() for c in session.query(ComponentType).all()}
    purities = {p.name.strip().lower() for p in session.query(PurityType).all()}
    categories = {c.name.strip().lower() for c in session.query(ItemCategory).all()}
    weight_types = {w.name.strip().lower() for w in session.query(WeightType).all()}
    supply_sources = {s.name.strip().lower() for s in session.query(SupplySource).all()}

    for label in ("Customers", "Parties"):
        for i, row in enumerate(sheets.get(label, []), start=2):
            if not _s(row.get("name")):
                err(label, i, "name is required")

    order_refs: set[str] = set()
    for i, row in enumerate(sheets.get("Orders", []), start=2):
        if not _s(row.get("customer_name")):
            err("Orders", i, "customer_name is required")
        category = _s(row.get("item_category")).lower()
        if not category:
            err("Orders", i, "item_category is required")
        elif category not in categories:
            err("Orders", i, f"unknown item_category '{row.get('item_category')}'")
        wt = _s(row.get("weight_type")).lower()
        if wt and wt not in weight_types:
            err("Orders", i, f"unknown weight_type '{row.get('weight_type')}'")
        ss = _s(row.get("supply_source")).lower()
        if ss and ss not in supply_sources:
            err("Orders", i, f"unknown supply_source '{row.get('supply_source')}'")
        if _parse_date(row.get("order_date")) is None:
            err("Orders", i, "order_date missing or not YYYY-MM-DD")
        status = _s(row.get("status")).lower() or "pending"
        if status not in VALID_STATUS:
            err("Orders", i, f"invalid status '{status}'")
        mode = _s(row.get("payment_mode")).lower()
        if mode and mode not in VALID_PAYMENT:
            err("Orders", i, f"invalid payment_mode '{mode}'")
        if _parse_decimal(row.get("payment_received")) is None:
            err("Orders", i, "payment_received is not a number")
        ref = _s(row.get("order_ref"))
        if ref:
            if ref in order_refs:
                err("Orders", i, f"duplicate order_ref '{ref}'")
            order_refs.add(ref)

    for i, row in enumerate(sheets.get("Order Items", []), start=2):
        ref = _s(row.get("order_ref"))
        if not ref or ref not in order_refs:
            err("Order Items", i, f"order_ref '{ref}' not found in Orders")
        comp = _s(row.get("component_type")).lower()
        if comp not in components:
            err("Order Items", i, f"unknown component_type '{row.get('component_type')}'")
        purity = _s(row.get("purity")).lower()
        if purity and purity not in purities:
            err("Order Items", i, f"unknown purity '{row.get('purity')}'")
        if _parse_decimal(row.get("price")) is None:
            err("Order Items", i, "price is not a number")

    for i, row in enumerate(sheets.get("Cash Entries", []), start=2):
        if _parse_date(row.get("date")) is None:
            err("Cash Entries", i, "date missing or not YYYY-MM-DD")
        if _s(row.get("type")).lower() not in VALID_CASH:
            err("Cash Entries", i, "type must be received or paid")
        if _parse_decimal(row.get("amount")) is None:
            err("Cash Entries", i, "amount is not a number")

    for i, row in enumerate(sheets.get("Purchases", []), start=2):
        if not _s(row.get("party_name")):
            err("Purchases", i, "party_name is required")
        if _parse_date(row.get("date")) is None:
            err("Purchases", i, "date missing or not YYYY-MM-DD")
        for fld in ("amount", "amount_paid"):
            if _parse_decimal(row.get(fld)) is None:
                err("Purchases", i, f"{fld} is not a number")

    for i, row in enumerate(sheets.get("Opening Balances", []), start=2):
        if _s(row.get("entity_type")).lower() not in VALID_ENTITY:
            err("Opening Balances", i, "entity_type must be customer or party")
        if not _s(row.get("entity_name")):
            err("Opening Balances", i, "entity_name is required")
        if _s(row.get("direction")).lower() not in VALID_DIRECTION:
            err("Opening Balances", i, "direction must be debit or credit")
        if _parse_decimal(row.get("amount")) is None:
            err("Opening Balances", i, "amount is not a number")
        if _parse_date(row.get("as_of_date")) is None:
            err("Opening Balances", i, "as_of_date missing or not YYYY-MM-DD")

    summary = {title: len(rows) for title, rows in sheets.items()}
    return {"ok": len(errors) == 0, "errors": errors, "summary": summary}


def commit(session: Session, user: User, sheets: dict[str, list[dict]], today: Optional[date] = None) -> dict:
    """Apply a validated import in one transaction. Raises on error (rolled back)."""
    today = today or date.today()
    comp_by_name = {c.name.strip().lower(): c for c in session.query(ComponentType).all()}
    purity_by_name = {p.name.strip().lower(): p for p in session.query(PurityType).all()}
    category_by_name = {c.name.strip().lower(): c for c in session.query(ItemCategory).all()}
    weight_by_name = {w.name.strip().lower(): w for w in session.query(WeightType).all()}
    supply_by_name = {s.name.strip().lower(): s for s in session.query(SupplySource).all()}
    counts = {"customers": 0, "parties": 0, "orders": 0, "order_items": 0,
              "cash_entries": 0, "purchases": 0, "opening_balances": 0}

    try:
        for row in sheets.get("Customers", []):
            cust, created = get_or_create_customer(session, _s(row.get("name")), created_by=user.id)
            if created:
                cust.phone = _s(row.get("phone")) or None
                cust.address = _s(row.get("address")) or None
                cust.notes = _s(row.get("notes")) or None
                counts["customers"] += 1
        for row in sheets.get("Parties", []):
            party, created = get_or_create_party(session, _s(row.get("name")), created_by=user.id)
            if created:
                party.phone = _s(row.get("phone")) or None
                party.address = _s(row.get("address")) or None
                party.notes = _s(row.get("notes")) or None
                counts["parties"] += 1

        ref_to_order: dict[str, Order] = {}
        for row in sheets.get("Orders", []):
            customer, _ = get_or_create_customer(session, _s(row.get("customer_name")), created_by=user.id)
            order_date = _parse_date(row.get("order_date"))
            wt = _s(row.get("weight_type")).lower()
            ss = _s(row.get("supply_source")).lower()
            order = Order(
                customer_id=customer.id,
                order_date=order_date,
                item_category_id=category_by_name[_s(row.get("item_category")).lower()].id,
                item_name=_s(row.get("item_name")) or None,
                weight_type_id=weight_by_name[wt].id if wt else None,
                supply_source_id=supply_by_name[ss].id if ss else None,
                order_code=_s(row.get("order_code")) or None,
                notes=_s(row.get("notes")) or None,
                status=OrderStatus(_s(row.get("status")).lower() or "pending"),
                payment_received=_parse_decimal(row.get("payment_received")) or Decimal("0"),
                payment_mode=PaymentMode(_s(row.get("payment_mode")).lower()) if _s(row.get("payment_mode")) else None,
                created_by=user.id,
                is_backdated=order_date < today if order_date else False,
                total_amount=Decimal("0"),
                balance=Decimal("0"),
            )
            session.add(order)
            session.flush()
            counts["orders"] += 1
            ref = _s(row.get("order_ref"))
            if ref:
                ref_to_order[ref] = order

        order_index: dict[int, int] = {}
        for row in sheets.get("Order Items", []):
            order = ref_to_order.get(_s(row.get("order_ref")))
            if order is None:
                continue
            idx = order_index.get(order.id, 0)
            order_index[order.id] = idx + 1
            comp = comp_by_name[_s(row.get("component_type")).lower()]
            purity_name = _s(row.get("purity")).lower()
            session.add(OrderItem(
                order_id=order.id,
                component_type_id=comp.id,
                pcs=int(row["pcs"]) if _s(row.get("pcs")).isdigit() else None,
                weight=_parse_decimal(row.get("weight")) if _s(row.get("weight")) else None,
                purity_type_id=purity_by_name[purity_name].id if purity_name else None,
                rate=_parse_decimal(row.get("rate")) if _s(row.get("rate")) else None,
                price=_parse_decimal(row.get("price")) or Decimal("0"),
                sort_order=idx,
            ))
            counts["order_items"] += 1

        # Recompute order totals from their imported items.
        session.flush()
        for order in ref_to_order.values():
            total = sum((it.price for it in order.items), Decimal("0"))
            order.total_amount = total
            order.balance = total - order.payment_received

        for row in sheets.get("Cash Entries", []):
            person = _s(row.get("person_name"))
            cust = find_customer_match(session, person) if person else None
            party = find_party_match(session, person) if person else None
            cash_date = _parse_date(row.get("date"))
            session.add(CashEntry(
                entry_date=cash_date,
                person_name=person,
                customer_id=cust.id if cust else None,
                party_id=party.id if (party and not cust) else None,
                details=_s(row.get("details")) or None,
                entry_type=CashEntryType(_s(row.get("type")).lower()),
                amount=_parse_decimal(row.get("amount")) or Decimal("0"),
                created_by=user.id,
                is_backdated=cash_date < today if cash_date else False,
            ))
            counts["cash_entries"] += 1

        for row in sheets.get("Purchases", []):
            party, _ = get_or_create_party(session, _s(row.get("party_name")), created_by=user.id)
            amount = _parse_decimal(row.get("amount")) or Decimal("0")
            paid = _parse_decimal(row.get("amount_paid")) or Decimal("0")
            p_date = _parse_date(row.get("date"))
            session.add(Purchase(
                purchase_date=p_date,
                party_id=party.id,
                details=_s(row.get("details")) or None,
                entry_notes=_s(row.get("entry_notes")) or None,
                amount=amount,
                amount_paid=paid,
                balance=amount - paid,
                created_by=user.id,
                is_backdated=p_date < today if p_date else False,
            ))
            counts["purchases"] += 1

        for row in sheets.get("Opening Balances", []):
            etype = EntityType(_s(row.get("entity_type")).lower())
            name = _s(row.get("entity_name"))
            if etype == EntityType.customer:
                entity, _ = get_or_create_customer(session, name, created_by=user.id)
            else:
                entity, _ = get_or_create_party(session, name, created_by=user.id)
            set_opening_balance(
                session, etype, entity.id, _parse_date(row.get("as_of_date")),
                _parse_decimal(row.get("amount")) or Decimal("0"),
                BalanceDirection(_s(row.get("direction")).lower()), created_by=user.id,
            )
            counts["opening_balances"] += 1

        session.commit()
        return {"ok": True, "imported": counts}
    except Exception:
        session.rollback()
        raise
