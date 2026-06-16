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

- D-043 (2026-06-16): M5 (property tracker) CLOSED — live on the appliance. Deployed the same day as the local build (D-037) and verified end-to-end on the VPS: t…
- D-042 (2026-06-16): Apify item-level error policy relaxed: skip junk rows everywhere, fail loud only when a call returns items but ZERO usable listings (broken …
- D-041 (2026-06-16): Test suite made hermetic vs the appliance's email-fallback creds (extends D-038 from the Sheet to the SMTP transport). Caught at the M5 depl…
- D-040 (2026-06-16): Apify added as the property lane's SECONDARY data source (managed-unblocker rung; the on-box scraper stays primary). D-039's verdict stood —…
- D-039 (2026-06-16): Property scraper → headed Chromium under Xvfb + light stealth, to pass the Yad2/Madlan anti-bot wall (the D-034 escape hatch, first/free run…

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
