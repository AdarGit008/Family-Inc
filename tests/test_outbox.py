"""Tests for automation/lib/outbox.py — THE chokepoint (SPEC §7.5, §8.1–8.4).

Covers the ENGINEERING §7 minimum bar: 2-cap, critical bypass, briefing
exemption, shared ledger across two sender sources, (id, target) dedup,
quiet-hours hold.
"""

import json
from datetime import date, datetime

import pytest

from automation.lib import config, outbox


DAY = date(2026, 6, 10)
MORNING = datetime(2026, 6, 10, 9, 30)   # inside send hours
NIGHT = datetime(2026, 6, 10, 23, 15)    # inside quiet hours (22:00–07:00)
EARLY = datetime(2026, 6, 10, 6, 20)     # quiet hours, before 07:00


def _outbox_rows():
    if not config.OUTBOX_FILE.exists():
        return []
    return [json.loads(l) for l in config.OUTBOX_FILE.read_text(encoding="utf-8").splitlines()]


def _events():
    p = config.OUTBOX_LEDGER_DIR / "events.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# Budget: 2/day cap, enforced per recipient at this single chokepoint
# ---------------------------------------------------------------------------
class TestBudget:
    def test_two_alerts_pass_third_defers(self, tmp_runtime):
        for i in range(2):
            res = outbox.queue("adar", f"alert {i}", "alert", msg_id=f"a{i}", now=MORNING)
            assert res.queued and not res.deferred
        res = outbox.queue("adar", "alert 2", "alert", msg_id="a2", now=MORNING)
        assert res.deferred == ["adar"]
        assert not res.queued
        assert len(_outbox_rows()) == 2
        assert outbox.read_ledger(DAY) == {"adar": 2}
        assert any(e["event"] == "alert_suppressed_by_budget" for e in _events())

    def test_corrupt_ledger_fails_closed(self, tmp_runtime, caplog):
        """outbox-budget#1: a torn/corrupt ledger must NOT silently reopen the
        day's cap (fail-OPEN flooded alerts). Fail CLOSED — read as cap-reached,
        so alerts defer (never lost) until the operator inspects + deletes it."""
        import logging
        config.OUTBOX_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        (config.OUTBOX_LEDGER_DIR / f"{DAY.isoformat()}.json").write_text(
            "{ this is not valid json", encoding="utf-8")
        with caplog.at_level(logging.ERROR, logger="outbox"):
            assert outbox.read_ledger(DAY) == {"adar": config.ALERT_BUDGET_PER_DAY,
                                               "shanee": config.ALERT_BUDGET_PER_DAY}
        assert any("CORRUPT" in r.message for r in caplog.records)   # loud for the operator
        res = outbox.queue("adar", "should defer", "alert", msg_id="z1", now=MORNING)
        assert res.deferred == ["adar"] and not res.queued      # deferred, not flooded
        # …but a critical still pierces — a corrupt ledger must never block safety.
        assert outbox.queue("adar", "emergency", "critical", msg_id="z2", now=MORNING).queued

    def test_ledger_is_per_recipient(self, tmp_runtime):
        outbox.queue("adar", "x", "alert", msg_id="a1", now=MORNING)
        outbox.queue("adar", "y", "alert", msg_id="a2", now=MORNING)
        res = outbox.queue("shanee", "z", "alert", msg_id="a3", now=MORNING)
        assert res.queued  # shanee's budget untouched by adar's spend

    def test_shared_ledger_across_sources(self, tmp_runtime):
        """The D-015 fix: engine + summarizer can no longer each spend 2/day."""
        outbox.queue("adar", "engine fire", "alert", source="daily_digest",
                     msg_id="rem-1", now=MORNING)
        outbox.queue("adar", "group alert", "alert", source="whatsapp_summarizer",
                     msg_id="wa-1", now=MORNING)
        res = outbox.queue("adar", "third", "alert", source="whatsapp_summarizer",
                           msg_id="wa-2", now=MORNING)
        assert res.deferred == ["adar"]

    def test_both_splits_when_one_recipient_capped(self, tmp_runtime):
        outbox.queue("adar", "x", "alert", msg_id="a1", now=MORNING)
        outbox.queue("adar", "y", "alert", msg_id="a2", now=MORNING)
        res = outbox.queue("both", "to everyone", "alert", msg_id="b1", now=MORNING)
        assert res.deferred == ["adar"]
        assert len(res.queued) == 1
        assert res.queued[0]["to"] == "shanee"

    def test_deferred_lands_in_tomorrows_digest(self, tmp_runtime):
        outbox.queue("adar", "x", "alert", msg_id="a1", now=MORNING)
        outbox.queue("adar", "y", "alert", msg_id="a2", now=MORNING)
        outbox.queue("adar", "held", "alert", msg_id="a3", now=MORNING)
        # same day: not yet visible
        assert outbox.read_deferred(DAY) == []
        # next morning: visible, then consumed exactly once
        tomorrow = date(2026, 6, 11)
        assert [r["body"] for r in outbox.read_deferred(tomorrow)] == ["held"]
        assert [r["body"] for r in outbox.pop_deferred(tomorrow)] == ["held"]
        assert outbox.pop_deferred(tomorrow) == []


