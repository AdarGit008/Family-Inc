"""
Family inc. — Hebcal client

Thin wrapper around Hebcal's JSON endpoints for Shabbat candle-lighting /
havdalah times and chag (festival) windows.

The geoname id lives in lib/config.py (nearest metro to home — Hebcal has no
entry for the family's town, and the coastal zman matches to ~1 minute).

Endpoints used:
  - Shabbat:  https://www.hebcal.com/shabbat/?cfg=json&geonameid=…&M=on
  - Calendar: https://www.hebcal.com/hebcal?v=1&cfg=json&maj=on&min=on&mod=on
              &nx=on&year=now&month=x&ss=on&mf=on&c=on&geo=geoname&geonameid=…

Cache: automation/cache/hebcal_cache.json — keyed by ISO week / month
window with a 24h TTL so we don't hammer the API.

Public API:
  shabbat_times(date=None) -> dict
  is_chag(date)           -> bool
  chagim_in_range(start, end) -> list[dict]

Run modes:
  python3 automation/hebcal_client.py   # smoke test: this Shabbat + 30d chagim
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/hebcal_client.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests

from automation.lib import config

CACHE_DIR = config.CACHE_DIR
CACHE_PATH = CACHE_DIR / "hebcal_cache.json"
TTL_SECONDS = config.HEBCAL_TTL_SECONDS
GEONAME_ID = config.HEBCAL_GEONAME_ID

SHABBAT_URL = "https://www.hebcal.com/shabbat/"
HEBCAL_URL = "https://www.hebcal.com/hebcal"

log = logging.getLogger("hebcal")

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

def _save_cache(cache: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")

def _cache_get(key: str) -> Optional[dict]:
    cache = _load_cache()
    entry = cache.get(key)
    if not entry:
        return None
    ts = entry.get("_fetched_at", 0)
    if (datetime.now(timezone.utc).timestamp() - ts) > TTL_SECONDS:
        return None
    return entry.get("data")

def _cache_put(key: str, data: dict) -> None:
    cache = _load_cache()
    cache[key] = {"_fetched_at": datetime.now(timezone.utc).timestamp(), "data": data}
    _save_cache(cache)

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
def _fetch_shabbat(d: date) -> dict:
    params = {"cfg": "json", "geonameid": GEONAME_ID, "M": "on", "gy": d.year, "gm": d.month, "gd": d.day}
    r = requests.get(SHABBAT_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def _fetch_hebcal_month(year: int, month: int) -> dict:
    params = {
        "v": 1, "cfg": "json", "maj": "on", "min": "on", "mod": "on",
        "nx": "on", "year": year, "month": month, "ss": "on", "mf": "on",
        "c": "on", "geo": "geoname", "geonameid": GEONAME_ID,
    }
    r = requests.get(HEBCAL_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def shabbat_times(d: Optional[date] = None) -> dict:
    """Return {candle_lighting, havdalah, parasha} for the Shabbat of the
    week containing `d` (Israel time strings, ISO 8601)."""
    d = d or date.today()
    # ISO week as cache key: same Shabbat for any day in that week
    iso_year, iso_week, _ = d.isocalendar()
    key = f"shabbat:{iso_year}-W{iso_week:02d}"
    cached = _cache_get(key)
    if cached:
        return cached

    try:
        payload = _fetch_shabbat(d)
    except requests.RequestException as e:
        log.warning("hebcal fetch failed (%s) — returning stub", e)
        return {"candle_lighting": None, "havdalah": None, "parasha": None,
                "_stub": True, "_reason": str(e)}

    out = {"candle_lighting": None, "havdalah": None, "parasha": None}
    for item in payload.get("items", []):
        cat = item.get("category")
        if cat == "candles" and not out["candle_lighting"]:
            out["candle_lighting"] = item.get("date")
        elif cat == "havdalah" and not out["havdalah"]:
            out["havdalah"] = item.get("date")
        elif cat == "parashat" and not out["parasha"]:
            out["parasha"] = item.get("hebrew") or item.get("title")
    _cache_put(key, out)
    return out

def chagim_in_range(start: date, end: date) -> list[dict]:
    """List chagim (major / minor / modern holidays) overlapping [start, end]."""
    months_needed = set()
    cur = date(start.year, start.month, 1)
    while cur <= end:
        months_needed.add((cur.year, cur.month))
        # next month
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)

    holidays: list[dict] = []
    for y, m in sorted(months_needed):
        key = f"hebcal:{y}-{m:02d}"
        data = _cache_get(key)
        if data is None:
            try:
                data = _fetch_hebcal_month(y, m)
                _cache_put(key, data)
            except requests.RequestException as e:
                log.warning("hebcal month fetch failed %s-%02d: %s", y, m, e)
                continue
        for item in data.get("items", []):
            if item.get("category") not in {"holiday", "roshchodesh"}:
                continue
            try:
                d = datetime.fromisoformat(item["date"]).date()
            except (KeyError, ValueError):
                continue
            if start <= d <= end:
                holidays.append({
                    "date": d.isoformat(),
                    "title": item.get("title"),
                    "hebrew": item.get("hebrew"),
                    "subcat": item.get("subcat"),
                    "yomtov": item.get("yomtov", False),
                })
    holidays.sort(key=lambda h: h["date"])
    return holidays

def is_chag(d: date) -> bool:
    """True if `d` is a yom-tov (work-forbidden chag) in Israel."""
    chagim = chagim_in_range(d, d)
    return any(h.get("yomtov") for h in chagim)

# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    today = date.today()
    print(f"Shabbat times around {today.isoformat()} (geoname {GEONAME_ID}):")
    st = shabbat_times(today)
    for k, v in st.items():
        print(f"  {k}: {v}")
    print(f"\nChagim in next 30 days ({today} → {today + timedelta(days=30)}):")
    chs = chagim_in_range(today, today + timedelta(days=30))
    if not chs:
        print("  (none)")
    for c in chs:
        flag = " [yom tov]" if c.get("yomtov") else ""
        print(f"  {c['date']}  {c.get('title','?')}{flag}")
