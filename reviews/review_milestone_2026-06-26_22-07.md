# Milestone review — milestone lane

- **When:** 2026-06-26T22:07:30
- **Provider:** DeepSeek (`deepseek-chat`)
- **Elapsed:** 43.0s
- **Attached files (12):**
  - `CLAUDE.md` (7,805 chars)
  - `SPEC.md` (50,193 chars)
  - `BACKLOG.md` (43,771 chars)
  - `ENGINEERING.md` (17,550 chars)
  - `DESIGN.md` (22,669 chars)
  - `automation/finance_recategorize.py` (9,058 chars)
  - `automation/lib/finance_coverage.py` (8,433 chars)
  - `automation/finance_coverage.py` (3,081 chars)
  - `automation/lib/categorize.py` (9,359 chars)
  - `ROADMAP.md` (30,450 chars)
  - `deploy/FINANCE.md` (14,482 chars)
  - `tests/test_finance.py` (54,806 chars)

---

## Response

### Concerns

1. **[HIGH] `finance_recategorize.py` uses `sheet.write_cells` without a header‑fix‑up path for absent headers.**  
   `write_cells` writes by `(row, col)` numeric position. If the live `Finance-Transactions` tab ever drifts (adds a column before Category/Cat‑Source) or the column order in the SPEC is changed without a corresponding backfill update, the surgical write silently stamps the wrong column. The standard ingest path (`finance_ingest.py`) uses `sheet.upsert_rows` with header‑resolved columns, but the backfill bypasses that entirely and assumes the column positions discovered at read time stay valid for write. This is the exact class of bug the §7.1 header guard was designed to prevent.  
   **File:** `automation/finance_recategorize.py` lines 140–144 (the `idx` mapping is built at read time, but `write_cells` uses the same indices for the write target; no re‑validation before the write call).

2. **[HIGH] The backfill writes every changed row as individual `(phys, col, value)` triples in a single `write_cells` call — if that call is partially applied (e.g. API timeout after 50 cells), the tab is left in a corrupted intermediate state.**  
   `sheet.write_cells` is a batch update, but gspread’s `batch_update` is atomic only per‑call, not per‑cell. If the write partially fails (gspread raises after some cells are written), the tab has a hybrid state: some rows got Category/Cat‑Source, others did not. Re‑running the backfill would then see the partially‑written rows as non‑blank (the Category cell is non‑empty) and skip them, leaving the failed rows half‑correct. This is a silent data‑corruption path.  
   **File:** `automation/finance_recategorize.py` lines 146–148 and `automation/lib/sheet.py` `write_cells` (called at line 154).

3. **[MEDIUM] `finance_recategorize.py`’s `--dry-run` skips the LLM gap‑fill, but this means the preview systematically UNDER‑reports the coverage lift the real run will deliver.**  
   The docstring and CLI help say “preview (rules‑only), no write”. If the operator sees a `dry‑run` coverage of, say, 75% → 82% and decides the real run won’t reach 90%, they may not run the real pass — but the real pass includes DeepSeek which could push it to 93%. The dry‑run’s inherently‑lower number is a misleading basis for the “report‑first” accept bar.  
   **File:** `automation/finance_recategorize.py` line 196 (`_print_summary` labels it “rules‑only (dry‑run preview)” and the `run()` function skips the LLM at line 99: `allow_llm=allow_llm and not dry_run`).

4. **[MEDIUM] `finance_coverage.py`’s `rows_from_grid` uses the raw column header as‑is from the Sheet to build the dict keys, but the upstream backfill and read‑time code all normalise via `_norm()`.**  
   If the live Sheet has a trailing space in a header (e.g. `"Category "`), `rows_from_grid` uses `"Category "` as the key, while `finance_recategorize.py`’s `_cell()` looks up `"Category"`. The coverage run would then see zero categorized rows (because the `category` key is missing from every dict) and report 0% coverage, even though the data is correctly categorised. This is a false‑negative display bug that could block a gate.  
   **File:** `automation/lib/finance_coverage.py` lines 48–55 (no `_norm()` on the header before building dict keys).

5. **[LOW] The `Card Settlement` exclusion block is a rules‑file‑order invariant, but the only thing enforcing that order is human discipline and a single test that concatenates tokens — it is very likely to break when a rule is added/removed.**  
   The test `test_excluded_bucket_never_shadows_a_merchant` checks the concat of every excluded‑pattern + every merchant‑pattern, but this only covers existing patterns. A new rule added before the exclusion block could still lift an excluded pattern above a merchant rule. The rules CSV has no explicit ordering marker (e.g. a comment `# BELOW ALL MERCHANT RULES`).  
   **File:** `seeds/14_Finance_Category_Rules.csv` (no section‑level comment) and `tests/test_finance.py` lines 402–420.

### Missed alternatives

1. **Backfill the Card‑Settlement rows via a one‑time SQL‑style `UPDATE` on Txn‑ID set, not a full re‑scan of every blank row.**  
2. **Use `sheet.upsert_rows` with a key_column for the backfill, so header drift is automatically absorbed on write (like the normal ingest path).**  
3. **Make the coverage report also write a machine‑readable JSONL file, so the PO’s box‑run script can assert `coverage_pct >= 0.9` without parsing markdown.**  
4. **Run the DeepSeek dry‑run in a separate `--dry-run-llm` mode that calls the LLM but discards the results for cost audit, rather than silently skipping the gap‑fill.**  
5. **Encode the exclusion‑block ordering constraint directly in the rules CSV by adding an `ORDER` column, so the CSV parser sorts descending before applying.**

### Affirmations

1. **Surgical `write_cells` with blank‑rows‑only scope.** This prevents the backfill from ever clobbering a human‑edited or previously‑assigned category. Idempotent by construction. Correct choice versus an upsert‑by‑key (which could spawn a partial row on a stray Txn‑ID).
2. **Coverage ≠ correctness deferral.** The ⭐ decision to report coverage as the milestone metric and defer the false‑positive rate to ROADMAP #12 is honest engineering. It avoids the impossible requirement of measuring classifier correctness without a human feedback channel, while still giving a meaningful yield number. The report‑first bar is also the right move for a nascent producer.
3. **The `by_source` breakdown scoped to categorized rows only.** The adversarial finding that double‑counting excluded rows in `by_source` made the rule‑count overshoot was fixed. The current code correctly partitions the coverage space and sums cleanly.
4. **The `gapfill_chunks` test for full coverage of a large import.** This is an excellent regression test that proves the chunk‑loop closes the B5 data‑loss path. The mock LLM rejecting off‑vocab answers is also well‑protected.

### Concrete suggestions

1. **In `automation/finance_recategorize.py`, before the `write_cells` call, re‑read the header and verify that the column indices have not shifted since the initial read.**  
   Replace lines 140–148 with:  
   ```python
   # Re‑validate the header before writing (the tab may have drifted since the initial read)
   current_grid = sheet.read_grid(cfg.FINANCE_TRANSACTIONS_TAB, sheet_path)
   current_header = [str(h or "").strip() for h in current_grid[0]]
   current_norm = [_norm(h) for h in current_header]
   for name in REQUIRED:
       if _norm(name) not in current_norm:
           raise RecategorizeError(...re‑raised failure message...)
   idx = {name: (current_norm.index(_norm(name))) for name in CANON}
   cat_col, src_col = idx["Category"] + 1, idx["Cat-Source"] + 1
   ```  
   **Because:** a header shift that happened between the read and the write would otherwise silently scribble into wrong columns, and the backfill cannot recover from that (it only runs once per row).

2. **In `automation/lib/finance_coverage.py`, normalise the header before building dict keys.**  
   On line 49, after reading the header, replace:  
   ```python
   header = [str(h or "").strip() for h in grid[0]]
   ```  
   with:  
   ```python
   raw_header = [str(h or "").strip() for h in grid[0]]
   norm_header = [_norm(h) for h in raw_header]
   ```  
   Then on line 52, use `norm_header[i]` (not `h`) as the dict key. Update `category` reads in `coverage()` to use the same normalised name (or normalise the key at call time).  
   **Because:** a trailing space or case difference in a live‑sheet header would make the coverage report read every row as “blank” and report 0%, even with a correct backfill.

3. **In `automation/finance_recategorize.py`, make `--dry-run` call the LLM but discard the result (a metadata‑only audit trail), or at least print a prominent warning that the real coverage will be higher.**  
   Add to line 196:  
   ```python
   if dry_run:
       print("⚠ dry‑run does not call DeepSeek — real coverage will be higher "
             f"(expected +{res.now_llm} categories from the gap‑fill). "
             "Run without --dry-run to see the live number.")
   ```  
   **Because:** a misleadingly‑low dry‑run number could incorrectly discourage the operator from running the real pass, when the gap‑fill could easily push coverage above the 90% bar.

4. **Add a comment to `seeds/14_Finance_Category_Rules.csv` at the top of the Card‑Settlement section, plus a single‑line test that reads the file and asserts all excluded patterns appear after every non‑excluded pattern.**  
   Add to the CSV:  
   ```csv
   # ---- CARD SETTLEMENT EXCLUSION BLOCK (must stay below ALL merchant rules) ----
   ```  
   Add a test:  
   ```python
   def test_excluded_block_is_last_in_rules_file():
       rules = categorize.load_rules()
       excluded_pat_lines = [i for i, (p, c) in enumerate(rules) if c in categorize.EXCLUDED_CATEGORIES]
       non_excluded_last = max(i for i, (p, c) in enumerate(rules) if c not in categorize.EXCLUDED_CATEGORIES)
       assert min(excluded_pat_lines) > non_excluded_last, "excluded patterns must be the LAST rules in the file"
   ```  
   **Because:** the existing test only checks concatenated tokens, not the file ordering. A regression could silently move an exclusion above a merchant rule without any test failing.

5. **In `deploy/FINANCE.md` §7, add a step between the dry‑run and the real run that checks the exit code / coverage output programmatically, so a coverage below 90% causes the runbook to warn the operator.**  
   Insert after step 2:  
   ```bash
   # Check if coverage after dry-run is plausibly ≥90% (rules-only will be lower;
   # adjust the threshold to, e.g., 60% for rules-only preview).
   if [ "$(python3 -c 'import sys, re; t=open("Briefings/…").read(); m=re.search(r"(\d+)%",t); print(m.group(1) if m else "0")' | head -1)" -lt 60 ]; then
     echo "⚠ Coverage after rules-only preview is low — real coverage with DeepSeek may still be below 90%. Proceed with caution."
   fi
   ```  
   **Because:** the “report‑first” bar is set from the live run; a low‑enough preview should trigger a manual review before the real run stamps the Sheet with categories the operator will later have to re‑run.

### One question for the team

**If the `write_cells` call in `finance_recategorize.py` partially fails (gspread timeout after 50 cells), the live tab is left with some rows categorised and some not — re‑running the backfill is safe for the uncategorised ones, but the half‑categorised ones are now non‑blank and will be skipped forever. What is the recovery path for that “torn‑write” state, and should we add a pre‑write snapshot or a per‑row write‑all loop that re‑validates each write?**

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
# Session changes — M6 finance acceptance tooling + threshold (2026-06-26)

Lane: M6.4/M6.5 finance acceptance (the 06-26 gate). This session built the
acceptance **tooling** and **defined the pass threshold**; the milestone CLOSE
(accepting M6, folding the property-lane review) still awaits the PO **box-run
numbers** (coverage %, accuracy run) and Shanee's budget-vocab fill.

## New code

- **`automation/finance_recategorize.py` — one-time re-categorize BACKFILL.**
  `finance_ingest` categorizes only NEW (post-dedup) rows, so the rows that landed
  before the M6.5 `Card Settlement` rule existed stay blank. This re-runs
  `lib/categorize` (on-box rules + DeepSeek gap-fill, **description + amount only**,
  §8.6) over the currently-**blank** `Finance-Transactions` rows and writes
  `Category`/`Cat-Source` back via **surgical `sheet.write_cells`** at the exact
  `(row, col)` — no append path, so a stray Txn-ID can never spawn a partial row.
  Scope = **blank rows only** (a human/prior tag is never clobbered → idempotent).
  Header-guarded (`RecategorizeError` on a missing load-bearing column, §7.1);
  live-or-`--sheet` only (refuses the committed seed). The ~66 Cal-mirror lines
  reclassify to `Card Settlement` via the existing rule in one pass.

- **`automation/lib/finance_coverage.py` (pure) + `automation/finance_coverage.py`
  (read-only CLI) — the COVERAGE (yield) surface.** Reports categorized vs the
  by-design-excluded `Card Settlement` mirror vs genuinely-blank wrappers, by
  account, naming the still-blank merchants. Headline = categorized / (total −
  excluded). Output is operator-only (stdout or the gitignored `Briefings/`), like
  `accuracy_review.py`. The by-source breakdown is scoped to categorized rows so it
  sums to the categorized headline.

## Threshold defined (the gate's "pass threshold")

- **Summarizer:** accept at **< 1 ALERT-tier false positive / week**
  (`accuracy_review.py`, SPEC §7.3) — ratified as the gate criterion; at/above,
  narrow the over-firing pattern and re-run.
- **Finance categorizer:** the metric is **coverage** (categorized / budget-eligible),
  **report-first** — the numeric bar is set from the first live read (candidate
  ≥90 %; Cal ~90 %). Coverage measures **coverage**, NOT **correctness**; a true
  categorizer false-positive rate needs a human-mark channel — deferred to
  ROADMAP rank 12 (the distinct, post-06-26 lane).

## Canon graduated

- **SPEC §12.2:** new "Categorization & acceptance" facet (backfill seam + coverage
  acceptance + the coverage-≠-correctness deferral + the summarizer cross-reference).
- **deploy/FINANCE.md:** §7 box-run runbook (coverage baseline → backfill dry-run →
  backfill → coverage after; + `accuracy_review.py --weeks 1`), and the **Shanee
  budget-vocab DATA-REQUEST** (she fills `Finance-Budget` columns A `Category` + B
  `Monthly Target` only; decides Fees/Income/Shopping + Income placement).
- **BACKLOG / ROADMAP:** status flips + the resolved "define the threshold" PO call.

## Tests — 483 green (+22 this session, hermetic, tmp-xlsx)

Backfill: backfills blanks (Cal mirror→`Card Settlement`, SHUFERSAL→Groceries,
unknown stays blank), manual row untouched, idempotent, dry-run writes nothing,
seed-safety skip, header-guard fail-loud, empty-tab no-op, **fully-blank interior
row** (write-index alignment invariant), **LLM branch** (dry-run = no API spend +
live `llm` write-back). Coverage: partition holds, per-account, blank samples,
empty degrade, `rows_from_grid`, read-only CLI, by_source sums to categorized.

## Internal adversarial review already run (before this gate)

A 6-lens parallel review (Sheet-write safety, coverage math, privacy/§8.6,
canon-conformance, test coverage, Hebrew/RTL tokens). Findings resolved: **1 major**
(coverage `by_source` double-counted the excluded Card-Settlement rows in the
breakdown printed under `categorized` → fixed; the test that enshrined it updated)
+ **2 test-gap minors** (the two new tests above) + **1 doc nit** (hedged "~66").
The three highest-risk lenses — write-safety, privacy/§8.6, Hebrew-token — returned
CLEAN with concrete verification.

## Explicitly NOT in this session (PO box-run + Shanee)

Running the backfill + coverage + `accuracy_review` ON THE BOX (live numbers),
setting the coverage bar from the read, and Shanee's A:B fill. The milestone CLOSE
+ the property-lane review fold follow once those land.

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

**Finance ingestion (M6, §12.2).** Read-only scrape → categorized transactions + balances in the Sheet → silent surfacing in the briefing and dashboard. **Live on Mizrahi (debit) since 2026-06-19**; the consumer wiring (M6.3) and analysis layer (M6.4) are landing. **Cal (Visa) hooked up 2026-06-23** — an immediate-debit card whose spend also lands merchant-less on the Mizrahi statement, so the Mizrahi-side Cal lines map to an excluded `Card Settlement` bucket (counted once via the card); more cards remain (M6.5). See `BACKLOG.md`.

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
| **Categorization & acceptance** | Two stages at ingest: an on-box keyword→category rules engine, then the LLM gap-fill on the rules-miss remainder (description + amount only — §8.6). Ingest tags **new rows only** (idempotency), so a rules change (e.g. the M6.5 `Card Settlement` exclusion, added after the first Mizrahi imports) reaches history only by a deliberate **one-time backfill**: `automation/finance_recategorize.py` re-runs the same engine over the currently-**blank** rows and writes `Category`/`Cat-Source` back **surgically** (blank rows only → a human or prior categorization is never clobbered; idempotent; header-guarded; live-or-`--sheet` only, never the seed). The milestone metric is **coverage** — `automation/finance_coverage.py` (read-only) reports categorized vs the by-design-excluded `Card Settlement` mirror vs genuinely-blank wrappers, by account, naming the still-blank merchants. The accept bar is set **report-first** from the first live read (candidate **≥ 90 % of budget-eligible rows** — total minus the excluded mirror; Cal already ~90 %). This is **coverage** (a category is present), not **correctness** (the category is right) — a true categorizer false-positive rate needs a human-mark channel, **deferred** (`ROADMAP.md` §classifier-fp-metric, rank 12). The **WhatsApp summarizer** keeps its own separate accuracy gate — **< 1 ALERT-tier false positive / week** (`accuracy_review.py`, §7.3). |
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

