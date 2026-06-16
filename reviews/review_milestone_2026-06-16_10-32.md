# Milestone review — milestone lane (D-040, Apify secondary source)

- **When:** 2026-06-16T10:32:00
- **Provider:** in-session adversarial reviewer (strong model, fresh context — the external Ollama/DeepSeek provider in `review.py` was keyless in the build sandbox; this holds the same "external adversarial reviewer outside our context" role, D-020/D-028 precedent). Re-runnable with a real provider via the command in the session handoff.
- **Trigger:** privacy/cost guarantee change (paid third party in the data path; amends §8.6 secrets + D-010) + §12.1 data model. Not an M-close.
- **Attached (11):** CLAUDE.md, SPEC.md, BACKLOG.md, ENGINEERING.md, DESIGN.md, DECISIONS.md, automation/lib/apify.py, automation/property_scrape.py, automation/lib/config.py, tests/test_apify.py, deploy/property_searches.example.json
- **Changes reviewed:** `reviews/session_changes_2026-06-16_D040.md`

---

## Response

### Concerns

**CRITICAL — gap-fill success consumed the once/day budget and could silently suppress a later backup.** The gate stamped on *any* Apify-using durable write and `used_apify` was set for gap-fill as well as backup; so a morning gap-fill (primary OK, one blank field) stamped the day, and an evening blocked-primary backup was then suppressed as a "no-op, not a failure" — a whole search's listings dropped for the day with no fail-flag. Violates hard requirement (2): no silent failure. *(Same class across searches: the global gate let search A's backup suppress search B's — SHOULD-FIX.)*

**SHOULD-FIX — §11 ≤₪120/mo ceiling is documented, not programmatically enforced.** Only controls are the once/day gate + per-search item/page caps; nothing reads a running cost. Bounded but unmeasured. Name it as monitored-not-enforced; consider a monthly result-counter cap.

**NIT — `_num` maps `0`→`None` for all numerics, incl. rooms/size** (honest-absence, not a violation; the "price on request" rationale is weaker for rooms/size — a quiet per-field semantic choice).

**NIT — `merge_listings` mutates primary in place** (fine in `gather`; mock path correctly de-aliased; undocumented contract is a latent foot-gun).

### Missed alternatives
- Per-search state record ("covered today: backup|gapfill|none") instead of one global stamp.
- Gate only backup on once/day; let gap-fill ride free (it judged gap-fill incremental).
- Cumulative monthly result-counter stamp as a real §11 backstop.
- Distinguish "genuine empty page" from "blocked" before deciding backup (an empty search burns a daily call).

### Affirmations
- Strict coercion contract genuinely well-built: bool-before-int guard, negative→error, corrupt→error-and-surface, absent→honest-None, item errors propagated to `res.errors`→fail-flag; tested. Requirement (2) met at row level.
- Network truly isolated in `_run_actor` with a `runner` seam; suite never hits network — mirrors `fetch_html`.
- "Primary always wins" correctly implemented as fill-blanks-only and tested — Apify cannot overwrite primary data. Requirement (1) holds.
- Backup-loud vs gap-fill-best-effort split coherent; both-sources-down re-appends `primary_err`.
- Token-gate inertness keeps the appliance untouched until deploy; "no credential storage" preserved (service key). Canon (SPEC §8.6/§12.1, DECISIONS, BACKLOG, config, example JSON) internally consistent.

### Concrete suggestions
- Gate the stamp on backup separately from gap-fill (track them apart) so gap-fill can't spend the backup budget.
- Make the once/day budget per-search, not global.
- Add a monthly result counter + cap for a real §11 backstop.
- Reconcile the test-count drift (253/+24 in canon vs 258/+29 in the session doc).

### One question for the team
Is the once/day budget meant to cap cost (then gate backup only) or all Apify traffic (then gap-fill must not silently cost tomorrow-morning's blocked-portal listings)?

---

## Resolution (Apply / Defend / Open)

- **CRITICAL → APPLIED.** Once/day gate redesigned to be **per-search AND per-kind** (`apify.load_run_stamp`/`ran_today`/`mark_run`; stamp shape `{"backup": {key: date}, "gapfill": {key: date}}`). Backup and gap-fill now hold independent daily budgets, so a gap-fill can never spend the backup's call, and one search never suppresses another. The team's question is answered in code: backup is load-bearing and is never silently skipped on a day it hasn't run; gap-fill is cosmetic and capped separately. New regression test `test_gapfill_does_not_consume_backup_budget` (fails on the old code). Suite **259 green**.
- **SHOULD-FIX #2 (global gate) → APPLIED** (subsumed by per-search keying).
- **SHOULD-FIX #3 (silent no-op signal) → APPLIED/MOOT** — with per-search backup-scoped gating, the only remaining no-op is "this search already backed up today," which is genuinely delayed-not-lost (logged, not a failure).
- **SHOULD-FIX #4 (cost ceiling not enforced) → OPEN, documented.** D-040 now states the §11 ceiling is monitored, not auto-enforced; bounded by per-search/per-day calls + caps. Monthly result-counter cap logged as a **v1.1 follow-up** (added to BACKLOG candidates).
- **NIT (0→None) → DEFEND.** Honest absence, never a fabricated value; documented in `_num`. Distinct from corrupt (negative→loud).
- **NIT (in-place merge) → APPLIED (doc).** `merge_listings` docstring now states the in-place contract; mock path already de-aliased.
- **Test-count drift → APPLIED.** Reconciled to 259 green / 29 in `tests/test_apify.py` across DECISIONS, BACKLOG, session-changes.

*Per ENGINEERING §11 a review never blocks; here it was run and resolved in-session, fixes applied pre-push. The external-provider (`review.py`) run remains available for the M4 "review on the live system" item (D-035 precedent).*
