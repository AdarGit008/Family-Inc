"""
Family inc. — date/time parsing + formatting. One implementation (SPEC.md §8.5).

The 2026-06-11 audit found `to_date` defined in three scripts; this is the
survivor. All times are naive local Asia/Jerusalem (system TZ on the appliance).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


def to_date(v) -> date | None:
    """Best-effort date. Accepts date/datetime cells, ISO strings (date or
    datetime — the engine stamps `Last Sent` as ISO datetime text since M2, and
    writes col D as ISO since Lane C), and the he-IL DD/MM/YYYY render (humans
    type it; the API returns it for a real date cell — SPEC §6.1 col D). None
    when unparseable — callers skip + report, never raise (data-hygiene)."""
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
        # ISO datetime text ("2026-06-12T07:30:00") — gspread returns strings.
        dt = to_datetime(s)
        return dt.date() if dt else None
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


# Hebrew weekday letters, Sunday-first (DESIGN.md §6: dates as "יום ג׳ 17/6").
# Python weekday(): Mon=0 … Sun=6.
HEBREW_WEEKDAY = {6: "א׳", 0: "ב׳", 1: "ג׳", 2: "ד׳", 3: "ה׳", 4: "ו׳", 5: "ש׳"}


def fmt_date_he(d: date | None) -> str:
    """יום ו׳ 12/6 — WhatsApp digest header style (DESIGN.md §6)."""
    if not d:
        return ""
    return f"יום {HEBREW_WEEKDAY[d.weekday()]} {d.day}/{d.month}"


# ---------------------------------------------------------------------------
# Recurrence bump (SPEC.md §7.1) — the ONE implementation; the dashboard's
# bumpDate() in app.js mirrors these rules and the two must not diverge.
# ---------------------------------------------------------------------------
_MONTHS_PER = {"Monthly": 1, "Quarterly": 3, "Yearly": 12}
_DAYS_IN = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
            7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def _last_day(year: int, month: int) -> int:
    if month == 2 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        return 29
    return _DAYS_IN[month]


def add_months(d: date, months: int) -> tuple[date, bool]:
    """d + months, clamped to the last day of the target month when the day
    doesn't exist there (Feb-29 → Feb-28, Jan-31 +1mo → Feb-28/29). Returns
    (new_date, clamped) — clamped dates get flagged for review (SPEC §7.1)."""
    y, m = divmod((d.year * 12 + d.month - 1) + months, 12)
    m += 1
    last = _last_day(y, m)
    if d.day > last:
        return date(y, m, last), True
    return date(y, m, d.day), False


def bump_due(due: date, recurrence: str) -> tuple[date | None, bool]:
    """Next due date for a completed recurring reminder. Returns
    (new_due, clamped); new_due is None when the recurrence isn't bumpable
    (One-off, Custom, unknown) — the caller flags those for review instead
    of guessing a period."""
    rec = (recurrence or "").strip()
    if rec == "Weekly":
        return due + timedelta(days=7), False
    if rec in _MONTHS_PER:
        return add_months(due, _MONTHS_PER[rec])
    return None, False
