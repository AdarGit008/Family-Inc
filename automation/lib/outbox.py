"""
Family inc. — THE outbox chokepoint (SPEC.md §7.5). The only path to a human.

    queue(to, body, kind, source=…, msg_id=…)
      briefing → exempt from budget, subject to quiet hours (22:00–07:00 → hold)
      alert    → consult ledger[date][recipient]; if ≥cap → defer to tomorrow's
                 digest + log alert_suppressed_by_budget; else queue + increment
      critical → queue immediately, any hour, log budget_bypassed_critical
      all      → idempotent by (id, target); ledger + queue are durable on disk

The ledger is shared across ALL senders (D-015) — engine and summarizer can no
longer each spend 2/day. Every sender goes through `queue()`; the pre-M1
`queue_message()` shim was deleted in M2. Do not add side doors.

Delivery is the bridge's job: it polls the outbox JSONL, refuses targets not in
its machine-local recipients.json, dedups per (id, target) against the sent
ledger, and skips rows whose `not_before` hasn't arrived.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from automation.lib import config

log = logging.getLogger("outbox")

VALID_RECIPIENTS = {"adar", "shanee", "both"}
KINDS = {"alert", "critical", "briefing"}


# ---------------------------------------------------------------------------
# Quiet hours (SPEC.md §8.2 — enforced here, nowhere else)
# ---------------------------------------------------------------------------
def is_quiet_hours(now: datetime) -> bool:
    """True inside the 22:00–07:00 window (straddles midnight)."""
    h = now.hour
    return h >= config.QUIET_HOURS_START or h < config.QUIET_HOURS_END


def quiet_hours_release(now: datetime) -> datetime:
    """The 07:00 that ends the quiet window containing `now`."""
    release = now.replace(hour=config.QUIET_HOURS_END, minute=0, second=0, microsecond=0)
    if now.hour >= config.QUIET_HOURS_START:
        release += timedelta(days=1)
    return release


# ---------------------------------------------------------------------------
# Durable state: ledger, dedup index, deferred queue
# ---------------------------------------------------------------------------
def _ledger_path(day: date):
    return config.OUTBOX_LEDGER_DIR / f"{day.isoformat()}.json"


def read_ledger(day: date) -> dict[str, int]:
    p = _ledger_path(day)
    if not p.exists():
        return {}
    try:
        return {k: int(v) for k, v in json.loads(p.read_text(encoding="utf-8")).items()}
    except (json.JSONDecodeError, OSError, ValueError):
        # FAIL-CLOSED (outbox-budget#1): a corrupt ledger must NOT silently reopen
        # the day's 2/day cap. Treat the day as already at cap so alerts defer
        # (never lost — they ride tomorrow's digest) instead of flooding. Loud so
        # the operator inspects/deletes the file to reset. Atomic writes below make
        # this rare (only true disk corruption, not a torn write).
        log.error("outbox ledger CORRUPT (%s) — fail-closed: treating today as cap-reached "
                  "(alerts will defer). Inspect and delete to reset.", p)
        return {r: config.ALERT_BUDGET_PER_DAY for r in ("adar", "shanee")}


def _write_ledger(day: date, ledger: dict[str, int]) -> None:
    config.OUTBOX_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    p = _ledger_path(day)
    # Atomic write (outbox-budget#1): tmp + replace, so a crash mid-write can't
    # leave a torn ledger that read_ledger would have to fail-closed on.
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    tmp.replace(p)


@contextlib.contextmanager
def _ledger_lock(day: date):
    """Exclusive lock around a day's ledger read-modify-write (outbox-budget#2),
    so two concurrent senders can't both pass the 2/day check and double-spend —
    the exact race the single-shared-ledger rule (D-015) exists to prevent."""
    config.OUTBOX_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = config.OUTBOX_LEDGER_DIR / f"{day.isoformat()}.lock"
    with open(lock_path, "w", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _log_event(event: str, **fields) -> None:
    """Append one audit line (criticals bypassing, alerts suppressed, …)."""
    config.OUTBOX_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now().isoformat(timespec="seconds"), "event": event, **fields}
    with (config.OUTBOX_LEDGER_DIR / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _jsonl_rows(path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue  # torn tail line self-heals next poll (SPEC §9)
    return rows


def _seen_pairs() -> set[tuple[str, str]]:
    """(id, target) pairs already queued or sent — the idempotency index."""
    seen: set[tuple[str, str]] = set()
    for row in _jsonl_rows(config.OUTBOX_FILE):
        targets = ["adar", "shanee"] if row.get("to") == "both" else [row.get("to", "")]
        for t in targets:
            seen.add((row.get("id", ""), t))
    for row in _jsonl_rows(config.SENT_FILE):
        seen.add((row.get("id", ""), row.get("target", row.get("to", ""))))
    return seen


def _append_outbox(row: dict) -> None:
    config.OUTBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.OUTBOX_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _append_deferred(row: dict) -> None:
    config.DEFERRED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.DEFERRED_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_deferred(upto: date) -> list[dict]:
    """Budget-deferred items due for inclusion in today's digest (SPEC §7.5:
    over-budget alerts 'append to tomorrow's digest'). Non-consuming peek."""
    return [r for r in _jsonl_rows(config.DEFERRED_FILE)
            if r.get("deferred_on", "") < upto.isoformat()]


