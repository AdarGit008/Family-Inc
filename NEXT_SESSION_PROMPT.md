# Next session — Family Inc

*Generated 2026-06-17 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current focus only.

**Current focus: In progress — M6 finance ingestion**

Open items:

- M6.2 — appliance deploy + first interactive auth (the "VPS hour"). Place `bank_creds.json` (mode 600); rename the 3 live-Sheet tabs to the f…
- M6.3 — consumer wiring + close. Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning fires. Acceptance =…
- M6.4 — analysis layer. The on-box rules engine (`seeds/14_Finance_Category_Rules.csv`) populates `Category`/`Cat-Source` at ingest; DeepSeek…
- Parallel (Shanee). Budget migration — her manual budget → `Finance-Budget`; gives the actuals a target and defines the category vocab the ru…

Recent commits (the dated decision record — decisions fold into the canon, not a separate log):

- 2026-06-18 docs: consolidate canon (SPEC bump) — present-tense rewrite; D-NN log retired to Archive/
- 2026-06-17 M6.1 review fixes (D-052): .gitignore bank_creds Blocker, SPEC 12.2 auth honesty, +tests
- 2026-06-17 M6.1: finance ingestion repo half + finance tab standardization (D-052)
- 2026-06-17 plan: finance LLM gap-fill approved (D-051) - 8.6 amended, Shanee
- 2026-06-17 plan: finance analysis layer (D-050) - categories and trends, LLM gap-fill gated on Shanee
- 2026-06-17 plan: finance ingestion thaw (D-049 co-signed); M6 + SPEC 12.2

Session contract: don't open lanes outside the current focus without a PO call ·
constants → config, utilities → `automation/lib/`, message copy → templates ·
a directional call = edit the relevant canon doc to the new present-tense state
(short inline *why* if non-obvious) with the dated rationale in the commit message ·
session end: tests green if code moved, `BACKLOG.md` flipped, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
