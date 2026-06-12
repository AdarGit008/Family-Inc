"""
Family inc. — THE outbox chokepoint (SPEC.md §7.5). The only path to a human.

    queue(to, body, kind, source=…, msg_id=…)
      briefing → exempt from budget, subject to quiet hours (22:00–07:00 → hold)
      alert    → consult ledger[date][recipient]; if ≥cap → defer to tomorrow's
                 digest + log alert_suppressed_by_budget; else queue + increment
      critical → queue immediately, any hour, log budget_bypassed_critical
      all      → idempotent by (id, target); ledger + queue are durable on disk

The ledger is shared across ALL senders (D-015) — engine and summarizer can no
longer each spend 2/day. M1 ships the chokepoint + tests; M2 rewires every
sender through `queue()` and deletes the legacy `queue_message()` shim.

Delivery is the bridge's job: it polls the outbox JSONL, refuses targets not in
its machine-local recipients.json, dedups per (id, target) against the sent
ledger, and skips rows whose `not_before` hasn't arrived.
"""
from __future__ import annotations

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
        log.warning("outbox ledger unreadable (%s) — treating as empty, fail-open", p)
        return {}


def _write_ledger(day: date, ledger: dict[str, int]) -> None:
    config.OUTBOX_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    _ledger_path(day).write_text(json.dumps(ledger, indent=1), encoding="utf-8")


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


def pop_deferred(upto: date) -> list[dict]:
    """Like read_deferred, but consumes what it returns (real digest runs)."""
    rows = _jsonl_rows(config.DEFERRED_FILE)
    take = [r for r in rows if r.get("deferred_on", "") < upto.isoformat()]
    keep = [r for r in rows if r.get("deferred_on", "") >= upto.isoformat()]
    if take:
        config.DEFERRED_FILE.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
    return take


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
    if kind == "alert":
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
# Legacy shim — exact pre-M1 wa_outbox.queue_message behavior (no kinds, no
# budget; callers still enforce their own). M2 rewires summarizer/reply_handler
# through queue() and DELETES this. Do not add new callers.
# ---------------------------------------------------------------------------
def queue_message(to: str, body: str, source: str = "unknown") -> str:
    if to not in VALID_RECIPIENTS:
        raise ValueError(f"recipient must be one of {VALID_RECIPIENTS}, got {to!r}")
    if not body or not body.strip():
        raise ValueError("empty message body")
    msg_id = str(uuid.uuid4())
    _append_outbox({
        "id": msg_id, "to": to, "body": body.strip(), "source": source,
        "queued_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    })
    return msg_id


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
