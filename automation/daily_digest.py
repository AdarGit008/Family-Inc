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

On-send-success Sheet stamping (Last Sent / Status per §7.1) arrives with the
M2 gspread port — there is no write-back against the seed xlsx.

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
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Callable, Optional

from automation import templates as T
from automation import reminders_engine as engine
from automation.lib import config, outbox

# ---------------------------------------------------------------------------
# Reminders section (renderer moved verbatim from the pre-M1 engine;
# byte-stability is locked by tests/test_render_golden.py)
# ---------------------------------------------------------------------------
def due_phrase(f: engine.Fire) -> str:
    if f.days_until < 0:
        return T.DUE_OVERDUE.format(n=-f.days_until, s="s" if f.days_until != -1 else "")
    if f.days_until == 0:
        return T.DUE_TODAY
    return T.DUE_FUTURE.format(n=f.days_until, date=f.reminder.due.isoformat())


def render_digest(d: engine.Digest, today: date) -> str:
    head = T.DIGEST_HEAD.format(date=today.isoformat())
    if not d.fires:
        return f"{head}\n{T.DIGEST_QUIET_DAY}"
    if len(d.fires) == 1:
        f = d.fires[0]
        emoji = T.FLAG_EMOJI.get(f.reason, "•")
        body = f"{head}\n" + T.DIGEST_SINGLE_ITEM.format(
            emoji=emoji, title=f.reminder.title, due_phrase=due_phrase(f))
        if f.reminder.notes:
            body += f"\n{f.reminder.notes}"
        body += T.DIGEST_FOOTER_SINGLE
        return body
    lines = [head, T.DIGEST_MULTI_INTRO.format(n=len(d.fires))]
    for i, f in enumerate(d.fires, 1):
        emoji = T.FLAG_EMOJI.get(f.reason, "•")
        lines.append(T.DIGEST_ITEM.format(
            i=i, emoji=emoji, title=f.reminder.title, due_phrase=due_phrase(f)))
    if d.dropped:
        lines.append("\n" + T.DIGEST_MORE_IN_DASHBOARD.format(n=len(d.dropped)))
    lines.append(T.DIGEST_FOOTER_MULTI)
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


def assemble(today: date, now: Optional[datetime] = None,
             sheet_path: Optional[Path] = None,
             briefings_dir: Optional[Path] = None,
             shabbat_times: Optional[Callable] = _DEFAULT,
             deferred: Optional[list[dict]] = None) -> dict[str, str]:
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
    return messages


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


def run(today: date, dry_run: bool = False, send: bool = False) -> dict[str, str]:
    # Real runs consume the deferred queue; dry runs only peek.
    deferred = outbox.read_deferred(today) if dry_run else outbox.pop_deferred(today)
    messages = assemble(today, deferred=deferred)
    if dry_run:
        for rcpt, body in messages.items():
            print(f"\n=== to {rcpt} ===\n{body}")
        return messages
    for p in write_briefing_files(messages, today):
        print(f"wrote {p}")
    if send:
        if not outbox.bridge_alive():
            print("[warn] bridge heartbeat stale — digest queued, delivery waits for reconnect")
        for rcpt, body in messages.items():
            res = outbox.queue(rcpt, body, "alert", source="daily_digest",
                               msg_id=f"brief-daily-{today.isoformat()}")
            print(f"queued → {rcpt}: {len(res.queued)} row(s)"
                  + (f", deferred {res.deferred}" if res.deferred else "")
                  + (f", duplicate {res.duplicates}" if res.duplicates else ""))
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
