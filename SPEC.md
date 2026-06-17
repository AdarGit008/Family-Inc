# Family Inc. — System Specification

*Canonical product + system spec. v2.0 · 2026-06-11 · supersedes `Archive/00_Architecture_and_Roadmap.md`, `Archive/02_Reminders_Engine_Spec.md`, `Archive/07_WhatsApp_Group_Summarizer_Spec.md` (absorbed and revised).*
*Companions: `ENGINEERING.md` (how we build/run it) · `DESIGN.md` (how it looks/reads) · `DECISIONS.md` (why) · `BACKLOG.md` (when).*

---

## 1. Overview

Family Inc. is a household operating system for a two-adult, two-child family in Israel. It watches the family's obligations (appointments, renewals, deadlines, school/daycare chatter) and reflects them back through **two calm surfaces**: a small number of WhatsApp messages, and a PWA dashboard pinned to both adults' iPhones. The master database is a single Google Sheet. The automation runs unattended on one small VPS.

The product's core promise: **nothing important gets dropped, without anyone having to watch a screen.**

### What it is not

- Not a chore-gamification app. No streaks, no scores, no nagging.
- Not a kid-facing product. Children's data is structured but adult-mediated.
- Not a finance robot. It never moves money, never stores bank credentials.
- Not a chat bot. It speaks at scheduled moments or for genuine urgency, within a hard budget.

## 2. Context

| | |
|---|---|
| Household | 2 adults (joint product owners) + 2 young children |
| Locale | Israel — Hebrew-first, RTL, ILS, Sunday-start week, Jewish calendar awareness (Shabbat, chagim) |
| Healthcare | Maccabi (no public API — ingestion is mail/manual) |
| Devices | Two iPhones (PWA + WhatsApp), one VPS, no other infrastructure |
| Cost ceiling | ~₪120/mo all-in (VPS ~₪20 + LLM ~₪35 + margin). Anything above needs a PO call |

Roles and decision authority are defined in `CLAUDE.md`. Personal data (names, phone JIDs, health specifics, real budgets) lives only in the Sheet and in gitignored config/seed files — never in this repo's committed code or docs.

## 3. Operating principles

Phrased so a reviewer can check compliance:

1. **One source of truth per domain.** Every datum has exactly one authoritative home (almost always a Sheet tab). Anything else holding it is a cache or a view, and is allowed to be lost.
2. **Boring tech.** Google Sheets over a database; vanilla JS over a framework; cron-like timers over orchestration; JSONL files over message queues. A new dependency must remove a failure mode, not add a capability we merely like.
3. **Alerts are a budget.** Hard cap 2 unsolicited messages per recipient per day, enforced at a single chokepoint (§8.1). Critical-safety messages bypass with an audit trail. Scheduled briefings are exempt — they are appointments, not interruptions.
4. **Briefings > notifications.** The default unit of communication is a scheduled digest. Real-time messages are the exception that must justify itself.
5. **Partner-symmetric.** Both adults see everything, can act on everything, and appear in the system as equals. No leaderboards.
6. **Fail loud, degrade quiet.** Infrastructure failures surface in the next briefing ("bridge silent 14h"), never as silence. Feature degradation (LLM down → deterministic fallback) must not page anyone.
7. **The system never promises an affordance it doesn't have.** No reply commands in messages until reply parsing ships; no buttons that don't write.

## 4. Scope

### v1 (committed)

| Capability | One-line contract |
|---|---|
| Reminders engine | Daily 07:25: read Reminders tab, compute due/lead-time/overdue fires; the 07:30 digest delivers them as one message per recipient |
| Weekly briefing | Sat 21:00: whole-Sheet narrative briefing (LLM-written, template fallback) |
| Hebcal enrichment | Friday/holiday awareness lines in briefings (candle-lighting, chagim, "tomorrow is a chag") |
| WhatsApp group summarizer | Hourly: classify group messages ALERT/DIGEST/ROUTINE; alerts within budget; daily digest section at 07:30 |
| Dashboard (PWA) | Today-first read view + write-back (done/snooze/note) with offline queue + tombstone race guard |
| Delivery | Self-hosted Baileys bridge: 1:1 messages to the two adults only, via a durable outbox |