**▶ Focus:** M6 finance acceptance — the **06-26 gate is now due**: (1) the first real **classifier-accuracy run** (`accuracy_review.py` over ≥1 week of live rules+DeepSeek output) **+ define the pass threshold**; (2) the historical **re-categorize backfill** (move the ~66 Cal mirror rows → `Card Settlement` and re-run the blank rows through the engine — `finance_ingest` tags only *new* rows, so the backlog never re-enters); (3) **Shanee's budget-vocab migration** (firms the provisional category vocab the rules engine maps to); (4) the **external milestone review** on the live system (folds in the property lane). Work M6.3 → M6.4 → M6.5 (below) in that order; full plan `ROADMAP.md` §2. **▶ Acceptance tooling landed 2026-06-26 (this session) — gate now box-run-only:** the one-time **re-categorize backfill** (`automation/finance_recategorize.py` — re-runs the engine over blank rows, surgical `write_cells` back-write, idempotent, blank-rows-only so a manual/prior tag is never clobbered; the ~66 Cal-mirror lines (box-unverified count) → `Card Settlement` via the existing rule) + a read-only **coverage** surface (`automation/finance_coverage.py` + pure `lib/finance_coverage.py` — categorized vs excluded-mirror vs blank, by account, blank merchants named) — hermetic + tested (**481 green**, +13). **Threshold defined:** summarizer = **< 1 ALERT-FP/week** (ratified, SPEC §7.3); finance = **coverage, report-first** (candidate ≥90% of budget-eligible rows; correctness/FP deferred → ROADMAP rank 12). Canon graduated: SPEC §12.2 (backfill seam + coverage acceptance facet) + `deploy/FINANCE.md §7` (box-run recipe) + the **Shanee budget-vocab data-request** (`deploy/FINANCE.md §6` — she fills `Finance-Budget` A:B only). **Remaining is the PO box-run block** (backfill dry-run → run · coverage before/after · `accuracy_review.py --weeks 1`) → set the bar from the live number → the external `review.py` milestone gate. **✅ v3 Today redesign CLOSED 2026-06-26 (V3.9 — the lane's last slice):** the external milestone review ran (`review.py` DeepSeek — `reviews/review_milestone_2026-06-26_20-47.md`; 1 Apply [SPEC §7.7 replacement-semantics clause], rest Defend/Open, **0 blockers**) alongside an internal **9-area canon-vs-code conformance audit** (every area conformant; 3 nit-level doc catch-ups Applied: SPEC §7.6 blank-title exclusion · DESIGN §4 quiet-day copy · the `userinfo`→`tokeninfo` comment fix — `reviews/review_milestone_2026-06-26_resolution.md`); SPEC §7.6/§7.7 + DESIGN §2/§3/§4/§5/§8/§9 graduated; **468 tests green**. V3.1–V3.8 (UI + i18n/a11y + the love-note text endpoint) are **code-complete, deploy-gated by the Pages publish** (V3.7 love-notes additionally tunnel-gated; voice frozen phase-2). Review follow-ups (JS interactive-logic harness · love-note rate-limit · 120-char composer hint · the Worker-vs-tunnel phase-2 PO call) → **Deferred** below.
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
- 🔵 **M6.3 — consumer wiring + close.** Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning is armed (`FINANCE_STALE_IMPORT_DAYS`). **Budget-SUMIFS installer ran live 2026-06-20** (`automation/finance_budget_formulas.py`): stamped the 66 machine cells onto `Finance-Budget`, actuals verified **non-zero** (Groceries/Transport; Health ₪0 — no health debits in-window, re-check in the 06-26 accuracy run) — the M6.4 reconciliation tail is now live. *Live-tab drift caught + fixed:* the early-created live tab was one column short of canon — the M6.4 helper block's **`J` `Last Month (ILS)`** header was never backfilled, so the installer's load-bearing-column guard refused; set `J1` by hand, then it stamped clean. **Installer then hardened (390 green):** it now titles its own *absent* machine headers (incl. `J`) and stamps, refusing only on a missing *human* header (Category/Target) or a real column shift — so Shanee's migration needs only Category + Monthly Target present, no machine-column setup (`deploy/FINANCE.md §6`, `test_budget_installer_titles_absent_machine_header`). **Dashboard `config.js` was a non-issue:** Pages generates it from `config.example.js` (already full tab names) on every `dashboard/**` push, and the TOTAL-row-exclusion fix shipped via Pages 2026-06-20 — no box-side edit. The dashboard Money drawer + Sunday money summary exclude the `Finance-Budget` `TOTAL` row (fixed at the `parseAll` source so both surfaces inherit it; the briefing's `section_money` already skipped it, tested); `mock_data.json` carries a TOTAL row so DEMO_MODE matches live. **Remaining = acceptance only:** the first real monthly review (~30 days in); classifier-accuracy run + external review gated ~2026-06-26.
- 🔵 **M6.4 — analysis layer.** *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates `Category`/`Cat-Source` at ingest; DeepSeek gap-fills the rules-miss remainder (description + amount only, §8.6). The briefing Money section gained per-category spend + month-over-month (the dashboard drawer reads the same tab — M6.3). **Reconciliation (the build-note landmine, resolved):** budget actuals now `SUMIFS` with a **text-prefix wildcard** on the ISO-text Date (`<yyyy-mm>&"*"`), not a serial `DATE()` window that read ₪0 — chosen over `USER_ENTERED` (which would coerce `Txn-ID`/`Account` and break dedup); the append stays RAW. Seed formulas updated + a regression test pins the form. **Installer built + tested 2026-06-20:** `automation/finance_budget_formulas.py` (single-sourced from `lib/finance_budget`, pinned against the seed) idempotently stamps the machine columns onto the live tab — machine columns only (a category row's Category/Target and every Notes cell untouched; only the TOTAL's Target is a machine sum), so there's no hand-copy and the "stray Notes SUMIFS" copy-artifact class is gone. **Gated to live data:** run it on the box (`--dry-run` first) + verify actuals go non-zero on the first real month. **PROVISIONAL** category vocab until Shanee's budget migration firms it up — when she remaps, just re-run the installer. Silent delivery; no anomaly detection. **Live categorization — reframed 2026-06-23 (Cal hookup): the earlier "~77% blank" alarm is *mostly structural, not a classifier failure*.** The blank rows on the Mizrahi debit are merchant-less wrappers (Cal settlements, ATM, cheque, other cards) that correctly return UNKNOWN — there is no merchant to categorize. Proof: **Cal's own scrape categorizes its 102 rows at ~90%** (the full tab now reads 48 rules + 74 LLM), because the card carries per-merchant descriptions. So the fix is **more sources** (hook up the remaining cards — M6.5), **Shanee's vocab migration** (firms the provisional vocab for the categorizable rows), and a **one-time re-categorize backfill** of the historical blank rows — **built 2026-06-26** (`automation/finance_recategorize.py`: re-runs the engine over blank rows, surgical write-back, idempotent, blank-rows-only; `finance_ingest` only categorizes *new* rows, so this is the deliberate seam for the backlog to re-enter the engine). Paired with a read-only **coverage** surface (`automation/finance_coverage.py` + `lib/finance_coverage.py`) — the report-first milestone metric (categorized vs excluded-mirror vs blank, by account). Both hermetic + tested (481 green); **box-run pending**. This trio is the substance of the gated 06-26 accuracy work; the `Finance-Budget` total is understated only by the genuinely-uncategorizable cash/cheque/other-card spend until those cards are added.
- 🔵 **M6.5 — cards lane (un-deferred 2026-06-23, the third VPS hour).** **Cal (Visa) is live** — hooked up via a one-time headed `--auth` device-trust login (xvfb + x11vnc over an SSH tunnel; `FINANCE.md §4`), now scraping **headless** daily (first import 103 txns, ~90% categorized). Cal is *immediate-debit*, so each purchase already lands merchant-less on the Mizrahi statement; the Cal scrape is what supplies the per-merchant detail. The Mizrahi-side Cal settlement lines map to an excluded **`Card Settlement`** bucket — a rules entry (`כא"ל`/`ויזה כאל` tokens; ASCII-quote `U+0022` verified against live data, no over-match incl. Shanee's `כרטיס דביט` and the `כארם` restaurant) + a test seam (`test_card_settlement_excludes_cal_mirror`, plus the vocab-test `excluded` set + inverse guard so a future budget migration can't make it a budget row; 422 green) — so each Cal purchase counts **once**, via the Cal side, never the mirror. **Verified no double-count empirically** (both Money consumers read the by-category `Finance-Budget` actuals; the mirror lines stay out of the SUMIFS). **Open:** **(a) Shanee's debit card — mirror token landed 2026-06-23 (this session).** It turns out to be a Cal-cleared *immediate-debit* card on the **already-connected Cal login**, so it needed **no new `--auth`** — *correcting the morning's "each remaining card needs its own auth" assumption*. The only repo change is the `רכישה בכרטיס דביט` → `Card Settlement` mirror token (its per-merchant detail rides the existing Cal scrape), plus **flipping the 06-23-morning over-match guard** (`test_card_settlement_excludes_cal_mirror`: `רכישה בכרטיס דביט` was asserted *not*-excluded when her card wasn't yet scraped; now asserted excluded — a `דמי כרטיס דביט` fee-line guard (tightened 2026-06-25 to assert `== Fees`) so the full `רכישה ב…` phrase can't catch a card fee). **Over-match fix (2026-06-25):** the whole `Card Settlement` exclusion block was moved *below* every merchant rule (a last-resort fallback), plus merchant-suffix contract assertions and a `test_excluded_bucket_never_shadows_a_merchant` ordering-invariant test; 423 green. **Box-verify pending (de-risked, not blocking):** (i) confirm her per-merchant rows actually ride the existing Cal scrape — the mirror only reclassifies the Mizrahi line blank→excluded (budget total unchanged either way), so the "count once" correctness completes when her Cal rows are confirmed flowing; if they're on a *separate* Cal login, add a second `cal`-keyed provider + creds + `--auth`. (ii) **RESOLVED 2026-06-25 (structural):** the exclusion block now sits *below* the merchant rules, so a merchant-suffixed settlement line categorizes by its merchant and only genuinely merchant-less wrappers fall through — the 06-23-flagged latent over-match is closed independent of the live feed (the invariant test pins it). The other statement cards still need each source confirmed before a mirror (`ויזה-דביט`; `חיוב ויזה כאל עתידי` is already caught by the `ויזה כאל` token). **(b)** the historical **backfill** to move the existing 66 Cal mirror rows to `Card Settlement` (the rule is forward-only — it tags new rows at ingest; correctness already holds since blanks are excluded, but the yield metric + ledger clarity want it). **Tool built 2026-06-26** (`finance_recategorize.py`, hermetic + tested; the Cal-mirror lines reclassify via the existing rule in one pass) — box-run pending.
- ⬜ **Parallel (Shanee).** Budget migration — her manual budget → `Finance-Budget`; gives the actuals a target and defines the category vocab the rules engine maps to.

## Gated — summarizer review (opens ~2026-06-20, needs ≥1 week live)

- ⬜ **First real classifier-accuracy run + false-positive cleanup** — run `accuracy_review.py --weeks 1` over a full week of live DeepSeek output; narrow any over-firing keyword patterns. **Threshold ratified 2026-06-26:** accept at **< 1 ALERT-tier false positive/week** (SPEC §7.3); at/above, narrow the pattern and re-run. In the PO box-run block.
- ⬜ **External milestone review on the live system** — folds in the property lane's review too. Runs (`review.py` DeepSeek) once the box-run numbers are in; this session's diff (backfill + coverage + canon) is part of its scope.

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

=== File: automation/finance_recategorize.py ===
"""
Family inc. — one-time finance re-categorize backfill (SPEC §12.2, M6.4/M6.5).

`finance_ingest` categorizes only the NEW (post-dedup) rows of each run, so the
historical backlog never re-enters the engine — by design (idempotency). When a
RULE changes (the M6.5 `Card Settlement` exclusion was added 2026-06-23, after
the first Mizrahi imports), the already-landed rows that the new rule would now
match stay BLANK. This is the deliberate seam to apply a rules change to history:
re-run the categorizer over the currently-BLANK rows and write the results back.

It is exactly the categorizer ingest runs (`lib/categorize`, rules + DeepSeek
gap-fill, description + amount only — §8.6), pointed at the live tab instead of a
fresh CSV. Two effects, one pass:
  • the ~66 Cal-mirror lines (`כא"ל`/`ויזה כאל`/`רכישה בכרטיס דביט`) match the
    Card Settlement rule → move blank → excluded (out of the actuals SUMIFS);
  • any genuine merchant the rules now cover, or the LLM can place, gets a
    category. A genuinely merchant-less wrapper (ATM/cheque) stays blank.

SAFETY:
  • Scope is BLANK rows only — a row that already carries a Category (rules, llm,
    or a human's manual edit) is never touched, so the backfill can't clobber a
    correction. Re-running is therefore idempotent: a second run finds nothing.
  • Writes are SURGICAL — `sheet.write_cells` to the exact (row, Category-col) and
    (row, Cat-Source-col) of each changed row, discovered by reading the tab. No
    append path exists, so a stray Txn-ID can never spawn a partial row (the one
    risk an upsert-by-key would carry).
  • Header-guarded (mirrors §7.1): a Finance-Transactions tab missing Category /
    Cat-Source / Description fails loud rather than writing by guessed position.
  • Live backend or explicit --sheet only — refuses to touch the committed seed,
    exactly like the ingest write path.

  python3 automation/finance_recategorize.py --dry-run     # preview (rules-only), no write
  python3 automation/finance_recategorize.py               # rules + DeepSeek, writes live
  python3 automation/finance_recategorize.py --no-llm      # rules-only, writes live
  python3 automation/finance_recategorize.py --sheet x.xlsx --dry-run
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/finance_recategorize.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from automation.lib import categorize
from automation.lib import config as cfg
from automation.lib import finance_coverage as fc
from automation.lib import sheet

log = logging.getLogger("finance.recategorize")

# Canonical keys the categorizer + coverage read — sourced by header position so a
# differently-cased live header still maps correctly (the guard below confirms the
# load-bearing ones exist first).
CANON = ["Date", "Account", "Description", "Amount (ILS)",
         "Category", "Cat-Source", "Txn-ID"]
REQUIRED = ("Category", "Cat-Source", "Description")


class RecategorizeError(RuntimeError):
    """The live Finance-Transactions tab lacks a load-bearing column (§7.1) —
    refuse to write Category/Cat-Source by guessed position. Fail loud."""


def _norm(h) -> str:
    return str(h or "").strip().casefold()


def _cell(raw: list, i: Optional[int]):
    if i is None or i >= len(raw):
        return ""
    v = raw[i]
    return "" if v is None else v


@dataclass
class RunResult:
    total: int = 0
    blank_before: int = 0
    recategorized: int = 0       # blank rows that gained a Category this run
    now_rules: int = 0
    now_llm: int = 0
    still_blank: int = 0
    wrote: bool = False
    before: Optional[fc.Coverage] = None
    after: Optional[fc.Coverage] = None


def run(today: Optional[date] = None, dry_run: bool = False, allow_llm: bool = True,
        sheet_path: Optional[Path] = None) -> RunResult:
    today = today or date.today()
    live = True if sheet_path is not None else sheet.is_live()
    res = RunResult()

    if sheet_path is None and not live:
        print("(no live Sheet backend — nothing to recategorize, won't touch the seed)")
        return res

    grid = sheet.read_grid(cfg.FINANCE_TRANSACTIONS_TAB, sheet_path)
    if not grid:
        print(f"(no {cfg.FINANCE_TRANSACTIONS_TAB} rows — nothing to recategorize)")
        return res

    header = [str(h or "").strip() for h in grid[0]]
    norm = [_norm(h) for h in header]
    idx = {name: (norm.index(_norm(name)) if _norm(name) in norm else None)
           for name in CANON}
    missing = [c for c in REQUIRED if idx[c] is None]
    if missing:
        raise RecategorizeError(
            f"{cfg.FINANCE_TRANSACTIONS_TAB} missing load-bearing column(s) "
            f"{missing} — refusing to write by position (SPEC §7.1)")

    # One pass: canonical-keyed dicts (decoupled from raw header casing) + the
    # physical 1-based row index for the surgical write. Skip fully-blank rows
    # (matches lib/finance_coverage.rows_from_grid).
    rows_all: list[dict] = []
    cand: list[tuple[int, dict]] = []          # (physical row, dict) for blank rows
    for phys, raw in enumerate(grid[1:], start=2):
        if not any(v not in (None, "") for v in raw):
            continue
        d = {name: _cell(raw, idx[name]) for name in CANON}
        rows_all.append(d)
        if not str(d.get("Category", "") or "").strip():
            cand.append((phys, d))

    res.total = len(rows_all)
    res.blank_before = len(cand)
    res.before = fc.coverage(rows_all)

    # Re-run the engine over the blank rows IN PLACE (same dict objects sit in
    # rows_all, so the AFTER coverage reflects the result). A dry-run previews the
    # rules stage only — deterministic, no API spend; the live run adds the LLM
    # gap-fill (§8.6). Already-categorized rows are absent from `cand`, untouched.
    categorize.categorize_transactions([d for _, d in cand],
                                       allow_llm=allow_llm and not dry_run)

    changed = [(phys, d) for phys, d in cand
               if str(d.get("Category", "") or "").strip()]
    res.recategorized = len(changed)
    res.now_rules = sum(1 for _, d in changed if d.get("Cat-Source") == "rules")
    res.now_llm = sum(1 for _, d in changed if d.get("Cat-Source") == "llm")
    res.still_blank = res.blank_before - res.recategorized
    res.after = fc.coverage(rows_all)

    cat_col, src_col = idx["Category"] + 1, idx["Cat-Source"] + 1
    cells = []
    for phys, d in changed:
        cells.append((phys, cat_col, d["Category"]))
        cells.append((phys, src_col, d["Cat-Source"]))

    _print_summary(res, changed, dry_run, allow_llm)

    if dry_run:
        print("(dry-run — no Sheet write)")
    elif cells:
        sheet.write_cells(cfg.FINANCE_TRANSACTIONS_TAB, cells, sheet_path)
        res.wrote = True
        print(f"wrote Category/Cat-Source for {res.recategorized} row(s)")
    else:
        print("nothing to write — every blank row stayed blank")
    return res


def _print_summary(res: RunResult, changed, dry_run: bool, allow_llm: bool) -> None:
    b, a = res.before, res.after
    print(f"\nFinance-Transactions: {res.total} rows · {res.blank_before} blank")
    stage = "rules-only (dry-run preview)" if dry_run else (
        "rules + DeepSeek" if allow_llm else "rules-only")
    print(f"recategorized [{stage}]: {res.recategorized} "
          f"(rules {res.now_rules} · llm {res.now_llm}) · {res.still_blank} still blank")
    print(f"coverage of budget-eligible rows: "
          f"{b.coverage_pct * 100:.0f}% → {a.coverage_pct * 100:.0f}%  "
          f"(excluded/Card-Settlement {b.excluded} → {a.excluded})")
    if changed:
        shown = changed[:25]
        print(f"\nchanges{' (first 25)' if len(changed) > 25 else ''}:")
        for _, d in shown:
            tid = str(d.get("Txn-ID", "") or "")[:10]
            desc = fc._clip(d.get("Description", ""), 40)
            print(f"  {tid:<10}  {desc:<41} → {d['Category']} [{d['Cat-Source']}]")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="preview the rules-stage reclassification, write nothing")
    ap.add_argument("--no-llm", action="store_true",
                    help="rules-only (skip the DeepSeek gap-fill) even on a live write")
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today (cosmetic, logging)")
    ap.add_argument("--sheet", help="explicit xlsx path (tooling/tests)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, dry_run=args.dry_run, allow_llm=not args.no_llm,
        sheet_path=Path(args.sheet) if args.sheet else None)


if __name__ == "__main__":
    main()

=== End: automation/finance_recategorize.py ===

=== File: automation/lib/finance_coverage.py ===
"""
Family inc. — finance categorization COVERAGE (SPEC §12.2, M6.4 acceptance).

A read-only measure of how much of `Finance-Transactions` carries a Category,
split into the three states that matter for the M6 milestone close:

  • categorized  — a Category that IS a budget row (Cat-Source rules | llm |
                   manual). These feed the actuals SUMIFS.
  • excluded     — a Category in `categorize.EXCLUDED_CATEGORIES`
                   ('Card Settlement', the Cal-mirror lines). DELIBERATELY not a
                   budget row — the spend counts once via the per-merchant card
                   scrape — so these are handled-by-design, neither a hit nor a
                   miss. They come OUT of the coverage denominator.
  • blank        — no Category. An honest unknown: a mix of merchants the engine
                   missed AND genuinely merchant-less wrappers (ATM, cheque,
                   inter-account) that have nothing to categorize.

The headline is COVERAGE OF BUDGET-ELIGIBLE ROWS = categorized / (total −
excluded). This is yield (did we put *a* category on it), NOT correctness (is
the category *right*) — a true false-positive rate needs a human-mark channel,
deferred to ROADMAP #12. So the milestone number this surface reports is
"X% categorized", and the accept bar is set report-first from the live read
(candidate ≥90% of budget-eligible rows; Cal already runs ~90%).

Pure: grid/rows in, numbers + a markdown render out. No Sheet I/O lives here
(the CLI, automation/finance_coverage.py, does the read through lib/sheet). The
render names the still-blank merchants so the operator can decide whether a new
rule is warranted — operator-only output (stdout or the gitignored Briefings/),
never a committed path, like accuracy_review.py's ALERT text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from automation.lib import config as cfg
from automation.lib.categorize import EXCLUDED_CATEGORIES

# Cat-Source values the categorizer writes; anything else a human typed → "manual".
KNOWN_SOURCES = ("rules", "llm")


def _norm(h) -> str:
    return str(h or "").strip().casefold()


def rows_from_grid(grid: list[list]) -> list[dict]:
    """A raw Finance-Transactions grid (header + rows) → header-keyed dicts,
    skipping fully-blank rows. Tolerant of short rows (missing trailing cells)."""
    if not grid:
        return []
    header = [str(h or "").strip() for h in grid[0]]
    out: list[dict] = []
    for row in grid[1:]:
        d = {h: (row[i] if i < len(row) else None) for i, h in enumerate(header)}
        if any(v not in (None, "") for v in d.values()):
            out.append(d)
    return out


