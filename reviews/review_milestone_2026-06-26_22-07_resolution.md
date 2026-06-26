# Resolution — milestone review `review_milestone_2026-06-26_22-07.md`

M6 finance-acceptance tooling (re-categorize backfill + coverage + threshold).
Reviewer: DeepSeek (`deepseek-chat`). This session also ran a 6-lens **internal**
adversarial review first; that resolution is folded into the code (1 major + 2
test-gaps + 1 nit). Below resolves the **external** gate. Suite **486 green**.

## Concerns

1. **[HIGH] No header re-validation between read and write (TOCTOU).** → **APPLY.**
   Added `_reverify_columns()` — re-reads the header immediately before `write_cells`
   and aborts (`RecategorizeError`, §7.1) if the Category/Cat-Source columns shifted
   since the initial read, rather than stamp the wrong column on the live ledger.
   Cheap on a once-per-gate run. Pinned by `test_recategorize_reverify_columns_catches_drift`.

2. **[HIGH] A partially-applied `write_cells` leaves a torn (half-categorized) row.**
   → **DEFEND** (premise doesn't hold for our backend). `GSheetBackend.batch_update`
   issues a **single** `ws.batch_update(data)` — one atomic Sheets API request carrying
   every range — so the two cells of a row (Category + Cat-Source) always land together;
   the API does not apply a subset of one request's ranges. The only realistic failure is
   the **whole** request not applying (a network timeout), which is **safe**: the backfill
   is idempotent (blank-rows-only), so a re-run reprocesses any still-blank row, and a row
   the server *did* categorize is correctly skipped. No half-Category/half-Source state is
   reachable. (A client-side per-cell chunking loop would *introduce* the very tear the
   concern describes — so we deliberately keep the single atomic batch.)

3. **[MEDIUM] `--dry-run` under-reports coverage (rules-only, no LLM).** → **APPLY.**
   The dry-run now prints "rules-only preview — the live run's DeepSeek gap-fill will
   categorize more", so a low preview number can't discourage the real pass. The full
   `--dry-run-llm` alternative is **declined** — calling the LLM in a no-write preview
   defeats the documented no-API-spend / no-description-egress purpose (§8.6); the note
   addresses the misread at zero cost.

4. **[MEDIUM] `coverage.rows_from_grid` keys off the raw header → a cased/spaced live
   header reads as 0%.** → **APPLY.** `rows_from_grid` now maps each header to its
   canonical column name via `_norm` (a `_CANON_BY_NORM` table), so `"Category "` /
   `"cat-source"` still resolve. Gives the read path the robustness the backfill already
   had. Pinned by `test_coverage_rows_from_grid_normalizes_header_casing`.

5. **[LOW] The exclusion-block file-order is enforced only by discipline + a token-concat
   test.** → **APPLY (test).** Added `test_excluded_block_is_last_in_rules_file` asserting
   every excluded pattern sits below every merchant rule (the direct file-order invariant
   the backfill relies on). The CSV already carries a prominent "LAST-RESORT FALLBACK …
   sits at the BOTTOM ON PURPOSE" comment block, so no further marker was added.

## Missed alternatives

1. **Targeted Txn-ID UPDATE instead of a full blank re-scan.** → **DEFEND.** The full
   re-scan is the point: it also catches non-mirror merchants the rules now cover and runs
   the LLM gap-fill — a targeted update would fix only the Cal mirror and miss the broader
   yield. Scope (blank-only) keeps it safe + idempotent.
2. **Use `upsert_rows` for the backfill (absorbs header drift on write).** → **DEFEND**
   (and the reviewer's own Affirmation #1 agrees): surgical `write_cells` was chosen
   precisely to avoid `upsert`'s append-on-unmatched-key path spawning a partial row from a
   stray Txn-ID. Header drift is instead handled by `_reverify_columns` (concern 1).
3. **Coverage also emits machine-readable JSONL so a box script can assert ≥0.9.** →
   **OPEN / deferred nicety.** The metric is **report-first** — a human reads the % and
   sets the bar. A JSONL emit serves an automated box-gate that doesn't exist yet; if the
   box-run grows one, add `--json` then. Not needed for this gate.
4. **`--dry-run-llm` mode.** → **DECLINE** (see concern 3).
5. **An `ORDER` column in the rules CSV.** → **DECLINE.** Over-engineering — file order
   *is* the order; the new ordering test pins it.

## Affirmations (recorded)

Surgical blank-only `write_cells` over upsert · coverage≠correctness deferral (the
report-first metric + #12 deferral) · `by_source` scoped to categorized rows · the
gap-fill chunk-loop regression test. No changes — affirmed as designed.

## Net

4 of 5 concerns **Applied** (1 header re-validate · 3 dry-run note · 4 coverage header
norm · 5 ordering test); concern 2 **Defended** (single atomic batch — torn state not
reachable; idempotent retry is the recovery path the reviewer asked for); 1 alternative
**Open** (coverage JSONL, deferred). **0 blockers.** Suite 483 → **486 green**.
