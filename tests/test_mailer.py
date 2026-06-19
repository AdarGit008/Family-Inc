"""SPEC §10.2 email fallback + ENGINEERING §5 fail-flag surfacing.

No real SMTP ever: smtplib.SMTP is monkeypatched with a recorder. Heartbeat
age drives the degrade decision; the digest must (a) email the identical
rendered content when the bridge is down >24h, (b) queue kind=briefing
(budget-exempt, D-027) when it isn't, and (c) report + clear logs/fail.flag
only in a digest that actually got delivered.
"""

import smtplib
from datetime import date, datetime, timedelta

import pytest

from automation import daily_digest
from automation.lib import config, mailer, outbox
from automation.lib.sheet import CellWrite, read_reminders, update_reminders


DAY = date(2026, 6, 10)  # Wednesday — no Hebcal fetch in assemble()


class FakeSMTP:
    sent: list = []   # class-level recorder; reset by the fixture
    fail = False

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        if FakeSMTP.fail:
            raise smtplib.SMTPException("server said no")
        FakeSMTP.sent.append(msg)


@pytest.fixture
def fake_smtp(monkeypatch):
    FakeSMTP.sent, FakeSMTP.fail = [], False
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_USER", "appliance@example.com")
    monkeypatch.setenv("SMTP_PASS", "app-password")
    monkeypatch.setenv(config.EMAIL_TO_ENV, "a@example.com, b@example.com")
    return FakeSMTP


def _outbox_rows():
    if not config.OUTBOX_FILE.exists():
        return []
    import json
    return [json.loads(l) for l in
            config.OUTBOX_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]


def _deferred_ids():
    return [r["id"] for r in outbox._jsonl_rows(config.DEFERRED_FILE)]


def _beat(age_hours: float = 0.0):
    """Write a heartbeat whose mtime is `age_hours` in the past (wall clock —
    infra health is never simulated, see outbox.heartbeat_age_hours)."""
    import os
    hb = config.HEARTBEAT_FILE
    hb.parent.mkdir(parents=True, exist_ok=True)
    hb.write_text("beat", encoding="utf-8")
    ts = (datetime.now() - timedelta(hours=age_hours)).timestamp()
    os.utime(hb, (ts, ts))


def _seed_sent(msg_id, recipients, status="sent"):
    """Simulate the Baileys bridge confirming delivery (GAP-2): append the
    SENT_FILE rows it writes on a real send ({id, to, status, at})."""
    import json
    config.SENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.SENT_FILE.open("a", encoding="utf-8") as fh:
        for r in recipients:
            fh.write(json.dumps({"id": msg_id, "to": r, "status": status,
                                 "at": "2026-06-10T07:30:05+03:00"}) + "\n")


# ---------------------------------------------------------------------------
# Heartbeat age (lib/outbox.py)
# ---------------------------------------------------------------------------
class TestHeartbeatAge:
    def test_missing_file_is_none(self, tmp_runtime):
        assert outbox.heartbeat_age_hours() is None

    def test_age_measured_from_mtime(self, tmp_runtime):
        _beat(age_hours=30)
        age = outbox.heartbeat_age_hours()
        assert 29.5 < age < 30.5

    def test_fresh_is_near_zero(self, tmp_runtime):
        _beat()
        assert outbox.heartbeat_age_hours() < 0.1