### Non-goals (permanent, from principles)

Money movement · credential storage · messaging anyone beyond the two adults · posting into any group · kid-facing surfaces · medical advice (scheduling only).

### Frozen (explicitly out of v1)

Finance ingestion, pediatric milestones, goal coaching, PDF/OCR/voice capture, Gmail parsing, Maccabi forwarders, WhatsApp reply parsing. Each has an unfreeze condition in `BACKLOG.md`. Frozen code lives in `attic/`, unmaintained. (2026-06-13, D-033/D-034: property tracking unfrozen → §12.1, M5; merchant categorization + anomaly detection killed.)

## 5. System architecture

```
                       ┌─────────────────────────────────────────────┐
                       │  GOOGLE (data plane)                        │
                       │  Family_OS Google Sheet  ←  master DB       │
                       │  Drive: /Briefings, /Documents              │
                       └────────▲───────────────────────▲────────────┘
                gspread (svc acct)│                      │ gapi (user OAuth)
                                  │                      │
┌─────────────────────────────────┴───────────┐   ┌──────┴───────────────────┐
│  THE APPLIANCE (one VPS, Asia/Jerusalem)    │   │  DASHBOARD (PWA)         │
│                                             │   │  GitHub Pages, vanilla   │
│  systemd timers:                            │   │  JS, pinned to 2 iPhones │
│   07:25 reminders_engine (compute)          │   │  read: batchGet          │
│   07:30 daily digest (assemble+send)        │   │  write: batchUpdate +    │
│   hourly whatsapp_summarizer                │   │   DoneAt/LastDoneBy/     │
│   Sat 21:00 weekly briefing                 │   │   WriteQueue_Tombstone   │
│                                             │   └──────────────────────────┘
│  Baileys bridge (Node, systemd service):    │
│   reads groups → inbox.jsonl                │         ┌──────────────────┐
│   polls outbox.jsonl → sends 1:1            │────────▶│ Adar + Shanee    │
│   recipients.json = hard scope guard        │ WhatsApp│ (the only        │
│                                             │         │  recipients)     │
│  lib/outbox.py = THE chokepoint:            │         └──────────────────┘
│   budget ledger, dedup, kinds               │
└─────────────────────────────────────────────┘
```

Key properties:

- **One write path to phones.** Every script that wants to reach a human appends to the outbox via `lib/outbox.py`. Budget, dedup, quiet hours, and scope live there once (§8.1).
- **One data plane.** All Python uses gspread with a service account; the dashboard uses gapi with each adult's own OAuth. The local `Family_OS.xlsx` is a seed template only — nothing reads it at runtime.
- **One machine.** Bridge and automation share the VPS. Its failure mode is total and therefore obvious (heartbeat goes stale → next successful briefing says so; if >24h, email fallback fires).
- **LLM calls are decoration, not structure.** Every LLM-dependent step has a deterministic fallback (templated briefing, keyword-rule classification). The system delivers value with the API key revoked.

## 6. Data model — `Family_OS` Google Sheet

Authoritative tab list. Column-level schema for the three tabs with code contracts; remaining tabs are human-edited and read loosely (missing columns tolerated, rows with unparseable dates surfaced as data-hygiene lines, never crash).

### 6.1 `Reminders` (keystone)

