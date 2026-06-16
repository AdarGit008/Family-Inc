"""
Family inc. — Apify secondary data source for the property lane (SPEC §12.1, D-040).

SECONDARY / supplementary only. The on-box headless-Chromium scraper
(`property_scrape.fetch_html`, D-039) stays the PRIMARY source and is unchanged.
Apify is called per saved-search ONLY when the primary is blocked or returns
nothing (backup) or to fill specific missing fields on listings the primary did
return (gap-fill). On merge the primary always wins; Apify only adds listings
the primary missed and fills blanks (`property_scrape.merge_listings`).

Why it exists: Yad2 (Cloudflare) and Madlan (PerimeterX) serve anti-bot
challenge pages to the VPS's datacenter IP (D-039 verdict). Apify runs the
scrape from its own residential proxy pool, so it clears the wall the on-box
browser can't. This is a paid third party in the data path — the D-040 call
amends D-010's "₪0 marginal" to the §11 monthly ceiling and is governed by it.

This module is the ONLY Apify client. The network lives in `_run_actor()`
exactly like `fetch_html` is the only Playwright user — every other function is
pure given dataset items, so the test suite never touches the network.

Strict, fail-loud, never-invent (the D-040 contract — mirrors "fail loud,
degrade quiet", SPEC §3):
  - token absent when Apify is actually invoked        -> ApifyError (loud)
  - HTTP non-2xx / network error / 408 sync cap        -> ApifyError (loud)
  - a portal with no configured actor or input         -> ApifyError (loud;
                                                          never guess input)
  - a dataset item missing its id, or a present-but-    -> ApifyItemError, the
    corrupt (non-numeric) price/rooms/size               item is skipped AND the
                                                          error is collected and
                                                          surfaced (never a
                                                          silently dropped row,
                                                          never a coerced value)
  - a genuinely ABSENT optional field                  -> left empty (honest
                                                          absence, not invented)

Actors (config.PROPERTY_APIFY_ACTORS, D-040 picks):
  yad2   = amit123~yadscraper      — ingests Yad2 saved-search URLs directly
  madlan = swerve~madlan-scraper   — parametric (city/dealType/price/rooms)
The per-actor field maps below are the single `# verify-live` seam — retune them
against a real dataset item if a portal's schema drifts, not scattered through
the code.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from automation.lib import config as cfg

log = logging.getLogger("property.apify")


class ApifyError(RuntimeError):
    """Transport/config failure (no token, HTTP error, timeout, unknown portal,
    missing required actor input). Collected into the run's errors → the
    systemd OnFailure fail-flag fires (§10.2). Never swallowed."""


class ApifyItemError(ValueError):
    """A single dataset item is unusable (missing id, or a corrupt numeric).
    The item is skipped and the message collected — fail loud at the row level
    (SPEC §9 "bad row data"), never a silent drop, never an invented value."""


# ---------------------------------------------------------------------------
# Token / enablement
# ---------------------------------------------------------------------------
def token(env: Optional[dict] = None) -> str:
    """The Apify API token from the environment (loaded from
    /etc/family-inc/env on the appliance, §8.6). "" when unset."""
    cfg.load_env()
    src = env if env is not None else os.environ
    return (src.get(cfg.APIFY_TOKEN_ENV) or "").strip()


def is_configured(env: Optional[dict] = None) -> bool:
    """True when a token is present. Absent token = the whole Apify path is
    inert (primary-only), so the appliance is untouched until it's placed."""
    return bool(token(env))


# ---------------------------------------------------------------------------
# Network — the ONLY function that calls Apify. Lazily uses `requests` (already
# a core dep — hebcal/review). Never invoked by the test suite (monkeypatched).
# ---------------------------------------------------------------------------
def _run_actor(actor_id: str, payload: dict, *, api_token: str,
               timeout_s: int) -> list:
    """POST run-sync-get-dataset-items and return the dataset items (a list).
    Raises ApifyError on any non-2xx, the 408 sync-timeout cap, or a network
    fault — never returns partial/None on failure."""
    import requests  # local import keeps module import light; dep is core

    url = f"{cfg.APIFY_BASE_URL}/acts/{actor_id}/run-sync-get-dataset-items"
    try:
        resp = requests.post(
            url,
            params={"format": "json", "clean": "true"},
            json=payload,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=timeout_s,
        )
    except requests.RequestException as e:                 # pragma: no cover
        raise ApifyError(f"{actor_id}: network error: {e}") from e
    if resp.status_code == 408:
        raise ApifyError(
            f"{actor_id}: sync run exceeded {timeout_s}s (HTTP 408) — lower the "
            f"item/page cap or move this actor to the async run+poll path")
    if not (200 <= resp.status_code < 300):
        snippet = (resp.text or "")[:300]
        raise ApifyError(f"{actor_id}: HTTP {resp.status_code}: {snippet}")
    try:
        data = resp.json()
    except ValueError as e:
        raise ApifyError(f"{actor_id}: response was not JSON") from e
    if not isinstance(data, list):
        raise ApifyError(f"{actor_id}: expected a JSON array of dataset items, "
                         f"got {type(data).__name__}")
    return data


