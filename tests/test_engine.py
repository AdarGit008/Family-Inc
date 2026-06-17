"""Tests for automation/reminders_engine.py — classify, route, apply_budget,
is_tombstoned (the SPEC §7.1 fire matrix + §8.3 tombstone window), and the M2
write path: recurrence bumps incl. Feb-29, send-success stamping, Last-Sent
idempotency (ENGINEERING §7)."""

import json
from datetime import date, datetime, timedelta

from automation.lib import config, outbox
from automation.lib.sheet import Reminder, read_reminders
from automation.reminders_engine import (
    Digest,
    Fire,
    apply_budget,
    apply_recurrence,
    classify,
    is_tombstoned,
    recurrence_writes,
    route,
    stamp_writes,
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

    def test_last_sent_today_never_refires(self, today, sample_reminder_kwargs):
        """SPEC §8.4: engine re-runs on the same day are no-ops (Last Sent
        guard) — even a due-today row stays quiet once stamped."""
        r = Reminder(**{**sample_reminder_kwargs, "due": today, "last_sent": today})
        assert classify(r, today) is None

    def test_sent_status_keeps_later_lead_times_alive(self, today, sample_reminder_kwargs):
        """Status=Sent (stamped at an earlier lead) must not kill the chain:
        a 30,7,1 reminder stamped at lead-30 still fires at lead-7."""
        r = Reminder(**{
            **sample_reminder_kwargs,
            "due": today + timedelta(days=7),
            "lead_times": [30, 7, 1],
            "status": "Sent",
            "last_sent": today - timedelta(days=23),
        })
        f = classify(r, today)
        assert f is not None and f.reason == "WEEK OUT"


# ---------------------------------------------------------------------------
# route — logical recipient ids (adar/shanee; numbers live only in
# recipients.json on the bridge machine)
# ---------------------------------------------------------------------------
class TestRoute:
    def test_routes_to_single_owner(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "owner": "Adar", "due": today})
        f = Fire(r, "FIRE TODAY", 0)
        digests = route([f])
        assert "adar" in digests
        assert len(digests["adar"].fires) == 1

    def test_routes_both_to_two_recipients(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "owner": "Both", "due": today})
        f = Fire(r, "FIRE TODAY", 0)
        digests = route([f])
        assert "adar" in digests
        assert "shanee" in digests
        assert len(digests["adar"].fires) == 1
        assert len(digests["shanee"].fires) == 1

    def test_legacy_partner_owner_maps_to_shanee(self, today, sample_reminder_kwargs):
        """Pre-remake sheets used 'Partner' — keep parsing them (additive-only)."""
        r = Reminder(**{**sample_reminder_kwargs, "owner": "Partner", "due": today})
        digests = route([Fire(r, "FIRE TODAY", 0)])
        assert "shanee" in digests
        assert len(digests) == 1

    def test_unknown_owner_defaults_to_adar(self, today, sample_reminder_kwargs):
        r = Reminder(**{**sample_reminder_kwargs, "owner": "UnknownPerson", "due": today})
        f = Fire(r, "FIRE TODAY", 0)
        digests = route([f])
        assert "adar" in digests
        assert len(digests) == 1

    def test_multiple_fires_for_same_recipient_grouped(self, today, sample_reminder_kwargs):
        r1 = Reminder(**{**sample_reminder_kwargs, "owner": "Adar", "title": "Item 1", "due": today})
        r2 = Reminder(**{**sample_reminder_kwargs, "owner": "Adar", "title": "Item 2", "due": today})
        digests = route([Fire(r1, "FIRE TODAY", 0), Fire(r2, "OVERDUE", -3)])
        assert len(digests["adar"].fires) == 2


