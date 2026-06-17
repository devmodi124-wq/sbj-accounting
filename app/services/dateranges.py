"""Resolve dashboard/report date-range presets to concrete (start, end) dates."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Optional

# Shared across the dashboard and every date-based report (kept in sync with the
# preset dropdown in static/js/ui.js → KhataDates.PRESETS).
PRESETS = {
    "all_time", "today",
    "this_month", "last_month",
    "this_quarter", "last_quarter",
    "this_year", "last_year",
    "last_7_days", "last_30_days",
    "custom",
}

_ALL_TIME_START = date(1900, 1, 1)


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

    if preset == "all_time":
        return _ALL_TIME_START, today
    if preset == "today":
        return today, today
    if preset == "last_7_days":
        return today - timedelta(days=6), today
    if preset == "last_30_days":
        return today - timedelta(days=29), today
    if preset == "this_month":
        return date(today.year, today.month, 1), _month_end(today.year, today.month)
    if preset == "last_month":
        prev_end = date(today.year, today.month, 1) - timedelta(days=1)
        return date(prev_end.year, prev_end.month, 1), prev_end
    if preset == "this_quarter":
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        return date(today.year, q_start_month, 1), _month_end(today.year, q_start_month + 2)
    if preset == "last_quarter":
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        prev_end = date(today.year, q_start_month, 1) - timedelta(days=1)
        pq_start_month = ((prev_end.month - 1) // 3) * 3 + 1
        return date(prev_end.year, pq_start_month, 1), prev_end
    if preset == "this_year":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    if preset == "last_year":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    if preset == "custom":
        return (custom_from or date(today.year, today.month, 1)), (custom_to or today)
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
