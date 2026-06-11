# Backlog

*The only live backlog. Status legend: ⬜ todo · 🔵 in progress · ✅ done · 🧊 frozen.*
*v1 definition and acceptance criteria live in `SPEC.md` §11. Migration session plan lives in `ENGINEERING.md` §9.*

## v1 — to first real message on both phones

### M1 — Repo restructure (1 session)

- ⬜ Create `automation/lib/` (`sheet.py`, `llm.py`, `outbox.py`, `dates.py`, `money.py`, `config.py`) — single implementations, scripts import from lib
- ⬜ Delete root-level `reminders_engine.py` + `sunday_briefing.py` (canonical copies live in `automation/`)
- ⬜ Move frozen scripts → `attic/` (see Frozen lanes below)
- ⬜ Purge Twilio references from code + runbooks (fallback documented only in `SPEC.md` §10)
- ⬜ Update `review.py` lane defaults + always-attach list to the new canon docs (it still references archived paths)
- ⬜ Remove hand-written future-dated files from `Briefings/`; add `briefings/fixtures/` for test fixtures
- ⬜ `pytest` scaffolding + first tests green (tombstone window, budget ledger, recurrence bump, classifier hard rules)

### M2 — One source of truth (1 session)

- ⬜ gspread port: engine, briefings, summarizer all read/write the live Google Sheet via service account
- ⬜ Dashboard writes `DoneAt` + `LastDoneBy` + `WriteQueue_Tombstone` in every write-back batch (closes the spec'd-but-missing race guard)
- ⬜ `Settings` tab: `UserMap` (email → display name) + `lang`
- ⬜ Outbox budget ledger: all senders queue through `lib/outbox.py`; 2/day cap enforced there; `critical` bypass flag; briefings exempt
- ⬜ Strip reply-command footers from message templates (reinstate in v1.1 with reply parsing)
- ⬜ Golden-file tests for briefing + digest rendering

### M3 — Appliance live = go-live (1 session + ~1h on the VPS)

- ⬜ Provision VPS per `ENGINEERING.md` §5 (user, TZ=Asia/Jerusalem, uv, Node LTS, systemd units)
- ⬜ Pair Baileys (one QR scan); place `recipients.json` + service-account JSON + `ANTHROPIC_API_KEY` in `/etc/family-inc/`
- ⬜ Enable timers: engine 07:25 · digest 07:30 · summarizer hourly (24h) · weekly briefing Sat 21:00 · backup Sun 03:00
- ⬜ Seed ≥20 real reminders across Car/Health/Education/Contracts (from `Setup/08` seed + kickoff backlog)
- ⬜ **Acceptance: both phones receive the morning digest 3 consecutive days; one full done→recur cycle visible in the log**
- ⬜ GitHub Pages live for `Dashboard/`; PWA pinned on both phones

### M4 — Summarizer hardening (1 session, after ≥1 week live)

- ⬜ Sender→role roster seeded (makes hard rules 2–3 reliable)
- ⬜ Phase F weekly accuracy review surface (false-positive purge)
- ⬜ PO call (joint): do family-group criticals override digest-only routing?
- ⬜ Milestone review (external model) on the live system

## v1.1 candidates (unordered — pick after v1 is boring)

- Reply parsing (done/snooze via WhatsApp) — *unlocks reinstating reply footers*
- Inbox-append trigger for the classifier (inotify on `inbox.jsonl`) — sub-hour critical latency without changing the hourly digest cadence *(review suggestion, 2026-06-12)*
- Google Calendar connector → Calendar-Events auto-populated
- iCloud → GCal ICS subscribe (15 min, `Setup/05`)
- Reminders `Priority` column + bulk-done flow
- Hebrew chrome string completion pass

## Frozen lanes 🧊

*Frozen = script moves to `attic/`, runbook to `Archive/`, no maintenance. Unfreeze = the stated condition is true AND v1 acceptance has held for 30 days.*

| Lane | Assets | Unfreeze condition |
|---|---|---|
| Finance ingestion | bank-scraper plan, `Setup/01` | POs commit to monthly finance review using the data |
| Hebrew categorizer | `hebrew_categorizer.py` | Finance ingestion live |
| Anomaly / subscription detector | `anomaly_detector.py` | ≥90 days of real transactions in the Sheet |
| Pediatric milestones | `pediatric_milestones.py`, `Setup/09` | Health tab actively maintained |
| Goal coaching | `goal_coaching.py` | Goals updated weekly for a month (proves the habit exists) |
| PDF→event, receipt OCR, voice capture, Yad2/Madlan/Dira trackers, Gmail bill parser, Maccabi forwarders | `pdf_to_event.py`, `dira_tracker.py`, `Setup/02,03,04,06,07` | Per-item PO request, one at a time |