def _rewrite_deferred(keep: list[dict]) -> None:
    # Atomic rewrite (tmp + replace), same discipline as the ledger
    # (outbox-budget#1) — a crash mid-rewrite must not corrupt the deferred
    # queue and lose alerts that haven't ridden a digest yet.
    tmp = config.DEFERRED_FILE.with_name(config.DEFERRED_FILE.name + ".tmp")
    tmp.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
    tmp.replace(config.DEFERRED_FILE)


def pop_deferred(upto: date) -> list[dict]:
    """Like read_deferred, but consumes what it returns (real digest runs)."""
    rows = _jsonl_rows(config.DEFERRED_FILE)
    take = [r for r in rows if r.get("deferred_on", "") < upto.isoformat()]
    keep = [r for r in rows if r.get("deferred_on", "") >= upto.isoformat()]
    if take:
        _rewrite_deferred(keep)
    return take


def drop_deferred(keys: set[tuple[str, str]]) -> None:
    """Consume specific deferred rows by (id, to) — called when the digest that
    carried them is CONFIRMED delivered (outbox-budget#3, GAP-2). Idempotent:
    keys already absent are a no-op, so a re-run never loses a different
    recipient's still-pending alert (deferred rows are single-target)."""
    if not keys:
        return
    rows = _jsonl_rows(config.DEFERRED_FILE)
    keep = [r for r in rows if (r.get("id", ""), r.get("to", "")) not in keys]
    if len(keep) != len(rows):
        _rewrite_deferred(keep)


