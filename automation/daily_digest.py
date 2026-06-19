"""
Family inc. — Daily digest assembly (SPEC.md §7.2: 07:30 — ONE morning message
per recipient, not several)

Carved out of the engine's send path in M1 (ENGINEERING.md §9). Assembles, in
order: reminders fires (engine compute) · alerts held by yesterday's budget ·
the WhatsApp groups digest (written hourly by whatsapp_summarizer) · new
property listings (written by property_scrape, M5/§12.1 — silent, no alert) ·
a Hebcal candle-lighting line on Fridays. Renders with `templates.py` copy and writes
one file per recipient to Briefings/; with --send it also queues through
lib/outbox.py (kind=briefing per SPEC §7.2 — budget-exempt, never deferrable;
was kind=alert until D-027 — id=brief-daily-{date}).

Delivery degrades per SPEC §10.2: heartbeat stale >24h → the identical
rendered content goes by SMTP (lib/mailer.py) instead of queueing rows the
bridge can't deliver. It also reports + clears logs/fail.flag (the systemd
OnFailure= hook, ENGINEERING §5) — fail loud, in the message humans read.

Until M3 go-live, run WITHOUT --send: files are written, nobody is messaged,
and nothing accumulates in the bridge outbox.

On CONFIRMED delivery the digest stamps each fired row back to the Sheet: Last
Sent = now, Status = Sent | Overdue (SPEC §7.1/§7.2). The bridge delivers
asynchronously, so a bridge-queued digest is not stamped on queue — it records a
pending row per recipient and reconcile_deliveries() (start of the next --send
run) stamps once whatsapp_sent.jsonl confirms (GAP-2: queue ≠ delivered, closing
a silent-loss path). The SMTP fallback's return value IS the confirmation, so it
stamps inline. Stamping is skipped — loudly — when no live backend is configured,
so a dev-machine --send can never mutate the committed seed xlsx.

Run modes:
  python3 automation/daily_digest.py             # write Briefings/ files
  python3 automation/daily_digest.py --dry-run   # print only
  python3 automation/daily_digest.py --send      # also queue to the outbox (M3)
  python3 automation/daily_digest.py --as-of 2026-06-15
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/daily_digest.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import csv
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Callable, Optional

from automation import templates as T
from automation import reminders_engine as engine
from automation.lib import config, mailer, outbox, sheet
from automation.lib.dates import fmt_date_he

# ---------------------------------------------------------------------------
# Reminders section (DESIGN §6 v1: one line per item — flag emoji · title ·
# due phrase; notes ride along only when ≤120 chars; no reply footers, D-014.
# Byte-stability is locked by tests/test_render_golden.py)
# ---------------------------------------------------------------------------
def due_phrase(f: engine.Fire) -> str:
    n = f.days_until
    if n < 0:
        if n == -1:
            return T.DUE_OVERDUE_1
        if n == -2:
            return T.DUE_OVERDUE_2
        return T.DUE_OVERDUE_N.format(n=-n)
    if n == 0:
        return T.DUE_TODAY
    if n == 1:
        return T.DUE_TOMORROW
    if n == 2:
        return T.DUE_IN_2
    return T.DUE_IN_N.format(n=n)


def render_digest(d: engine.Digest, today: date) -> str:
    head = T.DIGEST_HEAD.format(date=fmt_date_he(today))
    if not d.fires:
        return f"{head}\n{T.DIGEST_QUIET_DAY}"
    lines = [head]
    for f in d.fires:
        lines.append(T.DIGEST_ITEM.format(
            emoji=T.FLAG_EMOJI.get(f.reason, "•"),
            title=f.reminder.title, due_phrase=due_phrase(f)))
        notes = f.reminder.notes.strip()
        if notes and len(notes) <= config.NOTES_MAX_CHARS:
            lines.append(notes)
    if d.dropped:
        lines.append(T.DIGEST_MORE_IN_DASHBOARD.format(n=len(d.dropped)))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Batch-window dedup (guards a rerun/retry within BATCH_WINDOW_MINUTES;
# lives here because it is a send-path concern)
# ---------------------------------------------------------------------------
def batch_deduplicate(digests: dict[str, engine.Digest], now: datetime,
                      window_minutes: int = config.BATCH_WINDOW_MINUTES,
                      log_path: Optional[Path] = None) -> dict[str, engine.Digest]:
    """Suppress fires whose titles already appear in log rows inside the batch
    window, so a forced rerun doesn't message the same alert twice."""
    log_path = log_path or config.REMINDERS_LOG
    cutoff = now - timedelta(minutes=window_minutes)
    if not log_path.exists():
        return digests  # no history, nothing to dedup

    sent_recently: set[str] = set()
    try:
        with log_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    run_dt = datetime.fromisoformat(row.get("run_date", ""))
                    if run_dt >= cutoff:
                        for title in (row.get("titles_sent") or "").split(" | "):
                            if title.strip():
                                sent_recently.add(title.strip())
                except (ValueError, TypeError):
                    pass
    except OSError:
        return digests

    if not sent_recently:
        return digests

    deduped: dict[str, engine.Digest] = {}
    for recipient, d in digests.items():
        kept = [f for f in d.fires if f.reminder.title not in sent_recently]
        dropped = [f for f in d.fires if f.reminder.title in sent_recently]
        deduped[recipient] = engine.Digest(recipient=recipient, fires=kept,
                                           dropped=d.dropped + dropped)
    return deduped


