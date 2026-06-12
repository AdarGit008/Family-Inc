"""
Family inc. — ILS formatting. One implementation (SPEC.md §8.5: ILS only,
`₪{n:,}` in Python; legacy USD figures were restated in ILS in the Sheet).
"""
from __future__ import annotations


def fmt_money(n) -> str:
    """₪1,234 · sign-aware · '—' for missing · echoes non-numeric junk back
    (data-hygiene lines surface it; we never raise on a Sheet value)."""
    if n is None:
        return "—"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    sign = "-" if n < 0 else ""
    return f"{sign}₪{abs(n):,.0f}"


def pct(num, denom) -> float | None:
    """num/denom, None when denominator is falsy (no division-by-zero noise)."""
    if not denom:
        return None
    return num / denom
