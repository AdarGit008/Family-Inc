# Next session — Family Inc

*Generated 2026-06-12 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current milestone only.

**Current milestone: M3 — Appliance live = go-live (1 session + ~1h on the VPS)**

Open items:

- ⬜ Provision VPS per `ENGINEERING.md` §5 (user, TZ=Asia/Jerusalem, uv, Node LTS, systemd units)
- ⬜ Pair Baileys (one QR scan); place `recipients.json` + service-account JSON + `ANTHROPIC_API_KEY` **+ `FAMILY_INC_SHEET_ID`** in `/etc/family-inc/` (the sheet id is what flips `lib/sheet.py` to the live backend — without it everything keeps running dry against the seed)
- ⬜ Enable timers: engine 07:25 · digest 07:30 · summarizer hourly (24h) · weekly briefing Sat 21:00 · backup Sun 03:00
- ⬜ Seed ≥20 real reminders across Car/Health/Education/Contracts (from `Setup/08` seed + kickoff backlog)
- ⬜ **Acceptance: both phones receive the morning digest 3 consecutive days; one full done→recur cycle visible in the log**
- ⬜ GitHub Pages live for the dashboard; PWA pinned on both phones (`Dashboard/`→`dashboard/` case rename + `deploy/` scripts land here, with the Pages wiring; copy real `seeds/` + `Dashboard/config.js` to the machines that need them — both untracked since M1/D-024)

Recent decisions (full log in `DECISIONS.md`):

- D-026 (2026-06-12): M2 milestone review run (DeepSeek) and resolved: 2 wording applies (SPEC §8.3 one-clock tombstone semantics; §7.1 validate-before-write clau…
- D-025 (2026-06-12): M2 contract resolutions (one source of truth port). (a) SPEC §7.1 errata: engine reads Status ∉ {Done, Skipped} — the spec'd ∈ {Pending, Sno…
- D-024 (2026-06-12): Personal-data purge of the tracked tree (M1). Seed CSVs (reminders/vaccines/goals/group-config) → gitignored `seeds/`; `Dashboard/config.js`…
- D-023 (2026-06-12): Port Porto workflow patterns: D-numbered decisions, `Automation/session_kickoff.py` regenerating `NEXT_SESSION_PROMPT.md` each session end, …
- D-022 (2026-06-12): Hermes parallel sprint integrated. A second AI session ("Hermes") had pushed 15 commits to origin from another clone; 10 code commits cherry…

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
