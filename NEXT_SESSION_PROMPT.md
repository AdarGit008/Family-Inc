# Next session — Family Inc

*Generated 2026-06-15 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

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

- D-037 (2026-06-15): M5 property-tracker — local build landed (executed by PO; built one day before the §12.1 "earliest 2026-06-16" gate). v1 was accepted + M3 c…
- D-036 (2026-06-15): Hardening pass + open-question close-out (special session; plan-only, executed by PO; Adar + Shanee sign-off). (a) Three Cowork scheduled ta…
- D-035 (2026-06-15): M3 (go-live) CLOSED — v1 accepted, tagged `v1-live`. The SPEC §11 acceptance window (2026-06-13→15, clock from the D-029 Baileys-7 re-pair) …
- D-034 (2026-06-13): Property tracker (Yad2/Madlan) UNFROZEN — active house search (data-fetching planning session). The only lane unfrozen this session. Build s…
- D-033 (2026-06-13): Frozen-lane dispositions (data-fetching planning session). (a) Finance ingestion (L1) stays frozen — no commitment yet to the ~20–30 min/mon…

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