# ---------------------------------------------------------------------------
# Pending bridge-digests awaiting delivery confirmation (GAP-2 cross-run
# reconcile). The bridge delivers asynchronously, so "queued" ≠ "delivered":
# the digest records a pending row per recipient here and the next run's
# reconcile stamps Last Sent/Status once SENT_FILE confirms the delivery.
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def pending_lock():
    """Exclusive lock around the digest-pending file's read→reconcile→rewrite
    (and record_pending's append), so a concurrent --send run — a manual re-run
    or a future timer overlap — can't double-process an entry or clobber a
    freshly-recorded one on rewrite. Same fcntl discipline as _ledger_lock
    (outbox-budget#2)."""
    config.DIGEST_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = config.DIGEST_PENDING_FILE.with_name(config.DIGEST_PENDING_FILE.name + ".lock")
    with open(lock_path, "w", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def record_pending(entry: dict) -> None:
    """Append one pending-digest row (one per recipient queued this run).
    Callers hold pending_lock() so the append can't race a concurrent rewrite."""
    config.DIGEST_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.DIGEST_PENDING_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_pending() -> list[dict]:
    """Every pending-digest row not yet settled by reconcile."""
    return _jsonl_rows(config.DIGEST_PENDING_FILE)


def rewrite_pending(rows: list[dict]) -> None:
    """Atomic rewrite after reconcile drops settled entries; removes the file
    when nothing is left waiting."""
    if not rows:
        config.DIGEST_PENDING_FILE.unlink(missing_ok=True)
        return
    config.DIGEST_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.DIGEST_PENDING_FILE.with_name(config.DIGEST_PENDING_FILE.name + ".tmp")
    tmp.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(config.DIGEST_PENDING_FILE)


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------
@dataclass
class QueueResult:
    queued: list[dict] = field(default_factory=list)      # rows appended
    deferred: list[str] = field(default_factory=list)     # targets pushed to tomorrow's digest
    duplicates: list[str] = field(default_factory=list)   # targets skipped by (id, target) dedup


def queue(to: str, body: str, kind: str = "alert", *, source: str = "unknown",
          msg_id: Optional[str] = None, now: Optional[datetime] = None) -> QueueResult:
    """Queue one message toward a phone. See module docstring for semantics.

    `msg_id` should be the stable id from SPEC §8.4 (rem-…, wa-…, brief-…);
    a uuid is generated when omitted, which forfeits cross-run idempotency.
    """
    if to not in VALID_RECIPIENTS:
        raise ValueError(f"recipient must be one of {sorted(VALID_RECIPIENTS)}, got {to!r}")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {sorted(KINDS)}, got {kind!r}")
    if not body or not body.strip():
        raise ValueError("empty message body")

    now = now or datetime.now()
    msg_id = msg_id or str(uuid.uuid4())
    targets = ["adar", "shanee"] if to == "both" else [to]
    result = QueueResult()

    # Idempotency first — a re-run must not consume budget twice.
    seen = _seen_pairs()
    fresh = []
    for t in targets:
        if (msg_id, t) in seen:
            result.duplicates.append(t)
        else:
            fresh.append(t)
    targets = fresh
    if not targets:
        log.info("outbox: %s duplicate for all targets — no-op", msg_id)
        return result

    # Budget (alerts only; briefings exempt by principle, criticals by design).
    # The whole check+increment runs under an exclusive lock (outbox-budget#2) so
    # concurrent senders can't each pass the 2/day check on a stale read.
    if kind == "alert":
        with _ledger_lock(now.date()):
            ledger = read_ledger(now.date())
            ok, over = [], []
            for t in targets:
                (ok if ledger.get(t, 0) < config.ALERT_BUDGET_PER_DAY else over).append(t)
            for t in over:
                _append_deferred({
                    "id": msg_id, "to": t, "body": body.strip(), "source": source,
                    "deferred_on": now.date().isoformat(),
                })
                _log_event("alert_suppressed_by_budget", id=msg_id, target=t, source=source)
                log.info("alert suppressed by budget → tomorrow's digest (%s → %s)", msg_id, t)
            result.deferred = over
            if not ok:
                return result
            for t in ok:
                ledger[t] = ledger.get(t, 0) + 1
            _write_ledger(now.date(), ledger)
            targets = ok

    # Quiet hours: alerts + briefings hold; criticals do not (SPEC §8.2).
    not_before = None
    if kind != "critical" and is_quiet_hours(now):
        not_before = quiet_hours_release(now).isoformat(timespec="seconds")
    if kind == "critical":
        _log_event("budget_bypassed_critical", id=msg_id, targets=targets, source=source)

    row = {
        "id": msg_id,
        "to": "both" if set(targets) == {"adar", "shanee"} else targets[0],
        "body": body.strip(),
        "kind": kind,
        "source": source,
        "queued_at": now.astimezone().isoformat(timespec="seconds"),
    }
    if not_before:
        row["not_before"] = not_before
    _append_outbox(row)
    result.queued.append(row)
    return result


# ---------------------------------------------------------------------------
# Bridge health + delivery introspection (unchanged from wa_outbox.py)
# ---------------------------------------------------------------------------
def bridge_alive(now: Optional[datetime] = None) -> bool:
    """True if the bridge heartbeat file's mtime is fresh. Callers surface a
    warning when False — queued messages still go out on reconnect."""
    try:
        mtime = config.HEARTBEAT_FILE.stat().st_mtime
    except OSError:
        return False
    ts = datetime.fromtimestamp(mtime)
    now = now or datetime.now()
    return (now - ts) <= timedelta(minutes=config.HEARTBEAT_STALE_MINUTES)


def heartbeat_age_hours(now: Optional[datetime] = None) -> Optional[float]:
    """Heartbeat age in hours; None = no heartbeat file (bridge never ran
    here). Wall-clock by default — infra health is never simulated under
    --as-of. Past config.EMAIL_FALLBACK_AFTER_HOURS the daily digest degrades
    to the SPEC §10.2 email fallback."""
    try:
        mtime = config.HEARTBEAT_FILE.stat().st_mtime
    except OSError:
        return None
    now = now or datetime.now()
    return max(0.0, (now - datetime.fromtimestamp(mtime)).total_seconds() / 3600.0)


def delivery_status(msg_id: str) -> list[dict]:
    """Sent-ledger rows for one message id (one per target). Empty = pending."""
    return [r for r in _jsonl_rows(config.SENT_FILE) if r.get("id") == msg_id]


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] in VALID_RECIPIENTS:
        res = queue(sys.argv[1], " ".join(sys.argv[2:]), "alert", source="cli")
        alive = bridge_alive()
        print(f"queued {len(res.queued)} row(s), deferred {res.deferred or 'none'} "
              f"(bridge {'alive' if alive else 'DOWN — will send on reconnect'})")
    else:
        print("usage: python -m automation.lib.outbox adar|shanee|both <message text>")