# ---------------------------------------------------------------------------
# lib/mailer.py
# ---------------------------------------------------------------------------
class TestMailer:
    def test_sends_identical_content_with_note(self, tmp_runtime, fake_smtp):
        ok = mailer.send_digest({"adar": "body-a\n", "shanee": "body-b\n"}, 30.0, DAY)
        assert ok and len(FakeSMTP.sent) == 1
        msg = FakeSMTP.sent[0]
        body = msg.get_content()
        assert "delivered by email — bridge down 30h" in body  # SPEC §10.2 verbatim
        assert "body-a" in body and "body-b" in body
        assert msg["To"] == "a@example.com, b@example.com"
        assert "10/6" in msg["Subject"]

    def test_unknown_staleness_renders_question_mark(self, tmp_runtime, fake_smtp):
        assert mailer.send_digest({"adar": "x"}, None, DAY)
        assert "bridge down ?h" in FakeSMTP.sent[0].get_content()

    def test_missing_creds_returns_false(self, tmp_runtime, fake_smtp, monkeypatch):
        monkeypatch.delenv("SMTP_USER")
        assert mailer.send_digest({"adar": "x"}, 30.0, DAY) is False
        assert not FakeSMTP.sent

    def test_smtp_error_returns_false_never_raises(self, tmp_runtime, fake_smtp):
        FakeSMTP.fail = True
        assert mailer.send_digest({"adar": "x"}, 30.0, DAY) is False

    def test_env_recipients_win_over_settings(self, tmp_runtime, fake_smtp):
        assert mailer.fallback_recipients() == ["a@example.com", "b@example.com"]

    def test_settings_fallback_when_env_unset(self, tmp_runtime, fake_smtp,
                                              monkeypatch):
        monkeypatch.delenv(config.EMAIL_TO_ENV)
        from automation.lib import sheet

        class S:
            usermap = {"x@example.com": "Adar", "y@example.com": "Shanee"}
        monkeypatch.setattr(sheet, "read_settings", lambda: S())
        assert mailer.fallback_recipients() == ["x@example.com", "y@example.com"]

    def test_no_recipients_anywhere_returns_false(self, tmp_runtime, fake_smtp,
                                                  monkeypatch):
        monkeypatch.delenv(config.EMAIL_TO_ENV)
        from automation.lib import sheet
        monkeypatch.setattr(sheet, "read_settings",
                            lambda: (_ for _ in ()).throw(RuntimeError("down")))
        assert mailer.send_digest({"adar": "x"}, 30.0, DAY) is False


