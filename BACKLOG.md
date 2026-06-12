# Backlog

*The only live backlog. Status legend: ⬜ todo · 🔵 in progress · ✅ done · 🧊 frozen.*
*v1 definition and acceptance criteria live in `SPEC.md` §11. Migration session plan lives in `ENGINEERING.md` §9.*

**Now:** milestone = **M3** (go-live) — repo side done + reviewed, remaining work is the PO's ~1h at the VPS (`deploy/README.md`) + the 3-day acceptance watch · open via `NEXT_SESSION_PROMPT.md` · last session: 2026-06-12 (M3 session 1: deploy/ + Pages workflow + §10.2 email fallback + fail-flag + digest kind=briefing + dashboard/ rename + 31-row seed draft + D-027; §11 review resolved same-day: 2 applies (line-precise fail-flag clear, transport log + degraded-day surfacing), 3 evidence-defends, posture call D-028 — 199 tests)

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

### M3 — Appliance live = go-live (repo side ✅ 2026-06-12 session 1; remaining = PO's ~1h at the VPS, runbook: `deploy/README.md`)

- ✅ `deploy/` landed: idempotent `provision.sh` (user, TZ=Asia/Jerusalem, uv, Node 22, repo, deps, units, the one sudoers line), `deploy.sh` (pull→sync→test→bridge restart), `backup.sh` (tar bridge/state+logs → rclone, 90d prune), 13 systemd units incl. `family-fail-flag@.service`
- ✅ Delivery hardening (D-027): SPEC §10.2 email fallback built (`lib/mailer.py`; heartbeat >24h → digest by SMTP, stamps normally, falls back to queue when SMTP is down too); fail-flag wired (OnFailure → `logs/fail.flag` → next delivered digest reports + clears, weekly surfaces stragglers); daily digest queues kind=**briefing** (was alert — consumed budget and was circularly deferrable); `recipients.json` → `/etc/family-inc/` (local file = dev fallback); tests 172 → **191 green**
- ✅ Pages wiring: `.github/workflows/pages.yml` serves `dashboard/` (branch-mode can't serve subdirs), generates gitignored `config.js` from Actions secrets `DASHBOARD_CLIENT_ID`/`DASHBOARD_SHEET_ID`; `Dashboard/`→`dashboard/` case rename (two-step git mv in the session-1 handoff)
- 🔵 Seed ≥20 real reminders: `seeds/Reminders_Import_M3.csv` drafted — 31 rows across Car/Health/Education/Contracts/Finance/Other from the 08 seed + the kickoff health backlog — **PO reviews dates/owners, then imports** (instructions in `seeds/README.md`)
- ⬜ The VPS hour: provision (private-repo clone via read-only fine-grained PAT — repo turned out to be private at go-live) → secrets in `/etc/family-inc/` (`FAMILY_INC_SHEET_ID` = the live-backend flip, + SMTP creds for §10.2; **no LLM key — keyless go-live, provider call in M4**) → pair Baileys → verify timers → import seeds → one green `backup.sh` run · *prerequisite step-zero done 2026-06-12: live `Family_OS` Sheet created from the seed xlsx, Settings.UserMap fixed, GCP project + service account + OAuth client created*
- ⬜ **Publication** (gates Pages + PWA): history rewrite first — `git filter-repo` strips the 8 Archive personal docs + pre-D-024 blobs (kid names, kickoff health/money) from ALL history — then flip repo public (free-plan Pages requires public), enable Pages (Source=GitHub Actions + the two secrets + OAuth origin), pin PWA on both phones, rotate the provision PAT. **Repo stays private until the rewrite — D-027f's deferral is only safe unpublished.** Dashboard-dependent acceptance items (#2, #5) wait for this; digest acceptance (#1) ticks from tonight
- ⬜ **Acceptance: both phones receive the morning digest 3 consecutive days; one full done→recur cycle visible in the log** → then flip CLAUDE.md "Current state", tag `v1-live`, M4 after ≥1 week

### M4 — Summarizer hardening (1 session, after ≥1 week live)

- ⬜ Sender→role roster seeded (makes hard rules 2–3 reliable)
- ⬜ Phase F weekly accuracy review surface (false-positive purge)
- ⬜ PO call (joint): do family-group criticals override digest-only routing?
- ⬜ PO call (joint): quiet-day digest goes to Adar only (pre-M1 heartbeat behavior preserved) — Shanee gets nothing on days without her fires, incl. the WhatsApp-groups section. Partner-symmetric? (noticed at go-live 2026-06-12)
- ⬜ PO call (joint): LLM provider — Anthropic (as spec'd, §8.7) vs DeepSeek (cheaper; PRC data-handling tradeoff for group plaintext + Sheet data). v1 went live **keyless** by design (2026-06-12): keyword classification + template briefing until this lands; if DeepSeek wins, `lib/llm.py` gains an OpenAI-compatible backend (~30 lines + tests)
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