# ---------------------------------------------------------------------------
# Actor input — built per portal. NEVER guessed: a portal with no actor, or a
# parametric portal with no input block, fails loud (no invented search).
# ---------------------------------------------------------------------------
def _proxy_block() -> dict:
    return {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"],
            "apifyProxyCountry": "IL"}


def build_input(portal: str, search: dict, *, max_items: int,
                max_pages: int) -> dict:
    """Map a saved-search entry to the chosen actor's input.

    yad2 (amit123~yadscraper): URL-driven — reuse the entry's `url` (the same
      saved search the on-box primary fetches); pagination is automatic, capped
      by max_pages. An explicit `apify` block overrides if present.
    madlan (swerve~madlan-scraper): parametric — REQUIRES an `apify` block with
      at least {city, dealType}; the entry's `url` is for the primary only and
      is not understood by this actor, so we refuse to guess parameters.
    """
    override = search.get("apify")
    if override is not None and not isinstance(override, dict):
        raise ApifyError(f"{portal}: 'apify' must be an object, got "
                         f"{type(override).__name__}")

    if portal == "yad2":
        # Defaults (incl. the residential-IL proxy — the whole reason Apify
        # clears the wall) UNDER any override, so an override that tweaks one
        # param doesn't silently drop the proxy (review D-2).
        base = {"maxPagesPerSearch": max_pages, "proxy": _proxy_block()}
        url = str(search.get("url", "")).strip()
        if url:
            base["start_urls"] = [{"url": url}]
        merged = {**base, **override} if override else base
        if not merged.get("start_urls"):
            raise ApifyError("yad2: search has no url and no 'apify.start_urls' — "
                             "nothing to send to the actor")
        return merged

    if portal == "madlan":
        if not override:
            raise ApifyError(
                "madlan: swerve~madlan-scraper is parametric (city/dealType/"
                "price/rooms) and does not accept a URL — add an 'apify' block "
                "to this search in property_searches.json (see the example). "
                "Refusing to guess parameters from the url.")
        if not str(override.get("city", "")).strip() \
                or not str(override.get("dealType", "")).strip():
            raise ApifyError("madlan: the 'apify' block must set at least "
                             "'city' and 'dealType'")
        payload = dict(override)
        payload.setdefault("maxItems", max_items)
        return payload

    raise ApifyError(f"unknown portal {portal!r} — no Apify actor configured")


# ---------------------------------------------------------------------------
# Strict field coercion — present-but-corrupt raises; absent is honest None.
# ---------------------------------------------------------------------------
def _str(v) -> str:
    return str(v).strip() if v not in (None, "") else ""


def _num(item: dict, key: str, *, as_int: bool, field: str):
    """A numeric field. Absent/None/"" -> None (honest absence). A JSON number or
    clean numeric string ("1,850,000") -> parsed. A present non-numeric value or
    a NEGATIVE number -> ApifyItemError (corrupt, surfaced — never coerced or
    invented). A ZERO -> None: no real listing has a 0 price/rooms/size; 0 is the
    portals' "price on request" sentinel, so it's honest-absent, not a fake 0."""
    v = item.get(key)
    if v is None or v == "":
        return None
    if isinstance(v, bool):  # bool is an int subclass — guard it out explicitly
        raise ApifyItemError(f"corrupt {field}={v!r} (boolean, not a number)")
    if isinstance(v, (int, float)):
        num = float(v)
    else:
        s = str(v).strip().replace(",", "")
        if not re.fullmatch(r"\d+(?:\.\d+)?", s):
            raise ApifyItemError(f"corrupt {field}={v!r} (not numeric)")
        num = float(s)
    if num < 0:
        raise ApifyItemError(f"corrupt {field}={v!r} (negative)")
    if num == 0:
        return None
    return int(num) if as_int else float(num)


def _require_id(item: dict, key: str, portal: str) -> str:
    raw = item.get(key)
    rid = re.sub(r"\s+", "", str(raw)) if raw not in (None, "") else ""
    if not rid:
        raise ApifyItemError(f"{portal}: dataset item missing id field {key!r}")
    return rid


# ---------------------------------------------------------------------------
# Per-portal adapters — dataset item -> Listing. The ONE place schema lives.
# (verify-live: pin against a real run via `python -m automation.lib.apify ...`
# or a sample dataset item; field names below are the actors' documented output.)
# ---------------------------------------------------------------------------
def _adapt_yad2(item: dict):
    """amit123~yadscraper output (verify-live):
    item_id, item_url, price, rooms, square_meter, location, ..."""
    from automation.property_scrape import Listing  # lazy: avoids import cycle

    rid = _require_id(item, "item_id", "yad2")
    return Listing(
        listing_id=f"yad2:{rid}",
        portal="yad2",
        price_ils=_num(item, "price", as_int=True, field="yad2.price"),
        rooms=_num(item, "rooms", as_int=False, field="yad2.rooms"),
        size_sqm=_num(item, "square_meter", as_int=True, field="yad2.square_meter"),
        location=_str(item.get("location")),
        url=_str(item.get("item_url")),
    )