| Col | Field | Written by | Notes |
|---|---|---|---|
| A | Title | humans | used verbatim in messages |
| B | Domain | humans | controlled vocab: Car/Health/Education/Finance/Contracts/Goals/Other |
| C | Owner | humans | Adar / Shanee / Both |
| D | Due Date | humans, engine (recurrence bump) | DD/MM/YYYY |
| E | Lead Times | humans | CSV of day offsets, e.g. `60,30,7,1` |
| F | Recurrence | humans | One-off / Yearly / Monthly / Quarterly / Weekly / Custom |
| G | Status | engine, dashboard | Pending / Snoozed / Sent / Done / Skipped / Overdue |
| H | Last Sent | engine | ISO datetime of last fire for this row |
| I | Channel | humans | WhatsApp / Email / None |
| J | Notes | humans, dashboard (append) | appended to message if ≤120 chars |
| K | Days Until | sheet formula | `=D−TODAY()` |
| L | Auto-flag | sheet formula | OVERDUE / FIRE TODAY / WEEK OUT / MONTH OUT |
| M | LastDoneBy | dashboard | display name from `Settings.UserMap` |
| N | DoneAt | dashboard | ISO datetime; feeds 7-day arc + ticker |
| O | WriteQueue_Tombstone | dashboard | ISO datetime stamped on **every** dashboard write incl. queued-flush; engine skips rows tombstoned <6h (§8.3) |
| P | Guide URL | humans | optional Kol-Zchut / how-to link, appended to messages |

**Dashboard write contract:** every write-back is one `batchUpdate` touching its intent columns **plus M, N (when completing), and always O.** A dashboard that doesn't stamp O is non-conformant — this was the v1-blocking gap found 2026-06-11.

### 6.2 `WhatsApp_Inbox` (hot, 30-day rolloff) + `WhatsApp_Archive` (text-only, forever)

As built: msg_id, group_name, group_type, sender_name, sender_role, received_at, text, has_media, classification, one_liner, action_required, action_owner, critical, dispatched, dispatched_at, digested_at. Archive keeps msg_id/group/sender/received_at/text/one_liner only. Media is never stored — only the fact it existed. (critical/dispatched/dispatched_at are the outbox outcome record; budget enforcement itself lives only in the outbox ledger, §7.5.)

### 6.3 `WhatsApp_Group_Config`

group_name · group_type · importance_default (alert_eligible/digest_only/mute) · alert_recipients (both/adar/shanee/none) · close_contacts · alert_keywords (regex ;-list) · critical_keywords (regex ;-list, budget-bypassing). Seed: `Setup/12_WhatsApp_Group_Config_Seed.csv`.

### 6.4 Other tabs

`People`, `Calendar-Events`, `Finance-Budget`, `Goals`, `Health`, `Education`, `Car`, `Contracts`, `Contacts`, `Settings` (Key|Value rows: keys containing `@` are UserMap entries email→display-name; key `lang` is the chrome default), `Reminders-Archive` (one-offs roll here monthly), `Property-Listings` (pending M5 build, scraper-written — schema in §12.1). Money values are **ILS only**; legacy USD figures from the kickoff are restated in ILS in the Sheet.

## 7. Component contracts

### 7.1 Reminders engine (daily 07:25 — computes, does not send)

```
validate header row against the §6.1 column map; on mismatch: abort the run,
  log schema_drift, surface it in the next briefing (guards the dual write-path:
  dashboard and engine must agree on columns before anything fires; write-backs
  validate BEFORE the batch is issued — a drifted sheet is never partially
  written by position)
read Reminders where Status ∉ {Done, Skipped} — Sent rows stay eligible, or a
  60,30,7,1 lead-time chain would die at its first fire (errata 2026-06-12;
  same-day re-fires are blocked by the Last-Sent guard, §8.4)
  skip if WriteQueue_Tombstone within 6h        → log skipped_due_to_tombstone + age
  fire if: days_until < 0 AND last sent ≥3d ago → OVERDUE
        or days_until ∈ Lead Times              → LEAD-TIME
        or days_until == 0                      → DUE TODAY
hand fires to the 07:30 daily digest (§7.2), which renders ONE message per
recipient (DESIGN.md §6) → outbox(kind=alert)
on send success: Last Sent = now; Status = Sent | Overdue
recurrence on Done: bump Due Date by period, Status → Pending, Last Sent cleared;
  Feb-29-class failures → last day of target month + flag for review
heartbeat: append one line to logs/reminders_log.csv every run (fired/sent/skipped + reasons)
```

