"""
Family inc. — Pediatric milestones (Israel Tipat Halav schedule)

Given child birthdates, produce upcoming vaccines + Tipat Halav visits +
"things to celebrate" (CDC milestone watch-fors, positively framed).

Schedule: 2/4/6/12/18/24mo standard MOH series.
Visits: 2w, 1, 2, 4, 6, 9, 12, 18, 24, 36mo.

Outputs vaccines_due.csv (Reminders-tab ready) + per-kid console summary.
Run: python pediatric_milestones.py [--people CSV] [--as-of YYYY-MM-DD] [--window-days N]
"""
from __future__ import annotations
import argparse
import csv
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
OUT_CSV = ROOT / "vaccines_due.csv"
log = logging.getLogger("peds")

MOCK_PEOPLE = [
    {"name": "Kid A", "role": "child",  "birthdate": "2023-01-01", "kupah": "Maccabi"},
    {"name": "Kid B", "role": "child",  "birthdate": "2026-01-01", "kupah": "Maccabi"},
    {"name": "Adar",   "role": "parent", "birthdate": "1990-01-01", "kupah": "Maccabi"},
    {"name": "Shanee", "role": "parent", "birthdate": "1991-01-01", "kupah": "Maccabi"},
]

def _m(n: int) -> int: return int(n * 30.44)
def _w(n: int) -> int: return n * 7

# (age_days, kind, title)
VACCINES = [
    (_m(2),  "vaccine", "Hexa #1 (DTaP-IPV-Hib-HepB)"), (_m(2),  "vaccine", "Rotavirus #1"),
    (_m(2),  "vaccine", "PCV #1"), (_m(4),  "vaccine", "Hexa #2 (DTaP-IPV-Hib-HepB)"),
    (_m(4),  "vaccine", "Rotavirus #2"), (_m(4),  "vaccine", "PCV #2"),
    (_m(6),  "vaccine", "Hexa #3 (DTaP-IPV-Hib-HepB)"), (_m(6),  "vaccine", "Rotavirus #3"),
    (_m(6),  "vaccine", "PCV #3"), (_m(6),  "vaccine", "HepB #3"),
    (_m(12), "vaccine", "MMRV"), (_m(12), "vaccine", "HepA #1"),
    (_m(18), "vaccine", "DTaP-IPV-Hib #4"), (_m(18), "vaccine", "HepA #2"),
    (_m(24), "vaccine", "PCV booster"),
]
TIPAT_HALAV_VISITS = [
    (_w(2),  "visit", "Tipat Halav — 2-week check"), (_m(1),  "visit", "Tipat Halav — 1-month check"),
    (_m(2),  "visit", "Tipat Halav — 2-month check"), (_m(4),  "visit", "Tipat Halav — 4-month check"),
    (_m(6),  "visit", "Tipat Halav — 6-month check"), (_m(9),  "visit", "Tipat Halav — 9-month check"),
    (_m(12), "visit", "Tipat Halav — 12-month check"), (_m(18), "visit", "Tipat Halav — 18-month check"),
    (_m(24), "visit", "Tipat Halav — 24-month check"), (_m(36), "visit", "Tipat Halav — 36-month check"),
]

# CDC celebrate-watch-fors (two lines per band, positive framing)
CELEBRATE = [
    (_m(2),  "Social smiles + tracking faces — peak parent-payoff window"),
    (_m(2),  "Holds head up briefly during tummy time"),
    (_m(4),  "Babbles consonants; reaches for toys with both hands"),
    (_m(4),  "Laughs out loud — record it"),
    (_m(6),  "Sits with support; passes objects hand-to-hand"),
    (_m(6),  "Recognizes familiar people across the room"),
    (_m(9),  "Pulls to stand; plays peekaboo back"),
    (_m(9),  "Uses sounds like 'mama' / 'dada' non-specifically"),
    (_m(12), "First steps zone (anywhere 9-15 months is normal)"),
    (_m(12), "Waves bye-bye and points to wanted objects"),
    (_m(18), "Says 10+ words; follows one-step directions"),
    (_m(18), "Stacks 2-4 blocks; runs with confidence"),
    (_m(24), "Two-word phrases ('more milk'); parallel play with peers"),
    (_m(24), "Names body parts and familiar people in photos"),
    (_m(36), "Speaks in 3-word sentences; understands 'mine' / 'yours'"),
    (_m(36), "Pedals tricycle; draws a closed circle"),
]

# Load
def load_people(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        log.warning("RUNNING IN MOCK MODE — using built-in People list")
        return MOCK_PEOPLE
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))

def parse_bd(s: str) -> date | None:
    try: return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except (AttributeError, ValueError): return None

# Compute
def upcoming_for_child(name: str, bd: date, today: date, window_days: int) -> dict:
    end = today + timedelta(days=window_days)
    items = [{"date": bd + timedelta(days=a), "kind": k, "title": t}
             for a, k, t in VACCINES + TIPAT_HALAV_VISITS
             if today <= bd + timedelta(days=a) <= end]
    items.sort(key=lambda x: x["date"])
    age_days = (today - bd).days
    band = max((d for d in {c[0] for c in CELEBRATE} if d <= age_days + 30), default=None)
    celebrates = [c[1] for c in CELEBRATE if c[0] == band][:2] if band else []

    return {"name": name, "birthdate": bd, "age_days": age_days,
            "items": items, "celebrate": celebrates}

# Output
def write_reminders_csv(per_kid: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Title", "Domain", "Owner", "Due Date", "Lead Times",
                    "Recurrence", "Status", "Last Sent", "Channel", "Notes"])
        for kid in per_kid:
            for it in kid["items"]:
                w.writerow([f"{kid['name']} — {it['title']}", "Health", "Both",
                            it["date"].isoformat(), "14, 3", "One-off", "Pending",
                            "", "WhatsApp", f"Tipat Halav schedule for {kid['name']}"])

def print_summary(per_kid: list[dict], today: date) -> None:
    for kid in per_kid:
        y, mo = kid["age_days"] // 365, (kid["age_days"] % 365) // 30
        print(f"\n=== {kid['name']} (age ~{y}y {mo}m, born {kid['birthdate']}) ===")
        if kid["items"]:
            print("  Upcoming:")
            for it in kid["items"]:
                tag = "vax" if it["kind"] == "vaccine" else "visit"
                print(f"    {it['date'].isoformat()}  [{tag}]  {it['title']}")
        else:
            print("  No vaccines or Tipat Halav visits in the window.")
        if kid["celebrate"]:
            print("  Things to celebrate this month:")
            for c in kid["celebrate"]:
                print(f"    - {c}")

# Main
def run(people_csv: Path | None, today: date, window_days: int) -> Path:
    people = load_people(people_csv)
    per_kid = []
    for p in people:
        if (p.get("role") or "").lower() != "child":
            continue
        bd = parse_bd(p.get("birthdate", ""))
        if not bd: continue
        per_kid.append(upcoming_for_child(p["name"], bd, today, window_days))
    print_summary(per_kid, today)
    write_reminders_csv(per_kid, OUT_CSV)
    print(f"\nwrote {OUT_CSV} ({sum(len(k['items']) for k in per_kid)} rows)")
    return OUT_CSV

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--people", help="path to People CSV (name,role,birthdate,kupah)")
    ap.add_argument("--as-of", help="YYYY-MM-DD")
    ap.add_argument("--window-days", type=int, default=30)
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(Path(args.people) if args.people else None, today, args.window_days)

if __name__ == "__main__":
    main()
