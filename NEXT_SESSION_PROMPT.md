# Next session — Family Inc

*Generated 2026-06-17 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current milestone only.

**Current milestone: M4 — Summarizer hardening (build items landed 2026-06-16, D-044; reviews after ≥1 week live, ~2026-06-20)**

Open items:

- ⬜ Phase F weekly accuracy review surface (false-positive purge) — **gated** to the ≥1-week-live window (~2026-06-20)
- ⬜ Milestone review (external model) on the live system — **gated**; folds in the M5 review (D-035/D-043 precedent)

Recent decisions (full log in `DECISIONS.md`):

- D-045 (2026-06-17): Daily briefing is partner-symmetric every day — an asymmetric day (one adult has reminders, the other none) now briefs BOTH adults (PO call,…
- D-044 (2026-06-16): M4 gate-free build items pulled forward (DeepSeek wired · WhatsApp_Inbox rolloff · quiet-day symmetry · sender-role roster); the two review …
- D-043 (2026-06-16): M5 (property tracker) CLOSED — live on the appliance. Deployed the same day as the local build (D-037) and verified end-to-end on the VPS: t…
- D-042 (2026-06-16): Apify item-level error policy relaxed: skip junk rows everywhere, fail loud only when a call returns items but ZERO usable listings (broken …
- D-041 (2026-06-16): Test suite made hermetic vs the appliance's email-fallback creds (extends D-038 from the Sheet to the SMTP transport). Caught at the M5 depl…

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
