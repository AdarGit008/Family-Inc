# Backlog

*The only live backlog. Status legend: ⬜ todo · 🔵 in progress · ✅ done · 🧊 frozen.*
*v1 definition and acceptance criteria live in `SPEC.md` §11. Migration session plan lives in `ENGINEERING.md` §9.*

**Now:** **M3 (go-live) CLOSED 2026-06-15 — v1 live & accepted, tagged `v1-live`.** The §11 3-day window (2026-06-13→15, D-029 re-pair clock) passed: the morning digest reached both phones three consecutive days. **M5 property-tracker built (D-037); the Yad2/Madlan anti-bot wall blocked the on-box scraper from the VPS datacenter IP (D-038/D-039), resolved by adding Apify as a SECONDARY source (D-040, 2026-06-16) — VPS deploy pending (token + Madlan params);** **M4** (summarizer hardening) still waits ≥1 week live. · last session: **2026-06-15 (M3 close, D-035)**; prior: 2026-06-13 (data-fetching planning, D-031–034) — finance frozen, L2/L3 killed, Dira → M5 · **2026-06-15 hardening (D-036):** zombie tasks deleted, D-033 orphans removed, ticker removed, rolloff→30d, ENGINEERING §3 fixed, M4 open calls ratified. · **2026-06-15 M5 local build (D-037):** property_scrape + Property-Listings landing + silent digest section + systemd/provision artifacts, 229 tests green; VPS deploy pending.

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

### M3 — Appliance live = go-live (appliance live 2026-06-12; remaining = D-029 re-pair + publication + 3-day acceptance)

