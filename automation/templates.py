"""
Family inc. — WhatsApp message copy. ALL phone-bound strings live here so
`DESIGN.md` §6 can be reviewed against one file (session protocol step 3).

M1 note: this copy is the as-built English rendering, frozen byte-for-byte by
`tests/test_render_golden.py`. The DESIGN.md §6 Hebrew v1 templates — and the
removal of reply footers (D-014: never promise an affordance that doesn't
exist) — land together in M2 ("strip reply-command footers"), with a
deliberate golden-file update.
"""
from __future__ import annotations

# --- Daily digest (reminders section) --------------------------------------
DIGEST_HEAD = "🏠 Family inc. — {date}"
DIGEST_QUIET_DAY = "(no reminders today — quiet day.)"
DIGEST_MULTI_INTRO = "You have {n} reminders today:"
DIGEST_ITEM = "{i}. {emoji} {title} — {due_phrase}"
DIGEST_SINGLE_ITEM = "{emoji} {title}  ·  {due_phrase}"
DIGEST_MORE_IN_DASHBOARD = "(+{n} more in the dashboard)"

# Reply affordances — REMOVED in M2 per D-014; kept verbatim until then.
DIGEST_FOOTER_SINGLE = "\n\nReply:  ✅ done    📆 +N days    🤐 mute 30d"
DIGEST_FOOTER_MULTI = "\nReply N ✅ to mark done, or N +D to snooze D days."

DUE_OVERDUE = "overdue by {n} day{s}"
DUE_TODAY = "due today"
DUE_FUTURE = "due in {n} days ({date})"

FLAG_EMOJI = {
    "OVERDUE":    "🔴",
    "FIRE TODAY": "🟠",
    "WEEK OUT":   "🟡",
    "MONTH OUT":  "🟢",
}

# --- Daily digest (assembled sections, SPEC §7.2) ---------------------------
SECTION_DEFERRED = "Held by yesterday's alert budget:"
DEFERRED_ITEM = "• {body}"
HEBCAL_LINE = "🕯 הדלקת נרות {candles} · צאת שבת {havdalah}"

# --- Critical (budget-bypassing, DESIGN §6: single line, no frame) ----------
CRITICAL_LINE = "⚠ {group}: {one_liner} ({sender}, {time})"

# --- Bridge health (prepends, never replaces) --------------------------------
BRIDGE_SILENT = ("⚠ BRIDGE SILENT {hours:.0f}h — baileys_listener may be down "
                 "(check the appliance / re-pair QR)")

# --- Weekly briefing ---------------------------------------------------------
WEEKLY_TITLE = "# 🏠 Family inc. — Weekly Briefing"
WEEKLY_FOOTER = ("\n---\n_Read together with coffee, ~20 minutes. Edits go into "
                 "Family_OS — next week's briefing reflects them automatically._")
