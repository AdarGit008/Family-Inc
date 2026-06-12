"""
Family inc. — Daily digest assembly (SPEC.md §7.2: 07:30 — ONE morning message
per recipient, not several)

Carved out of the engine's send path in M1 (ENGINEERING.md §9). Assembles, in
order: reminders fires (engine compute) · alerts held by yesterday's budget ·
the WhatsApp groups digest (written hourly by whatsapp_summarizer) · a Hebcal
candle-lighting line on Fridays. Renders with `templates.py` copy and writes
one file per recipient to Briefings/; with --send it also queues through
lib/outbox.py (kind=alert per SPEC §7.1, id=brief-daily-{date}).

Until M3 go-live, run WITHOUT --send: files are written, nobody is messaged,
and nothing accumulates in the bridge outbox.

On send success (--send, rows actually queued this run) the digest stamps each
fired row back to the Sheet: Last Sent = now, Status = Sent | Overdue (SPEC
§7.1/§7.2). Stamping is skipped — loudly — when no live backend is configured,
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
from automation.lib import config, outbox, sheet
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


def _hebcal_line(today: date, shabbat_times: Optional[Callable]) -> str:
    """Candle-lighting line on Fridays (SPEC §7.2). Degrades to nothing —
    a missing Hebcal answer must not page anyone."""
    if today.weekday() != 4 or shabbat_times is None:  # 4 = Friday
        return ""
    try:
        st = shabbat_times(today)
    except Exception:
        return ""
    candles, havdalah = st.get("candle_lighting"), st.get("havdalah")
    if not candles or not havdalah:
        return ""
    def hhmm(iso: str) -> str:
        try:
            return datetime.fromisoformat(iso).strftime("%H:%M")
        except ValueError:
            return iso
    return T.HEBCAL_LINE.format(candles=hhmm(candles), havdalah=hhmm(havdalah))


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
             deferred: Optional[list[dict]] = None) -> Assembly:
    """One rendered message per recipient. Pure given its inputs (the Hebcal
    fetcher and the deferred list are injectable so tests stay deterministic
    and dry runs never consume the deferred queue)."""
    if now is None:
        now = datetime.now() if today == date.today() else datetime.combine(today, time(7, 30))
    if shabbat_times is _DEFAULT:
        from automation import hebcal_client
        shabbat_times = hebcal_client.shabbat_times
    briefings_dir = briefings_dir or config.BRIEFINGS_DIR

    result = engine.compute(today, now=now, sheet_path=sheet_path)
    digests = batch_deduplicate(result.digests, now)

    # Quiet day still produces one heartbeat message file for adar (pre-M1
    # behavior preserved): the digest's silence must be distinguishable from
    # the digest being broken.
    if not digests:
        digests = {"adar": engine.Digest(recipient="adar")}

    if deferred is None:
        deferred = outbox.read_deferred(today)
    wa_text = _wa_digest_text(today, briefings_dir)
    hebcal = _hebcal_line(today, shabbat_times)

    messages: dict[str, str] = {}
    for rcpt, d in digests.items():
        parts = [render_digest(d, today)]
        mine = [r for r in deferred if r.get("to") in (rcpt, "both")]
        if mine:
            parts.append("\n".join([T.SECTION_DEFERRED] +
                                   [T.DEFERRED_ITEM.format(body=r["body"]) for r in mine]))
        if wa_text:
            parts.append(wa_text)
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


def stamp_sent(assembly: Assembly, queued_for: set[str], now: datetime,
               sheet_path: Optional[Path] = None) -> int:
    """Write Last Sent/Status for every row that reached at least one phone
    this run (SPEC §7.1 'on send success'). Returns rows stamped. Deferred or
    duplicate targets don't count as sent — their rows stay eligible."""
    fires = [f for rcpt in queued_for
             for f in assembly.digests.get(rcpt, engine.Digest(rcpt)).fires]
    writes = engine.stamp_writes(fires, now)
    if not writes:
        return 0
    if sheet_path is None and not sheet.is_live():
        print("[warn] no live Sheet backend — Last Sent/Status NOT stamped "
              "(refusing to write the seed xlsx)")
        return 0
    sheet.update_reminders(writes, sheet_path)
    return len({w.row for w in writes})


def run(today: date, dry_run: bool = False, send: bool = False,
        sheet_path: Optional[Path] = None) -> dict[str, str]:
    # The run's clock: wall time normally, 07:30 of the simulated day under
    # --as-of — stamps must carry the day they speak about, or the Last-Sent
    # rerun guard can't see them.
    now = datetime.now() if today == date.today() else datetime.combine(today, time(7, 30))
    # Real runs consume the deferred queue; dry runs only peek.
    deferred = outbox.read_deferred(today) if dry_run else outbox.pop_deferred(today)
    assembly = assemble(today, now=now, deferred=deferred, sheet_path=sheet_path)
    messages = assembly.messages
    if dry_run:
        for rcpt, body in messages.items():
            print(f"\n=== to {rcpt} ===\n{body}")
        return messages
    for p in write_briefing_files(messages, today):
        print(f"wrote {p}")
    if send:
        if not outbox.bridge_alive():
            print("[warn] bridge heartbeat stale — digest queued, delivery waits for reconnect")
        queued_for: set[str] = set()
        for rcpt, body in messages.items():
            res = outbox.queue(rcpt, body, "alert", source="daily_digest",
                               msg_id=f"brief-daily-{today.isoformat()}")
            if res.queued:
                queued_for.add(rcpt)
            print(f"queued → {rcpt}: {len(res.queued)} row(s)"
                  + (f", deferred {res.deferred}" if res.deferred else "")
                  + (f", duplicate {res.duplicates}" if res.duplicates else ""))
        stamped = stamp_sent(assembly, queued_for, now, sheet_path)
        if stamped:
            print(f"stamped Last Sent/Status on {stamped} row(s)")
    return messages


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
