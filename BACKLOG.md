# Backlog

*The only live backlog. Status legend: ⬜ todo · 🔵 in progress · ✅ done · 🧊 frozen.*
*v1 definition and acceptance criteria live in `SPEC.md` §11. Migration session plan lives in `ENGINEERING.md` §9.*

**Now:** next milestone = **M3** (go-live; needs the PO at the VPS ~1h) · open via `NEXT_SESSION_PROMPT.md` · last session: 2026-06-12 (M2 closed: gspread port + write-backs + outbox consolidation + Hebrew templates + 172 tests + D-025)

## v1 — to first real message on both phones

### M1 — Repo restructure (1 session) — ✅ closed 2026-06-12

*2026-06-12 head start: the integrated Hermes sprint already delivered `Automation/config.py` (shared constants), a 55-test pytest suite (`tests/`), `requirements*.txt`, and `reply_handler.py` — several items below started from that base instead of zero.*

- ✅ Create `automation/lib/` (`sheet.py`, `llm.py`, `outbox.py`, `dates.py`, `money.py`, `config.py`) — single implementations, scripts import from lib; `outbox.queue()` implements the full SPEC §7.5 contract (ledger, kinds, dedup, quiet-hours `not_before`); LLM fake via `FAMILY_INC_LLM_FAKE`
- ✅ Delete root-level `reminders_engine.py` + `sunday_briefing.py` — engine moved to `automation/` as compute-only, `sunday_briefing` → `weekly_briefing.py`, send path carved into `automation/daily_digest.py` (ENGINEERING §9), copy → `automation/templates.py`
- ✅ Move frozen scripts → `attic/` (incl. `friday_briefing.py`, `bank-scraper/`, `Setup/code` → `attic/setup_code`); `Progress/` + frozen-lane runbooks + `00_Runbook.md` → `Archive/`
- ✅ Purge Twilio from code + runbooks (zero refs in code; fallback documented only in `SPEC.md` §10 — acceptance #7 grep is clean)
- ✅ `review.py`: canon-doc always-attach + lane defaults, new `milestone` lane, DeepSeek provider folded in (`--provider deepseek`, `--chunk`), audit output → `reviews/`
- ✅ Gitignore `Briefings/` + `logs/` (re-applied 556f445); review/audit artifacts → tracked `reviews/`; deleted future-dated briefings (06-23, 08-15); `tests/fixtures/` golden files
- ✅ Tests 55 → **115 green**: `test_outbox.py` (2-cap, critical bypass, briefing exemption, shared ledger, dedup, quiet hours), `test_summarizer.py` (5 hard rules, routing, NEEDS-A-LOOK, fallback, LLM-fake), `test_render_golden.py` (5 goldens), `test_sheet.py` (parsing tolerance), renamed `test_engine.py`/`test_briefing.py`
- ✅ uv conversion: `pyproject.toml` + `uv.lock` committed; dropped beautifulsoup4 + python-dateutil (consumers live in attic); `requirements*.txt` deleted
- ✅ D-024 privacy purge: `seeds/` gitignored (CSVs moved from `Setup/`), `Dashboard/config.js` untracked (+`config.example.js`), kid names/birthdates scrubbed from attic + review prompt

### M2 — One source of truth (1 session) — ✅ closed 2026-06-12

- ✅ gspread port: `lib/sheet.py` = two backends behind one surface (gspread+service-account when `FAMILY_INC_SHEET_ID` set, seed xlsx otherwise); engine/digest/briefing/summarizer all route through it; §7.1 header-validation guard on every Reminders read AND write (abort + `logs/schema_drift.flag`, healed by a clean read, surfaced by the weekly briefing); seed xlsx headers aligned to SPEC §6.1 (cols M–P added)
- ✅ Engine write-backs: `daily_digest --send` stamps `Last Sent`/`Status` (Sent|Overdue) only for rows actually queued; recurrence bump on Done (`Due+period`, `Status→Pending`, `Last Sent` cleared; Feb-29-class → month-end clamp + review flag; Custom → flagged, never guessed; tombstoned rows wait a run); classify gained the same-day Last-Sent guard — rerun is a no-op at every layer; creds-less runs never write the seed
- ✅ Dashboard write contract: stopped writing engine-owned col H (clears it on bump per §7.1); `bumpDate()` now mirrors `lib/dates.bump_due` (clamp, no Daily, Custom→null); DoneAt/Tombstone are full ISO-T datetimes (date-only tombstones had killed the 6h window); **tombstones re-stamped at flush time** (§8.3) — the actually-missing race guard
- ✅ `Settings` tab (Key|Value): UserMap + lang; `lib/sheet.read_settings()`; dashboard identity = userinfo.email scope → `Settings.UserMap` → display name (cfg.USERS demoted to fallback); Settings in the batchGet; sheet `lang` = cross-device default, local toggle wins; seed + mock get the tab (placeholder emails, D-024)
- ✅ Outbox consolidation: summarizer + reply paths on `queue()` with kinds (`critical` keyword → kind=critical) + stable `wa-{msg_id}` ids; shim + summarizer's local budget counter deleted (ledger = only enforcement, D-015); over-budget alerts now deferred by the outbox into tomorrow's digest instead of silently downgraded; `weekly_briefing --send` queues kind=briefing (`brief-weekly-{date}`)
- ✅ Reply footers stripped (D-014) + DESIGN §6 Hebrew templates: digest header `🏠 Family inc. · יום ו׳ 12/6`, uniform item lines, Hebrew due phrases (dual forms mirror the dashboard), קבוצות section with Hebrew type labels, `⚠ דורש מבט`, Hebrew bridge warning; summarizer CSVs gone — Inbox/Archive append to Sheet tabs
- ✅ Goldens re-cut deliberately (`--regen` made hermetic against a real reminders log); suite 115 → **172 green**

### M3 — Appliance live = go-live (1 session + ~1h on the VPS)

- ⬜ Provision VPS per `ENGINEERING.md` §5 (user, TZ=Asia/Jerusalem, uv, Node LTS, systemd units)
- ⬜ Pair Baileys (one QR scan); place `recipients.json` + service-account JSON + `ANTHROPIC_API_KEY` **+ `FAMILY_INC_SHEET_ID`** in `/etc/family-inc/` (the sheet id is what flips `lib/sheet.py` to the live backend — without it everything keeps running dry against the seed)
- ⬜ Enable timers: engine 07:25 · digest 07:30 · summarizer hourly (24h) · weekly briefing Sat 21:00 · backup Sun 03:00
- ⬜ Seed ≥20 real reminders across Car/Health/Education/Contracts (from `Setup/08` seed + kickoff backlog)
- ⬜ **Acceptance: both phones receive the morning digest 3 consecutive days; one full done→recur cycle visible in the log**
- ⬜ GitHub Pages live for the dashboard; PWA pinned on both phones (`Dashboard/`→`dashboard/` case rename + `deploy/` scripts land here, with the Pages wiring; copy real `seeds/` + `Dashboard/config.js` to the machines that need them — both untracked since M1/D-024)

### M4 — Summarizer hardening (1 session, after ≥1 week live)

- ⬜ Sender→role roster seeded (makes hard rules 2–3 reliable)
- ⬜ Phase F weekly accuracy review surface (false-positive purge)
- ⬜ PO call (joint): do family-group criticals override digest-only routing?
- ⬜ WhatsApp_Inbox hot-tab rolloff against the live Sheet (SPEC §6.2; deferred from M2 — nothing to roll off before ~3 months of live rows; also resolve the 90-day-spec vs 30-day-config disagreement, D-025)
- ⬜ Milestone review (external model) on the live system

## v1.1 candidates (unordered — pick after v1 is boring)

- Reply parsing (done/snooze via WhatsApp) — *code exists (`automation/reply_handler.py`, Hermes C4; on `queue()` with `wa-{msg_id}` ids since M2); remaining: lift the bridge's 1:1 read guard for exactly the two adult JIDs, port its sheet writes to `lib/sheet`, tests, reinstate reply footers, and a PO call on kinds — solicited acks currently ride kind=alert, i.e. they'd consume the unsolicited budget and hold in quiet hours (D-025)*
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
