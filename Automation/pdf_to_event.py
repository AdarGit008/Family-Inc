"""
Family inc. — PDF / image → calendar events (Ohai-style)

Takes a PDF or image (kindergarten newsletter, doctor referral, party
invite, etc.) and calls Claude multimodal to extract calendar events
into a CSV that can be merged into the Calendars tab.

Output columns:
  title, datetime (ISO 8601), location, who, source_doc

Run modes:
  python pdf_to_event.py /path/to/file.pdf
  python pdf_to_event.py                  # smoke test: scans test_inputs/

If ANTHROPIC_API_KEY is missing OR the SDK is absent OR no test inputs
are present, the script prints a clear notice and exits cleanly — never
crashes.
"""
from __future__ import annotations
import argparse
import base64
import csv
import json
import logging
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
TEST_DIR = ROOT / "test_inputs"
OUT_CSV = ROOT / "events_extracted.csv"

log = logging.getLogger("pdf2event")

SYSTEM = (
    "You extract calendar events from documents (Hebrew or English). "
    "Return a JSON array. Each item must have keys exactly: "
    "title, datetime, location, who. "
    "datetime must be ISO 8601 in Israel local time (e.g. 2026-06-12T16:30). "
    "If no events found, return []. Output ONLY the JSON array."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode("ascii")

def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".pdf":  "application/pdf",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif":  "image/gif",
    }.get(suffix, "application/octet-stream")

def _parse_json_array(text: str) -> list[dict]:
    # Strip code fences if present
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        data = json.loads(t)
    except json.JSONDecodeError:
        # try to find the first [...] block
        m = re.search(r"\[.*\]", t, re.DOTALL)
        if not m: return []
        try: data = json.loads(m.group(0))
        except json.JSONDecodeError: return []
    return data if isinstance(data, list) else []

# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def extract_events(path: Path) -> list[dict]:
    """Call Claude multimodal to extract events from one file."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        log.warning("RUNNING IN MOCK MODE — no ANTHROPIC_API_KEY; returning empty list for %s", path.name)
        return []
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed — cannot extract from %s", path.name)
        return []
    media = _media_type(path)
    if media == "application/pdf":
        content_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": media, "data": _b64(path)},
        }
    elif media.startswith("image/"):
        content_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media, "data": _b64(path)},
        }
    else:
        log.warning("unsupported media type %s for %s", media, path.name)
        return []
    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    content_block,
                    {"type": "text", "text": "Extract calendar events as JSON."},
                ],
            }],
        )
        text = msg.content[0].text if msg.content else ""
    except Exception as e:
        log.warning("Claude call failed for %s: %s", path.name, e)
        return []
    events = _parse_json_array(text)
    for e in events:
        e["source_doc"] = path.name
    return events

# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
FIELDS = ["title", "datetime", "location", "who", "source_doc"]

def write_csv(events: list[dict], out: Path) -> None:
    new_file = not out.exists()
    with out.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for e in events:
            row = {k: (e.get(k) or "") for k in FIELDS}
            w.writerow(row)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run(paths: list[Path]) -> Path | None:
    if not paths:
        print("no test inputs.")
        return None
    all_events = []
    for p in paths:
        if not p.exists():
            log.warning("missing: %s", p)
            continue
        ev = extract_events(p)
        print(f"{p.name}: {len(ev)} event(s)")
        for e in ev:
            print(f"  - {e.get('datetime','?')}  {e.get('title','?')}  @ {e.get('location','')}  ({e.get('who','')})")
        all_events.extend(ev)
    if all_events:
        write_csv(all_events, OUT_CSV)
        print(f"\nwrote {OUT_CSV} (+{len(all_events)} events)")
    return OUT_CSV if all_events else None

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help="path to PDF/image; omit for smoke test on test_inputs/")
    args = ap.parse_args()
    if args.file:
        run([Path(args.file)])
        return
    # smoke test
    if not TEST_DIR.exists():
        TEST_DIR.mkdir(exist_ok=True)
    inputs = sorted([p for p in TEST_DIR.iterdir()
                     if p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}])
    if not inputs:
        print("no test inputs.")
        sys.exit(0)
    run(inputs)

if __name__ == "__main__":
    main()
