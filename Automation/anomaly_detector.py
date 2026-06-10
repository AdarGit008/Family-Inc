"""
Family inc. — Finance anomaly detector

Flags: (1) subscription creep, (2) duplicate charges within 48h,
(3) amount drift >10% MoM, (4) category spike >2σ, (5) merchant
suffix drift. Expects CSV columns: date,vendor,amount,category.
Output: Briefings/anomalies_YYYY-MM-DD.json + console table.

Run: python anomaly_detector.py [--csv path] [--as-of YYYY-MM-DD]
Mocks a sample CSV if none provided.
"""
from __future__ import annotations
import argparse
import csv
import json
import logging
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from hebrew_categorizer import categorize

ROOT = Path(__file__).parent
BRIEFINGS_DIR = ROOT.parent / "Briefings"
SAMPLE_CSV = BRIEFINGS_DIR / "sample_transactions.csv"

log = logging.getLogger("anomaly")

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
MOCK_ROWS = [  # subscription creep + drift + dupes + suffix drift + spike + noise
    ("2026-03-04", "Netflix", -55.90, "Subscriptions"), ("2026-04-04", "Netflix", -55.90, "Subscriptions"),
    ("2026-05-04", "Netflix", -65.90, "Subscriptions"), ("2026-05-12", "פז", -310.00, "Fuel"),
    ("2026-05-13", "פז", -310.00, "Fuel"), ("2026-05-02", "שופרסל דיל", -412.30, "Groceries"),
    ("2026-05-09", "שופרסל אקספרס", -188.40, "Groceries"), ("2026-05-22", "שופרסל שלי", -301.10, "Groceries"),
    ("2026-05-25", "Best Buy", -2450.00, "Electronics"), ("2026-04-01", "רמי לוי", -650.00, "Groceries"),
    ("2026-05-01", "רמי לוי", -640.00, "Groceries"), ("2026-03-15", "Spotify", -19.90, "Subscriptions"),
    ("2026-04-15", "Spotify", -19.90, "Subscriptions"), ("2026-05-15", "Spotify", -19.90, "Subscriptions"),
]

def _write_sample(p: Path) -> None:
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "vendor", "amount", "category"])
        w.writerows(MOCK_ROWS)

# Normalization
HEBREW_SUFFIXES = ["דיל", "אקספרס", "שלי", "סופר", "מיני", "סיטי", "פלוס", "מרקט"]
ENGLISH_SUFFIXES = ["Express", "Mini", "Plus", "Online", "Market", "Store", "Shop"]
PUNCT_RE = re.compile(r"[\.,\-_/\\]+")

def normalize_vendor(v: str) -> str:
    """Strip whitespace, lowercase ascii, drop common suffix words."""
    s = v.strip()
    for suf in HEBREW_SUFFIXES + ENGLISH_SUFFIXES:
        s = re.sub(rf"\s+{re.escape(suf)}\b", "", s, flags=re.IGNORECASE)
    s = PUNCT_RE.sub(" ", s).strip()
    return s

def root_token(v: str) -> str:
    """Head token only — used for suffix-drift detection."""
    tokens = normalize_vendor(v).split()
    return tokens[0] if tokens else v