def _category(row: dict) -> str:
    return str(row.get("Category", "") or "").strip()


def _source(row: dict) -> str:
    s = str(row.get("Cat-Source", "") or "").strip().casefold()
    return s if s in KNOWN_SOURCES else ("manual" if _category(row) else "")


def _clip(text: str, n: int = 48) -> str:
    t = re.sub(r"\s+", " ", str(text or "").strip())
    return (t[: n - 1] + "…") if len(t) > n else t


@dataclass
class AccountCoverage:
    total: int = 0
    categorized: int = 0
    excluded: int = 0
    blank: int = 0

    @property
    def eligible(self) -> int:
        return self.total - self.excluded

    @property
    def pct(self) -> float:
        return self.categorized / self.eligible if self.eligible else 0.0


@dataclass
class Coverage:
    total: int = 0
    categorized: int = 0          # non-blank Category that is NOT an excluded bucket
    excluded: int = 0             # Category in EXCLUDED_CATEGORIES (Card Settlement)
    blank: int = 0                # no Category
    by_source: dict = field(default_factory=dict)        # rules|llm|manual -> count (categorized rows only)
    by_account: dict = field(default_factory=dict)       # account -> AccountCoverage
    blank_samples: list = field(default_factory=list)    # (description_clip, count), desc

    @property
    def eligible(self) -> int:
        """Budget-eligible rows — the coverage denominator (excludes the
        by-design Card-Settlement mirror lines, which are neither hit nor miss)."""
        return self.total - self.excluded

    @property
    def coverage_pct(self) -> float:
        return self.categorized / self.eligible if self.eligible else 0.0

    @property
    def raw_pct(self) -> float:
        return self.categorized / self.total if self.total else 0.0


def coverage(rows: list[dict]) -> Coverage:
    """Pure compute over Finance-Transactions dict-rows → Coverage. Every row is
    exactly one of categorized / excluded / blank, so the three partition total."""
    c = Coverage()
    blank_counts: dict[str, int] = {}
    for r in rows:
        c.total += 1
        cat = _category(r)
        acct = str(r.get("Account", "") or "").strip() or "(unknown)"
        ac = c.by_account.setdefault(acct, AccountCoverage())
        ac.total += 1
        if not cat:
            c.blank += 1
            ac.blank += 1
            key = _clip(r.get("Description", "")) or "(no description)"
            blank_counts[key] = blank_counts.get(key, 0) + 1
        elif cat in EXCLUDED_CATEGORIES:
            c.excluded += 1
            ac.excluded += 1
        else:
            c.categorized += 1
            ac.categorized += 1
            # by_source is the breakdown render() prints UNDER `categorized`, so tally it
            # over categorized rows only — an excluded Card-Settlement line carries
            # Cat-Source "rules" too, and counting it here would make the rules sub-count
            # overshoot (and not sum to) the categorized total on every live run.
            c.by_source[_source(r)] = c.by_source.get(_source(r), 0) + 1
    c.blank_samples = sorted(blank_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return c


def render(c: Coverage, today: date, *, blank_top: int = 15) -> str:
    """Markdown operator surface (stdout / gitignored Briefings/). Names the
    still-blank merchants so the operator can judge whether a rule is warranted —
    NEVER a committed path (the descriptions are live merchant strings)."""
    if c.total == 0:
        return ("# 🏠 Family inc. — finance categorization coverage\n"
                f"_{today.isoformat()}_\n\n_No finance transactions yet._\n")
    src = c.by_source
    parts = [
        "# 🏠 Family inc. — finance categorization coverage",
        f"_{today.isoformat()} · Finance-Transactions ({c.total} rows)_\n",
        "## Summary",
        f"- **Coverage of budget-eligible rows: {c.coverage_pct * 100:.0f}%** "
        f"({c.categorized} of {c.eligible})  ← the milestone metric",
        f"- categorized: {c.categorized}  "
        f"(rules {src.get('rules', 0)} · llm {src.get('llm', 0)}"
        + (f" · manual {src['manual']}" if src.get('manual') else "") + ")",
        f"- excluded by design (Card Settlement mirror): {c.excluded}",
        f"- uncategorized (blank): {c.blank}",
        f"- raw coverage (incl. excluded in the base): {c.raw_pct * 100:.0f}%",
    ]
    parts.append("\n## By account")
    parts.append("| account | rows | categorized | excluded | blank | coverage |")
    parts.append("|---|--:|--:|--:|--:|--:|")
    for acct, ac in sorted(c.by_account.items(), key=lambda kv: -kv[1].total):
        parts.append(f"| {acct} | {ac.total} | {ac.categorized} | {ac.excluded} "
                     f"| {ac.blank} | {ac.pct * 100:.0f}% |")
    if c.blank_samples:
        parts.append("\n## Uncategorized — top descriptions (operator review)")
        parts.append("_A merchant here that recurs is a candidate for a new rule "
                     "(`seeds/14_Finance_Category_Rules.csv`); a merchant-less "
                     "wrapper (ATM/cheque/inter-account) is correctly blank._")
        for desc, n in c.blank_samples[:blank_top]:
            parts.append(f"- {desc}  ×{n}")
        if len(c.blank_samples) > blank_top:
            parts.append(f"- …and {len(c.blank_samples) - blank_top} more distinct.")
    parts.append(
        "\n---\n_Bar: report-first — set the accept threshold from this read "
        "(candidate ≥90% of budget-eligible rows; Cal runs ~90%). This is "
        "COVERAGE (did we tag it), not CORRECTNESS (is the tag right) — a true "
        "false-positive rate needs a human-mark channel, deferred to ROADMAP #12._")
    return "\n".join(parts) + "\n"

=== End: automation/lib/finance_coverage.py ===

=== File: automation/finance_coverage.py ===
"""
Family inc. — finance categorization coverage report (SPEC §12.2, M6.4).

The read-only standing surface for the M6 milestone metric: how much of the live
Finance-Transactions tab carries a Category, by-source and by-account, with the
still-blank merchants named for the operator. Pairs with the one-time
re-categorize backfill (automation/finance_recategorize.py), which PRINTS this
before/after; this script is the on-demand / pre-review read.

Read-only — never writes the Sheet. Output is operator-only: stdout, or
--write drops it into the gitignored Briefings/ (like accuracy_review.py),
because the blank-merchant list is live description text. Degrades quiet: no
live backend and no --sheet → nothing to read, a calm note.

  python3 automation/finance_coverage.py [--as-of YYYY-MM-DD] [--write]
                                         [--sheet path.xlsx]
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/finance_coverage.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from automation.lib import config as cfg
from automation.lib import finance_coverage as fc
from automation.lib import sheet

log = logging.getLogger("finance.coverage")


def run(today: date, write: bool = False,
        sheet_path: Optional[Path] = None) -> fc.Coverage:
    live = True if sheet_path is not None else sheet.is_live()
    if sheet_path is None and not live:
        print("(no live Sheet backend — nothing to measure, won't read the seed)")
        return fc.coverage([])
    grid = sheet.read_grid(cfg.FINANCE_TRANSACTIONS_TAB, sheet_path)
    cov = fc.coverage(fc.rows_from_grid(grid))
    body = fc.render(cov, today)
    if cov.total:
        print(f"finance coverage · {today}: {cov.coverage_pct * 100:.0f}% of "
              f"{cov.eligible} budget-eligible rows categorized "
              f"({cov.categorized} cat · {cov.excluded} excluded · {cov.blank} blank)")
    if write and cov.total:
        cfg.BRIEFINGS_DIR.mkdir(exist_ok=True)
        out = cfg.BRIEFINGS_DIR / f"{today.isoformat()}_finance_coverage.md"
        out.write_text(body, encoding="utf-8")
        print(f"wrote {out}")
    else:
        print("\n" + body)
    return cov


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--write", action="store_true",
                    help="write the report to Briefings/ (gitignored) instead of stdout")
    ap.add_argument("--sheet", help="explicit xlsx path (tooling/tests)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, write=args.write,
        sheet_path=Path(args.sheet) if args.sheet else None)


if __name__ == "__main__":
    main()

=== End: automation/finance_coverage.py ===

=== File: automation/lib/categorize.py ===
"""
Family inc. — finance categorization (SPEC §12.2 / §8.6, M6.4; D-050/051).

Two stages, both degrade-quiet (§3.6):

  1. On-box rules engine — seeds/14_Finance_Category_Rules.csv maps a keyword
     (case-insensitive SUBSTRING, Hebrew or English) to a category. Applied to
     EVERY transaction; first match wins (rows are ordered specific→general).
     Most transactions are tagged here and never leave the box.

  2. DeepSeek gap-fill (lib/llm) — ONLY the rules-miss remainder, and ONLY each
     transaction's DESCRIPTION + AMOUNT (never the account, balance, Txn-ID,
     identifier, or the whole ledger — §8.6). The model must answer with a
     category from the rules file's own vocabulary or "UNKNOWN"; anything else
     leaves the transaction blank.

