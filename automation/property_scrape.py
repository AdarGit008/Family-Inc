"""
Family inc. — property-listing scraper (SPEC.md §12.1, M5; unfrozen D-034).

Active house search. Loads saved-search URLs (Yad2 primary, Madlan optional)
from /etc/family-inc/property_searches.json, renders each with headless
Chromium, extracts listing cards, diffs `listing_id` against the last-seen set
at /var/lib/family-inc/property/seen.json, appends NEW listings to the
Property-Listings tab via lib/sheet, and writes a "🏠 דירות חדשות" section that
daily_digest.py folds into the 07:30 morning message.

Delivery is SILENT (SPEC §12.1): new listings never fire an alert and never
touch the 2/day budget — property is not critical-safety (briefings >
notifications, §3 principle 4). A scrape error or anti-bot block fails LOUD via
the systemd OnFailure fail-flag, which the next delivered digest reports
(§9/§10.2) — never a silent miss.

Separation of concerns (so the test suite needs no browser):
  fetch_html()     — the ONLY Playwright user; imported lazily; VPS-only in
                     practice. Tests never call it.
  parse_listings() — pure: HTML str -> [Listing]; portal dispatch; unit-tested
                     against tests/fixtures/*.html. Detects anti-bot pages and
                     raises BlockedError (fail loud); a real-but-empty result
                     page returns [] (not an error).
  select_new / persist_new / build_digest_section — pure diff + lib/sheet
                     append (D-016: the only Sheet writer) + DESIGN-§6 copy.

MOCK MODE out-of-the-box: with no searches config and no --html, it loads a
small sample of listings, prints "RUNNING IN MOCK MODE", and exercises the full
diff -> (persist skipped, no live Sheet) -> digest path.

Run:
  python3 automation/property_scrape.py                       # mock
  python3 automation/property_scrape.py --dry-run
  python3 automation/property_scrape.py --html page.html --portal yad2
  python3 automation/property_scrape.py --as-of 2026-06-16
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/property_scrape.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from automation import templates as T
from automation.lib import config as cfg
from automation.lib import sheet

log = logging.getLogger("property")

PORTALS = ("yad2", "madlan")
PORTAL_BASE = {
    "yad2": "https://www.yad2.co.il",
    "madlan": "https://www.madlan.co.il",
}

# Landing-page signatures of an anti-bot wall (Yad2 fronts Cloudflare; Madlan
# has used PerimeterX). Matching any of these on a fetched page means we were
# challenged, not served listings — fail loud rather than diff an empty set and
# silently "lose" every listing. Lowercased substring match.
BLOCK_SIGNATURES = (
    "just a moment",            # Cloudflare interstitial
    "/cdn-cgi/challenge",       # Cloudflare challenge platform
    "cf-chl-",                  # Cloudflare challenge token
    "attention required",       # Cloudflare block
    "captcha",
    "px-captcha", "perimeterx", "_px",   # PerimeterX
    "are you a robot", "אימות אנושי", "אימות אבטחה",
)


class ScrapeError(RuntimeError):
    """A portal fetch/parse failed — the run reports it and exits non-zero so
    the systemd OnFailure fail-flag fires (§10.2)."""


class BlockedError(ScrapeError):
    """The fetched page is an anti-bot challenge, not a results page (§12.1)."""


# ---------------------------------------------------------------------------
# Listing model
# ---------------------------------------------------------------------------
@dataclass
class Listing:
    listing_id: str
    portal: str
    price_ils: Optional[int] = None
    rooms: Optional[float] = None
    size_sqm: Optional[int] = None
    location: str = ""
    url: str = ""
    first_seen: str = ""          # ISO-T, stamped when first selected as NEW

    def to_row(self) -> dict:
        """A Property-Listings row (SPEC §12.1). `status` starts 'new' and is
        thereafter human-edited in the Sheet — the scraper never overwrites it
        (append-only, no row updates)."""
        return {
            "listing_id": self.listing_id,
            "portal": self.portal,
            "first_seen": self.first_seen,
            "price_ils": self.price_ils if self.price_ils is not None else "",
            "rooms": _fmt_rooms(self.rooms),
            "size_sqm": self.size_sqm if self.size_sqm is not None else "",
            "location": self.location,
            "url": self.url,
            "status": "new",
        }


# ---------------------------------------------------------------------------
# Saved-search config (/etc/family-inc/property_searches.json — personal)
# ---------------------------------------------------------------------------
def load_searches(path: Path) -> list[dict]:
    """[{portal, url, label?}, …]. Missing file → [] (+warn). Entries with an
    unknown portal or no url are skipped loudly — a typo must not silently drop
    a whole search."""
    if not path.exists():
        log.warning("no searches config at %s — nothing to scrape", path)
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise ScrapeError(f"unreadable searches config {path}: {e}") from e
    raw = data.get("searches", data) if isinstance(data, dict) else data
    out = []
    for entry in raw or []:
        portal = str(entry.get("portal", "")).strip().lower()
        url = str(entry.get("url", "")).strip()
        if portal not in PORTALS or not url:
            log.warning("skipping bad search entry: %r", entry)
            continue
        out.append({"portal": portal, "url": url,
                    "label": str(entry.get("label", "")).strip()})
    return out


# ---------------------------------------------------------------------------
# Fetch — the ONLY Playwright user. Lazily imported so the suite (and any
# creds-less run) never needs a browser. VPS-only in practice.
# ---------------------------------------------------------------------------
_USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch_html(url: str, timeout_s: int = cfg.PROPERTY_FETCH_TIMEOUT_S) -> str:
    """Render `url` with headless Chromium and return the DOM HTML. Raises
    ScrapeError on a missing browser or a timeout — anti-bot detection happens
    later in parse_listings (a challenge page still returns HTML)."""
    try:
        from playwright.sync_api import TimeoutError as PWTimeout  # noqa: N814
        from playwright.sync_api import sync_playwright
    except ImportError as e:                       # pragma: no cover (VPS-only)
        raise ScrapeError(
            "playwright is not installed — the property unit runs via "
            "`uv run --with playwright`; for a local fetch: "
            "`uv run --with playwright python -m playwright install chromium`"
        ) from e
    with sync_playwright() as p:                   # pragma: no cover (VPS-only)
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context(
                user_agent=_USER_AGENT,
                locale="he-IL",
                viewport={"width": 1366, "height": 900},
            ).new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_s * 1000)
            except PWTimeout:
                pass  # network may never idle on ad-heavy pages; DOM is enough
            return page.content()
        except PWTimeout as e:
            raise ScrapeError(f"timeout loading {url}") from e
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Parse — pure HTML -> [Listing]. Robust to portal markup churn: pull the
# embedded JSON state (both portals are Next.js-class apps that ship listings
# as JSON) and walk it for listing-shaped objects, rather than chasing CSS
# classes that change weekly. The key maps below are the one place to retune
# against live HTML (a `# verify-live` seam, not a guess baked through the code).
# ---------------------------------------------------------------------------
_ID_KEYS = ("listing_id", "listingid", "id", "token", "linktoken",
            "ordernum", "adnumber", "orderid")
_PRICE_KEYS = ("price", "price_value", "pricevalue", "amount")
_ROOMS_KEYS = ("rooms", "room", "rooms_count", "roomscount", "numberofrooms",
               "rooms_text")
_SIZE_KEYS = ("square_meters", "squaremeter", "squaremeters", "size",
              "area", "builtarea", "square_meter")
_LOC_KEYS = ("address", "neighborhood", "neighbourhood", "city", "cityname",
             "street", "streetname", "location")   # NOT "title" — see _looks_like_listing
_URL_KEYS = ("url", "link", "canonicalurl", "page_url", "pageurl")

_SCRIPT_JSON_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_SCRIPT_ANY_JSON_RE = re.compile(
    r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', re.DOTALL)


def detect_block(html: str) -> bool:
    low = (html or "").lower()
    return any(sig in low for sig in BLOCK_SIGNATURES)


def _embedded_json(html: str) -> list:
    """Every JSON blob worth walking: the __NEXT_DATA__ payload first, then any
    other application/json <script> (Madlan ships an Apollo cache that way).
    The two regexes overlap on the __NEXT_DATA__ script, so dedup identical raw
    bodies before parsing — parse each blob once."""
    blobs, seen_raw = [], set()
    for rx in (_SCRIPT_JSON_RE, _SCRIPT_ANY_JSON_RE):
        for m in rx.finditer(html or ""):
            raw = m.group(1).strip()
            if raw in seen_raw:
                continue
            seen_raw.add(raw)
            try:
                blobs.append(json.loads(raw))
            except ValueError:
                continue
    return blobs


def _norm_keys(d: dict) -> dict:
    """Lowercased-key view for tolerant lookups (portals mix camel/snake)."""
    return {str(k).lower(): v for k, v in d.items()}


def _first(low: dict, keys) -> object:
    for k in keys:
        v = low.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def _looks_like_listing(low: dict) -> bool:
    # Require an id, a NUMERIC price, and at least one physical attribute. A
    # non-numeric price (e.g. "חבילת פרימיום") marks a promo/upsell block, and
    # `title` is deliberately NOT a qualifier (it's only a display fallback for
    # location) — so SEO/promo objects carrying just id+title don't slip in as
    # phantom listings.
    if _first(low, _ID_KEYS) is None or _to_int(_first(low, _PRICE_KEYS)) is None:
        return False
    return (_first(low, _ROOMS_KEYS) is not None
            or _first(low, _SIZE_KEYS) is not None
            or _first(low, _LOC_KEYS) is not None)


def _walk(obj, found: list, seen_ids: set, depth: int = 0) -> None:
    if depth > 30:
        return
    if isinstance(obj, dict):
        low = _norm_keys(obj)
        if _looks_like_listing(low):
            lid = _to_id(_first(low, _ID_KEYS))
            if lid and lid not in seen_ids:
                seen_ids.add(lid)
                found.append((lid, low))
        for v in obj.values():
            _walk(v, found, seen_ids, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, found, seen_ids, depth + 1)


def _to_id(v) -> str:
    return re.sub(r"\s+", "", str(v)) if v not in (None, "") else ""


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    digits = re.sub(r"[^\d]", "", str(v))
    return int(digits) if digits else None


def _to_rooms(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"\d+(?:\.\d+)?", str(v))
    return float(m.group()) if m else None


def _compose_location(low: dict) -> str:
    parts, seen = [], set()
    for k in ("street", "streetname", "address", "neighborhood",
              "neighbourhood", "city", "cityname"):
        v = low.get(k)
        if isinstance(v, dict):
            v = _norm_keys(v).get("text") or _norm_keys(v).get("name")
        v = str(v).strip() if v not in (None, "") else ""
        if v and v not in seen:
            seen.add(v)
            parts.append(v)
    if not parts:
        t = low.get("title")
        return str(t).strip() if t else ""
    return ", ".join(parts[:2])


def _abs_url(raw, portal: str) -> str:
    if not raw:
        return ""
    u = str(raw).strip()
    if u.startswith("http"):
        return u
    return PORTAL_BASE.get(portal, "").rstrip("/") + "/" + u.lstrip("/")


def _normalize(low: dict, portal: str) -> Optional[Listing]:
    lid = _to_id(_first(low, _ID_KEYS))
    if not lid:
        return None
    return Listing(
        listing_id=f"{portal}:{lid}",
        portal=portal,
        price_ils=_to_int(_first(low, _PRICE_KEYS)),
        rooms=_to_rooms(_first(low, _ROOMS_KEYS)),
        size_sqm=_to_int(_first(low, _SIZE_KEYS)),
        location=_compose_location(low),
        url=_abs_url(_first(low, _URL_KEYS), portal),
    )


def parse_listings(html: str, portal: str) -> list[Listing]:
    """HTML -> [Listing]. Raises BlockedError on an anti-bot page; returns []
    on a genuine empty-results page (both are §12.1 requirements)."""
    portal = (portal or "").lower()
    if detect_block(html):
        raise BlockedError(f"{portal}: anti-bot challenge page (no listings served)")
    found: list = []
    seen_ids: set = set()
    for blob in _embedded_json(html):
        _walk(blob, found, seen_ids)
    out = []
    for _lid, low in found:
        listing = _normalize(low, portal)
        if listing is not None:
            out.append(listing)
    return out


# ---------------------------------------------------------------------------
# Seen-set persistence (the diff key — SPEC §12.1)
# ---------------------------------------------------------------------------
def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        log.warning("unreadable seen-set %s — treating as empty", path)
        return set()
    return {str(x) for x in (data.get("listing_ids", []) if isinstance(data, dict)
                             else data)}


def save_seen(path: Path, ids: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"updated_at": datetime.now().isoformat(timespec="seconds"),
         "listing_ids": sorted(ids)}, ensure_ascii=False, indent=1),
        encoding="utf-8")


def select_new(listings: list[Listing], seen: set[str],
               now: Optional[datetime] = None) -> list[Listing]:
    """Listings whose id is not in `seen`, de-duplicated within the batch,
    each stamped first_seen=now. Order preserved (first occurrence wins)."""
    now = now or datetime.now()
    stamp = now.isoformat(timespec="seconds")
    out, batch = [], set()
    for li in listings:
        if li.listing_id in seen or li.listing_id in batch:
            continue
        batch.add(li.listing_id)
        li.first_seen = stamp
        out.append(li)
    return out


# ---------------------------------------------------------------------------
# Persist — append NEW rows to Property-Listings via lib/sheet (D-016: the only
# Sheet writer). Without a live backend (mock/dev) appends are skipped loudly —
# never written to the seed template (mirrors the summarizer).
# ---------------------------------------------------------------------------
def persist_new(new_listings: list[Listing], sheet_path: Optional[Path] = None,
                live_override: Optional[bool] = None) -> bool:
    live = sheet.is_live() if live_override is None else live_override
    if sheet_path is None and not live:
        print("(no live Sheet backend — Property-Listings rows NOT appended)")
        return False
    if not new_listings:
        return True
    # Belt-and-suspenders dedup: skip ids already on the tab even if the local
    # seen.json was lost/reset (the Sheet is the durable record).
    existing = {str(v).strip()
                for v in sheet.read_column(cfg.PROPERTY_LISTINGS_TAB,
                                           "listing_id", sheet_path)}
    rows = [li.to_row() for li in new_listings if li.listing_id not in existing]
    if rows:
        sheet.append_rows(cfg.PROPERTY_LISTINGS_TAB,
                          sheet.PROPERTY_LISTINGS_COLUMNS, rows, sheet_path)
    return True


# ---------------------------------------------------------------------------
# Digest section — "🏠 דירות חדשות", silent, folded into the 07:30 message by
# daily_digest.assemble (DESIGN §6 copy in templates.py, [Shanee review]).
# ---------------------------------------------------------------------------
def _fmt_rooms(rooms) -> str:
    if rooms in (None, ""):
        return ""
    try:
        r = float(rooms)
    except (TypeError, ValueError):
        return str(rooms)
    return str(int(r)) if r.is_integer() else str(r)


def _format_item(li: Listing) -> str:
    price = f"{li.price_ils:,}" if li.price_ils is not None else "?"
    rooms = T.PROPERTY_ROOMS.format(rooms=_fmt_rooms(li.rooms)) if li.rooms else ""
    size = T.PROPERTY_SIZE.format(size=li.size_sqm) if li.size_sqm else ""
    return T.PROPERTY_ITEM.format(
        location=li.location or "דירה", price=price,
        rooms=rooms, size=size, portal=li.portal)


def build_digest_section(new_listings: list[Listing],
                         max_items: int = cfg.PROPERTY_MAX_PER_DIGEST) -> str:
    """The morning section, or "" when there's nothing new (so the digest
    fold-in adds nothing on a quiet day). Cheapest first; overflow → a
    'more in the dashboard' line (reusing the reminders copy)."""
    if not new_listings:
        return ""
    ordered = sorted(new_listings,
                     key=lambda li: (li.price_ils is None,
                                     li.price_ils or 0, li.listing_id))
    lines = [T.PROPERTY_SECTION_HEAD]
    for li in ordered[:max_items]:
        lines.append(_format_item(li))
    extra = len(ordered) - max_items
    if extra > 0:
        lines.append(T.DIGEST_MORE_IN_DASHBOARD.format(n=extra))
    return "\n".join(lines)


def write_digest_file(section: str, today: date,
                      briefings_dir: Optional[Path] = None) -> Optional[Path]:
    """Write the section to Briefings/property_listings_{date}.md (the file
    daily_digest reads). Nothing new → no file → the digest stays silent."""
    if not section.strip():
        return None
    briefings_dir = briefings_dir or cfg.BRIEFINGS_DIR
    briefings_dir.mkdir(parents=True, exist_ok=True)
    p = briefings_dir / f"property_listings_{today.isoformat()}.md"
    p.write_text(section.rstrip() + "\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Mock data — a tiny sample so the script runs with no config and no browser
# (generic placeholder listings — no personal saved-search criteria).
# ---------------------------------------------------------------------------
MOCK_LISTINGS = [
    Listing("yad2:mock-1", "yad2", 1_850_000, 4, 92, "הרצליה", ""),
    Listing("yad2:mock-2", "yad2", 2_300_000, 5, 120, "רעננה, מרכז", ""),
    Listing("madlan:mock-3", "madlan", 1_690_000, 3.5, 78, "כפר סבא", ""),
]


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
@dataclass
class RunResult:
    all_listings: list[Listing] = field(default_factory=list)
    new_listings: list[Listing] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    is_mock: bool = False
    digest_path: Optional[Path] = None


def gather(searches: list[dict], html: Optional[str], portal: Optional[str],
           errors: list[str]) -> tuple[list[Listing], bool]:
    """Collect listings from (a) an explicit --html fixture, (b) the configured
    saved searches via headless Chromium, or (c) the mock sample. A per-URL
    block/error is recorded in `errors` and the other URLs still run — one dead
    portal must not suppress the rest; the run exits non-zero at the end."""
    if html is not None:
        return parse_listings(html, portal or "yad2"), False
    if not searches:
        print("RUNNING IN MOCK MODE — no searches config; using sample listings")
        return list(MOCK_LISTINGS), True
    collected: list[Listing] = []
    for s in searches:
        try:
            page_html = fetch_html(s["url"])
            collected.extend(parse_listings(page_html, s["portal"]))
        except Exception as e:   # noqa: BLE001 — isolate ANY per-URL browser
            # fault (block, launch crash, MemoryMax kill, navigation error), so
            # one flaky portal can't drop the others' listings; the run still
            # exits non-zero at the end → fail loud (OnFailure, §10.2).
            errors.append(f"{s['portal']} {s.get('label') or s['url']}: {e}")
            log.error("scrape failed: %s", e)
    return collected, False


def run(searches_path: Optional[Path] = None, state_path: Optional[Path] = None,
        today: Optional[date] = None, dry_run: bool = False,
        sheet_path: Optional[Path] = None, html: Optional[str] = None,
        portal: Optional[str] = None,
        briefings_dir: Optional[Path] = None) -> RunResult:
    today = today or date.today()
    state_path = state_path or cfg.PROPERTY_SEEN_FILE
    searches = [] if html is not None else load_searches(
        searches_path or cfg.PROPERTY_SEARCHES_FILE)

    res = RunResult()
    all_listings, res.is_mock = gather(searches, html, portal, res.errors)
    res.all_listings = all_listings

    seen = load_seen(state_path)
    res.new_listings = select_new(all_listings, seen, _run_now(today))

    print(f"\nFound {len(all_listings)} listing(s) "
          f"({'MOCK' if res.is_mock else 'live'}) · "
          f"{len(res.new_listings)} new · {len(res.errors)} error(s)")
    for li in res.new_listings:
        print(f"  NEW {li.listing_id}: {_format_item(li)}")

    section = build_digest_section(res.new_listings)
    if section:
        print("\n" + section)

    if dry_run:
        print("(dry-run — no Sheet write, no seen-set update, no digest file)")
    elif res.is_mock and sheet_path is None and sheet.is_live():
        # D-038 safety: MOCK sample data must NEVER reach the live Sheet or the
        # morning digest. Reaching here on the appliance means
        # /etc/family-inc/property_searches.json is missing — fail loud (systemd
        # OnFailure → fail-flag → next digest reports it) so the operator fixes
        # it, rather than silently appending rows like yad2:mock-1 to the tab.
        raise ScrapeError(
            "MOCK mode but a live Sheet is configured — "
            "property_searches.json is missing; refusing to write sample data")
    else:
        persisted = persist_new(res.new_listings, sheet_path)
        # Advance the seen-set ONLY when the rows were durably recorded. With no
        # live backend the rows are skipped — leaving seen untouched keeps these
        # listings "new" so a later live run still lands them. A seen-set that
        # runs ahead of the Sheet (e.g. a smoke test or the timer firing before
        # FAMILY_INC_SHEET_ID is in place) would silently lose a day's listings.
        if persisted:
            save_seen(state_path, seen | {li.listing_id for li in all_listings})
        res.digest_path = write_digest_file(section, today, briefings_dir)
        if res.digest_path:
            print(f"wrote {res.digest_path}")

    if res.errors:
        # Fail loud AFTER persisting the successes: the systemd OnFailure hook
        # appends to logs/fail.flag and the next digest reports it (§10.2).
        raise ScrapeError("; ".join(res.errors))
    return res


def _run_now(today: date) -> datetime:
    return datetime.now() if today == date.today() \
        else datetime.combine(today, datetime.min.time())


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--searches", help="path to property_searches.json")
    ap.add_argument("--state", help="path to seen.json (last-seen listing ids)")
    ap.add_argument("--html", help="parse a saved HTML file instead of fetching")
    ap.add_argument("--portal", choices=PORTALS, help="portal for --html")
    ap.add_argument("--as-of", help="YYYY-MM-DD, defaults to today")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse + print, write nothing")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    html = Path(args.html).read_text(encoding="utf-8") if args.html else None
    run(searches_path=Path(args.searches) if args.searches else None,
        state_path=Path(args.state) if args.state else None,
        today=today, dry_run=args.dry_run, html=html, portal=args.portal)


if __name__ == "__main__":
    main()