- ✅ `deploy/` landed: idempotent `provision.sh` (user, TZ=Asia/Jerusalem, uv, Node 22, repo, deps, units, the one sudoers line), `deploy.sh` (pull→sync→test→bridge restart), `backup.sh` (tar bridge/state+logs → rclone, 90d prune), 13 systemd units incl. `family-fail-flag@.service`
- ✅ Delivery hardening (D-027): SPEC §10.2 email fallback built (`lib/mailer.py`; heartbeat >24h → digest by SMTP, stamps normally, falls back to queue when SMTP is down too); fail-flag wired (OnFailure → `logs/fail.flag` → next delivered digest reports + clears, weekly surfaces stragglers); daily digest queues kind=**briefing** (was alert — consumed budget and was circularly deferrable); `recipients.json` → `/etc/family-inc/` (local file = dev fallback); tests 172 → **191 green**
- ✅ Pages wiring: `.github/workflows/pages.yml` serves `dashboard/` (branch-mode can't serve subdirs), generates gitignored `config.js` from Actions secrets `DASHBOARD_CLIENT_ID`/`DASHBOARD_SHEET_ID`; `Dashboard/`→`dashboard/` case rename (two-step git mv in the session-1 handoff)
- ✅ Seed ≥20 real reminders: **33 rows imported to the live Sheet 2026-06-12** (import tool grew `--fix-formats` for the template's date-format + K/L formula gaps en route)
- ✅ The VPS hour — **done 2026-06-12 evening**: provisioned (private-repo clone via read-only fine-grained PAT), secrets in `/etc/family-inc/` (`FAMILY_INC_SHEET_ID` live flip + SMTP; keyless go-live, LLM provider call in M4), Baileys paired, timers verified, seeds imported, one green `backup.sh` run
- ✅ Day-1 fix (D-029): bridge → **Baileys 7.0.0-rc13 + ESM** — deployed, `auth_state/` wiped, re-paired on VPS — **done 2026-06-13**
- ✅ **Publication** (D-030): `publish.sh` run, repo public, Pages live (GitHub Actions + secrets + OAuth origin), PWA pinned to both phones, VPS remote updated to credless public URL, provision PAT revoked — **done 2026-06-13**
- ✅ Publication-day dashboard fix: the appreciation-ticker block (landed 15890a4/D-028) was one literal-`\n` comment line — `renderAll` called an undefined function, killing boot before `initAuth`, so sign-in could only toast "OAuth not configured"; de-escaped back into 50 lines of code (`node --check` green), `sw.js` shell cache bumped v2→v3 so cached-broken clients self-heal. Ticker shipped live but unstyled; subsequently **removed entirely (D-036)** rather than styled — a passive completion surface still risked reading as a partner scoreboard. Second layer found under it: the Pages workflow generated `config.js` from the example with `DEMO_MODE: true` intact — real ids present but ignored, `initAuth` returned silently, site served mock data; sed now flips the flag + a generation-time guard fails the deploy if it survives, shell cache → v4
- ✅ **Acceptance PASSED 2026-06-15: morning digest reached both phones 3 consecutive days (2026-06-13→15, D-029 re-pair clock); done→recur cycle observed in the log.** CLAUDE.md current-state flipped to live; `v1-live` tagged (D-035). M4 after ≥1 week live

### M4 — Summarizer hardening (1 session, after ≥1 week live)

- ⬜ Sender→role roster seeded (makes hard rules 2–3 reliable)
- ⬜ Phase F weekly accuracy review surface (false-positive purge)
- ✅ resolved D-036: family-group criticals do NOT override digest-only routing (critical_keywords already bypass per-group)
- 🔵 decided D-036: quiet-day digest made partner-symmetric (both get the quiet-day line incl. WA-groups) — code lands M4
- 🔵 D-036: DeepSeek confirmed by Shanee — wiring lands M4 (lib/llm OpenAI-compatible backend, ~30 lines + tests)
- 🔵 D-036: WhatsApp_Inbox rolloff = 30-day (SPEC §6.2 aligned to config); rolloff code lands M4
- ⬜ Milestone review (external model) on the live system

### M5 — Property tracker (unfrozen D-034) — 🔵 built; anti-bot resolved via Apify secondary (D-040); VPS deploy pending

*First post-acceptance build; independent of finance. Full spec: `SPEC.md` §12.1. (`session_kickoff.py` still names M4 as "current" — it lists first with open ⬜ items; M5's build is the earlier one in wall-clock. M4 still waits ≥1 week live.)*

- 🔵 Provision headless Chromium on the VPS — `provision.sh` §4b written (ephemeral `uv run --with playwright`, kept out of the core lockfile; OS-deps as root + browser as app user, idempotent) and `family-property.service` runs via it; **runs at next deploy** (no appliance touch this session)
- ✅ `automation/property_scrape.py` — saved-search URLs from `/etc/family-inc/property_searches.json`, headless-Chromium fetch (lazy Playwright), embedded-JSON card extraction + tolerant normalize, diff `listing_id` vs `seen.json`; MOCK MODE out-of-the-box; anti-bot page → `BlockedError` (fail loud), genuine empty page → `[]`
- ✅ `Property-Listings` landing via `lib/sheet` (D-016) — `PROPERTY_LISTINGS_COLUMNS` (§12.1), append-only, dedup on `listing_id` (`seen.json` + a Sheet-side guard); tab auto-creates on first live append
- ✅ `family-property.timer` (07:10 + 19:10, before the 07:25/07:30 run) + `family-property.service` (`TimeoutStartSec=300`/`MemoryMax=1500M`, `StateDirectory`, `OnFailure` → fail-flag)
- ✅ Digest gains the silent "🏠 דירות חדשות" section — folded into `daily_digest.assemble` (never an alert, never budget); copy in `templates.py` **[Shanee review]**, DESIGN §6 addition pending
- ✅ Tests: 23 in `tests/test_property.py` — card parse/normalize, `BlockedError`, empty-result, seen-diff, persist skip/roundtrip/Sheet-dedup, digest section, daily-digest fold-in, junk/promo rejection, anti-poison seen-set
- ✅ **Anti-bot path (D-038 → D-040):** deploy-time pytest made hermetic vs the live Sheet (D-038); primary → headed Chromium under Xvfb + stealth (D-039) still drew challenges from the datacenter IP; **Apify added as the SECONDARY source** (`automation/lib/apify.py` — amit123 Yad2 + swerve Madlan): per-search backup + gap-fill, primary always wins, strict fail-loud / no-invented-data, once/day cost-gated, token-gated **inert without `FAMILY_INC_APIFY_TOKEN`**. 24 in `tests/test_apify.py` (suite → **253 green**, +24)

**Remaining (PO machine / VPS — deploy step, not done in-session):** **(1)** run `provision.sh` §4b (install Chromium for the primary); **(2)** place `/etc/family-inc/property_searches.json` (real saved searches — personal, never in repo; template = `deploy/property_searches.example.json`) — each **Madlan** entry needs an `apify: {city, dealType, …}` block (swerve is parametric, not URL-driven); **(3)** add `FAMILY_INC_APIFY_TOKEN=…` to `/etc/family-inc/env` (Apify account → API & Integrations; free tier seeds enough credit to verify); **(4)** `systemctl enable --now family-property.timer`, run once + verify a live scrape writes `Property-Listings` rows and the morning section (with the IP blocked, this exercises the Apify backup path end-to-end). Then M5 closes — its external-model review folds into the M4 "review on the live system" item (D-035 precedent), no separate run.

## v1.1 candidates (unordered — pick after v1 is boring)

- Reply parsing (done/snooze via WhatsApp) — *code exists (`automation/reply_handler.py`, Hermes C4; on `queue()` with `wa-{msg_id}` ids since M2); remaining: lift the bridge's 1:1 read guard for exactly the two adult JIDs, port its sheet writes to `lib/sheet`, tests, reinstate reply footers, and a PO call on kinds — solicited acks currently ride kind=alert, i.e. they'd consume the unsolicited budget and hold in quiet hours (D-025)*
- Inbox-append trigger for the classifier (inotify on `inbox.jsonl`) — sub-hour critical latency without changing the hourly digest cadence *(review suggestion, 2026-06-12)*
- Google Calendar connector → Calendar-Events auto-populated
- iCloud → GCal ICS subscribe (15 min, `Setup/05`)
- Reminders `Priority` column + bulk-done flow
- Hebrew chrome string completion pass

## Frozen lanes 🧊

*Frozen = script moves to `attic/`, runbook to `Archive/`, no maintenance. Unfreeze = the stated condition is true AND v1 acceptance has held for 30 days. (D-034 fast-tracked Dira/property to post-3-day-acceptance — active search.)*

| Lane | Assets | Unfreeze condition |
|---|---|---|
| Finance ingestion | bank-scraper plan, `Setup/01` (build arch resolved D-031: VPS+systemd, no Drive) | POs commit to monthly finance review using the data |
| Pediatric milestones | `pediatric_milestones.py`, `Setup/09` | Health tab actively maintained |
| Goal coaching | `goal_coaching.py` (Goals tab exists §6.4; automation frozen) | Goals updated weekly for a month (proves the habit exists) |
| PDF→event, receipt OCR, voice capture, Gmail bill parser, Maccabi forwarders | `pdf_to_event.py`, `Setup/02,03,04,06,07` | Per-item PO request, one at a time |

*Killed 2026-06-13 (D-033): Hebrew categorizer + anomaly/subscription detector — removed from the board; `attic/hebrew_categorizer.py` + `attic/anomaly_detector.py` orphaned (physical delete = a future code session). iCloud→GCal stays in v1.1 candidates (not reclassified).*