Cat-Source: "rules" | "llm" | "" (blank = uncategorized — the budget SUMIFS
just won't bucket it, and a human can fill it later). Nothing here raises into
the ingest: a missing rules file, a missing key, an LLM error, or an off-vocab
answer all collapse to "leave it blank".
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from automation.lib import config

log = logging.getLogger("finance.categorize")

# Per-prompt cap so a pathological import can't balloon a single LLM request.
# It is a CHUNK size, not a ceiling: `_gapfill` loops over all rules-misses in
# batches of this size, so every miss is categorized before the write. (A miss
# left blank would be appended with its real Txn-ID, then excluded from dedup
# forever — never re-presented to the LLM — so a one-shot 80-cap was permanent
# data loss on the first 45-day backlog. B5, audit 2026-06-18.)
GAPFILL_MAX_BATCH = 80


# ---------------------------------------------------------------------------
# Rules (stage 1) — pure, on-box
# ---------------------------------------------------------------------------
def load_rules(path: Optional[Path] = None) -> list[tuple[str, str]]:
    """Parse the rules CSV → [(pattern_casefolded, category)], file order kept.
    Comment (#) / blank / header lines are skipped; a missing file → [] (the
    rules engine no-ops, degrade quiet). Patterns are casefolded once here so
    matching is a plain case-insensitive substring test."""
    path = Path(path or config.FINANCE_CATEGORY_RULES)
    if not path.exists():
        log.warning("no finance category rules at %s — rules engine no-ops", path)
        return []
    rules: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.casefold().startswith("pattern,"):
            continue
        pat, _, cat = s.partition(",")
        pat, cat = pat.strip(), cat.strip()
        if pat and cat:
            rules.append((pat.casefold(), cat))
    return rules


# Categories a RULE may assign deterministically but the LLM gap-fill must NOT — the
# excluded buckets. 'Card Settlement' is the Cal-settlement mirror (M6.5): a not-a-
# budget-row label, so anything tagged with it contributes 0 to every actuals SUMIFS.
# That is correct for the Cal mirror lines (which match an exact rule), but if the LLM
# could pick it for an ambiguous NON-mirror row that misses every rule, it would
# silently zero a real expense. So apply_rules (stage 1) still assigns these; they are
# kept out of vocabulary() (the stage-2 LLM vocab) — reachable only by an exact rule.
EXCLUDED_CATEGORIES = frozenset({"Card Settlement"})


def vocabulary(rules: list[tuple[str, str]]) -> list[str]:
    """Distinct categories in file order, MINUS the EXCLUDED_CATEGORIES — the ONLY
    labels the LLM gap-fill may use. apply_rules can still assign an excluded bucket
    deterministically; this list is the stage-2 LLM vocab, so a bucket like 'Card
    Settlement' is reachable only by an exact rule match, never an LLM guess."""
    seen: set[str] = set()
    out: list[str] = []
    for _, cat in rules:
        if cat in EXCLUDED_CATEGORIES or cat in seen:
            continue
        seen.add(cat)
        out.append(cat)
    return out


def apply_rules(description: str, rules: list[tuple[str, str]]) -> Optional[str]:
    """First category whose keyword is a substring of the description, else None."""
    d = (description or "").casefold()
    if not d:
        return None
    for pat, cat in rules:
        if pat in d:
            return cat
    return None


# ---------------------------------------------------------------------------
# Orchestration — rules first, then the bounded gap-fill
# ---------------------------------------------------------------------------
def categorize_transactions(txns: list[dict], *, allow_llm: bool = True,
                            rules_path: Optional[Path] = None) -> None:
    """Populate Category + Cat-Source on each txn dict IN PLACE (Finance-
    Transactions shape). Rules run on every still-blank txn; then, when
    `allow_llm` and a provider key is configured, the LLM gap-fills the
    rules-miss remainder. A txn that already carries a Category is left as-is."""
    if not txns:
        return
    rules = load_rules(rules_path)
    misses: list[dict] = []
    for t in txns:
        if str(t.get("Category", "") or "").strip():   # already categorized
            continue
        cat = apply_rules(t.get("Description", ""), rules)
        if cat:
            t["Category"], t["Cat-Source"] = cat, "rules"
        else:
            misses.append(t)
    if allow_llm and misses:
        _gapfill(misses, vocabulary(rules))


def _gapfill(misses: list[dict], vocab: list[str]) -> None:
    """DeepSeek (or the configured fallback) over the rules-miss remainder, in
    chunks of GAPFILL_MAX_BATCH so the WHOLE remainder is categorized before the
    write — a large first import (the 45-day backlog) is fully covered, not
    truncated at the per-prompt cap. No vocab / no key → no-op. lib/llm is
    imported lazily so a keyless box pays nothing and the import never hinges on
    the LLM module."""
    if not vocab:
        return
    from automation.lib import llm
    if not llm.available():
        return
    for start in range(0, len(misses), GAPFILL_MAX_BATCH):
        _gapfill_batch(misses[start:start + GAPFILL_MAX_BATCH], vocab, llm)


def _gapfill_batch(batch: list[dict], vocab: list[str], llm) -> None:
    """One LLM request over <= GAPFILL_MAX_BATCH rules-misses. A failed/empty
    reply leaves THIS chunk blank (degrade quiet, §3.6) without aborting the
    other chunks — those rows can still be filled by a human or a later run."""
    # Privacy seam: each line carries a within-batch INDEX (not the Txn-ID), the
    # amount, and the description — nothing else from the row ever leaves the box.
    lines = []
    for i, t in enumerate(batch):
        amt = t.get("Amount (ILS)", "")
        desc = str(t.get("Description", "") or "").replace("\n", " ").strip()
        lines.append(f"{i}\t{amt}\t{desc}")
    system = (
        "You categorize Israeli household bank and credit-card transactions. "
        "For each line choose EXACTLY ONE category from this list:\n"
        f"{', '.join(vocab)}\n"
        'If none clearly fits, use "UNKNOWN". Decide from the description and '
        "amount only. Reply with a JSON object of the form "
        '{"results":[{"i":<index>,"category":"<one listed category or UNKNOWN>"}]}.'
    )
    prompt = "index\tamount\tdescription\n" + "\n".join(lines)
    # Size the reply budget to the chunk. A full GAPFILL_MAX_BATCH reply of
    # {"i":N,"category":"…"} items runs ~1.5k tokens — a fixed 600 truncates the
    # JSON array mid-stream, and a truncated object recovers NOTHING, so the
    # WHOLE chunk would land blank with real Txn-IDs and never be re-presented
    # (the very B5 data-loss this loop closes). ~24 tok/row + floor.
    raw = llm.complete(prompt, task="categorize", system=system,
                       max_tokens=max(256, len(batch) * 24),
                       source="finance.categorize", json_mode=True)
    if not raw:
        return
    for i, cat in _parse_gapfill(raw, vocab, len(batch)).items():
        batch[i]["Category"], batch[i]["Cat-Source"] = cat, "llm"


def _parse_gapfill(raw: str, vocab: list[str], n: int) -> dict[int, str]:
    """Tolerant parse: the first JSON object in the reply (DeepSeek json_mode is
    clean; the Anthropic fallback may wrap prose). Keep only in-range indices
    mapped to an in-vocab category (case-insensitive); drop UNKNOWN / off-vocab."""
    obj = _first_json_object(raw)
    if not isinstance(obj, dict):
        return {}
    canon = {c.casefold(): c for c in vocab}
    out: dict[int, str] = {}
    for item in obj.get("results") or []:
        if not isinstance(item, dict):
            continue
        try:
            i = int(item["i"])
        except (KeyError, TypeError, ValueError):
            continue
        cat = canon.get(str(item.get("category", "")).strip().casefold())
        if cat is not None and 0 <= i < n:
            out[i] = cat
    return out


def _first_json_object(raw: str):
    try:
        return json.loads(raw)
    except ValueError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None

=== End: automation/lib/categorize.py ===

=== File: ROADMAP.md ===
# Family Inc. — Roadmap & forward lane contracts

*Spec **ahead** of build. This is the one place the next things are sequenced and contracted before they are written — the deliberate counterweight to a build that runs ahead of its spec. v1.0 · 2026-06-20.*

*Companions: `SPEC.md` (what the system **is**, present tense) · `BACKLOG.md` (status: shipped / in-flight / gated / frozen) · `ENGINEERING.md` · `DESIGN.md`. **Status lives only in `BACKLOG.md`** — this doc holds the **plan** (the sequence) and the **forward contracts** (what each lane must do before it is built). When a lane ships, its contract graduates into `SPEC.md` and its status into `BACKLOG.md`; the entry here is then struck.*

*Generated from the 2026-06-20 audit + roadmap pass (50 verified drift findings → reconciliation; a value/risk/dependency judge panel → this sequence; per-lane spec-ahead drafts → the contracts below). The four PO calls of 2026-06-20 are baked in: GAP-7 → **fix (fail loud)** · reviewer default → **code flipped to DeepSeek** · the three phantom DESIGN components → **removed** · spec-ahead → **this doc**.*

---

## 1. The next lane (recommended)

> ✅ **Shipped 2026-06-23** — `.github/workflows/tests.yml` (pytest gate + `lib/pii.py` repo-wide leak guard + `config.js` smoke), **421 green**, merged to `main` (`9bf50cb`). The first Actions run was red — `astral-sh/setup-uv@v8` is unresolvable (no floating major past v7) — pinned `@v7` (`5168c6d`); see `BACKLOG.md`. **Two deviations from the sketch below, by design:** the leak guard is a **pytest, not a grep step** (single-sources its patterns with `test_seed_safety.py` + rides `deploy.sh`), and the job runs on the **whole tree with no path filter** (a path-filtered run would let a PII paste in docs/config bypass the guard). **The now-next lane is GAP-7** (§2 rank 2). The original rationale is kept below for the record.

**A pre-merge CI gate — and bundle two cheaper, higher-irreversibility wins into the same job.**

The hermetic 390-test suite (~2.6s) runs today **only** inside `deploy/deploy.sh` on the appliance. Nothing runs it on push/PR, so a red commit can sit on `main` and silently keep the box from reaching HEAD during the mandated 30-day boring hold. The gate is the meta-protection that makes every later fix in §3 safe to land — and it needs no live data, has zero guardrail surface, and fits the light 06-20→06-26 window.

Bundle (the audit critic's additions — same S-effort window, both currently un-automated):
1. **pytest job** — GitHub Actions, `uv run --frozen pytest -q` on push + PR to `main`, path-filtered to `automation/**` + `tests/**`. Mirror `.github/workflows/pages.yml`'s shape.
2. **Secret/PII-leak guard** — the "public-portfolio-safe by construction" guardrail (`CLAUDE.md`) has **zero** automation today; one slip is irreversible in git history. A grep step that fails on phone patterns, `@s.whatsapp.net` JIDs, or ILS-amount-shaped values in tracked files. Pairs with the existing `tests/test_seed_safety.py`.
3. **Dashboard `config.js` smoke** — `pages.yml` generates `config.js` from Actions secrets and is the real deploy path for the most-frequently-shipped artifact, yet has no pre-merge validation. A JS syntax/lint + "`config.example.js` still applies" check in the same job.

**First steps:** branch `ci/test-gate` → add `.github/workflows/tests.yml` (pytest + leak-grep + config-smoke) → confirm green locally (390/390) → PR → watch Actions go green. No `deploy.sh` change, no box contact. Then take **GAP-7** immediately after (rank 2), in the same window.

---

## 2. The sequence

Ranked by *fits-the-window-and-clears-blockers*, then value-per-effort. The window **now → ~06-26** is light (finance acceptance is gated on ≥1 week of live data + Shanee's budget-vocab migration), so it is a reconciliation/hardening slot, not a build-features slot. v1 holds boring/stable until ~07-13 (30 days from `v1-live`).

| # | Lane | Value | Effort | Risk | Window |
|---|---|---|---|---|---|
| 1 | **CI gate + PII-leak guard + config smoke** — ✅ shipped 06-23 (merged) | high | S | low | ✅ done |
| 2 | **GAP-7 Hebcal fail-loud** (decided: fix) | high | S | low | now → 06-26 |
| 3 | **Reviewer/provider canon** (done this session; verify) | med | S | low | now → 06-26 |
| 4 | **DESIGN reconcile** (done this session: 3 components removed) | high | S | low | now → 06-26 |
| 5 | **Lane C dashboard write-contract** (col-D format + header guard) — ✅ shipped 06-26 | high | M | med | ✅ done |
| 6 | **uptime-ping** (healthchecks.io dead-man) | high | S | low | now → 06-26 |
| 7 | **Box-side verification** of the live claims — ✅ done 06-23 (VPS hour) | high | S | low | ✅ done |
| 8 | **stale-digest → briefing system-health line** | med | S | low | now → 06-26 |
| 9 | **Lane B: JSONL rotation** (GAP-3) | med | M | low | now → 06-26 |
| 10 | **Lane E correctness remainders** (batch under the new gate) | med | M | low | now → 06-26 |
| 11 | **M6.3/M6.4 acceptance** (classifier-accuracy run + vocab migration + external review) | high | M | low | after 06-26 |
| 12 | **classifier-fp-metric** (human-mark channel) | med | M | low | after 06-26 |
| 13 | **Bridge scope-guard harness** (bridge-node#2) — *hard prereq to reply-parsing* | med | M | low | after 06-26 |
| 14 | **reply-parsing** (done/snooze via WhatsApp) | high | L | med | later v1.1 (post-hold) |
| 15 | **inbox-trigger** (inotify, sub-hour critical latency) | med | M | med | later v1.1 (post-hold) |
| 16 | **apify-cap** (≤₪120/mo result-counter) | low | M | low | later v1.1 |
| 17 | **calendar-connectors** (decomposed; Hebrew-string pass pullable early) | high | XL | high | later v1.1 (majors) |
| 18 | **v3-today-redesign** (decided 06-25; §3.8) — Today-surface UI rebuild | high | L | med | v1.1 — window is a PO call (now vs post-hold) |
| — | **big-charge-alert** (>₪500) | med | S | med | **frozen** — joint PO call |
| — | **ai-briefing** (LLM five-scene) | med | L | high | **frozen** — joint Shanee privacy call |
| — | **GCal/iCloud auto-ingest** | high | XL | high | **frozen** — credential-storage amendment |

**Where the lenses disagreed (resolved):** value-first opened on GAP-7 (cheapest family-felt fix); risk + dependency opened on the CI gate. Resolved **gate-first, GAP-7 immediately after** — same window, and GAP-7 ships *with* a regression test the new gate then enforces. Reply-parsing: value-first ranked it higher; risk/dependency pushed it past the bridge harness because it mutates two guardrail-sensitive seams (the budget chokepoint + the Sheet write path) — risk/dependency won.

---

## 3. Forward lane contracts

*Near-future tense. Each lane states its scope, behaviour contract, data touchpoints (additive-only), policy interactions, acceptance bar, dependencies, and the PO calls it still owes. Guardrails that must hold for every lane: no money movement · the outbox (`lib/outbox.py`) is the sole alert path · alert budget 2/day (criticals bypass, briefings exempt) · additive-only schema · no PII in committed files · two-adults-only · partner-symmetric, no scoring · no kid UI · boring tech.*

### 3.0 v1-hardening (lanes 1–10) — the pre-v1.1 stabilization bundle

The now→06-26 work. Each item is small, low-risk, needs no new live data, and either protects the dev loop or fixes a live correctness/honesty gap.

- **CI gate + leak guard + config smoke (lane 1)** — ✅ **built 2026-06-22** (status in `BACKLOG.md`; lands on push). `.github/workflows/tests.yml` runs the hermetic suite on push/PR to `main`. Acceptance met locally (421 green): a red commit can't merge; the PII guard (`tests/test_repo_pii_guard.py` + `lib/pii.py`) fails on a planted phone/JID/amount; the `config.js` smoke fails on a drifted template. **Two deviations from the §1 sketch, by design:** the leak guard is a **pytest, not a grep step** (single-sources its patterns with the seed guard + rides `deploy.sh` on the box), and the job runs on the **whole tree with no path filter** (a path-filtered run would let a PII paste outside `automation/**` bypass the guard). *PO call resolved: gate added.* **Shipped 2026-06-23** — first Actions run red (`setup-uv@v8` unresolvable → pinned `@v7`, `5168c6d`), then merged (`9bf50cb`); contract closed.
- **GAP-7 Hebcal fail-loud (lane 2)** — **decided fix.** `hebcal_client` returns `{_stub:true}` on fetch failure; today `daily_digest._hebcal_line` (and the Shabbat `shabbat_times` path — the higher-stakes weekly one) render that as **silence**, indistinguishable from a genuine no-chag day. Contract: on `_stub`, surface a short Hebrew "candle times unavailable" line (copy = Shanee) instead of silence, per the §3.6 clarification landed this session (time-critical data fails loud). Ships with a regression test. Policy: rides the budget-exempt `kind=briefing` digest, no new alert path. *Open: exact Hebrew string (Shanee); confirm both the Friday Shabbat and the erev-chag paths get the line.*
- **Reviewer/provider canon (lane 3)** — **done this session:** `review.py --provider` default flipped to `deepseek` so code matches the "DeepSeek default" canon; ollama stays the keyless local fallback via `--provider ollama`. Consequence: a bare `review.py` now needs `DEEPSEEK_API_KEY` (always present when the operator runs a gate). The runtime classifier + summarizer already run on DeepSeek — the canon is now consistent across all three. Verify before the 06-26 milestone gate fires.
- **DESIGN reconcile (lane 4)** — **done this session:** the progress arc, connection pill, and skeleton/shimmer loading — documented but never built — are **removed** from `DESIGN.md` (components, IA, states, acceptance, smoke checklist). The real stale-data badge + the single-signal Today status pill are now documented as-built. No code change; the dashboard never had these.
- **Lane C dashboard write-contract (lane 5)** — ✅ **shipped 2026-06-26 → graduated to SPEC §6.1/§7.6/§8.5.** PO call (2026-06-26): keep col D a real Sheets **date** cell (human-friendly DD/MM entry + the col-K/L Days-Until formulas keep working) and make the **read** robust rather than forcing ISO-text storage — the 06-25 "ISO everywhere" headline was re-confirmed once tracing showed `USER_ENTERED` coerces an ISO write back into the locale render anyway. Delivered: (a) both write surfaces now emit the **ISO literal** (the engine's `encode_value` joined the dashboard — Sheets parses ISO locale-unambiguously, where DD/MM would misparse under any other locale); (b) the dashboard's `parseDate` reads ISO + the he-IL DD/MM·DD.MM render (the machine M/N/O ISO-T *stamps* untouched — only col D was the bug); (c) the JS write surface resolves columns by **header name** and **pauses writes on header drift**, mirroring the engine's §7.1 guard. Acceptance: the parseDate round-trip cases + airplane-mode reverify (DESIGN §9 item 4 / new item 15). **Unblocks V3.3** (absolute snooze now round-trips: a future col-D clears OVERDUE).
- **uptime-ping (lane 6)** — see §3.5.
- **Box-side verification (lane 7)** — a one-time PO read confirming the asserted-live-but-unverifiable-from-repo facts before the 06-26 gate treats them as settled: `git` SHA of the box vs origin HEAD; `journalctl -u family-finance.service` for the 98-row ingest + dedup counters; the live `Finance-Budget` tab (J1 header, SUMIFS machine cells, non-zero actuals); `gh run list --workflow=pages.yml` green. **Output is a confirmation, not a commit.** Pairs with a standing follow-on: have the box log its git SHA into a line the weekly briefing surfaces, so "committed ≠ deployed" becomes invisibly checkable. **✅ Done 2026-06-23 (the VPS hour):** a 36-check read-only sweep found the system healthy and caught + fixed a 3-day-stale box (deployed to HEAD `9bf50cb`), a down finance scrape (lib bumped 6.7.3→6.7.8), and a ~77%-blank categorization gap (→ M6.4); findings in `BACKLOG.md`. The "box logs its git SHA into the weekly briefing" follow-on remains open.
- **stale-digest → briefing line (lane 8)** — see §3.4.
- **Lane B JSONL rotation (lane 9)** — append-only logs (`inbox/replies/whatsapp_sent/digest_pending.jsonl`) grow unbounded; reconcile + the classifier scan them every run. Contract: size/age rotation that **preserves the <48h reconcile horizon** (§7.5). Additive, hermetic. *Open: retain how many rotated files; rotate on size or age (Adar ops call).*
- **Lane E correctness remainders (lane 10)** — bounded batch under the new gate so the new tests are load-bearing: digest >30d flag, `derive_rule`, the OVERDUE cooldown boundary test (exactly 3 days — Brief 2 reminders-engine#3, currently untested), `reply_handler` stub flags, the property-apify test. Also fold in **Brief 2 reminders-engine#1** (now closed by the SPEC §8.4 reconciliation — no `rem-` id is emitted).

### 3.1 reply-parsing — done/snooze via WhatsApp

- **Scope.** Adult 1:1 WhatsApp replies (`done` / `+Nd` / `mute` / `?`) act on the `Reminders` tab. *Not:* free-text NLU, group replies, or any sender beyond the two adult JIDs.
- **Contract.** The bridge already logs 1:1 replies (no ack — B1) to `replies.jsonl`. Consume them: port `reply_handler.py`'s writes from `openpyxl` to the header-validated `lib/sheet` (never the parked openpyxl path); fix LID-addressing (`msg.key.remoteJidAlt`) so adult replies aren't dropped; reinstate the single reply-footer line; act only on rows present in the most recent digest snapshot for that recipient (anything else → "reply ? for the current list").
- **Data.** `Reminders` writes obey the §6.1 tombstone write contract, sender-attributed.
- **Policy — the central design point.** A solicited ack must **not** consume the unsolicited 2/day budget. The parked code defaults acks to `kind="alert"`, which the outbox **suppresses** under the cap — so a user's own confirmed action could silently vanish on a busy day. **Required:** a new outbox `kind="ack"` — budget-exempt and quiet-hours-exempt (the user just messaged; an immediate confirmation isn't an interruption). This is a §7.5 contract change → milestone review.
- **Acceptance.** A `done` reply marks the row done + recurrence-bumps; an ack returns within seconds, off-budget, only to the replier; an unknown JID is still dropped; the bridge scope-guard harness (lane 13) is green first.
- **Dependencies.** Hard-blocked behind lane 13 (bridge scope-guard harness) — reply-parsing expands the inbound 1:1 surface. Post the 30-day hold.
- **Open PO calls.** `kind="ack"` confirmed? · ack visible to both adults or only the replier (lean: replier; shared completion shows in dashboard/briefing)? · does `mute` truly suppress firing for N days (needs an engine mechanism) or is it just a label?

### 3.2 ai-briefing — LLM five-scene narrative (FROZEN until a privacy call)

- **Scope.** An LLM-written five-scene opener (the week's spend · a kids' moment · next week's three things · a goal line · a contract heads-up) layered over the existing deterministic 8-section template, which stays the **verbatim fallback**.
- **Contract.** Openers-only (recommended); the deterministic template renders first and is always the fallback if the LLM is down or the privacy gate is unmet.
- **Policy — the gate.** This is the **single largest guardrail surface in the pool**: it sends whole-Sheet context (incl. finance, kids' health) to the configured provider — strictly broader than today's §8.6 "description+amount only" finance gap-fill. Requires a **joint Shanee privacy call** *and* a content-review gate (which fields are redacted before send). Provider canon (lane 3) is a hard prerequisite — sending finance to an ambiguous provider is the failure mode. Stays `kind=briefing`; no new alert path.
- **Acceptance.** A real week reviewed before go-live; the deterministic fallback proven; privacy + content-review signed off.
- **Open PO calls.** Facts-only bounded summary acceptable to Shanee? · kids'-moment source (kid-keyword rows vs an additive kid-tag column)? · voice/personality? · re-run determinism (accept wording drift vs pin a seed)?

### 3.3 inbox-trigger — inotify sub-hour critical latency

- **Scope.** An inotify watcher on `inbox.jsonl` invokes the existing summarizer within seconds of a new group message, so critical-safety keywords fire sub-hour — **without** touching the hourly digest cadence or adding a second classifier path.
- **Contract.** `--critical-only` mode: classify the new line; on `kind=critical`, dispatch via the existing `dispatch_alert → queue()` path; write **zero** Sheet rows (the hourly run stays the single writer of record). Debounce ~10–15s to coalesce bursts.
- **Policy.** The outbox stays the sole alert path; only `kind=critical` travels this path and criticals already bypass the budget by spec — no `alert` slot spent, no new bypass.
- **Acceptance.** A planted critical fires within the debounce+poll window; a non-critical does nothing until the hourly run; no duplicate Sheet rows.
- **Dependencies.** A new always-on watcher = a new silent-failure surface → pair with the dead-man ping (§3.5) + JSONL rotation. Defer past the 30-day hold.
- **Open PO calls.** Debounce window? · critical-only scope (recommend yes) vs also the digest-only "⚠ NEEDS A LOOK" block?

### 3.4 classifier-fp-metric + stale-digest line — measured quality & visible degradation

- **classifier-fp-metric.** One **additive** `Review` column on `WhatsApp_Inbox`, marked from the dashboard, turning the weekly accuracy pass from a by-eye read into a measured ALERT-tier FP rate against the <1/week bar. No alert path (the only consumer is the budget-exempt weekly briefing). Best **after** the first 06-26 accuracy run gives a baseline. *Open: FP-only mark vs full reviewed-coverage; where the mark lives (inline vs a weekly review screen); does the number ever auto-narrow patterns (recommend: stays a human edit, §7.3).*
- **stale-digest → briefing line (lane 8).** GAP-2 already drops a digest unconfirmed past 48h and re-fires its reminders (safe), but the drop is only a log line — a persistently-failing bridge is invisible to the adults. Extend the weekly briefing's existing system-health/self-report section with the stale-drop count (budget-exempt, additive, no new alert path). The rejected "stamp-anyway" tier stays rejected (it would reintroduce silent loss). *Open: copy/tone (Shanee); threshold ≥1 vs ≥2; confirm `stale-dropped` replaces the reconcile `queued-stale` line to avoid double-counting.*

### 3.5 uptime-ping — external dead-man

- **Scope.** A healthchecks.io dead-man's switch that pages the **operator** out-of-band when the whole VPS goes dark — closing the one failure §9 still calls silent (a dead box pages no one, because the email fallback assumes the box is alive, and the design deliberately makes silence read as a calm day).
- **Contract.** The 07:30 digest run pings a healthchecks.io URL on success; a missed ping past a grace window pages the operator. Optionally a finer ~30–60min bridge-liveness ping as an additive follow-on.
- **Policy — the one named tension.** The "outbox is the sole alert path" guardrail governs **household** alerts to the two adults; this is an **operator** page emitted off-box by healthchecks.io. It does not route a family message outside the outbox — the guardrail's intent holds.
- **Acceptance.** Killing the box's networking pages the operator within grace; a normal day never pages.
- **Open PO calls.** Which checks ship in v1.1 (digest-daily first)? · grace window? · should a *recovered* briefing also carry an in-band "system was down N hours" line (a separate small lane)?

### 3.6 apify-cap — monthly cost backstop

- **Scope.** A durable monthly result-counter that hard-stops the Apify property secondary before billed results cross the §11 ≤₪120/mo ceiling — converting today's structurally-implied bound (per-search/per-day + item caps) into an enforced one, with the month's burn in the weekly briefing.
- **Contract.** Persist `{month, count}` (or projected-₪ at a conservative per-result rate); at the cap, hard-stop to primary-only for the rest of the month (degrade-quiet) + a budget-exempt briefing line. No alert.
- **Policy.** No new credentialed surface (an integer + a config rate, not an invoice read); outbox untouched.
- **Open PO calls.** Per-result ₪ rate to encode? · enforce on projected-₪ or raw count? · accept that a capped month may miss blocked-portal listings until rollover?

### 3.7 finance-cards-unfreeze — Cal **shipped 2026-06-23**; remaining cards follow the same path

**✅ Graduated into SPEC §12.2 / BACKLOG M6.5.** Cal (Visa) is live — the `--auth` device-trust path (built-but-dormant since 06-19) was exercised: a one-time headed login under xvfb + x11vnc over an SSH tunnel, then daily **headless** (first import 103 txns, ~90% categorized). The "config-only activation" held — a `bank_creds.json` `cal` block + the `--auth cal` login, no code change — **except** one addition the spec-ahead missed: a **`Card Settlement`** exclusion rule, because Cal is *immediate-debit* (its spend also lands merchant-less on the Mizrahi statement, so the mirror must be excluded or the spend double-counts). **Remaining cards** follow this now-proven path, but the `--auth` step is **only for a card on a new portal**: a card on an already-connected login rides the existing scrape, mirror-token-only. **Shanee's debit card (worked 2026-06-23) is the no-auth case** — a Cal-cleared immediate-debit card on the connected Cal login, so its only change was the `רכישה בכרטיס דביט` `Card Settlement` mirror token + flipping the morning's over-match guard (which had assumed it needed its own auth). The other Visa-debit lines (`ויזה-דביט`) still need each source confirmed before a mirror.

- **Open PO calls (carried to M6.5).** Per-card `Owner` default? · daily vs 2–3×/week cadence (re-challenge noise)? · does a card change the >35d stale-import expectation (a card may legitimately have no charges for a month)?

### 3.8 v3-today-redesign — rebuild the dashboard Today surface

**Decided 2026-06-25.** A visual + interaction evolution of the **Today** surface, from a hi-fi prototype handoff put through an 8-dimension adversarial design review; 8 calls co-signed (Adar + Shanee). Full decision record + design tokens in `V3_RECONCILE.md`; the **file-level build plan + 4 hard blockers + open PO calls in `V3_BUILD_PLAN.md`** (synthesized from a 13-agent planning pass, 2026-06-25); full pixel spec in the handoff (`~/Downloads/Family Inc Repo Redesign.zip`, **currently missing from the box** — V3.4–V3.6 geometry builds to the written contract until it's restored). Same data philosophy (calm tech, Today-first, Hebrew/RTL); new layout + two net-new components.

- **Scope.** The Today home surface only. A **system-wide cool retone** (tokens live on `:root`, so Sunday/Settings inherit colors but keep their layouts) + IBM Plex Mono for all numerals. New/changed components: a 3-tier status pill (red/amber/sage **+ count**), a parent-to-parent **love-note**, a 3-day scroll-snap **calendar**, a select-to-act **desk**, a **coming-up** strip (WEEK-OUT/MONTH-OUT), a cross-domain **timeline** (exponential 1wk→5yr zoom + category filter), and one data-driven **bottom-sheet** drawer replacing the inline accordions. *Not:* the WhatsApp surface; Sunday's or Settings' layouts.
- **Contract — the 8 calls (D1–D8).** D1 a coming-up strip homes the WEEK-OUT tier (replaces v1 "Next 7 days"). D2 love-notes (Data). D3 account-switch = real Google re-auth, never a label flip. D4 snooze writes an **absolute** Due date. D5 the pill keeps a **red** OVERDUE tier + count. D6 the Car drawer stays. D7 drop the prototype's notif-toggles / bank-connect / export from Settings. D8 goal **tile** = progress bar, **drawer** keeps the bright-line viz; retone system-wide; mono widened to all numerals.
- **Data touchpoints (additive-only).** (a) **Love-notes — appliance-local, not the Sheet:** one ephemeral note per direction (text|voice), 24h-or-on-replace expiry, over a small authenticated dashboard→appliance endpoint — the **first dashboard datum that is neither the Sheet nor the outbox**. The voice memo is the **bounded unfreeze** of the §4 voice-capture frozen lane (≤24h, appliance-local, the one stored-media exception). (b) **Snooze → col D as an absolute date** — settle the col-D format in Lane C (§2 rank 5) first so the engine round-trips it; an absolute future date clears OVERDUE cleanly (which +N could not on an already-overdue row). (c) **Timeline** needs a milestone-inclusion rule + a Domain→{finance,health,car,edu} map; no new tab.
- **Policy.** Love-notes have **no push** → no alert-budget spend, no new channel to phones (the note shows on the recipient's next open); the outbox stays the sole alert path. Two-adults-only, parents-only (no kid UI), partner-symmetric (each sends/receives). Switch-account keeps `LastDoneBy` truthful via the live OAuth session (both adults are editors on the one sheet + UserMap entries).
- **Acceptance.** Each slice ships tests-green and its DESIGN/SPEC sections **graduate to present-tense** as it lands. The DESIGN §9 smoke passes on the rebuilt Today; AA holds on both surfaces (the prototype's amber pill + muted text failed → the darkened `--amber #8A5E12` / `--muted #5F6878` are the fixes); RTL + EN-fallback intact (every new chrome string in `STRINGS` he+en); love-note round-trips with the 24h sweep; an overdue row snoozed to a future date leaves OVERDUE.
- **Build sequence.** V3.1 token retone → V3.2 scaffold + 3-tier pill → V3.3 desk + coming-up + absolute snooze → V3.4 calendar → V3.5 portfolios + bottom-sheet → V3.6 timeline → V3.7 love-notes (text) → **✅ V3.8 i18n + a11y + Settings (shipped 2026-06-26: `data-i18n-aria` walker · global `:focus-visible` + consolidated reduced-motion · WCAG-AA contrast test · real switch-account re-auth, no revoke · D7 · token-alias endgame · `--blue` dark value · cheap pure-fn JS tests)** → **V3.9 milestone review (`review.py`) + close** (the only remaining slice).
- **Dependencies.** Lane C (§2 rank 5) first (settles col-D). The love-note endpoint is the one appliance-side (server) piece. A full UI rebuild is **L–XL** — see the window call below.
- **PO calls — the 4 build blockers RESOLVED 2026-06-25** (detail + consequences in `V3_BUILD_PLAN.md` §0): **window → build the whole lane now** (V3.3+ still waits on Lane C as a real dependency, not a window choice); **col-D format → ISO `YYYY-MM-DD`** everywhere (`parseDate` stays as-is; both write surfaces stay ISO via Lane C's helper); **days 3–7 calendar gap → the coming-up strip carries calendar events** (3–7d, 📆-tagged); **love-note exposure → Cloudflare Tunnel** (+ a 4th `pages.yml` sed / `DASHBOARD_LOVENOTE_URL` secret / 4th config-smoke anchor). **Resolved since (folded into SPEC):** Timeline milestone-inclusion rule + Domain→category map + **Education's only Today home = Timeline** (V3.6, SPEC §7.6); **love-note on-box storage → flat JSON per direction**, **auth → access_token→Google-tokeninfo** (opt-in audience check), **`LOVENOTE_URL` sed-substituted** (4th `pages.yml` sed + smoke anchor) — V3.7 **text** phase landed 2026-06-25 (SPEC §7.7). **Resolved V3.8 (2026-06-26):** `--blue` → **kept as a distinct info token** + given its dark value (calendar event times; the dark-on-dark fix); JS-test-harness → **cheap pure-function node tests now + a tracked deferred harness lane** for the interactive logic (`BACKLOG.md` Deferred — no build step bolted on mid-redesign); account-switch UI → **a Settings button reusing the sign-in flow** (`prompt:'select_account'`, identity = the live OAuth session, **no token-revoke** — the 7-lens review showed revoking drops the shared grant and would sign you out on a same-account re-pick). **Still open:** **love-note voice phase** (the SPEC §4/§7.7 stored-media carve-out — not built) · the **V3.9** close (milestone `review.py` + BACKLOG flip + the whole §3.8 entry struck).

---

## 4. Decisions & open questions carried forward

**Landed this session (2026-06-20):**
- GAP-7 → **fix, fail loud** (§3.6 clarified: time-critical data surfaces an "unavailable" line, never silence). Implementation is lane 2.
- Reviewer/provider canon → **code flipped to DeepSeek default** (`review.py`); ollama is the keyless fallback.
- The three phantom DESIGN components → **removed from the project**.
- Spec-ahead lives here in **ROADMAP.md** (5th canon doc).
- ~30 doc-vs-code drift reconciliations across SPEC/ENGINEERING/DESIGN/README + code one-liners (see git history / `BACKLOG.md`).

**Landed 2026-06-25:**
- **v3 Today redesign decided** — 8 design calls co-signed (Adar + Shanee) after an 8-dimension adversarial review of a hi-fi prototype handoff. Captured as forward lane §3.8 + `V3_RECONCILE.md` (decision record + design tokens). Build not started; **window is an open PO call** (now vs after the boring-hold ~07-13). The first canon fold was mistakenly written against a stale base and discarded (the redesign reviewed while origin raced ahead with M6.5); this is the clean placement.

**Landed 2026-06-26 (finance-acceptance tooling):**
- **Classifier-accuracy PASS THRESHOLD defined** (resolves the open call below). **Summarizer:** accept at **< 1 ALERT-tier FP/week** (`accuracy_review.py`, SPEC §7.3); at/above → narrow the pattern + re-run. **Finance categorizer:** the milestone metric is **coverage** (categorized / budget-eligible), **report-first** — the numeric bar is set from the first live read (candidate ≥90%; Cal ~90%); categorizer *correctness* (a true FP rate) is **coverage's** distinct, deferred sibling (rank 12). Tooling: the one-time **re-categorize backfill** (`finance_recategorize.py`) + the read-only **coverage** surface (`finance_coverage.py` / `lib/finance_coverage.py`), hermetic + tested (481 green); SPEC §12.2 + `deploy/FINANCE.md §6/§7` graduated. Box-run is the only remaining step.

**Open PO calls before / at the 06-26 gate:**
- ~~Define the classifier-accuracy PASS THRESHOLD~~ **done 2026-06-26** (above).
- **Box-side verification** (lane 7) — ✅ done 06-23.
- Add the CI gate, or document a deliberate no-CI choice — ✅ done 06-23 (lane 1).

**Standing principle reaffirmed:** anomaly/subscription detection stays **killed**; `big-charge-alert` is its only bounded re-entry and needs a **joint** PO call + a recurring-payee exclusion (which itself depends on Shanee's budget-vocab migration) + the live finance baseline — it does **not** auto-ride card activation.

=== End: ROADMAP.md ===

=== File: deploy/FINANCE.md ===
# deploy/FINANCE.md — the finance go-live hour (M6.2 + M6.3)

*Runbook = ordered commands. The "why" lives in `SPEC.md` §12.2 and `BACKLOG.md`
(M6); if they disagree, SPEC wins and the disagreement is a bug. This covers the
appliance side of M6 only — the repo half (scraper, ingest, rules engine, budget
formulas) ships and is tested. Everything below runs on the VPS as root / `familyinc`;
git operations stay on the PO's machine.*

Layout recap: `automation/finance/scrape.js` (Node, read-only login → one CSV per
provider) → `automation/finance_ingest.py` (Python, the only Sheet writer). Driven by
`systemd/family-finance.{service,timer}` (06:00 daily, before the 07:25 engine read).
`provision.sh` already ran `npm ci` in `automation/finance/` and enabled the timer — but
the lane is **inert until `bank_creds.json` is placed**, so a clean box is safe.

## 0. Pre-flight (read BEFORE you start)

- **Mizrahi is password-only** → no `--auth` / device-trust step. *But* the portal may force a
  one-time **password change** (or a terms/confirm interstitial) that a headless run can't
  clear — it surfaces as a `TIMEOUT … #/change-pass` scrape error (seen on first go-live,
  2026-06-19). Clear it once by hand in a normal browser (change the password, then update
  `bank_creds.json`), and the headless run works. Do Mizrahi first and prove the whole pipe on
  it alone (§1–§3).
- **Max + Cal re-challenge a fresh browser, and `israeli-bank-scrapers` 6.7.3 has no
  programmatic OTP entry for them** (username+password only — there is no code path to type
  an OTP in). The mechanism is **device-trust persistence**: each provider has a persistent
  Chromium profile (`<finance-dir>/profiles/<provider>`), and a **one-time headed login you
  drive by hand** (`scrape.js --auth <provider>`) clears the challenge once. The portal then
  trusts that profile, so the daily headless run reuses it and is not re-challenged. On the
  headless VPS the headed browser is shown via **xvfb + x11vnc over an SSH tunnel** — the
  full procedure is **§4**. Do the cards there, after Mizrahi proves the pipe.
- **Run everything as `familyinc`** (the unit's user) so the profile the daily run reads is
  owned by the daily run. A profile authorized as `root` is unreadable by the timer.

## 1. Rename the 3 live-Sheet tabs (load-bearing)

In the **live `Family_OS` Google Sheet** (NOT the committed seed), rename the finance
tabs to the standardized full names the code reads:

| Old (as-built short) | New (standardized) |
|---|---|
| `Finance-Accts` | `Finance-Accounts` |
| `Finance-Txns`  | `Finance-Transactions` |
| `Finance-Bdgt`  | `Finance-Budget` |

These exact names are what `automation/lib/config.py` (`FINANCE_*_TAB`) and the dashboard
`config.js` `TABS` read. **Also update the live (gitignored) `dashboard/config.js`** so
`finance_acct/finance_txns/finance_bdgt` use the full names (the template
`config.example.js` already does) — otherwise the Money drawer reads a non-existent tab
after the rename. Renaming a tab preserves its data and formulas.

## 2. Place credentials (Mizrahi only, first)

```bash
# /etc/family-inc/bank_creds.json  (mode 600, owner familyinc)
# Copy deploy/bank_creds.example.json and fill ONLY the mizrahi block to start.
# Read-only portal logins. Omit a provider block to skip it.
sudo install -o familyinc -g familyinc -m 600 /dev/stdin /etc/family-inc/bank_creds.json <<'JSON'
{ "mizrahi": { "username": "…", "password": "…" } }
JSON
```

## 3. Verify the Mizrahi roundtrip (live)

```bash
# Run the oneshot by hand (node scrape → python ingest), then read the logs.
sudo systemctl start family-finance.service
journalctl -u family-finance.service -n 80 --no-pager
ls -l /var/lib/family-inc/finance/        # expect mizrahi_<date>.csv, no _scrape_errors.json
```

Confirm in the Sheet: `Finance-Transactions` gained rows (with `Category`/`Cat-Source`
populated by the rules engine), and `Finance-Accounts` shows Mizrahi with a fresh
`Last Imported`. A re-run must be idempotent (dedup → 0 new). If `_scrape_errors.json`
appears, the run **persisted the good data then failed loud** — read the marker.

## 4. Add the cards (Max + Cal) — one-time device-trust, then daily-headless

Add the `max` and `cal` blocks to `bank_creds.json` (§2). A first **headless** run will
likely fail loud on a device/OTP challenge for a card — that is expected; clear it once with
the headed `--auth` login, which trusts this box's browser profile so the daily run rides it.

**4a — install x11vnc and pause the daily timer (one-time):**

```bash
sudo apt-get install -y x11vnc          # xvfb is already present (property scraper)
sudo systemctl stop family-finance.timer  # so the 06:00 run can't open the same
                                          # profile mid-auth (Chrome SingletonLock).
                                          # Re-armed in §5; Persistent=true catches up.
```

**4b — run the headed login on the box, as `familyinc`, under xvfb.** Both terminals run
as `familyinc` and share a **pinned** xauth cookie, so x11vnc can attach to `:99` while the
display stays access-controlled (no `-ac` — `:99` will be showing a live banking session,
so it must not be open to every local process):

```bash
# Terminal A: headed Chrome on :99; -f pins the xauth cookie to a known path.
sudo -u familyinc xvfb-run -f /tmp/finance-xauth --server-num=99 \
  -s '-screen 0 1280x900x24' \
  node /opt/family-inc/automation/finance/scrape.js --auth max
# Terminal B (give A a second to bring :99 up): same user + pinned cookie, localhost only.
sudo -u familyinc env XAUTHORITY=/tmp/finance-xauth \
  x11vnc -display :99 -auth /tmp/finance-xauth -localhost -rfbport 5900 -nopw -forever
```

**4c — view + drive it from your laptop:**

```bash
ssh -L 5900:localhost:5900 <box>        # tunnel; then open any VNC viewer → localhost:5900
# In the VNC window: log into Max, complete the SMS/OTP "remember this device" step until
# you reach the account dashboard. Then go back to Terminal A and press ENTER to close it.
# (The session auto-closes after 20 min if you don't — just re-run --auth.)
```

> Alternative if you'd rather not run a VNC server: `ssh -X <box>` and run the same
> `sudo -u familyinc … --auth max` with the forwarded `DISPLAY` — the browser renders on
> your laptop, no xvfb/x11vnc. (You must `xauth add` the forwarded cookie for `familyinc`;
> we default to on-box VNC so the trusted browser is the same Chromium/IP as the daily run.)

The trust cookie is now persisted in `<finance-dir>/profiles/max/`. Repeat 4b–4c for `cal`.
Then re-run §3 (`systemctl start family-finance.service`) and confirm both cards land
**headless**. If a card still re-challenges, the trust didn't take — re-run `--auth` for it
(and see §12.2: cadence is the tuning knob — drop noisy cards to 2–3×/week).

> If device-trust ever expires (a card starts re-challenging weeks later), the fix is the
> same one-time `--auth` login — no creds change. A corrupt profile is recoverable by
> `rm -rf <finance-dir>/profiles/<provider>` then re-running `--auth`.

## 5. Enable the timer

`provision.sh` already `enable`d `family-finance.timer`. If you stopped it for the §4 auth,
re-arm it, then confirm it is active and the next fire is sane:

```bash
sudo systemctl start family-finance.timer                 # re-arm if §4a stopped it
sudo systemctl list-timers 'family-finance*' --no-pager   # next ~06:00 Asia/Jerusalem
```

M6.2 closes once a live scrape→Sheet roundtrip is verified on at least Mizrahi.

## 6. M6.3 — install the live budget formulas + close

The `Finance-Budget` actuals reconcile via a **text-prefix wildcard** `SUMIFS` on the
ISO-text `Date` (`<yyyy-mm>&"*"`), NOT a serial `DATE()` window (which reads ₪0 against
RAW-appended text dates). Don't hand-copy them — run the **installer**, which is the
single source of the formula text (`automation/lib/finance_budget.py`, pinned against the
committed seed by `tests/test_finance.py`):

```bash
# As familyinc, with the live Sheet env loaded (FAMILY_INC_SHEET_ID). Preview first.
python3 /opt/family-inc/automation/finance_budget_formulas.py --dry-run
python3 /opt/family-inc/automation/finance_budget_formulas.py            # stamp it
```

It reads the live `Finance-Budget` tab, validates the load-bearing column order (fails
loud on drift), and stamps **only** the machine columns — Actual/Variance/%/YTD/Last-Month
per category, the `I`-helper date tags, and the TOTAL sums — keyed off whatever category
rows the tab has. **A category row's Category and Monthly Target, and every Notes cell,
are never written** (the only Target it writes is the TOTAL row's `=SUM`), so it's
idempotent and re-running after a budget change just re-stamps for the new rows.
*(Re-stamps the current rows; it does not clear machine cells on a row you delete as a
category — clear those by hand.)* Then confirm actuals go **non-zero** on the first
real month (Groceries/Transport/Health).

- **Absent machine columns are auto-titled (hardened 2026-06-20):** the installer
  owns the machine columns (`Actual`/`Variance`/`%`/`YTD`/`J` Last-Month + the `H`/`I`
  helper block), so when a tab simply *lacks* one it **titles the column itself and
  stamps** — no hand-fix. This was the live 2026-06-20 case (the tab predated the M6.4
  block, so it was A–I only with no `J` `Last Month (ILS)`); it's also what a fresh
  budget from Shanee's migration looks like (only `Category`/`Monthly Target` filled).
  What it still **refuses** (fail loud): a *human* header (`Category` / `Monthly
  Target`) missing or renamed, or a machine header holding a *different* value (a real
  column shift). So before a fresh-tab stamp, ensure only the two human headers are
  present and exact — the installer provides the rest. (`deploy/FINANCE.md` was
  briefly amended 2026-06-20 to add `J1` by hand; the hardening superseded that.)
- **No stray-formula risk:** there's no manual copy, so the old "stray Notes-column
  `SUMIFS`" copy artifact can't happen — the installer emits no Notes cell (pinned by
  `test_budget_installer_never_writes_notes_column`).
- **Category-vocab gap (expected, not a bug yet):** the rules engine emits `Dining out`,
  `Health`, … but the budget also has rows `Subscriptions`, `Savings`, `Other` with no
  matching rules category — so those actuals read **₪0** even with perfect ingest. The
  vocab is **PROVISIONAL** pending Shanee's budget migration, which is the vocabulary
  authority. Don't unilaterally rename buckets to close this — it's a PO/Shanee call;
  when she maps them, just re-run the installer.

M6.3 acceptance is the first real **monthly** review (~30 days of live data).

### Budget-vocab migration — exactly what we need from Shanee

Shanee is the **vocabulary authority**: the `Finance-Budget` category list is what the
rules engine must map to (the actuals `SUMIFS` keys on the literal `Category` string, so
a label mismatch reads ₪0). She delivers it by filling **two columns of the live
`Finance-Budget` tab directly** — the installer titles + stamps every machine column
itself, so she touches only:

1. **Column A — `Category`:** the canonical list. Confirm / rename / split / merge / drop
   the provisional 11 the rules engine emits today — **Health, Groceries, Transport,
   Childcare, Utilities, Housing, Dining out, Entertainment, Shopping, Income, Fees**
   (pick a language per label; the briefing + dashboard render the string verbatim).
2. **Column B — `Monthly Target (ILS)`:** a target per category (approximate is fine).
   Drives variance / % / over-budget; a row with no target is skipped by the Money
   section. *(These ₪ values live in the Sheet only — never the repo.)*
3. **The 3 currently-unmapped labels — `Fees`, `Income`, `Shopping`:** the rules emit
   them but no budget row exists yet (held as an allow-list, so their spend reads ₪0).
   For each: **add a row** (give it a target), **remap** the rule to another category, or
   **drop** it.
4. **Where `Income` lives:** it's positive (not spend) — decide a budget row (target =
   expected income) **or** out-of-grid (recommended; the actuals `SUMIFS` negates spend,
   so an income row reads oddly).

Then re-point the rules seed to her exact labels (if renamed), shrink the
`Fees/Income/Shopping` allow-list in `test_rules_vocab_within_budget_categories`, and
re-run the installer (§6) + the backfill (§7). No code from her — only A:B.

## 7. M6.4/M6.5 — re-categorize backfill + coverage (the 06-26 gate)

`finance_ingest` categorizes **new rows only**, so the rows that landed before the
M6.5 `Card Settlement` rule existed stay blank. Apply that rule (and any merchant
the engine now covers) to history with the **one-time backfill**, then read the
**coverage** the milestone accepts on. As `familyinc`, live Sheet env loaded.

```bash
# 1. Baseline coverage (read-only — writes nothing).
python3 /opt/family-inc/automation/finance_coverage.py --write   # → Briefings/<date>_finance_coverage.md

# 2. Preview the backfill (rules-only, no write). Sanity-check: the Card Settlement
#    count should be ~66 (the Cal-mirror lines), and SHUFERSAL/PAZ-type blanks resolve.
python3 /opt/family-inc/automation/finance_recategorize.py --dry-run

# 3. Run it for real (rules + DeepSeek gap-fill; --no-llm for rules-only).
python3 /opt/family-inc/automation/finance_recategorize.py

# 4. Re-read coverage — confirm the lift + that excluded(Card Settlement) jumped.
python3 /opt/family-inc/automation/finance_coverage.py --write
```

The backfill is **idempotent** (touches blank rows only) and **safe to re-run** —
re-run after Shanee's budget-vocab migration re-points the rules, or whenever a new
card's source comes online. Set the **accept bar** from step 4 (report-first;
candidate ≥90% of budget-eligible rows). Coverage is *not* correctness — a true
categorizer FP rate is deferred (`ROADMAP.md` rank 12).

**Summarizer accuracy (the other half of the gate):** run the weekly review over
≥1 week of live classifier output and confirm **< 1 ALERT-tier false positive/week**;
the fix for an over-firing pattern is narrowing it in the group-config seed.

```bash
python3 /opt/family-inc/automation/accuracy_review.py --weeks 1   # → Briefings/<date>_accuracy_review.md
```

## Day-to-day

No digest/finance section by 08:00 → the fail-flag and `journalctl -u family-finance` tell
the story. Code reaches the box only via `deploy.sh`. The lane is silent by design — the
only finance *message* is fail-loud.

=== End: deploy/FINANCE.md ===

=== File: tests/test_finance.py ===
"""Tests for automation/finance_ingest.py (SPEC §12.2, M6.1; D-049/050/051).

Hermetic: a mock per-provider CSV → ingest → a tmp xlsx Sheet (explicit path,
never the live Sheet / committed seed). No banks, no Node, no network — the
Node scraper (scrape.js) is VPS-only and node-checked, not unit-tested.
Covers: CSV → Sheet, Txn-ID dedup + rerun idempotency, balance-only rows,
natural-key hash ids (the provider `identifier` is ignored — non-unique on
Mizrahi), Finance-Accounts upsert (human fields preserved),
fail-loud on missing creds / scrape-error marker, and the seed-safety gate.
"""

import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from automation import finance_ingest as fin
from automation.lib import config as cfg
from automation.lib import sheet

SCRAPE_JS = Path(__file__).resolve().parents[1] / "automation" / "finance" / "scrape.js"

TODAY = date(2026, 6, 17)
NOW = datetime(2026, 6, 17, 6, 0, 0)

CSV = (
    "account,balance,date,identifier,amount,description\n"
    "MIZ-0001,12500.00,2026-06-15,abc123,-432.50,SHUFERSAL DEAL\n"
    "MIZ-0001,12500.00,2026-06-16,,-89.90,SUPERPHARM\n"
    "MIZ-0777,,2026-06-15,,-280.00,PAZ GAS\n"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _csv(tmp_path, text=CSV, name="mizrahi_2026-06-17.csv"):
    d = tmp_path / "stage"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")
    return d


def _sheet(tmp_path, accounts_rows=None):
    """A tmp xlsx with a placeholder tab (so the file loads); optionally a
    pre-seeded Finance-Accounts tab to test upsert-preserves-human-fields."""
    wb = Workbook()
    wb.active.title = "Placeholder"
    if accounts_rows is not None:
        ws = wb.create_sheet(cfg.FINANCE_ACCOUNTS_TAB)
        ws.append(sheet.FINANCE_ACCOUNTS_COLUMNS)
        for r in accounts_rows:
            ws.append(r)
    p = tmp_path / "finance.xlsx"
    wb.save(p)
    return p


def _rows(path, tab):
    wb = load_workbook(path, data_only=True)
    if tab not in wb.sheetnames:
        return []
    return [[c.value for c in row] for row in wb[tab].iter_rows()]


def _col(tab_rows, name):
    """Values under a named column (skips header)."""
    i = tab_rows[0].index(name)
    return [r[i] for r in tab_rows[1:]]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def test_provider_of():
    from pathlib import Path
    assert fin.provider_of(Path("mizrahi_2026-06-17.csv")) == "mizrahi"
    assert fin.provider_of(Path("/var/x/MAX_2026-06-17.csv")) == "max"


def test_txn_id_is_natural_key_hash():
    # The provider identifier is NOT part of the key (Mizrahi reuses it across
    # distinct charges — §12.2). Same natural key → same id; a different natural
    # key (here, a different amount) → a different id. Deterministic.
    h1 = fin.txn_id("2026-06-15", -10, "X", "A")
    h2 = fin.txn_id("2026-06-15", -10, "X", "A")
    h3 = fin.txn_id("2026-06-15", -11, "X", "A")
    assert h1.startswith("h:") and h1 == h2 and h1 != h3


# ---------------------------------------------------------------------------
# CSV → Sheet
# ---------------------------------------------------------------------------
def test_mock_csv_ingests_to_sheet(tmp_path):
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=_csv(tmp_path), sheet_path=sp, today=TODAY, now=NOW)
    assert res.txns_new == 3 and res.accounts == 2 and res.wrote

    txns = _rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)
    assert txns[0] == sheet.FINANCE_TRANSACTIONS_COLUMNS          # header
    assert len(txns) - 1 == 3
    # All Txn-IDs are natural-key hashes — the provider `identifier` (abc123 on
    # the first row) is ignored, since it is not unique per transaction (§12.2).
    assert all(str(t).startswith("h:") for t in _col(txns, "Txn-ID"))
    assert len(set(_col(txns, "Txn-ID"))) == 3          # 3 distinct natural keys
    # M6.4: the on-box rules engine categorizes at ingest (no LLM key in tests
    # → rules only). SHUFERSAL→Groceries, SUPERPHARM→Health, PAZ→Transport.
    cat_by_desc = dict(zip(_col(txns, "Description"), _col(txns, "Category")))
    assert cat_by_desc["SHUFERSAL DEAL"] == "Groceries"
    assert cat_by_desc["SUPERPHARM"] == "Health"
    assert cat_by_desc["PAZ GAS"] == "Transport"
    assert set(_col(txns, "Cat-Source")) == {"rules"}
    assert "abc123" not in _col(txns, "Txn-ID")         # identifier is not the key
    assert -432.5 in _col(txns, "Amount (ILS)")

    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    assert len(accts) - 1 == 2
    miz1 = [r for r in accts[1:] if r[0] == "MIZ-0001"][0]
    assert miz1[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Type")] == "bank"
    assert miz1[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Balance Snapshot")] == 12500.0
    assert miz1[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Last Imported")] == "2026-06-17"
    assert miz1[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Last 4")] == "0001"


def test_dedup_rerun_is_idempotent(tmp_path):
    sp = _sheet(tmp_path)
    d = _csv(tmp_path)
    fin.run(csv_dir=d, sheet_path=sp, today=TODAY, now=NOW)
    res2 = fin.run(csv_dir=d, sheet_path=sp, today=TODAY, now=NOW)
    assert res2.txns_new == 0 and res2.txns_seen == 3
    assert len(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)) - 1 == 3   # no dupes
    assert len(_rows(sp, cfg.FINANCE_ACCOUNTS_TAB)) - 1 == 2       # upsert, not append


def test_natural_key_collision_drops_second_charge_as_phantom_dup(tmp_path):
    """Accepted floor (finance_ingest.py txn_id docstring): two genuinely distinct
    same-day charges with an identical account+amount+description hash to one
    Txn-ID, so the dedup drops the second as a phantom dup. This LOCKS that
    behavior (it is silent data loss) — recovering both needs a richer key + a PO
    call. Rare for a bank; re-verify per card before trusting a provider field."""
    text = ("account,balance,date,identifier,amount,description\n"
            "MIZ-0001,9000,2026-06-15,,-12.00,COFFEE KIOSK\n"
            "MIZ-0001,9000,2026-06-15,,-12.00,COFFEE KIOSK\n")   # two real ₪12 coffees
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=_csv(tmp_path, text), sheet_path=sp, today=TODAY, now=NOW)
    # finance-ingest#3: the in-batch collision is a distinct counter, NOT
    # mislabeled "already on the tab" (txns_seen).
    assert res.txns_new == 1 and res.txns_phantom_dup == 1 and res.txns_seen == 0
    assert len(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)) - 1 == 1


def test_distinct_identifiers_do_not_rescue_same_natural_key(tmp_path):
    """Inverts the pre-2026-06-19 behavior: distinct provider identifiers no
    longer keep two same-natural-key rows apart — `identifier` is out of the key
    (§12.2), so the second still drops. We stopped trusting identifier because
    Mizrahi reuses it; this same-day-collision merge is the symmetric cost."""
    text = ("account,balance,date,identifier,amount,description\n"
            "MIZ-0001,9000,2026-06-15,txn-a,-12.00,COFFEE KIOSK\n"
            "MIZ-0001,9000,2026-06-15,txn-b,-12.00,COFFEE KIOSK\n")
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=_csv(tmp_path, text), sheet_path=sp, today=TODAY, now=NOW)
    assert res.txns_new == 1 and res.txns_phantom_dup == 1
    assert all(str(t).startswith("h:")
               for t in _col(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB), "Txn-ID"))


def test_reused_identifier_across_distinct_charges_keeps_all(tmp_path):
    """Regression for the 2026-06-19 live data-loss bug: israeli-bank-scrapers
    hands Mizrahi a NON-unique identifier (one id shared across many distinct
    charges). The old `if identifier: return identifier` collapsed 96 real rows
    to 26 on the live tab. With the natural-key Txn-ID, distinct charges that
    happen to share an identifier are all kept (would FAIL on the old code:
    txns_new == 1, phantom_dup == 2)."""
    text = ("account,balance,date,identifier,amount,description\n"
            "MIZ-0001,9000,2026-06-10,dup-ref,-12.00,COFFEE\n"
            "MIZ-0001,9000,2026-06-11,dup-ref,-50.00,GROCERY\n"
            "MIZ-0001,9000,2026-06-12,dup-ref,-9.90,BAKERY\n")   # 3 distinct, 1 id
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=_csv(tmp_path, text), sheet_path=sp, today=TODAY, now=NOW)
    assert res.txns_new == 3 and res.txns_phantom_dup == 0       # all kept, no false dup
    assert len(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)) - 1 == 3


def test_balance_only_row_feeds_account_not_txn(tmp_path):
    sp = _sheet(tmp_path)
    text = ("account,balance,date,identifier,amount,description\n"
            "MIZ-0001,9000,2026-06-15,,-50,COFFEE\n"
            "SAV-0002,40000,,,,\n")          # balance-only: no date/amount
    res = fin.run(csv_dir=_csv(tmp_path, text), sheet_path=sp, today=TODAY, now=NOW)
    assert res.txns_new == 1 and res.accounts == 2
    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    sav = [r for r in accts[1:] if r[0] == "SAV-0002"][0]
    assert sav[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Balance Snapshot")] == 40000
    assert "SAV-0002" not in _col(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB), "Account")


def test_upsert_preserves_human_fields(tmp_path):
    # Pre-seed MIZ-0001 with human-edited Owner/Notes + a stale balance.
    pre = ["MIZ-0001", "bank", "mizrahi", "0001", "Adar", "ILS",
           "2026-01-01", 999, "my main account"]
    sp = _sheet(tmp_path, accounts_rows=[pre])
    fin.run(csv_dir=_csv(tmp_path), sheet_path=sp, today=TODAY, now=NOW)
    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    miz1 = [r for r in accts[1:] if r[0] == "MIZ-0001"][0]
    C = sheet.FINANCE_ACCOUNTS_COLUMNS
    assert miz1[C.index("Owner")] == "Adar"             # human field preserved
    assert miz1[C.index("Notes")] == "my main account"  # preserved
    assert miz1[C.index("Balance Snapshot")] == 12500.0  # refreshed
    assert miz1[C.index("Last Imported")] == "2026-06-17"  # refreshed
    # MIZ-0777 is new → appended (so 2 account rows total, no duplicate MIZ-0001)
    assert len(accts) - 1 == 2


# ---------------------------------------------------------------------------
# Fail-loud + seed-safety
# ---------------------------------------------------------------------------
def test_fail_loud_when_no_csvs_on_live(tmp_path):
    empty = tmp_path / "stage"
    empty.mkdir()
    with pytest.raises(fin.FinanceError, match="no finance CSVs"):
        fin.run(csv_dir=empty, today=TODAY, now=NOW, live_override=True)


def test_mock_mode_when_no_csvs_and_not_live(tmp_path):
    empty = tmp_path / "stage"
    empty.mkdir()
    res = fin.run(csv_dir=empty, today=TODAY, now=NOW, live_override=False)
    assert res.is_mock and not res.wrote


def test_scrape_error_marker_fails_loud_after_persisting(tmp_path):
    sp = _sheet(tmp_path)
    d = _csv(tmp_path)
    (d / fin.SCRAPE_ERRORS_FILE).write_text(
        '{"errors": [{"provider": "max", "error": "OTP re-challenge"}]}',
        encoding="utf-8")
    with pytest.raises(fin.FinanceError, match="OTP re-challenge"):
        fin.run(csv_dir=d, sheet_path=sp, today=TODAY, now=NOW)
    # the good CSV's transactions were persisted BEFORE the raise (no data lost)
    assert len(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)) - 1 == 3


def test_not_live_no_path_writes_nothing(tmp_path):
    # csvs present, but no live backend and no explicit path → parse, write
    # nothing (never touches the committed seed — D-038/M2 invariant).
    res = fin.run(csv_dir=_csv(tmp_path), today=TODAY, now=NOW, live_override=False)
    assert res.txns_new == 3 and not res.wrote


def test_dry_run_writes_nothing(tmp_path):
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=_csv(tmp_path), sheet_path=sp, today=TODAY, now=NOW,
                  dry_run=True)
    assert not res.wrote
    assert _rows(sp, cfg.FINANCE_TRANSACTIONS_TAB) == []   # tab never created


def test_amount_with_commas_and_iso_date(tmp_path):
    sp = _sheet(tmp_path)
    text = ("account,balance,date,identifier,amount,description\n"
            'MIZ-0001,"1,234.50",2026-06-15,,"-1,200.00",RENT\n')
    fin.run(csv_dir=_csv(tmp_path, text), sheet_path=sp, today=TODAY, now=NOW)
    txns = _rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)
    assert -1200.0 in _col(txns, "Amount (ILS)")
    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    assert accts[1][sheet.FINANCE_ACCOUNTS_COLUMNS.index("Balance Snapshot")] == 1234.5


# ---------------------------------------------------------------------------
# lib/sheet.upsert_rows — direct unit (seed-safety gate)
# ---------------------------------------------------------------------------
def test_upsert_rows_skips_without_live_or_path(tmp_path, monkeypatch):
    # No path + not live → must not write anything (won't touch the seed).
    monkeypatch.setattr(sheet, "is_live", lambda: False)
    sheet.upsert_rows("Whatever", ["Account Name", "Balance Snapshot"],
                      [{"Account Name": "X", "Balance Snapshot": 1}],
                      key_column="Account Name")   # path=None → no-op, no crash


# ---------------------------------------------------------------------------
# Schema contract — column ORDER is load-bearing (review S3, D-052)
# ---------------------------------------------------------------------------
def test_transactions_column_order_is_load_bearing():
    # The seed's Finance-Budget actuals are SUMIFS over Date(A)/Amount(D)/
    # Category(E). A reorder here silently breaks the live budget formulas —
    # pin it so that can't happen without a failing test.
    cols = sheet.FINANCE_TRANSACTIONS_COLUMNS
    assert cols[0] == "Date"          # column A
    assert cols[3] == "Amount (ILS)"  # column D
    assert cols[4] == "Category"      # column E


def test_upsert_creates_accounts_tab_when_absent(tmp_path):
    # The new-tab branch of upsert_rows (no pre-seeded Finance-Accounts).
    sp = _sheet(tmp_path)   # only a Placeholder tab exists
    fin.run(csv_dir=_csv(tmp_path), sheet_path=sp, today=TODAY, now=NOW)
    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    assert accts[0] == sheet.FINANCE_ACCOUNTS_COLUMNS   # header created
    assert len(accts) - 1 == 2


def test_imported_at_is_populated_from_now(tmp_path):
    sp = _sheet(tmp_path)
    fin.run(csv_dir=_csv(tmp_path), sheet_path=sp, today=TODAY, now=NOW)
    txns = _rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)
    assert all(v == NOW.isoformat(timespec="seconds")
               for v in _col(txns, "Imported-At"))


def test_multiple_provider_csvs_merge_in_one_run(tmp_path):
    d = _csv(tmp_path)   # mizrahi_… → MIZ-0001, MIZ-0777
    (d / "max_2026-06-17.csv").write_text(
        "account,balance,date,identifier,amount,description\n"
        "MAX-1234,,2026-06-15,maxid1,-150.00,SHOP\n", encoding="utf-8")
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=d, sheet_path=sp, today=TODAY, now=NOW)
    assert res.accounts == 3   # MIZ-0001, MIZ-0777, MAX-1234
    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    max_row = [r for r in accts[1:] if r[0] == "MAX-1234"][0]
    assert max_row[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Type")] == "card"


# ---------------------------------------------------------------------------
# Categorization — on-box rules + DeepSeek gap-fill (M6.4, §8.6; D-050/051)
# ---------------------------------------------------------------------------
from automation.lib import categorize  # noqa: E402
from automation.lib import llm  # noqa: E402


def test_rules_engine_maps_known_merchants():
    rules = categorize.load_rules()
    assert categorize.apply_rules("SHUFERSAL DEAL TLV", rules) == "Groceries"
    assert categorize.apply_rules("פז חיפה דרום", rules) == "Transport"
    # Ordering is load-bearing: SUPERPHARM must resolve to Health, not Groceries.
    assert categorize.apply_rules("SUPERPHARM 123", rules) == "Health"
    assert categorize.apply_rules("totally unknown vendor", rules) is None


def test_rules_vocabulary_is_distinct_and_seeded():
    vocab = categorize.vocabulary(categorize.load_rules())
    assert {"Groceries", "Health", "Transport"} <= set(vocab)
    assert len(vocab) == len(set(vocab))            # no dupes — the LLM vocab


def test_rules_vocab_within_budget_categories():
    """GAP-1 (single highest-value audit fix): every category the rules engine /
    LLM may emit MUST be a Finance-Budget row, or that category's actuals SUMIFS
    reads ₪0 and the spend is invisible. 'Dining'→'Dining out' is now aligned.
    KNOWN-PENDING — Shanee's budget-vocab migration is the authority: Fees/Income/
    Shopping have no budget row yet, held as an explicit allow-list so this test
    still catches any NEW drift and the gap can't be forgotten. When Shanee maps
    them (add rows, or remap the rules), shrink `pending` toward empty. The EXCLUDED
    set ('Card Settlement', `categorize.EXCLUDED_CATEGORIES`) is the opposite of
    pending: a label a RULE may assign (the Cal-settlement mirror) that must NEVER be
    a budget row AND must never be offered to the LLM gap-fill — so the spend counts
    once via the per-merchant Cal scrape, and the model can't zero a non-Cal row by
    guessing it."""
    rules = categorize.load_rules()
    all_cats = {cat for _, cat in rules}            # every label a RULE can assign (incl. excluded)
    llm_vocab = set(categorize.vocabulary(rules))   # the stage-2 LLM vocab (excludes the buckets)
    budget = {r[0] for r in _rows(cfg.SHEET_PATH, cfg.FINANCE_BUDGET_TAB)[1:]
              if r[0] and r[0] != "TOTAL"}
    pending = {"Fees", "Income", "Shopping"}        # GAP-1: awaiting Shanee's budget rows
    excluded = categorize.EXCLUDED_CATEGORIES       # 'Card Settlement' — rule-only, never a budget row
    unmapped = all_cats - budget - pending - excluded
    assert not unmapped, f"rules emit categories with no Finance-Budget row: {unmapped}"
    assert pending <= llm_vocab                     # the LLM may still emit the pending labels
    assert excluded <= all_cats                     # the exclusion bucket is defined as a rule
    assert excluded.isdisjoint(llm_vocab), (        # but NEVER in the LLM vocab (else it zeros a row)
        f"excluded buckets must not be offered to gap-fill: {excluded & llm_vocab}")
    assert not (excluded & budget), (               # and MUST stay out of the budget grid
        f"excluded categories must NOT be Finance-Budget rows: {excluded & budget}")
    assert "Dining out" in all_cats and "Dining" not in all_cats   # the GAP-1 rename


def test_card_settlement_excludes_cal_mirror():
    """Immediate-debit cards (Cal, and Shanee's Cal-cleared debit card) post each
    purchase per-merchant in the card's own scrape AND as a merchant-less settlement
    line on the Mizrahi debit. Those merchant-less mirror lines fall through to the
    EXCLUDED 'Card Settlement' bucket (not a budget row → out of the SUMIFS), so the
    spend counts once via the per-merchant card row. The exclusion block sits BELOW
    every merchant rule (a last-resort fallback), so a settlement token carrying a
    merchant suffix categorizes by its MERCHANT, never force-excluded — the M6.5
    box-verify (ii) over-match, closed structurally (2026-06-25). Tokens verified
    against live data: the כא"ל settlements + the future-charge line, and Shanee's
    'רכישה בכרטיס דביט' mirror (M6.5 2026-06-23, on the connected Cal login)."""
    rules = categorize.load_rules()
    # Genuinely merchant-less wrappers fall through to the exclusion bucket.
    assert categorize.apply_rules('דביט כא"ל (חיוב מיידי)', rules) == "Card Settlement"
    assert categorize.apply_rules('ויזה כא"ל (י)', rules) == "Card Settlement"
    assert categorize.apply_rules("חיוב ויזה כאל עתידי", rules) == "Card Settlement"
    # Shanee's debit card: its per-merchant detail rides the existing Cal scrape, so
    # the merchant-less Mizrahi mirror line is EXCLUDED — flipped from the 06-23 morning
    # guard (when her card wasn't yet scraped and the line was left in the budget).
    assert categorize.apply_rules("רכישה בכרטיס דביט", rules) == "Card Settlement"
    # CONTRACT (the fix for box-verify (ii)): a settlement token that carries a merchant
    # suffix categorizes by the MERCHANT, never the excluded bucket — because the block
    # sits below the merchant rules. A real grocery purchase is never silently zeroed.
    assert categorize.apply_rules("רכישה בכרטיס דביט שופרסל", rules) == "Groceries"
    assert categorize.apply_rules('ויזה כאל שופרסל', rules) == "Groceries"
    # Must NOT over-match: 'כארם' (Karem) has no merchant rule of its own → None, never
    # force-excluded; and a 'דמי כרטיס דביט' fee categorizes as Fees (the full 'רכישה ב…'
    # settlement phrase does not catch it).
    assert categorize.apply_rules("מסעדת ומאפיית כארם חסן", rules) != "Card Settlement"
    assert categorize.apply_rules("דמי כרטיס דביט", rules) == "Fees"
    # Deliberately absent from the budget grid (the SUMIFS exclusion) AND from the LLM
    # gap-fill vocab — reachable only by an exact settlement rule, never an LLM guess on
    # an ambiguous non-Cal row (which would silently zero a real expense).
    budget = {r[0] for r in _rows(cfg.SHEET_PATH, cfg.FINANCE_BUDGET_TAB)[1:] if r[0]}
    assert "Card Settlement" not in budget
    assert "Card Settlement" not in categorize.vocabulary(rules)


def test_excluded_bucket_never_shadows_a_merchant():
    """The Card Settlement exclusion is a LAST-RESORT fallback: it must sit below every
    merchant rule so a settlement wrapper that ever carries a merchant token categorizes
    by that MERCHANT, never the excluded bucket. Pins the file-order invariant — a future
    re-sort that lifts an excluded pattern above the merchant rules would silently zero
    real spend (the exact M6.5 over-match) — by appending each seeded merchant keyword to
    each excluded pattern and asserting the result is never the excluded bucket."""
    rules = categorize.load_rules()
    excluded = categorize.EXCLUDED_CATEGORIES
    excluded_pats = [pat for pat, cat in rules if cat in excluded]
    merchant_pats = [pat for pat, cat in rules if cat not in excluded]
    assert excluded_pats and merchant_pats            # guard: both populated
    for spat in excluded_pats:
        for mpat in merchant_pats:
            got = categorize.apply_rules(f"{spat} {mpat}", rules)
            assert got not in excluded, (
                f"'{spat} {mpat}' force-excluded as {got!r}: an excluded pattern is "
                f"shadowing merchant rule {mpat!r}. Keep the exclusion block BELOW all "
                f"merchant rules so a merchant-bearing line is never silently zeroed.")


def test_missing_rules_file_degrades_quiet(tmp_path):
    # No file → rules engine no-ops (returns []), categorize leaves blanks.
    txns = [{"Description": "SHUFERSAL", "Amount (ILS)": -10,
             "Category": "", "Cat-Source": ""}]
    categorize.categorize_transactions(
        txns, allow_llm=False, rules_path=tmp_path / "nope.csv")
    assert txns[0]["Category"] == "" and txns[0]["Cat-Source"] == ""


def test_unknown_stays_blank_without_llm(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    txns = [{"Description": "ZZZ MYSTERY", "Amount (ILS)": -10,
             "Category": "", "Cat-Source": ""}]
    categorize.categorize_transactions(txns, allow_llm=True)   # key-less → rules only
    assert txns[0]["Category"] == "" and txns[0]["Cat-Source"] == ""


def test_gapfill_sends_only_description_and_amount(monkeypatch):
    """§8.6 privacy: the gap-fill prompt carries description + amount only —
    never the account, the Txn-ID, or any other field of the row."""
    seen = {}

    def fake_complete(prompt, **kw):
        seen["prompt"] = prompt
        seen["system"] = kw.get("system", "")
        return '{"results":[{"i":0,"category":"Shopping"}]}'

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete", fake_complete)
    txns = [{
        "Date": "2026-06-15", "Account": "MIZ-SECRET-9999",
        "Description": "MYSTERY VENDOR QX", "Amount (ILS)": -54.30,
        "Category": "", "Cat-Source": "",
        "Txn-ID": "secret-identifier-123", "Imported-At": "z",
    }]
    categorize.categorize_transactions(txns, allow_llm=True)
    assert txns[0]["Category"] == "Shopping" and txns[0]["Cat-Source"] == "llm"
    blob = seen["prompt"] + seen["system"]
    assert "MYSTERY VENDOR QX" in blob          # description: allowed
    assert "54.3" in blob                        # amount: allowed
    assert "MIZ-SECRET-9999" not in blob         # account: NEVER leaves the box
    assert "secret-identifier-123" not in blob   # Txn-ID: NEVER leaves the box


def test_gapfill_rejects_offvocab_answer(monkeypatch):
    # A category not in the rules vocab is dropped — the txn stays blank.
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete",
                        lambda p, **k: '{"results":[{"i":0,"category":"Crypto"}]}')
    txns = [{"Description": "ZZZ MYSTERY", "Amount (ILS)": -10,
             "Category": "", "Cat-Source": ""}]
    categorize.categorize_transactions(txns, allow_llm=True)
    assert txns[0]["Category"] == "" and txns[0]["Cat-Source"] == ""


def test_gapfill_chunks_so_large_import_is_fully_categorized(monkeypatch):
    """B5: a rules-miss batch larger than GAPFILL_MAX_BATCH must be FULLY
    categorized before the write — chunk-looped, not truncated at the per-prompt
    cap. A blank-Category row keeps its real Txn-ID and is then excluded from
    dedup forever (never re-presented to the LLM), so an overflow left blank was
    permanent data loss on the first 45-day backlog."""
    import json
    budgets = []

    def fake_complete(prompt, **kw):
        budgets.append(kw.get("max_tokens"))
        # Cover every within-chunk index (a chunk is <= GAPFILL_MAX_BATCH rows).
        return json.dumps({"results": [{"i": i, "category": "Shopping"}
                                       for i in range(categorize.GAPFILL_MAX_BATCH)]})

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete", fake_complete)
    n = categorize.GAPFILL_MAX_BATCH * 2 + 5    # 165 — well over one prompt's cap
    txns = [{"Description": f"ZZZ MYSTERY {i}", "Amount (ILS)": -10,
             "Category": "", "Cat-Source": ""} for i in range(n)]
    categorize.categorize_transactions(txns, allow_llm=True)
    assert all(t["Category"] == "Shopping" and t["Cat-Source"] == "llm" for t in txns)
    assert len(budgets) == 3                     # ceil(165/80) chunks, not one truncated call
    # A full 80-row chunk's reply (~1.5k tokens) must not be truncated by a fixed
    # small cap — the reply budget scales with the chunk (else the whole chunk
    # parses to {} and lands blank: the B5 data-loss in disguise).
    assert max(budgets) >= categorize.GAPFILL_MAX_BATCH * 16


# ---------------------------------------------------------------------------
# Budget reconciliation — the SUMIFS landmine (M6.4 build note; D-050)
# ---------------------------------------------------------------------------
def test_seed_budget_uses_text_prefix_not_serial_sumifs():
    """The landmine: a serial DATE() window over the RAW ISO-text Date column
    reads ₪0. Pin the seed's actuals to the locale-independent text-prefix form
    so the serial form can't silently return, and pin the MoM column."""
    b = load_workbook(cfg.SHEET_PATH)[cfg.FINANCE_BUDGET_TAB]
    c2 = b["C2"].value
    assert '$I$2&"*"' in c2               # current-month TEXT prefix
    assert '">="&DATE(' not in c2         # NOT the broken serial window
    assert 'TEXT($I$1,"yyyy")&"*"' in b["F2"].value          # YTD = year prefix
    assert b["J1"].value == "Last Month (ILS)"               # MoM column present
    assert b["I3"].value == '=TEXT(EDATE($I$1,-1),"yyyy-mm")'  # prev-month tag


def test_text_prefix_month_window_sums_iso_text_dates():
    """Prove the LOGIC the SUMIFS encodes works on the ISO-TEXT dates ingest
    writes. This Python re-implementation is DELIBERATE (tests-quality#3 / GAP-6):
    the seed backend reads formula cells as None offline (lib/sheet XlsxBackend
    data_only caveat), so the real SUMIFS can't be evaluated here — it's verified
    live at M6.3. This is the value that read ₪0 before the fix."""
    txns = [
        {"Date": "2026-06-03", "Category": "Groceries", "Amount (ILS)": -432.50},
        {"Date": "2026-06-20", "Category": "Groceries", "Amount (ILS)": -100.00},
        {"Date": "2026-05-28", "Category": "Groceries", "Amount (ILS)": -999.00},
        {"Date": "2026-06-10", "Category": "Transport", "Amount (ILS)": -280.00},
    ]

    def month_actual(cat, tag):   # mirrors -SUMIFS(D, E=cat, A like tag&"*")
        return -sum(t["Amount (ILS)"] for t in txns
                    if t["Category"] == cat and t["Date"].startswith(tag))

    assert month_actual("Groceries", "2026-06") == 532.50   # non-zero, this month
    assert month_actual("Groceries", "2026-05") == 999.00   # prev month isolated
    assert month_actual("Transport", "2026-06") == 280.00


# ---------------------------------------------------------------------------
# Budget formula INSTALLER — lib/finance_budget + finance_budget_formulas (M6.3,
# the M6.4 reconciliation step gated to live data). Single source of formula
# text; pinned against the committed seed so seed/installer/live can't diverge.
# ---------------------------------------------------------------------------
from automation.lib import finance_budget as fb  # noqa: E402
from automation import finance_budget_formulas as fbf  # noqa: E402

BUDGET_HEADER = ["Category", "Monthly Target (ILS)", "Actual (current month)",
                 "Variance", "% of Target", "YTD Actual", "Notes", "As-of date",
                 None, "Last Month (ILS)"]   # col I (9) header is the =TODAY() helper


def _budget_grid(categories=("Groceries", "Transport"), total=True, header=None):
    """A Finance-Budget grid (list[list]) — header + category rows (A name, B
    target) + an optional TOTAL row, machine columns blank (pre-install)."""
    g = [list(header if header is not None else BUDGET_HEADER)]
    for name in categories:
        row = [None] * 10
        row[fb.COL_CATEGORY - 1], row[fb.COL_TARGET - 1] = name, 1000
        g.append(row)
    if total:
        row = [None] * 10
        row[fb.COL_CATEGORY - 1] = "TOTAL"
        g.append(row)
    return g


def _budget_sheet(tmp_path, categories=(("Groceries", 4000), ("Transport", 1500)),
                  total=True, header=None):
    """A tmp xlsx with a Finance-Budget tab (header + categories + optional TOTAL),
    machine columns blank — the live tab's state before the installer runs."""
    wb = Workbook()
    wb.active.title = "Placeholder"
    ws = wb.create_sheet(cfg.FINANCE_BUDGET_TAB)
    ws.append(header if header is not None else BUDGET_HEADER)
    for name, target in categories:
        ws.append([name, target])
    if total:
        ws.append(["TOTAL"])
    p = tmp_path / "budget.xlsx"
    wb.save(p)
    return p


def test_budget_cells_are_text_prefix_not_serial():
    """The landmine guard at the installer level: the month/YTD/last-month actuals
    are TEXT-prefix wildcards over the ISO-text Date, never a serial DATE() window."""
    cells = {(r, c): v for r, c, v in fb.budget_formula_cells(_budget_grid())}
    c2 = cells[(2, fb.COL_ACTUAL)]
    assert '$I$2&"*"' in c2 and '">="&DATE(' not in c2          # month text-prefix
    assert 'TEXT($I$1,"yyyy")&"*"' in cells[(2, fb.COL_YTD)]    # YTD = year prefix
    assert '$I$3&"*"' in cells[(2, fb.COL_LASTMONTH)]           # last-month
    assert cells[(1, fb.COL_HELPER)] == "=TODAY()"
    assert cells[(2, fb.COL_HELPER)] == '=TEXT(I1,"yyyy-mm")'
    assert cells[(3, fb.COL_HELPER)] == '=TEXT(EDATE($I$1,-1),"yyyy-mm")'
    assert cells[(2, fb.COL_VARIANCE)] == "=B2-C2"
    assert cells[(2, fb.COL_PCT)] == "=IFERROR(C2/B2,0)"
    # TOTAL sums over the category span (rows 2..3), plus its own variance/%.
    assert cells[(4, fb.COL_ACTUAL)] == "=SUM(C2:C3)"
    assert cells[(4, fb.COL_TARGET)] == "=SUM(B2:B3)"
    assert cells[(4, fb.COL_YTD)] == "=SUM(F2:F3)"


def test_budget_cells_match_committed_seed():
    """The anti-drift tie: the installer's output for the seed's own categories
    must EQUAL the seed's pinned formulas, so a live install and the committed
    seed (test_seed_budget_uses_text_prefix_not_serial_sumifs) stay identical."""
    seed = load_workbook(cfg.SHEET_PATH)[cfg.FINANCE_BUDGET_TAB]   # formulas (not data_only)
    grid = [[seed.cell(row=r, column=c).value for c in range(1, 11)]
            for r in range(1, seed.max_row + 1)]
    cells = {(r, c): v for r, c, v in fb.budget_formula_cells(grid)}
    for coord, key in {"C2": (2, 3), "F2": (2, 6), "J2": (2, 10), "D2": (2, 4),
                       "E2": (2, 5), "I1": (1, 9), "I2": (2, 9), "I3": (3, 9),
                       "C13": (13, 3), "B13": (13, 2), "F13": (13, 6)}.items():
        assert cells[key] == seed[coord].value, coord
    # …and the WHOLE installer output equals the seed, not just the spot-checks —
    # any divergence at any of the 66 machine cells (e.g. YTD on rows 3-12, the
    # TOTAL variance/%, the H labels) fails here, making the anti-drift tie total.
    for r, c, v in fb.budget_formula_cells(grid):
        assert v == seed.cell(row=r, column=c).value, (r, c)


def test_budget_installer_round_trips_to_live_formulas(tmp_path):
    """The write seam: cells stamped via sheet.write_cells (USER_ENTERED) land as
    live formulas, and the human columns (Category/Target/Notes) are untouched."""
    sp = _budget_sheet(tmp_path)
    cells = fb.budget_formula_cells(sheet.read_grid(cfg.FINANCE_BUDGET_TAB, sp))
    sheet.write_cells(cfg.FINANCE_BUDGET_TAB, cells, path=sp)
    ws = load_workbook(sp)[cfg.FINANCE_BUDGET_TAB]                 # data_only=False → formulas
    assert ws["C2"].value.startswith("=IFERROR(-SUMIFS(") and '$I$2&"*"' in ws["C2"].value
    assert 'TEXT($I$1,"yyyy")&"*"' in ws["F2"].value
    assert '$I$3&"*"' in ws["J2"].value
    assert ws["I1"].value == "=TODAY()" and ws["I2"].value == '=TEXT(I1,"yyyy-mm")'
    assert ws["A2"].value == "Groceries" and ws["B2"].value == 4000   # human cols intact
    assert ws["G2"].value in (None, "")                               # Notes never written
    assert ws["C4"].value == "=SUM(C2:C3)"                            # TOTAL over 2 rows


def test_budget_installer_never_writes_human_columns():
    """The irreversible-harm guard: the installer must never write a category row's
    Category (A) or Monthly Target (B), or any Notes (G) — those are Shanee's. (The
    TOTAL row's B is a machine =SUM and IS allowed.) This pins all three prongs of
    the safety contract, so a future refactor that emitted a human cell fails here
    rather than clobbering the live budget on the next re-stamp. Also covers the old
    'stray Transport-row Notes SUMIFS' artifact class (the G prong)."""
    grid = _budget_grid(categories=("Housing", "Groceries", "Transport"))
    cats = set(fb.category_rows(grid))
    cells = fb.budget_formula_cells(grid)
    assert all(c != fb.COL_NOTES for _, c, _ in cells)                        # G never (any row)
    assert all(c != fb.COL_CATEGORY for _, c, _ in cells)                     # A never (any row)
    assert all(not (c == fb.COL_TARGET and r in cats) for r, c, _ in cells)   # B never on a category row
    assert any(c == fb.COL_TARGET for _, c, _ in cells)                       # …but the TOTAL B SUM is present


def test_budget_header_drift_fails_loud(tmp_path):
    """A renamed load-bearing column → refuse to stamp by position (fail loud,
    never guess which column the actuals belong in). A *machine* header holding a
    DIFFERENT value is a real column shift, distinct from an absent one (titled)."""
    bad = list(BUDGET_HEADER)
    bad[fb.COL_ACTUAL - 1] = "Spent"                  # C header drifted (non-empty conflict)
    with pytest.raises(fb.BudgetHeaderError):
        fb.budget_formula_cells(_budget_grid(header=bad))


def test_budget_installer_titles_absent_machine_header():
    """Hardening (2026-06-20): a tab that simply LACKS a machine column header —
    the live tab created before the M6.4 block had no J 'Last Month (ILS)', and a
    fresh budget from Shanee's migration has only Category/Target — must NOT fail
    loud. The installer owns those columns, so it titles them (row 1) and stamps the
    data. An absent header is no contradiction; a CONFLICTING one still refuses
    (test_budget_header_drift_fails_loud). Removes the manual 'add J1 by hand' step."""
    hdr = list(BUDGET_HEADER)
    hdr[fb.COL_LASTMONTH - 1] = None    # J absent — the exact live 2026-06-20 case
    hdr[fb.COL_YTD - 1] = ""            # F absent too (blank, not None)
    cells = {(r, c): v for r, c, v in fb.budget_formula_cells(_budget_grid(header=hdr))}
    assert cells[(1, fb.COL_LASTMONTH)] == "Last Month (ILS)"   # installer titled J
    assert cells[(1, fb.COL_YTD)] == "YTD Actual"               # …and F
    assert '$I$3&"*"' in cells[(2, fb.COL_LASTMONTH)]           # …and still stamped its data
    assert (1, fb.COL_CATEGORY) not in cells                    # never (re)titles a human header


def test_budget_absent_human_header_still_fails_loud():
    """The installer titles its OWN columns, never the human ones: an absent
    Category or Monthly Target header is a malformed tab it refuses, rather than
    silently re-titling Shanee's columns (the human-vs-machine ownership boundary)."""
    for human_col in (fb.COL_CATEGORY, fb.COL_TARGET):
        hdr = list(BUDGET_HEADER)
        hdr[human_col - 1] = None
        with pytest.raises(fb.BudgetHeaderError):
            fb.budget_formula_cells(_budget_grid(header=hdr))


def test_budget_no_categories_fails_loud():
    """A header-only tab (no budget rows yet) fails loud rather than stamping an
    empty layout — Shanee's migration must populate column A first."""
    with pytest.raises(fb.BudgetHeaderError):
        fb.budget_formula_cells(_budget_grid(categories=(), total=False))


def test_budget_category_below_total_fails_loud():
    """A category row ordered BELOW the TOTAL row would put TOTAL inside its own SUM
    range (circular #ERROR, and two surfaces read TOTAL) — refuse the layout, never
    emit a self-referential sum. Guards a re-run after a budget reorder."""
    grid = [list(BUDGET_HEADER), [None] * 10, [None] * 10, [None] * 10]
    grid[1][fb.COL_CATEGORY - 1], grid[1][fb.COL_TARGET - 1] = "Housing", 8500   # row 2
    grid[2][fb.COL_CATEGORY - 1] = "TOTAL"                                       # row 3
    grid[3][fb.COL_CATEGORY - 1], grid[3][fb.COL_TARGET - 1] = "Savings", 1000   # row 4 < TOTAL
    with pytest.raises(fb.BudgetHeaderError):
        fb.budget_formula_cells(grid)


def test_write_cells_skips_without_live_or_path(monkeypatch):
    """sheet.write_cells refuses to write when path is None and not live — the
    lib-level 'never mutate the committed seed' backstop (mirrors upsert_rows). The
    CLI short-circuits before reaching this branch, so pin it directly."""
    monkeypatch.setattr(sheet, "is_live", lambda: False)
    before = load_workbook(cfg.SHEET_PATH)[cfg.FINANCE_BUDGET_TAB]["C2"].value
    sheet.write_cells(cfg.FINANCE_BUDGET_TAB, [(2, 3, "=1+1")], path=None)   # no-op
    after = load_workbook(cfg.SHEET_PATH)[cfg.FINANCE_BUDGET_TAB]["C2"].value
    assert after == before                                                  # seed untouched


def test_installer_dry_run_writes_nothing(tmp_path, capsys):
    sp = _budget_sheet(tmp_path)
    cells = fbf.run(path=sp, dry_run=True)
    assert cells
    assert load_workbook(sp)[cfg.FINANCE_BUDGET_TAB]["C2"].value in (None, "")
    assert "dry-run" in capsys.readouterr().out


def test_installer_refuses_without_live_or_path(capsys):
    """No live backend + no path → builds the cells (reading the seed) but writes
    NOTHING, so a creds-less dev run can't mutate the committed seed."""
    before = load_workbook(cfg.SHEET_PATH)[cfg.FINANCE_BUDGET_TAB]["C2"].value
    cells = fbf.run(path=None, dry_run=False)          # is_live() is False (conftest)
    assert cells and "NOT written" in capsys.readouterr().out
    after = load_workbook(cfg.SHEET_PATH)[cfg.FINANCE_BUDGET_TAB]["C2"].value
    assert after == before                             # seed untouched


# ---------------------------------------------------------------------------
# scrape.js — the Node scraper is VPS-only (banks + bundled Chromium), so these
# guard only the parts that need neither: it parses, and its argv/fail-loud
# contract holds. The deps (israeli-bank-scrapers, puppeteer) are required
# lazily, so these run green without `npm ci` having been done.
# ---------------------------------------------------------------------------
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node not installed (scrape.js is VPS-only)"
)


def _node(*args, env=None):
    return subprocess.run(
        ["node", str(SCRAPE_JS), *args],
        capture_output=True, text=True, env=env, timeout=30,
    )


@requires_node
def test_scrape_js_node_check_parses():
    """The syntax guard the module docstring promises (no test existed before)."""
    res = subprocess.run(
        ["node", "--check", str(SCRAPE_JS)], capture_output=True, text=True, timeout=30
    )
    assert res.returncode == 0, res.stderr


@requires_node
@pytest.mark.parametrize("args", [["--auth"], ["--auth", "bogus"]])
def test_scrape_js_auth_usage_guard(args):
    """`--auth` without a known provider exits 2 with usage and loads no Chromium
    (the guard runs before puppeteer is required, so it passes with no node_modules)."""
    res = _node(*args)
    assert res.returncode == 2
    assert "usage: node scrape.js --auth <provider>" in res.stderr
    assert "mizrahi, max, cal" in res.stderr


@requires_node
def test_scrape_js_auth_mizrahi_is_noop():
    """Mizrahi is password-only — `--auth mizrahi` is a clean no-op (exit 0), not a
    browser launch; only Max/Cal persist a device-trust profile."""
    res = _node("--auth", "mizrahi")
    assert res.returncode == 0
    assert "password-only" in res.stdout


@requires_node
@pytest.mark.parametrize("args", [["--foo"], ["mizrahi"], ["--auth", "max", "extra"]])
def test_scrape_js_rejects_unknown_invocation(args):
    """A typo or stray positional must fail loud (exit 2), never silently take the
    daily-scrape branch — fail-loud on the hand-typed `--auth` command."""
    res = _node(*args)
    assert res.returncode == 2
    assert "usage: node scrape.js" in res.stderr


@requires_node
def test_scrape_js_missing_creds_fails_loud():
    """A daily run with no creds file fails loud (exit 1) — the unit-fails →
    fail-flag contract. Lazy require means this hits loadCreds() before the lib."""
    import os
    env = {**os.environ, "FAMILY_INC_BANK_CREDS": "/nonexistent/bank_creds.json"}
    res = _node(env=env)
    assert res.returncode == 1
    assert "[fatal]" in res.stderr and "bank_creds.json" in res.stderr


# ---------------------------------------------------------------------------
# Re-categorize backfill + coverage (M6.4/M6.5 acceptance; SPEC §12.2)
# ---------------------------------------------------------------------------
from automation import finance_recategorize as recat  # noqa: E402
from automation.lib import finance_coverage as fincov  # noqa: E402

# Finance-Transactions rows for the backfill: a Cal mirror (→ Card Settlement via
# the existing rule), a grocery (→ Groceries), a genuine unknown (stays blank,
# LLM off in tests), Shanee's debit mirror (→ Card Settlement), and an
# already-categorized manual row whose description WOULD match a rule (PAZ →
# Transport) — it must survive untouched.
TXN_ROWS = [
    {"Date": "2026-06-15", "Account": "MIZ-0001", "Description": "ויזה כאל",
     "Amount (ILS)": -540.00, "Category": "", "Cat-Source": "",
     "Txn-ID": "h:cal0000000000a1", "Imported-At": "2026-06-19T06:00:00"},
    {"Date": "2026-06-15", "Account": "MIZ-0001", "Description": "SHUFERSAL DEAL TLV",
     "Amount (ILS)": -432.50, "Category": "", "Cat-Source": "",
     "Txn-ID": "h:groc000000000b2", "Imported-At": "2026-06-19T06:00:00"},
    {"Date": "2026-06-16", "Account": "MIZ-0001", "Description": "ZZZ MYSTERY VENDOR",
     "Amount (ILS)": -12.00, "Category": "", "Cat-Source": "",
     "Txn-ID": "h:unkn000000000c3", "Imported-At": "2026-06-19T06:00:00"},
    {"Date": "2026-06-16", "Account": "MIZ-0001", "Description": "רכישה בכרטיס דביט",
     "Amount (ILS)": -77.00, "Category": "", "Cat-Source": "",
     "Txn-ID": "h:dbit000000000d4", "Imported-At": "2026-06-19T06:00:00"},
    {"Date": "2026-06-17", "Account": "MIZ-0001", "Description": "PAZ GAS HAIFA",
     "Amount (ILS)": -280.00, "Category": "Health", "Cat-Source": "manual",
     "Txn-ID": "h:hand000000000e5", "Imported-At": "2026-06-19T06:00:00"},
]


def _txn_sheet(tmp_path, rows=TXN_ROWS, columns=None):
    """A tmp xlsx with a Finance-Transactions tab (header + rows)."""
    cols = columns or sheet.FINANCE_TRANSACTIONS_COLUMNS
    wb = Workbook()
    wb.active.title = "Placeholder"
    ws = wb.create_sheet(cfg.FINANCE_TRANSACTIONS_TAB)
    ws.append(cols)
    for r in rows:
        ws.append([r.get(c, "") for c in cols])
    p = tmp_path / "finance.xlsx"
    wb.save(p)
    return p


def _by_txn(path):
    """{Txn-ID: (Category, Cat-Source)} read back from the live tab. openpyxl
    rounds an empty cell to None on read — coerce to "" so a blank reads ("","")."""
    tab = _rows(path, cfg.FINANCE_TRANSACTIONS_TAB)
    hdr = tab[0]
    ti, ci, si = hdr.index("Txn-ID"), hdr.index("Category"), hdr.index("Cat-Source")
    s = lambda v: "" if v is None else v
    return {r[ti]: (s(r[ci]), s(r[si])) for r in tab[1:]}


def test_recategorize_backfills_blank_rows(tmp_path):
    sp = _txn_sheet(tmp_path)
    res = recat.run(sheet_path=sp, allow_llm=False)        # rules-only, deterministic
    assert res.wrote
    assert res.total == 5 and res.blank_before == 4
    assert res.recategorized == 3 and res.now_rules == 3 and res.still_blank == 1
    got = _by_txn(sp)
    assert got["h:cal0000000000a1"] == ("Card Settlement", "rules")  # Cal mirror
    assert got["h:groc000000000b2"] == ("Groceries", "rules")
    assert got["h:dbit000000000d4"] == ("Card Settlement", "rules")  # Shanee debit mirror
    assert got["h:unkn000000000c3"] == ("", "")                       # genuine unknown stays blank
    assert got["h:hand000000000e5"] == ("Health", "manual")           # manual row untouched


def test_recategorize_only_touches_blank_rows(tmp_path):
    """The manual 'Health' row whose description (PAZ) WOULD map to Transport is
    never re-derived — the backfill is scoped to blank rows, so a human (or prior)
    categorization is never clobbered."""
    sp = _txn_sheet(tmp_path)
    recat.run(sheet_path=sp, allow_llm=False)
    assert _by_txn(sp)["h:hand000000000e5"] == ("Health", "manual")


def test_recategorize_is_idempotent(tmp_path):
    sp = _txn_sheet(tmp_path)
    recat.run(sheet_path=sp, allow_llm=False)
    before = _by_txn(sp)
    res2 = recat.run(sheet_path=sp, allow_llm=False)       # only the 1 unknown left blank
    assert res2.blank_before == 1 and res2.recategorized == 0 and not res2.wrote
    assert _by_txn(sp) == before                            # nothing changed on the second pass


def test_recategorize_dry_run_writes_nothing(tmp_path):
    sp = _txn_sheet(tmp_path)
    res = recat.run(sheet_path=sp, dry_run=True, allow_llm=False)
    assert not res.wrote and res.recategorized == 3         # rules-preview counts the 3 hits
    # ...but the tab is untouched: every blank row is still blank.
    got = _by_txn(sp)
    for tid in ("h:cal0000000000a1", "h:groc000000000b2", "h:dbit000000000d4"):
        assert got[tid] == ("", "")


def test_recategorize_skips_without_live_or_path(monkeypatch):
    """Seed-safety: no live backend and no --sheet → reads/writes nothing, never
    touches the committed seed (mirrors test_upsert_rows_skips_without_live_or_path)."""
    monkeypatch.delenv(cfg.SHEET_ID_ENV, raising=False)
    sheet.reset_backend()
    res = recat.run(sheet_path=None)
    assert res.total == 0 and not res.wrote


def test_recategorize_fails_loud_on_missing_header(tmp_path):
    """A Finance-Transactions tab missing a load-bearing column (Cat-Source) fails
    loud (§7.1) rather than writing Category by guessed position."""
    cols = [c for c in sheet.FINANCE_TRANSACTIONS_COLUMNS if c != "Cat-Source"]
    sp = _txn_sheet(tmp_path, columns=cols)
    with pytest.raises(recat.RecategorizeError):
        recat.run(sheet_path=sp, allow_llm=False)


def test_recategorize_empty_tab_is_noop(tmp_path):
    sp = _txn_sheet(tmp_path, rows=[])
    res = recat.run(sheet_path=sp, allow_llm=False)
    assert res.total == 0 and not res.wrote


def test_recategorize_handles_blank_interior_row(tmp_path):
    """A fully-blank interior row must not shift the physical write index: every
    Txn-ID still maps to its OWN (Category, Cat-Source) and res.total counts only the
    non-blank rows. Pins the enumerate(grid[1:], start=2) invariant — a refactor that
    derived the write row from the filtered candidate list would stamp the rows BELOW
    the blank one onto the wrong transactions (silent ledger corruption)."""
    rows = TXN_ROWS[:2] + [{c: "" for c in sheet.FINANCE_TRANSACTIONS_COLUMNS}] + TXN_ROWS[2:]
    sp = _txn_sheet(tmp_path, rows=rows)
    res = recat.run(sheet_path=sp, allow_llm=False)
    assert res.total == 5                                  # the all-blank interior row is skipped
    got = _by_txn(sp)
    assert got["h:cal0000000000a1"] == ("Card Settlement", "rules")   # above the blank
    assert got["h:groc000000000b2"] == ("Groceries", "rules")
    assert got["h:dbit000000000d4"] == ("Card Settlement", "rules")   # below the blank — index held
    assert got["h:unkn000000000c3"] == ("", "")
    assert got["h:hand000000000e5"] == ("Health", "manual")           # below the blank — untouched


def test_recategorize_llm_fills_blank_and_dry_run_skips_llm(tmp_path, monkeypatch):
    """The live LLM gap-fill path: a genuine-unknown blank gets Cat-Source 'llm' from
    DeepSeek; and --dry-run must NOT call the LLM (the documented no-API-spend preview,
    so live merchant descriptions don't leave the box during a no-write run, §8.6)."""
    calls = {"n": 0}

    def fake_complete(prompt, **kw):
        calls["n"] += 1
        return '{"results":[{"i":0,"category":"Shopping"}]}'

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete", fake_complete)
    rows = [r for r in TXN_ROWS if r["Txn-ID"] == "h:unkn000000000c3"]   # the one rules-miss
    sp = _txn_sheet(tmp_path, rows=rows)
    # (1) dry-run with allow_llm=True must NOT call the LLM and must not write.
    res_dry = recat.run(sheet_path=sp, dry_run=True, allow_llm=True)
    assert calls["n"] == 0 and not res_dry.wrote
    assert _by_txn(sp)["h:unkn000000000c3"] == ("", "")
    # (2) live run calls the LLM once and writes Cat-Source 'llm'.
    res = recat.run(sheet_path=sp, dry_run=False, allow_llm=True)
    assert calls["n"] == 1 and res.now_llm == 1 and res.wrote
    assert _by_txn(sp)["h:unkn000000000c3"] == ("Shopping", "llm")


# ---- coverage (the read-only yield surface) ----

COV_ROWS = [
    {"Category": "Groceries", "Cat-Source": "rules", "Account": "MIZ", "Description": "shufersal"},
    {"Category": "Health", "Cat-Source": "llm", "Account": "MIZ", "Description": "clinic"},
    {"Category": "Card Settlement", "Cat-Source": "rules", "Account": "MIZ", "Description": "ויזה כאל"},
    {"Category": "", "Cat-Source": "", "Account": "MIZ", "Description": "ATM WITHDRAWAL"},
    {"Category": "Dining out", "Cat-Source": "", "Account": "CAL", "Description": "wolt"},  # manual
]


def test_coverage_counts_and_buckets():
    c = fincov.coverage(COV_ROWS)
    assert c.total == 5
    assert c.categorized == 3 and c.excluded == 1 and c.blank == 1     # partition → total
    assert c.categorized + c.excluded + c.blank == c.total
    assert c.eligible == 4                                             # total − excluded
    assert round(c.coverage_pct, 3) == 0.75                            # 3/4
    # by_source is scoped to CATEGORIZED rows, so it sums to `categorized` and the
    # excluded Card-Settlement row (Cat-Source "rules") is NOT counted here — else the
    # rules sub-count would overshoot the categorized headline on live data.
    assert c.by_source == {"rules": 1, "llm": 1, "manual": 1}          # Groceries · Health · Dining out
    assert sum(c.by_source.values()) == c.categorized


def test_coverage_per_account():
    c = fincov.coverage(COV_ROWS)
    miz, cal = c.by_account["MIZ"], c.by_account["CAL"]
    assert (miz.total, miz.categorized, miz.excluded, miz.blank) == (4, 2, 1, 1)
    assert miz.eligible == 3 and round(miz.pct, 3) == round(2 / 3, 3)
    assert (cal.total, cal.categorized, cal.pct) == (1, 1, 1.0)


def test_coverage_blank_samples_name_the_merchant():
    c = fincov.coverage(COV_ROWS)
    assert c.blank_samples == [("ATM WITHDRAWAL", 1)]


def test_coverage_empty_degrades():
    c = fincov.coverage([])
    assert c.total == 0 and c.coverage_pct == 0.0 and c.eligible == 0
    assert "No finance transactions" in fincov.render(c, date(2026, 6, 26))


def test_coverage_rows_from_grid_skips_blank_and_short_rows():
    grid = [
        ["Date", "Account", "Description", "Category", "Cat-Source"],
        ["2026-06-15", "MIZ", "shufersal", "Groceries", "rules"],
        ["2026-06-16", "MIZ", "atm"],                 # short row — trailing cells absent
        [None, None, None, None, None],               # fully blank — skipped
    ]
    rows = fincov.rows_from_grid(grid)
    assert len(rows) == 2
    assert rows[0]["Category"] == "Groceries"
    assert rows[1]["Description"] == "atm" and rows[1]["Category"] is None


def test_coverage_cli_reads_live_tab(tmp_path):
    """The read-only CLI reads the tab through lib/sheet and never writes it."""
    from automation import finance_coverage as cli
    sp = _txn_sheet(tmp_path)                          # 5 rows, 4 blank, 0 categorized yet
    cov = cli.run(date(2026, 6, 26), sheet_path=sp)
    assert cov.total == 5 and cov.blank == 4 and cov.categorized == 1   # only the manual Health row
    # read-only: the tab is byte-for-byte unchanged (still 4 blank).
    assert sum(1 for v in _by_txn(sp).values() if v == ("", "")) == 4

=== End: tests/test_finance.py ===


```

</details>
