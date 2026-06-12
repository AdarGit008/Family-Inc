# Milestone review — milestone lane

- **When:** 2026-06-12T13:35:13
- **Provider:** DeepSeek (`deepseek-chat`)
- **Elapsed:** 0.7s
- **Attached files (6):**
  - `CLAUDE.md` (5,183 chars)
  - `SPEC.md` (20,940 chars)
  - `BACKLOG.md` (9,499 chars)
  - `ENGINEERING.md` (13,990 chars)
  - `DESIGN.md` (9,650 chars)
  - `DECISIONS.md` (10,607 chars)

---

## Response

### Provider call failed

```
HTTP 401 Unauthorized: {"error":{"message":"Authentication Fails, Your api key: ****-... is invalid","type":"authentication_error","param":null,"code":"invalid_request_error"}}
```

Audit file written so the request payload is preserved. Re-run with a known-good model or report this shape to the script maintainer.


---

<details>
<summary>Full prompt sent (click to expand)</summary>

```
You are reviewing engineering decisions made in a working session on the "Family Inc"
household-automation project. You are the explicit adversarial-but-fair reviewer. The
team owners (Adar = CTO, Shanee = Chief Design + PO) value pushback over agreement.

## Project one-paragraph context
A household operating system for a two-adult, two-young-kid family in Israel
(ILS, Hebrew/RTL, Maccabi healthcare). Master DB = one Google Sheet. PWA dashboard
pinned to both iPhones, write-back to the Sheet. Messages via WhatsApp (self-hosted
Baileys bridge) through a single budgeted outbox. Operating principles (SPEC.md §3):
briefings > notifications, alert budget 2/day, no kid-facing UI, boring tech,
one source of truth per domain, fail loud / degrade quiet.

## What this session changed
# Session changes — 2026-06-12, M3 session 1 (go-live repo side)

Review trigger: touches delivery, budget, and privacy guarantees (ENGINEERING §11) — not an M-close.

- `deploy/` created: idempotent `provision.sh` (ENGINEERING §5 steps 1–4 + units), `deploy.sh` (§6 verbatim + frozen sync), `backup.sh` (tar bridge/state+logs → rclone remote from env, 90-day prune), `deploy/README.md` = the PO's go-live-hour runbook
- 13 systemd units in `deploy/systemd/`: always-on bridge (Restart=on-failure), 5 timer+service pairs (engine 07:25, digest 07:30, summarizer hourly, weekly Sat 21:00, backup Sun 03:00; all Persistent=true), templated `family-fail-flag@.service` on every unit's OnFailure=
- **Budget**: daily digest now queues kind=briefing, was kind=alert — it consumed 1 of 2 daily alert slots and was deferrable by the ledger into the next digest (circular, since over-budget alerts defer INTO the digest). PO call, D-027a, SPEC §7.2 clarified
- **Delivery**: SPEC §10.2 email fallback implemented — `lib/mailer.py` (the only smtplib import), `outbox.heartbeat_age_hours()`; digest --send degrades to SMTP when heartbeat stale >24h (identical content, "delivered by email — bridge down Nh" note, stamps normally); SMTP-also-down → queue + shout, fail flag retained. Framed as transport substitution, not an outbox bypass (D-027b)
- **Delivery**: fail-flag loop closed — `logs/fail.flag` (config.FAIL_FLAG) appended by OnFailure hook, reported (Hebrew prepend line, templates.py) + cleared by the next *delivered* digest, surfaced by the weekly briefing if stale (D-027e)
- **Privacy**: GitHub Pages serves `dashboard/` via `.github/workflows/pages.yml`; gitignored `config.js` generated at deploy from Actions secrets DASHBOARD_CLIENT_ID/DASHBOARD_SHEET_ID — ids never enter git history (D-027d, D-024 lineage)
- `recipients.json` read from `/etc/family-inc/` first, bridge-dir fallback for dev (D-027c) — code now matches ENGINEERING §2
- `Dashboard/` → `dashboard/` case rename (two-step git mv in the handoff block) + all content refs updated (review.py, READMEs, .gitignore)
- `seeds/Reminders_Import_M3.csv` drafted (31 rows from the 08 seed + kickoff health backlog, §6.1 layout, gitignored) + import instructions in seeds/README.md
- Tests 172 → 191 (new `tests/test_mailer.py`: heartbeat age, SMTP fake, degrade paths, kind=briefing, fail-flag report/clear/keep semantics); goldens untouched
- **Privacy** (D-027f, completes D-024): kid names/health details scrubbed from 10 tracked Setup/+reviews/ files the M1 purge missed; 8 personal Archive/ docs (kickoff output, money baseline, design docs with names) untracked + gitignored — files stay on PO machines, git history rewrite deliberately deferred
- Canon updates: SPEC §7.2 (digest kind), ENGINEERING §1/§2/§5 (layout current, Pages-via-Actions, fail-flag semantics), CLAUDE.md current-state, BACKLOG M3 statuses, DECISIONS D-027

## What I want you to review
1. Architectural soundness of the changes above.
2. Missed alternatives or simpler paths we didn't consider.
3. Tradeoffs we made implicitly without writing them down.
4. Risks / failure modes not covered.
5. Internal consistency across the changed files.

## What I do NOT want you to review
- Style, tone, formatting, copyediting.
- Adherence to design "best practices" in the abstract — only call those out if
  ignoring them creates a concrete risk for THIS project.
- The roles or session ritual itself (out of scope; that's our process).
- Files I did not list in "What this session changed" — assume those are settled.

## Required output (use these headings, in this order)
### Concerns
Things that should change. Be specific (file + section). Rank by severity.

### Missed alternatives
Paths we likely didn't explore. One-sentence each. Don't develop them — just name them.

### Affirmations
Decisions you think are correct, especially non-obvious ones. Brief.

### Concrete suggestions
Edits we could make right now. Phrase as "replace X with Y because Z."

### One question for the team
The single most useful question you'd ask Adar+Shanee+Claude if you had one.

Be terse. We're going to act on this directly.

---

## Attached context files

The following files are attached for you to read. Each is delimited by a header line.
Reference them by relative path in your review.

=== File: CLAUDE.md ===
# Family Inc. — Session Context

*Auto-loaded at the top of every session opened in this folder. Remade 2026-06-11 ("the remake"). Keep under 100 lines.*

## What this is

Household operating system for Adar + Shanee (+ 2 young kids, adult-mediated). Master DB = `Family_OS` Google Sheet. Two product surfaces: WhatsApp messages (self-hosted Baileys bridge) and a PWA dashboard pinned to both iPhones. All automation runs on **one VPS** ("the appliance"). Israeli context throughout: Hebrew/RTL, ILS, Asia/Jerusalem, Maccabi, Hebcal.

## Canon — five documents, one job each

| Doc | Owns | If you need |
|---|---|---|
| `SPEC.md` | What the system is: scope, architecture, data model, contracts, policies, acceptance | any contract or "how should X behave" |
| `ENGINEERING.md` | How it's built/run: repo layout, toolchain, VPS, deploy, tests, migration M1–M4 | any "how do we do X" |
| `DESIGN.md` | Both surfaces: dashboard UI + WhatsApp message design, i18n, states | any pixel or copy question |
| `DECISIONS.md` | Why: dated decision log — the only decision record | history or "didn't we decide…" |
| `BACKLOG.md` | When: v1 milestones M1–M4, v1.1 candidates, frozen lanes — the only status record | what's next / what's frozen |

`Archive/` = superseded docs (read-only history). `attic/` = frozen code, unmaintained (created in M1). Status lives **only** in `BACKLOG.md`; decisions **only** in `DECISIONS.md`. Don't re-create per-doc status flags or review appendices.

## Roles & authority

| Role | Person |
|---|---|
| CTO + co-PO | **Adar** — engineering direction, ships code |
| Chief Design + co-PO | **Shanee** — product direction, UX feel |
| Lead Architect | **Claude** — design, code, tradeoffs; defers to POs on product, to Adar on engineering detail |
| Reviewer | External model via `automation/review.py` (Gemini default) — milestone reviews only |

Either PO can lead a session and take routine calls solo; major directional calls (new feature, principle change, removing shipped behavior) are joint and land in `DECISIONS.md`. Session leader = whoever opened the session; Claude treats them as "the PO" unless they defer.

## Non-negotiable principles (full versions: SPEC §3)

One source of truth per domain · boring tech · alert budget 2/day enforced at the outbox (criticals bypass, briefings exempt) · briefings > notifications · partner-symmetric, no scoring · fail loud, degrade quiet · never promise an affordance that doesn't exist · no money movement, no credential storage, no messages beyond the two adults, no kid-facing UI.

## Current state (flip when M3 acceptance passes)

**Not live yet — M3 (go-live) is next.** v1 = keystone (reminders → WhatsApp + weekly briefing + dashboard write-back) + group summarizer. M1 (restructure) and M2 (one source of truth) closed 2026-06-12: `lib/sheet.py` is the only workbook access — live gspread when `FAMILY_INC_SHEET_ID` is set, seed xlsx otherwise, schema-drift guard on Reminders reads/writes; engine + dashboard write-backs per SPEC §7.1/§6.1; budget enforced only in the outbox ledger; DESIGN §6 Hebrew templates, no reply footers. Until M3 wires creds on the VPS, scripts run dry against the seed and nothing messages anyone (write-backs and `--send` are live-backend-gated). M3 session 1 (2026-06-12, D-027) landed the repo side: `deploy/` (provision/deploy/backup + systemd units), Pages-via-Actions with secret-generated `config.js`, SPEC §10.2 email fallback (`lib/mailer.py`), fail-flag wiring, digest kind=briefing, the `dashboard/` rename, and a 31-row seed import draft. Still pending: the PO's ~1h at the VPS + Pages enablement + 3-day acceptance (`deploy/README.md` is the runbook).

## Session protocol

0. `git pull --ff-only` before touching anything — other agents push to origin; the local folder is not assumed current (lesson of 2026-06-12, see `DECISIONS.md`).
1. Read `BACKLOG.md` first — it says where we are.
2. Work the current milestone; don't open new lanes without a PO call logged in `DECISIONS.md`.
3. Constants go in config, utilities in `automation/lib/`, message copy in templates (reviewable against `DESIGN.md` §6).
4. Session end: tests green if code moved, `BACKLOG.md` statuses flipped, `python3 automation/session_kickoff.py` regenerated `NEXT_SESSION_PROMPT.md`, and the PO gets ONE terminal block (stage → review gate if milestone-closing → commit → push) to run on their machine. Next session opens by pasting `NEXT_SESSION_PROMPT.md`.
5. **Milestone reviews only** (new spec / architecture shift / budget-privacy-delivery changes / each M-close): run `automation/review.py`, resolve as Apply / Defend / Open, log directional outcomes in `DECISIONS.md`. Tiny edits never trigger review.

## Guardrails for Claude in this repo

- Never put names, phone numbers, JIDs, or real finance values in committed files — they belong in the Sheet, `/etc/family-inc/`, or gitignored seeds (repo is public-portfolio-safe by construction).
- Never add an alert path that bypasses the outbox chokepoint (`automation/lib/outbox.py`).
- Schema changes are additive-only on the Sheet (old rows must keep parsing).
- If SPEC and code disagree, say so before "fixing" either.

=== End: CLAUDE.md ===

=== File: SPEC.md ===
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

Finance ingestion, merchant categorization, anomaly detection, pediatric milestones, goal coaching, PDF/OCR/voice capture, property trackers, Gmail parsing, Maccabi forwarders, WhatsApp reply parsing. Each has an unfreeze condition in `BACKLOG.md`. Frozen code lives in `attic/`, unmaintained.

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

### 6.2 `WhatsApp_Inbox` (hot, 90-day rolloff) + `WhatsApp_Archive` (text-only, forever)

As built: msg_id, group_name, group_type, sender_name, sender_role, received_at, text, has_media, classification, one_liner, action_required, action_owner, critical, dispatched, dispatched_at, digested_at. Archive keeps msg_id/group/sender/received_at/text/one_liner only. Media is never stored — only the fact it existed. (critical/dispatched/dispatched_at are the outbox outcome record; budget enforcement itself lives only in the outbox ledger, §7.5.)

### 6.3 `WhatsApp_Group_Config`

group_name · group_type · importance_default (alert_eligible/digest_only/mute) · alert_recipients (both/adar/shanee/none) · close_contacts · alert_keywords (regex ;-list) · critical_keywords (regex ;-list, budget-bypassing). Seed: `Setup/12_WhatsApp_Group_Config_Seed.csv`.

### 6.4 Other tabs

`People`, `Calendar-Events`, `Finance-Budget`, `Goals`, `Health`, `Education`, `Car`, `Contracts`, `Contacts`, `Settings` (Key|Value rows: keys containing `@` are UserMap entries email→display-name; key `lang` is the chrome default), `Reminders-Archive` (one-offs roll here monthly). Money values are **ILS only**; legacy USD figures from the kickoff are restated in ILS in the Sheet.

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

- WhatsApp plaintext exists in two places: Meta's servers (inherent) and the VPS we control. No third-party message processors. LLM classification sends one message + ≤3 context messages, never whole threads or cross-group context.
- Secrets (`recipients.json`, service-account JSON, `ANTHROPIC_API_KEY`) live in `/etc/family-inc/`, mode 600, never in the repo. The repo is public-safe by construction: personal values only in the Sheet and gitignored files.
- Phone numbers/JIDs appear nowhere except `recipients.json` on the VPS.
- The service account has access to exactly one spreadsheet (shared to it explicitly), nothing else in Drive.
- Known accepted risk: Baileys is an unofficial client — account-ban risk, elevated somewhat on datacenter IPs. Mitigations: household volume (≤10 msg/day), person-to-person pattern, dedicated paired session. Fallback chain in §10.

### 8.7 LLM usage

One wrapper (`lib/llm.py`), model ids in config not call sites, per-call cost logged to `logs/llm_costs.csv`. Current assignments: classification + briefing prose = Haiku-class; nothing in v1 needs more. Monthly cost line appears in the first weekly briefing of each month.

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
2. **Email digest** to both adults — automatic, and mechanically specified: the daily-digest task checks the bridge heartbeat before queuing; if stale >24h it sends the identical rendered content via SMTP (app-password in `/etc/family-inc/env`) and notes "delivered by email — bridge down Nh" in the body. No watcher process; the sender itself degrades.
3. **Twilio WhatsApp** — documented fallback, not in code. Adopt only if Baileys proves unworkable (ban recurrence); accepts template-approval constraints.
4. **Inforu SMS** — deep fallback, Hebrew-capable, ILS billing; revisit only on 2+ failures above.

## 11. Acceptance criteria (v1 = done when all true)

1. Both phones receive the 07:30 digest **3 consecutive days** — no manual intervention.
2. One reminder completes a full cycle: fires → marked done on the dashboard → recurrence bumps → next year's row visible.
3. A daycare-group message with an alert keyword reaches the right recipients within 10 minutes; a family-group meme reaches no one.
4. A critical keyword fires after the daily budget is spent (bypass proven in production, not mock).
5. Dashboard write-back from an offline phone flushes on reconnect; engine logs `skipped_due_to_tombstone` ≥1 time without a duplicate alert.
6. Weekly briefing arrives Sat 21:00 with Hebcal line and budget/goal sections; LLM-down fallback verified once by revoking the key.
7. `logs/` show 7 days of green runs; pytest suite green; zero Twilio references in code.
8. Total monthly run cost confirmed ≤ ₪120.

## 12. References

`ENGINEERING.md` — runtime, repo layout, migration plan, testing, ops. `DESIGN.md` — dashboard UI, message design system, i18n. `DECISIONS.md` — rationale history. `BACKLOG.md` — sequencing. `Archive/` — superseded docs, kept for the paper trail.

=== End: SPEC.md ===

=== File: BACKLOG.md ===
# Backlog

*The only live backlog. Status legend: ⬜ todo · 🔵 in progress · ✅ done · 🧊 frozen.*
*v1 definition and acceptance criteria live in `SPEC.md` §11. Migration session plan lives in `ENGINEERING.md` §9.*

**Now:** milestone = **M3** (go-live) — repo side done, remaining work is the PO's ~1h at the VPS (`deploy/README.md`) + the 3-day acceptance watch · open via `NEXT_SESSION_PROMPT.md` · last session: 2026-06-12 (M3 session 1: deploy/ + Pages workflow + §10.2 email fallback + fail-flag + digest kind=briefing + dashboard/ rename + 31-row seed draft + 191 tests + D-027)

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
- ⬜ The VPS hour: provision → secrets in `/etc/family-inc/` (incl. `FAMILY_INC_SHEET_ID`, the live-backend flip, + SMTP creds for §10.2) → pair Baileys → verify timers → import seeds → enable Pages (Source=GitHub Actions + the two secrets + OAuth origin) → pin PWA on both phones → one green `backup.sh` run
- ⬜ **Acceptance: both phones receive the morning digest 3 consecutive days; one full done→recur cycle visible in the log** → then flip CLAUDE.md "Current state", tag `v1-live`, M4 after ≥1 week

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

=== End: BACKLOG.md ===

=== File: ENGINEERING.md ===
# Family Inc. — Engineering Handbook

*How this system is built, tested, deployed, and operated. v1.0 · 2026-06-11.*
*Contracts live in `SPEC.md`; this document is the "how". If they disagree, `SPEC.md` wins and the disagreement is a bug.*

---

## 1. Repo layout (current — established in M1, completed in M3 session 1, both 2026-06-12: `deploy/` landed with provisioning and the PWA moved to `dashboard/`)

```
family-inc/
├── CLAUDE.md            # session context for Claude (thin; points here)
├── SPEC.md  ENGINEERING.md  DESIGN.md  DECISIONS.md  BACKLOG.md
├── automation/
│   ├── lib/
│   │   ├── config.py    # env + TOML loading; ALL constants live here
│   │   ├── sheet.py     # the only gspread client (retry, tab accessors)
│   │   ├── outbox.py    # the only path to a human (budget ledger, dedup, kinds)
│   │   ├── llm.py       # the only Anthropic wrapper (model registry, cost log)
│   │   ├── dates.py     # to_date / to_datetime / fmt_date — one implementation
│   │   └── money.py     # ILS formatting — one implementation
│   ├── reminders_engine.py
│   ├── weekly_briefing.py        # renamed from sunday_briefing (it runs Saturday)
│   ├── daily_digest.py           # assembles ONE morning message (engine fires + WA digest + hebcal)
│   ├── whatsapp_summarizer.py
│   ├── hebcal_client.py
│   ├── review.py                 # milestone review tool
│   ├── session_kickoff.py        # regenerates NEXT_SESSION_PROMPT.md at session end
│   └── bridge/                   # Baileys listener + sender (Node)
│       ├── baileys_listener.js  package.json
│       └── state/               # gitignored: auth_state/, inbox/, outbox/, ledgers
├── dashboard/            # vanilla PWA (GitHub Pages serves this directory)
│   ├── index.html  app.js  styles.css  sw.js  manifest.json
│   ├── config.example.js         # committed; real config.js is gitignored
│   └── mock_data.json
├── deploy/
│   ├── systemd/          # *.service + *.timer units (source of truth for schedules)
│   ├── provision.sh      # idempotent VPS setup
│   └── deploy.sh         # pull + test + restart (the only way code reaches the box)
├── tests/                # pytest; fixtures/ holds golden files
├── reviews/              # milestone-review audit trail + session_changes inputs (tracked, §11)
├── seeds/                # CSV seeds (reminders, group config, goals) — personal values → `*.csv` gitignored (D-024), README committed
├── Setup/                # live runbooks only (VPS, bridge pairing, OAuth, ICS)
├── Archive/              # superseded docs — read-only history
├── attic/                # frozen scripts — unmaintained, excluded from tests
└── logs/ Briefings/      # runtime output (gitignored except .gitkeep)
```

Rules: scripts never define utilities that belong in `lib/` (CI greps for redefinitions of `to_date`/`fmt_money`). Nothing outside `bridge/` touches WhatsApp. Nothing outside `lib/sheet.py` constructs a gspread client. Nothing outside `lib/llm.py` imports `anthropic`.

## 2. Toolchain

| Layer | Choice | Notes |
|---|---|---|
| Python | 3.12 + **uv** | `uv sync` on the box; lockfile committed |
| Key deps | gspread, google-auth, anthropic, pytest, requests | additions need a one-line justification in the PR/commit body |
| Node | LTS, plain npm | bridge only; `npm ci` |
| Scheduling | **systemd timers** (not crontab) | journald logs, `OnFailure=` hooks, `Persistent=true` catches missed runs after reboots |
| Hosting (dashboard) | GitHub Pages via Actions (`.github/workflows/pages.yml`) serving `main:/dashboard` | static, zero backend; branch-mode Pages can't serve subdirs — the workflow also generates the gitignored `config.js` from Actions secrets (D-027) |
| Secrets | `/etc/family-inc/` mode 600 | `service-account.json`, `env` (ANTHROPIC_API_KEY, SMTP app password, review-provider keys), `recipients.json` |

## 3. Configuration

- `automation/lib/config.py` loads `/etc/family-inc/env` then `config.toml` (committed, non-secret): schedule constants, budget cap, tombstone window, model ids, group digest order.
- **No constant may be defined in a script.** The 2026-06-11 audit found `ALERT_BUDGET_PER_DAY` defined twice with independent ledgers — the class of bug this rule exists to prevent.
- Dashboard config: `config.example.js` committed with placeholders; real `config.js` (Sheet ID, OAuth client id) gitignored. Sheet ID is not secret-secret, but keeping it out of the public repo is free.

## 4. Coding standards

- Python: type hints on public functions; dataclasses for Sheet rows; no bare `except:` — catch narrowly, log with context, and **decide**: degrade (LLM paths) or surface (data paths). Silent swallowing is the bug class that hid the mock/real boundary for two weeks.
- Every script is also a library: `main()` guarded, pure logic importable for tests.
- Logging: stdlib `logging` to stderr (journald captures); one structured CSV per domain in `logs/` for the self-reporting briefing lines.
- JS (dashboard): keep the single-file vanilla discipline; state lives in the one `state` object; every Sheet write goes through `applyWrites()` and conforms to the SPEC §6.1 write contract.
- Hebrew in code: string literals fine, identifiers English. Message copy lives in template constants, not inline f-strings, so DESIGN.md can review it.

## 5. The appliance (VPS)

Provisioning is `deploy/provision.sh`, idempotent, run as root once:

1. Create user `familyinc` (no sudo); `timedatectl set-timezone Asia/Jerusalem`.
2. Install uv + Node LTS; clone repo to `/opt/family-inc`; `uv sync`; `npm ci` in `bridge/`.
3. Copy `deploy/systemd/*` → `/etc/systemd/system/`; `systemctl enable --now` the bridge service + all timers.
4. Place secrets in `/etc/family-inc/` by hand (never scripted, never copied off the box).
5. Pair Baileys: `systemctl stop family-bridge && node bridge/baileys_listener.js` interactively once, scan QR, restart service. `bridge/state/auth_state/` is covered by the weekly backup — **after a VPS rebuild, restore it before considering a re-pair**; a fresh QR scan is the fallback, not the default.

Units (schedules are code — change them via PR, not on the box):

| Unit | Schedule | Runs |
|---|---|---|
| `family-bridge.service` | always-on, `Restart=on-failure` | Baileys listener + outbox sender |
| `family-reminders.timer` | 07:25 daily | reminders engine (writes fires, doesn't send) |
| `family-digest.timer` | 07:30 daily | daily digest assembly → outbox |
| `family-summarizer.timer` | hourly, 24h | classifier — runs at night so **criticals** can fire any hour; ordinary alerts are still held 22:00–07:00 by the outbox |
| `family-weekly.timer` | Sat 21:00 | weekly briefing |
| `family-backup.timer` | Sun 03:00 | tar `bridge/state` + `logs/` → Drive via rclone |

All units: `Persistent=true` on timers, `OnFailure=family-fail-flag@%n.service` — appends the failing unit to `logs/fail.flag`; the next **delivered** digest reports it (Hebrew line prepended) and clears the file; a flag still present on Saturday means digests aren't landing, and the weekly briefing says so (fail loud, SPEC §3.6).

## 6. Deployment

`deploy/deploy.sh` on the box (or via `ssh familyinc@appliance deploy`):

```
git pull --ff-only
uv sync && (cd automation/bridge && npm ci)
uv run pytest -q                 # red tests abort the deploy; running code is untouched
sudo /usr/bin/systemctl restart family-bridge   # the one whitelisted sudoers line
```

Timers pick up new code automatically on next fire (they exec scripts from the repo); only the long-running bridge needs a restart. The `familyinc` user has exactly one sudo capability — restarting `family-bridge` — so a compromised script can't escalate.

Dashboard deploys are just `git push` (Pages rebuilds in ~30s). The PWA on both phones picks up on next open; `sw.js` cache-busts on version bump in `config.example.js` → mirrored manually into `config.js`.

## 7. Testing policy

Base: M1 delivered the rename + extension (55 → 115); M2 added the write path (115 → 172, 2026-06-12). Minimum bar — these exist and stay green:

| Suite | Covers |
|---|---|
| `test_engine.py` | fire-reason matrix (overdue/lead/due-today), tombstone skip window incl. future-skew, recurrence bumps incl. Feb-29 clamp + Custom flagging, send-success stamping (Sent/Overdue), Last-Sent rerun idempotency end-to-end |
| `test_outbox.py` | budget ledger: 2-cap, critical bypass, briefing exemption, shared-ledger across two sender sources, (id,target) dedup, quiet-hours hold |
| `test_summarizer.py` | the 5 hard rules, per-group routing incl. `none`→NEEDS-A-LOOK, keyword fallback without API key, dispatch through the outbox (kinds, `wa-{msg_id}` ids, over-budget deferral), Sheet-tab persistence + rerun dedup |
| `test_render_golden.py` | weekly briefing + daily digest rendered against `tests/fixtures/*.md` golden files (byte-exact; update goldens deliberately) |
| `test_sheet.py` | row parsing tolerance (missing columns, bad dates → skipped + reported, never raised), §7.1 schema-drift guard both directions + flag heal, batched write path incl. formula survival, value encoding, Settings/UserMap |

LLM calls are never made in tests — `lib/llm.py` has a fake injected via env. The dashboard gets a manual smoke checklist in `DESIGN.md` §9 (no JS test harness — boring tech; revisit if app.js exceeds ~2,000 lines).

## 8. Observability

- journald per unit (`journalctl -u family-reminders`).
- `logs/reminders_log.csv`, `logs/wa_classifier.csv`, `logs/llm_costs.csv`, `logs/outbox_ledger/`.
- Self-reporting: the weekly briefing includes one system line — "7/7 runs green · 41 messages classified · 2 tombstone skips (max age 1.4h) · ₪6.10 LLM spend"; any fail-flag, schema-drift, or stale heartbeat replaces it with a warning. The humans never check logs unless the briefing tells them to.
- External uptime ping (healthchecks.io free tier) — optional, listed v1.1.

**"No digest by 08:00" runbook** (the most likely 24h failure is a logged-out WhatsApp session on a healthy VPS):

1. Check email — if the digest arrived there, the bridge is down but the system is fine: SSH in, re-pair the QR (restore `auth_state/` first if post-rebuild).
2. No email either → the VPS itself is down: reboot from the provider console; `Persistent=true` timers fire the missed runs on boot.
3. Repeated same-week bridge logouts → treat as ban signal; invoke the fallback chain decision (SPEC §10).

## 9. Migration plan (current tree → this handbook)

Executed as sessions M1–M4; the per-item checklists live in `BACKLOG.md`. Session boundaries are hard: each ends with tests green and a one-line entry in `DECISIONS.md` if anything was decided.

- **M1 — Restructure.** Create `lib/` by extracting the *best* duplicate of each utility (the audit mapped them); move frozen scripts to `attic/`; delete root-level legacy scripts; purge Twilio; rename `sunday_briefing` → `weekly_briefing`; carve `daily_digest.py` out of the engine's send path; pytest scaffold green.
- **M2 — One source of truth.** gspread port behind `lib/sheet.py`; dashboard write contract (DoneAt/LastDoneBy/Tombstone); `Settings.UserMap`; outbox chokepoint + shared ledger; strip reply footers; golden tests.
- **M3 — Go-live.** Provision VPS; pair bridge; secrets; timers on; seed ≥20 real reminders; GitHub Pages + PWA pinned; run SPEC §11 acceptance.
- **M4 — Harden.** Role roster; Phase-F accuracy review; family-criticals PO call; milestone review.

Rollback at any point = `git revert` + redeploy; the Sheet schema only ever gains columns (additive, backwards-compatible — old rows without M/N/O are treated as never-tombstoned).

## 10. Git & repo conventions

- `main` is deployable; small focused commits; imperative subjects; body explains *why* when non-obvious.
- Working sessions commit at session end minimum (the leader pushes; Pages + deploy.sh consume `main`).
- No long-lived branches — this is a two-committer repo (Adar + Claude-in-session).
- Tags: `v1-live` at M3 acceptance, then `vX.Y` per milestone.

## 11. Review ritual (revised 2026-06-11)

Reviews fire on **milestones**, not every session: new spec, architecture change, anything touching delivery/budget/privacy guarantees, and each M-milestone close. Mechanism: `automation/review.py` builds the prompt + attachment list; reviewer = best available external model (Gemini default; substitutions logged). Output is resolved in-session as Apply / Defend (reason appended to the affected doc §History) / Open (PO question), and the resolution lands in `DECISIONS.md` if directional. Tiny edits never trigger review. On milestone-closing sessions the gate runs **blocking inside the handoff chain** (`… && review gate && git commit && git push` — Porto pattern, D-023): a MAJOR finding stops the commit until resolved or explicitly overridden by the PO.

**review.py contract:** inputs = `--lane` (drives default attachments; `milestone` attaches all five canon docs), `--changes` (a PATH to a markdown bullet list of what the session changed — conventionally `reviews/session_changes_<date>_<M>.md`, tracked — or `-` for stdin; never the bullets inline), optional `--extra-files`, `--provider ollama|deepseek`; output = the assembled prompt (`--dry-run`) or the model's review, always saved under `reviews/review_*.md` as the audit trail (tracked). Failure behavior: a failed or truncated review never blocks a milestone — log the failure, proceed, and note it in `BACKLOG.md`. DeepSeek is a built-in provider since M1 (folded in from `run_review_deepseek.py`): plain + `--chunk` modes, key from `DEEPSEEK_API_KEY` env only. Without any provider key the script writes a clearly-marked MOCK audit file — that is not a review; rerun with a key.

## 12. Definition of done (any work item)

Code merged with tests for its logic · constants in config · errors either degrade or surface (no silent paths) · contracts updated in SPEC/DESIGN if changed · BACKLOG status flipped · deployed and observed green once on the appliance.

=== End: ENGINEERING.md ===

=== File: DESIGN.md ===
# Family Inc. — Design Specification

*The product has two surfaces: WhatsApp messages and the dashboard PWA. Both are designed here. v2.0 · 2026-06-11 · supersedes `Archive/05_Dashboard_Design.md` (absorbed, contradiction fixed: the offline model is queue + tombstone everywhere; the "explicit lock" wording is dead).*

---

## 1. Design principles

1. **Calm tech.** The system reports what happened and what's next; it never scolds, streaks, paces, or counts what you missed. Quiet days are a success state, not an empty state.
2. **The message is the product.** Most days the family touches Family Inc. only through WhatsApp. Message copy gets the same design rigor as pixels.
3. **Dense, then disclosed.** Today shows every domain at a glance; detail hides behind one tap. Linear/Notion density, not wellness-app whitespace.
4. **Partner-symmetric surfaces.** Attribution without scoring: domain leads, names follow.
5. **Honest affordances.** Nothing on either surface suggests an action the system can't take (no reply commands until reply parsing ships; no disabled-looking-but-tappable buttons).
6. **Hebrew-first, RTL-first.** English is the fallback, not the default. LTR runs (numbers, URLs) wrapped in `<bdi>`.

## 2. Visual system (dashboard)

### Color — warm paper + indigo

| Token | Light | Dark | Use |
|---|---|---|---|
| `--surface` | `#FAF8F5` | `#15161A` | page |
| `--ink` | `#1A1A1F` | `#E8E6E1` | text |
| `--muted` | `#71717A` | `#A1A1AA` | secondary text, ticks |
| `--accent` | `#5E6AD2` | `#5E6AD2` | arc, links, active tab |
| `--ok` | `#3F8F5F` | sage | all-clear, success |
| `--warn` | `#C58B3A` | amber | due-today |
| `--alert` | `#C44545` | terracotta | overdue |

Semantic colors appear only on status; the accent is the single brand color. No gradients except the skeleton shimmer.

### Type

- **Heebo** — Hebrew UI (default chrome).
- **Inter** — Latin UI (fallback chrome); tabular figures on.
- **Geist Mono** — money only (`₪4,280`) so amounts read as data at a glance.
- Scale: 17/15/13 body-secondary-caption; one display size (28) for the arc number and drawer KPIs. No font weight above 600.

### Components

- **Progress arc** (fixed 56px strip): ring + "N completed · last 7 days" + seven weekday ticks (✓/·). Rolling count, never a streak; never shows a target or deficit. Tap → per-domain mini-arcs.
- **Status banner**: one line — red if any overdue, amber if any fire-today, sage "all clear" otherwise.
- **Reminder row**: flag dot · title · due phrase; tap reveals `✓ done` `+Nd` `note` pills. Snooze pills: 1/3/7/14/30.
- **Domain drawers** (Money/Health/Goals/Car/Contracts): closed = one big KPI + sparkline; open = detail list. 
- **Bright-line goal viz**: target line + actual line + safety band (ahead/on-pace/behind) for multi-year goals — progress bars are banned for anything >90 days.
- **Appreciation ticker**: last 7 completions, grouped by domain, name + relative time inline. Non-interactive by design (a passive surface can't become a scoreboard).
- **Connection pill**: 🟢 live / ⛔ offline — N queued. The only place sync state appears.
- **Sticky status pill** (top): one-liner like "Weekly briefing ready · 2 alerts" — our budget-friendly stand-in for OS-level notification surfaces.

## 3. Information architecture (Today-first)

```
Today (home)
├── Header: Family inc. · date · sticky status pill · connection pill
├── Progress arc strip
├── Banner (overdue / today / all-clear)
├── TODAY — reminders where Auto-flag ∈ {OVERDUE, FIRE TODAY}
├── CALENDAR — today's Calendar-Events
├── NEXT 7 DAYS — week-out reminders + events
├── ▸ Drawers: Money · Health · Goals · Car · Contracts
└── RECENTLY COMPLETED — appreciation ticker
Briefing tab — latest weekly briefing rendered
Settings tab — sign-in · Sheet ID · language toggle · demo toggle · queue inspector
```

Rationale (kept from the four-direction exploration, `Archive/05`): Today-first wins the 8 AM glance; tiles demote to drawers; briefing gets a tab, not the home; stream and briefing-first lose on weekday staleness.

## 4. States

- **Loading**: skeleton shell <50ms with cached-snapshot shapes (counts from cache, else 3/2/3/4 rows); shimmer 1.6s; header/pills/tabs are real from t=0; cached values replace skeletons, live values cross-fade 120ms. Skeletons never shimmer while offline — static gray is more honest.
- **Quiet day**: arc keeps its ticks, banner shows sage "all clear", TODAY renders "(nothing urgent)", ticker shows the week's wins. The screen is never blank.
- **First run / empty ticker**: "Marks of work done will show up here." No CTA.
- **Offline**: pill flips to "⛔ offline — N queued"; rows keep working; a queued row shows "⏳ queued — will sync on reconnect"; ticker shows "will refresh after sync". **Buttons never disable offline.**
- **Write failure (online)**: optimistic UI rolls back; inline "Couldn't save — retry?"; token expiry → silent refresh once, then a re-sign-in banner.
- **Back from vacation (30 overdue)**: top 10 by due date + "+20 more" expander; banner offers bulk-done multi-select; arc shows the honest low count with zero commentary.

## 5. Interaction contract (write-back)

Every tap maps to one batched Sheet write per SPEC §6.1 (intent columns + `DoneAt`/`LastDoneBy` on completion + `WriteQueue_Tombstone` always):

| Action | Writes | UI |
|---|---|---|
| ✓ done | Status=Done, DoneAt, LastDoneBy, Tombstone (+ recurrence bump) | row → ticker prepend under its domain |
| +Nd | Due+=N, Status=Snoozed, Tombstone (no DoneAt — snooze isn't completion) | row re-sorts |
| note | append to Notes with `[date name]` prefix, Tombstone | inline confirm |

Offline: same writes queued (`localStorage.pendingWrites[]`, cap 50 with a one-shot loss warning at the cap); flush in tap order on reconnect; idempotent via tombstone.

## 6. WhatsApp message design system

The most-used UI in the product. Rules:

- **One morning message.** Engine fires, group digest, and Hebcal line are assembled into a single 07:30 message per recipient — never 2–3 separate sends.
- **Line economy.** One line per item: flag emoji · title · due phrase. Notes only if ≤120 chars. >5 items → top 5 by priority + "+N more — בלוח" (in the dashboard).
- **Emoji are semantics, not decoration**: 🔴 overdue · 🟠 today · 🟡 week-out · 🟢 month-out · ⚠ needs-a-look · 🕯 Shabbat line. No other emoji in generated copy.
- **No reply affordances** until reply parsing ships (SPEC §3.7). Messages end with content, not instructions. When v1.1 lands, the reply grammar returns as a single footer line.
- **Hebrew copy register**: short, warm, zero exclamation marks, no imperatives toward a person ("לקבוע תור" not "תקבעי תור!"). Dates as "יום ג׳ 17/6". Money as ₪ with thousands separator.
- **Attribution mirrors the ticker**: domain first, name inline.

### Templates (v1)

Daily digest (the only routine alert-channel message):

```
🏠 Family inc. · יום ו׳ 12/6
🔴 טסט שנתי לרכב — באיחור 3 ימים
🟠 תור שיניים לילד — היום
🟡 ביטוח דירה — בעוד 6 ימים

קבוצות (24ש׳):
גן — מחר יום פרי, להביא 🍐 (גננת, 22:14)
ועד — מעלית מושבתת חמישי 09:00–12:00

🕯 הדלקת נרות 19:24 · צאת שבת 20:35
```

Critical (budget-bypassing, rare): single line, no frame — `⚠ {group}: {one_liner} ({sender}, {time})`.

Weekly briefing (Sat 21:00): five scenes, vertical, one line each opener — *the week's spend · kids' moment · next week's three things · one goal line · one contract heads-up* — then short sections. Strava-year-in-review meets Morning Brew; typography is the design.

Bridge-health warning prepends, never replaces: `⚠ הגשר שקט 14 שעות — ייתכן שפספסנו הודעות`.

## 7. i18n rules

- `<html lang="he" dir="rtl">` default; `localStorage.familyinc.lang="en"` flips lang/dir + chrome strings (pre-paint, no flash).
- Logical CSS properties only (`padding-inline-start`); no left/right literals.
- Chrome strings in the parallel STRINGS table; data values (merchants, group names, guide links) render Hebrew regardless of toggle.
- Dates `DD/MM`, week starts Sunday, `he-IL` number formatting in both languages (the audience is Israeli in either chrome).
- Brand stays Latin "Family inc." everywhere incl. home-screen title.
- WhatsApp messages are Hebrew-only (no toggle exists there; the recipients are known).

## 8. Accessibility & ergonomics

Tap targets ≥44px; contrast AA against both surfaces (the muted zinc fails on dark — use `#A1A1AA` minimum); focus-visible outlines on; reduced-motion media query kills shimmer + cross-fades; PWA `apple-touch-icon` relies on the OS glass treatment, no fake translucency in-app; thumb-zone: action pills render below the row, not above.

## 9. Manual smoke checklist (per dashboard deploy)

1. Cold load <1s on phone over LTE; skeletons → live without layout shift.
2. Hebrew default renders RTL with no mirrored numerals; toggle flips chrome only.
3. Mark done online → row moves to ticker, Sheet shows M/N/O stamped.
4. Airplane mode → tap done → pill shows queued → reconnect → flush + ticker refresh; engine log shows tombstone skip if within window.
5. Demo toggle never touches the live Sheet.
6. Lighthouse PWA installable; offline reload serves shell + cached data.

## 10. History

- 2026-06-11: v2.0. Absorbed `Archive/05_Dashboard_Design.md`; removed the contradictory "explicit offline lock" refinement (queue+tombstone is the single offline model); elevated WhatsApp messages to a designed surface; banned reply affordances until parsing ships; single-morning-message rule added.
- 2026-05-30: arc/ticker/skeleton/queue+tombstone refinements; Hebrew-default chrome; domain-grouped ticker (post-review resolutions preserved in `Archive/05_Dashboard_Design.md`).

=== End: DESIGN.md ===

=== File: DECISIONS.md ===
# Decision Log

*One row per decision: ID · date · decision · why · what it superseded. Newest first; IDs ascend chronologically (D-001 = oldest). Reference decisions anywhere as `D-0NN`.*
*This is the only place decisions live. Specs describe the current state; this file explains how we got here.*

| ID | Date | Decision | Why | Supersedes |
|---|---|---|---|---|
| D-027 | 2026-06-12 | **M3 session-1 contract resolutions** (delivery infrastructure). (a) Daily digest queues **kind=briefing** — it was kind=alert, consuming 1 of the 2/day alert slots and, worse, deferrable by the ledger *into the next digest* (circular, since over-budget alerts defer INTO the digest, D-025/D-026); SPEC §7.2 clarified. (b) SPEC §10.2 email fallback **built** (`lib/mailer.py`, the only smtplib import): heartbeat stale >24h → digest goes by SMTP, identical content, stamps normally; both-transports-down queues to the bridge outbox and shouts. Documented as transport substitution, NOT an outbox bypass — content already passed outbox policy. (c) `recipients.json` moved to `/etc/family-inc/` (code now matches ENGINEERING §2; local file = dev fallback). (d) Pages serves `dashboard/` via Actions workflow (branch-mode can't serve subdirs); gitignored `config.js` is **generated from Actions secrets** at deploy — ids reach the live site without entering git history (D-024 lineage). (e) Fail-flag semantics: `OnFailure=family-fail-flag@%n.service` appends to `logs/fail.flag`; the next **delivered** digest reports + clears; weekly briefing surfaces still-uncleared flags. (f) D-024 completion: kid names/health details scrubbed from 10 tracked `Setup/`+`reviews/` files the purge missed, and 8 personal `Archive/` docs (kickoff output, money baseline) untracked + gitignored — Archive stays the public paper trail minus personal data; git *history* still holds old blobs, rewrite deliberately deferred | Go-live runs on this plumbing; each item was a SPEC-vs-code disagreement or an unwired contract surfaced while writing `deploy/` — PO (Adar) called all six in-session | Digest kind=alert; bridge-dir recipients.json; unspecified Pages mechanism; unwired OnFailure hook; tracked personal Archive docs |
| D-026 | 2026-06-12 | **M2 milestone review run (DeepSeek) and resolved: 2 wording applies (SPEC §8.3 one-clock tombstone semantics; §7.1 validate-before-write clause), 5 defends, 0 open — no direction changes.** Notable defends: deferral is consumption into tomorrow's digest (no re-queue loop); no aging-into-critical bypass (erodes the 2/day principle); schema guard stays uniform across backends. Full table appended to the audit: `reviews/review_milestone_2026-06-12_10-45.md` | Milestone-only ritual: M-close qualifies (D-012); blocking gate inside the handoff chain (D-023) | — |
| D-025 | 2026-06-12 | **M2 contract resolutions** (one source of truth port). (a) SPEC §7.1 errata: engine reads Status ∉ {Done, Skipped} — the spec'd ∈ {Pending, Snoozed, Overdue} would kill multi-lead-time chains after the first `Sent` stamp; same-day re-fires blocked by a Last-Sent guard instead. (b) Machine datetime stamps (Last Sent/DoneAt/Tombstone) = ISO-8601 `T`-form TEXT on both surfaces; dashboard tombstones re-stamped at flush time and carry hour resolution (date-only tombstones had silently disabled the §8.3 race guard). (c) Col H is engine-owned — dashboard stopped writing it on ✓done. (d) Recurrence bump = one rule both sides (`lib/dates.bump_due` ↔ `bumpDate()`): month-end clamp + review flag; Custom never guessed, flagged. (e) Live hot-tab rolloff deferred to M4. (f) Reply-ack outbox kind (solicited vs the unsolicited budget) = open PO call at v1.1 reinstatement | The gspread port made both surfaces write the same sheet for real — every place they disagreed (or quietly broke a guard) had to be resolved before go-live | SPEC §7.1 status-set wording; dashboard H-writes; date-only tombstones; JS date-overflow bump |
| D-024 | 2026-06-12 | **Personal-data purge of the tracked tree (M1).** Seed CSVs (reminders/vaccines/goals/group-config) → gitignored `seeds/`; `Dashboard/config.js` (real emails, Sheet ID slot) untracked with `config.example.js` committed; kids' names+birthdates scrubbed from attic mocks and the review-prompt template; home-town strings dropped from code comments/mocks. Committed code now carries placeholders only | D-013 says portfolio-grade public repo; the audit found names, a child vaccine schedule, and a real email tracked — enforcement, made explicit so it survives future sessions | Tracked seed CSVs; tracked `Dashboard/config.js` |
| D-023 | 2026-06-12 | **Port Porto workflow patterns:** D-numbered decisions, `Automation/session_kickoff.py` regenerating `NEXT_SESSION_PROMPT.md` each session end, and the single terminal handoff block ritual. NOT ported: separate `state.md` (status stays only in `BACKLOG.md`), per-commit blocking gate (milestone-only reviews stand; the gate is blocking inside milestone-close handoff chains) | Porto's continuity system solves the exact failure mode of the Hermes divergence; Family Inc keeps its one-source-of-truth and lighter review cadence | Ad-hoc session handoffs |
| D-022 | 2026-06-12 | **Hermes parallel sprint integrated.** A second AI session ("Hermes") had pushed 15 commits to origin from another clone; 10 code commits cherry-picked onto the remake (tests ×55, `config.py`, reply parsing, quiet-hours/batch-window impl, fixes), 5 doc/status commits superseded by the remake. "Hermes" naming **not adopted**. Originals preserved on `remote-backup` branch | Real work must not be lost; remade docs supersede its doc edits | Hermes doc commits A1–A4, Progress-page status |
| D-021 | 2026-06-12 | **Sessions must `git pull --ff-only` before any work; origin is the sync point between agents** (session protocol step 0) | Two sessions diverged silently for a week — local audit was stale against pushed work | Implicit "local folder is current" assumption |
| D-020 | 2026-06-12 | Remake milestone review run (DeepSeek; Gemini unavailable this session) and resolved: 6 applies (schema-drift guard, data-driven tombstone tuning, specified email fallback, review.py contract, auth-state restore note, no-digest runbook), 5 defends, 0 open — no direction changes. Audit: `Briefings/review_remake_2026-06-12.md` | Milestone-only ritual: a new spec qualifies | — |
| D-019 | 2026-06-11 | **Full remake.** Canon docs = `SPEC.md` + `ENGINEERING.md` + `DESIGN.md` + `DECISIONS.md` + `BACKLOG.md`; superseded docs → `Archive/` | 4 competing sources of truth for status; doc sprawl outpaced shipping | All numbered docs |
| D-018 | 2026-06-11 | Runtime = **one VPS** ("the appliance"): Baileys bridge + systemd timers + all Python | Bridge needs always-on anyway; no home hardware; one failure domain | Cowork scheduled tasks, Render cron, "always-on home machine" |
| D-017 | 2026-06-11 | v1 scope = **keystone + group summarizer**; six lanes frozen (see `BACKLOG.md`) | Ship the loop that justifies the system; breadth-first is how nothing went live | "All lanes active" |
| D-016 | 2026-06-11 | Python Sheets access = **gspread + service account**; local `Family_OS.xlsx` demoted to seed template | openpyxl-vs-gapi split = two diverging sources of truth, violating principle #1 | openpyxl reads of local xlsx |
| D-015 | 2026-06-11 | **Alert budget enforced at the outbox** (single daily ledger, all senders), not per-script | Engine + summarizer each kept their own 2/day counter → combined 4+/day possible | Per-script budget counters |
| D-014 | 2026-06-11 | WhatsApp messages **must not advertise reply commands** until reply parsing ships (v1.1) | Current templates promise `✅ done` replies that go nowhere — dishonest UI | Reply footers in message templates |
| D-013 | 2026-06-11 | Docs are **portfolio-grade**: English, self-contained, public-repo-ready; personal data lives only in gitignored config/seeds | Doubles as a showcase artifact for Adar's job search (Goal 2) | Internal-only doc tone |
| D-012 | 2026-06-11 | Review ritual = **milestone-only** (new spec, architecture shift, go-live), via `review.py`, best available external model, Gemini default | Per-session reviews drifted (DeepSeek/Ollama substitutions); codify reality | Per-session mandatory Gemini review |
| D-011 | 2026-06-11 | Currency = **ILS everywhere**; weekly briefing = **Sat 21:00** | Kickoff mixed USD/ILS; docs disagreed Sat 21:00 vs Sun 18:00 | Mixed currencies; Sun 18:00 |
| D-010 | 2026-06-04 | WhatsApp delivery = **self-hosted Baileys outbox**; Twilio dropped to documented fallback | ₪0 marginal, no WABA verification, no template approval, free-form Hebrew | "WhatsApp via Twilio" (D-001) |
| D-009 | 2026-06-02 | Bridge = **self-hosted Baileys** (not Whapi/Green API); all 5 groups in, incl. family | Free + plaintext never leaves the box we control | Whapi.cloud fast path |
| D-008 | 2026-06-02 | **Per-group alert routing** (daycare/building → both; student → Adar; family/neighborhood → digest-only) + **critical-keyword bypass** of the daily cap | Relevance is per-group; emergencies must never queue behind mundane alerts | Global routing; flat 2/day cap |
| D-007 | 2026-05-30 | Offline model = **optimistic queue + per-row tombstone** (`WriteQueue_Tombstone`, 6h skip window) | No cognitive load offline, no engine race | Explicit offline lock (disabled buttons) |
| D-006 | 2026-05-30 | **No PWA push.** WhatsApp is the only alert channel | One channel, one budget | PWA web-push proposal |
| D-005 | 2026-05-30 | Dashboard chrome **Hebrew default, RTL**, English fallback toggle; data values stay Hebrew | Household reads Hebrew; toggle costs little | English-default chrome |
| D-004 | 2026-05-30 | Appreciation ticker grouped by **domain**, names inline | Avoid leaderboard/scoring read between partners | Person-grouped ticker |
| D-003 | 2026-05-30 | Palette = warm-paper + indigo `#5E6AD2`; type = Inter + Heebo + Geist Mono | Calm-tech; Hebrew/Latin metric parity; money legibility | Green `#2d5f3f` palette |
| D-002 | 2026-05-30 | Kickoff agreements: alert budget **2/day hard cap**, both adults get everything, weekly review Sat 21:00, nothing off-limits to track | Joint PO session output | — |
| D-001 | 2026-05-25 | Storage = Google Sheets + Drive; dashboard = vanilla PWA; finance = CSV drops (now frozen) | Boring tech; both adults already on Google | — |

## How to add a decision

Append a row at the top with the next ID. If it changes a contract, update `SPEC.md`/`DESIGN.md` in the same commit. If it's a major directional call, both POs decide (see `CLAUDE.md` → Decision authority).

=== End: DECISIONS.md ===


```

</details>
