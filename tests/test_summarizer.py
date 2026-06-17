"""Tests for automation/whatsapp_summarizer.py — the SPEC §7.3 hard rules,
per-group routing (incl. none → NEEDS-A-LOOK), and the deterministic fallback
that keeps classification working with the API key revoked."""

import re
from datetime import date

from automation import templates as T
from automation.whatsapp_summarizer import (
    build_digest,
    classify,
    deterministic_classify,
    hard_rule_alert,
    load_config,
    load_roster,
    owner_from_recipients,
    resolve_role,
)


def _cfg(**overrides):
    base = {
        "group_type": "daycare",
        "importance_default": "alert_eligible",
        "alert_recipients": "both",
        "close_contacts": [],
        "alert_keywords": [],
        "critical_keywords": [],
    }
    base.update(overrides)
    return {"הגן": base}


def _msg(**overrides):
    base = {
        "msg_id": "t1",
        "group_name": "הגן",
        "sender_name": "מישהי",
        "sender_role": "unknown",
        "received_at": "2026-06-10T12:00:00",
        "text": "סתם הודעה רגילה לגמרי",
        "has_media": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# The 5 hard rules (SPEC §7.3)
# ---------------------------------------------------------------------------
class TestHardRules:
    def test_rule_critical_keyword_bypasses_budget(self):
        cfg = _cfg(critical_keywords=[re.compile("חירום")])
        reason, critical = hard_rule_alert(_msg(text="חירום: הגן סגור מחר"), cfg)
        assert reason and critical is True

    def test_rule_alert_keyword(self):
        cfg = _cfg(alert_keywords=[re.compile("ביטול")])
        reason, critical = hard_rule_alert(_msg(text="שימו לב, ביטול חוגים היום"), cfg)
        assert reason and critical is False

    def test_rule_teacher_evening_window(self):
        cfg = _cfg()
        m = _msg(sender_role="teacher", received_at="2026-06-09T21:30:00",
                 text="מחר להביא כובע")
        reason, _ = hard_rule_alert(m, cfg)
        assert reason == "daycare teacher, evening window"

    def test_teacher_midday_is_not_hard_rule(self):
        cfg = _cfg()
        m = _msg(sender_role="teacher", received_at="2026-06-09T12:30:00",
                 text="תמונות מהיום")
        reason, _ = hard_rule_alert(m, cfg)
        assert reason is None

    def test_rule_vaad_utility(self):
        cfg = _cfg(group_type="building")
        m = _msg(sender_role="vaad_bayit", text="הפסקת מים מחר בבוקר")
        reason, _ = hard_rule_alert(m, cfg)
        assert reason == "vaad bayit utility/maintenance"

    def test_rule_media_only_is_routine_without_llm_call(self):
        cfg = _cfg()
        result = classify(_msg(text="", has_media=True), cfg, recent=[], use_llm=False)
        assert result["classification"] == "ROUTINE"
        assert result["rule"] == "media-only"

    def test_rule_muted_group_never_alerts(self):
        cfg = _cfg(importance_default="mute")
        result = classify(_msg(text="מחר דדליין חשוב!!"), cfg, recent=[], use_llm=False)
        assert result["classification"] == "ROUTINE"
        assert result["reason"] == "muted group"

    def test_hard_rule_forces_alert_class(self):
        cfg = _cfg(alert_keywords=[re.compile("אסיפת הורים")])
        result = classify(_msg(text="אסיפת הורים ביום שני"), cfg, recent=[], use_llm=False)
        assert result["classification"] == "ALERT"
        assert result["action_required"] is True
        assert result["one_liner"]  # fallback one-liner filled in


# ---------------------------------------------------------------------------
# Deterministic fallback (no API key — SPEC §5: value with the key revoked)
# ---------------------------------------------------------------------------
class TestDeterministicFallback:
    def test_actiony_text_becomes_digest(self):
        cfg = _cfg()
        result = deterministic_classify(_msg(text="תזכורת: מחר להביא פרי"), cfg)
        assert result["classification"] == "DIGEST"
        assert result["action_required"] is True

    def test_question_becomes_digest(self):
        cfg = _cfg()
        result = deterministic_classify(_msg(text="מישהו יודע אם יש גן מחר?"), cfg)
        assert result["classification"] == "DIGEST"

    def test_no_signal_is_routine(self):
        cfg = _cfg()
        result = deterministic_classify(_msg(text="איזה כיף היה היום"), cfg)
        assert result["classification"] == "ROUTINE"

    def test_fallback_never_invents_alert(self):
        cfg = _cfg()
        result = classify(_msg(text="דדליין הגשה מחר בערב"), cfg, recent=[], use_llm=False)
        assert result["classification"] == "DIGEST"  # actiony, but not a hard rule


# ---------------------------------------------------------------------------
# digest_only downgrade + routing
# ---------------------------------------------------------------------------
class TestRouting:
    def test_digest_only_group_cannot_self_escalate(self, tmp_runtime, monkeypatch):
        """Without a hard rule, an ALERT classification in a digest_only group
        downgrades to DIGEST (the LLM can't page anyone on its own)."""
        monkeypatch.setenv("FAMILY_INC_LLM_FAKE",
                           '{"classification":"ALERT","one_liner":"דחוף","action_required":true,"reason":"llm"}')
        cfg = _cfg(importance_default="digest_only")
        result = classify(_msg(text="הודעה כלשהי"), cfg, recent=[], use_llm=True)
        assert result["classification"] == "DIGEST"
        assert "downgraded" in result["reason"]

    def test_hard_rule_beats_digest_only_default(self):
        cfg = _cfg(importance_default="digest_only",
                   critical_keywords=[re.compile("פריצה")])
        result = classify(_msg(text="הייתה פריצה בבניין"), cfg, recent=[], use_llm=False)
        assert result["classification"] == "ALERT"
        assert result["critical"] is True

    def test_owner_mapping(self):
        assert owner_from_recipients("both") == "both"
        assert owner_from_recipients("adar") == "adar"
        assert owner_from_recipients("shanee") == "shanee"
        assert owner_from_recipients("none") == "none"
        assert owner_from_recipients("garbage") == "none"

    def test_llm_fake_injection_classifies(self, tmp_runtime, monkeypatch):
        """ENGINEERING §7: lib/llm.py has a fake injected via env — prove the
        whole classify path consumes it without an API key."""
        monkeypatch.setenv("FAMILY_INC_LLM_FAKE",
                           '{"classification":"DIGEST","one_liner":"סיכום קצר","action_required":false,"reason":"fake"}')
        cfg = _cfg()
        result = classify(_msg(text="טקסט חופשי"), cfg, recent=[], use_llm=True)
        assert result["classification"] == "DIGEST"
        assert result["one_liner"] == "סיכום קצר"


# ---------------------------------------------------------------------------
# Digest builder — DESIGN §6 Hebrew section: ⚠ דורש מבט floats first, then
# קבוצות (24ש׳) with Hebrew type labels in fixed group order
# ---------------------------------------------------------------------------
class TestBuildDigest:
    def _row(self, **overrides):
        base = {
            "msg_id": "m1", "group_name": "הגן", "group_type": "daycare",
            "sender_name": "הגננת", "sender_role": "teacher",
            "received_at": "2026-06-10T08:00:00", "text": "מחר טיול",
            "has_media": False, "classification": "DIGEST",
            "one_liner": "מחר טיול", "action_required": True,
            "action_owner": "both", "critical": False, "dispatched": False,
            "dispatched_at": "", "digested_at": "",
        }
        base.update(overrides)
        return base

    def test_unrouted_alert_floats_to_needs_a_look(self):
        rows = [self._row(classification="ALERT", action_owner="none",
                          one_liner="משהו דחוף בקבוצה משפחתית")]
        digest = build_digest(rows, date(2026, 6, 10))
        assert T.WA_NEEDS_A_LOOK in digest
        assert "משהו דחוף" in digest
        # the float happens INSTEAD of a regular listing, not in addition
        assert digest.count("משהו דחוף") == 1

    def test_groups_render_in_fixed_order_with_hebrew_labels(self):
        rows = [
            self._row(msg_id="m1", group_type="building", one_liner="מעלית מושבתת"),
            self._row(msg_id="m2", group_type="daycare", one_liner="יום פירות"),
        ]
        digest = build_digest(rows, date(2026, 6, 10))
        assert digest.index(T.WA_SECTION_HEAD) < digest.index("גן —")
        assert digest.index("גן — יום פירות") < digest.index("ועד — מעלית מושבתת")
        assert "(הגננת, 08:00)" in digest

    def test_routine_rows_not_shown(self):
        rows = [self._row(classification="ROUTINE", one_liner="")]
        digest = build_digest(rows, date(2026, 6, 10))
        assert digest.strip() == ""  # nothing to say → empty section, omitted upstream

    def test_warning_prepends(self):
        digest = build_digest([self._row()], date(2026, 6, 10),
                              warning="⚠ הגשר שקט 14 שעות — ייתכן שפספסנו הודעות")
        assert digest.splitlines()[0].startswith("⚠ הגשר שקט")
        assert T.WA_SECTION_HEAD in digest

    def test_no_reply_footers_anywhere(self):
        """D-014: messages end with content, not instructions."""
        rows = [self._row(), self._row(msg_id="m9", classification="ALERT",
                                       action_owner="none", one_liner="עוד משהו")]
        digest = build_digest(rows, date(2026, 6, 10))
        assert "Reply" not in digest and "השב" not in digest


# ---------------------------------------------------------------------------
# Dispatch — the outbox ledger is the ONLY budget enforcement (D-015), ids
# are stable wa-{msg_id} (SPEC §8.4)
# ---------------------------------------------------------------------------
class TestDispatch:
    def _outbox_rows(self):
        import json
        from automation.lib import config
        if not config.OUTBOX_FILE.exists():
            return []
        return [json.loads(ln) for ln in
                config.OUTBOX_FILE.read_text(encoding="utf-8").splitlines()]

    def _patch_briefings(self, monkeypatch, tmp_path):
        import automation.whatsapp_summarizer as was
        monkeypatch.setattr(was, "BRIEFINGS_DIR", tmp_path / "Briefings")

    def test_alert_queues_with_wa_id_and_kind(self, tmp_runtime, monkeypatch, tmp_path):
        from automation.whatsapp_summarizer import dispatch_alert
        self._patch_briefings(monkeypatch, tmp_path)
        ok = dispatch_alert(_msg(msg_id="m77", text="ביטול חוגים"), "ביטול חוגים היום",
                            "both", "daycare", dry_run=False, critical=False)
        assert ok
        rows = self._outbox_rows()
        assert rows[-1]["id"] == "wa-m77"
        assert rows[-1]["kind"] == "alert"
        assert rows[-1]["body"].startswith("גן: ")

    def test_critical_bypasses_exhausted_budget(self, tmp_runtime, monkeypatch, tmp_path):
        from datetime import datetime
        from automation.lib import outbox
        from automation.whatsapp_summarizer import dispatch_alert
        self._patch_briefings(monkeypatch, tmp_path)
        now = datetime.now()  # same (real) ledger day as dispatch_alert's clock
        outbox.queue("both", "a1", "alert", source="t", msg_id="x1", now=now)
        outbox.queue("both", "a2", "alert", source="t", msg_id="x2", now=now)
        ok = dispatch_alert(_msg(msg_id="m11", text="חירום"), "הגן סגור מחר",
                            "both", "daycare", dry_run=False, critical=True)
        assert ok
        rows = self._outbox_rows()
        assert rows[-1]["kind"] == "critical"
        assert rows[-1]["body"].startswith("⚠ גן: ")

    def test_standard_alert_over_budget_defers_not_queues(self, tmp_runtime,
                                                          monkeypatch, tmp_path):
        from datetime import datetime
        from automation.lib import config, outbox
        from automation.whatsapp_summarizer import dispatch_alert
        self._patch_briefings(monkeypatch, tmp_path)
        # dispatch_alert queues with the real clock — exhaust the budget on
        # the same (real) ledger day.
        now = datetime.now()
        outbox.queue("both", "a1", "alert", source="t", msg_id="x1", now=now)
        outbox.queue("both", "a2", "alert", source="t", msg_id="x2", now=now)
        before = len(self._outbox_rows())
        ok = dispatch_alert(_msg(msg_id="m78", text="עוד משהו"), "עוד אחד",
                            "both", "daycare", dry_run=False, critical=False)
        assert not ok
        assert len(self._outbox_rows()) == before  # nothing queued today
        assert config.DEFERRED_FILE.exists()       # …it rides tomorrow's digest

    def test_dry_run_queues_nothing(self, tmp_runtime, monkeypatch, tmp_path):
        from automation.whatsapp_summarizer import dispatch_alert
        self._patch_briefings(monkeypatch, tmp_path)
        ok = dispatch_alert(_msg(msg_id="m79"), "אחד", "both", "daycare",
                            dry_run=True, critical=False)
        assert not ok and self._outbox_rows() == []


# ---------------------------------------------------------------------------
# Persistence — Inbox/Archive tabs via lib/sheet (no CSVs since M2)
# ---------------------------------------------------------------------------
class TestPersistence:
    def _rows(self):
        return [{
            "msg_id": "m1", "group_name": "הגן", "group_type": "daycare",
            "sender_name": "הגננת", "sender_role": "teacher",
            "received_at": "2026-06-10T08:00:00", "text": "מחר טיול",
            "has_media": False, "classification": "DIGEST",
            "one_liner": "מחר טיול", "action_required": True,
            "action_owner": "both", "critical": False, "dispatched": False,
            "dispatched_at": "", "digested_at": "",
        }]

    def test_persist_and_dedup_roundtrip(self, tmp_path):
        from openpyxl import Workbook
        from automation.whatsapp_summarizer import _processed_ids, persist_rows
        p = tmp_path / "s.xlsx"
        wb = Workbook()
        wb.active.title = "README"
        wb.save(p)
        assert persist_rows(self._rows(), sheet_path=p)
        assert _processed_ids(sheet_path=p) == {"m1"}

    def test_no_live_backend_skips_loudly(self, capsys):
        from automation.whatsapp_summarizer import persist_rows
        assert not persist_rows(self._rows(), sheet_path=None, live_override=False)
        assert "NOT appended" in capsys.readouterr().out

    def test_run_appends_then_rolls_off_old_inbox_rows(self, tmp_runtime, tmp_path):
        """End-to-end of the rolloff wiring (D-044): run() appends this run's
        rows, then rolls the WhatsApp_Inbox 30-day window — an old row already
        in the tab is gone, today's stays. Archive is untouched."""
        import json

        from openpyxl import Workbook
        from automation.lib import sheet
        from automation.whatsapp_summarizer import run

        p = tmp_path / "s.xlsx"
        wb = Workbook(); wb.active.title = "README"; wb.save(p)
        # An old Inbox row, well past the 30-day horizon.
        sheet.append_rows("WhatsApp_Inbox",
                          ["msg_id", "received_at", "text"],
                          [{"msg_id": "old", "received_at": "2026-01-01T08:00:00",
                            "text": "ישן"}], p)

        today = date(2026, 6, 10)  # cutoff = 2026-05-11 → 'old' rolls off
        inbox = tmp_path / "inbox.jsonl"
        inbox.write_text(json.dumps({
            "msg_id": "new", "group_name": "הגן", "sender_name": "מישהי",
            "sender_role": "unknown", "received_at": "2026-06-10T08:00:00",
            "text": "הודעה חדשה", "has_media": False}) + "\n", encoding="utf-8")

        run(inbox, tmp_path / "no_groups.csv", today, dry_run=False,
            sheet_path=p, roster_path=tmp_path / "no_roster.csv")

        ids = sheet.read_column("WhatsApp_Inbox", "msg_id", p)
        assert "new" in ids and "old" not in ids
        # Archive keeps text forever — the old message is NOT rolled off there.
        assert "new" in sheet.read_column("WhatsApp_Archive", "msg_id", p)


# ---------------------------------------------------------------------------
# Group-config CSV loading
# ---------------------------------------------------------------------------
class TestLoadConfig:
    def test_loads_and_compiles(self, tmp_path):
        p = tmp_path / "groups.csv"
        p.write_text(
            "group_name,group_type,importance_default,alert_recipients,close_contacts,alert_keywords,critical_keywords\n"
            "הגן,daycare,alert_eligible,both,הגננת,ביטול;אסיפה,חירום\n",
            encoding="utf-8")
        cfg = load_config(p)
        assert "הגן" in cfg
        g = cfg["הגן"]
        assert g["alert_recipients"] == "both"
        assert [k.pattern for k in g["alert_keywords"]] == ["ביטול", "אסיפה"]
        assert g["critical_keywords"][0].search("חירום בגן")

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_config(tmp_path / "nope.csv") == {}


# ---------------------------------------------------------------------------
# Sender → role roster (M4, D-044): makes hard rules 2–3 reliable when the
# bridge can't label sender_role
# ---------------------------------------------------------------------------
class TestSenderRoster:
    def test_load_keys_on_jid_and_name_skips_blank_role(self, tmp_path):
        p = tmp_path / "roster.csv"
        p.write_text(
            "sender_jid,sender_name,role\n"
            "111@s.whatsapp.net,הגננת,teacher\n"
            ",דני ועד,vaad_bayit\n"
            "222@s.whatsapp.net,,parent\n"
            "333@s.whatsapp.net,ללא תפקיד,\n",   # blank role → skipped
            encoding="utf-8")
        r = load_roster(p)
        assert r["111@s.whatsapp.net"] == "teacher"
        assert r["הגננת"] == "teacher"
        assert r["דני ועד"] == "vaad_bayit"
        assert r["222@s.whatsapp.net"] == "parent"
        assert "333@s.whatsapp.net" not in r

    def test_missing_file_is_empty(self, tmp_path):
        assert load_roster(tmp_path / "nope.csv") == {}

    def test_existing_known_role_wins(self):
        msg = _msg(sender_role="teacher", sender_jid="x", sender_name="y")
        assert resolve_role(msg, {"x": "parent"}) == "teacher"

    def test_unknown_role_filled_from_roster_jid_first(self):
        msg = _msg(sender_role="unknown", sender_jid="j1", sender_name="n1")
        assert resolve_role(msg, {"j1": "vaad_bayit", "n1": "teacher"}) == "vaad_bayit"

    def test_falls_back_to_name_then_unknown(self):
        assert resolve_role(_msg(sender_role="", sender_name="n1"), {"n1": "teacher"}) == "teacher"
        assert resolve_role(_msg(sender_role="unknown", sender_name="ghost"), {}) == "unknown"

    def test_roster_makes_teacher_evening_rule_fire(self):
        """The whole point: a real-traffic message with no role, resolved via
        the roster to 'teacher', trips hard rule 2 in the evening window."""
        roster = {"teacher-jid@s.whatsapp.net": "teacher"}
        msg = _msg(sender_role="unknown", sender_jid="teacher-jid@s.whatsapp.net",
                   received_at="2026-06-09T21:30:00", text="מחר להביא כובע")
        msg["sender_role"] = resolve_role(msg, roster)
        reason, _ = hard_rule_alert(msg, _cfg())  # _cfg() group_type=daycare
        assert reason == "daycare teacher, evening window"
