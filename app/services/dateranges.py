"""Resolve dashboard/report date-range presets to concrete (start, end) dates."""
from __future__ import annotations

import calendar
from datetime import date
from typing import Optional

PRESETS = {"today", "this_month", "this_quarter", "this_year", "custom"}


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def resolve_range(
    preset: str,
    today: Optional[date] = None,
    custom_from: Optional[date] = None,
    custom_to: Optional[date] = None,
) -> tuple[date, date]:
    today = today or date.today()
    preset = preset or "this_month"

    if preset == "today":
        return today, today
    if preset == "this_month":
        return date(today.year, today.month, 1), _month_end(today.year, today.month)
    if preset == "this_quarter":
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        q_end_month = q_start_month + 2
        return date(today.year, q_start_month, 1), _month_end(today.year, q_end_month)
    if preset == "this_year":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    if preset == "custom":
        start = custom_from or date(today.year, today.month, 1)
        end = custom_to or today
        return start, end
    # Unknown preset -> default to this month.
    return date(today.year, today.month, 1), _month_end(today.year, today.month)


def last_n_months(n: int, today: Optional[date] = None) -> list[tuple[int, int]]:
    """Return [(year, month), …] for the last ``n`` months ending with the current one."""
    today = today or date.today()
    out: list[tuple[int, int]] = []
    year, month = today.year, today.month
    for _ in range(n):
        out.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(out))