# ---------------------------------------------------------------------------
# apply_budget (digest shaping — the message-count budget lives in lib/outbox)
# ---------------------------------------------------------------------------
class TestApplyBudget:
    def test_small_digest_passes_through(self, today, sample_reminder_kwargs):
        d = Digest(recipient="adar")
        r = Reminder(**{**sample_reminder_kwargs, "due": today})
        d.fires = [Fire(r, "FIRE TODAY", 0)]
        apply_budget(d)
        assert len(d.fires) == 1
        assert len(d.dropped) == 0

    def test_trims_to_5(self, today, sample_reminder_kwargs):
        d = Digest(recipient="adar")
        d.fires = []
        for i in range(8):
            r = Reminder(**{**sample_reminder_kwargs, "title": f"Item {i}", "due": today + timedelta(days=i + 3), "lead_times": [14, 7]})
            d.fires.append(Fire(r, "WEEK OUT", i + 3))
        apply_budget(d)
        assert len(d.fires) == 5
        assert len(d.dropped) == 3

    def test_overdue_always_kept(self, today, sample_reminder_kwargs):
        d = Digest(recipient="adar")
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
        d = Digest(recipient="adar")
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
# stamp_writes — on send success: Last Sent = now, Status = Sent | Overdue
# ---------------------------------------------------------------------------
class TestStampWrites:
    def test_future_fire_stamps_sent(self, now, sample_reminder_kwargs):
        r = Reminder(**sample_reminder_kwargs)
        writes = stamp_writes([Fire(r, "WEEK OUT", 5)], now)
        by_field = {w.field: w.value for w in writes}
        assert by_field["Status"] == "Sent"
        assert by_field["Last Sent"] == now

    def test_overdue_fire_stamps_overdue(self, now, sample_reminder_kwargs):
        r = Reminder(**sample_reminder_kwargs)
        writes = stamp_writes([Fire(r, "OVERDUE", -3)], now)
        assert {w.value for w in writes if w.field == "Status"} == {"Overdue"}

    def test_both_owner_row_stamped_once(self, now, sample_reminder_kwargs):
        """An Owner=Both fire reaches two digests but is ONE sheet row."""
        r = Reminder(**sample_reminder_kwargs)
        f = Fire(r, "FIRE TODAY", 0)
        writes = stamp_writes([f, f], now)
        assert len(writes) == 2  # one Last Sent + one Status


# ---------------------------------------------------------------------------
# recurrence_writes / apply_recurrence — SPEC §7.1 recurrence on Done
# ---------------------------------------------------------------------------
class TestRecurrence:
    def _done(self, kw, **overrides):
        base = {**kw, "status": "Done", "recurrence": "Yearly",
                "due": date(2026, 6, 1), "last_sent": date(2026, 5, 31)}
        base.update(overrides)
        return Reminder(**base)

    def test_done_yearly_bumps(self, now, sample_reminder_kwargs):
        writes = recurrence_writes([self._done(sample_reminder_kwargs)], now)
        by_field = {w.field: w.value for w in writes}
        assert by_field["Due Date"] == date(2027, 6, 1)
        assert by_field["Status"] == "Pending"
        assert by_field["Last Sent"] is None  # cleared per §7.1

    def test_one_off_done_left_alone(self, now, sample_reminder_kwargs):
        r = self._done(sample_reminder_kwargs, recurrence="One-off")
        assert recurrence_writes([r], now) == []

    def test_pending_recurring_left_alone(self, now, sample_reminder_kwargs):
        r = self._done(sample_reminder_kwargs, status="Pending")
        assert recurrence_writes([r], now) == []

    def test_fresh_tombstone_defers_the_bump(self, now, sample_reminder_kwargs):
        """Same race guard as fires: the dashboard may still be writing."""
        r = self._done(sample_reminder_kwargs,
                       write_queue_tombstone=now - timedelta(minutes=30))
        assert recurrence_writes([r], now) == []

    def test_stale_tombstone_allows_the_bump(self, now, sample_reminder_kwargs):
        r = self._done(sample_reminder_kwargs,
                       write_queue_tombstone=now - timedelta(hours=9))
        assert len(recurrence_writes([r], now)) == 3

    def test_custom_recurrence_flagged_not_guessed(self, tmp_runtime, now,
                                                   sample_reminder_kwargs):
        r = self._done(sample_reminder_kwargs, recurrence="Custom")
        assert recurrence_writes([r], now) == []
        flags = [json.loads(ln) for ln in
                 config.ENGINE_FLAGS.read_text(encoding="utf-8").splitlines()]
        assert flags[0]["reason"] == "unbumpable_recurrence"

    def test_feb29_clamps_and_flags(self, tmp_runtime, now, sample_reminder_kwargs):
        r = self._done(sample_reminder_kwargs, due=date(2028, 2, 29))
        writes = recurrence_writes([r], now)
        assert {w.value for w in writes if w.field == "Due Date"} == {date(2029, 2, 28)}
        flags = [json.loads(ln) for ln in
                 config.ENGINE_FLAGS.read_text(encoding="utf-8").splitlines()]
        assert flags[0]["reason"] == "recurrence_clamped_to_month_end"

    def test_apply_recurrence_end_to_end(self, tmp_runtime, make_sheet):
        """Dashboard marked it Done last night; the 07:25 engine run bumps it
        on the sheet — DoneAt/LastDoneBy survive for the arc + ticker."""
        p = make_sheet([[
            "Renew lease", "Contracts", "Both", date(2026, 6, 1), "30,7",
            "Yearly", "Done", datetime(2026, 5, 2, 7, 30), "WhatsApp", "",
            "", "", "Shanee", datetime(2026, 6, 11, 21, 4),
            datetime(2026, 6, 11, 21, 4),
        ]])
        bumped = apply_recurrence(date(2026, 6, 12),
                                  now=datetime(2026, 6, 12, 7, 25), sheet_path=p)
        assert bumped == 1
        r = read_reminders(p)[0]
        assert r.due == date(2027, 6, 1)
        assert r.status == "Pending"
        assert r.last_sent is None
        assert r.last_done_by == "Shanee"          # ticker attribution intact
        assert r.done_at is not None               # arc data intact


