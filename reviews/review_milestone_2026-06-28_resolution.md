# Milestone review resolution — M6 finance close (2026-06-28)

Review: `reviews/review_milestone_2026-06-28_16-20.md` (DeepSeek, milestone lane).
**Outcome: 0 blockers.** 1 HIGH, 2 MEDIUM, 2 LOW — resolved Apply / Defend / Open below.

## Concerns

**C1 (HIGH) — overlay deferred without a timely check-in → APPLY (partial) + DEFEND.**
- *Apply:* converted the open-ended deferral into a dated condition — **revisit 2026-07-12**
  (~2 weeks of live data): does the recurring local-grocery undercount *materially* dent
  `Finance-Budget` Groceries actuals? If yes, pull the overlay forward; else confirm the
  deferral. Landed in `ROADMAP.md` rank 12.1 + §3.7 and the `BACKLOG.md` Focus note.
- *Defend:* building the overlay **this** session is out — the PO explicitly chose "accept
  88%, close now" over opening the overlay lane mid-gate (don't bolt a new lane onto a
  milestone close). The reviewer's `bank_creds.json` string-prefix bridge is a degenerate,
  untested version of the same overlay → rejected in favour of building the real thing if
  the 07-12 check-in says it matters.

**C2 (MEDIUM) — "backfill bypasses the LLM gap-fill" → DEFEND + APPLY (precision).**
- *Defend:* factually wrong. `finance_recategorize.run(allow_llm=True)` by default
  (`automation/finance_recategorize.py:95,142,219`); the summary prints `rules + DeepSeek`;
  the **live 06-28 run** categorized **5 rows via the LLM** (`rules 0 · llm 5`). The backfill
  re-runs **both** stages; `--no-llm` is the explicit opt-down (and what the dry-run uses).
- *Apply:* the reviewer correctly caught that the *prose* was ambiguous ("re-runs the same
  engine"). Tightened `SPEC.md` §12.2 to "re-runs **both engine stages** (rules → LLM
  gap-fill; `--no-llm` opts down to rules-only)".

**C3 (MEDIUM) — no combinatorial exclusion×merchant invariant test → DEFEND + APPLY (pin).**
- *Defend:* it already exists. `tests/test_finance.py::test_excluded_bucket_never_shadows_a_merchant`
  (line 417) iterates **every excluded pattern × every merchant pattern** and asserts the
  merchant wins — exactly the bi-directional test requested. OBSIDIAN, now a merchant rule,
  is auto-covered by construction. (The reviewer saw only the doc, not the test.)
- *Apply:* added a **positive** pin `apply_rules("OBSIDIAN.MD MEMBERSHIP") == "Shopping"` in
  `test_rules_engine_maps_known_merchants` so the new rule has direct coverage, not only the
  ordering sweep.

**C4 (LOW) — §7 recipe fix not enforced by deploy.sh/CI → DEFEND.**
- The *scheduled* finance runs already use these exact invocations via the systemd units
  (`family-finance.service` etc. = `uv run --no-sync python …`) — that is the enforced path,
  and the §7 manual recipe now matches it. A bare `python3` as root **fails loud** (no creds,
  no deps), so a regression is self-correcting, not silent. CI-grepping a markdown recipe adds
  process without removing a real risk; CI cannot stop an operator mistyping at a prompt.

**C5 (LOW) — installer misses a human column *swap* → OPEN.**
- Fair hardening, but on `finance_budget_formulas.py` — **settled, out-of-this-diff** code.
  Tracked as a finance-hardening test-gap (Lane E): a column-**content** sanity check at
  install (sample a `Category` cell, assert it holds a known-vocab value) to catch a drag
  that the head-presence guard passes. Not a blocker for the M6 close.

## Affirmations (noted, no action)
Report-first 88% bar · structural reframing of the blanks · OBSIDIAN-mid-close · Card
Settlement below merchant rules · deferring the correctness-FP metric (rank 12).

## Net
3 applied (timed check-in · SPEC precision · OBSIDIAN pin), 3 defended, 1 opened (tracked).
No blocker; M6 close proceeds. Suite stays green.