# ---------------------------------------------------------------------------
# Assembly (SPEC §7.2): reminders · budget-deferred · WA digest · Hebcal
# ---------------------------------------------------------------------------
def _wa_digest_text(today: date, briefings_dir: Path) -> str:
    p = briefings_dir / f"whatsapp_digest_{today.isoformat()}.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


def _property_text(today: date, briefings_dir: Path) -> str:
    """The "🏠 דירות חדשות" section written by property_scrape (M5, §12.1).
    Absent on days with no new listings → contributes nothing (silent)."""
    p = briefings_dir / f"property_listings_{today.isoformat()}.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


def _hebcal_line(today: date, shabbat_times: Optional[Callable],
                 chag_candles: Optional[Callable] = None) -> str:
    """Candle-lighting line on erev-Shabbat (Fridays) AND erev-chag (yom-tov eves)
    — SPEC §7.2/§4. Fridays read shabbat_times(); other days read chag_candles(),
    which returns None on a plain (non-eve) day. Degrades to nothing — a missing
    Hebcal answer must not page anyone, and a non-eve simply renders no line."""
    if shabbat_times is None:
        return ""
    # A chag whose eve falls on a Friday is handled as Shabbat (candle time is
    # correct; for a Sat+Sun yom-tov block the havdalah shown is Saturday night).
    is_friday = today.weekday() == 4  # 4 = Friday
    try:
        if is_friday:
            st = shabbat_times(today)
        elif chag_candles is not None:
            st = chag_candles(today)
        else:
            st = None
    except Exception:
        return ""
    if not st:
        return ""
    candles, havdalah = st.get("candle_lighting"), st.get("havdalah")
    if not candles or not havdalah:
        return ""
    def hhmm(iso: str) -> str:
        try:
            return datetime.fromisoformat(iso).strftime("%H:%M")
        except ValueError:
            return iso
    tmpl = T.HEBCAL_LINE if is_friday else T.HEBCAL_LINE_CHAG  # "צאת שבת" vs "צאת החג"
    return tmpl.format(candles=hhmm(candles), havdalah=hhmm(havdalah))


def _deferred_for(deferred: list[dict], rcpt: str) -> list[dict]:
    """The budget-deferred alerts that ride this recipient's digest (SPEC §7.5).
    One filter, used by assembly (to render them) and the send path (to record
    which (id, to) keys the digest carries, so reconcile consumes them only on
    confirmed delivery). Deferred rows are single-target — `both` is defensive."""
    return [r for r in deferred if r.get("to") in (rcpt, "both")]


