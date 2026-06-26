# Next session — Family Inc

*Generated 2026-06-26 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current focus only.

**Current focus: v3 Today redesign — **V3.9** (milestone review via `review.py` + canon close + BACKLOG flip) is the final slice; all UI + i18n/a11y slices are code-complete. **✅ V3.8 i18n + a11y + Settings shipped 2026-06-26**: a declarative **`data-i18n-aria` walker** (in `applyChromeStrings`, retiring the hand-rolled boot aria-labels); a **global `:focus-visible`** + **one consolidated `prefers-reduced-motion`** block (replaced 3 scattered ones; neutralizes transitions + `:active` scale + scroll); a hermetic **WCAG-AA contrast assertion** test (pins `--muted`/`--amber`/`--on-accent`/`--blue`, "assert don't re-pick"); a **real switch-account re-auth** (D3 — Google account chooser, **no token-revoke** so `LastDoneBy` stays truthful and re-picking yourself can't sign you out) + D7 (no notif/bank/export markup); the **token-alias endgame** (the 6 V3.1 aliases migrated across 24 refs + deleted; `--blue` kept as a theme-paired info token, given its missing dark value — the dark calendar-time fix, Shanee's "keep distinct info blue" call); and **cheap pure-function JS tests** (`parseDate`/`fmtISO`/`flagFor`/`bumpDate` via plain node, no toolchain — the **interactive-logic JS harness is a tracked deferred lane**, Deferred below). 2 PO calls settled (JS-test depth · `--blue` fate); **7-lens adversarial review** (correctness · auth/security · a11y · i18n/RTL · CSS-tokens · canon · test-quality, each refute-verified) → **9 confirmed, all fixed** — the switch-account **same-account-revoke major** dissolved by dropping the revoke entirely (revoke drops the shared grant), + the chooser-cancel dangling state, the redundant `.desk-row` focus ring, the missing dark-`--amber` assertion, and a TZ-fragile round-trip pin; **0 refuted**. SPEC §7.6 + DESIGN §2/§3/§8/§9 graduated, **468 tests green** — code-complete, **deploy-gated by the Pages publish**. V3.1–V3.7 on Pages; V3.7 love-notes **text** is additionally tunnel-gated; **voice** is a frozen phase-2.**

*(The focus headline is set by a `**Focus:** …` pin in `BACKLOG.md` → `## Now`; absent a pin it's the freshest 🔵 lane.)*

Active lanes (🔵 in progress — work the focus above first; don't open the others without a PO call):

- M6.3 — consumer wiring + close. Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning is armed (`FINANCE_STALE_IMPORT_DAYS`). Budget-SUMIFS installer ran live …
- M6.4 — analysis layer. *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates …
- M6.5 — cards lane (un-deferred 2026-06-23, the third VPS hour). Cal (Visa) is live — hooked up via a one-time headed `--auth` device-trust login (xvfb + x11vnc over an SSH tunnel; `FINANCE.md §4`) …
- v3 Today redesign (decided 2026-06-25; building). The dashboard Today surface gets a cool retone + new IA + two net-new components (parent-to-parent love-note, cross-domain timeline). 8 design calls …

Recent commits (the dated decision record — decisions fold into the canon, not a separate log):

- 2026-06-26 feat(dashboard): V3.3 — select-to-act desk + ±30-day coming-up + absolute snooze
- 2026-06-26 fix: Lane C — col-D round-trip + dashboard header guard (unblocks V3.3)
- 2026-06-26 feat(dashboard): V3.7 — love-notes (text): appliance endpoint + Cloudflare Tunnel
- 2026-06-25 feat(dashboard): V3.6 — cross-domain timeline (1wk→5yr zoom + category filter)
- 2026-06-25 docs: regenerate next-session prompt (post V3.5)
- 2026-06-25 feat(dashboard): V3.5 — portfolios + one data-driven bottom-sheet (replaces the accordions)

Session contract: don't open lanes outside the current focus without a PO call ·
constants → config, utilities → `automation/lib/`, message copy → templates ·
a directional call = edit the relevant canon doc to the new present-tense state
(short inline *why* if non-obvious) with the dated rationale in the commit message ·
session end: tests green if code moved, `BACKLOG.md` flipped, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
