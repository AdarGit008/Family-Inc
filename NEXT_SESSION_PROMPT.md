# Next session — Family Inc

*Generated 2026-06-23 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current focus only.

**Current focus: In progress — M6 finance ingestion**

Open items:

- M6.3 — consumer wiring + close. Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning is armed (`FINANCE_STALE_IMPORT_DAYS`). Budget-SUMIFS installer ran live …
- M6.4 — analysis layer. *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates …
- M6.5 — cards lane (un-deferred 2026-06-23, the third VPS hour). Cal (Visa) is live — hooked up via a one-time headed `--auth` device-trust login (xvfb + x11vnc over an SSH tunnel; `FINANCE.md §4`) …
- Parallel (Shanee). Budget migration — her manual budget → `Finance-Budget`; gives the actuals a target and defines the category vocab the rules engine maps to.

Recent commits (the dated decision record — decisions fold into the canon, not a separate log):

- 2026-06-23 feat(finance): hook up Cal (Visa) + Card Settlement exclusion — un-defer cards lane (M6.5)
- 2026-06-23 docs: next-session opener — add Cal/Visa card (un-defers cards lane, reframes categorization)
- 2026-06-23 docs: close 2026-06-23 VPS hour — lane-7 box verification, CI gate merged, finance lib bump
- 2026-06-23 fix(finance): bump israeli-bank-scrapers 6.7.3 -> 6.7.8
- 2026-06-23 fix(ci): pin setup-uv to @v7 — @v8 floating tag is unresolvable
- 2026-06-22 feat: hardening lane 1 — pre-merge CI gate + repo-wide PII guard + config.js smoke

Session contract: don't open lanes outside the current focus without a PO call ·
constants → config, utilities → `automation/lib/`, message copy → templates ·
a directional call = edit the relevant canon doc to the new present-tense state
(short inline *why* if non-obvious) with the dated rationale in the commit message ·
session end: tests green if code moved, `BACKLOG.md` flipped, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