_DEFAULT = object()  # sentinel: "use the real hebcal client"


@dataclass
class Assembly:
    """Rendered messages plus the digests they were rendered from — the send
    path stamps Last Sent/Status for exactly the fires that went out."""
    messages: dict[str, str] = field(default_factory=dict)
    digests: dict[str, engine.Digest] = field(default_factory=dict)


def assemble(today: date, now: Optional[datetime] = None,
             sheet_path: Optional[Path] = None,
             briefings_dir: Optional[Path] = None,
             shabbat_times: Optional[Callable] = _DEFAULT,
             chag_candles: Optional[Callable] = _DEFAULT,
             deferred: Optional[list[dict]] = None,
             failed_units: Optional[list[str]] = None) -> Assembly:
    """One rendered message per recipient. Pure given its inputs (the Hebcal
    fetchers and the deferred list are injectable so tests stay deterministic
    and dry runs never consume the deferred queue)."""
    if now is None:
        now = datetime.now() if today == date.today() else datetime.combine(today, time(7, 30))
    if shabbat_times is _DEFAULT or chag_candles is _DEFAULT:
        from automation import hebcal_client
        if shabbat_times is _DEFAULT:
            shabbat_times = hebcal_client.shabbat_times
        if chag_candles is _DEFAULT:
            chag_candles = hebcal_client.chag_candles
    briefings_dir = briefings_dir or config.BRIEFINGS_DIR

    result = engine.compute(today, now=now, sheet_path=sheet_path)
    digests = batch_deduplicate(result.digests, now)

    # Brief BOTH adults EVERY day (D-045). A recipient with no fires today still
    # gets the morning briefing — the quiet-day line plus the shared WA-groups /
    # property sections. This generalizes the partner-symmetric quiet-day rule
    # (D-036e/D-044, which only covered a FULLY-quiet day) to the asymmetric day:
    # when one adult has fires and the other none, the empty-handed adult is no
    # longer left with no morning message at all. Briefings are budget-exempt
    # (kind=briefing), so the extra message never spends an alert slot, and the
    # message's silence stays distinguishable from a broken digest. Canonical
    # (adar, shanee) order; engine.compute only ever keys these two (§7.3 routing).
    digests = {r: digests[r] if r in digests else engine.Digest(recipient=r)
               for r in config.DIGEST_RECIPIENTS}

    if deferred is None:
        deferred = outbox.read_deferred(today)
    wa_text = _wa_digest_text(today, briefings_dir)
    property_text = _property_text(today, briefings_dir)
    hebcal = _hebcal_line(today, shabbat_times, chag_candles)

    # Overnight unit failures prepend, never replace (DESIGN §6) — the humans
    # never check journald unless a message tells them to (ENGINEERING §8).
    fail_line = (T.FAIL_FLAG_LINE.format(units=", ".join(failed_units))
                 if failed_units else None)

    messages: dict[str, str] = {}
    for rcpt, d in digests.items():
        parts = ([fail_line] if fail_line else []) + [render_digest(d, today)]
        mine = _deferred_for(deferred, rcpt)
        if mine:
            parts.append("\n".join([T.SECTION_DEFERRED] +
                                   [T.DEFERRED_ITEM.format(body=r["body"]) for r in mine]))
        if wa_text:
            parts.append(wa_text)
        if property_text:
            parts.append(property_text)
        if hebcal:
            parts.append(hebcal)
        messages[rcpt] = "\n\n".join(parts) + "\n"
    return Assembly(messages=messages, digests=digests)


# ---------------------------------------------------------------------------
# Persist + queue
# ---------------------------------------------------------------------------
def write_briefing_files(messages: dict[str, str], today: date,
                         briefings_dir: Optional[Path] = None) -> list[Path]:
    briefings_dir = briefings_dir or config.BRIEFINGS_DIR
    briefings_dir.mkdir(exist_ok=True)
    out = []
    for rcpt, body in messages.items():
        p = briefings_dir / f"{today.isoformat()}_briefing_{rcpt}.md"
        p.write_text(body, encoding="utf-8")
        out.append(p)
    return out