def load_transactions(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                d = datetime.strptime(row["date"].strip(), "%Y-%m-%d").date()
                amt = float(row["amount"])
            except (KeyError, ValueError):
                continue
            v = row.get("vendor", "").strip()
            raw_cat = (row.get("category") or "").strip()
            cat = raw_cat if raw_cat and raw_cat.lower() != "uncategorized" else categorize(v, amt)
            rows.append({"date": d, "vendor": v, "amount": amt, "abs": abs(amt),
                         "category": cat, "norm": normalize_vendor(v), "root": root_token(v)})
    return rows

# Detectors
def detect_subscription_creep(rows: list[dict]) -> list[dict]:
    months_by: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for r in rows:
        months_by[r["norm"]].add((r["date"].year, r["date"].month))
    out = []
    for vendor, months in months_by.items():
        sm = sorted(months); streak = max_streak = 1
        for (ay, am), (by, bm) in zip(sm, sm[1:]):
            if (by, bm) == (ay + (am == 12), am % 12 + 1):
                streak += 1; max_streak = max(streak, max_streak)
            else:
                streak = 1
        # Only report if the streak is still active (covers the most recent month in data)
        if max_streak >= 2 and streak == max_streak:
            out.append({"type": "subscription_creep", "vendor": vendor, "consecutive_months": max_streak})
    return out

def detect_duplicates(rows: list[dict]) -> list[dict]:
    by_pair: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by_pair[(r["norm"], round(r["abs"], 2))].append(r)
    out = []
    for (vendor, amt), group in by_pair.items():
        group.sort(key=lambda x: x["date"])
        for a, b in zip(group, group[1:]):
            if 0 <= (b["date"] - a["date"]).days <= 2:
                out.append({"type": "duplicate", "vendor": vendor, "amount": amt,
                            "dates": [a["date"].isoformat(), b["date"].isoformat()]})
    return out

def detect_amount_drift(rows: list[dict]) -> list[dict]:
    by_month: dict[str, dict[tuple, float]] = defaultdict(dict)
    for r in rows:
        by_month[r["norm"]][(r["date"].year, r["date"].month)] = r["abs"]
    out = []
    for vendor, monthly in by_month.items():
        months = sorted(monthly)
        for prev, cur in zip(months, months[1:]):
            p, c = monthly[prev], monthly[cur]
            if p and abs((c - p) / p) > 0.10:
                out.append({"type": "amount_drift", "vendor": vendor, "from": p, "to": c,
                            "pct_change": round((c - p) / p * 100, 1),
                            "month": f"{cur[0]}-{cur[1]:02d}"})
    return out

def detect_category_spike(rows: list[dict], today: date) -> list[dict]:
    start = today - timedelta(days=90)
    all_, recent = defaultdict(list), defaultdict(list)
    for r in rows:
        if not (start <= r["date"] <= today): continue
        all_[r["category"]].append(r["abs"])
        if (today - r["date"]).days <= 30:
            recent[r["category"]].append(r["abs"])
    out = []
    for cat, vals in all_.items():
        if len(vals) < 4: continue
        try: mean, sd = statistics.mean(vals), statistics.stdev(vals)
        except statistics.StatisticsError: continue
        if sd == 0: continue
        for v in recent.get(cat, []):
            if v > mean + 2 * sd:
                out.append({"type": "category_spike", "category": cat, "amount": v,
                            "mean_90d": round(mean, 2), "sigma": round(sd, 2)})
    return out

def detect_merchant_drift(rows: list[dict]) -> list[dict]:
    by_root: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        by_root[r["root"]].add(r["vendor"])
    return [{"type": "merchant_drift", "root": root, "variants": sorted(v)}
            for root, v in by_root.items() if root and len(v) >= 2]

# Run
def analyze(rows: list[dict], today: date) -> list[dict]:
    findings = []
    findings += detect_subscription_creep(rows)
    findings += detect_duplicates(rows)
    findings += detect_amount_drift(rows)
    findings += detect_category_spike(rows, today)
    findings += detect_merchant_drift(rows)
    return findings

def print_table(findings: list[dict]) -> None:
    if not findings:
        print("No anomalies detected.")
        return
    print(f"{'#':<3} {'type':<22} detail")
    print("-" * 80)
    for i, f in enumerate(findings, 1):
        detail = ", ".join(f"{k}={v}" for k, v in f.items() if k != "type")
        print(f"{i:<3} {f['type']:<22} {detail}")

def run(csv_path: Path | None, today: date) -> Path:
    if csv_path is None:
        csv_path = SAMPLE_CSV
        if not csv_path.exists():
            log.warning("RUNNING IN MOCK MODE — writing sample CSV to %s", csv_path)
            _write_sample(csv_path)
    rows = load_transactions(csv_path)
    findings = analyze(rows, today)
    print_table(findings)
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    out = BRIEFINGS_DIR / f"anomalies_{today.isoformat()}.json"
    out.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return out

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="path to transactions CSV")
    ap.add_argument("--as-of", help="YYYY-MM-DD, defaults to today")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    csv_path = Path(args.csv) if args.csv else None
    run(csv_path, today)

if __name__ == "__main__":
    main()
