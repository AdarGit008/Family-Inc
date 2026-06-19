# Next session — Family Inc

*Generated 2026-06-19 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current focus only.

**Current focus: In progress — M6 finance ingestion**

Open items:

- M6.2 — appliance deploy + first live auth (the "VPS hour"). Place `bank_creds.json` (mode 600); rename the 3 live-Sheet tabs to the full names; Mizrahi first → verify CSV→Sheet roundtrip live → Max + …
- M6.3 — consumer wiring + close. Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning fires. Acceptance = the first real monthly review (~30 days in).
- M6.4 — analysis layer. *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates …
- Parallel (Shanee). Budget migration — her manual budget → `Finance-Budget`; gives the actuals a target and defines the category vocab the rules engine maps to.

Recent commits (the dated decision record — decisions fold into the canon, not a separate log):

- 2026-06-19 fix: GAP-2 + outbox-budget#3 — cross-run delivery reconcile (Brief 3, Lane B)
- 2026-06-19 reviews: GAP-2 delivery-reconcile session opener (Brief 3)
- 2026-06-18 fix: Brief-2 Lane B (partial) — outbox/delivery integrity (budget#1/#2, GAP-8, GAP-10)
- 2026-06-18 fix: Brief-2 Lane S — publish/privacy safety (GAP-5 + deploy-systemd#4)
- 2026-06-18 fix: Brief-2 small fixes — Lane A (finance hardening) + Lane E canon hygiene
- 2026-06-18 fix: Brief-1 audit lane — 1 blocker + 7 majors (B1–B8)

Session contract: don't open lanes outside the current focus without a PO call ·
constants → config, utilities → `automation/lib/`, message copy → templates ·
a directional call = edit the relevant canon doc to the new present-tense state
(short inline *why* if non-obvious) with the dated rationale in the commit message ·
session end: tests green if code moved, `BACKLOG.md` flipped, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
