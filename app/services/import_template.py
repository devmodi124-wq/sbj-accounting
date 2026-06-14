"""Generate the downloadable Excel import template (one sheet per data group)."""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.orm import Session

from app.models import ComponentType, ItemCategory, PurityType, SupplySource, WeightType

HEADER_FILL = PatternFill("solid", fgColor="1C1B19")
HEADER_FONT = Font(color="FBF8F2", bold=True)

SHEETS = {
    "Customers": ["name", "phone", "address", "notes"],
    "Parties": ["name", "phone", "address", "notes"],
    "Opening Balances": ["entity_type", "entity_name", "as_of_date", "amount", "direction"],
    "Orders": ["order_ref", "customer_name", "order_date", "item_category", "item_name",
               "weight_type", "supply_source", "order_code", "status", "payment_received",
               "payment_mode", "notes"],
    "Order Items": ["order_ref", "component_type", "pcs", "weight", "purity", "rate", "price"],
    "Cash Entries": ["date", "person_name", "details", "type", "amount"],
    "Purchases": ["date", "party_name", "details", "entry_notes", "amount", "amount_paid"],
}

INSTRUCTIONS = [
    "Khata — Import Template",
    "",
    "Fill each sheet and upload it under Settings > Import. Validation runs before anything is saved.",
    "",
    "Customers / Parties: 'name' is required; phone/address/notes optional.",
    "Orders: one row per order. 'order_ref' is your own reference used to link Order Items.",
    "  item_category is REQUIRED (dropdown). item_name (free text), weight_type and",
    "  supply_source are optional. status = pending or delivered.",
    "  payment_mode = cash/upi/bank_transfer/old_gold_exchange/other.",
    "Order Items: one or more rows per order; 'order_ref' must match a row in Orders.",
    "  component_type and purity must match the shop's configured lists (dropdowns provided).",
    "Cash Entries: type = received or paid.",
    "Opening Balances: entity_type = customer or party; direction = debit or credit.",
    "Dates: use YYYY-MM-DD (e.g. 2026-06-14).",
    "Customer/supplier names are matched case-insensitively; new names are created automatically.",
]


def _list_validation(values: list[str]) -> DataValidation:
    joined = ",".join(values)
    dv = DataValidation(type="list", formula1=f'"{joined}"', allow_blank=True)
    return dv


def _style_header(ws, headers: list[str]) -> None:
    for col, name in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=name)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        ws.column_dimensions[cell.column_letter].width = max(14, len(name) + 2)


def build_template(session: Session) -> bytes:
    components = [c.name for c in session.query(ComponentType).filter_by(is_active=True).all()]
    purities = [p.name for p in session.query(PurityType).filter_by(is_active=True).all()]
    categories = [c.name for c in session.query(ItemCategory).filter_by(is_active=True).all()]
    weights = [w.name for w in session.query(WeightType).filter_by(is_active=True).all()]
    supplies = [s.name for s in session.query(SupplySource).filter_by(is_active=True).all()]

    wb = Workbook()
    # Instructions sheet first.
    ws_info = wb.active
    ws_info.title = "Instructions"
    for i, line in enumerate(INSTRUCTIONS, start=1):
        ws_info.cell(row=i, column=1, value=line)
    ws_info.column_dimensions["A"].width = 100

    for title, headers in SHEETS.items():
        ws = wb.create_sheet(title)
        _style_header(ws, headers)

        def add_dv(values, col_letter):
            if not values:
                return
            dv = _list_validation(values)
            ws.add_data_validation(dv)
            dv.add(f"{col_letter}2:{col_letter}1000")

        if title == "Orders":
            # Columns: A ref, B customer, C date, D category, E item_name, F weight,
            #          G supply, H code, I status, J received, K mode, L notes
            add_dv(categories, "D")
            add_dv(weights, "F")
            add_dv(supplies, "G")
            add_dv(["pending", "delivered"], "I")
            add_dv(["cash", "upi", "bank_transfer", "old_gold_exchange", "other"], "K")
        elif title == "Order Items":
            add_dv(components, "B")
            add_dv(purities, "E")
        elif title == "Cash Entries":
            add_dv(["received", "paid"], "D")
        elif title == "Opening Balances":
            add_dv(["customer", "party"], "A")
            add_dv(["debit", "credit"], "E")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