def _apply_reminder_writes(writes: list, sheet_path: Optional[Path]) -> int:
    """Issue Last Sent/Status writes, refusing to mutate the committed seed xlsx
    when no live backend is configured (a dev-machine --send must stay inert).
    Returns the number of distinct rows written."""
    if not writes:
        return 0
    if sheet_path is None and not sheet.is_live():
        print("[warn] no live Sheet backend — Last Sent/Status NOT stamped "
              "(refusing to write the seed xlsx)")
        return 0
    sheet.update_reminders(writes, sheet_path)
    return len({w.row for w in writes})


def stamp_sent(assembly: Assembly, queued_for: set[str], now: datetime,
               sheet_path: Optional[Path] = None) -> int:
    """Write Last Sent/Status for every row that reached at least one phone this
    run (SPEC §7.1). Used by the SMTP fallback, whose return value IS the
    confirmation, so it stamps inline. The bridge path defers to
    reconcile_deliveries() instead (queue ≠ delivered). Deferred or duplicate
    targets don't count as sent — their rows stay eligible."""
    fires = [f for rcpt in queued_for
             for f in assembly.digests.get(rcpt, engine.Digest(rcpt)).fires]
    return _apply_reminder_writes(engine.stamp_writes(fires, now), sheet_path)


def _record_pending(assembly: Assembly, rcpt: str, today: date, now: datetime,
                    deferred: list[dict], fail_lines: list[str], msg_id: str) -> None:
    """Persist what this recipient's just-queued bridge-digest carries, so the
    next run's reconcile can stamp / clear / consume on confirmed delivery
    (GAP-2). Rows + overdue rebuild the §7.1 stamp; deferred_keys are the
    (id, to) of the budget-deferred alerts the digest rode (outbox-budget#3);
    reported_fail_lines are cleared from the fail flag on confirm."""
    d = assembly.digests.get(rcpt, engine.Digest(rcpt))
    outbox.record_pending({
        "msg_id": msg_id,
        "digest_date": today.isoformat(),
        "recipient": rcpt,
        # `due` lets reconcile detect a row that moved (reschedule / recurrence
        # bump) between queue and confirm and decline to stamp a stale snapshot.
        "rows": [{"row": f.reminder.row, "overdue": f.days_until < 0,
                  "due": f.reminder.due.isoformat() if f.reminder.due else None}
                 for f in d.fires],
        "deferred_keys": [[r.get("id", ""), r.get("to", "")]
                          for r in _deferred_for(deferred, rcpt)],
        "reported_fail_lines": fail_lines,
        "queued_at": now.isoformat(timespec="seconds"),
    })


def _pending_age_hours(entry: dict, now: datetime) -> float:
    """Hours since the digest was queued; +inf for an unparseable stamp so a
    corrupt entry is dropped (loudly) rather than pinned forever."""
    try:
        return (now - datetime.fromisoformat(entry.get("queued_at", ""))).total_seconds() / 3600.0
    except (ValueError, TypeError):
        return float("inf")


def _digest_sent_at(entry: dict, now: datetime) -> datetime:
    """The moment the digest actually went out (its queue time) — the truthful
    Last Sent, even when reconcile confirms it a run (or days) later. Falls back
    to `now` only for an unparseable stamp."""
    try:
        return datetime.fromisoformat(entry.get("queued_at", ""))
    except (ValueError, TypeError):
        return now


