"""Tests for automation/whatsapp_summarizer.py — the SPEC §7.3 hard rules,
per-group routing (incl. none → NEEDS-A-LOOK), and the deterministic fallback
that keeps classification working with the API key revoked."""

import re
from datetime import date

from automation.whatsapp_summarizer import (
    build_digest,
    classify,
    deterministic_classify,
    hard_rule_alert,
    load_config,
    owner_from_recipients,
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
# Digest builder — none-routed ALERTs float to NEEDS A LOOK (SPEC §7.3)
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
        assert "⚠ NEEDS A LOOK" in digest
        assert "משהו דחוף" in digest

    def test_groups_render_in_fixed_order(self):
        rows = [
            self._row(msg_id="m1", group_type="building", one_liner="מעלית מושבתת"),
            self._row(msg_id="m2", group_type="daycare", one_liner="יום פירות"),
        ]
        digest = build_digest(rows, date(2026, 6, 10))
        assert digest.index("DAYCARE") < digest.index("BUILDING")

    def test_routine_rows_not_shown(self):
        rows = [self._row(classification="ROUTINE", one_liner="")]
        digest = build_digest(rows, date(2026, 6, 10))
        assert "0 alerts fired" in digest

    def test_warning_prepends(self):
        digest = build_digest([], date(2026, 6, 10), warning="⚠ BRIDGE SILENT 14h")
        assert "BRIDGE SILENT" in digest.splitlines()[2]


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
