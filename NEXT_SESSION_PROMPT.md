# Next session — Family Inc

*Generated 2026-06-17 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current milestone only.

**Current milestone: M4 — Summarizer hardening (build items landed 2026-06-16, D-044; reviews after ≥1 week live, ~2026-06-20)**

Open items:

- ⬜ Milestone review (external model) on the live system — **gated**; folds in the M5 review (D-035/D-043 precedent)

Recent decisions (full log in `DECISIONS.md`):

- D-049 (2026-06-17): Finance-ingestion lane UNFROZEN (joint — Adar + Shanee co-signed); the "no credential storage" non-goal AMENDED to permit read-only bank/car…
- D-048 (2026-06-17): Phase-F weekly classifier accuracy review surface BUILT — front-loaded by PO call (D-044 precedent); the first real review run + the externa…
- D-047 (2026-06-17): Milestone-lane review of the debrief + D-046 resolved; the weekly briefing is confirmed TEMPLATE-ONLY by design (PO call, Adar) — SPEC/DESIG…
- D-046 (2026-06-17): WhatsApp classifier JSON parse made trailing-prose-tolerant + DeepSeek strict JSON mode — fixes a silent accuracy leak found live during the…
- D-045 (2026-06-17): Daily briefing is partner-symmetric every day — an asymmetric day (one adult has reminders, the other none) now briefs BOTH adults (PO call,…

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
