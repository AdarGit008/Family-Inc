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
from automation.lib.sheet import read_reminders


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


def _beat(age_hours: float = 0.0):
    """Write a heartbeat whose mtime is `age_hours` in the past (wall clock —
    infra health is never simulated, see outbox.heartbeat_age_hours)."""
    import os
    hb = config.HEARTBEAT_FILE
    hb.parent.mkdir(parents=True, exist_ok=True)
    hb.write_text("beat", encoding="utf-8")
    ts = (datetime.now() - timedelta(hours=age_hours)).timestamp()
    os.utime(hb, (ts, ts))


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
        assert len(rows) == 1 and rows[0]["kind"] == "briefing"

    def test_fresh_bridge_queues_kind_briefing_no_email(self, tmp_runtime,
                                                        make_sheet, fake_smtp):
        _beat()
        p = make_sheet([list(self.ROW)])
        daily_digest.run(DAY, send=True, sheet_path=p)
        assert not FakeSMTP.sent
        rows = _outbox_rows()
        assert len(rows) == 1 and rows[0]["kind"] == "briefing"  # D-027


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

    def test_reported_and_cleared_when_queued(self, tmp_runtime, make_sheet,
                                              fake_smtp):
        _beat()
        _write_flag()
        p = make_sheet([["Car test", "Car", "Adar", DAY, "7,1", "One-off", "Pending"]])
        messages = daily_digest.run(DAY, send=True, sheet_path=p)
        assert "family-backup.service" in messages["adar"]   # prepended line
        assert messages["adar"].index("תקלה") < messages["adar"].index("Car test")
        assert not config.FAIL_FLAG.exists()                 # reported → cleared

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
