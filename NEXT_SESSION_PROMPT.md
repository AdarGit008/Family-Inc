# Next session — Family Inc

*Generated 2026-06-16 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current milestone only.

**Current milestone: M4 — Summarizer hardening (1 session, after ≥1 week live)**

Open items:

- ⬜ Sender→role roster seeded (makes hard rules 2–3 reliable)
- ⬜ Phase F weekly accuracy review surface (false-positive purge)
- ⬜ Milestone review (external model) on the live system

Recent decisions (full log in `DECISIONS.md`):

- D-040 (2026-06-16): Apify added as the property lane's SECONDARY data source (managed-unblocker rung; the on-box scraper stays primary). D-039's verdict stood —…
- D-039 (2026-06-16): Property scraper → headed Chromium under Xvfb + light stealth, to pass the Yad2/Madlan anti-bot wall (the D-034 escape hatch, first/free run…
- D-038 (2026-06-16): Test suite made hermetic vs the live Google Sheet; `deploy.sh` strips `FAMILY_INC_SHEET_ID` for tests (caught at M5 deploy). M5's first `dep…
- D-037 (2026-06-15): M5 property-tracker — local build landed (executed by PO; built one day before the §12.1 "earliest 2026-06-16" gate). v1 was accepted + M3 c…
- D-036 (2026-06-15): Hardening pass + open-question close-out (special session; plan-only, executed by PO; Adar + Shanee sign-off). (a) Three Cowork scheduled ta…

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
