# Next session — Family Inc

*Generated 2026-06-12 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current milestone only.

**Current milestone: M3 — Appliance live = go-live (repo side ✅ 2026-06-12 session 1; remaining = PO's ~1h at the VPS, runbook: `deploy/README.md`)**

Open items:

- ⬜ The VPS hour: provision → secrets in `/etc/family-inc/` (incl. `FAMILY_INC_SHEET_ID`, the live-backend flip, + SMTP creds for §10.2) → pair Baileys → verify timers → import seeds → enable Pages (Source=GitHub Actions + the two secrets + OAuth origin) → pin PWA on both phones → one green `backup.sh` run
- ⬜ **Acceptance: both phones receive the morning digest 3 consecutive days; one full done→recur cycle visible in the log** → then flip CLAUDE.md "Current state", tag `v1-live`, M4 after ≥1 week

Recent decisions (full log in `DECISIONS.md`):

- D-027 (2026-06-12): M3 session-1 contract resolutions (delivery infrastructure). (a) Daily digest queues kind=briefing — it was kind=alert, consuming 1 of the 2…
- D-026 (2026-06-12): M2 milestone review run (DeepSeek) and resolved: 2 wording applies (SPEC §8.3 one-clock tombstone semantics; §7.1 validate-before-write clau…
- D-025 (2026-06-12): M2 contract resolutions (one source of truth port). (a) SPEC §7.1 errata: engine reads Status ∉ {Done, Skipped} — the spec'd ∈ {Pending, Sno…
- D-024 (2026-06-12): Personal-data purge of the tracked tree (M1). Seed CSVs (reminders/vaccines/goals/group-config) → gitignored `seeds/`; `Dashboard/config.js`…
- D-023 (2026-06-12): Port Porto workflow patterns: D-numbered decisions, `Automation/session_kickoff.py` regenerating `NEXT_SESSION_PROMPT.md` each session end, …

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