# ---------------------------------------------------------------------------
# Send-success stamping, end to end (daily_digest --send against a tmp sheet):
# queue → stamp → rerun is a no-op at every layer (ENGINEERING §7 Last-Sent
# idempotency)
# ---------------------------------------------------------------------------
class TestSendStamping:
    def test_send_stamps_then_rerun_is_noop(self, tmp_runtime, make_sheet):
        from automation import daily_digest

        day = date(2026, 6, 10)  # Wednesday — no Hebcal fetch in assemble()
        # Owner "Both" so the first run briefs BOTH adults — then the rerun is a
        # true no-op even after the quiet-day digest went partner-symmetric
        # (D-036e/D-044): a fully quiet day briefs adar AND shanee, so a row
        # owned by only one of them would leave the other un-briefed and the
        # rerun would (correctly) queue them, which isn't what this test checks.
        p = make_sheet([
            ["Car test", "Car", "Both", day, "7,1", "One-off", "Pending"],
        ])
        messages = daily_digest.run(day, send=True, sheet_path=p)
        assert "Car test" in messages["adar"] and "Car test" in messages["shanee"]

        r = read_reminders(p)[0]
        assert r.status == "Sent"
        assert r.last_sent == day
        first_queue = config.OUTBOX_FILE.read_text(encoding="utf-8").splitlines()
        assert len(first_queue) == 2  # one briefing row per adult

        # Rerun the same morning: the row is stamped (classify guard) and both
        # message ids are spent (outbox dedup) — nothing moves anywhere.
        messages2 = daily_digest.run(day, send=True, sheet_path=p)
        assert "Car test" not in messages2["adar"]  # quiet heartbeat digest
        assert config.OUTBOX_FILE.read_text(encoding="utf-8").splitlines() == first_queue
        assert read_reminders(p)[0].last_sent == day

    def test_overdue_send_stamps_overdue_status(self, tmp_runtime, make_sheet):
        from automation import daily_digest

        day = date(2026, 6, 10)
        p = make_sheet([
            ["Late thing", "Other", "Adar", day - timedelta(days=4), "7,1",
             "One-off", "Pending"],
        ])
        daily_digest.run(day, send=True, sheet_path=p)
        r = read_reminders(p)[0]
        assert r.status == "Overdue"
        assert r.last_sent == day

    def test_send_without_queue_success_does_not_stamp(self, tmp_runtime, make_sheet):
        """If the outbox dedup (or budget) kept the message from queuing,
        the rows must stay eligible — stamping only follows real sends."""
        from automation import daily_digest

        day = date(2026, 6, 10)
        # Spend the digest's message id in advance for both recipients.
        outbox.queue("both", "placeholder", "alert", source="test",
                     msg_id=f"brief-daily-{day.isoformat()}",
                     now=datetime(2026, 6, 10, 7, 0))
        p = make_sheet([
            ["Car test", "Car", "Adar", day, "7,1", "One-off", "Pending"],
        ])
        daily_digest.run(day, send=True, sheet_path=p)
        assert read_reminders(p)[0].last_sent is None


# ---------------------------------------------------------------------------
# Quiet-day digest is partner-symmetric (D-036e/D-044): a day with no fires for
# anyone briefs BOTH adults, each with the quiet-day line + shared sections
# ---------------------------------------------------------------------------
class TestQuietDaySymmetry:
    def test_fully_quiet_day_briefs_both_partners(self, tmp_runtime, make_sheet):
        from automation import daily_digest
        from automation import templates as T

        day = date(2026, 6, 10)  # Wednesday — no Hebcal fetch in assemble()
        asm = daily_digest.assemble(day, sheet_path=make_sheet([]))  # no reminders
        assert set(asm.messages) == {"adar", "shanee"}
        for body in asm.messages.values():
            assert T.DIGEST_QUIET_DAY in body
