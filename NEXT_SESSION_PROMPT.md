# Next session — Family Inc

*Generated 2026-06-26 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current focus only.

**Current focus: M6 finance acceptance — the **06-26 gate is now due**: (1) the first real **classifier-accuracy run** (`accuracy_review.py` over ≥1 week of live rules+DeepSeek output) **+ define the pass threshold**; (2) the historical **re-categorize backfill** (move the ~66 Cal mirror rows → `Card Settlement` and re-run the blank rows through the engine — `finance_ingest` tags only *new* rows, so the backlog never re-enters); (3) **Shanee's budget-vocab migration** (firms the provisional category vocab the rules engine maps to); (4) the **external milestone review** on the live system (folds in the property lane). Work M6.3 → M6.4 → M6.5 (below) in that order; full plan `ROADMAP.md` §2. **▶ Acceptance tooling landed 2026-06-26 (this session) — gate now box-run-only:** the one-time **re-categorize backfill** (`automation/finance_recategorize.py` — re-runs the engine over blank rows, surgical `write_cells` back-write, idempotent, blank-rows-only so a manual/prior tag is never clobbered; the ~66 Cal-mirror lines (box-unverified count) → `Card Settlement` via the existing rule) + a read-only **coverage** surface (`automation/finance_coverage.py` + pure `lib/finance_coverage.py` — categorized vs excluded-mirror vs blank, by account, blank merchants named) — hermetic + tested (**486 green**, +18). **Threshold defined:** summarizer = **< 1 ALERT-FP/week** (ratified, SPEC §7.3); finance = **coverage, report-first** (candidate ≥90% of budget-eligible rows; correctness/FP deferred → ROADMAP rank 12). Canon graduated: SPEC §12.2 (backfill seam + coverage acceptance facet) + `deploy/FINANCE.md §7` (box-run recipe) + the **Shanee budget-vocab data-request** (`deploy/FINANCE.md §6` — she fills `Finance-Budget` A:B only). **Reviews ran on the diff:** an internal 6-lens adversarial pass (1 major — coverage `by_source` double-counted excluded settlements → fixed; +2 test-gaps, +1 nit) **and** the external `review.py` DeepSeek gate (`reviews/review_milestone_2026-06-26_22-07.md` + `_resolution.md`: **0 blockers**; 4/5 concerns Applied — header re-validate before write · dry-run under-report note · coverage header-normalize · exclusion-order test — concern 2 [torn write] Defended: `batch_update` is a single atomic call). **Remaining is the PO box-run block** (backfill dry-run → run · coverage before/after · `accuracy_review.py --weeks 1`) → set the bar from the live number → the milestone CLOSE (accepting M6 + the property-lane review fold). **✅ v3 Today redesign CLOSED 2026-06-26 (V3.9 — the lane's last slice):** the external milestone review ran (`review.py` DeepSeek — `reviews/review_milestone_2026-06-26_20-47.md`; 1 Apply [SPEC §7.7 replacement-semantics clause], rest Defend/Open, **0 blockers**) alongside an internal **9-area canon-vs-code conformance audit** (every area conformant; 3 nit-level doc catch-ups Applied: SPEC §7.6 blank-title exclusion · DESIGN §4 quiet-day copy · the `userinfo`→`tokeninfo` comment fix — `reviews/review_milestone_2026-06-26_resolution.md`); SPEC §7.6/§7.7 + DESIGN §2/§3/§4/§5/§8/§9 graduated; **468 tests green**. V3.1–V3.8 (UI + i18n/a11y + the love-note text endpoint) are **code-complete, deploy-gated by the Pages publish** (V3.7 love-notes additionally tunnel-gated; voice frozen phase-2). Review follow-ups (JS interactive-logic harness · love-note rate-limit · 120-char composer hint · the Worker-vs-tunnel phase-2 PO call) → **Deferred** below.**

*(The focus headline is set by a `**Focus:** …` pin in `BACKLOG.md` → `## Now`; absent a pin it's the freshest 🔵 lane.)*

Active lanes (🔵 in progress — work the focus above first; don't open the others without a PO call):

- M6.3 — consumer wiring + close. Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning is armed (`FINANCE_STALE_IMPORT_DAYS`). Budget-SUMIFS installer ran live …
- M6.4 — analysis layer. *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates …
- M6.5 — cards lane (un-deferred 2026-06-23, the third VPS hour). Cal (Visa) is live — hooked up via a one-time headed `--auth` device-trust login (xvfb + x11vnc over an SSH tunnel; `FINANCE.md §4`) …

Recent commits (the dated decision record — decisions fold into the canon, not a separate log):

- 2026-06-26 docs: V3.9 — close the v3 Today redesign (milestone review + canon conformance)
- 2026-06-26 feat(dashboard): V3.8 — i18n aria walker + a11y pass + switch-account + token-alias endgame
- 2026-06-26 feat(dashboard): V3.3 — select-to-act desk + ±30-day coming-up + absolute snooze
- 2026-06-26 fix: Lane C — col-D round-trip + dashboard header guard (unblocks V3.3)
- 2026-06-26 feat(dashboard): V3.7 — love-notes (text): appliance endpoint + Cloudflare Tunnel
- 2026-06-25 feat(dashboard): V3.6 — cross-domain timeline (1wk→5yr zoom + category filter)

Session contract: don't open lanes outside the current focus without a PO call ·
constants → config, utilities → `automation/lib/`, message copy → templates ·
a directional call = edit the relevant canon doc to the new present-tense state
(short inline *why* if non-obvious) with the dated rationale in the commit message ·
session end: tests green if code moved, `BACKLOG.md` flipped, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
