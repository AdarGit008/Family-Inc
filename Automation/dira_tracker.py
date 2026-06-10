"""
Family inc. — Dira BeHanacha tender tracker

Polls https://www.dira.moch.gov.il/ for new affordable-housing lotteries
in the Northern District (מחוז הצפון) — Adar's eligible region — and
specifically flags Kiryat Tivon / ⟨town⟩ matches.

Real-world note: the dira.moch.gov.il site is a heavy JS SPA backed by
Government Procurement APIs. Hitting it directly with requests is best-
effort; if the layout shifts or we get a 4xx/5xx we fall back to a stub
text file so the user knows to check manually. We never crash.

Outputs:
  - dira_matches.csv      (one row per tender)
  - dira_stub.txt         (only when scrape fails — explains fallback)

Run:
  python dira_tracker.py
  python dira_tracker.py --region "צפון"
"""
from __future__ import annotations
import argparse
import csv
import logging
from datetime import date
from pathlib import Path

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore

ROOT = Path(__file__).parent
OUT_CSV = ROOT / "dira_matches.csv"
STUB_TXT = ROOT / "dira_stub.txt"

DIRA_URL = "https://www.dira.moch.gov.il/"
DEFAULT_REGION = "צפון"
TARGET_CITIES = ["קרית טבעון", "קריית טבעון", "⟨town⟩", "⟨town⟩", "טבעון"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.6",
}

log = logging.getLogger("dira")

# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def fetch_html(url: str = DIRA_URL) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        log.warning("dira fetch failed: %s", e)
        return None

# ---------------------------------------------------------------------------
# Parse — best-effort
# ---------------------------------------------------------------------------
def parse_tenders(html: str, region: str, cities: list[str]) -> list[dict]:
    """Look for any element whose text contains the region or target
    cities, and try to lift nearby context (heading text + the closest
    anchor href). The dira site changes its DOM frequently — this is
    intentionally permissive."""
    if BeautifulSoup is None:
        log.warning("beautifulsoup4 not installed — cannot parse")
        return []
    soup = BeautifulSoup(html, "html.parser")
    matches: list[dict] = []
    seen_titles = set()

    needles = [region] + cities
    for tag in soup.find_all(["a", "div", "li", "tr"]):
        txt = tag.get_text(" ", strip=True)
        if not txt or len(txt) > 400: continue
        if not any(n in txt for n in needles): continue
        title = txt[:200]
        if title in seen_titles: continue
        seen_titles.add(title)
        # try to grab the closest link
        href = None
        if tag.name == "a" and tag.get("href"):
            href = tag["href"]
        else:
            a = tag.find("a", href=True)
            if a: href = a["href"]
        is_target_city = any(c in txt for c in cities)
        matches.append({
            "title": title,
            "region": region,
            "is_target_city": is_target_city,
            "url": href or DIRA_URL,
            "found_on": date.today().isoformat(),
        })
    return matches

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_matches(matches: list[dict], out: Path) -> None:
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["title", "region", "is_target_city", "url", "found_on"])
        w.writeheader()
        for m in matches:
            w.writerow(m)

def write_stub(reason: str) -> None:
    STUB_TXT.write_text(
        "Family inc. — Dira BeHanacha tracker fallback\n"
        f"Reason: {reason}\n\n"
        "The automated scrape did not return parseable results.\n"
        "Manual fallback:\n"
        "  1. Open https://www.dira.moch.gov.il/\n"
        f"  2. Filter by מחוז הצפון, sort by date\n"
        f"  3. Look specifically for: {', '.join(TARGET_CITIES)}\n"
        "  4. Paste any new lotteries into the Goals tab under 'House — ⟨town⟩'.\n",
        encoding="utf-8",
    )

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run(region: str) -> Path | None:
    html = fetch_html()
    if html is None:
        write_stub("HTTP request failed")
        print(f"RUNNING IN MOCK MODE — wrote stub at {STUB_TXT}")
        return STUB_TXT
    matches = parse_tenders(html, region, TARGET_CITIES)
    if not matches:
        write_stub("no matches found / page structure may have changed")
        print(f"No matches parsed — wrote stub at {STUB_TXT}")
        return STUB_TXT
    write_matches(matches, OUT_CSV)
    target_hits = sum(1 for m in matches if m["is_target_city"])
    print(f"wrote {OUT_CSV} ({len(matches)} match(es), {target_hits} in target cities)")
    for m in matches[:10]:
        flag = " *TARGET*" if m["is_target_city"] else ""
        print(f"  - {m['title'][:80]}{flag}")
    if len(matches) > 10:
        print(f"  ... and {len(matches) - 10} more")
    return OUT_CSV

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default=DEFAULT_REGION)
    args = ap.parse_args()
    run(args.region)

if __name__ == "__main__":
    main()