# ---------------------------------------------------------------------------
# Digest degrade path (SPEC §10.2) + kind=briefing (D-027)
# ---------------------------------------------------------------------------
class TestDigestDegrade:
    ROW = ["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]

    def test_stale_bridge_emails_stamps_and_skips_queue(self, tmp_runtime,
                                                        make_sheet, fake_smtp):
        _beat(age_hours=30)  # > EMAIL_FALLBACK_AFTER_HOURS
        p = make_sheet([list(self.ROW)])
        messages = daily_digest.run(DAY, send=True, sheet_path=p)
        assert "Car test" in messages["adar"]
        assert len(FakeSMTP.sent) == 1
        assert "Car test" in FakeSMTP.sent[0].get_content()  # identical content
        assert _outbox_rows() == []                          # nothing queued
        assert read_reminders(p)[0].status == "Sent"         # stamped anyway

    def test_no_heartbeat_ever_also_degrades(self, tmp_runtime, make_sheet,
                                             fake_smtp):
        p = make_sheet([list(self.ROW)])
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert len(FakeSMTP.sent) == 1

    def test_smtp_down_too_falls_back_to_queue(self, tmp_runtime, make_sheet,
                                               fake_smtp):
        FakeSMTP.fail = True
        _beat(age_hours=30)
        p = make_sheet([list(self.ROW)])
        daily_digest.run(DAY, send=True, sheet_path=p)
        rows = _outbox_rows()
        # D-045: an Adar-only fire still briefs BOTH adults — two briefing rows
        # (adar's fire + shanee's quiet-day), both budget-exempt (D-027).
        assert len(rows) == 2
        assert all(r["kind"] == "briefing" for r in rows)
        assert {r["to"] for r in rows} == {"adar", "shanee"}

    def test_fresh_bridge_queues_kind_briefing_no_email(self, tmp_runtime,
                                                        make_sheet, fake_smtp):
        _beat()
        p = make_sheet([list(self.ROW)])
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert not FakeSMTP.sent
        rows = _outbox_rows()
        # D-027: kind=briefing (budget-exempt). D-045: both adults briefed, so
        # two rows (adar's fire + shanee's quiet-day), neither via email.
        assert len(rows) == 2
        assert all(r["kind"] == "briefing" for r in rows)
        assert {r["to"] for r in rows} == {"adar", "shanee"}


# ---------------------------------------------------------------------------
# Fail flag (ENGINEERING §5): reported + cleared by a DELIVERED digest only
# ---------------------------------------------------------------------------
def _write_flag():
    config.FAIL_FLAG.parent.mkdir(parents=True, exist_ok=True)
    config.FAIL_FLAG.write_text(
        "2026-06-10T03:00:01+03:00 family-backup.service\n"
        "2026-06-10T04:00:02+03:00 family-summarizer.service\n"
        "2026-06-10T05:00:02+03:00 family-summarizer.service\n",
        encoding="utf-8")


class TestFailFlag:
    def test_parse_sorted_unique(self, tmp_runtime):
        _write_flag()
        assert daily_digest.read_fail_flag() == [
            "family-backup.service", "family-summarizer.service"]

    def test_reported_and_cleared_when_confirmed(self, tmp_runtime, make_sheet,
                                                 fake_smtp):
        _beat()
        _write_flag()
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        messages = daily_digest.run(DAY, send=True, sheet_path=p)
        assert "family-backup.service" in messages["adar"]   # prepended line (reported)
        assert messages["adar"].index("תקלה") < messages["adar"].index("Car test")
        # GAP-2: the bridge digest is only queued, not yet confirmed — the flag
        # must NOT clear until a digest actually lands (fail loud).
        assert config.FAIL_FLAG.exists()
        # Bridge confirms → the next run's reconcile clears exactly the reported lines.
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar", "shanee"])
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert not config.FAIL_FLAG.exists()                 # reported in a delivered digest → cleared

    def test_reported_and_cleared_when_emailed(self, tmp_runtime, make_sheet,
                                               fake_smtp):
        _beat(age_hours=30)
        _write_flag()
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert "family-backup.service" in FakeSMTP.sent[0].get_content()
        assert not config.FAIL_FLAG.exists()

    def test_kept_when_nothing_delivered(self, tmp_runtime, make_sheet, fake_smtp):
        FakeSMTP.fail = True
        _beat(age_hours=30)   # bridge down AND smtp down
        _write_flag()
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert config.FAIL_FLAG.exists()                     # waits for a digest that lands

    def test_weekly_briefing_surfaces_uncleared_flag(self, tmp_runtime):
        _write_flag()
        from automation.weekly_briefing import _system_flags
        issues = _system_flags()
        assert any("family-backup.service" in i for i in issues)


# ---------------------------------------------------------------------------
# Review 2026-06-12 applies (D-028): race-safe clear + transport observability
# ---------------------------------------------------------------------------
class TestReviewD028:
    ROW = ["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]

    def test_clear_preserves_lines_appended_during_run(self, tmp_runtime):
        """A unit failing WHILE the digest runs must survive to the next one —
        the clear removes exactly the reported lines, not the whole file."""
        _write_flag()
        lines = daily_digest._read_fail_flag_lines()
        with config.FAIL_FLAG.open("a", encoding="utf-8") as f:
            f.write("2026-06-10T07:30:01+03:00 family-engine-late.service\n")
        daily_digest._clear_fail_flag(lines)
        kept = config.FAIL_FLAG.read_text(encoding="utf-8").strip().splitlines()
        assert kept == ["2026-06-10T07:30:01+03:00 family-engine-late.service"]

    def test_clear_removes_file_when_all_reported(self, tmp_runtime):
        _write_flag()
        daily_digest._clear_fail_flag(daily_digest._read_fail_flag_lines())
        assert not config.FAIL_FLAG.exists()

    def test_delivery_log_baileys_on_confirm_and_rerun_adds_nothing(self, tmp_runtime,
                                                                    make_sheet, fake_smtp):
        _beat()
        # Owner "Both" so the first run briefs both adults; the rerun is then a
        # true no-op even after the quiet-day digest went partner-symmetric
        # (D-036e/D-044) — an adar-only row would leave the quiet rerun briefing
        # shanee for the first time, which is correct but not what this checks.
        p = make_sheet([["Car test", "Car", "Both", DAY, "7,1", "One-off", "Pending"]])
        daily_digest.run(DAY, send=True, sheet_path=p)
        # GAP-2: a healthy queue is unconfirmed — no transport line yet.
        assert not config.DELIVERY_LOG.exists()
        # Bridge confirms → the next run's reconcile logs one `baileys` line
        # (both recipients) dated to the digest day.
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar", "shanee"])
        daily_digest.run(DAY, send=True, sheet_path=p)
        rows = config.DELIVERY_LOG.read_text(encoding="utf-8").strip().splitlines()
        assert rows[0] == "date,transport,recipients"
        assert rows[1] == f"{DAY.isoformat()},baileys,adar|shanee"
        daily_digest.run(DAY, send=True, sheet_path=p)  # nothing pending, dedup: adds nothing
        assert len(config.DELIVERY_LOG.read_text(encoding="utf-8").strip().splitlines()) == 2

    def test_delivery_log_smtp_on_fallback(self, tmp_runtime, make_sheet, fake_smtp):
        _beat(age_hours=30)
        p = make_sheet([list(self.ROW)])
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert f"{DAY.isoformat()},smtp," in config.DELIVERY_LOG.read_text(encoding="utf-8")

    def test_delivery_log_queued_stale_when_both_transports_down(self, tmp_runtime,
                                                                 make_sheet, fake_smtp):
        FakeSMTP.fail = True
        _beat(age_hours=30)
        p = make_sheet([list(self.ROW)])
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert f"{DAY.isoformat()},queued-stale," in config.DELIVERY_LOG.read_text(encoding="utf-8")

    def _seed_log(self, *rows):
        config.DELIVERY_LOG.parent.mkdir(parents=True, exist_ok=True)
        config.DELIVERY_LOG.write_text(
            "date,transport,recipients\n" + "".join(r + "\n" for r in rows),
            encoding="utf-8")

    def test_weekly_surfaces_smtp_days_as_degraded(self, tmp_runtime):
        self._seed_log(
            f"{(DAY - timedelta(days=2)).isoformat()},smtp,adar|shanee",
            f"{(DAY - timedelta(days=1)).isoformat()},baileys,adar|shanee")
        from automation.weekly_briefing import _system_flags
        assert any("bridge degraded" in i for i in _system_flags(DAY))

    def test_weekly_quiet_when_all_baileys(self, tmp_runtime):
        self._seed_log(f"{(DAY - timedelta(days=1)).isoformat()},baileys,adar|shanee")
        from automation.weekly_briefing import _system_flags
        assert not [i for i in _system_flags(DAY) if "degraded" in i or "lagging" in i]

    def test_weekly_ignores_rows_older_than_window(self, tmp_runtime):
        self._seed_log(f"{(DAY - timedelta(days=30)).isoformat()},smtp,adar|shanee")
        from automation.weekly_briefing import _system_flags
        assert not [i for i in _system_flags(DAY) if "degraded" in i]


# ---------------------------------------------------------------------------
# GAP-2 cross-run reconcile: stale-drop (fail loud) + outbox-budget#3 (a
# budget-deferred alert is consumed only after the carrying digest is confirmed)
# ---------------------------------------------------------------------------
class TestReconcileGAP2:
    def _pending(self, hours_ago, now, **over):
        entry = {
            "msg_id": f"brief-daily-{DAY.isoformat()}",
            "digest_date": DAY.isoformat(),
            "recipient": "adar",
            "rows": [{"row": 2, "overdue": False}],
            "deferred_keys": [],
            "reported_fail_lines": [],
            "queued_at": (now - timedelta(hours=hours_ago)).isoformat(timespec="seconds"),
        }
        entry.update(over)
        outbox.record_pending(entry)

    def test_stale_pending_dropped_logged_not_stamped(self, tmp_runtime, make_sheet, capsys):
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        now = datetime(2026, 6, 10, 7, 30)
        self._pending(49, now)                                # > 48h horizon, never confirmed
        stamped = daily_digest.reconcile_deliveries(now, sheet_path=p)
        assert stamped == 0                                   # nothing confirmed → nothing stamped
        assert read_reminders(p)[0].last_sent is None         # reminder stays eligible → re-fires
        assert outbox.read_pending() == []                    # dropped
        assert "DROPPING" in capsys.readouterr().out          # logged loud
        assert f"{DAY.isoformat()},queued-stale," in config.DELIVERY_LOG.read_text(encoding="utf-8")

    def test_within_horizon_pending_kept(self, tmp_runtime, make_sheet):
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        now = datetime(2026, 6, 10, 7, 30)
        self._pending(10, now)                                # 10h < 48h: still waiting
        assert daily_digest.reconcile_deliveries(now, sheet_path=p) == 0
        assert len(outbox.read_pending()) == 1                # kept
        assert not config.DELIVERY_LOG.exists()               # neither confirmed nor stale yet

    def test_deferred_consumed_only_on_confirmed_digest(self, tmp_runtime, make_sheet,
                                                        fake_smtp):
        _beat()
        # An alert deferred yesterday is due to ride today's digest (SPEC §7.5).
        outbox._append_deferred({
            "id": "wa-xyz", "to": "adar", "body": "deferred alert body",
            "source": "summarizer", "deferred_on": (DAY - timedelta(days=1)).isoformat(),
        })
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        messages = daily_digest.run(DAY, send=True, sheet_path=p)
        assert "deferred alert body" in messages["adar"]      # rode the digest
        # Unconfirmed: NOT consumed — it re-rides the next digest (budget#3).
        assert "wa-xyz" in _deferred_ids()
        # Bridge confirms the carrying digest → reconcile consumes it.
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar", "shanee"])
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert "wa-xyz" not in _deferred_ids()

    def test_deferred_consumed_per_recipient_on_confirm(self, tmp_runtime, make_sheet,
                                                        fake_smtp):
        """budget#3 is per-recipient: confirming adar's digest consumes only the
        alert adar's digest carried, not shanee's still-undelivered one."""
        _beat()
        for who in ("adar", "shanee"):
            outbox._append_deferred({
                "id": f"wa-{who}", "to": who, "body": f"for {who}", "source": "summarizer",
                "deferred_on": (DAY - timedelta(days=1)).isoformat(),
            })
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        daily_digest.run(DAY, send=True, sheet_path=p)
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar"])   # only adar confirmed
        daily_digest.run(DAY, send=True, sheet_path=p)
        ids = _deferred_ids()
        assert "wa-adar" not in ids       # adar's digest confirmed → its deferred consumed
        assert "wa-shanee" in ids         # shanee unconfirmed → hers re-rides next digest

    def test_non_sent_status_does_not_confirm(self, tmp_runtime, make_sheet):
        """A SENT_FILE row with status send_failed / refused_unknown_recipient is
        NOT a delivery — reconcile must not stamp; a real 'sent' row later does."""
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        now = datetime(2026, 6, 10, 7, 30)
        self._pending(1, now)                                    # adar, row 2, 1h ago
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar"], status="send_failed")
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar"], status="refused_unknown_recipient")
        assert daily_digest.reconcile_deliveries(now, sheet_path=p) == 0
        assert read_reminders(p)[0].last_sent is None            # not stamped
        assert len(outbox.read_pending()) == 1                   # kept (within horizon)
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar"])   # a real delivery
        assert daily_digest.reconcile_deliveries(now, sheet_path=p) == 1
        assert read_reminders(p)[0].last_sent == DAY
        assert outbox.read_pending() == []

    def test_single_recipient_confirm_leaves_other_pending(self, tmp_runtime, make_sheet,
                                                           fake_smtp):
        """Owner Adar: the row rides adar's digest; shanee gets the quiet-day
        briefing. Confirming shanee's leg must NOT stamp adar's reminder (the
        shared brief-daily-{date} msg_id is discriminated per-recipient)."""
        _beat()
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        daily_digest.run(DAY, send=True, sheet_path=p)
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["shanee"])  # only shanee confirmed
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert read_reminders(p)[0].last_sent is None             # adar's row NOT stamped
        assert {e["recipient"] for e in outbox.read_pending()} == {"adar"}  # shanee settled, adar waits
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar"])
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert read_reminders(p)[0].last_sent == DAY              # adar confirmed → stamped
        assert outbox.read_pending() == []

    def test_confirm_does_not_resurrect_completed_reminder(self, tmp_runtime, make_sheet,
                                                           fake_smtp):
        """Blocker regression: the stamp now lands a run after queue, so a row the
        user marks Done between queue and confirm must NOT be clobbered to Sent."""
        _beat()
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        daily_digest.run(DAY, send=True, sheet_path=p)            # queues, unstamped
        update_reminders([CellWrite(2, "Status", "Done")], p)    # user completes it in the dashboard
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar", "shanee"])
        daily_digest.run(DAY, send=True, sheet_path=p)            # reconcile must respect the Done
        r = read_reminders(p)[0]
        assert r.status == "Done"                                 # not resurrected to Sent
        assert r.last_sent is None
        assert outbox.read_pending() == []                        # digest WAS delivered → entry settled

    def test_confirm_does_not_stamp_rescheduled_row(self, tmp_runtime, make_sheet, fake_smtp):
        """A row whose Due moved (reschedule / recurrence bump) between queue and
        confirm is not stamped from the stale queue-time snapshot."""
        _beat()
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        daily_digest.run(DAY, send=True, sheet_path=p)            # queued with due=DAY
        update_reminders([CellWrite(2, "Due Date", DAY + timedelta(days=14))], p)  # rescheduled
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar", "shanee"])
        daily_digest.run(DAY, send=True, sheet_path=p)
        r = read_reminders(p)[0]
        assert r.last_sent is None                               # not stamped (row moved)
        assert r.status == "Pending"                             # untouched
        assert outbox.read_pending() == []                       # digest delivered → entry settled

    def test_stamp_dated_to_digest_day_not_reconcile_day(self, tmp_runtime, make_sheet):
        """No +1-day skew: a digest queued on DAY but confirmed two days later
        stamps Last Sent = DAY (the real send day), not the reconcile day."""
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        self._pending(0, datetime(2026, 6, 10, 7, 30))            # queued_at = DAY 07:30
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar"])
        later = datetime(2026, 6, 12, 7, 30)                      # reconcile two days on
        assert daily_digest.reconcile_deliveries(later, sheet_path=p) == 1
        assert read_reminders(p)[0].last_sent == DAY

    def test_tombstoned_row_defers_confirmed_stamp(self, tmp_runtime, make_sheet):
        """A dashboard write in flight (§8.3) on a confirmed digest's row defers
        the stamp to the next run rather than racing it."""
        from datetime import timedelta as _td
        now = datetime(2026, 6, 10, 7, 30)
        # Row carries a fresh tombstone (write landing within the 6h window).
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending", "",
                         "WhatsApp", "", "", "", "", "", (now - _td(hours=1)).isoformat()]])
        self._pending(1, now)
        _seed_sent(f"brief-daily-{DAY.isoformat()}", ["adar"])
        assert daily_digest.reconcile_deliveries(now, sheet_path=p) == 0  # deferred, not stamped
        assert len(outbox.read_pending()) == 1                            # kept for next run
        assert read_reminders(p)[0].last_sent is None
