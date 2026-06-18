# Next session — Family Inc

*Generated 2026-06-18 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current focus only.

**Current focus: In progress — M6 finance ingestion**

Open items:

- M6.2 — appliance deploy + first live auth (the "VPS hour"). Place `bank_creds.json` (mode 600); rename the 3 live-Sheet tabs to the full nam…
- M6.3 — consumer wiring + close. Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning fires. Acceptance =…
- M6.4 — analysis layer. *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/1…
- Parallel (Shanee). Budget migration — her manual budget → `Finance-Budget`; gives the actuals a target and defines the category vocab the ru…

Recent commits (the dated decision record — decisions fold into the canon, not a separate log):

- 2026-06-18 fix: Brief-1 audit lane — 1 blocker + 7 majors (B1–B8)
- 2026-06-18 reviews: full-project audit + two self-contained fix briefs
- 2026-06-18 M6.4: finance categorizer + budget reconciliation (D-050/051)
- 2026-06-18 tools: repoint review.py + session_kickoff.py off the retired D-NN log
- 2026-06-18 docs: consolidate canon (SPEC bump) — present-tense rewrite; D-NN log retired to Archive/
- 2026-06-17 M6.1 review fixes (D-052): .gitignore bank_creds Blocker, SPEC 12.2 auth honesty, +tests

Session contract: don't open lanes outside the current focus without a PO call ·
constants → config, utilities → `automation/lib/`, message copy → templates ·
a directional call = edit the relevant canon doc to the new present-tense state
(short inline *why* if non-obvious) with the dated rationale in the commit message ·
session end: tests green if code moved, `BACKLOG.md` flipped, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