### 7.2 Weekly briefing (Sat 21:00) + daily digest assembly (07:30)

Weekly: read all tabs → LLM writes a 5-scene narrative (DESIGN.md §6) → `Briefings/` + outbox(kind=briefing). LLM unavailable → deterministic template. Daily: one short message assembled from engine fires + WhatsApp digest section + Hebcal line (Fridays/erev chag), queued as outbox(**kind=briefing** — budget-exempt and never deferrable, like every briefing; was kind=alert until D-027, which made the §8.1 deferral circular). **One morning message, not several** — assembly happens before queuing; on send success the digest stamps each fired row's Last Sent/Status per §7.1.

### 7.3 WhatsApp summarizer (hourly)

Reads new inbox lines → classification = hard rules first (the 5 rules as built: keyword match, teacher-evening, vaad-utilities, media-only→ROUTINE, muted-group), LLM (Haiku) for the rest with 3-message group context, deterministic keyword fallback without API → writes Inbox + Archive rows → ALERT rows route per group config → outbox(kind=alert, or kind=critical on critical_keywords match). Digest-only groups with a critical match → "⚠ NEEDS A LOOK" block at the top of the next digest (family-group override is an open PO call, `BACKLOG.md` M4).

### 7.4 Bridge (Baileys, Node, systemd service)

Listens to **groups only** → `inbox.jsonl`. Polls `outbox.jsonl` every 15s → sends **1:1 only** to JIDs present in `recipients.json` (machine-local, gitignored); any other target is refused and logged. Per-(id,target) dedup against a sent ledger. Heartbeat file on connect/message/15-min idle. Never posts to groups. Never reads 1:1 chats (until reply parsing v1.1, which will lift the guard for exactly two JIDs).

### 7.5 Outbox (`lib/outbox.py`) — the chokepoint

```
queue(to: "adar"|"shanee"|"both", body, kind: "alert"|"critical"|"briefing", source, id)
  briefing → exempt from budget, subject to quiet hours (22:00–07:00 → hold to 07:00)
  alert    → consult ledger[date][recipient]; if ≥2 → downgrade: append to tomorrow's
             digest, log alert_suppressed_by_budget; else send + increment
  critical → send immediately, any hour, log budget_bypassed_critical
  all      → idempotent by (id, target); ledger + queue are durable JSONL on disk
```

The ledger is shared across **all** senders — engine and summarizer can no longer each spend 2/day.

### 7.6 Dashboard (PWA)

Read: `batchGet` all bound ranges (DESIGN.md carries the UI contract). Write: per §6.1 write contract, optimistic UI, offline queue in `localStorage.pendingWrites[]` (cap 50), flush on reconnect in tap order, failed flushes retry next online event. Identity: Google sign-in → `Settings.UserMap` → display name. Demo mode renders `mock_data.json` and never calls gapi.

## 8. Cross-cutting policies

### 8.1 Alert budget

2 unsolicited messages / recipient / day, enforced only in `lib/outbox.py`. Trim priority when over: OVERDUE and kids' Health always survive; WEEK/MONTH-OUT bump first; Goals never alert (briefing-only). >10% of fires suppressed over rolling 14 days → next weekly briefing says "budget is biting — raise cap or tighten rules?".

### 8.2 Quiet hours

22:00–07:00 Asia/Jerusalem. Alerts and briefings hold; criticals do not.

### 8.3 Offline write / engine race (tombstone)

Dashboard stamps `WriteQueue_Tombstone` (ISO-T datetime) on every write — queued offline writes re-stamp it at flush, so the cell always carries the moment the write *landed* on the Sheet. The engine compares that cell value against its own `now()` and skips the row while `cell + 6h > now()` (one clock semantics: the window starts at flush, not at the tap). Residual accepted race: phone offline with a queued tap that flushes inside the same minute the engine reads → at most one duplicate alert; the flush itself is idempotent. **Tuning is data-driven, not anecdotal:** every skip is logged with tombstone age, and the weekly briefing reports "N tombstone skips · max age seen" — widen the window when the age distribution approaches 6h, not when someone remembers a duplicate.

