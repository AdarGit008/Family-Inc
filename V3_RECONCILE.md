# v3 Today redesign — reconcile sheet

> **STATUS (2026-06-25): decisions locked; folded into `ROADMAP.md` §3.8** (the forward-lane home — the redesign is decided but unbuilt, and per the 5-doc canon discipline `SPEC.md`/`DESIGN.md` stay present-tense and **graduate slice-by-slice as V3.x ships**). Status line in `BACKLOG.md`. This file is the **decision record (D1–D8) + the build tokens** below. The first fold was mistakenly written against a stale base (origin had raced ahead to M6.5) and was discarded — this is the clean placement. **Next: a PO call on the build window** (now vs post the boring-hold ~07-13), then V3.1 token retone.


*Decisions to settle before any code is written. Each conflict is between the **v3 handoff** and current **DESIGN.md / SPEC.md / CLAUDE.md**. Mark a call in the `→` line; the **Canon delta** says which doc to edit once decided. Joint (Adar + Shanee) calls flagged ⚑. Source: the v3 review, 2026-06-25.*

## Signed decisions — Adar + Shanee, 2026-06-25 (all closed; folded into DESIGN.md v3.1 + SPEC.md §4/§5/§6.1/§6.5 + BACKLOG.md v3 lane)
- **D1** — **B**: a "coming up" strip under the desk for WEEK-OUT / MONTH-OUT reminders.
- **D2** — Love-notes feature (distinct from WhatsApp): one ephemeral note **per direction**, lives **on the server (not the Sheet)**, dies at **24h or on replacement**; sender→other parent by who's logged in. **Voice memos in** → bounded unfreeze of the voice lane + first stored media (≤24h, appliance-local). New appliance endpoint (first non-Sheet dashboard data). **No nudge** — appears on the recipient's next open; spends no alert budget.
- **D3** — **B** (real sign-out/sign-in re-auth), **same sheet**: shared as editor with both Google accounts; both emails in `Settings.UserMap`; switch-account reuses the existing flow (`prompt:'select_account'`). No data-model change; `LastDoneBy` stays truthful.
- **D4** — **A**: absolute `Due = X` snooze (fixes the overdue-snooze bug).
- **D5** — **A**: restore red tier + count on the status pill.
- **D6** — **A**: keep the Car drawer.
- **D7** — Remove notif toggles + bank-connect + export from Settings; everything else stays. Account-switch (D3) is the one legit addition.
- **D8** — Goal viz = **v3 bar** (tile), bright-line kept in the **drawer**. Retone **system-wide**; mono rule **widened to all numerals**.

---

### D1 ⚑ Where do 🟡 WEEK-OUT / MONTH-OUT reminders live?
v3 deletes the "Next 7 days" list; the desk takes OVERDUE/today only, the calendar shows events, the timeline shows far milestones — so a reminder due in 5 days appears **nowhere**.
- **A.** Extend the timeline's default window + a `WEEK OUT → near milestone` rule (one surface, no new section)
- **B.** Add a compact "coming up" strip under the desk
- **C.** Render reminder lead-times as calendar entries
- *Rec:* **A** — reuses the net-new component; define the milestone-inclusion rule here too.
- *Canon delta:* DESIGN §3 (IA) + the timeline milestone rule into SPEC.
- → **Decision:** ________________

### D2 ⚑ Family note — voice & delivery
Two sub-calls. **Voice** collides with SPEC §4 (frozen lane) + "media is never stored." **Delivery:** for a note to *reach* the other phone (not just appear on open) implies push or WhatsApp — which bypasses/adds to the 2/day outbox.
- Voice: **text-only v1** *(rec)* / unfreeze voice (needs SPEC §4 edit + media-storage decision)
- Delivery: **read-on-open, no push** *(rec — accept it may go unseen)* / notify **through `lib/outbox.py`** (counts against budget) — never a side channel
- *Canon delta:* new `FamilyNotes` tab + 24h sweep in SPEC §6; note the delivery model in DESIGN §6 / SPEC §3.
- → **Voice:** __________  **Delivery:** __________

### D3 ⚑ "Switch account" / identity
v3 flips `currentUser` (adar|shani) as a label and ties it to `LastDoneBy` (col M) — but identity is the OAuth session, one adult per device. A label-flip stamps the wrong parent.
- **A.** Drop it — identity stays bound to OAuth *(rec; each adult is already on their own phone)*
- **B.** Make it a real sign-out / sign-in (re-auth)
- *Never:* let `currentUser` become a writable toggle feeding col M.
- *Canon delta:* none if A; SPEC §settings/auth note if B.
- → **Decision:** ________________

### D4 Snooze write semantics
v3's date-picker emits an **absolute** date; live contract is `Due += N` (pills 1/3/7/14/30). Different results against overdue rows; interacts with the OVERDUE formula + engine re-fire.
- **A.** `Due = X` absolute — verify it clears OVERDUE correctly
- **B.** Convert picker → nearest +N delta (keeps the existing write) *(rec — smallest contract change)*
- *Canon delta:* DESIGN §5 + SPEC §6.1 write table.
- → **Decision:** ________________

