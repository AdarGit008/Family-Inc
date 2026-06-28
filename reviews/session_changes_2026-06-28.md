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