### 8.4 Idempotency & dedup

Outbox messages carry stable ids: engine = `rem-{row}-{date}`, summarizer = `wa-{msg_id}`, briefings = `brief-{type}-{date}`. Bridge dedups per (id, target). Engine re-runs on the same day are no-ops (Last Sent guard).

### 8.5 Time & locale

All schedules in Asia/Jerusalem (DST-correct via system TZ, never UTC offsets). Dates DD/MM/YYYY; week starts Sunday; money `Intl.NumberFormat('he-IL', ILS)` / `₪{n:,}` in Python. Chrome strings Hebrew-default with English fallback; data values stay Hebrew always. Machine-written datetime stamps (Last Sent, DoneAt, WriteQueue_Tombstone) are ISO-8601 `T`-form text in both surfaces — the T keeps Sheets from coercing them into locale-formatted date cells, so they round-trip byte-exact and keep the hour resolution the 6h tombstone window needs.

### 8.6 Privacy & security

- WhatsApp plaintext exists in places we don't fully control — Meta's servers (inherent) and the configured LLM provider — plus the VPS we do. The single permitted external message processor is **DeepSeek** (wired M4, D-044); no others. LLM classification sends one message + ≤3 context messages, never whole threads or cross-group context. *(This amends the original "no third-party message processors": the joint call was confirmed by Shanee, D-036e, and the OpenAI-compatible backend shipped at M4 wiring, D-044/D-032. The key is `FAMILY_INC_DEEPSEEK_API_KEY` in `/etc/family-inc/env`; absent → the system runs keyless on keyword classification, degrade-quiet §3.6.)*
- Secrets (`recipients.json`, service-account JSON, `FAMILY_INC_DEEPSEEK_API_KEY` / `ANTHROPIC_API_KEY`, `FAMILY_INC_APIFY_TOKEN` — the property secondary source, D-040) live in `/etc/family-inc/`, mode 600, never in the repo. The repo is public-safe by construction: personal values only in the Sheet and gitignored files.
- Phone numbers/JIDs appear nowhere except `recipients.json` on the VPS.
- The service account has access to exactly one spreadsheet (shared to it explicitly), nothing else in Drive.
- Known accepted risk: Baileys is an unofficial client — account-ban risk, elevated somewhat on datacenter IPs. Mitigations: household volume (≤10 msg/day), person-to-person pattern, dedicated paired session. Fallback chain in §10.

### 8.7 LLM usage

One wrapper (`lib/llm.py`), model ids in config not call sites, per-call cost logged to `logs/llm_costs.csv`. **Provider = DeepSeek** (wired M4, D-044): `lib/llm` calls DeepSeek's OpenAI-compatible `/chat/completions` over stdlib urllib (no SDK), model ids in `config.MODELS` (`deepseek-chat` for classification + briefing prose). The active provider is chosen by key presence — DeepSeek (`FAMILY_INC_DEEPSEEK_API_KEY`) first, the Haiku-class Anthropic path (`config.ANTHROPIC_MODELS`) as fallback, else the deterministic fallback. Monthly cost line appears in the first weekly briefing of each month. **Until the PO places the key the live system runs keyless** (keyword classification + template briefing), unchanged from v1. (Direction set in D-032, confirmed by Shanee in D-036e.)

## 9. Failure modes

