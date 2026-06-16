"""
Family inc. — WhatsApp message copy. ALL phone-bound strings live here so
`DESIGN.md` §6 can be reviewed against one file (session protocol step 3).

M2: the DESIGN.md §6 Hebrew v1 templates. Register (DESIGN §6): short, warm,
zero exclamation marks, no imperatives toward a person; emoji are semantics,
not decoration; messages end with content, not instructions — the reply
footers are GONE per D-014 (reinstated in v1.1 with reply parsing). Dates as
"יום ו׳ 12/6" (lib/dates.fmt_date_he). Byte-stability is locked by
tests/test_render_golden.py; copy changes re-cut the goldens deliberately.

Copy lines marked [Shanee review] had no literal in DESIGN §6 and were written
to its register — fair game to reword (then regen goldens).
"""
from __future__ import annotations

# --- Daily digest (reminders section, DESIGN §6 template) -------------------
DIGEST_HEAD = "🏠 Family inc. · {date}"
DIGEST_QUIET_DAY = "אין תזכורות להיום — יום שקט."          # [Shanee review]
DIGEST_ITEM = "{emoji} {title} — {due_phrase}"
DIGEST_MORE_IN_DASHBOARD = "+{n} more — בלוח"

# Due phrases — DESIGN §6 wording; singular/dual mirror the dashboard's
# duePhrase() grammar (the two surfaces must read the same).
DUE_OVERDUE_1 = "באיחור יום"
DUE_OVERDUE_2 = "באיחור יומיים"
DUE_OVERDUE_N = "באיחור {n} ימים"
DUE_TODAY = "היום"
DUE_TOMORROW = "מחר"
DUE_IN_2 = "בעוד יומיים"
DUE_IN_N = "בעוד {n} ימים"

FLAG_EMOJI = {
    "OVERDUE":    "🔴",
    "FIRE TODAY": "🟠",
    "WEEK OUT":   "🟡",
    "MONTH OUT":  "🟢",
}

# --- Daily digest (assembled sections, SPEC §7.2) ---------------------------
SECTION_DEFERRED = "נשמרו מאתמול (מכסת הודעות):"            # [Shanee review]
DEFERRED_ITEM = "• {body}"
HEBCAL_LINE = "🕯 הדלקת נרות {candles} · צאת שבת {havdalah}"

# --- WhatsApp groups section (built hourly, folded into the digest) ---------
WA_SECTION_HEAD = "קבוצות (24ש׳):"
WA_ITEM = "{group} — {one_liner} ({sender}, {time})"
WA_NEEDS_A_LOOK = "⚠ דורש מבט"                              # [Shanee review]
WA_NEEDS_A_LOOK_ITEM = "• {one_liner} ({sender}, {time})"

# --- Property tracker section (M5, SPEC §12.1: silent landing in the digest) -
# No DESIGN §6 literal yet — written to the §6 register; the section layout +
# which facets to show is a design call. [Shanee review: head + line shape]
PROPERTY_SECTION_HEAD = "🏠 דירות חדשות"
PROPERTY_ITEM = "{location} — ₪{price}{rooms}{size} ({portal})"
PROPERTY_ROOMS = " · {rooms} חד׳"      # appended only when rooms is known
PROPERTY_SIZE = " · {size} מ״ר"        # appended only when size is known

# --- Alerts (unsolicited, in-budget) and criticals (budget-bypassing) -------
# DESIGN §6: critical is a single line, no frame. The standard alert shares
# the shape minus the warning glyph. [Shanee review: alert shape]
ALERT_LINE = "{group}: {one_liner} ({sender}, {time})"
CRITICAL_LINE = "⚠ {group}: {one_liner} ({sender}, {time})"

# --- Bridge health (prepends, never replaces — DESIGN §6) --------------------
BRIDGE_SILENT = "⚠ הגשר שקט {hours:.0f} שעות — ייתכן שפספסנו הודעות"
FAIL_FLAG_LINE = "⚠ תקלה טכנית הלילה: {units} — נרשם ביומן"   # [Shanee review]

# --- Email fallback (SPEC §10.2 — body note copy is spec'd verbatim) ---------
EMAIL_FALLBACK_SUBJECT = "Family inc. — digest {date} (bridge down)"
EMAIL_FALLBACK_NOTE = "delivered by email — bridge down {hours}h"
EMAIL_SECTION_HEAD = "— {recipient} —"

# --- Weekly briefing ---------------------------------------------------------
# Deterministic fallback copy (SPEC §7.2); the LLM five-scene narrative and a
# Hebrew pass are still open — this stays the as-built English markdown until
# that lane is scheduled.
WEEKLY_TITLE = "# 🏠 Family inc. — Weekly Briefing"
WEEKLY_FOOTER = ("\n---\n_Read together with coffee, ~20 minutes. Edits go into "
                 "Family_OS — next week's briefing reflects them automatically._")