def reconcile_deliveries(now: datetime, sheet_path: Optional[Path] = None) -> int:
    """Stamp reminders for bridge-digests the bridge has since CONFIRMED
    delivering (GAP-2). Runs at the START of every --send run, before today's
    compute, so a just-confirmed row is seen as stamped and never re-fires.

    Per pending entry: if SENT_FILE shows a `status=='sent'` row to that
    recipient → apply the §7.1 Last Sent/Status writes (dated to the digest's
    own send day, not this run), clear the entry's reported fail-flag lines,
    consume the budget-deferred alerts it carried (outbox-budget#3), and drop it.
    An entry unconfirmed past DIGEST_PENDING_STALE_HOURS is dropped and logged
    loud — its reminders stay unstamped, so they re-fire (fail loud, degrade
    quiet). Confirmed/stale outcomes write the transport log (`baileys`/
    `queued-stale`) dated to the digest's day, grouped per digest so a normal
    morning is one line. Returns rows stamped.

    Because the stamp now lands a run later than the digest, reconcile re-reads
    the Sheet and honors the engine's own write guards: a row the user has since
    completed (Status Done/Skipped) is NOT resurrected, and an entry whose row
    has a dashboard write in flight (§8.3 tombstone) is deferred to the next run
    — never clobbered."""
    # outbox-budget#2 discipline: serialize the whole pending-file
    # read→reconcile→rewrite so a concurrent --send run (manual re-run / future
    # timer overlap) can't double-process or lose a freshly-recorded entry.
    with outbox.pending_lock():
        return _reconcile_locked(now, sheet_path)


def _reconcile_locked(now: datetime, sheet_path: Optional[Path]) -> int:
    pending = outbox.read_pending()
    if not pending:
        return 0
    # Current Sheet state, so a confirmed stamp can't overwrite a completion or
    # recurrence-bump made between queue and confirm (the cross-run clobber).
    current = {r.row: r for r in sheet.read_reminders(sheet_path)}

    by_digest: dict[str, list[dict]] = {}
    for e in pending:
        by_digest.setdefault(e.get("msg_id", ""), []).append(e)

    keep: list[dict] = []
    total_stamped = 0
    for msg_id, entries in by_digest.items():
        digest_date = entries[0].get("digest_date", "")
        confirmed: list[dict] = []
        stale_rcpts: set[str] = set()
        for e in entries:
            rcpt = e.get("recipient", "")
            delivered = any(r.get("to") == rcpt and r.get("status") == "sent"
                            for r in outbox.delivery_status(msg_id))
            if delivered:
                confirmed.append(e)
            elif _pending_age_hours(e, now) > config.DIGEST_PENDING_STALE_HOURS:
                stale_rcpts.add(rcpt)
                print(f"[warn] digest {msg_id} → {rcpt} unconfirmed after "
                      f">{config.DIGEST_PENDING_STALE_HOURS}h — DROPPING the pending stamp; "
                      "its reminders stay unstamped and will re-fire (fail loud)")
            else:
                keep.append(e)  # still inside the horizon — wait for confirmation
        # A dashboard write landing on a confirmed digest's row (§8.3) — defer
        # the whole confirmed set and re-check next run once the tombstone clears.
        if confirmed and any(
                row["row"] in current and engine.is_tombstoned(current[row["row"]], now)
                for e in confirmed for row in e.get("rows", [])):
            keep.extend(confirmed)
            confirmed = []

        writes: list = []
        for e in confirmed:
            sent_at = _digest_sent_at(e, now)
            for row in e.get("rows", []):
                cur = current.get(row["row"])
                if cur is None:
                    continue  # row deleted since the digest — nothing to stamp
                if cur.status in {"Done", "Skipped"}:
                    continue  # user acted on the delivered reminder — keep their state
                stored_due = row.get("due")
                if stored_due is not None and (cur.due is None or cur.due.isoformat() != stored_due):
                    continue  # row rescheduled / recurrence-bumped since queue — don't stamp a stale snapshot
                writes += engine.stamp_cell_writes(row["row"], sent_at, bool(row.get("overdue")))
        total_stamped += _apply_reminder_writes(writes, sheet_path)
        # Settle (clear flag / consume deferred) only after the stamp lands, so a
        # Sheet-write failure retries the whole entry next run instead of
        # half-clearing the flag or losing a deferred alert.
        for e in confirmed:
            _clear_fail_flag(e.get("reported_fail_lines", []))
            outbox.drop_deferred({tuple(k) for k in e.get("deferred_keys", [])})

        try:
            d = date.fromisoformat(digest_date)
        except ValueError:
            d = now.date()
        confirmed_rcpts = {e.get("recipient", "") for e in confirmed}
        if confirmed_rcpts:
            _log_delivery(d, "baileys", confirmed_rcpts)
        if stale_rcpts:
            _log_delivery(d, "queued-stale", stale_rcpts)
    outbox.rewrite_pending(keep)
    return total_stamped


