# Next session — Family Inc

*Generated 2026-06-12 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current milestone only.

**Current milestone: M2 — One source of truth (1 session)**

Open items:

- ⬜ gspread port: engine, briefings, summarizer all read/write the live Google Sheet via service account (behind `lib/sheet.py`; add the §7.1 header-validation schema-drift guard while in there)
- ⬜ Engine write-backs on send success: `Last Sent`/`Status` stamping from `daily_digest`, recurrence bump on Done incl. Feb-29 + Last-Sent idempotency tests (ENGINEERING §7 rows deferred from M1 — no write path existed against the seed xlsx)
- ⬜ Dashboard writes `DoneAt` + `LastDoneBy` + `WriteQueue_Tombstone` in every write-back batch (closes the spec'd-but-missing race guard)
- ⬜ `Settings` tab: `UserMap` (email → display name) + `lang`
- ⬜ Outbox consolidation: summarizer + reply paths move from `queue_message()` (legacy shim) to `queue()` with kinds + stable `wa-{msg_id}` ids; delete the shim and the summarizer's local budget counter (the `lib/outbox.py` ledger from M1 becomes the only enforcement — D-015)
- ⬜ Strip reply-command footers from message templates (D-014; reinstate in v1.1 with reply parsing) — deliberate golden-file regen (`tests/test_render_golden.py --regen`), DESIGN §6 Hebrew templates land here too
- ⬜ Golden-file tests for briefing + digest rendering — *base goldens shipped in M1; M2 re-cuts them with the template swap*

Recent decisions (full log in `DECISIONS.md`):

- D-024 (2026-06-12): Personal-data purge of the tracked tree (M1). Seed CSVs (reminders/vaccines/goals/group-config) → gitignored `seeds/`; `Dashboard/config.js`…
- D-023 (2026-06-12): Port Porto workflow patterns: D-numbered decisions, `Automation/session_kickoff.py` regenerating `NEXT_SESSION_PROMPT.md` each session end, …
- D-022 (2026-06-12): Hermes parallel sprint integrated. A second AI session ("Hermes") had pushed 15 commits to origin from another clone; 10 code commits cherry…
- D-021 (2026-06-12): Sessions must `git pull --ff-only` before any work; origin is the sync point between agents (session protocol step 0)
- D-020 (2026-06-12): Remake milestone review run (DeepSeek; Gemini unavailable this session) and resolved: 6 applies (schema-drift guard, data-driven tombstone t…

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
