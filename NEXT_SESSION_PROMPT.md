# Next session — Family Inc

*Generated 2026-06-20 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current focus only.

**Current focus: In progress — M6 finance ingestion**

Open items:

- M6.3 — consumer wiring + close. Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning is armed (`FINANCE_STALE_IMPORT_DAYS`). Budget-SUMIFS installer ran live …
- M6.4 — analysis layer. *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates …
- Parallel (Shanee). Budget migration — her manual budget → `Finance-Budget`; gives the actuals a target and defines the category vocab the rules engine maps to.

Recent commits (the dated decision record — decisions fold into the canon, not a separate log):

- 2026-06-20 feat: M6.3 budget installer — live stamp + harden against absent machine headers
- 2026-06-20 docs: M6.3 live budget-SUMIFS install — stamped + J-header drift fixed
- 2026-06-20 chore: regenerate NEXT_SESSION_PROMPT (M6.3 installer + dashboard wiring landed)
- 2026-06-20 fix: M6.3 dashboard Money drawer — exclude Finance-Budget TOTAL row (double-count)
- 2026-06-20 chore: gitignore .claude/ (local Claude Code settings + locks)
- 2026-06-20 feat: M6.3 budget-SUMIFS installer — idempotent live formula stamp (lib/finance_budget + CLI)

Session contract: don't open lanes outside the current focus without a PO call ·
constants → config, utilities → `automation/lib/`, message copy → templates ·
a directional call = edit the relevant canon doc to the new present-tense state
(short inline *why* if non-obvious) with the dated rationale in the commit message ·
session end: tests green if code moved, `BACKLOG.md` flipped, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
