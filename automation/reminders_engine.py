"""
Family inc. — Reminders Engine (SPEC.md §7.1: daily 07:25 — computes, does not send)

Reads the Reminders tab (via lib/sheet.py — the live Google Sheet when
FAMILY_INC_SHEET_ID is configured, the seed xlsx otherwise), applies the
tombstone guard and fire rules, and returns one Digest per recipient.
Delivery belongs to daily_digest.py (07:30), which renders ONE morning
message per recipient, queues it through lib/outbox.py, and stamps
Last Sent / Status back to the Sheet on send success.

This run's own write-back (M2): recurrence on Done — rows the dashboard
marked Done with a recurrence period get their Due Date bumped, Status →
Pending, Last Sent cleared (SPEC §7.1). Feb-29-class clamps and Custom
periods are flagged for review in logs/engine_flags.jsonl, surfaced by the
weekly briefing. Tombstoned rows (<6h) are skipped here exactly like fires —
write-backs honor the same race guard. Writes only happen against the live
backend (or an explicit --apply-writes for a local xlsx) so a creds-less run
never mutates the committed seed template.

Every run appends a heartbeat line to logs/reminders_log.csv (fired/dropped/
skipped + reasons).

Run modes:
  python3 automation/reminders_engine.py            # compute + log heartbeat (+ bumps when live)
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
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

from automation.lib import config, sheet
from automation.lib.dates import bump_due
from automation.lib.sheet import CellWrite, Reminder, read_reminders

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
    # SPEC §7.1 reads "Status ∉ {Done, Skipped}" — Sent rows stay eligible so a
    # 60,30,7,1 lead-time chain keeps firing after its first fire stamps Sent.
    if r.status in {"Done", "Skipped"}:
        return None
    if r.due is None:
        return None
    # Last-Sent guard (SPEC §8.4): a row already stamped today never re-fires —
    # engine/digest re-runs on the same day are no-ops at compute level.
    if r.last_sent == today:
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
    "tombstone_max_age_h",   # additive (B6): max skip age this run, for the
                             # weekly self-report "max age seen" (SPEC §8.3)
]


def append_log(today: date, digests: dict[str, Digest], log_path: Path | None = None,
               skipped_tombstone: int = 0, dry_run: bool = False,
               tombstone_max_age_h: float = 0.0) -> None:
    """One row per recipient per run. `skipped_due_to_tombstone` /
    `tombstone_max_age_h` are per-run metrics, repeated on each recipient row
    (older rows predate the age column → read as 0)."""
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
                titles, f"{tombstone_max_age_h:.2f}",
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
    reminders = read_reminders(sheet_path)  # None → live Sheet when configured

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


# ---------------------------------------------------------------------------
# Write-backs (M2, SPEC §7.1) — the engine's only Sheet writes
# ---------------------------------------------------------------------------
def _flag_for_review(reason: str, r: Reminder, **fields) -> None:
    """Append one review line to logs/engine_flags.jsonl (weekly briefing
    surfaces unreviewed flags in data hygiene)."""
    config.ENGINE_FLAGS.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now().isoformat(timespec="seconds"), "reason": reason,
           "row": r.row, "title": r.title, **fields}
    with config.ENGINE_FLAGS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def recurrence_writes(reminders: list[Reminder], now: datetime) -> list[CellWrite]:
    """Recurrence on Done (SPEC §7.1): bump Due Date by the period, Status →
    Pending, Last Sent cleared. DoneAt/LastDoneBy stay — the dashboard arc and
    ticker read them. Tombstoned rows (<6h) wait for the next run; clamped
    dates (Feb-29 class) and Custom periods are flagged for review."""
    writes: list[CellWrite] = []
    for r in reminders:
        if r.status != "Done" or r.recurrence in ("", "One-off"):
            continue
        if is_tombstoned(r, now):
            continue  # same race guard as fires — the dashboard may still be writing
        if r.due is None:
            _flag_for_review("recurring_done_without_due", r)
            continue
        new_due, clamped = bump_due(r.due, r.recurrence)
        if new_due is None:
            _flag_for_review("unbumpable_recurrence", r, recurrence=r.recurrence)
            continue
        if clamped:
            _flag_for_review("recurrence_clamped_to_month_end", r,
                             old_due=r.due.isoformat(), new_due=new_due.isoformat())
        writes += [
            CellWrite(r.row, "Due Date", new_due),
            CellWrite(r.row, "Status", "Pending"),
            CellWrite(r.row, "Last Sent", None),
        ]
    return writes


def stamp_writes(fires: list[Fire], now: datetime) -> list[CellWrite]:
    """On send success (daily_digest --send): Last Sent = now,
    Status = Sent | Overdue (SPEC §7.1)."""
    writes: list[CellWrite] = []
    for f in {f.reminder.row: f for f in fires}.values():  # one stamp per row
        writes += [
            CellWrite(f.reminder.row, "Last Sent", now),
            CellWrite(f.reminder.row, "Status",
                      "Overdue" if f.days_until < 0 else "Sent"),
        ]
    return writes


def apply_recurrence(today: date, now: datetime | None = None,
                     sheet_path: Path | None = None) -> int:
    """Read → bump Done recurring rows → one batched write. Returns rows bumped."""
    now = now or datetime.now()
    reminders = read_reminders(sheet_path)
    writes = recurrence_writes(reminders, now)
    if writes:
        sheet.update_reminders(writes, sheet_path)
    return len({w.row for w in writes})


def run(today: date, dry_run: bool = False, now: datetime | None = None,
        sheet_path: Path | None = None, apply_writes: bool | None = None) -> dict[str, Digest]:
    """CLI entry: compute + recurrence write-back + heartbeat log + console
    summary. Rendering and delivery live in daily_digest.py — this engine
    never messages anyone.

    `apply_writes`: None → write only against the live backend (sheet.is_live());
    True forces writes (tests, against an explicit sheet_path); dry_run always
    suppresses them."""
    if apply_writes is None:
        apply_writes = sheet.is_live() and sheet_path is None
    if apply_writes and not dry_run:
        bumped = apply_recurrence(today, now=now, sheet_path=sheet_path)
        if bumped:
            print(f"recurrence: bumped {bumped} Done row(s) to their next due date")

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
               dry_run=dry_run,
               tombstone_max_age_h=max((a for _, a in result.tombstoned), default=0.0))
    return result.digests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply-writes", action="store_true",
                    help="force recurrence write-backs without a live backend "
                         "(normally implied by FAMILY_INC_SHEET_ID)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, dry_run=args.dry_run,
        apply_writes=True if args.apply_writes else None)


if __name__ == "__main__":
    main()
