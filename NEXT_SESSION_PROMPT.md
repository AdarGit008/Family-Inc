# Next session — Family Inc

*Generated 2026-06-11 by `Automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current milestone only.

**Current milestone: M1 — Repo restructure (1 session)**

Open items:

- ⬜ Create `automation/lib/` (`sheet.py`, `llm.py`, `outbox.py`, `dates.py`, `money.py`, `config.py`) — single implementations, scripts import from lib. `Automation/config.py` exists; move + absorb remaining script-level constants
- ⬜ Delete root-level `reminders_engine.py` + `sunday_briefing.py` (canonical copies live in `automation/`)
- ⬜ Move frozen scripts → `attic/` (see Frozen lanes below); archive `Progress/` status page (status lives only here)
- ⬜ Purge Twilio references from code + runbooks (fallback documented only in `SPEC.md` §10)
- ⬜ Update `review.py` lane defaults + always-attach list to the new canon docs (it still references archived paths); fold `run_review_deepseek.py` in as a provider
- ⬜ Gitignore generated `Briefings/` output (re-apply skipped Hermes commit `556f445` deliberately); move review/audit artifacts to a tracked `reviews/` dir + update `ENGINEERING.md` §11 paths; remove hand-written future-dated files; add `tests/fixtures/`
- ⬜ Extend the Hermes pytest suite (55 green: engine + briefing) to cover outbox budget ledger, classifier hard rules, golden-file rendering; rename to match target layout
- ⬜ Convert `requirements*.txt` → uv (`pyproject.toml` + lockfile) per `ENGINEERING.md` §2

Recent decisions (full log in `DECISIONS.md`):

- D-023 (2026-06-12): Port Porto workflow patterns: D-numbered decisions, `Automation/session_kickoff.py` regenerating `NEXT_SESSION_PROMPT.md` each session end, …
- D-022 (2026-06-12): Hermes parallel sprint integrated. A second AI session ("Hermes") had pushed 15 commits to origin from another clone; 10 code commits cherry…
- D-021 (2026-06-12): Sessions must `git pull --ff-only` before any work; origin is the sync point between agents (session protocol step 0)
- D-020 (2026-06-12): Remake milestone review run (DeepSeek; Gemini unavailable this session) and resolved: 6 applies (schema-drift guard, data-driven tombstone t…
- D-019 (2026-06-11): Full remake. Canon docs = `SPEC.md` + `ENGINEERING.md` + `DESIGN.md` + `DECISIONS.md` + `BACKLOG.md`; superseded docs → `Archive/`

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 Automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
