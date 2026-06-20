# Dashboard — Design Log

*One line per design session. Newest at top. The running prototype in this folder is the source of truth; this file is the audit trail of who changed what, when, and why.*

**Format:** `YYYY-MM-DD — Person — change summary (one sentence).`

---

## Log

- **2026-06-20 — Claude (M6.3 finance wiring)** — Money drawer now drops the `Finance-Budget` `TOTAL` row from the budget breakdown — it's a SUM of the categories, so including it doubled the money-summary ₪ totals + KPI, listed a phantom "TOTAL" line, and could over-count over-budget categories; now mirrors the weekly briefing's `section_money`. Added a TOTAL row to `mock_data.json` so DEMO_MODE matches the live tab shape and exercises the guard.
- **2026-06-01 — Adar (post-review)** — Applied DeepSeek's partial review: header date in `renderAll()` routed through `currentLang()` (was hardcoded `en-GB` — the highest-severity miss from this session); `<meta description>` reduced to language-neutral brand; spec drift fixed (`localStorage.familyinc.lang` everywhere). Three concerns defended with tradeoff notes; canonical Gemini review still pending.
- **2026-06-01 — Adar** — Hebrew chrome strings wired end-to-end: STRINGS.he/en table + `t()` helper + `data-i18n`/`-html`/`-placeholder` attribute walker; tabbar, sections, six drawers (contracts → "מנויים וחוזים"), banner, status pill, row buttons (✓ בוצע / + דחה / + הערה), all empty states, Sunday view ("סיכום ראשון" + literal subheads + "7.6 — 14.6" date range), Settings + sign-in + stale-badge + toasts; `duePhrase` now grammar-aware (יום/יומיים/ימים); "שפה / Language" segmented toggle added to Settings (persists to localStorage, reloads).
- **2026-05-30 — Claude (apply Gemini-review resolutions)** — Hebrew chrome default with English toggle (lang/dir flip + pre-paint script); the three new schema columns are referenced from the spec but UI surfacing is the next-session work for Shanee.
- **2026-05-30 — Claude (design refresh from lift recommendations)** — Palette swapped to warm-paper + Linear indigo; Inter+Heebo+Geist Mono added; sticky status pill, big-number+sparkline drawer states, Beeminder bright-line goal viz, "Nothing on fire ☕" empty state, Liquid Glass apple-touch-icon hint.
- **2026-05-28 — Claude (Phase 6 initial build)** — First working PWA: Today/Sunday/Settings tabs, domain drawers, write-back with snooze pills + notes, demo mode + live Sheets-API mode, OAuth setup documented.

---

*Next session: open. Likely candidates — schema-bump UI wiring (LastDoneBy / DoneAt / WriteQueue_Tombstone) or Shanee's pass on the Hebrew copy now that strings are in one place.*