# ---------------------------------------------------------------------------
# Critical: bypasses budget AND quiet hours, with an audit trail
# ---------------------------------------------------------------------------
class TestCritical:
    def test_critical_bypasses_spent_budget(self, tmp_runtime):
        outbox.queue("adar", "x", "alert", msg_id="a1", now=MORNING)
        outbox.queue("adar", "y", "alert", msg_id="a2", now=MORNING)
        res = outbox.queue("adar", "GAN CLOSED", "critical", msg_id="wa-crit", now=MORNING)
        assert res.queued
        assert any(e["event"] == "budget_bypassed_critical" for e in _events())

    def test_critical_ignores_quiet_hours(self, tmp_runtime):
        res = outbox.queue("both", "burst pipe", "critical", msg_id="c1", now=NIGHT)
        assert res.queued
        assert "not_before" not in res.queued[0]

    def test_critical_does_not_consume_budget(self, tmp_runtime):
        outbox.queue("adar", "emergency", "critical", msg_id="c1", now=MORNING)
        assert outbox.read_ledger(DAY).get("adar", 0) == 0


# ---------------------------------------------------------------------------
# Briefings: exempt from budget, held by quiet hours
# ---------------------------------------------------------------------------
class TestBriefing:
    def test_briefings_exempt_from_budget(self, tmp_runtime):
        for i in range(4):
            res = outbox.queue("adar", f"briefing {i}", "briefing",
                               msg_id=f"brief-{i}", now=MORNING)
            assert res.queued
        assert outbox.read_ledger(DAY) == {}

    def test_briefing_held_in_quiet_hours(self, tmp_runtime):
        res = outbox.queue("adar", "weekly", "briefing", msg_id="brief-w", now=NIGHT)
        assert res.queued[0]["not_before"] == "2026-06-11T07:00:00"


# ---------------------------------------------------------------------------
# Quiet hours (SPEC §8.2): 22:00–07:00, alerts hold to 07:00
# ---------------------------------------------------------------------------
class TestQuietHours:
    def test_alert_at_night_holds_to_next_morning(self, tmp_runtime):
        res = outbox.queue("adar", "late alert", "alert", msg_id="a1", now=NIGHT)
        assert res.queued[0]["not_before"] == "2026-06-11T07:00:00"

    def test_alert_before_dawn_holds_to_same_morning(self, tmp_runtime):
        res = outbox.queue("adar", "early alert", "alert", msg_id="a1", now=EARLY)
        assert res.queued[0]["not_before"] == "2026-06-10T07:00:00"

    def test_daytime_alert_has_no_hold(self, tmp_runtime):
        res = outbox.queue("adar", "day alert", "alert", msg_id="a1", now=MORNING)
        assert "not_before" not in res.queued[0]

    def test_is_quiet_hours_window(self):
        assert outbox.is_quiet_hours(datetime(2026, 6, 10, 22, 0))
        assert outbox.is_quiet_hours(datetime(2026, 6, 10, 3, 0))
        assert outbox.is_quiet_hours(datetime(2026, 6, 10, 6, 59))
        assert not outbox.is_quiet_hours(datetime(2026, 6, 10, 7, 0))
        assert not outbox.is_quiet_hours(datetime(2026, 6, 10, 21, 59))


# ---------------------------------------------------------------------------
# Idempotency (SPEC §8.4): (id, target) dedup against queue + sent ledger
# ---------------------------------------------------------------------------
class TestDedup:
    def test_requeue_same_id_is_noop(self, tmp_runtime):
        outbox.queue("adar", "digest", "alert", msg_id="brief-daily-2026-06-10", now=MORNING)
        res = outbox.queue("adar", "digest", "alert", msg_id="brief-daily-2026-06-10", now=MORNING)
        assert res.duplicates == ["adar"]
        assert not res.queued
        assert len(_outbox_rows()) == 1
        # budget charged once, not twice
        assert outbox.read_ledger(DAY) == {"adar": 1}

    def test_dedup_against_sent_ledger(self, tmp_runtime):
        config.SENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.SENT_FILE.write_text(
            json.dumps({"id": "rem-5-2026-06-10", "to": "adar", "status": "sent"}) + "\n",
            encoding="utf-8")
        res = outbox.queue("adar", "already sent", "alert", msg_id="rem-5-2026-06-10", now=MORNING)
        assert res.duplicates == ["adar"]
        assert not res.queued

    def test_both_dedups_per_target(self, tmp_runtime):
        outbox.queue("adar", "x", "alert", msg_id="m1", now=MORNING)
        res = outbox.queue("both", "x", "alert", msg_id="m1", now=MORNING)
        assert res.duplicates == ["adar"]
        assert len(res.queued) == 1
        assert res.queued[0]["to"] == "shanee"


# ---------------------------------------------------------------------------
# Validation + torn-line resilience
# ---------------------------------------------------------------------------
class TestValidation:
    def test_bad_recipient_raises(self, tmp_runtime):
        with pytest.raises(ValueError):
            outbox.queue("savta", "hi", "alert", now=MORNING)

    def test_bad_kind_raises(self, tmp_runtime):
        with pytest.raises(ValueError):
            outbox.queue("adar", "hi", "nudge", now=MORNING)

    def test_empty_body_raises(self, tmp_runtime):
        with pytest.raises(ValueError):
            outbox.queue("adar", "   ", "alert", now=MORNING)

    def test_torn_outbox_line_skipped(self, tmp_runtime):
        config.OUTBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.OUTBOX_FILE.write_text('{"id": "ok", "to": "adar"}\n{"id": "torn', encoding="utf-8")
        res = outbox.queue("adar", "after torn line", "alert", msg_id="new", now=MORNING)
        assert res.queued  # reader skipped the torn tail (SPEC §9)
