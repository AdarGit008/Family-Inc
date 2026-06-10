"""Tests for reminders_engine.py — classify, route, apply_budget, is_tombstoned."""

from datetime import date, datetime, timedelta

import pytest

from reminders_engine import (
    Reminder,
    Fire,
    Digest,
    classify,
    route,
    apply_budget,
    is_tombstoned,
    parse_lead_times,
    to_date,
)


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------
class TestClassify:
    def test_none_when_done_status(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "status": "Done"})
        assert classify(r, today) is None

    def test_none_when_skipped_status(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "status": "Skipped"})
        assert classify(r, today) is None

    def test_none_when_no_due_date(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "due": None})
        assert classify(r, today) is None

    def test_fire_today_on_due_date(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "due": today})
        f = classify(r, today)
        assert f is not None
        assert f.reason == "FIRE TODAY"
        assert f.days_until == 0

    def test_overdue_fires(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "due": today - timedelta(days=5)})
        f = classify(r, today)
        assert f is not None
        assert f.reason == "OVERDUE"
        assert f.days_until == -5

    def test_overdue_cooldown_respected(self, today, sample_reminder_kwargs):
        """Overdue items should respect OVERDUE_REPEAT_DAYS (3 days)."""
        r = Reminder(**{
            **sample_reminder_kwargs,
            "due": today - timedelta(days=10),
            "last_sent": today - timedelta(days=2),  # only 2 days ago
        })
        assert classify(r, today) is None

    def test_overdue_fires_after_cooldown(self, today, sample_reminder_kwargs):
        r = Reminder(**{
            **sample_reminder_kwargs,
            "due": today - timedelta(days=10),
            "last_sent": today - timedelta(days=4),  # 4 days ago, past cooldown
        })
        f = classify(r, today)
        assert f is not None
        assert f.reason == "OVERDUE"

    def test_lead_time_fire(self, today, sample_reminder_kwargs):
        """Due in 7 days, lead_time=7 → fires."""
        r = Reminder(**{
            **sample_reminder_kwargs,
            "due": today + timedelta(days=7),
            "lead_times": [7, 1],
        })
        f = classify(r, today)
        assert f is not None
        assert f.reason == "WEEK OUT"
        assert f.days_until == 7

    def test_lead_time_1_day(self, today, sample_reminder_kwargs):
        """Due in 1 day, lead_time=1 → FIRE TODAY (short lead)."""
        r = Reminder(**{
            **sample_reminder_kwargs,
            "due": today + timedelta(days=1),
            "lead_times": [3, 1],
        })
        f = classify(r, today)
        assert f is not None
        assert f.reason == "FIRE TODAY"
        assert f.days_until == 1

    def test_lead_time_month_out(self, today, sample_reminder_kwargs):
        """Due in 14 days, lead_time=14 → MONTH OUT."""
        r = Reminder(**{
            **sample_reminder_kwargs,
            "due": today + timedelta(days=14),
            "lead_times": [14],
        })
        f = classify(r, today)
        assert f is not None
        assert f.reason == "MONTH OUT"

    def test_no_fire_when_not_due_and_no_lead_time(self, today, sample_reminder_kwargs):
        r = Reminder(**{
            **sample_reminder_kwargs,
            "due": today + timedelta(days=20),
            "lead_times": [7, 1],
        })
        assert classify(r, today) is None


# ---------------------------------------------------------------------------
# route
# ---------------------------------------------------------------------------
class TestRoute:
    def test_routes_to_single_owner(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "owner": "Adar", "due": today})
        f = Fire(r, "FIRE TODAY", 0)
        digests = route([f])
        assert "Adar" in digests
        assert len(digests["Adar"].fires) == 1

    def test_routes_both_to_two_recipients(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "owner": "Both", "due": today})
        f = Fire(r, "FIRE TODAY", 0)
        digests = route([f])
        assert "Adar" in digests
        assert "Partner" in digests
        assert len(digests["Adar"].fires) == 1
        assert len(digests["Partner"].fires) == 1

    def test_unknown_owner_defaults_to_adar(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "owner": "UnknownPerson", "due": today})
        f = Fire(r, "FIRE TODAY", 0)
        digests = route([f])
        assert "Adar" in digests
        assert len(digests) == 1

    def test_multiple_fires_for_same_recipient_grouped(self, today, sample_reminder_kwargs):
        r1 = Reminder(**{**sample_reminder_kwargs, "owner": "Adar", "title": "Item 1", "due": today})
        r2 = Reminder(**{**sample_reminder_kwargs, "owner": "Adar", "title": "Item 2", "due": today})
        digests = route([Fire(r1, "FIRE TODAY", 0), Fire(r2, "OVERDUE", -3)])
        assert len(digests["Adar"].fires) == 2