def _madlan_location(item: dict) -> str:
    parts, seen = [], set()
    for k in ("address", "neighbourhood", "cityHebrew", "city"):
        v = _str(item.get(k))
        if v and v not in seen:
            seen.add(v)
            parts.append(v)
    return ", ".join(parts[:2])


def _adapt_madlan(item: dict):
    """swerve~madlan-scraper output (verify-live):
    id, url, price, rooms, areaSqm, address, neighbourhood, cityHebrew, ..."""
    from automation.property_scrape import Listing  # lazy: avoids import cycle

    rid = _require_id(item, "id", "madlan")
    return Listing(
        listing_id=f"madlan:{rid}",
        portal="madlan",
        price_ils=_num(item, "price", as_int=True, field="madlan.price"),
        rooms=_num(item, "rooms", as_int=False, field="madlan.rooms"),
        size_sqm=_num(item, "areaSqm", as_int=True, field="madlan.areaSqm"),
        location=_madlan_location(item),
        url=_str(item.get("url")),
    )


_ADAPTERS = {"yad2": _adapt_yad2, "madlan": _adapt_madlan}


def adapt_items(portal: str, items: list) -> tuple[list, list[str]]:
    """Map dataset items to Listings. Returns (listings, item_errors): a bad
    item is skipped and its error collected (fail loud at the row level), never
    silently dropped. A non-dict item is itself an error, not a skip."""
    adapt = _ADAPTERS.get(portal)
    if adapt is None:
        raise ApifyError(f"unknown portal {portal!r} — no adapter")
    listings, errors = [], []
    for raw in items:
        if not isinstance(raw, dict):
            errors.append(f"{portal}: non-object dataset item {raw!r}")
            continue
        try:
            listings.append(adapt(raw))
        except ApifyItemError as e:
            errors.append(str(e))
    return listings, errors


# ---------------------------------------------------------------------------
# Public: fetch one saved-search's listings from Apify.
# ---------------------------------------------------------------------------
def fetch_listings(portal: str, search: dict, *, api_token: Optional[str] = None,
                   max_items: Optional[int] = None,
                   max_pages: Optional[int] = None,
                   timeout_s: Optional[int] = None,
                   runner=None) -> tuple[list, list[str]]:
    """Run the portal's actor for one saved search and return
    (listings, item_errors). Raises ApifyError on any transport/config fault
    (no token, unknown portal, missing required input, HTTP error) — fail loud.

    `runner` overrides `_run_actor` for tests so the network is never touched.
    """
    portal = (portal or "").lower()
    actor_id = cfg.PROPERTY_APIFY_ACTORS.get(portal)
    if not actor_id:
        raise ApifyError(f"no Apify actor configured for portal {portal!r}")

    tok = api_token if api_token is not None else token()
    if not tok:
        raise ApifyError(
            f"{cfg.APIFY_TOKEN_ENV} is not set — cannot call Apify for {portal} "
            f"(add it to /etc/family-inc/env). Refusing to proceed silently.")

    payload = build_input(
        portal, search,
        max_items=max_items or cfg.PROPERTY_APIFY_MAX_ITEMS,
        max_pages=max_pages or cfg.PROPERTY_APIFY_MAX_PAGES,
    )
    run = runner or _run_actor
    items = run(actor_id, payload, api_token=tok,
                timeout_s=timeout_s or cfg.PROPERTY_APIFY_TIMEOUT_S)
    listings, item_errors = adapt_items(portal, items)
    log.info("apify %s: %d item(s) -> %d listing(s), %d bad",
             portal, len(items), len(listings), len(item_errors))
    return listings, item_errors


# ---------------------------------------------------------------------------
# Once-per-day cost gate — PER SEARCH and PER KIND. Apify is priced per result;
# the on-box primary keeps its free 2×/day while Apify lands at most once a
# calendar day (the digest is morning-only, so a same-day second call buys the
# user nothing). Two INDEPENDENT budgets so a cheap GAP-FILL can never consume
# the load-bearing BACKUP's daily call and silently suppress a later
# blocked-primary backup (review CRITICAL); per-SEARCH so one search's backup
# never suppresses another's (review SHOULD-FIX #2). Marked ONLY after a durable
# Sheet write, so a failed call still lets the next run retry. Stamp shape:
#   {"backup": {<search_key>: "YYYY-MM-DD"}, "gapfill": {<search_key>: "..."}}
def load_run_stamp(stamp_path) -> dict:
    try:
        data = json.loads(stamp_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def ran_today(stamp: dict, kind: str, key: str, today) -> bool:
    return stamp.get(kind, {}).get(key) == today.isoformat()


def mark_run(stamp: dict, kind: str, key: str, today) -> None:
    stamp.setdefault(kind, {})[key] = today.isoformat()


def save_run_stamp(stamp_path, stamp: dict) -> None:
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(json.dumps(stamp, ensure_ascii=False, indent=1),
                          encoding="utf-8")
