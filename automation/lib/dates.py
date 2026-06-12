"""
Family inc. — date/time parsing + formatting. One implementation (SPEC.md §8.5).

The 2026-06-11 audit found `to_date` defined in three scripts; this is the
survivor. All times are naive local Asia/Jerusalem (system TZ on the appliance).
"""
from __future__ import annotations

from datetime import date, datetime


def to_date(v) -> date | None:
    """Best-effort date. Accepts date/datetime cells, ISO strings, and the
    Sheet's DD/MM/YYYY contract (SPEC.md §6.1 col D). None when unparseable —
    callers skip + report, never raise (data-hygiene principle)."""
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None
    return None


def to_datetime(v) -> datetime | None:
    """Best-effort ISO datetime parser. Handles datetime cells, date cells,
    and the ISO-ish string shapes the dashboard write-back emits."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # Tolerate trailing Z and space-separator
        s = s.replace("Z", "+00:00").replace(" ", "T", 1) if "T" not in s and " " in s else s.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            # Callers compare against naive local time. Drop tz if present.
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
        except ValueError:
            try:
                return datetime.strptime(s, "%Y-%m-%d")
            except ValueError:
                return None
    return None


def fmt_date(d: date | None) -> str:
    """Sun May 31 — weekly-briefing style."""
    if not d:
        return ""
    return d.strftime("%a %b %-d")