# ---------------------------------------------------------------------------
# apply_budget
# ---------------------------------------------------------------------------
class TestApplyBudget:
    def test_small_digest_passes_through(self, today, sample_reminder_kwargs):
        d = Digest(recipient="Adar")
        r = Reminder(**{**sample_reminder_kwargs, "due": today})
        d.fires = [Fire(r, "FIRE TODAY", 0)]
        apply_budget(d)
        assert len(d.fires) == 1
        assert len(d.dropped) == 0

    def test_trims_to_5(self, today, sample_reminder_kwargs):
        d = Digest(recipient="Adar")
        d.fires = []
        for i in range(8):
            r = Reminder(**{**sample_reminder_kwargs, "title": f"Item {i}", "due": today + timedelta(days=i + 3), "lead_times": [14, 7]})
            d.fires.append(Fire(r, "WEEK OUT", i + 3))
        apply_budget(d)
        assert len(d.fires) == 5
        assert len(d.dropped) == 3

    def test_overdue_always_kept(self, today, sample_reminder_kwargs):
        d = Digest(recipient="Adar")
        # 6 items: 5 OVERDUE + 1 FIRE TODAY. All are "must-keep".
        # The budget trims to 5 total; the last item (FIRE TODAY) gets dropped.
        d.fires = []
        for i in range(5):
            r = Reminder(**{**sample_reminder_kwargs, "title": f"Overdue {i}", "due": today - timedelta(days=i + 1), "last_sent": today - timedelta(days=5)})
            d.fires.append(Fire(r, "OVERDUE", -(i + 1)))
        r_fire = Reminder(**{**sample_reminder_kwargs, "title": "Fire", "due": today})
        d.fires.append(Fire(r_fire, "FIRE TODAY", 0))
        apply_budget(d)
        # 5 kept (all overdue), 1 dropped (fire today — last in list)
        assert len(d.fires) == 5
        assert len(d.dropped) == 1
        assert all(f.reason == "OVERDUE" for f in d.fires)

    def test_health_domain_always_kept(self, today, sample_reminder_kwargs):
        d = Digest(recipient="Adar")
        # 6 MONTH OUT items, one from Health
        d.fires = []
        for i in range(5):
            r = Reminder(**{**sample_reminder_kwargs, "title": f"Item {i}", "domain": "Kids", "due": today + timedelta(days=14), "lead_times": [14]})
            d.fires.append(Fire(r, "MONTH OUT", 14))
        r_health = Reminder(**{**sample_reminder_kwargs, "title": "Vaccine", "domain": "Health", "due": today + timedelta(days=14), "lead_times": [14]})
        d.fires.append(Fire(r_health, "MONTH OUT", 14))
        apply_budget(d)
        # Health + 4 Kids = 5 kept, 1 Kid dropped
        assert len(d.fires) == 5
        kept_domains = {f.reminder.domain for f in d.fires}
        assert "Health" in kept_domains


# ---------------------------------------------------------------------------
# is_tombstoned
# ---------------------------------------------------------------------------
class TestIsTombstoned:
    def test_false_when_no_tombstone(self, now, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "write_queue_tombstone": None})
        assert not is_tombstoned(r, now)

    def test_true_when_recent_tombstone(self, now, sample_reminder_kwargs):
        r = Reminder(**{
            **sample_reminder_kwargs,
            "write_queue_tombstone": now - timedelta(hours=2),
        })
        assert is_tombstoned(r, now)

    def test_false_when_old_tombstone(self, now, sample_reminder_kwargs):
        r = Reminder(**{
            **sample_reminder_kwargs,
            "write_queue_tombstone": now - timedelta(hours=7),
        })
        assert not is_tombstoned(r, now)

    def test_true_when_future_dated_tombstone(self, now, sample_reminder_kwargs):
        """Future-dated tombstones treated as fresh (dashboard clock drift)."""
        r = Reminder(**{
            **sample_reminder_kwargs,
            "write_queue_tombstone": now + timedelta(hours=1),
        })
        assert is_tombstoned(r, now)

    def test_exactly_at_window_boundary(self, now, sample_reminder_kwargs):
        """At exactly 6h, the tombstone is NOT considered fresh (>= window)."""
        r = Reminder(**{
            **sample_reminder_kwargs,
            "write_queue_tombstone": now - timedelta(hours=6),
        })
        assert not is_tombstoned(r, now)


# ---------------------------------------------------------------------------
# parse_lead_times
# ---------------------------------------------------------------------------
class TestParseLeadTimes:
    def test_none_defaults(self):
        assert parse_lead_times(None) == [7, 1]

    def test_single_int(self):
        assert parse_lead_times(14) == [14]

    def test_comma_string(self):
        assert parse_lead_times("14, 7, 1") == [14, 7, 1]

    def test_sorts_descending(self):
        assert parse_lead_times("1, 14, 7") == [14, 7, 1]

    def test_filters_junk(self):
        assert parse_lead_times("7, junk, 14") == [14, 7]

    def test_empty_defaults(self):
        assert parse_lead_times("") == [7, 1]


# ---------------------------------------------------------------------------
# to_date
# ---------------------------------------------------------------------------
class TestToDate:
    def test_python_date_passthrough(self):
        d = date(2026, 6, 1)
        assert to_date(d) == d

    def test_datetime_converted(self):
        from datetime import datetime as dt
        assert to_date(dt(2026, 6, 1, 12, 30)) == date(2026, 6, 1)

    def test_iso_string(self):
        assert to_date("2026-06-15") == date(2026, 6, 15)

    def test_invalid_string_returns_none(self):
        assert to_date("not-a-date") is None

    def test_none_returns_none(self):
        assert to_date(None) is None
