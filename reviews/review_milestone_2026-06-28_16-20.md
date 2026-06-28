# Milestone review — milestone lane

- **When:** 2026-06-28T16:20:53
- **Provider:** DeepSeek (`deepseek-chat`)
- **Elapsed:** 25.1s
- **Attached files (5):**
  - `CLAUDE.md` (7,805 chars)
  - `SPEC.md` (51,061 chars)
  - `BACKLOG.md` (45,256 chars)
  - `ENGINEERING.md` (17,550 chars)
  - `DESIGN.md` (22,669 chars)

---

## Response

### Concerns

1. **HIGH — finance-local-rules-overlay deferred without a timely stub.** The `load_rules` function explicitly reads only the public seed, so the 4 recurring local-grocery blanks will stay blank until the overlay lands. The `ROADMAP.md` rank 12.1 pointer is a placeholder with no acceptance bar or check-in point. The explicit design choice (§12.2 "stays blank by design") is logically correct but practically a decision to leave live data in a known-degraded state for an indeterminate time. *Fix: either build the overlay as a `--local-rules` flag in the same session that lands this close, or set a concrete date/condition for when a missing-overlay is a bug (e.g. "if a merchant appears in ≥2 months of data without an overlay, the fixture is a silent loss, not a design virtue").*

2. **MEDIUM — finance_recategorize.py bypasses the categorizer's own fallback on first run.** The backfill script re-runs the same engine over blank rows — but in the first live run, the engine only tags via the keyword rules, leaving LLM gap-fill for later ingest. When backfill runs, it won't re-run the LLM gap-fill, so blanks that *are* genuinely categorizable by description+amount but have no keyword match stay blank. The SPEC contract (§12.2 Categorization & acceptance) implies that a backfill is the seam to re-enter *every* categorizer stage, but the implementation only re-runs the rules engine. *Fix: either backfill calls the full categorization pipeline (rules → LLM gap-fill) or the SPEC makes explicit that backfill is rules-only and LLM gap-fill is forward-only.*

3. **MEDIUM — `Card Settlement` exclusion block lives below merchant rules, but the invariant test ($test_excluded_bucket_never_shadows_a_merchant) doesn't test all merchant suffixes.** The fix moved the exclusion block to a last-resort fallback, but the invariant test as described only asserts an ordering property — it doesn't generate a comprehensive set of real merchant names + settlement suffixes and verify the merchant wins. A `test_card_settlement_excludes_cal_mirror` tests the exclusion itself. *Fix: add a bi-directional test: for every token in the exclusion block, verify that a merchant-bearing row containing that token still lands on the merchant's category (proving ordering is truly last-resort), not on `Card Settlement`.*

4. **LOW — `deploy/FINANCE.md` §7 recipe update (`uv run --no-sync python`) is not reflected in any CI or deploy.sh guard.** If someone runs the box-run recipe incorrectly (e.g., bare `python3` as root again), there is no detection mechanism beyond "the operator knows to check". The `deploy/FINANCE.md` change is documentation-only; the actual deploy path (`deploy.sh`) doesn't enforce the correct invocation. *Fix: add a `deploy.sh` precondition check (or a separate CI smoke) that verifies the box-run command syntax, to prevent a future root-python3 regression.*

5. **LOW — M6 close marks `Finance-Transactions` column order as load-bearing (`SPEC.md §12.2`) but the installer (`finance_budget_formulas.py`) only installs machine columns; a column drift in the live tab (human reorder) would make `SUMIFS` read wrong amounts against wrong categories.** The guarding logic in the installer refuses on a missing human header or a real column shift, but this is a *tab-level* check — it doesn't detect a column *swap* (e.g., human dragging D next to E). A subtly-swapped column would pass head presence, then read `Amount` from what was `Category`. *Fix: add a column-order hash or a sample-row-content sanity check at install time (e.g., verify `Category` cell contains one of the known category vocab values, proving the column wasn't just renamed but meaningfully wrong).*

### Missed alternatives