| Failure | Detection | Behavior |
|---|---|---|
| VPS down | heartbeat stale (external check optional, v1.1) | total outage; on recovery, outbox flushes; missed runs reported in next briefing |
| Bridge logged out / WA protocol break | heartbeat stale >12h | digest prepends "⚠ BRIDGE SILENT Nh"; >24h → email fallback digest to both adults |
| WhatsApp account banned | send failures + logout | switch to email digests same-day (one-line config); decide Twilio/SMS path per §10 |
| Sheet API 5xx / quota | gspread retries w/ backoff, then skip run | "missed yesterday" line in next successful run |
| LLM API down/keyless | exception → fallback path | templated briefing / keyword classification; logged, not alerted |
| Bad row data (unparseable date) | per-row try/except | row skipped + listed under "data hygiene" in weekly briefing |
| Sheet header drift (column added/renamed out of contract) | engine header validation, every run | run aborts before firing anything; schema_drift logged + surfaced in next briefing |
| Outbox/inbox JSONL torn line | reader skips malformed tail | self-heals next poll (single-writer appends) |
| Clock skew / future tombstone | tombstone > now | treat as valid for full window, log anomaly |
| Both adults edit same row | last-writer-wins | acceptable at household scale, by decision |

## 10. Fallback chain (delivery)

1. **Baileys bridge** (primary).
2. **Email digest** to both adults — automatic, and mechanically specified: the daily-digest task checks the bridge heartbeat before queuing; if stale >24h it sends the identical rendered content via SMTP (app-password in `/etc/family-inc/env`) and notes "delivered by email — bridge down Nh" in the body. No watcher process; the sender itself degrades. Every send-run logs its transport (`logs/delivery_log.csv`); email-fallback days are **degraded, not green** — the weekly briefing surfaces them, so a dying bridge can't hide behind a working fallback (D-028).
3. **Twilio WhatsApp** — documented fallback, not in code. Adopt only if Baileys proves unworkable (ban recurrence); accepts template-approval constraints.
4. **Inforu SMS** — deep fallback, Hebrew-capable, ILS billing; revisit only on 2+ failures above.

## 11. Acceptance criteria (v1 = done when all true)