### D5 ⚑ Status pill severity (never-red)
v3 pill is amber/green only — an OVERDUE red item summarizes as amber, and the count is gone. DESIGN §2/§8.1 mandate red-if-overdue and treat OVERDUE/kids-health as never-suppressed.
- **A.** Restore a **red tier + count** on the pill (desk already computes `deskCount`) *(rec)*
- **B.** Accept the de-escalation and document it as deliberate
- *Canon delta:* DESIGN §2 banner/pill spec.
- → **Decision:** ________________

### D6 ⚑ Car domain
v3 portfolios = Money/Timeline/Health/Goals/Contracts — Car survives only as a timeline *category*; car items that aren't milestones lose their drawer. Car is still a first-class Domain (SPEC §6.1 col B).
- **A.** Keep a Car drawer
- **B.** Fold Car into Timeline + Contracts, document the data source for non-milestone car items *(rec only if D1 gives car items a home)*
- *Canon delta:* DESIGN §3.
- → **Decision:** ________________

### D7 Settings scope
README says "additions only"; prototype **replaces** Settings, drops the real controls, and adds 6 undocumented ones (notif toggles + bank-connect + export). Notif toggles collide with the outbox-budget model; bank-connect brushes no-credential-storage.
- **A.** Scope Settings **out** — keep current Settings, ignore the prototype's overlay *(rec)*
- **B.** Enumerate each control as kept/new, and flag notif toggles + bank row as their own conflicts
- → **Decision:** ________________

### D8 ⚑ Visual retone scope (palette + mono + goal viz)
v3 retones `--bg`/`--accent` and swaps Geist→IBM Plex Mono — but those live on `:root` and feed Sunday/Settings/dark-mode, so "Today-only" isn't possible without scoping tokens to a container. Also: goal tile uses a progress bar (DESIGN §2 bans bars >90d; you already ship `renderGoalLine`).
- Retone: **system-wide** (update `:root` + theme blocks + font) *(rec — clean)* / scope to `.view-today` and accept mismatch
- Mono "money-only" rule: keep, or extend to dates/percent (v3 overreaches)
- Goal viz: **keep bright-line off long goals** / allow the v3 bar
- *Canon delta:* DESIGN §2 (color/type/goal-viz).
- → **Retone:** ______  **Mono:** ______  **Goal viz:** ______

---

**Not decisions — just build scope (once the above land):** bottom-sheet system is net-new **L** (your drawers are accordions); every chrome string needs **EN** added to `STRINGS`; a11y fixes (amber/muted contrast, avatar urgency text, button names, reduced-motion). **Already resolved in the handoff:** Shabbat-as-calendar-entry, Brief-overlay-is-illustrative (Sunday stays source of truth).

---

## Design tokens & components (build reference)

*The concrete values the retone locks in. Full pixel geometry lives in the handoff (`~/Downloads/Family Inc Repo Redesign.zip` → README). These graduate into `DESIGN.md` per slice as built — they are **not** present-tense canon yet.*

**Palette (light).** `--bg #EBEEF2` · `--tile #FFFFFF` · `--tile2 #E9EDF3` · `--ink #12151C` · `--muted #5F6878` *(darkened from the prototype's #697282 to clear AA)* · `--line #E1E5EB` · `--accent #2C57C8` · `--soft rgba(44,87,200,.10)` · `--green #2F8559` · `--amber #8A5E12` *(darkened from #BC852B to clear AA on the pill)* · `--red #C4403B`. Dark mode: provisional (prior hues, retoned) — own pass later. **No gradients.** Reconcile names with the existing `--border`/`--font-mono` in `styles.css`.

**Type.** Heebo 400–800 (Hebrew UI) · Inter 400–700 (Latin fallback) · **IBM Plex Mono** 400–600 (all numerals: money/dates/counts/times/%; replaces Geist Mono). Weight ≤800; body ≤600; no italic.

**Shape / elevation.** `--rad 20px` (cards/sheets), 12–14px inner, 999px pills; card shadow `0 1px 2px rgba(0,0,0,.03), 0 8px 22px rgba(0,0,0,.05)`; bottom-sheet `0 -8px 40px rgba(18,21,28,.22)`. Tap targets ≥44px; action pills below rows.

**Components (Today, top→bottom).** header (connection pill · Latin "Family inc." · greeting + date · 3-tier status pill) · love-note card (empty-feed-hidden) · 3-day scroll-snap calendar · select-to-act desk · coming-up strip · portfolios (Money hero: donut + category bar + sparkline · Timeline · Health avatars · Goals bar · Car · Contracts) → one data-driven bottom-sheet drawer. **a11y invariants:** urgency never color-only (text label + non-color glyph); icon-only buttons named + keyboard-operable; `prefers-reduced-motion` honored; numerals <12px never carry status.

**Build:** see `ROADMAP.md` §3.8 for the V3.1–V3.9 sequence, dependencies, and open PO calls. SPEC/DESIGN graduate as each slice ships.
