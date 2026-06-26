# v3 Today redesign — build plan (file-level)

> **STATUS (2026-06-25): planning artifact, not canon.** This is the build-level expansion of the `ROADMAP.md` §3.8 lane contract — the way `V3_RECONCILE.md` is the *decision*-level expansion (D1–D8 + tokens). `ROADMAP.md` §3.8 stays the canonical lane contract; `SPEC.md`/`DESIGN.md` stay present-tense and graduate slice-by-slice as each V3.x ships. **No code has been written.** Produced from a 13-agent planning pass (3 code maps → 9 per-slice planners → 1 adversarial critic), then the four hard blockers were verified against the live code. **The build window remains an open PO call** (now vs after the ~07-13 boring-hold).

---

## 0. Read this first — four hard blockers (ALL RESOLVED 2026-06-25)

The slice decomposition is sound and the per-slice contracts are accurate against the real 1515-line `app.js`. The four blockers that made the plan "not buildable as-is" were taken to the PO one-by-one and **decided**:

1. **col-D date format → ISO `YYYY-MM-DD` everywhere** (sheet + dashboard + engine). Rationale: it's already what the dashboard writes (`fmtISO`), `parseDate`'s `new Date(v)` already parses it unambiguously, the engine reads it trivially, and it sorts correctly — the smallest change with the fewest failure modes. *(The rejected DD/MM option would have broken the dashboard reading its own write: verified `new Date('25/06/2026')` → Invalid Date, `'01/02/2026')` → Jan 02 MM/DD.)* **Consequences to apply in V3.3 / Lane C:** keep `parseDate` as-is (already ISO-correct); Lane C pins **ISO** as col-D's canonical format on both read and write; **both** dashboard write surfaces — the snooze write *and* the `handleDone` recurrence bump (`app.js:1248`) — stay on `fmtISO`/ISO via Lane C's helper so col-D never goes mixed-format. The D4 "overdue-snoozed-to-future clears OVERDUE" smoke test (V3.9 #10) then round-trips cleanly. *Open implementation check at Lane C time:* confirm the Sheets API returns col-D as an ISO-parseable string under the he-IL sheet locale (if the column is a real Sheets date displayed DD/MM, store col-D as **plain text** ISO).

2. **Days 3–7 calendar gap → the coming-up strip carries calendar events too**, for the 3–7-day window, tagged with 📆 (emoji-as-semantics keeps reminders vs events distinct). Restores the old "nothing this week vanishes" coverage, reuses a component already being built, and keeps the 3-day calendar focused on today+2. **Consequences to apply:** V3.3's `renderComingUp` ingests **two** sources (WEEK-OUT/MONTH-OUT reminders **+** calendar events 3–7 days out), sorted by date — re-homing the merge V3.3 was dropping from `renderNext7`. V3.4's 3-day strip stays today+2 only (no overlap). Update V3.3 + V3.4 contracts accordingly.

3. **Love-note network exposure → Cloudflare Tunnel.** The box dials out to Cloudflare → a stable public HTTPS URL routing home; no port-forward, no home-IP exposure, TLS handled, a clean CORS target for the Pages PWA. Least operational burden; works from anywhere. **Consequences to apply in V3.7:** add the `cloudflared` tunnel as a deploy/ENGINEERING step + a systemd unit (or Cloudflare-managed connector) alongside `family-lovenote.service`; `love_note_server.py` binds localhost and the tunnel fronts it; CORS allow-origin = the GitHub-Pages origin; and the missing config path is added — a **4th `pages.yml` sed + `DASHBOARD_LOVENOTE_URL` secret + a 4th `test_dashboard_config_smoke.py` anchor** for `LOVENOTE_URL` (feature self-disables when blank, no promised affordance). *(Storage shape — flat JSON vs sqlite, and where voice bytes live — stays a minor V3.7 implementation call.)*

4. **Build window → build the whole lane now.** The boring-hold protects the *alert pipeline + finance bedding-in*, not the dashboard read/write surface; slices land tested + graduation-gated + reversible, and `committed ≠ deployed` (we can merge to `main` and gate the Pages publish). **Consequence:** V3.1 (retone) starts immediately — it is blocker-free and fully specced. **V3.3+ still cannot *complete* until Lane C (col-D, ROADMAP §2 rank-5, gated ~06-26) lands** — that is a real-dependency wait, not a window choice. So the practical order is: V3.1 → V3.2 now; V3.4 / V3.5 / V3.6 (Lane-C-independent) can proceed; V3.3 (snooze) gates on Lane C; V3.7 gates on standing up the tunnel + endpoint.

**Secondary must-fixes (no PO call — applied into the slice contracts):** pill-rewrite + `#banner`-deletion ownership pinned to **V3.2** (V3.3 only feeds `deskCount`); **V3.2 emits the Shabbat data-shape** (a `source==='shabbat'` field on the resolved Calendar-Events row) that V3.4 consumes; **V3.5 deletes the education-drawer markup** (7 drawers exist, not 6).

---

## 1. Cross-cutting build rules

These hold across the whole sequence — agreeing them once prevents mid-sequence churn:

- **Symbol-anchored edits, strict serial build.** 8 of 9 slices edit `dashboard/app.js`; the cited line numbers already drift 0–3 lines vs reality and drift more as slices land. Re-anchor every edit by **symbol name** (`renderAll`, `renderStatusPill`, `parseDate`…), not line number, and build **strictly in order** — no parallel branches, or merge conflicts on `app.js`/`styles.css` are guaranteed.
- **Alias endgame.** V3.1 renames `:root` tokens but keeps **back-compat aliases** (`--card→--tile`, `--border→--line`, `--ink-dim→--muted`, `--orange`/`--yellow→--amber`, `--radius→--rad`, `--blue`). The retone is system-wide (feeds Sunday + Settings + dark), so an alias must survive until its consuming slice migrates its ~40 selector references. **No alias is removed until a final audit confirms zero references.** No slice currently owns this endgame → assign it to V3.8 or V3.9.
- **`--blue` decided once.** `.cal-time` info color (`styles.css:274`) has no V3 home; three slices touch it with different defaults. **Decide in V3.1** (fold→`--accent` or keep a distinct info token), consume downstream.
- **JS test gap is real and accepted-by-plan.** The suite is Python/pytest; all new interactive JS (selection state, batch-write fan-out, bottom-sheet focus-trap, absolute-snooze, love-note fetch) is covered **only** by `node --check` (syntax) + the manual DESIGN §9 smoke. `app.js` crosses the documented ~2000-line JS-harness trigger (ENGINEERING §7) mid-sequence. **Raise a follow-on "JS test harness" lane** before/around V3.3; at minimum add the cheap node checks below.
- **STRINGS namespace agreed once.** `t()` is fail-visible (echoes the dotted key on a he-only/en-only miss). V3.3 and V3.8 both add snooze keys — agree the key namespace (`snooze.*`) once so they don't collide.

---

## 2. The slice sequence (file map + effort)

| Slice | Title | Effort | Hard deps | New files |
|---|---|---|---|---|
| **V3.1** | Token retone (cool palette · IBM Plex Mono all-numerals · AA amber/muted) | S | none | — |
| **V3.2** | Today scaffold + 3-tier status pill (red/amber/sage **+ count**, non-color) | M | V3.1 | — |
| **V3.3** | Select-to-act desk + coming-up strip + **absolute** snooze | L | **Lane C**, V3.2 | — |
| **V3.4** | 3-day scroll-snap calendar strip | M | V3.2 | — |
| **V3.5** | Portfolios + one data-driven **bottom-sheet** (replaces 6/7 accordions) | L | V3.2 | — |
| **V3.6** | Cross-domain **timeline** (exp 1wk→5yr zoom + category filter) | L | V3.5, (V3.3 soft) | — |
| **V3.7** | **Love-notes** — appliance endpoint + UI (text first, voice second) | L | **net-new server + exposure** | `love_note_server.py`, `sweep_love_notes.py`, 3× systemd units, `test_love_note_server.py` |
| **V3.8** | i18n completeness + a11y pass + Settings (add switch-account; drop notif/bank/export) | M | all UI slices | — |
| **V3.9** | Milestone review (`review.py`) + canon graduation + BACKLOG flip | M | all + Lane C | `reviews/session_changes_*_v3-today.md` |

`L–XL` total. Files touched by nearly every slice: `dashboard/{index.html, app.js, styles.css}` + `DESIGN.md`. V3.7 is the only slice with a server/appliance piece.

---

## 3. Per-slice detail

### V3.1 — Token retone  ·  S  ·  deps: none
- **Files:** `styles.css` (retone `:root` + the 4 theme blocks — `@media dark`, `[data-theme=dark]`, `[data-theme=light]`; rename-with-aliases; add `--tile2`/`--soft`/`--rad`/`--rad-sm`/`--sheet-shadow`; swap `--font-mono`→IBM Plex; widen mono to a single `.num`/all-numerals rule) · `index.html` (Google-Fonts link Geist→`IBM+Plex+Mono:wght@400;500;600`; `theme-color` meta `#5E6AD2`→`#2C57C8`; migrate the inline `var(--border,#333)` on `#money-recent-txns`) · `manifest.webmanifest` (`theme_color`/`background_color`) · `DESIGN.md` (§Type + §Palette graduate).
- **New:** the v3 token set + the `.num` all-numerals mono rule (pairs with `unicode-bidi:isolate` on ₪-adjacent amounts).
- **Risks:** alias-vs-rename drift (don't delete an alias before its consumer migrates); IBM Plex digit-width differs from Geist → verify no wrap on the longest ₪ amount + KPI row; iOS caches `theme-color` at install (won't reach installed PWAs until reinstall); dark washes (banner/caught-up/goal-bands/stale-badge rgba in `:root` only) under-contrast after retone — defer to a dark pass but **own it** (see §1).
- **Open calls:** confirm rename-with-aliases (vs big-bang rename now) · `--blue` fold vs keep · ship provisional retoned dark now vs leave dark on old palette · whether `.num` span-tagging in render output is V3.1 or a V3.2 follow-up.
- **Graduates:** DESIGN §Type (IBM Plex / all numerals) + §Palette (cool tokens, AA `--amber #8A5E12` / `--muted #5F6878`). SPEC untouched.

### V3.2 — Scaffold + 3-tier pill  ·  M  ·  deps: V3.1
- **Files:** `index.html` (rewrite `#view-today` skeleton: single tiered pill replacing `#status-pill`+`#banner`; add empty slots `#love-note-slot`/`#calendar-slot`/`#desk`/`#coming-up`/`#portfolios`; keep the 6 `.drawer` blocks inside `#portfolios` so `renderDrawers` stays green this slice) · `app.js` (add `computeCounts()`; rewrite `renderStatusPill`/`setStatusPill` to 3 tiers; **delete `renderBanner` + its `renderAll` call**; add passthrough stub renderers wired to existing logic; new STRINGS he+en; mark `banner.*` deprecated) · `styles.css` (3-tier `.status-pill` via `data-tier` + `.pill-glyph` + mono `.pill-count`; **delete `.banner` block**; minimal empty-slot layout, no shift).
- **New:** StatusPill (tier overdue>today>clear; count; glyph+label non-color; `role=status` `aria-live=polite`; clear is a visible resting state, never hidden) · the Today scaffold slots.
- **Factual correction baked in:** `deskCount` does **not** exist today (D5's "desk already computes deskCount" is forward framing). This slice **creates** the shared `computeCounts()` that V3.3's desk reuses.
- **Open calls:** Sunday-ready = clear-tier label (no 4th tier)? · emoji glyph now vs custom glyph in V3.8 · land the **full** skeleton now (recommended, so V3.3–V3.7 only fill) · pill **loading** treatment between first paint and data (must not read as premature "all clear" — the deleted banner carried `state.loading`).
- **Graduates:** DESIGN §2 "Status banner"+"Sticky status pill" bullets collapse into one "3-tier pill (red/amber/sage + count)"; §4 quiet-day restated against the pill; §9 gains pill checks. SPEC untouched.

### V3.3 — Desk + coming-up + absolute snooze  ·  L  ·  deps: **Lane C**, V3.2
- **Files:** `app.js` (`renderToday`→select-to-act desk w/ batch action bar; `renderNext7`→`renderComingUp`; desk-row variant of `renderReminderRow` minus inline `.actions`/`.snooze-pills`; rewire `attachRowHandlers` from `.expanded`/`.snoozing` accordion to selection; add `handleSnoozeAbsolute` (Due=X) + retire relative `handleSnooze`; add selection + snooze-target to `state`; feed `deskCount` to the pill; STRINGS) · `index.html` (`#next7-list`→`#coming-up` strip; desk batch-action bar + selection-count) · `styles.css` (`.desk-row[.selected]`, `.desk-actionbar` sticky, non-color `.desk-check`, `.coming-up` scroll-snap + `.coming-up-chip`, absolute-date picker) · `DESIGN.md` + `SPEC.md` §6.1 (snooze `Due += N` → `Due = absolute`).
- **New:** Desk (checkbox-semantics rows, keyboard, non-color selection, batch → one `applyWrites` batch) · Desk action bar · Absolute-date snooze picker (chips resolve to **absolute** dates; a future date makes `daysUntil≥0` so `flagFor` is non-OVERDUE — the D4 fix) · Coming-up strip (WEEK-OUT [+ MONTH-OUT?], read-only).
- **Keep unchanged:** `applyWrites`/`enqueueWrites`/`flushQueue` + col-O tombstone-at-flush; `flagFor`/`flagEmoji` (the OVERDUE threshold is load-bearing for the D4 clear).
- **Risks:** **Lane-C ordering is the #1 risk** (writing an unparseable col-D format); clear `state.selection` after every batch + on reload (stale `_row`); batch-Done over recurring rows multiplies the recurrence-bump write set; `app.js` line growth.
- **Open calls:** Lane C col-D format (DD/MM vs ISO vs dual) — **THE gate**, must also fix `parseDate` read side · desk-Note = window.prompt now or defer to V3.5 sheet · coming-up chips read-only vs tap-to-act · MONTH-OUT inclusion (rec: yes) · which absolute presets · confirm V3.2 (not V3.3) deletes `#banner`.
- **Graduates:** DESIGN Today surface (desk, coming-up replacing Next-7, absolute snooze) + §9; SPEC §6.1 snooze line (with Lane C).

### V3.4 — 3-day calendar  ·  M  ·  deps: V3.2
- **Files:** `app.js` (`renderTodayCalendar`→`render3DayCalendar`: widen the `daysBetween(e.date,today)===0` filter to a 0..2 window grouped by day; day-label helper; Shabbat hook; register in `renderAll`) · `index.html` (`#today-cal`→scroll-snap `#today-cal-strip`) · `styles.css` (`.cal-strip` `scroll-snap-type:x mandatory`, `.cal-day` snap-align, `.cal-day-head`, `.cal-event.shabbat` accent; `prefers-reduced-motion`) · `DESIGN.md` §5/§9.
- **New:** `render3DayCalendar` — exactly 3 panes (today,+1,+2), each = day-head + reused `.cal-event` rows; empty pane shows copy (strip never collapses); Shabbat = 🕯 glyph + non-color border; **read-only** (no `data-row`, no writes); RTL snap from `dir=rtl` + logical props only.
- **Coverage-hole note (see §0.2):** this slice renders only d=0,1,2 — days 3–7 events need a home decided before V3.3 drops the Next-7 merge.
- **Risks:** RTL horizontal scroll-snap is WebKit-finicky → **verify snap direction on iOS specifically** (the only real target); always-3-panes empty state must not layout-shift; Shabbat tag is inert unless V3.2 emits the field.
- **Open calls:** what identifies the Shabbat row (`source==='shabbat'`? title token? `Owner='System'`?) — **V3.2 must produce it** · pane geometry (lost-zip; provisional `flex:0 0 calc(100% - 32px)`, 12px gap) · candle/havdalah times on the strip or just a label.
- **Graduates:** DESIGN §5 ("CALENDAR" → 3-day) + §9. SPEC untouched (read-only).

### V3.5 — Portfolios + bottom-sheet  ·  L  ·  deps: V3.2
- **Files:** `index.html` (**delete all drawer blocks incl. education** — 7 exist, not 6; add `#portfolio-grid` of 6 `.tile[data-portfolio]`; add net-new bottom-sheet `#sheet-scrim`+`#sheet` `role=dialog aria-modal`) · `app.js` (`renderDrawers`→`renderPortfolios` (tile faces) + `buildSheet(domain)` (thin switch reusing existing builders) + `openSheet`/`closeSheet` + `state.activeSheet`; tile-viz helpers donut/cat-bar/avatar/goal-bar; **keep** `renderGoalLine`/`renderSparkline`/`renderKpi`/`isSpendTxn` untouched, now called from `buildSheet`) · `styles.css` (delete `.drawer*` rules, **keep** `.kpi`/`.sparkline`/`.kv` relocated under `.tile`/`.sheet`; add `.portfolio-grid`/`.tile`/`.donut`/`.cat-bar`/`.health-avatar`/`.goal-bar` + the bottom-sheet system w/ `0 -8px 40px rgba(18,21,28,.22)` shadow + reduced-motion) · `config.example.js` (no change — flagged so smoke stays green).
- **New:** BottomSheet (one instance, data-driven, never six; Esc/scrim/close, focus-in-on-open + return-on-close, focus-trap, scroll-lock, reduced-motion) · PortfolioTile (button-role, non-color status: Money "N over" ▲, Health day-count) · HealthAvatar (initials **not photo** — no media; 3 non-color urgency buckets).
- **Risks:** focus-trap/scroll-lock is net-new (only current modal is `window.prompt`) — fiddly without a framework, propagates to V3.6; non-color urgency is the easiest invariant to violate (donut/bar/avatar need text+glyph, not just fills); Goals **tile** bar must be simple % (D8 allows it; bright-line stays in the sheet — don't reintroduce the banned >90d bar); an **open sheet during background reload** must rebuild `#sheet-body` from fresh `state.data`.
- **Open calls:** **Education** surface — fold into Timeline category / ride another tile / drop from Today (code retained either way) · tile/sheet geometry (lost-zip; to-contract on `--rad 20px`/`≥44px`/shadows) · Money donut = overall % vs category ring · Timeline placeholder tappable-to-empty vs non-interactive (rec: non-promising per SPEC §3.7).
- **Graduates:** DESIGN §2 (portfolio-tile + single bottom-sheet; Goals tile-bar vs drawer bright-line) + §3 IA. SPEC untouched.

### V3.6 — Cross-domain timeline  ·  L  ·  deps: V3.5 (hard), V3.3 (soft), V3.1
- **Files:** `app.js` (`buildTimelineItems`/`timelineMilestones` predicate/`DOMAIN_CATEGORY` map/`state.timeline`/`renderTimeline` (sheet body) + `renderTimelineTile`; wire into V3.5 dispatch + `renderAll`; zoom/filter via the `attachRowHandlers` delegation; **read-only**) · `index.html` (`#timeline` tile `data-sheet="timeline"` + sheet-body scaffold: zoom strip + filter chips + `#timeline-track`; **no new nav tab**) · `styles.css` (timeline classes on v3 tokens; non-color urgency; reduced-motion) · `DESIGN.md` §3 + `SPEC.md` (milestone rule + Domain→category map graduate) · `config.example.js` (no new key expected).
- **New:** Timeline sheet view (flattens every dated source already in `parseAll` — reminders/cal/goals/health/car/education/contracts; zoom 1wk→5yr; category filter; read-only) · Timeline tile · `DOMAIN_CATEGORY` map + `timelineMilestones()` predicate (the two pure functions that graduate to SPEC).
- **Risks:** **inclusion rule is an unratified open PO call but graduates to SPEC** — V3.6 can't honestly graduate §3.8 until signed; `r.domain` is free-text → unmapped must fall to `other` and still appear (never dropped); de-dup vs the coming-up strip (same row could appear twice); `app.js` size; full re-render on every zoom/filter (fine at household scale, cap if it grows).
- **Open calls:** ratify the milestone-inclusion rule + Domain→category map (signs into SPEC) · zoom rungs + default (rec: 3mo) · accept vertical date-sorted list w/ fixed now-marker as the lost-zip fallback (vs horizontal pixel axis) · resolve **together** with V3.3's MONTH-OUT open call.
- **Graduates:** DESIGN §3 IA (portfolios incl. Timeline, replacing ▸Drawers + Next-7) + SPEC (milestone rule + category map).

### V3.7 — Love-notes  ·  L  ·  deps: net-new server + exposure decision (§0.3)
- **New server files:** `automation/love_note_server.py` (stdlib `ThreadingHTTPServer`; `GET/PUT/DELETE/OPTIONS /lovenote`; verify the dashboard's Google access_token via Google userinfo; email→parent via `Settings.UserMap`; one note per direction under the state dir; 24h-or-on-replace expiry on read; tight CORS to the Pages origin; **never** imports `outbox`, **never** writes the Sheet, **never** logs/persists the token) · `automation/sweep_love_notes.py` (hourly oneshot disk sweep — belt-and-suspenders behind lazy read-expiry) · `deploy/systemd/family-lovenote.service` (long-running, `StateDirectory=family-inc/lovenote` mode 0700) · `family-lovenote-sweep.{service,timer}` (hourly `OnCalendar`, `Persistent=true`).
- **Config/tests:** `automation/lib/config.py` (`LOVENOTE_STATE_DIR` via `FAMILY_INC_LOVENOTE_DIR`, `LOVENOTE_TTL_HOURS=24`, `LOVENOTE_PORT`, `LOVENOTE_ALLOWED_ORIGIN`) · `tests/test_love_note_server.py` (NEW — **explicit negative asserts**: no-outbox-import, no-Sheet-write, **token never persisted**, CORS allowlist, unknown-email 403, lazy + sweep expiry, one-per-direction overwrite) · `tests/conftest.py` (monkeypatch the state dir to tmp) · `dashboard/config.example.js` (`LOVENOTE_URL`) · **`pages.yml` + `test_dashboard_config_smoke.py`** (4th sed + secret + anchor — *currently missing from the slice; required, see §0.3*).
- **UI:** `app.js` (`loadLoveNote`/`renderLoveNote`/`handleSendLoveNote`/`handleClearLoveNote`; voice = phase-2 `MediaRecorder` behind a flag) · `index.html` (inbound card + composer; voice button flag-gated) · `styles.css` (v3 tokens, non-color "new note", RTL) · `ENGINEERING.md` §5 (systemd inventory + the 2nd inbound listener) · `SPEC.md` §4/§6 (voice carve-out graduates **only** when voice ships).
- **Risks:** 2nd inbound listener widens attack surface — strict token-verify + tight CORS; forwarding the token cross-origin is OK only if never logged/stored; no-push means a note can expire unseen (accepted — UI must not imply delivery/seen, SPEC §3.7); **DEMO_MODE can't exercise the inbound card** (`mock_data.json` has no `loveNote`) → add a fixture or V3.9 smoke needs a live 2-account round-trip; committed≠deployed.
- **Open calls — RESOLVED in the build (2026-06-25, text phase shipped):** network exposure → **Cloudflare Tunnel**; auth → **access_token→Google tokeninfo** (opt-in audience check, a review refinement of the userinfo call); storage → **flat JSON per direction** (voice bytes, if/when phase-2 lands, sit beside it); sweep → **hourly** timer behind lazy read-expiry; `LOVENOTE_URL` → **sed-substituted** (4th `pages.yml` sed + 4th smoke anchor, optional secret → feature self-disables when blank). Remaining: the **voice phase** (SPEC §4/§7.7 carve-out — not built).
- **Graduates:** ENGINEERING §5 (units) immediately; DESIGN §9 (smoke); SPEC §4/§6 media carve-out **only** with the voice phase; love-note noted as the sanctioned "one datum neither Sheet nor outbox" exception to §3.1.

### V3.8 — i18n + a11y + Settings  ·  M  ·  deps: all UI slices
- **Files:** `app.js` (~25–40 he+en STRINGS for every new V3 chrome string; `switchAccount()` = real Google sign-out→`prompt:'select_account'` re-auth; extend `renderSettings`/`boot`; a11y helpers; `data-i18n-aria` walker pass) · `index.html` (`#switch-account` button; `aria-label`/`role`/`aria-live` on new controls; **no** notif/bank/export markup) · `styles.css` (`@media (prefers-reduced-motion: reduce)` neutralizing transitions + `.row:active` scale; `:focus-visible` outlines; assert AA on `--amber #8A5E12`/`--muted #5F6878`) · `DESIGN.md` §9 + `SPEC.md` §7.6 (switch-account = real re-auth, never a `currentUser` label-flip).
- **New:** `switchAccount()` (revoke-in-callback recommended so cancel is a no-op; guarantees col-M `LastDoneBy` = actually-signed-in parent; both emails in `Settings.UserMap`) · `data-i18n-aria` walker (makes icon-only buttons named in both langs) · the pill a11y/i18n/contrast acceptance.
- **Risks:** he-only/en-only key echoes the dotted key (fail-visible) — he+en pairing is a hard checklist item; switch-account token-revoke race (prefer revoke-in-callback); JS-driven sheet animation must also check `matchMedia` if it animates via JS not CSS (prefer CSS transitions so the one media block covers all); don't re-pick the AA token values, **assert** them.
- **Open calls:** revoke timing (rec: in-callback) · confirm the love-note slice consumes the aria walker (not hand-rolled) · `--blue` contrast decision feeds this audit · add a `node --check app.js` step to §9 smoke.
- **Graduates:** DESIGN §9 (a11y + bilingual rows + switch-account state) + §6 (new STRINGS canonical); SPEC §7.6 (D3 re-auth, identity = OAuth session); D7 "no notif/bank/export" as a present-tense Settings-scope statement.

### V3.9 — Review + close  ·  M  ·  deps: all + Lane C
- **Files:** `reviews/session_changes_*_v3-today.md` (NEW — the `--changes` input for `review.py`, keyed to D1–D8, **no PII/money**) · `reviews/review_milestone_*.md` (GENERATED audit) · `DESIGN.md` (bump version line; sweep any §2/§3/§4/§5/§8/§9 sections not already graduated; apply Apply-marked findings) · `SPEC.md` (sweep §4/§6/§6.1) · `BACKLOG.md` (flip the v3 line ⬜→✅, cite the audit) · `ROADMAP.md` (§3.8 → graduated/shipped, resolve the lane's open calls) · `V3_RECONCILE.md` (STATUS note; stays a decision record) · `NEXT_SESSION_PROMPT.md` (regenerate via `session_kickoff.py`).
- **§9 smoke additions (9–15):** (9) pill shows correct tier **and count**, red OVERDUE present, never color-only [D5] · (10) overdue snoozed to a **future absolute date** leaves OVERDUE cleared [D4] · (11) one bottom-sheet per domain replaces the accordions; Goals drawer=bright-line, tile=bar [D8] · (12) love-note round-trips text via the endpoint, swept at 24h-or-on-replace, shows on next open with **no push** [D2] · (13) account-switch is real re-auth, col-M stays truthful [D3] · (14) Settings shows no notif/bank/export [D7] · (15) AA holds on both surfaces, RTL default + EN fallback intact, every new STRINGS key he+en.
- **Risks:** review may force a canon edit (love-note auth / voice carve-out) before an honest close — budget triage time, don't rubber-stamp; graduation drift if an earlier slice under-graduated (diff DESIGN/SPEC vs the V3_RECONCILE token block + D1–D8); `app.js` likely crosses ~2000 lines (raise the harness lane); committed≠deployed (dashboard is inert until a Pages publish at HEAD — don't say "live" in BACKLOG until confirmed).
- **Open calls:** **build window** (if still open here, the close is premature) · reviewer model (DeepSeek default vs stronger `--model`) · which findings are joint vs solo · inherited love-note open calls must be closed+documented before §6 graduates · JS harness now vs defer.

---

## 4. Dependency / sequencing map

```
Lane C (col-D format + parseDate read-side)  ─────────┐  (external, NOT a V3 slice)
                                                       ▼
V3.1 retone ─► V3.2 scaffold+pill ─┬─► V3.3 desk+coming-up+ABS-snooze ──┐
                                   ├─► V3.4 3-day calendar               │
                                   └─► V3.5 portfolios+bottom-sheet ─► V3.6 timeline
                                                                         │   (V3.6 soft-deps V3.3 coming-up boundary)
V3.7 love-notes (server + exposure; Sheet-independent, can land in parallel once exposure is decided)
                                                                         ▼
                                          V3.8 i18n + a11y + Settings (closer over ALL surfaces)
                                                                         ▼
                                          V3.9 review + canon graduation + BACKLOG flip
```

- **External injection:** Lane C lands **between V3.2 and V3.3** — it is not a numbered V3 slice. The single biggest sequencing fragility.
- **Ownership pins (decided):** the pill rewrite → **V3.2** (V3.3 only feeds `deskCount`) · the `#banner` deletion → **V3.2** · the Shabbat data-shape → **V3.2 emits** (`source==='shabbat'`), V3.4 consumes.
- **V3.7** is Sheet-independent and can proceed in parallel with the UI slices (exposure = **Cloudflare Tunnel**, decided) — but its UI surface sits inside the V3 Today shell, so land the card/composer after V3.2's scaffold.

---

## 5. Cheap test additions (close the biggest manual-only gaps)

Even without a full JS harness, these are low-cost and high-value:
- **`parseDate` round-trip (node, ~3 lines):** write Lane C's chosen col-D format → `parseDate` → assert a valid Date with correct Y/M/D. Catches the `new Date('25/06/2026')` = Invalid-Date class of bug pre-build.
- **`computeCounts()` equivalence (node):** assert the new shared helper returns the same overdue/today counts the deleted inline sites computed.
- **STRINGS he+en completeness (node):** assert every `STRINGS.he` key exists in `STRINGS.en` and vice-versa. Closes the largest bilingual gap.
- **`test_love_note_server.py` security asserts (pytest):** token-never-persisted + no-outbox-import + no-Sheet-write + CORS allowlist are the load-bearing negatives.
- **Config-smoke 4th anchor:** if `LOVENOTE_URL` becomes a sed target, add its anchor so the test fails loud on a missing substitution.
- **`node --check app.js`** in the DESIGN §9 smoke (config-smoke only checks the *generated config*, not `app.js`).

---

## 6. Consolidated open PO calls (gate the lane)

**The four hard blockers — RESOLVED 2026-06-25 (see §0):**
1. ~~Build window~~ → **build the whole lane now** (V3.3+ still waits on Lane C as a real dependency, not a window choice).
2. ~~Lane C col-D format~~ → **ISO `YYYY-MM-DD`** everywhere; `parseDate` stays as-is; both write surfaces stay ISO via Lane C's helper.
3. ~~Days 3–7 calendar coverage~~ → **the coming-up strip carries calendar events** (3–7d, 📆-tagged).
4. ~~Love-note network exposure~~ → **Cloudflare Tunnel**; + the 4th `pages.yml` sed / `DASHBOARD_LOVENOTE_URL` secret / 4th smoke anchor.

**Answer during the relevant slice (still open):**
5. Education's surface home (Timeline category / another tile / drop) [V3.5].
6. Timeline milestone-inclusion rule + Domain→category map (signs into SPEC) [V3.6], resolved **with** V3.3's MONTH-OUT call.
7. `--blue` token fate (decide in V3.1, consume downstream).
8. JS test harness now vs deferred follow-on lane (app.js crosses ~2000 lines).
9. Voice phase of love-notes (the bounded §4 unfreeze) — ship text-only first; voice is a flagged second phase needing the SPEC §4 edit.

---

*Source: 13-agent planning pass (run `wf_b5ecb72a-ae3`), blockers verified against live code 2026-06-25. Full per-slice agent output (component contracts, a11y invariants, every risk) is in the run transcript; this doc is the synthesized, verified build plan.*