def _read_fail_flag_lines() -> list[str]:
    """Raw non-empty lines of logs/fail.flag — captured once per run so the
    clear can remove exactly what was reported (review 2026-06-12 C1, D-028)."""
    try:
        return [ln for ln in config.FAIL_FLAG.read_text(encoding="utf-8").splitlines()
                if ln.strip()]
    except OSError:
        return []


def read_fail_flag(lines: Optional[list[str]] = None) -> list[str]:
    """Failed unit names from logs/fail.flag — one line per OnFailure= firing
    ("<iso-ts> <unit>", ENGINEERING §5). Sorted unique; [] when absent."""
    src = _read_fail_flag_lines() if lines is None else lines
    return sorted({ln.strip().split()[-1] for ln in src})


def _log_delivery(today: date, transport: str, recipients: set[str]) -> None:
    """One transport line per digest-day: smtp (inline, SPEC §10.2) | baileys
    (reconcile, on confirmation) | queued-stale (queue time when the bridge is
    visibly down, or reconcile when a pending digest is stale-dropped) — review
    2026-06-12 C2, D-028; GAP-2 moved baileys/queued-stale to confirmation time.
    The weekly briefing reads this (per-day) to surface degraded mornings — a
    slowly dying bridge must not hide behind a working fallback."""
    config.DELIVERY_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not config.DELIVERY_LOG.exists()
    with config.DELIVERY_LOG.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "transport", "recipients"])
        w.writerow([today.isoformat(), transport, "|".join(sorted(recipients))])


