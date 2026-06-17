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

- D-052 (2026-06-17): M6.1 — finance-ingestion repo half BUILT (hermetic, no appliance) + the finance tab names standardized to full forms (PO "standardize now").…
- D-051 (2026-06-17): §8.6 amended: DeepSeek may process finance-transaction text for categorization gap-fill (joint — Shanee approved); resolves D-050's gate. Th…
- D-050 (2026-06-17): Finance scope expanded from raw-only to categorized + trends (PO call, Adar; reverses D-033's categorizer kill — anomaly detection stays kil…
- D-049 (2026-06-17): Finance-ingestion lane UNFROZEN (joint — Adar + Shanee co-signed); the "no credential storage" non-goal AMENDED to permit read-only bank/car…
- D-048 (2026-06-17): Phase-F weekly classifier accuracy review surface BUILT — front-loaded by PO call (D-044 precedent); the first real review run + the externa…

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
