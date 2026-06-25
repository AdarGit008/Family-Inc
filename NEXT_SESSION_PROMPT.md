# Next session — Family Inc

*Generated 2026-06-25 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

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

- 2026-06-25 feat(dashboard): V3.1 — cool token retone (IBM Plex Mono all-numerals, AA-cleared amber/muted)
- 2026-06-25 docs(v3): resolve the 4 Today-redesign build blockers + add file-level build plan
- 2026-06-25 docs: regenerate next-session prompt (post-rebase)
- 2026-06-25 fix(finance): move Card Settlement exclusion below merchant rules — close the latent over-match (M6.5)
- 2026-06-25 docs(roadmap): add v3 Today-redesign lane (§3.8) + decision record
- 2026-06-23 feat(finance): hook up Shanee's debit card via the connected Cal login (M6.5)

Session contract: don't open lanes outside the current focus without a PO call ·
constants → config, utilities → `automation/lib/`, message copy → templates ·
a directional call = edit the relevant canon doc to the new present-tense state
(short inline *why* if non-obvious) with the dated rationale in the commit message ·
session end: tests green if code moved, `BACKLOG.md` flipped, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