def run(today: date, dry_run: bool = False, send: bool = False,
        sheet_path: Optional[Path] = None) -> dict[str, str]:
    # The run's clock: wall time normally, 07:30 of the simulated day under
    # --as-of — stamps must carry the day they speak about, or the Last-Sent
    # rerun guard can't see them.
    now = datetime.now() if today == date.today() else datetime.combine(today, time(7, 30))
    # GAP-2: before today's compute, stamp any prior bridge-digests the bridge
    # has since confirmed delivering (and drop the ones it never did). Running
    # first means a just-confirmed row reads as stamped and won't re-fire today.
    if send and not dry_run:
        reconciled = reconcile_deliveries(now, sheet_path)
        if reconciled:
            print(f"reconciled {reconciled} confirmed-delivery stamp(s) from prior digest(s)")
    # Peek the deferred queue — it is consumed only on CONFIRMED delivery
    # (outbox-budget#3): the SMTP path inline, the bridge path at reconcile. An
    # unconfirmed digest leaves its deferred alerts to re-ride the next one.
    deferred = outbox.read_deferred(today)
    fail_lines = _read_fail_flag_lines()
    failed_units = read_fail_flag(fail_lines)
    assembly = assemble(today, now=now, deferred=deferred, sheet_path=sheet_path,
                        failed_units=failed_units)
    messages = assembly.messages
    if dry_run:
        for rcpt, body in messages.items():
            print(f"\n=== to {rcpt} ===\n{body}")
        return messages
    for p in write_briefing_files(messages, today):
        print(f"wrote {p}")
    if send:
        delivered = False
        stale = outbox.heartbeat_age_hours()
        if stale is None or stale > config.EMAIL_FALLBACK_AFTER_HOURS:
            # SPEC §10.2 layer 2: the sender itself degrades — identical
            # content by SMTP instead of queueing rows the bridge can't deliver.
            # send_digest returns True only on a real send, so this IS the
            # confirmation: stamp / consume deferred / clear the flag inline.
            if mailer.send_digest(messages, stale, today):
                hours = "?" if stale is None else f"{stale:.0f}"
                print(f"[email-fallback] bridge down {hours}h — digest delivered by SMTP")
                stamped = stamp_sent(assembly, set(messages), now, sheet_path)
                if stamped:
                    print(f"stamped Last Sent/Status on {stamped} row(s)")
                outbox.pop_deferred(today)  # confirmed → consume what it carried (budget#3)
                _log_delivery(today, "smtp", set(messages))
                _clear_fail_flag(fail_lines)
                return messages
            # Both transports down: queue anyway (bridge delivers on reconnect),
            # shout, and leave the fail flag for a digest that actually lands.
            print("[error] email fallback failed — queueing to the bridge outbox; "
                  "delivery waits for reconnect")
        elif not outbox.bridge_alive():
            print("[warn] bridge heartbeat stale — digest queued, delivery waits for reconnect")
            delivered = True  # <24h blip: queued rows go out on reconnect
        else:
            delivered = True
        msg_id = f"brief-daily-{today.isoformat()}"
        queued_for: set[str] = set()
        for rcpt, body in messages.items():
            # kind=briefing (SPEC §7.2, D-027): budget-exempt, never deferrable —
            # over-budget alerts defer INTO the digest, so the digest itself
            # must be undeferrable or the ledger goes circular.
            res = outbox.queue(rcpt, body, "briefing", source="daily_digest", msg_id=msg_id)
            if res.queued:
                queued_for.add(rcpt)
            print(f"queued → {rcpt}: {len(res.queued)} row(s)"
                  + (f", deferred {res.deferred}" if res.deferred else "")
                  + (f", duplicate {res.duplicates}" if res.duplicates else ""))
        # GAP-2: queueing is NOT delivery. Record a pending entry per recipient;
        # the next run's reconcile stamps Last Sent/Status (+ clears the fail
        # flag, + consumes the deferred this digest carried) once the bridge
        # confirms in whatsapp_sent.jsonl. Stamping on queue let a bridge that
        # dropped its session read "Sent" while the reminder never arrived — the
        # silent loss this closes. No transport line yet on a healthy queue;
        # reconcile logs `baileys` on confirmation.
        with outbox.pending_lock():
            for rcpt in queued_for:
                _record_pending(assembly, rcpt, today, now, deferred, fail_lines, msg_id)
        # A digest queued against a visibly-down bridge (both transports down) is
        # a known-degraded delivery — surface it now (weekly "delivery lagging");
        # reconcile still stamps it later if the bridge reconnects and confirms.
        if queued_for and not delivered:
            _log_delivery(today, "queued-stale", queued_for)
    return messages


def _clear_fail_flag(reported_lines: list[str]) -> None:
    """Reported-in-a-delivered-digest → cleared (ENGINEERING §5). Removes
    exactly the lines that were read at run start: a failure appended WHILE
    this digest was running survives for the next one to report (review
    2026-06-12 C1, D-028). Journald keeps the detail; the flag only exists
    to get a human to look."""
    if not reported_lines:
        return
    try:
        current = [ln for ln in config.FAIL_FLAG.read_text(encoding="utf-8").splitlines()
                   if ln.strip()]
    except OSError:
        return
    remaining = current.copy()
    for ln in reported_lines:
        if ln in remaining:
            remaining.remove(ln)
    if remaining:
        config.FAIL_FLAG.write_text("\n".join(remaining) + "\n", encoding="utf-8")
    else:
        config.FAIL_FLAG.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--dry-run", action="store_true", help="print only, write nothing")
    ap.add_argument("--send", action="store_true",
                    help="queue to the bridge outbox (M3 timers use this)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, dry_run=args.dry_run, send=args.send)


if __name__ == "__main__":
    main()