1. Both phones receive the 07:30 digest **3 consecutive days** — no manual intervention, **via WhatsApp** (email-fallback days don't count toward acceptance, D-028).
2. One reminder completes a full cycle: fires → marked done on the dashboard → recurrence bumps → next year's row visible.
3. A daycare-group message with an alert keyword reaches the right recipients within 10 minutes; a family-group meme reaches no one.
4. A critical keyword fires after the daily budget is spent (bypass proven in production, not mock).
5. Dashboard write-back from an offline phone flushes on reconnect; engine logs `skipped_due_to_tombstone` ≥1 time without a duplicate alert.
6. Weekly briefing arrives Sat 21:00 with Hebcal line and budget/goal sections; LLM-down fallback verified once by revoking the key.
7. `logs/` show 7 days of green runs; pytest suite green; zero Twilio references in code.
8. Total monthly run cost confirmed ≤ ₪120.

## 12. Data ingestion lanes

Specs for ingestion lanes that have been **unfrozen**. Frozen lanes (finance, pediatric, goal coaching, Gmail/Maccabi parsing, PDF/OCR/voice) carry no spec here until unfrozen; their dispositions — and the pre-resolved finance build architecture — live in `DECISIONS.md` (D-031–D-034). All ingestion obeys the same rules: one runtime (the VPS, D-018), `lib/sheet` is the only Sheet writer (D-016), no new path bypasses `lib/outbox.py` (§8.1), secrets only in `/etc/family-inc/` (§8.6).

### 12.1 Property listings — Yad2 / Madlan (unfrozen 2026-06-13, D-034)

Active house search. Build scheduled **after the v1 3-day acceptance window closes (earliest 2026-06-16)**, not during it; independent of any other lane.

| Facet | Spec |
|---|---|
| **Source** | Saved-search result pages on Yad2 (primary) and Madlan (optional). One or more saved-search URLs per portal, each encoding the criteria (area, price, rooms). No public API for either portal: the **primary** path scrapes (below); a permitted **secondary** source (Apify) backs it up when the scrape is blocked and fills missing fields (D-040). |
| **Mechanism** | Headless Chromium on the VPS (the same browser dependency the frozen finance scraper will use — one shared dep, provisioned once in `provision.sh`). A small scraper loads each saved-search URL, extracts listing cards (`listing_id`, price, rooms, size, location, url, posted-at), and diffs the `listing_id` set against the last-seen set persisted at `/var/lib/family-inc/property/seen.json`. New ids = new listings. |
| **Secondary source (D-040)** | Apify is a SECONDARY/supplementary source, never a replacement: `automation/lib/apify.py` (the only Apify client) is consulted **per saved-search only when the primary is blocked/empty (backup) or returned listings with missing fields (gap-fill)**, then merged with the **primary always winning** (`merge_listings` — Apify only adds missed listings + fills blanks, never overwrites). Actors: `amit123~yadscraper` (Yad2, ingests the saved-search URL directly) and `swerve~madlan-scraper` (Madlan, parametric — the search needs a `{city,dealType,…}` `apify` block; params are never guessed from the url). Strict, fail-loud, never-invent: a dataset item missing its id or carrying a corrupt numeric is skipped **and** surfaced (→ fail-flag); an absent optional field is honest-empty, never fabricated; a missing token/HTTP/timeout is a loud `ApifyError`. Apify runs from its own residential proxy pool, clearing the anti-bot wall the VPS datacenter IP cannot (D-039). **Cost-bounded:** priced per result, so it lands at most **once/calendar-day** (the on-box primary keeps its free 2×/day; the digest is morning-only) with per-search item/page caps — governed by the §11 ≤₪120/mo ceiling (D-040 amends D-010's ₪0). |
| **Runtime** | One `systemd` timer (`family-property.timer`), Asia/Jerusalem, 1–2×/day (not real-time — listings don't churn by the minute and tighter polling raises ban risk). `TimeoutStartSec` + `MemoryMax` bound a stuck or runaway browser; the unit is independent of the bridge service. No second runtime (D-018). |
| **Auth model** | None for the portals (public listings). Secrets: the saved-search config at `/etc/family-inc/property_searches.json` (mode 600, personal criteria, never in the repo — D-024), and — for the secondary source — `FAMILY_INC_APIFY_TOKEN` in `/etc/family-inc/env` (mode 600; a SERVICE api key, not a portal login, so "no credential storage" holds; absent → the Apify path is inert, primary-only). Sheet writes use the existing `Family_OS` service account (access scoped to the one spreadsheet, §8.6). |
| **Sheet landing zone** | New `Property-Listings` tab. Columns: `listing_id` (dedup key) · `portal` · `first_seen` (ISO-T) · `price_ils` · `rooms` · `size_sqm` · `location` · `url` · `status` (human-edited: new/seen/contacted/dismissed). Append-only via `lib/sheet`; dedup on `listing_id`; a listing that drops out of results is left in place (no delisting tracking in v1 of the lane). |
| **Delivery** | New listings land **silently** in the Sheet and surface in a "🏠 דירות חדשות / New listings" section of the 07:30 daily digest. They never fire an alert and never bypass the budget — property is not critical-safety (briefings > notifications, §3 principle 4, §8.1). |
| **Failure handling** | A scrape error or anti-bot block (Yad2 runs Cloudflare; scraper fragility is rising across 2026 Israeli portals) sets the fail-flag (`OnFailure` → `logs/fail.flag`); the next delivered digest reports "property scrape failed" and the weekly briefing surfaces persistent failures — fail loud, never silent (§9, §10.2). Persistent block → the realized escape hatch is the Apify secondary source (D-040), which runs from a residential proxy pool off-box; an anti-detect browser (e.g. a Camoufox-based fork) on the one VPS remains a further fallback. |
| **Unfreeze ordering** | Independent of finance. Build after acceptance (≥2026-06-16). The first scraper to land (property or, later, finance) pays the one-time Chromium provisioning cost; the second reuses it. |

## 13. References

`ENGINEERING.md` — runtime, repo layout, migration plan, testing, ops. `DESIGN.md` — dashboard UI, message design system, i18n. `DECISIONS.md` — rationale history. `BACKLOG.md` — sequencing. `Archive/` — superseded docs, kept for the paper trail.
