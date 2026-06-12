"""
Family inc. — Reminders Engine (SPEC.md §7.1: daily 07:25 — computes, does not send)

Reads the Reminders tab (via lib/sheet.py — local seed xlsx until the M2
gspread port), applies the tombstone guard and fire rules, and returns one
Digest per recipient. Delivery belongs to daily_digest.py (07:30), which
renders ONE morning message per recipient and queues it through lib/outbox.py.

Every run appends a heartbeat line to logs/reminders_log.csv (fired/dropped/
skipped + reasons) — that is this script's only side effect.

Run modes:
  python3 automation/reminders_engine.py            # compute + log heartbeat
  python3 automation/reminders_engine.py --dry-run  # compute + print, still logs (flagged)
  python3 automation/reminders_engine.py --as-of 2026-06-15  # simulate any date
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/reminders_engine.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import csv
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

from automation.lib import config
from automation.lib.sheet import Reminder, read_reminders

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Fire:
    reminder: Reminder
    reason: str       # OVERDUE / FIRE TODAY / WEEK OUT / MONTH OUT / LEAD-{n}
    days_until: int


@dataclass
class Digest:
    recipient: str    # logical id: "adar" | "shanee" (numbers live in recipients.json)
    fires: list[Fire] = field(default_factory=list)
    dropped: list[Fire] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tombstone guard (SPEC.md §8.3 — offline-queue race window)
# ---------------------------------------------------------------------------
def is_tombstoned(r: Reminder, now: datetime,
                  window_hours: int = config.TOMBSTONE_SKIP_HOURS) -> bool:
    """True if the dashboard wrote (or flushed a queued write) within the last
    `window_hours`. When True, the engine MUST skip this row — the sheet state
    may be one hop behind reality."""
    if r.write_queue_tombstone is None:
        return False
    age = now - r.write_queue_tombstone
    if age.total_seconds() < 0:
        # Future-dated tombstone — treat as fresh, not as expired (SPEC §9).
        return True
    return age < timedelta(hours=window_hours)


# ---------------------------------------------------------------------------
# Decide-what-fires (SPEC.md §7.1)
# ---------------------------------------------------------------------------
def classify(r: Reminder, today: date) -> Fire | None:
    if r.status in {"Done", "Skipped"}:
        return None
    if r.due is None:
        return None
    days = (r.due - today).days

    # Overdue cooldown
    if days < 0:
        if r.last_sent and (today - r.last_sent).days < config.OVERDUE_REPEAT_DAYS:
            return None
        return Fire(r, "OVERDUE", days)

    if days == 0:
        return Fire(r, "FIRE TODAY", 0)
    if days in r.lead_times:
        if days <= 1:
            return Fire(r, "FIRE TODAY", days)
        if days <= 7:
            return Fire(r, "WEEK OUT", days)
        if days <= 30:
            return Fire(r, "MONTH OUT", days)
        return Fire(r, f"LEAD-{days}", days)
    return None


# ---------------------------------------------------------------------------
# Route to recipients — logical ids only; Owner column is display-cased
# ---------------------------------------------------------------------------
OWNER_TO_RECIPIENTS = {
    "adar": ["adar"],
    "shanee": ["shanee"],
    "partner": ["shanee"],          # legacy rows from the pre-remake sheet
    "both": ["adar", "shanee"],
}


def route(fires: list[Fire]) -> dict[str, Digest]:
    digests: dict[str, Digest] = {}
    for f in fires:
        recipients = OWNER_TO_RECIPIENTS.get(f.reminder.owner.strip().lower(), ["adar"])
        for r in recipients:
            digests.setdefault(r, Digest(recipient=r)).fires.append(f)
    return digests


# ---------------------------------------------------------------------------
# Digest shaping (priority-aware trimming — keeps the morning message short)
# ---------------------------------------------------------------------------
PRIORITY = {"OVERDUE": 0, "FIRE TODAY": 1, "WEEK OUT": 2, "MONTH OUT": 3}


def apply_budget(d: Digest, max_items: int = config.DIGEST_MAX_ITEMS) -> None:
    """Trim to `max_items`: OVERDUE / FIRE TODAY / Health always survive;
    Goals bump first (SPEC §8.1 trim priority)."""
    must = [f for f in d.fires if f.reason == "OVERDUE"
            or f.reason == "FIRE TODAY"
            or f.reminder.domain in config.ALWAYS_INCLUDE_DOMAINS]
    rest = [f for f in d.fires if f not in must]
    rest.sort(key=lambda f: (PRIORITY.get(f.reason, 9),
                             f.reminder.domain in config.DROP_FIRST_DOMAINS,
                             f.days_until))
    keep = must + rest
    if len(keep) > max_items:
        d.dropped = keep[max_items:]
        keep = keep[:max_items]
    d.fires = keep


# ---------------------------------------------------------------------------
# Heartbeat log (SPEC §7.1: one line per run, always)
# ---------------------------------------------------------------------------
LOG_HEADER = [
    "run_date", "recipient", "fires_sent", "fires_dropped",
    "skipped_due_to_tombstone", "dry_run", "titles_sent",
]


def append_log(today: date, digests: dict[str, Digest], log_path: Path | None = None,
               skipped_tombstone: int = 0, dry_run: bool = False) -> None:
    """One row per recipient per run. `skipped_due_to_tombstone` is the per-run
    count and is repeated on each recipient row (it's a run-level metric)."""
    log_path = log_path or config.REMINDERS_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not log_path.exists()
    with log_path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new_file:
            w.writerow(LOG_HEADER)
        # If there are no digests but the run still happened (all tombstoned
        # or genuinely quiet), emit one heartbeat row so log analysis sees the run.
        rows_to_emit = list(digests.items()) or [("(none)", Digest(recipient="(none)"))]
        for r, d in rows_to_emit:
            titles = " | ".join(f.reminder.title for f in d.fires)
            w.writerow([
                today.isoformat(), r,
                len(d.fires), len(d.dropped),
                skipped_tombstone, "yes" if dry_run else "no",
                titles,
            ])


# ---------------------------------------------------------------------------
# Compute (pure; the 07:30 digest assembler calls this)
# ---------------------------------------------------------------------------
@dataclass
class ComputeResult:
    digests: dict[str, Digest]
    tombstoned: list[tuple[Reminder, float]]   # (reminder, age_hours)


def compute(today: date, now: datetime | None = None,
            sheet_path: Path | None = None) -> ComputeResult:
    """Read → tombstone-guard → classify → route → trim. No side effects."""
    if now is None:
        now = datetime.now() if today == date.today() else datetime.combine(today, time(7, 30))
    reminders = read_reminders(sheet_path or config.SHEET_PATH)

    active: list[Reminder] = []
    tombstoned: list[tuple[Reminder, float]] = []
    for r in reminders:
        if is_tombstoned(r, now):
            age_h = (now - r.write_queue_tombstone).total_seconds() / 3600.0
            tombstoned.append((r, age_h))
        else:
            active.append(r)

    fires = [f for f in (classify(r, today) for r in active) if f]
    digests = route(fires)
    for d in digests.values():
        apply_budget(d)
    return ComputeResult(digests=digests, tombstoned=tombstoned)


def run(today: date, dry_run: bool = False, now: datetime | None = None,
        sheet_path: Path | None = None) -> dict[str, Digest]:
    """CLI entry: compute + heartbeat log + console summary. Rendering and
    delivery live in daily_digest.py — this engine never messages anyone."""
    result = compute(today, now=now, sheet_path=sheet_path)

    if result.tombstoned:
        print(f"tombstone-guard: skipped {len(result.tombstoned)} row(s) "
              f"(window={config.TOMBSTONE_SKIP_HOURS}h)")
        for r, age_h in result.tombstoned:
            print(f"  row {r.row} '{r.title}' — tombstone age {age_h:.2f}h")

    if not result.digests:
        print(f"{today}: quiet day — no fires")
    for rcpt, d in result.digests.items():
        print(f"{today}: {rcpt} ← {len(d.fires)} fire(s), {len(d.dropped)} dropped")
        if dry_run:
            for f in d.fires:
                print(f"    {f.reason:<10} {f.reminder.title}")

    append_log(today, result.digests, skipped_tombstone=len(result.tombstoned),
               dry_run=dry_run)
    return result.digests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