- Instead of deferring the local-rules overlay, a `gitignored` one-override file could have been built as a 15-minute task in the same session, with `load_rules` reading it if present — reducing technical debt to near-zero.
- The backfill could have been built as a re-run of `finance_ingest` in a "forced recap" mode (re-ingesting the raw CSV) instead of a separate script, reducing the surface area of a one-time tool.
- The OBSIDIAN rule could have been committed as part of the M6 close (it was added but the box hasn't re-run) — deploying it alongside the acceptance stamp would have closed the 88%→89% lift immediately instead of leaving it for "next re-run".
- The coverage gap for the 4 local-grocery blanks could have been papered by a temporary "force-groceries" override in `bank_creds.json` (a string prefix that maps to category `Shopping`), bypassing the rules-engine entirely — testable, low-risk, and revertable.

### Affirmations

- **The 88% acceptance bar set "report-first" from live data is correct.** The structural reframing (blanks are merchant-less wrappers, not classifier failures) is an honest, maintainable reading — it sets the team up to fix the right thing (more sources) rather than over-optimizing classifier recall.
- **Accidentally adding the OBSIDIAN rule mid-close is the right move** — it's a public, recurring, non-local merchant, consistent with the invariant. The commit message explains the lift (~89%), so the close record is honest about the pre-re-run state.
- **Card Settlement exclusion below merchant rules** (2026-06-25 fix) is a necessary structural change that closes the latent over-match independent of live feed — the post-fix invariant test is what should have been there from day one.
- **The decision to defer correctness-FP metric** (`ROADMAP.md` rank 12) is correct: coverage is the gating metric, and the classifier's false-positive rate is operator-observable through `accuracy_review.py`; a formal metric adds process without removing risk.

### Concrete suggestions

1. **Replace "deferred as finance-local-rules-overlay" with a timed check-in in `BACKLOG.md`:** append "— **revisit 2026-07-12 (2 weeks of live data)** to assess whether the 4 blanks create a material undercount in `Finance-Budget`." This converts an open-ended deferral into a concrete condition that either closes the overlay (if the blanks matter) or confirms the deferral (if they don't).

2. **Replace "backfill re-runs the engine over blank rows" with a SPEC §12.2 clarification** that the backfill is rules-only (no LLM), and the LLM gap-fill is forward-only. The current language ("re-runs the same engine") is ambiguous — the engine has two stages. A one-line note: "the backfill re-runs the *rules* engine only; the LLM gap-fill runs only at ingest" closes the ambiguity.

3. **Replace the existing `test_card_settlement_excludes_cal_mirror` with a combinatorial invariant test** that iterates every exclusion token × every merchant rule token and asserts the merchant wins when both are present. Add a test case for the OBSIDIAN rule + settlement suffix interaction as a concrete example.

4. **Add a `deploy.sh` guard** that checks for `python3` being invoked instead of `uv run --no-sync python` in the finance box-run commands — a simple grep that exits non-zero. The box-run recipe fix is a documentation change that someone might miss.

5. **Strengthen the installer's column check** (`finance_budget_formulas.py`) to verify at least one `Category` cell sample: after locating column E (the Category position), read the first non-header, non-blank row's Category cell and assert it matches a pattern from the known vocab. This catches a swap where column E's header reads "Category" but its content is actually amounts.

### One question for the team

**Given that the 4 local-grocery blanks are recurring (every month for the foreseeable future), how would you detect whether the missing categorization materially understates the `Finance-Budget` `Groceries actuals` before the overlay ships — and would you accept a forced "if description starts with X → Shopping" rule in `bank_creds.json` (a one-line override, outside the committed seed, testable, revertable) as a temporary bridge until the overlay lands?**

---

<details>
<summary>Full prompt sent (click to expand)</summary>

```
You are reviewing engineering decisions made in a working session on the "Family Inc"
household-automation project. You are the explicit adversarial-but-fair reviewer. The
team owners (Adar = CTO, Shanee = Chief Design + PO) value pushback over agreement.

## Project one-paragraph context
A household operating system for a two-adult, two-young-kid family in Israel
(ILS, Hebrew/RTL, Maccabi healthcare). Master DB = one Google Sheet. PWA dashboard
pinned to both iPhones, write-back to the Sheet. Messages via WhatsApp (self-hosted
Baileys bridge) through a single budgeted outbox. Operating principles (SPEC.md §3):
briefings > notifications, alert budget 2/day, no kid-facing UI, boring tech,
one source of truth per domain, fail loud / degrade quiet.

## What this session changed
# Session changes — M6 finance milestone close (2026-06-28)

Milestone review scope: this session's diff **plus** the M6 finance lane as a whole
and the **property lane** fold-in (per the close contract). Reviewer: DeepSeek.

## What ran on the live box (the M6 acceptance gate)
- Re-categorize backfill (`finance_recategorize.py`) ran on the live Sheet: coverage
  **85% → 88%** of 155 budget-eligible rows (137 categorized · 117 excluded · 18 blank).
- The expected ~66 Cal-mirror → `Card Settlement` backfill was a **no-op**: those
  mirrors were already excluded by `finance_ingest` at ingest (dry-run added 0). The
  3-point lift was **5 DeepSeek gap-fills** (cheque→Fees ×2, value-credit→Income,
  vending→Shopping, a café→Dining out).
- Coverage accepted **report-first** at 88%. The headline is **structure-gated**: of
  the 18 blanks, ~12 are merchant-less wrappers (Leumi ATM cash ×9, BIT/PAYBOX P2P, an
  ANOMALY) that correctly return UNKNOWN → ~96% of *genuinely-categorizable* rows carry
  a category.
- Summarizer accuracy gate (`accuracy_review.py --weeks 1`): **503 classified over 7
  days, 0 ALERT-tier FP** (0 critical, 0 needs-a-look) vs the <1/week bar — clean pass.

## Code change
- `seeds/14_Finance_Category_Rules.csv`: added `OBSIDIAN,Shopping` (a public, recurring
  SaaS merchant; lifts coverage to ~89% once the box re-runs the backfill). Non-personal,
  consistent with the seed's public-merchant invariant. Suite **486 green** (unchanged
  count — covered by the existing `rules.vocab ⊆ budget` guard).

## Decision surfaced and deferred
- A **household-specific local merchant** (a local grocery, recurring ×4 in the blanks —
  name kept out of the repo by design) has **no home**: `load_rules` reads only the
  committed, public-portfolio-safe
  seed, whose invariant forbids household-specific payees (and committing one would leak a
  location signal). Deferred as the **finance-local-rules-overlay** forward item
  (`ROADMAP.md` rank 12.1 / §3.7): a gitignored on-box rules file that `load_rules` merges
  with local precedence.

## Canon graduated (present-tense state)
- `SPEC.md` §12.2 — acceptance facet now records the accepted report-first bar (88%, the
  structural reframing, the summarizer pass) + the local-merchant overlay pointer; §62
  live-state line marks M6 accepted 2026-06-28.
- `BACKLOG.md` — Focus flipped to the post-M6 recommended next lane (deploy code-complete
  v3 + Shanee vocab migration); M6.3/M6.4/M6.5 → ✅; the accuracy-run item → ✅; the
  external-review item → 🔵 (this gate).
- `ROADMAP.md` — rank 11 (M6.3/M6.4 acceptance) struck ✅; new rank 12.1
  finance-local-rules-overlay + its §3.7 contract stub.
- `deploy/FINANCE.md` §7 — box-run recipe corrected from bare `python3` (as root, no
  creds/deps) to `uv run --no-sync python` as `familyinc`, matching every systemd unit;
  accept-bar paragraph updated to the accepted 06-28 numbers.

## Property lane (folded into this milestone review)
- Live per the canon: Yad2 on-box + Madlan via Apify, silent listings in the morning
  digest; no code change this session. In scope for the reviewer's milestone pass.

## What I want you to review
1. Architectural soundness of the changes above.
2. Missed alternatives or simpler paths we didn't consider.
3. Tradeoffs we made implicitly without writing them down.
4. Risks / failure modes not covered.
5. Internal consistency across the changed files.

## What I do NOT want you to review
- Style, tone, formatting, copyediting.
- Adherence to design "best practices" in the abstract — only call those out if
  ignoring them creates a concrete risk for THIS project.
- The roles or session ritual itself (out of scope; that's our process).
- Files I did not list in "What this session changed" — assume those are settled.

## Required output (use these headings, in this order)
### Concerns
Things that should change. Be specific (file + section). Rank by severity.

### Missed alternatives
Paths we likely didn't explore. One-sentence each. Don't develop them — just name them.

### Affirmations
Decisions you think are correct, especially non-obvious ones. Brief.

### Concrete suggestions
Edits we could make right now. Phrase as "replace X with Y because Z."

### One question for the team
The single most useful question you'd ask Adar+Shanee+Claude if you had one.

Be terse. We're going to act on this directly.

---

## Attached context files

The following files are attached for you to read. Each is delimited by a header line.
Reference them by relative path in your review.

=== File: CLAUDE.md ===
# Family Inc. — Session Context

*Auto-loaded at the top of every session opened in this folder. Consolidated 2026-06-17 (the SPEC bump: canon rewritten clean, the D-NN decision log retired to `Archive/`). 2026-06-20: spec-ahead pass — `ROADMAP.md` added as the 5th canon doc; canon reconciled to code. Keep under 100 lines.*

## What this is

A household operating system for Adar + Shanee (+ 2 young kids, adult-mediated). Master DB = the `Family_OS` Google Sheet. Two product surfaces: WhatsApp messages (self-hosted Baileys bridge) and a PWA dashboard pinned to both iPhones. All automation runs on **one VPS** ("the appliance"). Israeli context throughout: Hebrew/RTL, ILS, Asia/Jerusalem, Maccabi, Hebcal.

## Canon — five documents, one job each

| Doc | Owns | Open it for |
|---|---|---|
| `SPEC.md` | what the system is: scope, architecture, data model, contracts, policies | any contract or "how should X behave" |
| `ENGINEERING.md` | how it's built/run: repo layout, toolchain, VPS, deploy, tests, ops | any "how do we do X" |
| `DESIGN.md` | both surfaces: dashboard UI + WhatsApp message design, i18n, states | any pixel or copy question |
| `BACKLOG.md` | current status: shipped, in-progress, gated, frozen lanes | where we are / what's frozen |
| `ROADMAP.md` | the forward plan: the ranked v1.1 sequence + per-lane forward contracts (spec **ahead** of build) | what to build next / a future lane's contract |

The first four are **present-tense snapshots** of the current state; `ROADMAP.md` is the **near-future** plan (a lane's contract graduates into `SPEC.md` when it ships). `Archive/` holds superseded docs and the full dated decision history (the old `DECISIONS.md` D-001…D-052 log) — read-only, for "didn't we decide…". Status lives **only** in `BACKLOG.md`; the forward sequence lives **only** in `ROADMAP.md`.

## Roles & authority

| Role | Person |
|---|---|
| CTO + co-PO | **Adar** — engineering direction, ships code |
| Chief Design + co-PO | **Shanee** — product direction, UX feel |
| Lead Architect | **Claude** — design, code, tradeoffs; defers to POs on product, to Adar on engineering detail |
| Reviewer | external model via `automation/review.py` (DeepSeek default) — milestone reviews only |

Either PO can lead a session and take routine calls solo; major directional calls (new feature, principle change, removing shipped behavior) are joint. Session leader = whoever opened the session; Claude treats them as "the PO" unless they defer.

## Non-negotiable principles (full versions: SPEC §3)

One source of truth per domain · boring tech · alert budget 2/day enforced at the outbox (criticals bypass, briefings exempt) · briefings > notifications · partner-symmetric, no scoring · fail loud, degrade quiet · never promise an affordance that doesn't exist · no money movement, no credential storage (except appliance-local read-only finance logins + the device-trust browser profiles they authorize), no messages beyond the two adults, no kid-facing UI.

## Current state (live)

**v1 live & accepted since 2026-06-13 (`v1-live`).** Running on the appliance: the keystone loop (reminders → WhatsApp digest + dashboard write-back), the weekly briefing (deterministic template), the group summarizer (on **DeepSeek**, keyword fallback keyless), and the **property tracker** (Yad2 on-box + Madlan via Apify, silent listings in the morning digest). Delivery has an email fallback; the outbox enforces the budget.

**M6 finance ingestion — live on Mizrahi (debit) since 2026-06-19:** daily read-only scrape → categorized, idempotent Sheet write (verified 98/98, dedup on a natural-key Txn-ID). **Cal (Visa) hooked up 2026-06-23** — the household is **not** debit-only: Cal is an *immediate-debit* card whose spend hits the Mizrahi statement merchant-less, so its own scrape brings the categorizable per-merchant detail (live **headless** via a one-time `--auth` device-trust login; first import 103 txns, **~90% categorized**). The Mizrahi-side Cal settlement lines map to an excluded **`Card Settlement`** bucket (not a budget row) so each purchase counts **once**, via the Cal side. **Shanee's debit card** turns out to be a Cal-cleared immediate-debit card on the **already-connected Cal login** — so it needs **no new `--auth`**; its repo change is just the `רכישה בכרטיס דביט` `Card Settlement` mirror token (landed 2026-06-23, pending a box-verify that her per-merchant rows ride the existing Cal scrape). Other statement cards remain (cards lane **un-deferred**, `BACKLOG.md`). M6.3 (briefing/dashboard consumers) + M6.4 (analysis layer) remain. **Gated to ~2026-06-26** (needs ≥1 week of live finance data): the first real classifier-accuracy run + the external milestone review. Full status: `BACKLOG.md`; the forward plan + lane contracts: `ROADMAP.md`.

**2026-06-23 (second VPS hour):** box-side verification (ROADMAP lane 7) confirmed the asserted-live claims; the CI gate (lane 1) merged to `main` (first run red on `setup-uv@v8` → pinned `@v7`); the Mizrahi scraper lib was bumped 6.7.3→6.7.8 after a 06-22 login-flow failure; and a **~77%-blank live-categorization gap** was surfaced.

**2026-06-23 (third VPS hour — Cal hookup):** the "77% blank" turned out **mostly structural, not an engine failure** — the blanks are merchant-less wrappers (Cal settlements, ATM, cheque, other cards), correctly UNKNOWN. Cal's own scrape categorizes its rows at ~90%, so the fix is *more sources*, not a better classifier. The `Card Settlement` exclusion (rules + test seam, 422 green) prevents the immediate-debit double-count. **Shanee's debit card** is the first "remaining card" worked (2026-06-23): it rides the connected Cal login (no new `--auth`), so the change is just its `רכישה בכרטיס דביט` mirror token (landed; box-verify pending). Still gated to 06-26 (Shanee's vocab migration + a re-categorize backfill of historical blanks + the remaining statement cards).

## Session protocol

0. `git pull --ff-only` before touching anything — other agents push to origin; the local folder is not assumed current.
1. Read `BACKLOG.md` first — it says where we are.
2. Work the current item; don't open new lanes without a PO call.
3. Constants go in config, utilities in `automation/lib/`, message copy in templates (reviewable against `DESIGN.md` §6).
4. **Decisions fold into the canon, not a log.** A directional call = edit the relevant doc to the new present-tense state, add a short inline *why* if it's non-obvious, and carry the dated rationale in the commit message. Major/joint calls land the same way. (The separate D-NN log is retired; git history is the dated record.)
5. Session end: tests green if code moved, `BACKLOG.md` statuses flipped, `python3 automation/session_kickoff.py` regenerated `NEXT_SESSION_PROMPT.md`, and the PO gets ONE terminal block (stage → review gate if milestone-closing → commit → push) to run on their machine.
6. **Milestone reviews only** (new spec / architecture shift / budget-privacy-delivery change / each milestone close): run `automation/review.py`, resolve as Apply / Defend / Open. Tiny edits never trigger a review.

## Guardrails for Claude in this repo

- Never put names, phone numbers, JIDs, or real finance values in committed files — they belong in the Sheet, `/etc/family-inc/`, or gitignored seeds (the repo is public-portfolio-safe by construction).
- Never add an alert path that bypasses the outbox chokepoint (`automation/lib/outbox.py`).
- Schema changes are additive-only on the Sheet (old rows must keep parsing).
- Committed ≠ deployed: a feature or placed secret is inert until `deploy.sh` pulls it; confirm the box is at origin HEAD before declaring anything live.
- Git operations run on the PO's machine, never in a sandbox.
- If SPEC and code disagree, say so before "fixing" either.

=== End: CLAUDE.md ===

=== File: SPEC.md ===
# Family Inc. — System Specification

*What the system is: scope, architecture, data model, contracts, policies. v3.1 · 2026-06-20.*
*This is a present-tense snapshot — it describes how the system behaves today, not how it got here. The dated history (every prior "we changed X to Y" rationale) lives in `Archive/`. Companions: `ENGINEERING.md` (how it's built and run) · `DESIGN.md` (how it looks and reads) · `BACKLOG.md` (current status) · `ROADMAP.md` (the forward v1.1 plan + lane contracts).*

---

## 1. Overview

Family Inc. is a household operating system for a two-adult, two-child family in Israel. It watches the family's obligations — appointments, renewals, deadlines, school/daycare chatter — and reflects them back through **two calm surfaces**: a small number of WhatsApp messages, and a PWA dashboard pinned to both adults' iPhones. The master database is a single Google Sheet. The automation runs unattended on one small VPS ("the appliance").

The core promise: **nothing important gets dropped, without anyone having to watch a screen.**

### What it is not

- Not a chore-gamification app. No streaks, no scores, no nagging.
- Not a kid-facing product. Children's data is structured but adult-mediated.
- Not a finance robot. It never moves money; the only financial credentials it holds are appliance-local, read-only portal logins (and the per-provider device-trust browser profiles they authorize) used to *read* balances and transactions.
- Not a chat bot. It speaks at scheduled moments, or for genuine urgency, within a hard budget.

## 2. Context

| | |
|---|---|
| Household | 2 adults (joint product owners) + 2 young children |
| Locale | Israel — Hebrew-first, RTL, ILS, Sunday-start week, Jewish-calendar aware (Shabbat, chagim) |
| Healthcare | Maccabi (no public API — any ingestion is mail/manual) |
| Devices | Two iPhones (PWA + WhatsApp), one VPS, no other infrastructure |
| Cost ceiling | ~₪120/mo all-in (VPS ~₪20 + LLM ~₪35 + margin). Anything above needs a PO call |

Roles and decision authority live in `CLAUDE.md`. Personal data — names, phone JIDs, health specifics, real budgets — lives only in the Sheet and in gitignored config/seed files, never in committed code or docs. The repo is public-portfolio-safe by construction.

## 3. Operating principles

Phrased so a reviewer can check compliance:

1. **One source of truth per domain.** Every datum has exactly one authoritative home (almost always a Sheet tab). Anything else holding it is a cache or a view, and is allowed to be lost.
2. **Boring tech.** Google Sheets over a database; vanilla JS over a framework; systemd timers over orchestration; JSONL files over message queues. A new dependency must remove a failure mode, not just add a capability we like.
3. **Alerts are a budget.** Hard cap of 2 unsolicited messages per recipient per day, enforced at one chokepoint (§7.5). Critical-safety messages bypass it with an audit trail. Scheduled briefings are exempt — they are appointments, not interruptions. *(Enforced in one place because two scripts that each kept their own 2/day counter could combine to 4+/day.)*
4. **Briefings > notifications.** The default unit of communication is a scheduled digest. A real-time message is the exception that must justify itself.
5. **Partner-symmetric.** Both adults see everything, can act on everything, and appear as equals. No leaderboards, no scoring.
6. **Fail loud, degrade quiet.** Infrastructure failures surface in the next briefing ("bridge silent 14h"), never as silence. Feature degradation (LLM down → deterministic fallback) must not page anyone. **Time-critical, user-facing data is the exception to "degrade quiet":** when a fetch fails for a time-sensitive line — e.g. Shabbat/chag candle-lighting times — surface an explicit "unavailable" line, never silence, because a missing safety line that's indistinguishable from "nothing today" is itself a silent failure (GAP-7, 2026-06-20).
7. **Never promise an affordance the system doesn't have.** No reply commands in messages until reply parsing ships; no buttons that don't write.

## 4. Scope

### Live today

| Capability | One-line contract |
|---|---|
| Reminders engine | Daily 07:25: read the Reminders tab, compute due / lead-time / overdue fires. |
| Daily digest | Daily 07:30: assemble engine fires + WhatsApp group digest + new-property listings + Hebcal line into **one** message per adult, and send. **Both adults every day** (§7.2). |
| Weekly briefing | Sat 21:00: whole-Sheet narrative rendered from a deterministic template. |
| Hebcal enrichment | Friday/holiday awareness lines in briefings (candle-lighting, chagim). |
| WhatsApp summarizer | Hourly: classify group messages ALERT / DIGEST / ROUTINE; alerts within budget; a digest section at 07:30. |
| Property tracker | New Yad2 / Madlan listings land silently in the Sheet + a digest section (§12.1). |
| Dashboard (PWA) | Today-first read view + write-back (done / snooze / note) with offline queue and a tombstone race guard. |
| Delivery | Self-hosted Baileys bridge: 1:1 messages to the two adults only, via a durable outbox. |

### Building now

**Finance ingestion (M6, §12.2).** Read-only scrape → categorized transactions + balances in the Sheet → silent surfacing in the briefing and dashboard. **Live on Mizrahi (debit) since 2026-06-19**; consumer wiring (M6.3) + analysis layer (M6.4) shipped, and **M6 was accepted 2026-06-28** at **88 % categorization coverage** (report-first; ~96 % of *genuinely-categorizable* rows — §12.2). **Cal (Visa) hooked up 2026-06-23** — an immediate-debit card whose spend also lands merchant-less on the Mizrahi statement, so the Mizrahi-side Cal lines map to an excluded `Card Settlement` bucket (counted once via the card); more cards remain (M6.5). See `BACKLOG.md`.

**Love-notes (V3.7, §7.7).** A parent-to-parent ephemeral note over a small authenticated dashboard→appliance endpoint — the one dashboard datum that is **neither the Sheet nor the outbox**. The **text** phase is code-complete, deploy-gated on standing up the Cloudflare Tunnel + its `DASHBOARD_LOVENOTE_URL` secret; **voice** is a frozen phase-2 (below). See `BACKLOG.md`.

### Non-goals (permanent)

Money movement · credential storage *(except appliance-local, read-only financial portal logins and the device-trust browser profiles they authorize)* · messaging anyone beyond the two adults · posting into any group · kid-facing surfaces · medical advice (scheduling only).

### Frozen (out of scope until a stated condition is met)

Pediatric milestones, goal coaching, PDF/OCR/voice capture, Gmail bill parsing, Maccabi forwarders, WhatsApp reply parsing. Each unfreeze condition is in `BACKLOG.md`; frozen code lives in `attic/`, unmaintained. *(Voice capture's first bounded unfreeze is the love-note **voice memo** (§7.7 phase-2): ≤24h, appliance-local, the single exception to "media is never stored" — it graduates only with its own §4/§7.7 carve-out, which has not landed; the love-note text phase stores no media.)* Anomaly/subscription detection is **killed** (not frozen) — the false-positive cost isn't worth it. A keyword categorizer, also once killed, returns in a bounded form only as the on-box finance rules engine (§12.2).

## 5. System architecture

```
                       ┌─────────────────────────────────────────────┐
                       │  GOOGLE (data plane)                        │
                       │  Family_OS Google Sheet  ←  master DB       │
                       │  Drive: /Briefings, /Documents              │
                       └────────▲───────────────────────▲────────────┘
                gspread (svc acct)│                      │ gapi (user OAuth)
                                  │                      │
┌─────────────────────────────────┴───────────┐   ┌──────┴───────────────────┐
│  THE APPLIANCE (one VPS, Asia/Jerusalem)    │   │  DASHBOARD (PWA)         │
│                                             │   │  GitHub Pages, vanilla   │
│  systemd timers:                            │   │  JS, pinned to 2 iPhones │
│   07:25 reminders engine (compute)          │   │  read: batchGet          │
│   07:30 daily digest (assemble + send)      │   │  write: batchUpdate +    │
│   hourly whatsapp summarizer                │   │   DoneAt / LastDoneBy /  │
│   ~06:00 finance scrape (M6: live)          │   │   WriteQueue_Tombstone   │
│   2×/day property scrape                    │   └──────────────────────────┘
│   Sat 21:00 weekly briefing                 │
│                                             │         ┌──────────────────┐
│  Baileys bridge (Node, systemd service):    │ WhatsApp│ Adar + Shanee    │
│   reads groups → inbox.jsonl                │────────▶│ (the only        │
│   polls outbox.jsonl → sends 1:1            │         │  recipients)     │
│   recipients.json = hard scope guard        │         └──────────────────┘
│                                             │
│  lib/outbox.py = THE chokepoint:            │
│   budget ledger, dedup, kinds, quiet hours  │
└─────────────────────────────────────────────┘
```

Key properties:

- **One write path to phones.** Every script that wants to reach a human appends to the outbox via `lib/outbox.py`. Budget, dedup, quiet hours, and scope live there once.
- **One data plane.** All Python uses gspread with a service account; the dashboard uses gapi with each adult's own OAuth. The local `Family_OS.xlsx` is a seed template only — nothing reads it at runtime. *(A split between openpyxl reads and a gapi dashboard would be two diverging sources of truth.)*
- **One machine.** Bridge and automation share the VPS. Its failure mode is total and therefore obvious (heartbeat goes stale → the next successful briefing says so; if >24h, the email fallback fires). *(The bridge needs to be always-on anyway, so a second runtime would only add a failure domain.)*
- **LLM calls are decoration, not structure.** Every LLM-dependent step has a deterministic fallback (templated briefing, keyword classification). The system delivers value with the API key revoked.

## 6. Data model — the `Family_OS` Google Sheet

Authoritative tab list. The three tabs with code contracts get column-level schemas below; the rest are human-edited and read loosely (missing columns tolerated, rows with unparseable dates surfaced as data-hygiene lines, never crashing a run). All schema changes are **additive-only** — old rows must keep parsing.

### 6.1 `Reminders` (keystone)

| Col | Field | Written by | Notes |
|---|---|---|---|
| A | Title | humans | used verbatim in messages |
| B | Domain | humans | Car / Health / Education / Finance / Contracts / Goals / Other |
| C | Owner | humans | Adar / Shanee / Both |
| D | Due Date | humans, engine + dashboard (recurrence bump / snooze) | a real Sheets **date** cell (he-IL renders it DD/MM); machine writes emit the **ISO `YYYY-MM-DD`** literal — Sheets parses ISO locale-unambiguously — and both surfaces **read** ISO *or* the DD/MM·DD.MM render (Lane C) |
| E | Lead Times | humans | CSV of day offsets, e.g. `60,30,7,1` |
| F | Recurrence | humans | One-off / Yearly / Monthly / Quarterly / Weekly / Custom |
| G | Status | engine, dashboard | Pending / Snoozed / Sent / Done / Skipped / Overdue |
| H | Last Sent | engine | ISO datetime of the last fire for this row |
| I | Channel | humans | WhatsApp / Email / None |
| J | Notes | humans, dashboard (append) | appended to a message if ≤120 chars |
| K | Days Until | sheet formula | `=D−TODAY()` |
| L | Auto-flag | sheet formula | OVERDUE / FIRE TODAY / WEEK OUT / MONTH OUT |
| M | LastDoneBy | dashboard | display name from `Settings.UserMap` |
| N | DoneAt | dashboard | ISO datetime; feeds the 7-day arc |
| O | WriteQueue_Tombstone | dashboard | ISO datetime stamped on **every** dashboard write; the engine skips rows tombstoned <6h (§8.3) |
| P | Guide URL | humans | optional how-to / Kol-Zchut link, appended to messages |

**Dashboard write contract:** every write-back is one `batchUpdate` touching its intent columns **plus M, N (when completing), and always O.** A dashboard that doesn't stamp O is non-conformant. **Snooze writes an *absolute* future Due date** (today + the chosen offset, or a picked date — never `Due += N`), so an already-overdue row snoozed forward clears OVERDUE cleanly. The Today **desk** is select-to-act (V3.3): a multi-row selection fans its done / snooze / note out to **one** `batchUpdate`, every row's columns resolved by header name (Lane C, §7.6).

### 6.2 `WhatsApp_Inbox` (hot, 30-day rolloff) + `WhatsApp_Archive` (text-only, forever)

`WhatsApp_Inbox` columns: msg_id, group_name, group_type, sender_name, sender_role, received_at, text, has_media, classification, one_liner, action_required, action_owner, critical, dispatched, dispatched_at, digested_at. After each successful append, rows older than 30 days roll off (the Archive never rolls). `WhatsApp_Archive` keeps msg_id / group / sender / received_at / text / one_liner only. **Media is never stored** — only the fact that it existed. The `critical` / `dispatched` fields are the outbox *outcome* record; budget enforcement itself lives only in the outbox ledger.

### 6.3 `WhatsApp_Group_Config`

group_name · group_type · importance_default (alert_eligible / digest_only / mute) · alert_recipients (both / adar / shanee / none) · close_contacts · alert_keywords (regex `;`-list) · critical_keywords (regex `;`-list, budget-bypassing).

### 6.4 Other tabs

`People`, `Calendars`, `Calendar-Events`, `Finance-Budget`, `Finance-Accounts`, `Finance-Transactions` (finance landing zone — schema in §12.2), `Goals`, `Health`, `Education`, `Car`, `Contracts`, `Contacts`, `Lists`, `Settings` (Key|Value rows — keys containing `@` are UserMap entries email→display-name; key `lang` is the chrome default), `Reminders-Archive` (one-offs roll here monthly), `Property-Listings` (scraper-written — schema in §12.1). `Calendars` and `Lists` are human-only (no code contract; read loosely, out of code scope). Money values are **ILS only**.

## 7. Component contracts

### 7.1 Reminders engine — daily 07:25 (computes, does not send)

```
validate the header row against the §6.1 column map; on mismatch: abort the run,
  log schema_drift, surface it in the next briefing. (Guards the dual write-path:
  dashboard and engine must agree on columns before anything fires; write-backs
  validate BEFORE the batch is issued, so a drifted sheet is never written by
  position.)
read Reminders where Status ∉ {Done, Skipped}.  (NOT "∈ {Pending, Snoozed,
  Overdue}": a 60,30,7,1 lead-time chain would die at its first Sent stamp.
  Same-day re-fires are blocked by the Last-Sent guard instead.)
  skip if WriteQueue_Tombstone is within 6h      → log skipped_due_to_tombstone + age
  fire if days_until < 0 AND last sent ≥3d ago   → OVERDUE
       or days_until ∈ Lead Times                → LEAD-TIME
       or days_until == 0                         → DUE TODAY
hand fires to the 07:30 daily digest (§7.2).
on CONFIRMED delivery (in the digest): Last Sent = now; Status = Sent | Overdue.
  (Confirmed = the bridge's whatsapp_sent.jsonl, reconciled at the next run; the
  §10.2 SMTP fallback confirms inline. NOT on queue — the bridge delivers
  asynchronously, so stamping a merely-queued digest let a bridge that dropped
  its session read "Sent" while the reminder never arrived, and the Last-Sent
  guard then silently suppressed the re-fire. Stamping on confirmation closes
  that silent-loss; an unconfirmed digest leaves its rows unstamped → they
  re-fire. See §7.5.)
recurrence on Done: bump Due Date by the period, Status → Pending, Last Sent
  cleared; Feb-29-class dates clamp to the last day of the target month + a
  review flag; Custom is flagged, never guessed.
heartbeat: append one line to logs/reminders_log.csv every run.
```

### 7.2 Daily digest (07:30) + weekly briefing (Sat 21:00)

**Daily digest:** one short message assembled from engine fires + the WhatsApp digest section + new-property listings + a Hebcal line (Fridays / erev chag), queued as `kind=briefing`. **One morning message, not several** — assembly happens before queuing. On **confirmed delivery** the digest stamps each fired row's Last Sent / Status per §7.1 (the bridge delivers asynchronously, so a digest queued one morning is stamped when the next run reconciles its confirmation; the SMTP fallback stamps inline).

**Both adults, every day.** The digest is assembled and queued for adar **and** shanee on every run. An adult with no fires of their own still gets the briefing — the quiet-day line plus the shared sections (WhatsApp groups, property). This keeps the surface partner-symmetric and means silence always signals a *broken* digest, never an empty day. Because it is `kind=briefing` it is budget-exempt, so briefing the empty-handed adult never spends an alert slot.

**Weekly briefing:** read all tabs → render the **deterministic-template** sections — week ahead · reminders firing this week · overdue · Money · Goals · data hygiene · system self-report · classifier accuracy → write to `Briefings/` and queue `kind=briefing`. The **Classifier accuracy** section carries the week's WhatsApp ALERT-tier counts, by-rule tally, and the <1/week false-positive target; the **self-report** line carries runs-green, messages classified, tombstone skips, and LLM spend. *(Deterministic by design — no LLM call. An LLM-written "five-scene narrative" (the week's spend · a kids' moment · next week's three things · a goal line · a contract heads-up) over whole-Sheet context is a deferred v1.1 lane — `ROADMAP.md` §ai-briefing — not a gap: it needs a whole-Sheet→provider privacy call and keeps this template as its proven fallback.)*

Both message kinds are budget-exempt and subject only to quiet hours.

### 7.3 WhatsApp summarizer — hourly

Reads new inbox lines → classifies: **hard rules first** — a critical/safety keyword is a budget-exempt ALERT that **pierces even a muted group**; below that tier a **muted group raises nothing** (mute is itself a hard rule); otherwise, for non-muted groups, alert-keyword / teacher-evening / vaad-utilities → ALERT and media-only → ROUTINE — then the LLM (the configured provider) for the rest with up to 3 messages of group context, then a deterministic keyword fallback when no key is present → writes Inbox + Archive rows → ALERT rows route per group config → `outbox(kind=alert)`, or `kind=critical` on a critical-keyword match. A digest-only group with a critical match raises a "⚠ NEEDS A LOOK" block at the top of the next digest. Family-group criticals do **not** override digest-only routing (critical_keywords already bypass per group). *(Mute is the one knob that silences ordinary alerts entirely; a true safety keyword is the deliberate exception — PO call 2026-06-18.)*

A weekly accuracy pass (`automation/accuracy_review.py`) re-reads the week's Inbox rows and re-derives each ALERT's triggering rule by reusing the live `hard_rule_alert` function — so the review can't drift from the classifier, and needs no schema change. It surfaces ALERT-tier false positives against the **<1/week** bar, folds a compact pulse into the weekly briefing, and writes a full operator report to `Briefings/`. The "fix" for a false positive is narrowing the offending keyword pattern.

### 7.4 Bridge — Baileys, Node, systemd service

Listens to **groups** → `inbox.jsonl`. Polls `outbox.jsonl` every 15s → sends **1:1 only** to JIDs present in `recipients.json` (machine-local, gitignored); any other target is refused and logged. Per-(id, target) dedup against a sent ledger. Heartbeat file on connect / message / 15-min idle. Never posts to groups. Inbound 1:1 chats from the two known senders (`recipients.json` JIDs) are **silently logged** to `replies.jsonl` as raw material for the v1.1 reply-parsing feature — the bridge does **not** act on them and **never acks** (no affordance it can't honor — §3.7); every other 1:1 sender is dropped. *(LID-addressed 1:1s fall through the known-sender guard and are dropped until v1.1. Self-hosted Baileys, not a paid API: ₪0 marginal, no business-API verification or template approval, free-form Hebrew. Pinned to Baileys 7.x on ESM — the pre-7 line broke companion self-sends after WhatsApp's LID identity migration.)*

### 7.5 Outbox (`lib/outbox.py`) — the chokepoint

```
queue(to: "adar"|"shanee"|"both", body, kind: "alert"|"critical"|"briefing", *, source, msg_id)
  briefing → exempt from budget; subject to quiet hours (22:00–07:00 → hold to 07:00)
  alert    → consult ledger[date][recipient]; if ≥2 → defer: append to tomorrow's
             digest, log alert_suppressed_by_budget; else send + increment
  critical → send immediately, any hour, log budget_bypassed_critical
  all      → idempotent by (id, target); ledger + queue are durable JSONL on disk
```

The ledger is shared across **all** senders — the engine and the summarizer can't each spend a separate 2/day. *(The daily digest is `kind=briefing`, not `alert`: as an alert it consumed a budget slot and, worse, an over-budget alert defers *into* the next digest — which is itself the message, a circular dependency.)*

**Delivery confirmation (cross-run reconcile).** The bridge delivers asynchronously and records each confirmed send to `whatsapp_sent.jsonl`. So queueing is **not** delivery: the daily digest does not stamp on queue — it writes a pending row per recipient to `digest_pending.jsonl`, and at the start of every `--send` run `reconcile_deliveries()` stamps Last Sent / Status (§7.1), clears the reported fail-flag lines, and consumes the budget-deferred alerts that digest carried — but only for the entries the bridge has since confirmed. An entry left unconfirmed past 48h is dropped and logged; its reminders stay unstamped and re-fire (fail loud, degrade quiet). The §10.2 SMTP fallback is itself the confirmation, so it stamps and consumes inline. Because the stamp now lands a run *after* the digest, reconcile re-reads the Sheet and honors the engine's own write guards: it never overwrites a row the user has since completed (Status Done/Skipped), rescheduled, or that recurrence bumped, defers a row with a §8.3 write in flight, and dates Last Sent to the digest's own send day. *(A bounded in-run wait was tried and rejected: it duplicates digests if bridge latency ever exceeds the window and couples the run to the bridge's async timing. Reconcile stamps whenever the bridge eventually confirms — next run or the one after.)*

### 7.6 Dashboard (PWA)

Read: `batchGet` over all bound ranges (UI contract in `DESIGN.md`). Write: per the §6.1 write contract — optimistic UI, an offline queue in `localStorage.pendingWrites[]` (cap 50), flushed on reconnect in tap order, failed flushes retried on the next online event. The write surface resolves its target columns by **header name** (not a hardcoded letter) and **pauses writes on header drift** — the JS mirror of the engine's §7.1 schema guard (Lane C), so a restructured Reminders tab can't be written by position. Identity: Google sign-in → `Settings.UserMap` → display name. **Switch-account** (D3) is a real OAuth re-auth — the Google account chooser (`prompt:'select_account'`), never a label flip — so `LastDoneBy` always reflects the parent actually signed in; cancelling the chooser is a no-op and the superseded token is simply dropped (never revoked — `revoke()` would drop the shared user+client grant). Settings carries **no** notification-toggle, bank-connect, or export controls (D7). Demo mode renders `mock_data.json` and never calls gapi.

**Cross-domain timeline (read-only derived view, V3.6).** The Today *Timeline* tile flattens every dated row already read above into one chronology, governed by two ratified rules. **Milestone-inclusion:** one timeline item per dated field — `Reminders.Due Date` (excluding the terminal Status values {Done, Skipped}), `Calendar-Events.Date`, `Goals.Target Date`, `Health.Next Due`, `Car`'s {Annual Test, Insurance Renewal, License Expiry}, `Education.Next Key Date`, `Contracts.Renewal Date` — kept only within the window `today − 14d … today + 5y`; undated, out-of-window, and blank-title rows are excluded (a dated row with no Title can't render a coherent card — the timeline's fourth, defensive exclusion). **Domain→category** (the filter set): each item carries exactly one of `finance · health · car · education · goals · contracts · calendar · other`; calendar and other are assigned by source, every other source maps to its own domain, and a reminder's free-text `Domain` (§6.1 col B) maps near-identity (lower-cased) with any unrecognised value falling to `other` — **never dropped**. The view is read-only (no write contract — items are edited at their source tab) and fully Sheet-derived (no new tab). This timeline is **Education's only Today home** (Education has no portfolio tile).

### 7.7 Love-note endpoint (V3.7)

The one dashboard datum that is **neither the Sheet nor the outbox** — the sanctioned exception to §3.1 (its authoritative home is an appliance file, not a Sheet tab). A parent-to-parent ephemeral note over a small authenticated dashboard→appliance HTTP endpoint (`automation/love_note_server.py`, bound to localhost; a Cloudflare Tunnel fronts it). **One note per direction** (Adar→Shanee, Shanee→Adar), stored as one flat JSON file per direction under the appliance state dir (`/var/lib/family-inc/lovenote`, mode 700), **expiring at 24h-or-on-replacement** — lazy on read **plus** an hourly sweep (`sweep_love_notes.py`). Replacement is atomic and silent: the appliance holds only the *current* note per direction (no version history), so a note the sender replaces before the recipient's next open is simply never seen. **No push:** a note appears on the recipient's **next dashboard open**, spends **no alert budget**, never rides `lib/outbox.py`, never writes the Sheet, and carries **no delivery/"seen" signal** back to the sender (§3.7) — `DELETE` clears only the author's own note. **Auth:** the PWA forwards its live Google access_token; the server verifies it once against Google's **tokeninfo** endpoint (which also exposes the token's audience — so when the dashboard's OAuth client id is configured [`FAMILY_INC_LOVENOTE_AUD`] the server rejects a token minted for any *other* app, closing the confused-deputy gap), maps the verified email to a parent via `Settings.UserMap` (unknown → 403), then **drops the token — never logged, never persisted** (a short in-memory cache keyed by the token's SHA-256, never the raw token, avoids re-hitting Google under a burst). **CORS** is allow-listed to the Pages origin only; a blank/unset origin denies every browser, so the feature **self-disables fail-safe** (never promise a dead affordance, §3.7). The listener also caps request bodies (413) and rejects unframed (chunked) bodies pre-auth. **Text only** — voice is a frozen phase-2 (§4).

## 8. Cross-cutting policies

### 8.1 Alert budget

2 unsolicited messages / recipient / day, enforced only in `lib/outbox.py`. When over budget, trim priority: OVERDUE and kids' Health always survive; **Goals are de-prioritised first** (`DROP_FIRST_DOMAINS` — sorted out ahead of WEEK/MONTH-OUT, since the weekly briefing already covers them; not a hard exclusion — a Goals fire still rides along when there is room under the per-digest cap), then WEEK/MONTH-OUT. If >10% of fires are suppressed over a rolling 14 days, the next weekly briefing says "budget is biting — raise the cap or tighten the rules?".

### 8.2 Quiet hours

22:00–07:00 Asia/Jerusalem. Alerts and briefings hold; criticals do not.

### 8.3 Offline write / engine race (tombstone)

The dashboard stamps `WriteQueue_Tombstone` (ISO-T datetime) on every write; queued offline writes re-stamp it **at flush time**, so the cell always carries the moment the write *landed* on the Sheet. The engine skips a row while `tombstone + 6h > now()` (one clock: the window starts at flush, not at the tap). *(Date-only tombstones had silently disabled this guard — the hour resolution is load-bearing.)* Residual accepted race: a phone that flushes a queued tap inside the same minute the engine reads → at most one duplicate alert; the flush itself is idempotent. Every skip is logged with the tombstone age, and the weekly briefing reports "N tombstone skips · max age seen" — widen the window from data, not anecdote. **Background-timer races (accepted):** the Sheet-writing timers are deliberately staggered — finance 06:00, reminders 07:25, digest 07:30, property on its own slot — so they don't run concurrently, and each writes a disjoint tab/column set (finance → `Finance-*`; engine + digest → `Reminders`; property → `Property-Listings`); `gspread` batch updates are atomic per call. v1 attempts no cross-timer transaction: the residual is a run that overran into the next timer's window, at most a stale read that self-heals next run.

### 8.4 Idempotency & dedup

Outbox messages carry stable ids: summarizer `wa-{msg_id}`, briefings `brief-{type}-{date}` — the daily digest queues once per recipient as `brief-daily-{date}`; **individual reminders carry no outbox id** (the engine computes, the digest delivers). The bridge dedups per (id, target). Engine re-runs on the same day are no-ops (the Last-Sent guard). The digest's confirmed-delivery stamp (§7.5) keys its pending rows on the same `brief-{type}-{date}` id and drops a settled row once stamped, so reconcile is idempotent — a re-run never double-stamps or re-consumes a deferred alert.

### 8.5 Time & locale

All schedules in Asia/Jerusalem (DST-correct via system TZ, never UTC offsets). Dates are **displayed** DD/MM/YYYY; week starts Sunday; money `Intl.NumberFormat('he-IL', ILS)` / `₪{n:,}` in Python. The one **stored** date both surfaces write, `Reminders.Due Date` (§6.1 col D), is a real Sheets date — machine writes emit the **ISO** literal (locale-safe) and the reads accept ISO or the he-IL DD/MM·DD.MM render (Lane C), so it round-trips regardless of the Sheet's locale. Chrome strings are Hebrew-default with an English fallback; data values stay Hebrew always. Machine-written datetime stamps (Last Sent, DoneAt, WriteQueue_Tombstone) are ISO-8601 `T`-form **text** on both surfaces — the `T` stops Sheets from coercing them into locale date cells, so they round-trip byte-exact and keep the hour resolution the 6h tombstone window needs.

### 8.6 Privacy & security

- WhatsApp plaintext exists in places we don't fully control — Meta's servers (inherent) and the configured LLM provider — plus the VPS we do. Exactly **one** LLM provider is configured at a time (DeepSeek by default — §8.7), and **every provider is treated identically**: the privacy guarantee is not *which* vendor may see the text but *how little it ever sees* — LLM classification sends one message + up to 3 context messages, never whole threads or cross-group context, whichever provider is active. Switching providers is an operator key-swap, not a policy change. *(DeepSeek is the default on cost; it routes group plaintext through PRC-jurisdiction infra — a deliberate privacy-vs-jurisdiction call by the POs, accepted because volume is negligible, every path has a keyless fallback, and the operator may swap providers at will.)*
- **Finance categorization:** the configured LLM provider may assign a category to the **rules-miss remainder only** — a transaction's **description + amount**, never account numbers, balances, credentials, identifiers, or the whole ledger. The on-box rules engine tags first, so most transactions never leave the box.
- **Love-notes (§7.7):** the appliance holds one ephemeral text note per direction (`/var/lib/family-inc/lovenote`, mode 700, never in the repo/backups); the caller's Google OAuth access_token is verified once against Google and then **dropped — never logged or persisted**, and CORS is allow-listed to the Pages origin. No voice/media is stored (text only) until the §4 carve-out.
- Secrets — `recipients.json`, the service-account JSON, `FAMILY_INC_DEEPSEEK_API_KEY`, `FAMILY_INC_APIFY_TOKEN` (property secondary source), `bank_creds.json` (read-only finance logins), SMTP password — live in `/etc/family-inc/`, mode 600, never in the repo. The **device-trust browser profiles** (Max/Cal only; `/var/lib/family-inc/finance/profiles/<provider>`, mode 700) are appliance-local bearer state — not in `/etc`, never in the repo or backups.
- Phone numbers / JIDs appear nowhere except `recipients.json` on the VPS.
- The service account has access to exactly one spreadsheet, nothing else in Drive.
- Known accepted risk: Baileys is an unofficial client — some account-ban risk, elevated on datacenter IPs. Mitigations: household volume (≤10 msg/day), a person-to-person pattern, a dedicated paired session. Fallback chain in §10.

### 8.7 LLM usage

One wrapper (`lib/llm.py`); model ids in config, not at call sites; per-call cost logged to `logs/llm_costs.csv`. The active provider is chosen by **key presence**: `FAMILY_INC_DEEPSEEK_API_KEY` → DeepSeek (`deepseek-chat`, via its OpenAI-compatible endpoint over stdlib urllib — no SDK); else `ANTHROPIC_API_KEY` → a Haiku-class provider, **treated identically** (the minimal-payload rule in §8.6 is provider-independent); else the deterministic fallback (keyword classification, template briefing). Classification requests strict JSON mode and tolerates trailing prose in the reply. The weekly briefing makes no LLM call. The weekly self-report line (ENGINEERING §8) carries the week's LLM spend; the first briefing of each month reports month-to-date.

## 9. Failure modes

| Failure | Detection | Behavior |
|---|---|---|
| VPS down | heartbeat stale (external check optional, v1.1) | total outage; on recovery the outbox flushes; missed runs reported in the next briefing |
| Bridge logged out / WA break | heartbeat stale >12h | digest prepends "⚠ BRIDGE SILENT Nh"; >24h → email-fallback digest to both adults |
| WhatsApp account banned | send failures + logout | switch to email digests same-day (one-line config); decide the §10 path |
| Sheet API 5xx / quota | gspread retries with backoff, then skips the run | "missed yesterday" line in the next successful run |
| LLM API down / keyless | exception → fallback path | templated briefing / keyword classification; logged, not alerted |
| Bad row data (unparseable date) | per-row try/except | row skipped + listed under "data hygiene" in the weekly briefing |
| Sheet header drift | engine header validation, every run | run aborts before firing anything; schema_drift logged + surfaced |
| Outbox/inbox JSONL torn line | reader skips the malformed tail | self-heals next poll (single-writer appends) |
| Clock skew / future tombstone | tombstone > now | treated as valid for the full window, anomaly logged |
| Both adults edit the same row | last-writer-wins | acceptable at household scale, by decision |

## 10. Fallback chain (delivery)

1. **Baileys bridge** (primary).
2. **Email digest** to both adults — automatic and mechanical: the daily-digest task checks the bridge heartbeat before queuing; if stale >24h it sends the identical rendered content via SMTP and notes "delivered by email — bridge down Nh". No watcher process; the sender itself degrades. Every send-run logs its transport to `logs/delivery_log.csv`; **email-fallback days are degraded, not green** — the weekly briefing surfaces them, so a dying bridge can't hide behind a working fallback.
3. **Twilio WhatsApp** — documented fallback, not in code. Adopt only if Baileys proves unworkable (recurring bans); accepts template-approval constraints.
4. **Inforu SMS** — deep fallback, Hebrew-capable, ILS billing; revisit only after 2+ failures above.

## 11. Acceptance (v1 — met)

v1 went live and was accepted on 2026-06-15 (tagged `v1-live`): the 07:30 WhatsApp digest reached both phones three consecutive days with no intervention; a reminder completed a full done→recurrence cycle; an alert-keyword group message reached the right recipients while a family-group meme reached no one; a critical keyword fired after the daily budget was spent; an offline dashboard write flushed on reconnect with the engine logging a tombstone skip and no duplicate; the weekly briefing arrived with its Hebcal and budget sections and the LLM-down fallback was verified; logs showed seven green days; monthly cost confirmed ≤ ₪120. New features inherit the same bar: live, observed green on the appliance, with a deterministic fallback proven.

## 12. Data ingestion lanes

Specs for ingestion lanes that are unfrozen. All ingestion obeys the same rules: one runtime (the VPS), `lib/sheet` is the only Sheet writer, no new path bypasses `lib/outbox.py`, secrets only in `/etc/family-inc/`.

### 12.1 Property listings — Yad2 / Madlan (live)

Active house search. New listings land silently and surface in the morning digest.

| Facet | Spec |
|---|---|
| **Source** | Saved-search result pages on Yad2 (primary) and Madlan. One or more saved-search URLs per portal in `/etc/family-inc/property_searches.json` (personal criteria, gitignored). No public API: the **primary** path scrapes; a permitted **secondary** source (Apify) backs it up when the scrape is blocked and fills missing fields. |
| **Mechanism** | Headless Chromium on the VPS (run headed under Xvfb with light stealth, because a plain headless browser from a datacenter IP is challenged). A scraper loads each saved-search URL, extracts listing cards (`listing_id`, price, rooms, size, location, url, posted-at), and diffs the `listing_id` set against `/var/lib/family-inc/property/seen.json`. New ids = new listings. |
| **Secondary source (Apify)** | `automation/lib/apify.py` is the only Apify client. It is consulted **per saved-search only** when the primary is blocked/empty (backup) or returned listings with missing fields (gap-fill), then merged with the **primary always winning** — Apify only adds missed listings and fills blanks, never overwrites. Actors: `amit123~yadscraper` (Yad2, ingests the saved-search URL) and `swerve~madlan-scraper` (Madlan, parametric — needs a `{city,dealType,…}` `apify` block; params are never guessed from the URL). Strict and fail-loud: a junk item (missing id, corrupt number) is skipped; an item error is fatal **only** when a call returned items but **none** were usable; a missing token / HTTP error / timeout is a loud `ApifyError`. Apify runs from a residential proxy pool, clearing the anti-bot wall the datacenter IP cannot. Priced per result, so it runs at most **once/calendar-day per search per kind**, under the §11 ≤₪120/mo ceiling; absent the token, the whole path is inert (primary-only). |
| **Runtime** | One systemd timer (`family-property.timer`), 1–2×/day (not real-time — listings don't churn by the minute and tighter polling raises ban risk). `TimeoutStartSec` + `MemoryMax` bound a stuck browser; independent of the bridge. |
| **Sheet landing zone** | `Property-Listings`: `listing_id` (dedup key) · `portal` · `first_seen` (ISO-T) · `price_ils` · `rooms` · `size_sqm` · `location` · `url` · `status` (human-edited: new/seen/contacted/dismissed). Append-only via `lib/sheet`; a listing that drops out of results is left in place. |
| **Delivery** | New listings land **silently** and surface in a "🏠 דירות חדשות / New listings" section of the 07:30 digest. They never alert and never bypass the budget — property is not critical-safety. |
| **Failure handling** | A scrape error or anti-bot block sets the fail-flag (`OnFailure` → `logs/fail.flag`); the next digest reports "property scrape failed" and the weekly briefing surfaces persistent failures. The realized escape hatch from a persistent block is the Apify secondary; an anti-detect browser on-box is a further fallback. |

### 12.2 Finance — Mizrahi / Max / Cal (live on Mizrahi + Cal, M6)

A committed monthly finance review is the standing consumer. Scope = Mizrahi (bank) + Max + Cal (cards); **categorized + month-over-month trends**; investments/brokerage out of scope. Anomaly detection stays killed. Delivery is silent. **Live on Mizrahi (debit) since 2026-06-19** (daily read-only scrape → categorized, idempotent Sheet write); the consumer wiring (M6.3) + analysis layer (M6.4) are landing. **Cal (Visa) live since 2026-06-23** — an *immediate-debit* card whose spend also lands merchant-less on the Mizrahi statement, so its own scrape supplies the per-merchant detail and the Mizrahi-side Cal settlement lines map to an excluded **`Card Settlement`** category (not a `Finance-Budget` row → out of the actuals `SUMIFS`) so each purchase counts **once**, via the card. More cards remain — Shanee's debit card + others (`BACKLOG.md` M6.5).

| Facet | Spec |
|---|---|
| **Source** | The online portals of Mizrahi-Tefahot + Max + Cal, read via `israeli-bank-scrapers` (Puppeteer/headless-Linux, pinned 6.7.8, Node ≥ 22.13 — the library's own `engines` floor). No public API; the library drives each portal's web session. **Read-only by nature** — it fetches balances + transactions and cannot move money. |
| **Mechanism** | A systemd timer runs `automation/finance/scrape.js`: logs into each provider with creds from `/etc/family-inc/bank_creds.json`, fetches balances + a **fixed ~45-day** transaction window (`FAMILY_INC_FINANCE_WINDOW_DAYS`; `Txn-ID` dedup makes overlapping reruns idempotent, so a fixed window is simpler and correct — no since-last-success state to keep), writes one CSV per provider to `/var/lib/family-inc/finance/`. `automation/finance_ingest.py` then normalizes, dedups on `Txn-ID`, and writes via `lib/sheet`. Node scrapes; **Python owns every Sheet write.** The local CSV is the only staging — no Drive. Same-day reruns overwrite the day's CSV and dedup on ingest → idempotent; the import advance gates on a successful Sheet write. **Categorization:** an on-box keyword→category rules engine tags each transaction at ingest; the configured LLM provider assigns categories the rules miss (description + amount on the rules-miss remainder only — §8.6). |
| **Runtime** | One systemd timer (`family-finance.timer`), **~06:00 daily** — ahead of the 07:25/07:30 morning runs so balances are fresh for the M6.3 finance consumers (the weekly briefing Money section + dashboard drawer + the >35d stale-import line). The **daily run is headless** Puppeteer (no Xvfb). The one-time `--auth` device-trust login (Auth model, below) runs **headed under xvfb + x11vnc** — the box already runs xvfb for the property scraper. Cadence is the first tuning knob: if Max/Cal re-challenges prove noisy, drop the cards to 2–3×/week and keep the bank daily. |
| **Auth model** | Read-only portal logins live at `/etc/family-inc/bank_creds.json` (mode 600, never in the repo, never logged). This is where the "no credential storage" non-goal is narrowed — *appliance-local, read-only financial logins*: this creds file **and** the per-provider device-trust browser profiles it authorizes (below), both appliance-local — while "no money movement" stays absolute (the scrapers cannot transfer). **2FA / device-trust:** Mizrahi is password-only. Max + Cal can re-challenge a fresh browser, and `israeli-bank-scrapers` 6.7.8 has **no programmatic OTP entry** for them (their credentials are username+password only; the library's `triggerTwoFactorAuth`/`otpCodeRetriever` path is OneZero-only). So **Max + Cal** each get a **persistent browser profile** (a Chromium `--user-data-dir`, mode 700, under the finance staging dir) — the device-trust cookie jar, a bearer artifact, hence covered by the narrowing above; **Mizrahi**, password-only, stays ephemeral (no stored session). A **one-time operator-driven headed login** — `node automation/finance/scrape.js --auth <provider>`, run on-box under xvfb+x11vnc viewed over an SSH tunnel (`deploy/FINANCE.md` §4) — clears the challenge once by hand; the portal then trusts that profile and the **daily headless run reuses it** and is not re-challenged. A re-challenge still **fails loud** (next digest); the remedy is re-running `--auth` (a same-window rerun stays idempotent via `Txn-ID` dedup). This is the persisted-session hardening, **brought forward to M6.2** because the cards need it to run unattended. **Cal live (2026-06-23):** the debit-only assumption was wrong — Cal was hooked up via the headed `--auth cal` login (the **first** real exercise of this path; verified daily-headless after), confirming the spec above against a live card. Remaining cards split by portal: one on a **new** portal needs a ~20-min `--auth` of its own; one on an **already-connected** login needs **no new auth** — it rides the existing scrape. **Shanee's debit card (M6.5, 2026-06-23) is the latter** — a Cal-cleared immediate-debit card on the connected Cal login, so its only repo change was the mirror token, no `--auth`; pending the 06-26 box-verify that her per-merchant rows actually ride that connected login (else a second `cal`-keyed provider). Either way each immediate-debit card also gets a **`Card Settlement`** mirror token (the Mizrahi side maps there so the spend isn't double-counted); the exclusion tokens sit **below** the merchant rules (a last-resort fallback) so a merchant-bearing line always categorizes by its merchant first — no other code change. |
| **Sheet landing zone** | Two tabs via `lib/sheet`. **`Finance-Accounts`** — one row per account/card, current-state (upserted on `Account Name`): `Account Name` · `Type` · `Bank/Provider` · `Last 4` · `Owner` · `Currency` · `Last Imported` (drives the >35d stale-import warning) · `Balance Snapshot` · `Notes`. The importer overwrites only the machine-owned columns, so a human's `Owner`/`Notes` survive a re-import. **`Finance-Transactions`** — one row per transaction, append-only, `Txn-ID` dedup: `Date` · `Account` · `Description` · `Amount (ILS)` (signed) · `Category` · `Cat-Source` (rule/llm) · `Txn-ID` · `Imported-At`. `Txn-ID` is a **stable hash of `Date|Amount|Description|Account`** (the natural key) — the provider `identifier` is recorded in the CSV but is **not** the key, because `israeli-bank-scrapers` reuses one identifier across distinct Mizrahi charges (trusting it dropped ~70% of rows on the first live import, 2026-06-19); the natural key separated every transaction with zero collisions and is stable across re-fetches. **Column order is load-bearing** — the `Finance-Budget` actuals `SUMIFS` over Date (A) / Amount (D) / Category (E). The date criteria are a **text-prefix wildcard** on the ISO-text `Date` (`<yyyy-mm>&"*"` for the month, `<yyyy>&"*"` for YTD, plus a `Last Month (ILS)` column for month-over-month): a serial `DATE()` window read ₪0 against the RAW-appended text dates, and keeping the append RAW leaves `Txn-ID` dedup intact — so text-prefix is chosen over a `USER_ENTERED` append, which would coerce `Txn-ID`/`Account` (M6.4). M6.3 installs the same formulas onto the live `Finance-Budget` tab via an idempotent installer (`automation/finance_budget_formulas.py`, single-sourced from `lib/finance_budget` and pinned against the seed) that stamps the machine columns only — a category row's Category/Target and every Notes cell are human-owned and never written (only the TOTAL row's Target is a machine `=SUM`), so there's no hand-copy and the stray-formula class is impossible — then verifies actuals go non-zero on the first real month. Retention: keep all (low volume; the monthly review wants history). |
| **Categorization & acceptance** | Two stages at ingest: an on-box keyword→category rules engine, then the LLM gap-fill on the rules-miss remainder (description + amount only — §8.6). Ingest tags **new rows only** (idempotency), so a rules change (e.g. the M6.5 `Card Settlement` exclusion, added after the first Mizrahi imports) reaches history only by a deliberate **one-time backfill**: `automation/finance_recategorize.py` re-runs the same engine over the currently-**blank** rows and writes `Category`/`Cat-Source` back **surgically** (blank rows only → a human or prior categorization is never clobbered; idempotent; header-guarded; live-or-`--sheet` only, never the seed). The milestone metric is **coverage** — `automation/finance_coverage.py` (read-only) reports categorized vs the by-design-excluded `Card Settlement` mirror vs genuinely-blank wrappers, by account, naming the still-blank merchants. The accept bar is set **report-first**: the first live read (**2026-06-28**) landed coverage at **88 % (137/155 budget-eligible rows** — total minus the excluded mirror; an added `OBSIDIAN` rule lifts it to ~89 %), **accepted** — the headline is gated by *structure*, not classifier quality: of the 18 still-blank rows ~12 are merchant-less wrappers (Leumi ATM cash ×9, BIT/PAYBOX P2P, an ANOMALY) that correctly return UNKNOWN, so ~96 % of *genuinely-categorizable* rows carry a category. The matching summarizer gate passed clean (**503 classified over the 7-day window, 0 ALERT-tier FP**). This is **coverage** (a category is present), not **correctness** (the category is right) — a true categorizer false-positive rate needs a human-mark channel, **deferred** (`ROADMAP.md` §classifier-fp-metric, rank 12). A **household-specific local merchant** (e.g. a local grocery) cannot enter the public, portfolio-safe rules seed (national brands + generic labels only) and there is no box-local overlay yet → the **finance-local-rules-overlay** forward item (`ROADMAP.md`); until it lands, such a merchant stays blank by design. The **WhatsApp summarizer** keeps its own separate accuracy gate — **< 1 ALERT-tier false positive / week** (`accuracy_review.py`, §7.3). |
| **Delivery** | Finance lands **silently**: balances, per-category spend, month-over-month trends, and actuals-vs-`Finance-Budget` surface in the weekly briefing **Money** section + the dashboard **Money** drawer, alongside the >35d stale-import line — **never an alert, never a budget bypass.** The only finance *message* is fail-loud. A ">₪500 single charge" alert is deliberately not wired (it's an alert path that brushes the killed anomaly lane — deferred to a deliberate PO call). |
| **Failure handling** | An OTP / device re-challenge (remedy: re-run `--auth <provider>`), a site-change error, or a Sheet-write failure sets the fail-flag; the next digest reports it ("⚠ <provider> צריך אימות מחדש" / "finance scrape failed") and the weekly briefing surfaces persistent failures + the >35d stale line. CSVs are retained on a Sheet-write failure (no data loss; retry next run). If a Cloudflare wall ever appears, the escape hatch is the maintained anti-detect fork on-box, then a managed-proxy pivot. A box compromise leaks read-only visibility only — no transfer capability. |

## 13. References

`ENGINEERING.md` — runtime, repo layout, testing, ops. `DESIGN.md` — dashboard UI, message design system, i18n. `BACKLOG.md` — current status; what's frozen. `ROADMAP.md` — the sequenced forward plan + v1.1 lane contracts. `Archive/` — the dated decision history and superseded docs.

=== End: SPEC.md ===

=== File: BACKLOG.md ===
# Backlog

*The only live status record. What's shipped, what's in flight, what's parked, what's frozen.*
*Legend: ✅ done · 🔵 in progress · ⬜ todo · 🧊 frozen. Scope and acceptance live in `SPEC.md`. The dated history of how each item landed lives in `Archive/`.*

## Now

**▶ Focus:** **(PO call — recommended)** **deploy the code-complete v3 dashboard** — the Pages publish that un-gates V3.1–V3.8 + the love-note text endpoint (tunnel-gated) is the largest block of already-built, deploy-gated work — with **Shanee's budget-vocab migration** the parallel data task (`deploy/FINANCE.md §6`; firms the provisional vocab so Fees/Income/Shopping actuals stop reading ₪0). Queued behind it: `ROADMAP.md` §2 rank 10 (Lane E correctness remainders), the new **finance-local-rules-overlay** (§3), rank 12 classifier-fp-metric. **✅ M6 finance — ACCEPTED & CLOSED 2026-06-28:** the box-run gate ran live — coverage **85% → 88%** after the backfill (137 cat · 117 excluded · 18 blank of 155 budget-eligible; the ~66 Cal mirrors were *already* excluded by `finance_ingest` so the dry-run added 0 — the 3-pt lift was 5 DeepSeek gap-fills), plus an `OBSIDIAN→Shopping` rule (→ ~89% on re-run); the summarizer half passed clean (**503 classified / 7d · 0 ALERT-tier FP** vs the <1/week bar). **Bar accepted report-first** — 88% is structure-gated (~12 of 18 blanks are merchant-less wrappers: Leumi ATM cash ×9, BIT/PAYBOX, an ANOMALY → ~96% of *genuinely-categorizable* rows carry a category). **Deferred:** a household-specific local merchant (e.g. a local grocery) can't enter the public seed → the **finance-local-rules-overlay** forward item. Canon graduated: SPEC §12.2/§62 + `deploy/FINANCE.md §7` (recipe fixed to `uv run --no-sync python` as `familyinc`). **▶ Acceptance tooling landed 2026-06-26 (this session) — gate now box-run-only:** the one-time **re-categorize backfill** (`automation/finance_recategorize.py` — re-runs the engine over blank rows, surgical `write_cells` back-write, idempotent, blank-rows-only so a manual/prior tag is never clobbered; the ~66 Cal-mirror lines (box-unverified count) → `Card Settlement` via the existing rule) + a read-only **coverage** surface (`automation/finance_coverage.py` + pure `lib/finance_coverage.py` — categorized vs excluded-mirror vs blank, by account, blank merchants named) — hermetic + tested (**486 green**, +18). **Threshold defined:** summarizer = **< 1 ALERT-FP/week** (ratified, SPEC §7.3); finance = **coverage, report-first** (candidate ≥90% of budget-eligible rows; correctness/FP deferred → ROADMAP rank 12). Canon graduated: SPEC §12.2 (backfill seam + coverage acceptance facet) + `deploy/FINANCE.md §7` (box-run recipe) + the **Shanee budget-vocab data-request** (`deploy/FINANCE.md §6` — she fills `Finance-Budget` A:B only). **Reviews ran on the diff:** an internal 6-lens adversarial pass (1 major — coverage `by_source` double-counted excluded settlements → fixed; +2 test-gaps, +1 nit) **and** the external `review.py` DeepSeek gate (`reviews/review_milestone_2026-06-26_22-07.md` + `_resolution.md`: **0 blockers**; 4/5 concerns Applied — header re-validate before write · dry-run under-report note · coverage header-normalize · exclusion-order test — concern 2 [torn write] Defended: `batch_update` is a single atomic call). **M6 CLOSE done (2026-06-28)** — the box-run block ran (coverage before/after · backfill · `accuracy_review.py --weeks 1`), the bar was set report-first from the live number, and the **external `review.py` milestone gate (folding in the property lane) runs on this close's diff** in the PO terminal block (stage → review → resolve → commit → push). **✅ v3 Today redesign CLOSED 2026-06-26 (V3.9 — the lane's last slice):** the external milestone review ran (`review.py` DeepSeek — `reviews/review_milestone_2026-06-26_20-47.md`; 1 Apply [SPEC §7.7 replacement-semantics clause], rest Defend/Open, **0 blockers**) alongside an internal **9-area canon-vs-code conformance audit** (every area conformant; 3 nit-level doc catch-ups Applied: SPEC §7.6 blank-title exclusion · DESIGN §4 quiet-day copy · the `userinfo`→`tokeninfo` comment fix — `reviews/review_milestone_2026-06-26_resolution.md`); SPEC §7.6/§7.7 + DESIGN §2/§3/§4/§5/§8/§9 graduated; **468 tests green**. V3.1–V3.8 (UI + i18n/a11y + the love-note text endpoint) are **code-complete, deploy-gated by the Pages publish** (V3.7 love-notes additionally tunnel-gated; voice frozen phase-2). Review follow-ups (JS interactive-logic harness · love-note rate-limit · 120-char composer hint · the Worker-vs-tunnel phase-2 PO call) → **Deferred** below.
<!-- ^ this Focus pin steers session_kickoff.py's next-session headline; retarget it when the active lane changes. -->

**🔭 Spec-ahead pass — 2026-06-20.** A full audit (**50 verified** canon-vs-code drift findings, 0 false positives) reconciled the canon to reality, and a value/risk/dependency roadmap pass produced **`ROADMAP.md`** — the sequenced v1.1 plan + per-lane forward contracts (5th canon doc). PO calls landed: GAP-7 → **fix (fail loud)**; reviewer default → **`review.py` flipped to DeepSeek** (code now matches the "DeepSeek default" canon; ollama is the keyless fallback); the 3 never-built DESIGN components (progress arc, connection pill, skeleton/shimmer) → **removed**; spec-ahead → **ROADMAP.md**. ~30 drift edits applied across SPEC/ENGINEERING/DESIGN/README + code one-liners (git history is the dated record). Suite **390/390** green, tree clean at HEAD. **CI gate (lane 1) built this session (2026-06-22) — see the dedicated paragraph below; next build lane = GAP-7 Hebcal fail-loud (`ROADMAP.md` §2 rank 2).** Two Brief-2 stragglers that had fallen off the board are now tracked: **reminders-engine#1** (closed by the SPEC §8.4 reconcile — no `rem-` id is emitted) and **reminders-engine#3** (OVERDUE 3-day boundary test, folded into Lane E). **Box-side verification ran 2026-06-23 (the second VPS hour) — see the dedicated paragraph below; the asserted-live claims are now box-verified.** Open before the 06-26 gate: define the classifier-accuracy **pass threshold**; **fix the live categorization yield** (the VPS hour found ~77% of live transactions uncategorized → `Finance-Budget` actuals understated).

**✅ CI gate (ROADMAP §1, lane 1) — merged to `main` 2026-06-23 (`9bf50cb`).** New `.github/workflows/tests.yml` runs the hermetic suite on every push + PR to `main`, so a red commit can't merge. Three parts: the **pytest gate** (mirrors `deploy.sh`'s `FAMILY_INC_SHEET_ID= uv run --frozen pytest -q`, + Node 22 so the `@requires_node` syntax-check tests run, not skip); a **repo-wide PII-leak guard** (`tests/test_repo_pii_guard.py`) scanning every tracked text file via patterns extracted to **`automation/lib/pii.py`** — one source of truth, now also backing the seed guard (`test_seed_safety.py` refactored, behaviour identical) — **scoped + allowlisted** per PO call (synthetic-by-design `tests/`/`seeds/`/`reviews/`/`Archive/`/`mock_data.json`/lockfiles exempt; the new transaction-shaped `ILS_AMOUNT` skips `.md` prose; identifiers scanned everywhere); and a **`config.js` smoke** (`tests/test_dashboard_config_smoke.py`) pinning `pages.yml`'s sed anchors + `node --check`. Built as **pytest, not a grep step** (rides `deploy.sh` on the box — no `deploy.sh` change) and runs on the **whole tree, no path filter** (so a PII paste anywhere trips it) — both deviations from the §1 sketch, recorded in `ROADMAP.md`. Suite **390 → 421** (+26 pattern regression cases + guard + smoke). Adversarially reviewed (4 lenses). **No external `review.py` gate**: a hermetic test addition, no spec/arch/policy change (CLAUDE.md §6). **The first Actions run (2026-06-22) was RED** — `astral-sh/setup-uv@v8` is unresolvable (setup-uv publishes floating major tags only through v7; v8 exists only as full release tags like `v8.2.0`), so the job died at *Set up job* in ~3s with empty logs; the earlier "`@v8`, verified against the live tag list" note was wrong (`v8` is a release prefix, not a usable ref). **Fixed by pinning `@v7`** (`5168c6d`); first green run confirmed 2026-06-23, then **merged to `main`** (`9bf50cb`, fast-forward, bundled with the finance-lib bump). Lane 1 closed; the gate now guards every PR to `main`.

**✅ Box-side verification (ROADMAP §3.0 lane 7) — ran 2026-06-23 (the second VPS hour).** A read-only 36-check appliance sweep confirmed the live system is **fundamentally healthy**: bridge up + daily digests delivered to both phones (baileys), all 7 timers + 16 units byte-match the repo, single sudo capability + secrets locked down (Mizrahi-only, none in git), outbox budget/quiet-hours/email-fallback/GAP-2 contracts intact, summarizer on DeepSeek (0 fallback drops), property + backups working, live Sheet reads verified (Txn-IDs 117/117 unique, no doubling). **Three findings, all resolved or triaged:** (1) the box was **3 days stale** (`c282afb`, −4 commits — violating committed≠deployed) → **`deploy.sh` to HEAD** (`9bf50cb`); (2) the **finance scrape was down since 06-22** — an `israeli-bank-scrapers` `#/change-pass` URL timeout while a *human* login showed no password-change screen (library-vs-site drift, or a transient bank hiccup — **not** a forced password change) → **bumped 6.7.3 → 6.7.8** (5 patches behind; live re-scrape green, fresh data); (3) **categorization is ~77% blank** (90/117 rows) → a **prioritized M6.4 item before 06-26** (see M6.4). The build of the read-only runbook + adversarial check ran as a Workflow; execution was PO-on-box (no box access from the repo machine).

**v1 is live and accepted** (since 2026-06-13, tagged `v1-live`): the morning WhatsApp digest, the weekly briefing, the dashboard write-back loop, and the group summarizer all run unattended on the appliance. The **property tracker** is live (Yad2 on-box + Madlan via Apify). The summarizer runs on **DeepSeek**. **Finance ingestion (M6) is live on Mizrahi (debit) since 2026-06-19** — daily read-only scrape → categorized, idempotent Sheet write; M6.3 (consumers) + M6.4 (analysis) remain; **Cal (Visa) hooked up 2026-06-23** (an immediate-debit card whose own scrape brings the categorizable merchant detail — ~90% categorized) so the **cards lane is un-deferred** (M6.5; **Shanee's debit-card mirror landed 2026-06-23** (box-verify pending) — a Cal-cleared card on the connected Cal login, no new auth; more statement cards to add). The M6 classifier-accuracy run + external milestone review are **gated to ~2026-06-26** (a week of live finance data from go-live). The two summarizer-review items remain gated ~2026-06-20.

**✅ Audit fix lane — Brief 1 (blocker + 7 majors), landed 2026-06-18** (from the 2026-06-18 full-project audit in `reviews/`): bridge 1:1 chats are now **log-only, no ack** (B1, SPEC §7.4); the candle-lighting line fires on **erev-chag** too (B2); **criticals pierce mute** while non-critical rules are suppressed in muted groups, closing the budget-bypass (B3, SPEC §7.3); LLM privacy reconciled **provider-agnostic** (B4, SPEC §8.6/§8.7); finance gap-fill **chunk-loops** so a large first import is fully categorized (B5, M6); `deploy.sh` installs the **finance Node deps** + restores `--frozen` (B7, M6 — unblocks M6.2); the weekly briefing carries the **ENGINEERING §8 self-report line** (B6); the dashboard offline queue **caps at 50 with a one-shot warning** (B8). Tests green (350). **Brief 2** (10 gaps + minors + disputed) remains open. The fix touched privacy/delivery/budget → the `review.py` gate **ran 2026-06-18** (DeepSeek; `reviews/review_milestone_2026-06-18_16-41.md`): B1/B4/B5/B7/B8 affirmed; one false-positive defended (the mute short-circuit already follows the critical check), `chag_candles` window widened to +5d (Applied), and the dashboard-recurrence-bump finding routed to **Brief 2 GAP-4** (Open — pre-existing, out of lane).

**🔵 Brief 2 (small fixes) — Lane A + Lane E canon-hygiene landed 2026-06-18.** Lane A (finance hardening, M6-critical): GAP-1 `Dining`→`Dining out` aligned + a guard test pinning `rules.vocab ⊆ budget` (Fees/Income/Shopping held as a tracked allow-list **pending Shanee's budget-vocab migration** — the authority); finance-ingest#3 distinct in-batch-dup counter; OTP "interactive" promise scrubbed to truth (decision #1); fixed 45-day window doc'd (decision #2); Node pin bumped to ≥22.13 (the lib's real floor); GAP-6 `data_only` caveat + tests-quality#3 comment; seeds/README documents the committed rules CSV. Lane E hygiene: `Haiku`→DeepSeek docstring, ENGINEERING boundary-rules wording, 7-timers, finance-timer/SPEC consumer wording, D-NN sweep, BACKLOG Hebcal-line correction, `FINANCE_PLAN.md`→`Archive/`.

**✅ Lane S (publish/privacy safety) — landed 2026-06-18.** Audited all 18 tabs of the committed `Family_OS.xlsx`: **confirmed synthetic by construction** — no real emails (all `example.com`), phones, Teudat-Zehut (`000000000`), JIDs, or account numbers; the only real identifiers are the principals' first names `Adar`/`Shanee`, which are **accepted-public by design** (owner-routing tokens `OWNER_TO_RECIPIENTS`, Settings UserMap, CLAUDE.md roles, git author) — so GAP-5's feared real-PII leak was unfounded. Added **`tests/test_seed_safety.py`** (the dedicated check — fails CI if any high-severity PII is ever pasted into the seed) and documented in `publish_paths.txt` why the binary seed is kept-at-HEAD-and-guarded rather than history-stripped. deploy-systemd#4: `publish.sh` gauntlet now verifies `regex:` redaction rules (PCRE) instead of silently skipping them. Tests 355→357. **Review gate ran** (DeepSeek; `reviews/review_spec_2026-06-18_19-02.md`): core decisions affirmed; Applied — seed-safety test hardened (config sanity-check so it can't pass vacuously + Unicode-domain email detection) and `publish.sh` no-PCRE failure made actionable; Defended the O(N·M) re-grep + the "rewrite gauntlet in Python" alternative (fail-loud suffices); a full seed-recovery script left as a deferred nicety (the test already fails loud + names the recovery command).

**🔵 Lane B (robustness seams) — GAP-2 + budget#3 landed 2026-06-19; GAP-3 + bridge-node#2 remain.** Earlier (2026-06-18) the bounded outbox-integrity cluster landed: **outbox-budget#1** — the budget ledger now writes atomically (tmp+replace) and reads **fail-CLOSED** (a corrupt ledger reads as cap-reached → alerts defer, never flood; loud for the operator); **outbox-budget#2** — an `fcntl` lock around the ledger read-modify-write so concurrent senders can't double-spend the 2/day cap; **GAP-10** — the bridge's `processOutbox` got per-row try/catch (one failed `sendMessage` no longer abandons the rest of the batch; transient failures retry, only terminal sent/refused suppress); **GAP-8** — the multi-timer Sheet race documented as accepted (SPEC §8.3). **✅ GAP-2 (the [high] silent-loss path) + outbox-budget#3 — cross-run reconcile, 2026-06-19.** The digest no longer stamps Last Sent/Status when it *queues*; it records a pending row per recipient (`digest_pending.jsonl`) and `reconcile_deliveries()` (start of each `--send` run) stamps — and clears the fail flag, and consumes the budget-deferred alerts the digest carried (budget#3) — only for the entries the bridge has **confirmed** in `whatsapp_sent.jsonl`. Unconfirmed past **48h** (PO call) → dropped + logged, reminders re-fire (no silent loss). The SMTP fallback confirms inline. "Sent" on the Sheet now means *delivered*. Because the stamp lands a run after the digest, reconcile re-reads the Sheet and never resurrects a row the user has since completed/rescheduled/recurrence-bumped (or one with a §8.3 write in flight), and dates Last Sent to the digest's send day — a blocker the adversarial review caught and that now has its own regression tests. The rejected bounded-in-run-wait is documented in SPEC §7.5. Transport log moved to confirmation time (`baileys` on confirm; `queued-stale` at queue only when the bridge is visibly down, or on stale-drop). The interim-risk window (silent-loss open since v1) is **PO-acknowledged**. Tests 358→369. Canon: SPEC §7.1/§7.2/§7.5/§8.4. **Review gate (delivery+budget) runs at close.** Remaining Lane B: GAP-3 (JSONL rotation), bridge-node#2 (bridge scope-guard test harness).

**Deferred** (next sessions): **Lane B remainder** (GAP-3 JSONL rotation, bridge-node#2 scope-guard harness), Lane C (dashboard), and Lane E's code-correctness + test-gap items (digest >30d flag, derive_rule, property-apify, OVERDUE-overflow test, reply_handler stub flags, the deferred "budget is biting" line — decision #3). **⬜ Dashboard JS test harness (raised V3.8; reaffirmed at the V3.9 close):** `dashboard/app.js` (~2458 lines) crossed the ~2000-line JS-harness trigger (ENGINEERING §7). V3.8 added cheap **pure-function** node tests (`tests/test_dashboard_js_pure.py` — `parseDate`/`fmtISO`/`flagFor`/`bumpDate`, no toolchain), but the **interactive** logic (desk selection + batch write fan-out, bottom-sheet focus-trap, absolute-snooze, love-note fetch) is still covered only by `node --check` + the manual DESIGN §9 smoke. A real harness (jsdom + a runner) is a **build-step decision** vs the no-build-step principle — a deliberate PO call, deferred as its own lane (don't bolt a toolchain on mid-redesign). **V3.9-review-recommended first step:** before a full jsdom harness, extract the highest-risk **write path** (`applyWrites`/`enqueueWrites`/`flushQueue`) into a DOM-free module and pure-function-test it (same no-build-step pattern as the V3.8 tests) — a bug there corrupts the Sheet, so it earns coverage even if the rest of the harness waits.
- **⬜ Love-note follow-ups (raised at the V3.9 close, `reviews/review_milestone_2026-06-26_resolution.md`):** (a) **rate-limit** the `/lovenote` endpoint — bounded today by systemd CPUQuota/TasksMax + the 120 s verify-cache, but no per-request limit; (b) a **120-char composer hint** in the dashboard note box (matches `NOTES_MAX_CHARS`, so a long note doesn't silently drop from the WhatsApp digest line — it still lands on the Sheet + dashboard either way); (c) **phase-2 PO call** — serve love-notes via a **Cloudflare Worker** instead of the box's inbound listener (removes the only inbound listener; re-architects the endpoint — a joint call alongside the frozen voice phase).

## Shipped

- **Keystone loop** — reminders engine (07:25) → daily digest (07:30) → WhatsApp, with dashboard write-back, the outbox budget chokepoint, quiet hours, and the offline-write tombstone guard.
- **Weekly briefing** (Sat 21:00) — deterministic template, the system self-report, and a classifier-accuracy section. *(The candle-lighting Hebcal line is the daily digest's, not the weekly briefing's.)*
- **WhatsApp summarizer** — 5 hard rules + DeepSeek (with keyless keyword fallback), per-group routing, critical-keyword bypass.
- **Daily digest is partner-symmetric** — both adults briefed every day; the empty-handed adult gets the quiet-day line + shared sections, budget-free.
- **Property tracker** — saved-search scrape (headed Chromium under Xvfb) + Apify secondary (backup + gap-fill, primary always wins), silent `Property-Listings` landing + morning digest section.
- **Delivery hardening** — email (SMTP) fallback when the bridge is silent >24h, fail-flag → next-digest reporting, transport logging; email days count as degraded, not green.
- **Go-live + publication** — VPS provisioned, Baileys paired (7.x/ESM), GitHub Pages + PWA pinned to both phones, repo history rewritten clean and made public.
- **Classifier-accuracy surface** — `accuracy_review.py` re-derives each ALERT's rule from persisted Inbox fields (no schema change); a compact pulse folds into the weekly briefing.

## In progress — M6 finance ingestion

Banks + cards, categorized + trends, delivered silently. Read-only logins permitted on the appliance; "no money movement" unchanged. Full contract: `SPEC.md` §12.2.

- ✅ **M6.1 — repo port + schema (hermetic, no appliance).** `automation/finance/scrape.js` (read-only login → CSV) + `finance_ingest.py` (CSV → normalize → Txn-ID dedup → `lib/sheet`: append `Finance-Transactions`, upsert `Finance-Accounts`). Finance tabs standardized to `Finance-Budget`/`Finance-Accounts`/`Finance-Transactions`; `Category`/`Cat-Source` ship present-but-blank (the budget `SUMIFS` keys on the Category column position). `family-finance.{service,timer}` + provision wiring. Tests green; no live bank contact.
- ✅ **M6.2 — appliance deploy + first live auth (the "VPS hour"), live 2026-06-19.** Box brought to HEAD + finance units installed; `bank_creds.json` placed (Mizrahi only); the 3 live tabs renamed; Mizrahi proven end-to-end — daily read-only scrape → categorized Sheet write, **98/98 transactions, idempotent on re-run**. Two live bugs caught + fixed: (1) a forced Mizrahi **password change** (cleared by hand; `FINANCE.md §0`); (2) a silent **73% data-loss dedup bug** — `israeli-bank-scrapers` hands Mizrahi a *non-unique* `identifier` and `txn_id()` trusted it (96→26); fixed to a **natural-key hash** (`date|amount|description|account`), tests rewritten + regression added (378 green), SPEC §12.2 updated, deployed. **Cards were deferred here on a "debit-only household" assumption that turned out wrong — un-deferred 2026-06-23 when Cal was hooked up (M6.5); the `--auth` device-trust path, built-but-dormant since 06-19, was finally exercised.** Follow-up (deferred): `append_rows` should re-write a missing header so a stray Sheet clear can't silently double the tab. **Runbook: `deploy/FINANCE.md`.** **Library maintenance (2026-06-23, the second VPS hour):** the daily scrape failed 06-22 on an `israeli-bank-scrapers` `#/change-pass` login-flow timeout (no real password change — a human login was clean) → bumped **6.7.3 → 6.7.8** (the library patch-tracks Mizrahi site changes; we were 5 behind); CI green, box deployed to HEAD, live re-scrape green (3 runs 06-23, fresh data). The recurring-interstitial fragility is the standing risk; if it returns on 6.7.8, escalate to a headed `--auth` run (`FINANCE.md §4`) to see what the bot session faces.
- ✅ **M6.3 — consumer wiring + close (accepted 2026-06-28).** Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning is armed (`FINANCE_STALE_IMPORT_DAYS`). **Budget-SUMIFS installer ran live 2026-06-20** (`automation/finance_budget_formulas.py`): stamped the 66 machine cells onto `Finance-Budget`, actuals verified **non-zero** (Groceries/Transport; Health ₪0 — no health debits in-window, re-check in the 06-26 accuracy run) — the M6.4 reconciliation tail is now live. *Live-tab drift caught + fixed:* the early-created live tab was one column short of canon — the M6.4 helper block's **`J` `Last Month (ILS)`** header was never backfilled, so the installer's load-bearing-column guard refused; set `J1` by hand, then it stamped clean. **Installer then hardened (390 green):** it now titles its own *absent* machine headers (incl. `J`) and stamps, refusing only on a missing *human* header (Category/Target) or a real column shift — so Shanee's migration needs only Category + Monthly Target present, no machine-column setup (`deploy/FINANCE.md §6`, `test_budget_installer_titles_absent_machine_header`). **Dashboard `config.js` was a non-issue:** Pages generates it from `config.example.js` (already full tab names) on every `dashboard/**` push, and the TOTAL-row-exclusion fix shipped via Pages 2026-06-20 — no box-side edit. The dashboard Money drawer + Sunday money summary exclude the `Finance-Budget` `TOTAL` row (fixed at the `parseAll` source so both surfaces inherit it; the briefing's `section_money` already skipped it, tested); `mock_data.json` carries a TOTAL row so DEMO_MODE matches live. **Remaining = acceptance only:** the first real monthly review (~30 days in); classifier-accuracy run + external review gated ~2026-06-26.
- ✅ **M6.4 — analysis layer (accepted 2026-06-28 @ 88% coverage, report-first).** *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates `Category`/`Cat-Source` at ingest; DeepSeek gap-fills the rules-miss remainder (description + amount only, §8.6). The briefing Money section gained per-category spend + month-over-month (the dashboard drawer reads the same tab — M6.3). **Reconciliation (the build-note landmine, resolved):** budget actuals now `SUMIFS` with a **text-prefix wildcard** on the ISO-text Date (`<yyyy-mm>&"*"`), not a serial `DATE()` window that read ₪0 — chosen over `USER_ENTERED` (which would coerce `Txn-ID`/`Account` and break dedup); the append stays RAW. Seed formulas updated + a regression test pins the form. **Installer built + tested 2026-06-20:** `automation/finance_budget_formulas.py` (single-sourced from `lib/finance_budget`, pinned against the seed) idempotently stamps the machine columns onto the live tab — machine columns only (a category row's Category/Target and every Notes cell untouched; only the TOTAL's Target is a machine sum), so there's no hand-copy and the "stray Notes SUMIFS" copy-artifact class is gone. **Gated to live data:** run it on the box (`--dry-run` first) + verify actuals go non-zero on the first real month. **PROVISIONAL** category vocab until Shanee's budget migration firms it up — when she remaps, just re-run the installer. Silent delivery; no anomaly detection. **Live categorization — reframed 2026-06-23 (Cal hookup): the earlier "~77% blank" alarm is *mostly structural, not a classifier failure*.** The blank rows on the Mizrahi debit are merchant-less wrappers (Cal settlements, ATM, cheque, other cards) that correctly return UNKNOWN — there is no merchant to categorize. Proof: **Cal's own scrape categorizes its 102 rows at ~90%** (the full tab now reads 48 rules + 74 LLM), because the card carries per-merchant descriptions. So the fix is **more sources** (hook up the remaining cards — M6.5), **Shanee's vocab migration** (firms the provisional vocab for the categorizable rows), and a **one-time re-categorize backfill** of the historical blank rows — **built 2026-06-26** (`automation/finance_recategorize.py`: re-runs the engine over blank rows, surgical write-back, idempotent, blank-rows-only; `finance_ingest` only categorizes *new* rows, so this is the deliberate seam for the backlog to re-enter the engine). Paired with a read-only **coverage** surface (`automation/finance_coverage.py` + `lib/finance_coverage.py`) — the report-first milestone metric (categorized vs excluded-mirror vs blank, by account). Both hermetic + tested (486 green); **box-run pending**. This trio is the substance of the gated 06-26 accuracy work; the `Finance-Budget` total is understated only by the genuinely-uncategorizable cash/cheque/other-card spend until those cards are added.
- ✅ **M6.5 — cards lane (Cal + Shanee debit live; backfill ran 2026-06-28; further statement cards are incremental, non-blocking adds).** **Cal (Visa) is live** — hooked up via a one-time headed `--auth` device-trust login (xvfb + x11vnc over an SSH tunnel; `FINANCE.md §4`), now scraping **headless** daily (first import 103 txns, ~90% categorized). Cal is *immediate-debit*, so each purchase already lands merchant-less on the Mizrahi statement; the Cal scrape is what supplies the per-merchant detail. The Mizrahi-side Cal settlement lines map to an excluded **`Card Settlement`** bucket — a rules entry (`כא"ל`/`ויזה כאל` tokens; ASCII-quote `U+0022` verified against live data, no over-match incl. Shanee's `כרטיס דביט` and the `כארם` restaurant) + a test seam (`test_card_settlement_excludes_cal_mirror`, plus the vocab-test `excluded` set + inverse guard so a future budget migration can't make it a budget row; 422 green) — so each Cal purchase counts **once**, via the Cal side, never the mirror. **Verified no double-count empirically** (both Money consumers read the by-category `Finance-Budget` actuals; the mirror lines stay out of the SUMIFS). **Open:** **(a) Shanee's debit card — mirror token landed 2026-06-23 (this session).** It turns out to be a Cal-cleared *immediate-debit* card on the **already-connected Cal login**, so it needed **no new `--auth`** — *correcting the morning's "each remaining card needs its own auth" assumption*. The only repo change is the `רכישה בכרטיס דביט` → `Card Settlement` mirror token (its per-merchant detail rides the existing Cal scrape), plus **flipping the 06-23-morning over-match guard** (`test_card_settlement_excludes_cal_mirror`: `רכישה בכרטיס דביט` was asserted *not*-excluded when her card wasn't yet scraped; now asserted excluded — a `דמי כרטיס דביט` fee-line guard (tightened 2026-06-25 to assert `== Fees`) so the full `רכישה ב…` phrase can't catch a card fee). **Over-match fix (2026-06-25):** the whole `Card Settlement` exclusion block was moved *below* every merchant rule (a last-resort fallback), plus merchant-suffix contract assertions and a `test_excluded_bucket_never_shadows_a_merchant` ordering-invariant test; 423 green. **Box-verify pending (de-risked, not blocking):** (i) confirm her per-merchant rows actually ride the existing Cal scrape — the mirror only reclassifies the Mizrahi line blank→excluded (budget total unchanged either way), so the "count once" correctness completes when her Cal rows are confirmed flowing; if they're on a *separate* Cal login, add a second `cal`-keyed provider + creds + `--auth`. (ii) **RESOLVED 2026-06-25 (structural):** the exclusion block now sits *below* the merchant rules, so a merchant-suffixed settlement line categorizes by its merchant and only genuinely merchant-less wrappers fall through — the 06-23-flagged latent over-match is closed independent of the live feed (the invariant test pins it). The other statement cards still need each source confirmed before a mirror (`ויזה-דביט`; `חיוב ויזה כאל עתידי` is already caught by the `ויזה כאל` token). **(b)** the historical **backfill** to move the existing 66 Cal mirror rows to `Card Settlement` (the rule is forward-only — it tags new rows at ingest; correctness already holds since blanks are excluded, but the yield metric + ledger clarity want it). **Tool built 2026-06-26** (`finance_recategorize.py`, hermetic + tested; the Cal-mirror lines reclassify via the existing rule in one pass) — box-run pending.
- ⬜ **Parallel (Shanee).** Budget migration — her manual budget → `Finance-Budget`; gives the actuals a target and defines the category vocab the rules engine maps to.

## Gated — summarizer review (opens ~2026-06-20, needs ≥1 week live)

- ✅ **First real classifier-accuracy run (2026-06-28) — clean pass:** 503 classified over the 7-day window, **0 ALERT-tier FP** (0 critical, 0 needs-a-look) vs the **< 1/week** bar (SPEC §7.3); no over-firing pattern to narrow.
- 🔵 **External milestone review on the live system** — folds in the property lane's review too. Runs (`review.py` DeepSeek) on **this close's diff** (OBSIDIAN rule + the M6-close canon) in the PO terminal block; resolve Apply/Defend/Open before the commit.

## v1.1 candidates — now sequenced & contracted in `ROADMAP.md`

The pool below was **ranked, phased, and given forward contracts** in `ROADMAP.md` (the 2026-06-20 spec-ahead pass). Status still lives here; the **plan + contracts** live there. In brief:

- **Now → ~06-26 (hardening):** CI gate (+ PII-leak guard + `config.js` smoke) · GAP-7 fail-loud fix · ~~Lane C dashboard write-contract (col-D format + header guard)~~ **✅ shipped 06-26** (col-D stays a real date cell; both surfaces write the ISO literal; `parseDate` reads ISO + he-IL DD/MM·DD.MM; JS write surface header-guarded → SPEC §6.1/§7.6/§8.5; unblocks V3.3) · uptime-ping · box-side verification · stale-digest→briefing line · JSONL rotation · Lane E batch.
- **After 06-26:** M6.3/M6.4 acceptance (classifier-accuracy run + budget-vocab migration + external review) · classifier-fp-metric · bridge scope-guard harness *(hard prereq to reply-parsing)*.
- **Later v1.1 (post the 30-day hold, each a PO call):** reply-parsing (needs a budget-exempt `ack` kind) · inbox-trigger · apify-cap · calendar-connectors (decomposed — Hebrew-string pass pullable early).
- **Frozen (joint / Shanee call):** big-charge-alert (brushes the **killed** anomaly lane) · ai-briefing (whole-Sheet→provider privacy expansion) · GCal/iCloud auto-ingest (credential-storage amendment).
- **✅ v3 Today redesign — CLOSED 2026-06-26 (V3.9).** The dashboard Today surface got a cool retone + new IA + two net-new components (parent-to-parent love-note, cross-domain timeline). 8 design calls co-signed (Adar + Shanee) after an 8-dimension adversarial review; decision record + design tokens in `V3_RECONCILE.md`, lane contract + V3.1–V3.9 build sequence in `ROADMAP.md` §3.8, file-level build plan in `V3_BUILD_PLAN.md`. **All 4 build blockers resolved 2026-06-25** — window: **build the whole lane now**; col-D → **ISO `YYYY-MM-DD`**; days 3–7 calendar → **coming-up strip carries events**; love-note exposure → **Cloudflare Tunnel**. **✅ V3.1 token retone landed 2026-06-25** (cool palette + IBM Plex Mono all-numerals + AA-cleared amber/muted; rename-with-aliases so no selector breaks; semantic washes wired to tokens via `color-mix`; DESIGN §2 Color/Type graduated + smoke #9 added; 423 tests green) — **code-complete, deploy-gated by the Pages publish** (committed ≠ deployed). **✅ V3.2 scaffold + 3-tier pill landed 2026-06-25** (`#view-today` rebuilt into named slots love-note/calendar/desk/coming-up/portfolios with the legacy renderers kept green inside; single 3-tier status pill — red/amber/sage + mono count + a neutral `loading` tier — replacing the old pill **and** the banner: `role=status`/`aria-live`, never color-only, and it closes the old green-`banner clear`-on-load premature-"all clear"; shared `computeCounts()` ready for V3.3's desk; a `source==='shabbat'` parseAll seam for V3.4; DESIGN §2/§3/§4/§9 graduated; a new `node --check app.js` CI guard; 7-lens adversarial review → 2 real findings fixed (Shabbat seam was over-tagging the whole Hebcal feed; a stale §4 banner reference); **429 tests green**) — **code-complete, deploy-gated by the Pages publish**. **✅ V3.4 3-day scroll-snap calendar landed 2026-06-25** (`#today-cal-strip` — an x-snap strip of exactly 3 panes today/+1/+2, read-only, reusing `.cal-event` rows; the V3.2 `source==='shabbat'` seam → 🕯 glyph + non-color inline-start border; `renderNext7`'s calendar-event window narrowed to **3–7d** so the strip and the Next-7 list can't double-render +1/+2; mock fixture gains a Fri candle-lighting row so DEMO exercises the Shabbat tag; DESIGN §2/§3/§9 graduated; 7-lens adversarial review → **5 fixed** (2 majors: shadow-clip from forced `overflow-y`, the +1/+2 overlap; 1 minor: aria-hidden the 🕯; 2 nits: hardened the time-sort vs un-padded hours, deleted the orphaned `empty.noEventsToday`); **429 tests green**) — **code-complete, deploy-gated by the Pages publish**. **✅ V3.5 portfolios + one data-driven bottom-sheet landed 2026-06-25** (the 6 domain accordions → a grid of 5 `<button>` tiles — Money hero (overall-% donut + category bar + 7-day sparkline), Health (initials-avatars, non-color urgency), Goals (% bar; bright-line moved into the sheet, D8), Car, Contracts — that open **one** shared, data-driven `role=dialog`/`aria-modal` bottom-sheet (focus-trap + scroll-lock + `#app` `inert` + focus-return-to-tile + Esc/scrim/close + reduced-motion); `renderKpi`/`renderSparkline`/`renderGoalLine`/`isSpendTxn` kept + reused; **PO calls 2026-06-25**: Education drops from Today (data retained → V3.6 timeline), 5 tiles now (Timeline tile lands in V3.6), Money donut = overall %; DESIGN §2/§3/§9 graduated; 7-lens adversarial review → **8 fixed** (4 majors: focus-return detached-on-reload, Car warn was color-only, `.sheet-body` couldn't scroll [flex `min-block-size`], + the dup focus-return; 4 minors/nit: `#app` not inert, `-Xd` overdue copy, scroll-reset on reload, the hero amount's bidi-isolation, reduced-motion on tiles); **429 tests green**) — **code-complete, deploy-gated by the Pages publish**. **✅ V3.6 cross-domain timeline landed 2026-06-25** (a 6th portfolio tile [2nd, after the Money hero] opens the shared bottom-sheet onto a **read-only chronology** — every dated row across all domains flattened onto one vertical, date-sorted axis with a now-marker, an exponential **1wk→5yr** zoom [default 3mo], and a category-chip filter [`finance · health · car · education · goals · contracts · calendar · other`]; zoom/filter swap **only** the track + `aria-pressed`, keeping the pressed control's focus; non-color urgency [glyph + due phrase]; **the two PO calls were ratified 2026-06-25** [Adar + Shanee onboard] — the *everything-dated* inclusion rule + the full Domain→category map, with **Education's only Today home = this timeline** — both **graduated to SPEC §7.6**; DESIGN §2/§3/§9-item-13 graduated; a new hermetic **STRINGS he↔en parity test**; 7-lens adversarial review → **6 confirmed fixed** [dark-mode pressed-chip AA via a new theme-paired `--on-accent` token; reset-to-3mo-default on each open; `meta` now rendered for cross-domain disambiguation; the `Archived`-status canon mismatch reconciled to the §6.1 enum; + focus-restore-on-bg-reload, the sticky-controls seam, and the tile `≤14` boundary]; **430 tests green**) — **code-complete, deploy-gated by the Pages publish**. **✅ V3.7 love-notes (text phase) landed 2026-06-25** (the first dashboard datum that is **neither the Sheet nor the outbox**, a sanctioned §3.1 exception: a net-new appliance endpoint `automation/love_note_server.py` — stdlib `ThreadingHTTPServer` on localhost, `GET/PUT/DELETE/OPTIONS /lovenote`, **one ephemeral note per direction**, **24h-or-on-replacement** [lazy read-expiry + an hourly `sweep_love_notes.py`], **flat-JSON-per-direction** storage [the ratified storage-shape call], **access_token→Google-tokeninfo** verify (opt-in **audience check** vs the dashboard's OAuth client when `FAMILY_INC_LOVENOTE_AUD` set — closes the confused-deputy gap; a refinement of the ratified userinfo call surfaced by the review) → `Settings.UserMap`→parent [unknown→403], token **never persisted/logged** [a short SHA-256-keyed in-memory verify cache, never the raw token], **tight CORS** to the Pages origin [blank origin → feature self-disables fail-safe], request-body cap [413] + chunked-reject pre-auth; **3 systemd units** [+ `TasksMax`/`CPUQuota`] + a **Cloudflare-Tunnel** connector unit; the **4th `pages.yml` sed** + `DASHBOARD_LOVENOTE_URL` secret + **4th `config-smoke` anchor**; the dashboard slot [inbound 💌 card hidden-when-empty + composer, no push, **no 'seen' signal**, parent-only gate, draft-preserving re-render] + he↔en STRINGS + `mock_data.json` fixture; **29 new security/behaviour tests** [no-outbox-import · no-Sheet-write · token-never-persisted · CORS allowlist · unknown-email 403 · dual expiry · one-per-direction · audience-reject · non-object-JSON guards]; **SPEC §7.7** [+ §3.1 exception, §4 voice-frozen note, §8.6 privacy bullet] + **ENGINEERING §5/§6** [units + the box's first inbound listener + the 2nd sudoers/restart line] + **DESIGN §3/§9-item-14** graduated; a **3-lens adversarial review** [security/correctness/contract, each finding verified] → **11 confirmed fixed**; **459 tests green**) — **code-complete, deploy-gated** on the PO standing up the Cloudflare Tunnel + the `DASHBOARD_LOVENOTE_URL` secret (committed ≠ deployed; the feature stays inert until both land). **✅ V3.3 desk + coming-up + absolute snooze landed 2026-06-26** (the Lane-C-gated straggler, now unblocked): `renderToday`→a **select-to-act desk** — `deskRow` checkbox-semantics rows (`role=checkbox`, click + Space/Enter, non-color selection = a ✓ box + `--soft` wash + `aria-checked`), `attachRowHandlers` rewired from the `.expanded`/`.snoozing` accordion to selection, a sticky batch bar fanning `state.deskSelection` out to **one** `applyWrites` per action (the recurrence bump multiplied per row); **absolute snooze** — `handleBatchSnooze` writes `Due = <absolute ISO>` (5 chips today+1/3/7/14/30 **+ a `min=today` date picker**), retiring the relative `+Nd` pills, so an overdue row snoozed forward clears OVERDUE (the D4 fix); `renderNext7`→**`renderComingUp`** — a read-only **±30-day** horizontal scroll band with a now-marker (past = calendar events only [overdue stays on the desk — PO call]; future = WEEK/MONTH-OUT reminders + events; today/+1/+2 owned by the 3-day strip; opens positioned at "now", RTL-aware `scrollBy`). The old `handleDone`/`handleSnooze`/`handleAddNote` + `renderReminderRow` deleted; `applyWrites`/`enqueueWrites`/`flushQueue` + the col-O tombstone + `flagFor`/`flagEmoji` kept unchanged. **6 PO calls settled** (5 snooze chips + a date picker · ±30 scroll band · read-only chips · past-events-only back-scroll · inline note composer · — vs the earlier ambiguity). New STRINGS he+en (`snooze.*`/`desk.*`, namespace agreed once with V3.8); SPEC §6.1 write contract + DESIGN §2/§3/§5/§9-items-16–18 graduated; demo fixture enriched (a fire-today row + a month-out reminder + a future event so DEMO exercises the desk + the band's future side). **7-lens adversarial review** (correctness · Lane-C write-contract · a11y · RTL/i18n · CSS · XSS · canon-conformance — each finding refute-verified) → **9 confirmed, all fixed** (note-textarea aria-label · 44px snooze tap-targets · focusable coming-up region · focus-return after a batch · flag-emoji aria-hidden in the checkbox name · live-region selection count · Hebrew `נבחרו: {n}` number-agreement · re-arm the date picker so a repeat pick fires · past-date snooze guard) and **2 correctness claims correctly rejected** (the offline-queue cap still holds — not the B8 bug; the drop-then-mutate is pre-existing single-row behaviour a reload corrects); **460 tests green** (the interactive JS stays `node --check` + STRINGS-parity + manual-smoke covered — `app.js` ~2150 lines now crosses the ~2000-line **JS-harness trigger**: raise a harness lane in V3.8/V3.9). **— code-complete, deploy-gated by the Pages publish** (committed ≠ deployed). **Voice is a frozen phase-2** — SPEC §4/§7.7 stored-media carve-out, **not built**. **✅ V3.8 i18n + a11y + Settings landed 2026-06-26** (the closer over all surfaces): a declarative **`data-i18n-aria` walker** retiring the hand-rolled boot aria-labels; a **global `:focus-visible`** + **one consolidated `prefers-reduced-motion`** block (transitions + `:active` scale + scroll, replacing 3 scattered blocks); a hermetic **WCAG-AA contrast test** (`tests/test_dashboard_a11y_contrast.py` — pins `--muted`/`--amber`/`--on-accent`/`--blue` both themes); a **real switch-account** Google re-auth (`prompt:'select_account'`, identity = the live OAuth session never a label flip, D3) that **does not revoke** the prior token (revoke drops the shared grant → would sign you out on a same-account re-pick + force the other parent to re-consent); **D7** confirmed (no notif/bank/export markup ever built); the **token-alias endgame** (the 6 V3.1 back-compat aliases migrated + deleted, zero-ref audit clean; `--blue` kept as a theme-paired info token + given its dark value); and **cheap pure-function JS tests** (`parseDate`/`fmtISO`/`flagFor`/`bumpDate` via plain node, no npm/build step). **7-lens adversarial review → 9 confirmed/all fixed, 0 refuted** (the same-account-revoke major dissolved by dropping the revoke; + cancel-dangling state, a redundant focus ring, a missing dark-`--amber` assert, a TZ-fragile round-trip). SPEC §7.6 + DESIGN §2/§3/§8/§9 graduated; **468 tests green** — code-complete, **deploy-gated by the Pages publish**. **✅ V3.9 milestone close landed 2026-06-26** — the external `review.py` DeepSeek gate (`reviews/review_milestone_2026-06-26_20-47.md`: 1 Apply [SPEC §7.7 replacement-semantics], rest Defend/Open, 0 blockers; affirmed the §3.1 exception, the no-revoke switch-account, the ISO write contract, the batch→single-`applyWrites` fan-out) + an internal **9-area canon-vs-code conformance audit** (all conformant; 3 nit doc catch-ups Applied: SPEC §7.6 blank-title exclusion · DESIGN §4 quiet-day copy · the `userinfo`→`tokeninfo` comment) — full resolution `reviews/review_milestone_2026-06-26_resolution.md`. **Lane closed.** The whole lane stays **deploy-gated by the Pages publish** (V3.7 love-notes additionally tunnel-gated; voice frozen phase-2). Review follow-ups deferred (see Deferred).

See `ROADMAP.md` §2 for the ranked sequence and §3 for each lane's contract, acceptance bar, and open PO calls. **Killed stays killed:** anomaly/subscription detection.

## Frozen lanes 🧊

*Frozen = the script lives in `attic/`, unmaintained. Unfreeze = the stated condition holds AND v1 has been stable for 30 days.*

| Lane | Unfreeze condition |
|---|---|
| Pediatric milestones | the Health tab is actively maintained |
| Goal coaching | the Goals tab is updated weekly for a month (proves the habit) |
| PDF→event, receipt OCR, voice capture, Gmail bill parser, Maccabi forwarders | per-item PO request, one at a time |

**Killed** (not frozen — gone from the board): anomaly / subscription detection. A keyword categorizer, also once killed, returns only in bounded form as the on-box finance rules engine (M6.4).

=== End: BACKLOG.md ===

=== File: ENGINEERING.md ===
# Family Inc. — Engineering Handbook

*How the system is built, tested, deployed, and operated. v2.0 · 2026-06-17.*
*Contracts live in `SPEC.md`; this is the "how". If they disagree, `SPEC.md` wins and the disagreement is a bug.*

---

## 1. Repo layout

```
family-inc/
├── CLAUDE.md            # session context for Claude (thin; points here)
├── SPEC.md  ENGINEERING.md  DESIGN.md  BACKLOG.md
├── automation/
│   ├── lib/
│   │   ├── config.py    # env + constants; ALL non-secret constants live here
│   │   ├── sheet.py     # the only gspread client (retry, tab accessors, upsert)
│   │   ├── outbox.py    # the only path to a human (budget ledger, dedup, kinds)
│   │   ├── llm.py       # the only LLM wrapper (provider registry, cost log)
│   │   ├── apify.py     # the only Apify client (property secondary source)
│   │   ├── mailer.py    # the only smtplib import (email fallback)
│   │   ├── categorize.py       # on-box finance rules engine (M6.4)
│   │   ├── finance_budget.py   # budget-SUMIFS formula source of truth
│   │   ├── dates.py     # to_date / to_datetime / fmt_date — one implementation
│   │   └── money.py     # ILS formatting — one implementation
│   ├── reminders_engine.py
│   ├── daily_digest.py           # assembles ONE morning message, sends
│   ├── weekly_briefing.py        # Saturday narrative (template) + accuracy section
│   ├── whatsapp_summarizer.py
│   ├── accuracy_review.py        # weekly classifier accuracy pass
│   ├── property_scrape.py
│   ├── finance/scrape.js         # bank/card scraper (Node) → CSV
│   ├── finance_ingest.py         # CSV → lib/sheet
│   ├── finance_budget_formulas.py # live budget-SUMIFS installer
│   ├── templates.py              # message copy (reviewable against DESIGN.md)
│   ├── reply_handler.py          # parked, v1.1 (reply parsing)
│   ├── import_reminders.py       # one-shot M3 Reminders seeder
│   ├── hebcal_client.py
│   ├── review.py                 # milestone review tool
│   ├── session_kickoff.py        # regenerates NEXT_SESSION_PROMPT.md at session end
│   └── bridge/                   # Baileys listener + sender (Node)
│       ├── baileys_listener.js  package.json
│       └── state/               # gitignored: auth_state/, inbox/, outbox/, ledgers
├── dashboard/            # vanilla PWA (GitHub Pages serves this directory)
│   ├── index.html  app.js  styles.css  sw.js  manifest.webmanifest
│   ├── config.example.js         # committed; real config.js is gitignored
│   └── mock_data.json
├── deploy/
│   ├── systemd/          # *.service + *.timer units (source of truth for schedules)
│   ├── provision.sh      # idempotent VPS setup
│   ├── deploy.sh         # pull + test + restart (the only way code reaches the box)
│   ├── backup.sh         # tar bridge/state + logs → Drive via rclone
│   └── publish.sh        # public-repo history-rewrite kit
├── tests/                # pytest; fixtures/ holds golden files
├── reviews/              # milestone-review audit trail (tracked)
├── seeds/                # CSV seeds — personal values gitignored, README committed
├── Setup/                # live runbooks only (VPS, bridge pairing, OAuth, ICS)
├── Archive/              # superseded docs + the dated decision history — read-only
├── attic/                # frozen scripts — unmaintained, excluded from tests
└── logs/ Briefings/      # runtime output (gitignored except .gitkeep)
```

Boundary rules (convention, reviewer-checked — no CI enforces them yet): scripts never define a utility that belongs in `lib/` (no redefining `to_date`/`fmt_money`). Each external-site touch is the sole, named function in its own module — the bridge listener, finance `scrape.js`, `property_scrape.py`, `lib/apify.py`, and `hebcal_client.py` — never scattered ad-hoc. Nothing outside `lib/sheet.py` constructs a gspread client. Nothing outside `lib/llm.py` imports an LLM SDK. Nothing outside `lib/outbox.py` reaches a human.

## 2. Toolchain

| Layer | Choice | Notes |
|---|---|---|
| Python | 3.12 + **uv** | `uv sync --frozen` on the box; lockfile committed; appliance path is `uv run --frozen` |
| Key deps | gspread, google-auth, anthropic, pytest, requests | additions need a one-line justification in the commit body |
| Node | 22 LTS, plain npm | bridge + finance scraper only; `npm ci --omit=dev`; lockfiles committed. The `engines` floors are the real minimums (bridge ≥20.11, finance ≥22.13); `provision.sh` installs 22 LTS |
| Browser | per-lane Chromium | **Playwright Chromium** (property; ephemeral `uv run --with playwright`, headed under `xvfb-run`) + **Puppeteer Chromium** bundled by `israeli-bank-scrapers` (finance; daily headless). The one-time `--auth` device-trust login is headed under xvfb+x11vnc, persisting a per-provider profile under `/var/lib/family-inc/finance/profiles/`, mode 700 — but **x11vnc is NOT installed by `provision.sh`** (it installs xvfb+xauth only); the operator adds x11vnc when first using `--auth`. Low urgency while cards are deferred. No chromium apt package is installed; each lane pulls its own browser, kept out of the uv lockfile |
| Scheduling | **systemd timers** | journald logs, `OnFailure=` hooks, `Persistent=true` catches missed runs after reboots |
| Dashboard hosting | GitHub Pages via Actions serving `main:/dashboard` | static, zero backend; the workflow generates the gitignored `config.js` from Actions secrets |
| Secrets | `/etc/family-inc/` mode 600 | `service-account.json`, `env` (DeepSeek/Anthropic keys, SMTP, Apify token), `recipients.json`, `property_searches.json`, `bank_creds.json` |

## 3. Configuration

- `automation/lib/config.py` loads secrets from `/etc/family-inc/env`. **All non-secret constants — alert-budget cap, tombstone window, quiet hours, digest size, lead/recurrence thresholds, inbox retention, model ids — are defined directly in `config.py`.** There is no `config.toml`.
- **No constant may be defined in a script.** This rule exists because the alert-budget cap was once defined twice with independent ledgers — exactly the class of bug it prevents.
- Dashboard config: `config.example.js` committed with placeholders; real `config.js` (Sheet ID, OAuth client id) gitignored and generated at deploy.

## 4. Coding standards

- Python: type hints on public functions; dataclasses for Sheet rows; no bare `except:` — catch narrowly, log with context, and **decide**: degrade (LLM paths) or surface (data paths). Silent swallowing is the bug class that once hid the mock/real boundary for two weeks.
- Every script is also a library: `main()` guarded, pure logic importable for tests.
- Logging: stdlib `logging` to stderr (journald captures); one structured CSV per domain in `logs/` for the self-reporting briefing lines.
- JS (dashboard): single-file vanilla discipline; state lives in the one `state` object; every Sheet write goes through `applyWrites()` and conforms to the SPEC §6.1 write contract.
- Hebrew in code: string literals fine, identifiers English. Message copy lives in template constants (`templates.py`), not inline f-strings, so `DESIGN.md` can review it.

## 5. The appliance (VPS)

`deploy/provision.sh` is idempotent and run as root once:

1. Create user `familyinc` (no sudo); `timedatectl set-timezone Asia/Jerusalem`.
2. Install uv + Node 22; clone the repo to `/opt/family-inc`; `uv sync --frozen`; `npm ci --omit=dev` in `bridge/` and `finance/`; install xvfb+xauth (the Playwright browser and Puppeteer's Chromium are pulled per-lane, not by an apt package).
3. Copy `deploy/systemd/*` → `/etc/systemd/system/`; `systemctl enable --now` the bridge service + all timers + the love-note + tunnel services (V3.7; install `cloudflared` and place `CLOUDFLARED_TUNNEL_TOKEN` first).
4. Place secrets in `/etc/family-inc/` by hand (never scripted, never copied off the box).
5. Pair Baileys: `systemctl stop family-bridge && node bridge/baileys_listener.js` once, scan the QR, restart. `bridge/state/auth_state/` is in the weekly backup — **after a VPS rebuild, restore it before re-pairing**; a fresh QR scan is the fallback, not the default. (A Baileys *major*-version bump is the one case that requires wiping `auth_state/` and re-pairing.)

Units (schedules are code — change them via PR, not on the box):

| Unit | Schedule | Runs |
|---|---|---|
| `family-bridge.service` | always-on, `Restart=on-failure` | Baileys listener + outbox sender |
| `family-finance.timer` | ~06:00 daily | bank scrape → ingest (live on Mizrahi/debit since 2026-06-19; cards Max/Cal deferred) |
| `family-property.timer` | 07:10 + 19:10 | property scrape → Sheet + digest section |
| `family-reminders.timer` | 07:25 daily | reminders engine (computes, doesn't send) |
| `family-digest.timer` | 07:30 daily | daily digest assembly → outbox |
| `family-summarizer.timer` | hourly, 24h | classifier — runs at night so **criticals** can fire any hour; ordinary alerts are still held 22:00–07:00 by the outbox |
| `family-weekly.timer` | Sat 21:00 | weekly briefing + classifier-accuracy section |
| `family-backup.timer` | Sun 03:00 | tar `bridge/state` + `logs/` → Drive via rclone |
| `family-lovenote.service` | always-on, `Restart=on-failure` | love-note endpoint (V3.7, SPEC §7.7) — localhost HTTP, fronted by the tunnel |
| `family-lovenote-tunnel.service` | always-on, `Restart=on-failure` | Cloudflare Tunnel → the love-note endpoint (token-managed; ingress set in the Cloudflare dashboard) |
| `family-lovenote-sweep.timer` | hourly | expire love-notes past 24h (belt-and-suspenders behind the server's lazy read-expiry) |

All timers: `Persistent=true`; `OnFailure=family-fail-flag@%n.service` appends the failing unit to `logs/fail.flag`. The next **delivered** digest reports it (a Hebrew line prepended) and clears the file; a flag still present on Saturday means digests aren't landing, and the weekly briefing says so.

**The love-note endpoint is the box's FIRST inbound HTTP listener** (everything else is an outbound timer/sender). It binds `127.0.0.1:8787` only; the Cloudflare Tunnel is the sole public path, so there is no port-forward and no home-IP exposure. It reads `Settings.UserMap` (the live Sheet, service account) and needs `FAMILY_INC_LOVENOTE_ORIGIN` (the Pages origin, for CORS) + `CLOUDFLARED_TUNNEL_TOKEN` in `/etc/family-inc/env`; a blank origin keeps the feature inert. Unlike the timers, the server is long-running — a deploy that changes its code needs an explicit `systemctl restart family-lovenote` (add it to the `familyinc` sudoers whitelist alongside `family-bridge`), since no timer picks it up.

## 6. Deployment

`deploy/deploy.sh` on the box:

```
git pull --ff-only
uv sync --frozen && (cd automation/bridge && npm ci --omit=dev) && (cd automation/finance && npm ci --omit=dev)
FAMILY_INC_SHEET_ID= uv run --frozen pytest -q   # red tests abort the deploy; running code is untouched
sudo /usr/bin/systemctl restart family-bridge    # whitelisted sudoers line
# family-lovenote restarted too when installed (guarded; long-running, not a timer)
```

Timers pick up new code automatically on the next fire (they exec scripts from the repo); the two **long-running** services — `family-bridge` and `family-lovenote` (V3.7) — are the exception and `deploy.sh` restarts both (the love-note restart is guarded, so it no-ops until the unit is installed). **Committed is not deployed** — a placed secret or a merged feature is inert until `deploy.sh` pulls it; confirm the box is at origin HEAD before declaring anything live. The `familyinc` user has exactly two sudo capabilities (restart `family-bridge` / `family-lovenote`, both restart-only), so a compromised script can't escalate.

**Pre-merge CI:** `.github/workflows/tests.yml` runs the hermetic pytest suite — including the seed-safety guard, the repo-wide PII-leak guard (`tests/test_repo_pii_guard.py` + the shared patterns in `lib/pii.py`), and the dashboard `config.js` smoke — on every push + PR to `main`, so a red commit can't merge. It gates **merge**, not the box: `deploy.sh` still runs the same suite on the appliance as the safety net before restarting the bridge (no `deploy.sh` change — the guards are plain pytest, so they ride the existing run). The job has no path filter (the PII guard scans the whole tree, so a leaked value in docs or config trips it too) and installs Node 22 so the `@requires_node` syntax-check tests run rather than skip.

Dashboard deploys are `git push` (Pages rebuilds in ~30s); the PWA on both phones picks up on next open. `sw.js` cache-busts on a version bump in `config.example.js`, mirrored into `config.js`.

## 7. Testing policy

These suites exist and stay green:

| Suite | Covers |
|---|---|
| `test_engine.py` | fire-reason matrix (overdue/lead/due-today), tombstone skip window incl. future-skew, recurrence bumps incl. Feb-29 clamp + Custom flagging, send-success stamping, Last-Sent rerun idempotency |
| `test_outbox.py` | budget ledger: 2-cap, critical bypass, briefing exemption, shared-ledger across senders, (id,target) dedup, quiet-hours hold |
| `test_summarizer.py` | the 5 hard rules, per-group routing incl. `none`→NEEDS-A-LOOK, keyword fallback without a key, dispatch through the outbox, Sheet-tab persistence + rerun dedup, JSON-parse tolerance |
| `test_render_golden.py` | weekly briefing + daily digest rendered against `tests/fixtures/*.md` golden files (byte-exact; update goldens deliberately) |
| `test_sheet.py` | row-parsing tolerance, schema-drift guard both directions + flag heal, batched write path incl. formula survival, Settings/UserMap, upsert |
| `test_property.py` | card parse/normalize, BlockedError, empty result, seen-diff, Sheet-dedup, digest section, junk rejection |
| `test_apify.py` | adapter field maps, backup vs gap-fill, primary-wins merge, per-search/per-kind cost gate, fail-loud-only-on-zero-usable, token-inert |
| `test_finance.py` | mock CSV → ingest → mock Sheet, Txn-ID dedup/idempotency, fail-loud on missing creds, account upsert preserving human fields, column-order pin |

**Tests are hermetic.** An autouse fixture blanks `FAMILY_INC_SHEET_ID`, the LLM keys, and the SMTP creds, so the appliance's `deploy.sh` pytest can never reach the live Sheet, a real model, or actually send email. LLM calls are never made in tests — `lib/llm.py` has a fake injected via env. The dashboard has a manual smoke checklist in `DESIGN.md` §9 (no JS harness — boring tech; revisit if `app.js` exceeds ~2,000 lines).

## 8. Observability

- journald per unit (`journalctl -u family-reminders`).
- `logs/reminders_log.csv`, `logs/llm_costs.csv`, `logs/outbox_ledger/`, `logs/delivery_log.csv` (transport per send-run: baileys | smtp | queued-stale). The classifier's per-message record lives on the `WhatsApp_Inbox` Sheet tab, not in `logs/`.
- Self-reporting: the weekly briefing carries one system line — "7/7 runs green · 41 messages classified · 2 tombstone skips (max age 1.4h) · ₪6.10 LLM spend". Any fail-flag, schema-drift, or stale heartbeat replaces it with a warning. The humans never check logs unless the briefing tells them to.
- External uptime ping (healthchecks.io free tier) is an accepted gap — a hard VPS-down is currently silent; listed v1.1.

**"No digest by 08:00" runbook** (the most likely 24h failure is a logged-out WhatsApp session on a healthy VPS):

1. Check email — if the digest arrived there, the bridge is down but the system is fine: SSH in, re-pair the QR (restore `auth_state/` first if post-rebuild).
2. No email either → the VPS is down: reboot from the provider console; `Persistent=true` timers fire the missed runs on boot.
3. Repeated same-week logouts → treat as a ban signal; invoke the `SPEC.md` §10 fallback decision.

## 9. Git & repo conventions

- `main` is deployable; small focused commits; imperative subjects; the body explains *why* when non-obvious.
- Sessions `git pull --ff-only` before any work (origin is the sync point between agents) and commit at session end (the leader pushes; Pages + `deploy.sh` consume `main`). Git operations run on the PO's machine, never in a sandbox.
- No long-lived branches — this is a two-committer repo (Adar + Claude-in-session).
- The Sheet schema only ever gains columns (additive, backwards-compatible); old rows without M/N/O are treated as never-tombstoned. Rollback at any point = `git revert` + redeploy.
- Tags: `v1-live` at acceptance, then `vX.Y` per milestone.

## 10. Review ritual

Reviews fire on **milestones**, not every session: a new spec, an architecture change, anything touching delivery/budget/privacy guarantees, and each milestone close. Mechanism: `automation/review.py` builds the prompt + attachment list; the reviewer is the best available external model (DeepSeek default; substitutions logged). A keyless local fallback is available via `--provider ollama` (₪0/run, on-box privacy). Findings are resolved in-session as Apply / Defend / Open, and any directional outcome is recorded. Tiny edits never trigger a review. On a milestone-closing session the gate runs **blocking inside the handoff chain** (`… && review gate && git commit && git push`) — a MAJOR finding stops the commit until resolved or explicitly overridden by the PO. A failed or truncated review never blocks a milestone: log it, proceed, note it in `BACKLOG.md`.

## 11. Definition of done (any work item)

Code merged with tests for its logic · constants in config · errors either degrade or surface (no silent paths) · contracts updated in `SPEC.md`/`DESIGN.md` if changed · `BACKLOG.md` status flipped · deployed and observed green once on the appliance.

=== End: ENGINEERING.md ===

=== File: DESIGN.md ===
# Family Inc. — Design Specification

*The product has two surfaces: WhatsApp messages and the dashboard PWA. Both are designed here. v3.1 · 2026-06-20. The single offline model is queue + tombstone everywhere.*

---

## 1. Design principles

1. **Calm tech.** The system reports what happened and what's next; it never scolds, streaks, paces, or counts what you missed. Quiet days are a success state, not an empty state.
2. **The message is the product.** Most days the family touches Family Inc. only through WhatsApp. Message copy gets the same design rigor as pixels.
3. **Dense, then disclosed.** Today shows every domain at a glance; detail hides behind one tap. Linear/Notion density, not wellness-app whitespace.
4. **Partner-symmetric surfaces.** Attribution without scoring: domain leads, names follow. No passive "recently completed" surface either — even a neutral one risks reading as a scoreboard between partners.
5. **Honest affordances.** Nothing on either surface suggests an action the system can't take (no reply commands until reply parsing ships; no disabled-looking-but-tappable buttons).
6. **Hebrew-first, RTL-first.** English is the fallback, not the default. LTR runs (numbers, URLs) wrapped in `<bdi>`.

## 2. Visual system (dashboard)

### Color — cool grey + blue *(v3 retone, shipped V3.1 2026-06-25; token names match `styles.css` canon)*

| Token | Light | Dark (provisional) | Use |
|---|---|---|---|
| `--bg` | `#EBEEF2` | `#14161B` | page |
| `--tile` | `#FFFFFF` | `#1C2027` | card / sheet surface |
| `--ink` | `#12151C` | `#E7E9ED` | text |
| `--muted` | `#5F6878` | `#A1AAB8` | secondary text (AA-cleared) |
| `--line` | `#E1E5EB` | `#2A2E36` | hairlines |
| `--accent` | `#2C57C8` | `#6E8BE8` | links, active tab — single brand color |
| `--green` | `#2F8559` | `#4CA877` | all-clear, success |
| `--amber` | `#8A5E12` | `#C79A4A` | due-today (darkened to clear AA) |
| `--red` | `#C4403B` | `#DB6B63` | overdue |
| `--blue` | `#4A6FA5` | `#82A9D9` | info — calendar event times (`.cal-time`) |

Semantic colors appear only on status; the accent is the single brand color. No gradients. Semantic washes are `color-mix` off these tokens so they track the palette. Dark mode is **provisional** (its own pass later). The V3.1 back-compat aliases (`--card`/`--border`/`--ink-dim`/`--orange`/`--yellow`/`--radius`) were **retired in V3.8** — every selector now uses the canonical token (a zero-ref audit confirmed none remained); `--blue` stays as a real info token, theme-paired in every block (V3.8 gave it its dark value). `--rad 20px` (cards/sheets), `--rad-sm 8px` (inputs), 999px pills; card shadow `0 1px 2px/0 8px 22px`, bottom-sheet `--sheet-shadow`.

### Type

- **Heebo** — Hebrew UI (default chrome).
- **Inter** — Latin UI (fallback chrome); tabular figures on.
- **IBM Plex Mono** — **all numerals** (money `₪4,280`, dates, counts, times, %) so figures read as data at a glance, via the `.num` utility + `<time>` (loose count/% spans get tagged as later slices render them).
- Scale: 17/15/13 body-secondary-caption; one display size (28) for drawer KPIs. No font weight above 600.

### Components

- **3-tier status pill** (Today view, sticky; *v3, V3.2 — replaced the old status banner + plain pill*): a single signal, always visible (clear is a resting state, never hidden). Tier by priority `overdue` (red) > `today` (amber) > `clear` (sage), rendered as a decorative glyph + a **mono count** + a **text label** (`{n}` `overdue` / `{n}` `due today` / `Nothing urgent` / `Sunday briefing ready` on Sundays) — never color-only: the count + label carry the meaning. A `loading` tier holds first paint so it never reads as a premature "all clear". One signal at a time — our budget-friendly stand-in for OS-level notifications.
- **3-day calendar strip** (Today view; *v3, V3.4*): a horizontal scroll-snap strip of exactly three day-panes (today/+1/+2), each a day-head (today/tomorrow/weekday + date) over its `Calendar-Events`. **Read-only** — a glance surface, no tap/write affordance; events are edited at their source. An empty day shows a short line so the strip never collapses (stable snap geometry). RTL "just works" off `dir=rtl` + logical props. Days 3–7 live in the coming-up strip, so this stays today+2 with no overlap. The 🕯 Shabbat line (the `source==='shabbat'` seam) carries a glyph + a non-color inline-start border, never hue alone.
- **Select-to-act desk** (Today; *v3, V3.3 — replaced the tap-to-expand reminder row*): the OVERDUE/FIRE-TODAY reminders as **checkbox** rows (flag dot · title · due phrase; keyboard-operable; selection is never color-only — a ✓ box + wash + `aria-checked`). Selecting ≥1 reveals a **sticky batch bar** (`✓ done` · `+ snooze` · `+ note`) that fans the whole selection out to **one** Sheet write. **Snooze is absolute**: chips (tomorrow · +3 · 1 week · 2 weeks · 1 month) + a date picker resolve to an absolute Due date (so an overdue row snoozed forward clears OVERDUE); the note is an inline composer appended to each selected row's Notes.
- **Coming-up strip** (Today; *v3, V3.3 — replaced "Next 7 days"*): a **read-only** ±30-day horizontal scroll band with a **now**-marker. Date-sorted: WEEK-OUT/MONTH-OUT reminders + calendar events; the past side carries past calendar events (overdue reminders stay on the desk), the future side what's coming. today/+1/+2 events stay in the 3-day calendar strip (no double-render). Opens positioned at "now"; scroll back for the past, forward for what's ahead.
- **Portfolio tiles + one bottom-sheet** (Today; *v3, V3.5 — replaced the accordions*): a grid of domain **tiles** (Money hero = an overall-% donut + category bar + 7-day sparkline · Timeline = count of upcoming milestones · Health = initials-avatars with non-color urgency · Goals = a % bar · Car · Contracts) — each a `<button>` that opens **one** shared, data-driven **bottom-sheet** (`role=dialog`/`aria-modal`; Esc / scrim / close dismiss; focus-trapped + scroll-locked; focus returns to the launching tile; reduced-motion honored). Never six panels. Status is never color-only (text + glyph). Education has **no** Today tile (its data folds into the Timeline). The **Timeline** tile (*v3, V3.6*) opens a read-only **cross-domain timeline** — every dated row across all domains flattened onto one vertical, date-sorted axis with a now-marker, an exponential 1wk→5yr zoom (default 3mo), and a category-chip filter (`finance · health · car · education · goals · contracts · calendar · other`); items are edited at their source tab, never here.
- **Bright-line goal viz**: target line + actual line + safety band (ahead/on-pace/behind) for multi-year goals — progress bars are banned for anything >90 days. The Goals **tile** shows a simple % bar; the bright-line lives in the Goals **bottom-sheet** (D8).
- **Stale-data badge**: shown only when a live load fails and a cache exists — `לא מקוון — נתונים מ-{when}`. There is no positive "live" indicator; the pending-write count lives in Settings → queue inspector.

## 3. Information architecture (Today-first)

```
Today (home)
├── Header: Family inc. · date
├── 3-tier status pill (sticky) — overdue (red) / today (amber) / clear (sage); loading tier on first paint
├── LOVE-NOTE (V3.7) — a parent-to-parent ephemeral note (💌): an inbound card (hidden when none) above a small composer (write/replace/clear); appliance-backed, NOT the Sheet; the whole slot is hidden unless configured + signed in
├── CALENDAR — a 3-day scroll-snap strip (today/+1/+2), read-only; 🕯 marks the Shabbat line
├── DESK (select-to-act) — reminders where Auto-flag ∈ {OVERDUE, FIRE TODAY}; multi-select → one batch (done / absolute-snooze / note)
├── COMING UP — a read-only ±30-day scroll band (now-marker): week/month-out reminders + calendar events (today/+1/+2 stay in the calendar strip); scroll back for past events
└── PORTFOLIOS — domain tiles (Money · Timeline · Health · Goals · Car · Contracts) → one shared bottom-sheet; the Timeline tile opens a read-only cross-domain chronology (1wk→5yr zoom + category filter); Education folds in here (no separate tile)
Sunday tab — a live week-ahead view computed from the Sheet (week ahead · reminders this week · overdue · Money · Goals · data hygiene), NOT the rendered weekly-briefing markdown
Settings tab — account (switch-account = a real Google re-auth · sign-out · force-refresh) · language toggle · theme · Sheet ID · demo toggle · queue inspector (pending-write count); no notification-toggle / bank-connect / export controls (D7)
```

Today-first wins the 8 AM glance; tiles demote to drawers; the Sunday week-ahead gets a tab, not the home.

## 4. States

- **Loading**: the status pill shows its neutral `loading` tier (`Loading…`) while the first `batchGet` is in flight — never a premature "all clear"; header/tabs are real from t=0; lists render once data arrives (cached snapshot first if present, then live). No skeleton or shimmer.
- **Quiet day**: the status pill shows the sage `clear` tier (`Nothing urgent`, or `Sunday briefing ready` on Sundays) and the desk renders its warm empty line ("Nothing on fire. ☕" / "שום דבר לא בוער. ☕"). The screen is never blank.
- **Offline**: a one-shot toast confirms each queued write; the stale-data badge shows if the view was served from cache; rows keep working and re-render optimistically (the pending-write count is in Settings). **Buttons never disable offline.**
- **Write failure (online)**: optimistic UI rolls back; inline "Couldn't save — retry?"; token expiry → silent refresh once, then a re-sign-in banner.
- **Back from vacation (30 overdue)**: top 10 by due date + "+20 more" expander; bulk-done multi-select via the V3.3 select-to-act desk, with zero commentary.

## 5. Interaction contract (write-back)

Every action maps to one batched Sheet write per SPEC §6.1 (intent columns + `DoneAt`/`LastDoneBy` on completion + `WriteQueue_Tombstone` always); the select-to-act desk (V3.3) fans a multi-row selection into a **single** batch:

| Action | Writes | UI |
|---|---|---|
| ✓ done | Status=Done, DoneAt, LastDoneBy, Tombstone (+ recurrence bump) | row clears from the desk |
| snooze | Due = an **absolute** date (today + offset, or a picked day), Status=Snoozed, Tombstone (no DoneAt — snooze isn't completion) | row leaves the desk once future (OVERDUE cleared) |
| note | append to Notes with `[date name]` prefix, Tombstone | inline confirm |

Offline: the same writes queue (`localStorage.pendingWrites[]`, cap 50 with a one-shot loss warning at the cap); flush in tap order on reconnect; idempotent via tombstone (re-stamped at flush time).

## 6. WhatsApp message design system

The most-used UI in the product. Rules:

- **One morning message.** Engine fires, group digest, new-property listings, and the Hebcal line are assembled into a single 07:30 message per recipient — never 2–3 separate sends.
- **Both adults, every day.** Each adult gets their own 07:30 message every day — partner-symmetric. An adult with no reminders of their own still receives the briefing: the quiet-day line `אין תזכורות להיום — יום שקט.` followed by whatever shared groups / property sections exist. A truly empty day is just the head + quiet-day line — never *no* message (silence must stay distinguishable from a broken digest) and never a scold (quiet is a success state).
- **Line economy.** One line per item: flag emoji · title · due phrase. Notes only if ≤120 chars. >5 items → top 5 by priority + "+N more — בלוח" (in the dashboard).
- **Emoji are semantics, not decoration**: 🔴 overdue · 🟠 today · 🟡 week-out · 🟢 month-out · ⚠ needs-a-look · 🕯 Shabbat line · 🏠 new listings. No other emoji in generated copy.
- **Budget-deferred carry-over.** Alerts the 2/day budget defers ride the *next* morning's digest under a `נשמרו מאתמול (מכסת הודעות):` section — surfaced, never dropped (copy pending Shanee review).
- **No reply affordances** until reply parsing ships. Messages end with content, not instructions. When v1.1 lands, the reply grammar returns as a single footer line.
- **Hebrew copy register**: short, warm, zero exclamation marks, no imperatives toward a person ("לקבוע תור" not "תקבעי תור!"). Dates as "יום ג׳ 17/6". Money as ₪ with a thousands separator.
- **Attribution**: domain first, name inline.

### Templates

Daily digest (the only routine alert-channel message):

```
🏠 Family inc. · יום ו׳ 12/6
🔴 טסט שנתי לרכב — באיחור 3 ימים
🟠 תור שיניים לילד — היום
🟡 ביטוח דירה — בעוד 6 ימים

קבוצות (24ש׳):
גן — מחר יום פרי, להביא 🍐 (גננת, 22:14)
ועד — מעלית מושבתת חמישי 09:00–12:00

🏠 דירות חדשות:
4 חד׳ · ₪2,450,000 · רמת גן

🕯 הדלקת נרות 19:24 · צאת שבת 20:35
```

Quiet day for this adult (no reminders of their own; shared sections still ride along):

```
🏠 Family inc. · יום ג׳ 17/6
אין תזכורות להיום — יום שקט.

קבוצות (24ש׳):
ועד — מעלית מושבתת חמישי 09:00–12:00
```

Critical (budget-bypassing, rare): a single line, no frame — `⚠ {group}: {one_liner} ({sender}, {time})`.

Weekly briefing (Sat 21:00): **deterministic flat sections** — week ahead · reminders firing this week · overdue · Money · Goals · data hygiene · system self-report · classifier accuracy — vertical, one line per item, the typography carrying the design. **Rendered from a deterministic template, no LLM call.** *(The "five-scene narrative" opener — the week's spend · a kids' moment · next week's three things · a goal line · a contract heads-up, Strava-year-in-review meets Morning Brew — is a deferred v1.1 LLM lane (`ROADMAP.md` §ai-briefing) with this template as its fallback, not the current output.)*

Bridge-health warning prepends, never replaces: `⚠ הגשר שקט 14 שעות — ייתכן שפספסנו הודעות`.

## 7. i18n rules

- `<html lang="he" dir="rtl">` default; `localStorage.familyinc.lang="en"` flips lang/dir + chrome strings (pre-paint, no flash).
- Logical CSS properties only (`padding-inline-start`); no left/right literals.
- Chrome strings in the parallel STRINGS table; data values (merchants, group names, guide links) render Hebrew regardless of the toggle.
- Dates `DD/MM`, week starts Sunday, `he-IL` number formatting in both languages (the audience is Israeli in either chrome).
- The brand stays Latin "Family inc." everywhere, including the home-screen title.
- WhatsApp messages are Hebrew-only (no toggle exists there; the recipients are known).

## 8. Accessibility & ergonomics

Tap targets ≥44px. Contrast clears **AA on both surfaces**, pinned by a hermetic test (`tests/test_dashboard_a11y_contrast.py`) over the deliberately-engineered tokens — `--muted`/`--amber` darkened to clear AA, `--on-accent` paired per theme, `--blue` given a dark value (V3.8) — so a future retone can't silently regress them ("assert, don't re-pick"). A **global `:focus-visible`** outline (`:where(a, button, input, select, textarea, [tabindex])`) covers every interactive element; a single **`prefers-reduced-motion`** block neutralizes transitions, the `:active` scale, and scroll animation. Icon-only / unlabelled controls are named in **both languages** declaratively via the `data-i18n-aria` walker (applied at boot from STRINGS). The PWA `apple-touch-icon` relies on the OS glass treatment, no fake translucency in-app; thumb-zone — action pills render below the row, not above.

## 9. Manual smoke checklist (per dashboard deploy)

1. Cold load <1s on phone over LTE; the `Loading…` pill gives way to live lists without layout shift.
2. Hebrew default renders RTL with no mirrored numerals; the toggle flips chrome only.
3. Mark done online → row clears, the Sheet shows M/N/O stamped.
4. Airplane mode → tap done → a queued toast shows → reconnect → flush; the engine log shows a tombstone skip if within the window.
5. The demo toggle never touches the live Sheet.
6. Lighthouse PWA installable; an offline reload serves the shell + cached data.
7. Offline, tap until the queue hits 50 → a one-shot "queue full" warning shows; further taps don't grow the queue; reconnect → flush re-arms the warning.
8. (bridge) A 1:1 message to the bridge number from a known sender is logged to `replies.jsonl` but gets **no reply/ack** (reply-parsing is v1.1, SPEC §7.4); an unknown 1:1 sender is dropped.
9. (V3.1 retone) Cold load shows the cool palette (`--bg #EBEEF2`, `--accent #2C57C8`) and IBM Plex Mono numerals with no Geist FOUC; amber/muted text clears AA on both surfaces; Sunday + Settings inherit the palette with no layout shift; the longest `₪` amount + the drawer KPI row don't wrap under the new mono metrics.
10. (V3.2 pill) The Today status pill shows exactly one tier by priority — red `overdue` + mono count when any overdue, else amber `due today` + count, else sage `Nothing urgent` (or `Sunday briefing ready` on Sundays); first paint shows the neutral `loading` tier (never a premature "all clear"); the tier reads from the count + label, not color alone; the pill is always visible (clear is a resting state) and resolves with no layout shift.
11. (V3.4 calendar) The calendar slot is a 3-day strip of exactly three panes (today/+1/+2) that horizontally **snaps** — verify the snap direction on **iOS** specifically, RTL: today is the right-most pane and snap advances right-to-left, the next pane peeking. Each pane has a day-head (today/tomorrow/weekday + mono date); an empty day shows a short line and does **not** collapse the strip or shift layout. Times render in IBM Plex Mono. A Shabbat line (🕯 + a non-color inline-start border) is distinguishable without color; the cards are read-only (no done/snooze/note affordance). EN fallback flips the day-heads; reduced-motion neutralizes scroll animation.
12. (V3.5 portfolios) The domains render as a tile grid (Money hero + Health/Goals/Car/Contracts), each a `<button>`; tapping one opens **one** shared bottom-sheet for that domain with the full detail (Goals shows the bright-line **in the sheet**, a % bar on the tile [D8]). The sheet traps focus, locks page scroll, dismisses on Esc / scrim / close, and **returns focus to the tile**; reduced-motion disables the slide. Urgency is never color-only (donut %, avatar glyph + day-count, "N over ▲"). No Education tile (folds into the Timeline). RTL default + EN fallback; every new STRINGS key he+en.
13. (V3.6 timeline) The **Timeline** tile (second, after the Money hero) opens the shared bottom-sheet onto a read-only cross-domain chronology: a vertical, date-sorted list with a **now**-marker dividing the recent-past tail from the future. The zoom rungs (1wk/1mo/3mo/1yr/5yr, default 3mo) widen the window; the category chips (all · finance · health · car · education · goals · contracts · calendar · other) filter in place — both update **only** the track + the `aria-pressed` flags, keeping the pressed control's focus (no full-body rebuild). Urgency is never color-only (🔴/⚠/· glyph + due phrase, redundant border). Done/skipped/archived reminders and undated rows never appear; an unmapped reminder Domain still shows under `other`. RTL default + EN fallback; every new STRINGS key he+en.
14. (V3.7 love-note) With `LOVENOTE_URL` configured: signed in as one adult, send a note → the **other** adult sees it as an inbound card (💌 + "from {name}" + text, never color-only) on their **next open**, with **no push**. A second send **replaces** (one note per direction); the sender's "waiting for {name}" + **Clear** removes only their own note; a note older than **24h** is gone (lazy on read + the hourly sweep). The sender gets no "seen" signal. With `LOVENOTE_URL` blank, the whole slot is **absent** (no dead affordance). DEMO_MODE shows the fixture card + a `(demo)` composer. RTL default + EN fallback; every new STRINGS key he+en.
15. (Lane C col-D) Snooze/complete a reminder, reload (incl. **airplane-mode** flush, item 4): the bumped/snoozed Due date **round-trips** — the row keeps its correct day and an overdue row snoozed to a future date leaves OVERDUE (the dashboard reads back col-D whether the Sheet renders it ISO or he-IL DD/MM·DD.MM). Rename/remove a Reminders write column in the Sheet → on next load the dashboard toasts **"writes paused"** and the done/snooze/note taps no-op (no position-write to the wrong column) until the header is restored.
16. (V3.3 desk) The TODAY desk is **select-to-act**: each overdue/fire-today reminder is a checkbox row (tap or Space/Enter toggles; selection is never color-only — a ✓ box + wash + `aria-checked`); no inline expand. Selecting ≥1 reveals the **sticky batch bar** with the live count; tapping ✓ done marks **all** selected rows in one write (recurring rows recurrence-bump), they clear the desk, and the selection + bar reset. The selection also clears on a background reload (no stale `_row`).
17. (V3.3 absolute snooze) On the desk, select a row → `+ snooze` → the chips (tomorrow · +3 · 1 week · 2 weeks · 1 month) **and** the date picker each write an **absolute** Due date. An **OVERDUE** row snoozed to any future date leaves the desk (OVERDUE cleared — the D4 fix); snoozing to tomorrow keeps it as today/fire-today. The picker won't offer past dates (min = today). One snooze over a multi-selection writes all rows in one batch.
18. (V3.3 coming-up) The coming-up slot is a **read-only** ±30-day horizontal scroll band with a **now**-marker; it opens positioned at "now". Scroll **back** shows past calendar events (overdue reminders are **not** repeated here — they live on the desk); scroll **forward** shows week/month-out reminders + upcoming events. today/+1/+2 events appear only in the 3-day calendar strip (no double-render). Verify the RTL scroll direction on **iOS** specifically; chips carry no done/snooze affordance. EN fallback flips copy; every new STRINGS key he+en.
19. (V3.8 i18n + a11y + Settings) **Keyboard-tab** the Today surface: every interactive element shows a visible **`:focus-visible`** ring; tab into the desk rows, the coming-up region, the snooze chips/date-picker, the portfolio tiles, the bottom-sheet (focus stays trapped). With a **screen reader / EN toggle**, the icon-only controls are **named in the active language** (sheet close ✕, coming-up region, snooze date-picker, note field) — flip he↔en and the names flip. With **reduce-motion** on, no transition/scale/scroll animation fires. **Settings → Switch account** opens the Google **account chooser**: pick the *other* parent → the dashboard reloads as them and a new `LastDoneBy` writes their name; **cancel** the chooser → nothing changes (current session intact); re-picking the **same** account does **not** sign you out. Settings shows **no** notif/bank-connect/export controls. Contrast holds AA on both surfaces (the `test_dashboard_a11y_contrast` floor); every new STRINGS key is he+en.

=== End: DESIGN.md ===


```

</details>
