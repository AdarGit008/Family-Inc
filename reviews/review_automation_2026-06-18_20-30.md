# Milestone review — automation lane

- **When:** 2026-06-18T20:30:16
- **Provider:** DeepSeek (`deepseek-chat`)
- **Elapsed:** 16.3s
- **Attached files (7):**
  - `CLAUDE.md` (5,311 chars)
  - `SPEC.md` (35,548 chars)
  - `BACKLOG.md` (12,460 chars)
  - `ENGINEERING.md` (13,878 chars)
  - `automation/lib/outbox.py` (12,416 chars)
  - `automation/bridge/baileys_listener.js` (19,271 chars)
  - `tests/test_outbox.py` (10,412 chars)

---

## Response

### Concerns

1. **[HIGH] `lib/outbox.py` `read_deferred()` and `pop_deferred()` have no versioning on the deferred JSONL.** If a crash or deploy rewrites the DEEFERRED_FILE between the `read_deferred()` peek (used by digest assembly to know what to include) and `pop_deferred()` (the actual consumption by the digest runner), the digest could be built with items that are later lost, or items could be double-included. The deferred file is read-written without atomicity, and the pop's filter logic (`< upto.isoformat()`) is a fragile date comparison.

2. **[MEDIUM] `test_outbox.py` `test_corrupt_ledger_fails_closed` uses `tmp_runtime` but does not verify the log was written.** The test asserts deferral + critical bypass but never asserts that `log.error()` was called with the expected message. This means the alert path (human operator sees the ERROR log) is untested, and silent failure of the logging itself would go undetected.

3. **[MEDIUM] `bridge/baileys_listener.js` the sent-file dedup filter (`status === 'sent' || status === 'refused_unknown_recipient'`) includes `refused_unknown_recipient` which is written when the scope guard rejects a JID.** This is brittle: if a legitimate recipient JID is typoed in `recipients.json`, the row is permanently refused and *never retried* even after the file is corrected. A `refused_*` status should be retryable on next deploy/restart, not permanent.

4. **[LOW] `lib/outbox.py` `_seen_pairs()` reads the entire outbox file and sent file into memory on every `queue()` call.** For a daily volume of ~10 messages this is fine today, but `_seen_pairs()` is called inside the `_ledger_lock` context for alerts, holding an exclusive lock while scanning potentially large files. If the outbox/sent files grow (e.g., a runaway sender or a bug), this blocks all alert sends.

### Missed alternatives

- Use a database (SQLite) for the ledger instead of JSONL files + flock, giving atomic reads and row-level locking.
- Replace the two-file deque (`outbox.jsonl` + `sent.jsonl`) with a single SQLite table where rows are deleted on confirm, eliminating the full-file scan for dedup.
- Implement `pop_deferred()` as an atomic rename of the entire deferred file to a temp name, then filter from the temp file — eliminates the read-then-write race.
- Use the `watcher` package in Node to trigger `processOutbox()` on file-change instead of polling every 15s (POLL_MS) even when idle.

### Affirmations

- **Fail-closed on corrupt ledger:** Correct choice. A silent budget reset on disk corruption would violate the entire alert-budget principle. The exception for criticals also correctly honors safety.
- **Per-row try/catch in the bridge's `processOutbox()`:** Correct. A transient failure on one message should not block the entire batch. Recording `send_failed` (not `sent`) ensures retry.
- **`fcntl` lock around the alert check+increment:** Correct. The single-shared-ledger rule exists precisely because of this race; the lock closes it without adding a new dependency.
- **Deferring GAP-2 (stamp-after-deliver) to a separate pass:** Correct. The described cross-run reconcile is the right design; a rushed first-cut with an in-run wait would create a worse risk (duplicate digests).

### Concrete suggestions

1. **Replace `pop_deferred()` implementation** in `lib/outbox.py` with an atomic approach: rename `DEFERRED_FILE` to a temp name, filter from the temp file, and write remaining items back to a new `DEFERRED_FILE` atomically (tmp + replace). This eliminates the race where a co-developer's `read_deferred()` interleaves with `pop_deferred()`.

2. **Add a `corrupt_ledger_logged` assertion** to `test_outbox.py::test_corrupt_ledger_fails_closed`: replace the comment "deferred, not flooded" with a concrete assertion that `log.error` was called with the expected message, using `caplog` from pytest.

3. **Change `refused_unknown_recipient` to a retryable status** in `bridge/baileys_listener.js`: exclude `refused_*` from the `done` dedup set so that after an operator repairs `recipients.json` and restarts the bridge, all previously-refused rows are retried. The scope guard still works — only valid JIDs will eventually match.

### One question for the team

Given that this session explicitly deferred GAP-2 (stamp-after-deliver) which is the [HIGH] silent-loss path for the "fail loud" principle — when is the earliest session slot scheduled to implement the cross-run reconcile, and has the risk window been accepted by both POs in writing?

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
# Session changes — Brief 2, Lane B (robustness seams) — PARTIAL

Source: `reviews/fix_brief_2_…` Lane B (review-triggering — touches the budget /
delivery chokepoint). Tests 357→358. This is the bounded, low-risk subset; GAP-2
is deliberately deferred (below).

## Landed

- **outbox-budget#1 (`lib/outbox.py`).** The per-day budget ledger now (a) WRITES
  atomically — tmp file + `replace()` — so a crash can't leave a torn ledger, and
  (b) READS **fail-CLOSED**: a corrupt/unreadable ledger is treated as cap-reached
  (returns `{adar: CAP, shanee: CAP}`) and logged at ERROR, so alerts **defer**
  (ride tomorrow's digest, never lost) instead of the previous fail-OPEN behavior
  that silently reset the day's hard cap to 0 and could flood. Criticals still
  pierce (budget-exempt) — a corrupt ledger must never block safety.
- **outbox-budget#2 (`lib/outbox.py`).** An `fcntl.flock` exclusive lock
  (`_ledger_lock`) wraps the whole alert check+increment, so two concurrent
  senders can't each pass the 2/day check on a stale read — the exact race the
  single-shared-ledger rule (D-015) exists to prevent.
- **GAP-10 (`bridge/baileys_listener.js`).** `processOutbox` now wraps each
  `sendMessage` in try/catch: one failed send no longer abandons the rest of the
  poll (head-of-line block). A transient failure is recorded as `send_failed`
  (NOT in the `done` set → retried next poll); only terminal `sent`/`refused`
  outcomes suppress a retry.
- **GAP-8 (`SPEC §8.3`).** The multi-timer Sheet race documented as accepted: the
  timers are staggered (06:00/07:25/07:30/property) and write disjoint tabs;
  `gspread` batches are atomic per call; v1 attempts no cross-timer transaction.

## Deferred (and WHY)

- **GAP-2 [high] stamp-after-deliver + outbox-budget#3 (pop-deferred-after-confirm).**
  These change the delivery contract (when Last Sent / Status / fail-flag-clear /
  deferred-consume happen — on the bridge's *confirmed* delivery, not the mere
  queue). A first cut using a bounded in-run wait was reverted: it risks duplicate
  digests if the bridge's delivery latency ever exceeds the wait window, and it's
  awkward to test cleanly. The correct design is a **cross-run reconcile** — stamp
  whenever the bridge eventually confirms via `whatsapp_sent.jsonl`, keyed by the
  digest msg_id, with stale-expiry — which deserves its own careful pass with
  full tests + the review gate, not a rushed tail-of-session change. (4 existing
  delivery tests in test_engine/test_mailer encode the old contract and will need
  adapting then.)
- GAP-3 (JSONL rotation), bridge-node#2 (bridge scope-guard Node test harness) —
  separate surface, lower severity.

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

*Auto-loaded at the top of every session opened in this folder. Consolidated 2026-06-17 (the SPEC bump: canon rewritten clean, the D-NN decision log retired to `Archive/`). Keep under 100 lines.*

## What this is

A household operating system for Adar + Shanee (+ 2 young kids, adult-mediated). Master DB = the `Family_OS` Google Sheet. Two product surfaces: WhatsApp messages (self-hosted Baileys bridge) and a PWA dashboard pinned to both iPhones. All automation runs on **one VPS** ("the appliance"). Israeli context throughout: Hebrew/RTL, ILS, Asia/Jerusalem, Maccabi, Hebcal.

## Canon — four documents, one job each

| Doc | Owns | Open it for |
|---|---|---|
| `SPEC.md` | what the system is: scope, architecture, data model, contracts, policies | any contract or "how should X behave" |
| `ENGINEERING.md` | how it's built/run: repo layout, toolchain, VPS, deploy, tests, ops | any "how do we do X" |
| `DESIGN.md` | both surfaces: dashboard UI + WhatsApp message design, i18n, states | any pixel or copy question |
| `BACKLOG.md` | what's next: shipped, in-progress, gated, v1.1, frozen lanes | what to work on / what's frozen |

Each doc is a **present-tense snapshot** — it describes the current state, not the history. `Archive/` holds superseded docs and the full dated decision history (the old `DECISIONS.md` D-001…D-052 log) — read-only, for "didn't we decide…". Status lives **only** in `BACKLOG.md`.

## Roles & authority

| Role | Person |
|---|---|
| CTO + co-PO | **Adar** — engineering direction, ships code |
| Chief Design + co-PO | **Shanee** — product direction, UX feel |
| Lead Architect | **Claude** — design, code, tradeoffs; defers to POs on product, to Adar on engineering detail |
| Reviewer | external model via `automation/review.py` (DeepSeek default) — milestone reviews only |

Either PO can lead a session and take routine calls solo; major directional calls (new feature, principle change, removing shipped behavior) are joint. Session leader = whoever opened the session; Claude treats them as "the PO" unless they defer.

## Non-negotiable principles (full versions: SPEC §3)

One source of truth per domain · boring tech · alert budget 2/day enforced at the outbox (criticals bypass, briefings exempt) · briefings > notifications · partner-symmetric, no scoring · fail loud, degrade quiet · never promise an affordance that doesn't exist · no money movement, no credential storage (except appliance-local read-only finance logins), no messages beyond the two adults, no kid-facing UI.

## Current state (live)

**v1 live & accepted since 2026-06-13 (`v1-live`).** Running on the appliance: the keystone loop (reminders → WhatsApp digest + dashboard write-back), the weekly briefing (deterministic template), the group summarizer (on **DeepSeek**, keyword fallback keyless), and the **property tracker** (Yad2 on-box + Madlan via Apify, silent listings in the morning digest). Delivery has an email fallback; the outbox enforces the budget.

**Building: M6 finance ingestion** (banks + cards, read-only, categorized + trends, silent delivery). The repo half is built and tested; the appliance step (place `bank_creds.json`, rename the 3 live-Sheet finance tabs, first interactive OTP) is next. **Gated to ~2026-06-20** (needs ≥1 week of live data): the first real classifier-accuracy run + the external milestone review. Full status: `BACKLOG.md`.

## Session protocol

0. `git pull --ff-only` before touching anything — other agents push to origin; the local folder is not assumed current.
1. Read `BACKLOG.md` first — it says where we are.
2. Work the current item; don't open new lanes without a PO call.
3. Constants go in config, utilities in `automation/lib/`, message copy in templates (reviewable against `DESIGN.md` §6).
4. **Decisions fold into the canon, not a log.** A directional call = edit the relevant doc to the new present-tense state, add a short inline *why* if it's non-obvious, and carry the dated rationale in the commit message. Major/joint calls land the same way. (The separate D-NN log is retired; git history is the dated record.)
5. Session end: tests green if code moved, `BACKLOG.md` statuses flipped, `python3 automation/session_kickoff.py` regenerated `NEXT_SESSION_PROMPT.md`, and the PO gets ONE terminal block (stage → review gate if milestone-closing → commit → push) to run on their machine.
6. **Milestone reviews only** (new spec / architecture shift / budget-privacy-delivery change / each milestone close): run `automation/review.py`, resolve as Apply / Defend / Open. Tiny edits never trigger a review.

## Guardrails for Claude in this repo

- Never put names, phone numbers, JIDs, or real finance values in committed files — they belong in the Sheet, `/etc/family-inc/`, or gitignored seeds (the repo is public-portfolio-safe by construction).
- Never add an alert path that bypasses the outbox chokepoint (`automation/lib/outbox.py`).
- Schema changes are additive-only on the Sheet (old rows must keep parsing).
- Committed ≠ deployed: a feature or placed secret is inert until `deploy.sh` pulls it; confirm the box is at origin HEAD before declaring anything live.
- Git operations run on the PO's machine, never in a sandbox.
- If SPEC and code disagree, say so before "fixing" either.

=== End: CLAUDE.md ===

=== File: SPEC.md ===
# Family Inc. — System Specification

*What the system is: scope, architecture, data model, contracts, policies. v3.0 · 2026-06-17.*
*This is a present-tense snapshot — it describes how the system behaves today, not how it got here. The dated history (every prior "we changed X to Y" rationale) lives in `Archive/`. Companions: `ENGINEERING.md` (how it's built and run) · `DESIGN.md` (how it looks and reads) · `BACKLOG.md` (what's next).*

---

## 1. Overview

Family Inc. is a household operating system for a two-adult, two-child family in Israel. It watches the family's obligations — appointments, renewals, deadlines, school/daycare chatter — and reflects them back through **two calm surfaces**: a small number of WhatsApp messages, and a PWA dashboard pinned to both adults' iPhones. The master database is a single Google Sheet. The automation runs unattended on one small VPS ("the appliance").

The core promise: **nothing important gets dropped, without anyone having to watch a screen.**

### What it is not

- Not a chore-gamification app. No streaks, no scores, no nagging.
- Not a kid-facing product. Children's data is structured but adult-mediated.
- Not a finance robot. It never moves money; the only financial credentials it holds are appliance-local, read-only portal logins used to *read* balances and transactions.
- Not a chat bot. It speaks at scheduled moments, or for genuine urgency, within a hard budget.

## 2. Context

| | |
|---|---|
| Household | 2 adults (joint product owners) + 2 young children |
| Locale | Israel — Hebrew-first, RTL, ILS, Sunday-start week, Jewish-calendar aware (Shabbat, chagim) |
| Healthcare | Maccabi (no public API — any ingestion is mail/manual) |
| Devices | Two iPhones (PWA + WhatsApp), one VPS, no other infrastructure |
| Cost ceiling | ~₪120/mo all-in (VPS ~₪20 + LLM ~₪35 + margin). Anything above needs a PO call |

Roles and decision authority live in `CLAUDE.md`. Personal data — names, phone JIDs, health specifics, real budgets — lives only in the Sheet and in gitignored config/seed files, never in committed code or docs. The repo is public-portfolio-safe by construction.

## 3. Operating principles

Phrased so a reviewer can check compliance:

1. **One source of truth per domain.** Every datum has exactly one authoritative home (almost always a Sheet tab). Anything else holding it is a cache or a view, and is allowed to be lost.
2. **Boring tech.** Google Sheets over a database; vanilla JS over a framework; systemd timers over orchestration; JSONL files over message queues. A new dependency must remove a failure mode, not just add a capability we like.
3. **Alerts are a budget.** Hard cap of 2 unsolicited messages per recipient per day, enforced at one chokepoint (§7.5). Critical-safety messages bypass it with an audit trail. Scheduled briefings are exempt — they are appointments, not interruptions. *(Enforced in one place because two scripts that each kept their own 2/day counter could combine to 4+/day.)*
4. **Briefings > notifications.** The default unit of communication is a scheduled digest. A real-time message is the exception that must justify itself.
5. **Partner-symmetric.** Both adults see everything, can act on everything, and appear as equals. No leaderboards, no scoring.
6. **Fail loud, degrade quiet.** Infrastructure failures surface in the next briefing ("bridge silent 14h"), never as silence. Feature degradation (LLM down → deterministic fallback) must not page anyone.
7. **Never promise an affordance the system doesn't have.** No reply commands in messages until reply parsing ships; no buttons that don't write.

## 4. Scope

### Live today

| Capability | One-line contract |
|---|---|
| Reminders engine | Daily 07:25: read the Reminders tab, compute due / lead-time / overdue fires. |
| Daily digest | Daily 07:30: assemble engine fires + WhatsApp group digest + new-property listings + Hebcal line into **one** message per adult, and send. **Both adults every day** (§7.2). |
| Weekly briefing | Sat 21:00: whole-Sheet narrative rendered from a deterministic template. |
| Hebcal enrichment | Friday/holiday awareness lines in briefings (candle-lighting, chagim). |
| WhatsApp summarizer | Hourly: classify group messages ALERT / DIGEST / ROUTINE; alerts within budget; a digest section at 07:30. |
| Property tracker | New Yad2 / Madlan listings land silently in the Sheet + a digest section (§12.1). |
| Dashboard (PWA) | Today-first read view + write-back (done / snooze / note) with offline queue and a tombstone race guard. |
| Delivery | Self-hosted Baileys bridge: 1:1 messages to the two adults only, via a durable outbox. |

### Building now

**Finance ingestion (M6, §12.2).** Read-only scrape of the bank + cards → categorized transactions + balances in the Sheet → silent surfacing in the briefing and dashboard. The repo half is built; first live run is pending the appliance step. See `BACKLOG.md`.

### Non-goals (permanent)

Money movement · credential storage *(except appliance-local, read-only financial portal logins)* · messaging anyone beyond the two adults · posting into any group · kid-facing surfaces · medical advice (scheduling only).

### Frozen (out of scope until a stated condition is met)

Pediatric milestones, goal coaching, PDF/OCR/voice capture, Gmail bill parsing, Maccabi forwarders, WhatsApp reply parsing. Each unfreeze condition is in `BACKLOG.md`; frozen code lives in `attic/`, unmaintained. Anomaly/subscription detection is **killed** (not frozen) — the false-positive cost isn't worth it. A keyword categorizer, also once killed, returns in a bounded form only as the on-box finance rules engine (§12.2).

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
│   07:25 reminders engine (compute)          │   │  read: batchGet          │
│   07:30 daily digest (assemble + send)      │   │  write: batchUpdate +    │
│   hourly whatsapp summarizer                │   │   DoneAt / LastDoneBy /  │
│   ~06:00 finance scrape (building)          │   │   WriteQueue_Tombstone   │
│   2×/day property scrape                    │   └──────────────────────────┘
│   Sat 21:00 weekly briefing                 │
│                                             │         ┌──────────────────┐
│  Baileys bridge (Node, systemd service):    │ WhatsApp│ Adar + Shanee    │
│   reads groups → inbox.jsonl                │────────▶│ (the only        │
│   polls outbox.jsonl → sends 1:1            │         │  recipients)     │
│   recipients.json = hard scope guard        │         └──────────────────┘
│                                             │
│  lib/outbox.py = THE chokepoint:            │
│   budget ledger, dedup, kinds, quiet hours  │
└─────────────────────────────────────────────┘
```

Key properties:

- **One write path to phones.** Every script that wants to reach a human appends to the outbox via `lib/outbox.py`. Budget, dedup, quiet hours, and scope live there once.
- **One data plane.** All Python uses gspread with a service account; the dashboard uses gapi with each adult's own OAuth. The local `Family_OS.xlsx` is a seed template only — nothing reads it at runtime. *(A split between openpyxl reads and a gapi dashboard would be two diverging sources of truth.)*
- **One machine.** Bridge and automation share the VPS. Its failure mode is total and therefore obvious (heartbeat goes stale → the next successful briefing says so; if >24h, the email fallback fires). *(The bridge needs to be always-on anyway, so a second runtime would only add a failure domain.)*
- **LLM calls are decoration, not structure.** Every LLM-dependent step has a deterministic fallback (templated briefing, keyword classification). The system delivers value with the API key revoked.

## 6. Data model — the `Family_OS` Google Sheet

Authoritative tab list. The three tabs with code contracts get column-level schemas below; the rest are human-edited and read loosely (missing columns tolerated, rows with unparseable dates surfaced as data-hygiene lines, never crashing a run). All schema changes are **additive-only** — old rows must keep parsing.

### 6.1 `Reminders` (keystone)

| Col | Field | Written by | Notes |
|---|---|---|---|
| A | Title | humans | used verbatim in messages |
| B | Domain | humans | Car / Health / Education / Finance / Contracts / Goals / Other |
| C | Owner | humans | Adar / Shanee / Both |
| D | Due Date | humans, engine (recurrence bump) | DD/MM/YYYY |
| E | Lead Times | humans | CSV of day offsets, e.g. `60,30,7,1` |
| F | Recurrence | humans | One-off / Yearly / Monthly / Quarterly / Weekly / Custom |
| G | Status | engine, dashboard | Pending / Snoozed / Sent / Done / Skipped / Overdue |
| H | Last Sent | engine | ISO datetime of the last fire for this row |
| I | Channel | humans | WhatsApp / Email / None |
| J | Notes | humans, dashboard (append) | appended to a message if ≤120 chars |
| K | Days Until | sheet formula | `=D−TODAY()` |
| L | Auto-flag | sheet formula | OVERDUE / FIRE TODAY / WEEK OUT / MONTH OUT |
| M | LastDoneBy | dashboard | display name from `Settings.UserMap` |
| N | DoneAt | dashboard | ISO datetime; feeds the 7-day arc |
| O | WriteQueue_Tombstone | dashboard | ISO datetime stamped on **every** dashboard write; the engine skips rows tombstoned <6h (§8.3) |
| P | Guide URL | humans | optional how-to / Kol-Zchut link, appended to messages |

**Dashboard write contract:** every write-back is one `batchUpdate` touching its intent columns **plus M, N (when completing), and always O.** A dashboard that doesn't stamp O is non-conformant.

### 6.2 `WhatsApp_Inbox` (hot, 30-day rolloff) + `WhatsApp_Archive` (text-only, forever)

`WhatsApp_Inbox` columns: msg_id, group_name, group_type, sender_name, sender_role, received_at, text, has_media, classification, one_liner, action_required, action_owner, critical, dispatched, dispatched_at, digested_at. After each successful append, rows older than 30 days roll off (the Archive never rolls). `WhatsApp_Archive` keeps msg_id / group / sender / received_at / text / one_liner only. **Media is never stored** — only the fact that it existed. The `critical` / `dispatched` fields are the outbox *outcome* record; budget enforcement itself lives only in the outbox ledger.

### 6.3 `WhatsApp_Group_Config`

group_name · group_type · importance_default (alert_eligible / digest_only / mute) · alert_recipients (both / adar / shanee / none) · close_contacts · alert_keywords (regex `;`-list) · critical_keywords (regex `;`-list, budget-bypassing).

### 6.4 Other tabs

`People`, `Calendar-Events`, `Finance-Budget`, `Finance-Accounts`, `Finance-Transactions` (finance landing zone — schema in §12.2), `Goals`, `Health`, `Education`, `Car`, `Contracts`, `Contacts`, `Settings` (Key|Value rows — keys containing `@` are UserMap entries email→display-name; key `lang` is the chrome default), `Reminders-Archive` (one-offs roll here monthly), `Property-Listings` (scraper-written — schema in §12.1). Money values are **ILS only**.

## 7. Component contracts

### 7.1 Reminders engine — daily 07:25 (computes, does not send)

```
validate the header row against the §6.1 column map; on mismatch: abort the run,
  log schema_drift, surface it in the next briefing. (Guards the dual write-path:
  dashboard and engine must agree on columns before anything fires; write-backs
  validate BEFORE the batch is issued, so a drifted sheet is never written by
  position.)
read Reminders where Status ∉ {Done, Skipped}.  (NOT "∈ {Pending, Snoozed,
  Overdue}": a 60,30,7,1 lead-time chain would die at its first Sent stamp.
  Same-day re-fires are blocked by the Last-Sent guard instead.)
  skip if WriteQueue_Tombstone is within 6h      → log skipped_due_to_tombstone + age
  fire if days_until < 0 AND last sent ≥3d ago   → OVERDUE
       or days_until ∈ Lead Times                → LEAD-TIME
       or days_until == 0                         → DUE TODAY
hand fires to the 07:30 daily digest (§7.2).
on send success (in the digest): Last Sent = now; Status = Sent | Overdue.
recurrence on Done: bump Due Date by the period, Status → Pending, Last Sent
  cleared; Feb-29-class dates clamp to the last day of the target month + a
  review flag; Custom is flagged, never guessed.
heartbeat: append one line to logs/reminders_log.csv every run.
```

### 7.2 Daily digest (07:30) + weekly briefing (Sat 21:00)

**Daily digest:** one short message assembled from engine fires + the WhatsApp digest section + new-property listings + a Hebcal line (Fridays / erev chag), queued as `kind=briefing`. **One morning message, not several** — assembly happens before queuing. On send success the digest stamps each fired row's Last Sent / Status per §7.1.

**Both adults, every day.** The digest is assembled and queued for adar **and** shanee on every run. An adult with no fires of their own still gets the briefing — the quiet-day line plus the shared sections (WhatsApp groups, property). This keeps the surface partner-symmetric and means silence always signals a *broken* digest, never an empty day. Because it is `kind=briefing` it is budget-exempt, so briefing the empty-handed adult never spends an alert slot.

**Weekly briefing:** read all tabs → render a five-scene narrative (the week's spend · a kids' moment · next week's three things · one goal line · one contract heads-up) from a **deterministic template** → write to `Briefings/` and queue `kind=briefing`. It also carries a compact **Classifier accuracy** section — the week's WhatsApp ALERT-tier counts, by-rule tally, and the <1/week false-positive target — and the standard self-report line (runs green, messages classified, tombstone skips, LLM spend). *(The briefing is template-only by design. An LLM-written version would have to send whole-Sheet context — reminders, finance, kids' health — to the model, far beyond the "one message + ≤3 context" bound the classifier observes. AI prose is a deferred v1.1 candidate, not a gap.)*

Both message kinds are budget-exempt and subject only to quiet hours.

### 7.3 WhatsApp summarizer — hourly

Reads new inbox lines → classifies: **hard rules first** — a critical/safety keyword is a budget-exempt ALERT that **pierces even a muted group**; below that tier a **muted group raises nothing** (mute is itself a hard rule); otherwise, for non-muted groups, alert-keyword / teacher-evening / vaad-utilities → ALERT and media-only → ROUTINE — then the LLM (the configured provider) for the rest with up to 3 messages of group context, then a deterministic keyword fallback when no key is present → writes Inbox + Archive rows → ALERT rows route per group config → `outbox(kind=alert)`, or `kind=critical` on a critical-keyword match. A digest-only group with a critical match raises a "⚠ NEEDS A LOOK" block at the top of the next digest. Family-group criticals do **not** override digest-only routing (critical_keywords already bypass per group). *(Mute is the one knob that silences ordinary alerts entirely; a true safety keyword is the deliberate exception — PO call 2026-06-18.)*

A weekly accuracy pass (`automation/accuracy_review.py`) re-reads the week's Inbox rows and re-derives each ALERT's triggering rule by reusing the live `hard_rule_alert` function — so the review can't drift from the classifier, and needs no schema change. It surfaces ALERT-tier false positives against the **<1/week** bar, folds a compact pulse into the weekly briefing, and writes a full operator report to `Briefings/`. The "fix" for a false positive is narrowing the offending keyword pattern.

### 7.4 Bridge — Baileys, Node, systemd service

Listens to **groups** → `inbox.jsonl`. Polls `outbox.jsonl` every 15s → sends **1:1 only** to JIDs present in `recipients.json` (machine-local, gitignored); any other target is refused and logged. Per-(id, target) dedup against a sent ledger. Heartbeat file on connect / message / 15-min idle. Never posts to groups. Inbound 1:1 chats from the two known senders (`recipients.json` JIDs) are **silently logged** to `replies.jsonl` as raw material for the v1.1 reply-parsing feature — the bridge does **not** act on them and **never acks** (no affordance it can't honor — §3.7); every other 1:1 sender is dropped. *(LID-addressed 1:1s fall through the known-sender guard and are dropped until v1.1. Self-hosted Baileys, not a paid API: ₪0 marginal, no business-API verification or template approval, free-form Hebrew. Pinned to Baileys 7.x on ESM — the pre-7 line broke companion self-sends after WhatsApp's LID identity migration.)*

### 7.5 Outbox (`lib/outbox.py`) — the chokepoint

```
queue(to: "adar"|"shanee"|"both", body, kind: "alert"|"critical"|"briefing", source, id)
  briefing → exempt from budget; subject to quiet hours (22:00–07:00 → hold to 07:00)
  alert    → consult ledger[date][recipient]; if ≥2 → defer: append to tomorrow's
             digest, log alert_suppressed_by_budget; else send + increment
  critical → send immediately, any hour, log budget_bypassed_critical
  all      → idempotent by (id, target); ledger + queue are durable JSONL on disk
```

The ledger is shared across **all** senders — the engine and the summarizer can't each spend a separate 2/day. *(The daily digest is `kind=briefing`, not `alert`: as an alert it consumed a budget slot and, worse, an over-budget alert defers *into* the next digest — which is itself the message, a circular dependency.)*

### 7.6 Dashboard (PWA)

Read: `batchGet` over all bound ranges (UI contract in `DESIGN.md`). Write: per the §6.1 write contract — optimistic UI, an offline queue in `localStorage.pendingWrites[]` (cap 50), flushed on reconnect in tap order, failed flushes retried on the next online event. Identity: Google sign-in → `Settings.UserMap` → display name. Demo mode renders `mock_data.json` and never calls gapi.

## 8. Cross-cutting policies

### 8.1 Alert budget

2 unsolicited messages / recipient / day, enforced only in `lib/outbox.py`. When over budget, trim priority: OVERDUE and kids' Health always survive; WEEK/MONTH-OUT bump first; Goals never alert (briefing-only). If >10% of fires are suppressed over a rolling 14 days, the next weekly briefing says "budget is biting — raise the cap or tighten the rules?".

### 8.2 Quiet hours

22:00–07:00 Asia/Jerusalem. Alerts and briefings hold; criticals do not.

### 8.3 Offline write / engine race (tombstone)

The dashboard stamps `WriteQueue_Tombstone` (ISO-T datetime) on every write; queued offline writes re-stamp it **at flush time**, so the cell always carries the moment the write *landed* on the Sheet. The engine skips a row while `tombstone + 6h > now()` (one clock: the window starts at flush, not at the tap). *(Date-only tombstones had silently disabled this guard — the hour resolution is load-bearing.)* Residual accepted race: a phone that flushes a queued tap inside the same minute the engine reads → at most one duplicate alert; the flush itself is idempotent. Every skip is logged with the tombstone age, and the weekly briefing reports "N tombstone skips · max age seen" — widen the window from data, not anecdote. **Background-timer races (accepted):** the Sheet-writing timers are deliberately staggered — finance 06:00, reminders 07:25, digest 07:30, property on its own slot — so they don't run concurrently, and each writes a disjoint tab/column set (finance → `Finance-*`; engine + digest → `Reminders`; property → `Property-Listings`); `gspread` batch updates are atomic per call. v1 attempts no cross-timer transaction: the residual is a run that overran into the next timer's window, at most a stale read that self-heals next run.

### 8.4 Idempotency & dedup

Outbox messages carry stable ids: engine `rem-{row}-{date}`, summarizer `wa-{msg_id}`, briefings `brief-{type}-{date}`. The bridge dedups per (id, target). Engine re-runs on the same day are no-ops (the Last-Sent guard).

### 8.5 Time & locale

All schedules in Asia/Jerusalem (DST-correct via system TZ, never UTC offsets). Dates DD/MM/YYYY; week starts Sunday; money `Intl.NumberFormat('he-IL', ILS)` / `₪{n:,}` in Python. Chrome strings are Hebrew-default with an English fallback; data values stay Hebrew always. Machine-written datetime stamps (Last Sent, DoneAt, WriteQueue_Tombstone) are ISO-8601 `T`-form **text** on both surfaces — the `T` stops Sheets from coercing them into locale date cells, so they round-trip byte-exact and keep the hour resolution the 6h tombstone window needs.

### 8.6 Privacy & security

- WhatsApp plaintext exists in places we don't fully control — Meta's servers (inherent) and the configured LLM provider — plus the VPS we do. Exactly **one** LLM provider is configured at a time (DeepSeek by default — §8.7), and **every provider is treated identically**: the privacy guarantee is not *which* vendor may see the text but *how little it ever sees* — LLM classification sends one message + up to 3 context messages, never whole threads or cross-group context, whichever provider is active. Switching providers is an operator key-swap, not a policy change. *(DeepSeek is the default on cost; it routes group plaintext through PRC-jurisdiction infra — a deliberate privacy-vs-jurisdiction call by the POs, accepted because volume is negligible, every path has a keyless fallback, and the operator may swap providers at will.)*
- **Finance categorization:** the configured LLM provider may assign a category to the **rules-miss remainder only** — a transaction's **description + amount**, never account numbers, balances, credentials, identifiers, or the whole ledger. The on-box rules engine tags first, so most transactions never leave the box.
- Secrets — `recipients.json`, the service-account JSON, `FAMILY_INC_DEEPSEEK_API_KEY`, `FAMILY_INC_APIFY_TOKEN` (property secondary source), `bank_creds.json` (read-only finance logins), SMTP password — live in `/etc/family-inc/`, mode 600, never in the repo.
- Phone numbers / JIDs appear nowhere except `recipients.json` on the VPS.
- The service account has access to exactly one spreadsheet, nothing else in Drive.
- Known accepted risk: Baileys is an unofficial client — some account-ban risk, elevated on datacenter IPs. Mitigations: household volume (≤10 msg/day), a person-to-person pattern, a dedicated paired session. Fallback chain in §10.

### 8.7 LLM usage

One wrapper (`lib/llm.py`); model ids in config, not at call sites; per-call cost logged to `logs/llm_costs.csv`. The active provider is chosen by **key presence**: `FAMILY_INC_DEEPSEEK_API_KEY` → DeepSeek (`deepseek-chat`, via its OpenAI-compatible endpoint over stdlib urllib — no SDK); else `ANTHROPIC_API_KEY` → a Haiku-class provider, **treated identically** (the minimal-payload rule in §8.6 is provider-independent); else the deterministic fallback (keyword classification, template briefing). Classification requests strict JSON mode and tolerates trailing prose in the reply. The weekly briefing makes no LLM call. The weekly self-report line (ENGINEERING §8) carries the week's LLM spend; the first briefing of each month reports month-to-date.

## 9. Failure modes

| Failure | Detection | Behavior |
|---|---|---|
| VPS down | heartbeat stale (external check optional, v1.1) | total outage; on recovery the outbox flushes; missed runs reported in the next briefing |
| Bridge logged out / WA break | heartbeat stale >12h | digest prepends "⚠ BRIDGE SILENT Nh"; >24h → email-fallback digest to both adults |
| WhatsApp account banned | send failures + logout | switch to email digests same-day (one-line config); decide the §10 path |
| Sheet API 5xx / quota | gspread retries with backoff, then skips the run | "missed yesterday" line in the next successful run |
| LLM API down / keyless | exception → fallback path | templated briefing / keyword classification; logged, not alerted |
| Bad row data (unparseable date) | per-row try/except | row skipped + listed under "data hygiene" in the weekly briefing |
| Sheet header drift | engine header validation, every run | run aborts before firing anything; schema_drift logged + surfaced |
| Outbox/inbox JSONL torn line | reader skips the malformed tail | self-heals next poll (single-writer appends) |
| Clock skew / future tombstone | tombstone > now | treated as valid for the full window, anomaly logged |
| Both adults edit the same row | last-writer-wins | acceptable at household scale, by decision |

## 10. Fallback chain (delivery)

1. **Baileys bridge** (primary).
2. **Email digest** to both adults — automatic and mechanical: the daily-digest task checks the bridge heartbeat before queuing; if stale >24h it sends the identical rendered content via SMTP and notes "delivered by email — bridge down Nh". No watcher process; the sender itself degrades. Every send-run logs its transport to `logs/delivery_log.csv`; **email-fallback days are degraded, not green** — the weekly briefing surfaces them, so a dying bridge can't hide behind a working fallback.
3. **Twilio WhatsApp** — documented fallback, not in code. Adopt only if Baileys proves unworkable (recurring bans); accepts template-approval constraints.
4. **Inforu SMS** — deep fallback, Hebrew-capable, ILS billing; revisit only after 2+ failures above.

## 11. Acceptance (v1 — met)

v1 went live and was accepted on 2026-06-15 (tagged `v1-live`): the 07:30 WhatsApp digest reached both phones three consecutive days with no intervention; a reminder completed a full done→recurrence cycle; an alert-keyword group message reached the right recipients while a family-group meme reached no one; a critical keyword fired after the daily budget was spent; an offline dashboard write flushed on reconnect with the engine logging a tombstone skip and no duplicate; the weekly briefing arrived with its Hebcal and budget sections and the LLM-down fallback was verified; logs showed seven green days; monthly cost confirmed ≤ ₪120. New features inherit the same bar: live, observed green on the appliance, with a deterministic fallback proven.

## 12. Data ingestion lanes

Specs for ingestion lanes that are unfrozen. All ingestion obeys the same rules: one runtime (the VPS), `lib/sheet` is the only Sheet writer, no new path bypasses `lib/outbox.py`, secrets only in `/etc/family-inc/`.

### 12.1 Property listings — Yad2 / Madlan (live)

Active house search. New listings land silently and surface in the morning digest.

| Facet | Spec |
|---|---|
| **Source** | Saved-search result pages on Yad2 (primary) and Madlan. One or more saved-search URLs per portal in `/etc/family-inc/property_searches.json` (personal criteria, gitignored). No public API: the **primary** path scrapes; a permitted **secondary** source (Apify) backs it up when the scrape is blocked and fills missing fields. |
| **Mechanism** | Headless Chromium on the VPS (run headed under Xvfb with light stealth, because a plain headless browser from a datacenter IP is challenged). A scraper loads each saved-search URL, extracts listing cards (`listing_id`, price, rooms, size, location, url, posted-at), and diffs the `listing_id` set against `/var/lib/family-inc/property/seen.json`. New ids = new listings. |
| **Secondary source (Apify)** | `automation/lib/apify.py` is the only Apify client. It is consulted **per saved-search only** when the primary is blocked/empty (backup) or returned listings with missing fields (gap-fill), then merged with the **primary always winning** — Apify only adds missed listings and fills blanks, never overwrites. Actors: `amit123~yadscraper` (Yad2, ingests the saved-search URL) and `swerve~madlan-scraper` (Madlan, parametric — needs a `{city,dealType,…}` `apify` block; params are never guessed from the URL). Strict and fail-loud: a junk item (missing id, corrupt number) is skipped; an item error is fatal **only** when a call returned items but **none** were usable; a missing token / HTTP error / timeout is a loud `ApifyError`. Apify runs from a residential proxy pool, clearing the anti-bot wall the datacenter IP cannot. Priced per result, so it runs at most **once/calendar-day per search per kind**, under the §11 ≤₪120/mo ceiling; absent the token, the whole path is inert (primary-only). |
| **Runtime** | One systemd timer (`family-property.timer`), 1–2×/day (not real-time — listings don't churn by the minute and tighter polling raises ban risk). `TimeoutStartSec` + `MemoryMax` bound a stuck browser; independent of the bridge. |
| **Sheet landing zone** | `Property-Listings`: `listing_id` (dedup key) · `portal` · `first_seen` (ISO-T) · `price_ils` · `rooms` · `size_sqm` · `location` · `url` · `status` (human-edited: new/seen/contacted/dismissed). Append-only via `lib/sheet`; a listing that drops out of results is left in place. |
| **Delivery** | New listings land **silently** and surface in a "🏠 דירות חדשות / New listings" section of the 07:30 digest. They never alert and never bypass the budget — property is not critical-safety. |
| **Failure handling** | A scrape error or anti-bot block sets the fail-flag (`OnFailure` → `logs/fail.flag`); the next digest reports "property scrape failed" and the weekly briefing surfaces persistent failures. The realized escape hatch from a persistent block is the Apify secondary; an anti-detect browser on-box is a further fallback. |

### 12.2 Finance — Mizrahi / Max / Cal (building, M6)

A committed monthly finance review is the standing consumer. Scope = Mizrahi (bank) + Max + Cal (cards); **categorized + month-over-month trends**; investments/brokerage out of scope. Anomaly detection stays killed. Delivery is silent. The repo half is built and tested; the live appliance run is pending (`BACKLOG.md` M6).

| Facet | Spec |
|---|---|
| **Source** | The online portals of Mizrahi-Tefahot + Max + Cal, read via `israeli-bank-scrapers` (Puppeteer/headless-Linux, pinned 6.7.3, Node ≥ 22.13 — the library's own `engines` floor). No public API; the library drives each portal's web session. **Read-only by nature** — it fetches balances + transactions and cannot move money. |
| **Mechanism** | A systemd timer runs `automation/finance/scrape.js`: logs into each provider with creds from `/etc/family-inc/bank_creds.json`, fetches balances + a **fixed ~45-day** transaction window (`FAMILY_INC_FINANCE_WINDOW_DAYS`; `Txn-ID` dedup makes overlapping reruns idempotent, so a fixed window is simpler and correct — no since-last-success state to keep), writes one CSV per provider to `/var/lib/family-inc/finance/`. `automation/finance_ingest.py` then normalizes, dedups on `Txn-ID`, and writes via `lib/sheet`. Node scrapes; **Python owns every Sheet write.** The local CSV is the only staging — no Drive. Same-day reruns overwrite the day's CSV and dedup on ingest → idempotent; the import advance gates on a successful Sheet write. **Categorization:** an on-box keyword→category rules engine tags each transaction at ingest; the configured LLM provider assigns categories the rules miss (description + amount on the rules-miss remainder only — §8.6). |
| **Runtime** | One systemd timer (`family-finance.timer`), **~06:00 daily** — ahead of the 07:25/07:30 morning runs so balances are fresh for the M6.3 finance consumers (the weekly briefing Money section + dashboard drawer + the >35d stale-import line). Headless Puppeteer (no Xvfb — the anti-bot is clean for this mix). Cadence is the first tuning knob: if Max/Cal OTP challenges prove noisy, drop the cards to 2–3×/week and keep the bank daily. |
| **Auth model** | Read-only portal logins live at `/etc/family-inc/bank_creds.json` (mode 600, never in the repo, never logged). This is the one place the "no credential storage" non-goal is narrowed — *appliance-local, read-only financial logins* — while "no money movement" stays absolute (the scrapers cannot transfer). **2FA:** the scraper logs in fresh each run; an OTP re-challenge **fails loud** (next digest), and the operator re-runs the scraper unit once the challenge clears (the scraper is headless — there is no interactive OTP prompt; a same-window rerun is idempotent via `Txn-ID` dedup). Persisting a login session to cut repeat OTPs is a later hardening, taken only if the cards prove noisy. |
| **Sheet landing zone** | Two tabs via `lib/sheet`. **`Finance-Accounts`** — one row per account/card, current-state (upserted on `Account Name`): `Account Name` · `Type` · `Bank/Provider` · `Last 4` · `Owner` · `Currency` · `Last Imported` (drives the >35d stale-import warning) · `Balance Snapshot` · `Notes`. The importer overwrites only the machine-owned columns, so a human's `Owner`/`Notes` survive a re-import. **`Finance-Transactions`** — one row per transaction, append-only, `Txn-ID` dedup: `Date` · `Account` · `Description` · `Amount (ILS)` (signed) · `Category` · `Cat-Source` (rule/llm) · `Txn-ID` · `Imported-At`. **Column order is load-bearing** — the `Finance-Budget` actuals `SUMIFS` over Date (A) / Amount (D) / Category (E). The date criteria are a **text-prefix wildcard** on the ISO-text `Date` (`<yyyy-mm>&"*"` for the month, `<yyyy>&"*"` for YTD, plus a `Last Month (ILS)` column for month-over-month): a serial `DATE()` window read ₪0 against the RAW-appended text dates, and keeping the append RAW leaves `Txn-ID` dedup intact — so text-prefix is chosen over a `USER_ENTERED` append, which would coerce `Txn-ID`/`Account` (M6.4). M6.3 applies the same formulas to the live `Finance-Budget` tab and verifies actuals go non-zero on the first real month. Retention: keep all (low volume; the monthly review wants history). |
| **Delivery** | Finance lands **silently**: balances, per-category spend, month-over-month trends, and actuals-vs-`Finance-Budget` surface in the weekly briefing **Money** section + the dashboard **Money** drawer, alongside the >35d stale-import line — **never an alert, never a budget bypass.** The only finance *message* is fail-loud. A ">₪500 single charge" alert is deliberately not wired (it's an alert path that brushes the killed anomaly lane — deferred to a deliberate PO call). |
| **Failure handling** | An OTP re-challenge, a site-change error, or a Sheet-write failure sets the fail-flag; the next digest reports it ("⚠ <provider> צריך אימות מחדש" / "finance scrape failed") and the weekly briefing surfaces persistent failures + the >35d stale line. CSVs are retained on a Sheet-write failure (no data loss; retry next run). If a Cloudflare wall ever appears, the escape hatch is the maintained anti-detect fork on-box, then a managed-proxy pivot. A box compromise leaks read-only visibility only — no transfer capability. |

## 13. References

`ENGINEERING.md` — runtime, repo layout, testing, ops. `DESIGN.md` — dashboard UI, message design system, i18n. `BACKLOG.md` — what's next and what's frozen. `Archive/` — the dated decision history and superseded docs.

=== End: SPEC.md ===

=== File: BACKLOG.md ===
# Backlog

*The only live status record. What's shipped, what's in flight, what's parked, what's frozen.*
*Legend: ✅ done · 🔵 in progress · ⬜ todo · 🧊 frozen. Scope and acceptance live in `SPEC.md`. The dated history of how each item landed lives in `Archive/`.*

## Now

**v1 is live and accepted** (since 2026-06-13, tagged `v1-live`): the morning WhatsApp digest, the weekly briefing, the dashboard write-back loop, and the group summarizer all run unattended on the appliance. The **property tracker** is live (Yad2 on-box + Madlan via Apify). The summarizer runs on **DeepSeek**. **Finance ingestion (M6)** is the current build — the repo half is done; the appliance step is next. Two summarizer-review items are **gated** until ~2026-06-20 (they need a week of live classifier output to judge).

**✅ Audit fix lane — Brief 1 (blocker + 7 majors), landed 2026-06-18** (from the 2026-06-18 full-project audit in `reviews/`): bridge 1:1 chats are now **log-only, no ack** (B1, SPEC §7.4); the candle-lighting line fires on **erev-chag** too (B2); **criticals pierce mute** while non-critical rules are suppressed in muted groups, closing the budget-bypass (B3, SPEC §7.3); LLM privacy reconciled **provider-agnostic** (B4, SPEC §8.6/§8.7); finance gap-fill **chunk-loops** so a large first import is fully categorized (B5, M6); `deploy.sh` installs the **finance Node deps** + restores `--frozen` (B7, M6 — unblocks M6.2); the weekly briefing carries the **ENGINEERING §8 self-report line** (B6); the dashboard offline queue **caps at 50 with a one-shot warning** (B8). Tests green (350). **Brief 2** (10 gaps + minors + disputed) remains open. The fix touched privacy/delivery/budget → the `review.py` gate **ran 2026-06-18** (DeepSeek; `reviews/review_milestone_2026-06-18_16-41.md`): B1/B4/B5/B7/B8 affirmed; one false-positive defended (the mute short-circuit already follows the critical check), `chag_candles` window widened to +5d (Applied), and the dashboard-recurrence-bump finding routed to **Brief 2 GAP-4** (Open — pre-existing, out of lane).

**🔵 Brief 2 (small fixes) — Lane A + Lane E canon-hygiene landed 2026-06-18.** Lane A (finance hardening, M6-critical): GAP-1 `Dining`→`Dining out` aligned + a guard test pinning `rules.vocab ⊆ budget` (Fees/Income/Shopping held as a tracked allow-list **pending Shanee's budget-vocab migration** — the authority); finance-ingest#3 distinct in-batch-dup counter; OTP "interactive" promise scrubbed to truth (decision #1); fixed 45-day window doc'd (decision #2); Node pin bumped to ≥22.13 (the lib's real floor); GAP-6 `data_only` caveat + tests-quality#3 comment; seeds/README documents the committed rules CSV. Lane E hygiene: `Haiku`→DeepSeek docstring, ENGINEERING boundary-rules wording, 7-timers, finance-timer/SPEC consumer wording, D-NN sweep, BACKLOG Hebcal-line correction, `FINANCE_PLAN.md`→`Archive/`.

**✅ Lane S (publish/privacy safety) — landed 2026-06-18.** Audited all 18 tabs of the committed `Family_OS.xlsx`: **confirmed synthetic by construction** — no real emails (all `example.com`), phones, Teudat-Zehut (`000000000`), JIDs, or account numbers; the only real identifiers are the principals' first names `Adar`/`Shanee`, which are **accepted-public by design** (owner-routing tokens `OWNER_TO_RECIPIENTS`, Settings UserMap, CLAUDE.md roles, git author) — so GAP-5's feared real-PII leak was unfounded. Added **`tests/test_seed_safety.py`** (the dedicated check — fails CI if any high-severity PII is ever pasted into the seed) and documented in `publish_paths.txt` why the binary seed is kept-at-HEAD-and-guarded rather than history-stripped. deploy-systemd#4: `publish.sh` gauntlet now verifies `regex:` redaction rules (PCRE) instead of silently skipping them. Tests 355→357. **Review gate ran** (DeepSeek; `reviews/review_spec_2026-06-18_19-02.md`): core decisions affirmed; Applied — seed-safety test hardened (config sanity-check so it can't pass vacuously + Unicode-domain email detection) and `publish.sh` no-PCRE failure made actionable; Defended the O(N·M) re-grep + the "rewrite gauntlet in Python" alternative (fail-loud suffices); a full seed-recovery script left as a deferred nicety (the test already fails loud + names the recovery command).

**🔵 Lane B (robustness seams) — partial, 2026-06-18.** Landed the bounded outbox-integrity cluster: **outbox-budget#1** — the budget ledger now writes atomically (tmp+replace) and reads **fail-CLOSED** (a corrupt ledger reads as cap-reached → alerts defer, never flood; loud for the operator); **outbox-budget#2** — an `fcntl` lock around the ledger read-modify-write so concurrent senders can't double-spend the 2/day cap; **GAP-10** — the bridge's `processOutbox` got per-row try/catch (one failed `sendMessage` no longer abandons the rest of the batch; transient failures retry, only terminal sent/refused suppress); **GAP-8** — the multi-timer Sheet race documented as accepted (SPEC §8.3). Tests 357→358. **GAP-2 (stamp-after-deliver — the [high] silent-loss path) + outbox-budget#3 (pop-deferred-after-confirm) DEFERRED to a focused pass**: it changes the delivery contract (when "Sent" is written) and a bounded in-run wait risks duplicate digests if bridge latency ever exceeds the window — the correct design is a **cross-run reconcile** (stamp whenever the bridge eventually confirms via `whatsapp_sent.jsonl`), which deserves careful tests + the review gate, not a rushed tail-of-session change. Also deferred in Lane B: GAP-3 (JSONL rotation), bridge-node#2 (bridge scope-guard test harness).

**Deferred** (next sessions): **Lane B remainder** (GAP-2 + budget#3 cross-run reconcile, GAP-3, bridge-node#2 — review-triggering), Lane C (dashboard), and Lane E's code-correctness + test-gap items (digest >30d flag, derive_rule, property-apify, OVERDUE-overflow test, reply_handler stub flags, the deferred "budget is biting" line — decision #3).

## Shipped

- **Keystone loop** — reminders engine (07:25) → daily digest (07:30) → WhatsApp, with dashboard write-back, the outbox budget chokepoint, quiet hours, and the offline-write tombstone guard.
- **Weekly briefing** (Sat 21:00) — deterministic template, the system self-report, and a classifier-accuracy section. *(The candle-lighting Hebcal line is the daily digest's, not the weekly briefing's.)*
- **WhatsApp summarizer** — 5 hard rules + DeepSeek (with keyless keyword fallback), per-group routing, critical-keyword bypass.
- **Daily digest is partner-symmetric** — both adults briefed every day; the empty-handed adult gets the quiet-day line + shared sections, budget-free.
- **Property tracker** — saved-search scrape (headed Chromium under Xvfb) + Apify secondary (backup + gap-fill, primary always wins), silent `Property-Listings` landing + morning digest section.
- **Delivery hardening** — email (SMTP) fallback when the bridge is silent >24h, fail-flag → next-digest reporting, transport logging; email days count as degraded, not green.
- **Go-live + publication** — VPS provisioned, Baileys paired (7.x/ESM), GitHub Pages + PWA pinned to both phones, repo history rewritten clean and made public.
- **Classifier-accuracy surface** — `accuracy_review.py` re-derives each ALERT's rule from persisted Inbox fields (no schema change); a compact pulse folds into the weekly briefing.

## In progress — M6 finance ingestion

Banks + cards, categorized + trends, delivered silently. Read-only logins permitted on the appliance; "no money movement" unchanged. Full contract: `SPEC.md` §12.2.

- ✅ **M6.1 — repo port + schema (hermetic, no appliance).** `automation/finance/scrape.js` (read-only login → CSV) + `finance_ingest.py` (CSV → normalize → Txn-ID dedup → `lib/sheet`: append `Finance-Transactions`, upsert `Finance-Accounts`). Finance tabs standardized to `Finance-Budget`/`Finance-Accounts`/`Finance-Transactions`; `Category`/`Cat-Source` ship present-but-blank (the budget `SUMIFS` keys on the Category column position). `family-finance.{service,timer}` + provision wiring. Tests green; no live bank contact.
- ⬜ **M6.2 — appliance deploy + first live auth (the "VPS hour").** Place `bank_creds.json` (mode 600); rename the 3 live-Sheet tabs to the full names; Mizrahi first → verify CSV→Sheet roundtrip live → Max + Cal (OTP once each — the headless scraper has no interactive prompt; the operator re-runs the unit once the challenge clears); enable the timer. **Runbook: `deploy/FINANCE.md`.**
- ⬜ **M6.3 — consumer wiring + close.** Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning fires. Acceptance = the first real monthly review (~30 days in).
- 🔵 **M6.4 — analysis layer.** *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates `Category`/`Cat-Source` at ingest; DeepSeek gap-fills the rules-miss remainder (description + amount only, §8.6). The briefing Money section gained per-category spend + month-over-month (the dashboard drawer reads the same tab — M6.3). **Reconciliation (the build-note landmine, resolved):** budget actuals now `SUMIFS` with a **text-prefix wildcard** on the ISO-text Date (`<yyyy-mm>&"*"`), not a serial `DATE()` window that read ₪0 — chosen over `USER_ENTERED` (which would coerce `Txn-ID`/`Account` and break dedup); the append stays RAW. Seed formulas updated + a regression test pins the form. **Gated to M6.3 (live):** apply the same formulas to the live `Finance-Budget` tab and verify actuals go non-zero on the first real month. **PROVISIONAL** category vocab until Shanee's budget migration firms it up. Silent delivery; no anomaly detection.
- ⬜ **Parallel (Shanee).** Budget migration — her manual budget → `Finance-Budget`; gives the actuals a target and defines the category vocab the rules engine maps to.

## Gated — summarizer review (opens ~2026-06-20, needs ≥1 week live)

- ⬜ **First real classifier-accuracy run + false-positive cleanup** — run `accuracy_review.py` over a full week of live DeepSeek output; narrow any over-firing keyword patterns.
- ⬜ **External milestone review on the live system** — folds in the property lane's review too.

## v1.1 candidates (unordered — pick after v1 is boring)

- **Reply parsing** (done/snooze via WhatsApp) — the bridge already **logs** 1:1 replies from the two adult JIDs to `replies.jsonl` (no ack — B1); `reply_handler.py` exists (already on `queue()` with `wa-{msg_id}` ids). Remaining: consume those logged replies — port `reply_handler`'s Sheet writes to `lib/sheet`, resolve LID-addressing (`msg.key.remoteJidAlt`) so replies aren't dropped, reinstate the reply footer, and a PO call on kinds (solicited acks would otherwise consume the unsolicited budget).
- **AI-written weekly briefing** — the briefing is template-only by design; wiring LLM prose needs a privacy call (whole-Sheet context → DeepSeek) with Shanee. Pair it with a content review of the template.
- **Inbox-append trigger** for the classifier (inotify on `inbox.jsonl`) — sub-hour critical latency without changing the hourly digest cadence.
- **Machine-measured classifier FP rate** — a human-mark channel (an Inbox `review` column or a dashboard control) to replace the by-eye accuracy read.
- **Apify monthly result-counter cap** — a programmatic ≤₪120/mo backstop for the property secondary source (today bounded only by per-search/per-day calls + item caps).
- **">₪500 single charge" finance alert** — an explicit PO call; it's an alert path that brushes the killed anomaly lane, so deferred deliberately.
- **External uptime ping** (healthchecks.io dead-man) — closes the silent hard-VPS-down gap.
- Google Calendar connector → `Calendar-Events`; iCloud → GCal ICS subscribe; a Reminders `Priority` column + bulk-done; a Hebrew chrome-string completion pass.

## Frozen lanes 🧊

*Frozen = the script lives in `attic/`, unmaintained. Unfreeze = the stated condition holds AND v1 has been stable for 30 days.*

| Lane | Unfreeze condition |
|---|---|
| Pediatric milestones | the Health tab is actively maintained |
| Goal coaching | the Goals tab is updated weekly for a month (proves the habit) |
| PDF→event, receipt OCR, voice capture, Gmail bill parser, Maccabi forwarders | per-item PO request, one at a time |

**Killed** (not frozen — gone from the board): anomaly / subscription detection. A keyword categorizer, also once killed, returns only in bounded form as the on-box finance rules engine (M6.4).

=== End: BACKLOG.md ===

=== File: ENGINEERING.md ===
# Family Inc. — Engineering Handbook

*How the system is built, tested, deployed, and operated. v2.0 · 2026-06-17.*
*Contracts live in `SPEC.md`; this is the "how". If they disagree, `SPEC.md` wins and the disagreement is a bug.*

---

## 1. Repo layout

```
family-inc/
├── CLAUDE.md            # session context for Claude (thin; points here)
├── SPEC.md  ENGINEERING.md  DESIGN.md  BACKLOG.md
├── automation/
│   ├── lib/
│   │   ├── config.py    # env + constants; ALL non-secret constants live here
│   │   ├── sheet.py     # the only gspread client (retry, tab accessors, upsert)
│   │   ├── outbox.py    # the only path to a human (budget ledger, dedup, kinds)
│   │   ├── llm.py       # the only LLM wrapper (provider registry, cost log)
│   │   ├── apify.py     # the only Apify client (property secondary source)
│   │   ├── mailer.py    # the only smtplib import (email fallback)
│   │   ├── dates.py     # to_date / to_datetime / fmt_date — one implementation
│   │   └── money.py     # ILS formatting — one implementation
│   ├── reminders_engine.py
│   ├── daily_digest.py           # assembles ONE morning message, sends
│   ├── weekly_briefing.py        # Saturday narrative (template) + accuracy section
│   ├── whatsapp_summarizer.py
│   ├── accuracy_review.py        # weekly classifier accuracy pass
│   ├── property_scrape.py
│   ├── finance/scrape.js         # bank/card scraper (Node) → CSV
│   ├── finance_ingest.py         # CSV → lib/sheet
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
│   ├── deploy.sh         # pull + test + restart (the only way code reaches the box)
│   ├── backup.sh         # tar bridge/state + logs → Drive via rclone
│   └── publish.sh        # public-repo history-rewrite kit
├── tests/                # pytest; fixtures/ holds golden files
├── reviews/              # milestone-review audit trail (tracked)
├── seeds/                # CSV seeds — personal values gitignored, README committed
├── Setup/                # live runbooks only (VPS, bridge pairing, OAuth, ICS)
├── Archive/              # superseded docs + the dated decision history — read-only
├── attic/                # frozen scripts — unmaintained, excluded from tests
└── logs/ Briefings/      # runtime output (gitignored except .gitkeep)
```

Boundary rules (convention, reviewer-checked — no CI enforces them yet): scripts never define a utility that belongs in `lib/` (no redefining `to_date`/`fmt_money`). Each external-site touch is the sole, named function in its own module — the bridge listener, finance `scrape.js`, `property_scrape.py`, `lib/apify.py`, and `hebcal_client.py` — never scattered ad-hoc. Nothing outside `lib/sheet.py` constructs a gspread client. Nothing outside `lib/llm.py` imports an LLM SDK. Nothing outside `lib/outbox.py` reaches a human.

## 2. Toolchain

| Layer | Choice | Notes |
|---|---|---|
| Python | 3.12 + **uv** | `uv sync` on the box; lockfile committed; appliance path is `uv run --frozen` |
| Key deps | gspread, google-auth, anthropic, pytest, requests | additions need a one-line justification in the commit body |
| Node | 22 LTS, plain npm | bridge + finance scraper only; `npm ci`; lockfiles committed |
| Browser | headless Chromium | property (headed under Xvfb) + finance (headless); installed once by `provision.sh`, kept out of the uv lockfile |
| Scheduling | **systemd timers** | journald logs, `OnFailure=` hooks, `Persistent=true` catches missed runs after reboots |
| Dashboard hosting | GitHub Pages via Actions serving `main:/dashboard` | static, zero backend; the workflow generates the gitignored `config.js` from Actions secrets |
| Secrets | `/etc/family-inc/` mode 600 | `service-account.json`, `env` (DeepSeek/Anthropic keys, SMTP, Apify token), `recipients.json`, `property_searches.json`, `bank_creds.json` |

## 3. Configuration

- `automation/lib/config.py` loads secrets from `/etc/family-inc/env`. **All non-secret constants — alert-budget cap, tombstone window, quiet hours, digest size, lead/recurrence thresholds, inbox retention, model ids — are defined directly in `config.py`.** There is no `config.toml`.
- **No constant may be defined in a script.** This rule exists because the alert-budget cap was once defined twice with independent ledgers — exactly the class of bug it prevents.
- Dashboard config: `config.example.js` committed with placeholders; real `config.js` (Sheet ID, OAuth client id) gitignored and generated at deploy.

## 4. Coding standards

- Python: type hints on public functions; dataclasses for Sheet rows; no bare `except:` — catch narrowly, log with context, and **decide**: degrade (LLM paths) or surface (data paths). Silent swallowing is the bug class that once hid the mock/real boundary for two weeks.
- Every script is also a library: `main()` guarded, pure logic importable for tests.
- Logging: stdlib `logging` to stderr (journald captures); one structured CSV per domain in `logs/` for the self-reporting briefing lines.
- JS (dashboard): single-file vanilla discipline; state lives in the one `state` object; every Sheet write goes through `applyWrites()` and conforms to the SPEC §6.1 write contract.
- Hebrew in code: string literals fine, identifiers English. Message copy lives in template constants (`templates.py`), not inline f-strings, so `DESIGN.md` can review it.

## 5. The appliance (VPS)

`deploy/provision.sh` is idempotent and run as root once:

1. Create user `familyinc` (no sudo); `timedatectl set-timezone Asia/Jerusalem`.
2. Install uv + Node 22; clone the repo to `/opt/family-inc`; `uv sync`; `npm ci` in `bridge/` and `finance/`; install Chromium + Xvfb.
3. Copy `deploy/systemd/*` → `/etc/systemd/system/`; `systemctl enable --now` the bridge service + all timers.
4. Place secrets in `/etc/family-inc/` by hand (never scripted, never copied off the box).
5. Pair Baileys: `systemctl stop family-bridge && node bridge/baileys_listener.js` once, scan the QR, restart. `bridge/state/auth_state/` is in the weekly backup — **after a VPS rebuild, restore it before re-pairing**; a fresh QR scan is the fallback, not the default. (A Baileys *major*-version bump is the one case that requires wiping `auth_state/` and re-pairing.)

Units (schedules are code — change them via PR, not on the box):

| Unit | Schedule | Runs |
|---|---|---|
| `family-bridge.service` | always-on, `Restart=on-failure` | Baileys listener + outbox sender |
| `family-finance.timer` | ~06:00 daily | bank/card scrape → ingest *(building)* |
| `family-property.timer` | 07:10 + 19:10 | property scrape → Sheet + digest section |
| `family-reminders.timer` | 07:25 daily | reminders engine (computes, doesn't send) |
| `family-digest.timer` | 07:30 daily | daily digest assembly → outbox |
| `family-summarizer.timer` | hourly, 24h | classifier — runs at night so **criticals** can fire any hour; ordinary alerts are still held 22:00–07:00 by the outbox |
| `family-weekly.timer` | Sat 21:00 | weekly briefing + classifier-accuracy section |
| `family-backup.timer` | Sun 03:00 | tar `bridge/state` + `logs/` → Drive via rclone |

All timers: `Persistent=true`; `OnFailure=family-fail-flag@%n.service` appends the failing unit to `logs/fail.flag`. The next **delivered** digest reports it (a Hebrew line prepended) and clears the file; a flag still present on Saturday means digests aren't landing, and the weekly briefing says so.

## 6. Deployment

`deploy/deploy.sh` on the box:

```
git pull --ff-only
uv sync && (cd automation/bridge && npm ci) && (cd automation/finance && npm ci)
FAMILY_INC_SHEET_ID= uv run --frozen pytest -q   # red tests abort the deploy; running code is untouched
sudo /usr/bin/systemctl restart family-bridge    # the one whitelisted sudoers line
```

Timers pick up new code automatically on the next fire (they exec scripts from the repo); only the long-running bridge needs a restart. **Committed is not deployed** — a placed secret or a merged feature is inert until `deploy.sh` pulls it; confirm the box is at origin HEAD before declaring anything live. The `familyinc` user has exactly one sudo capability (restart `family-bridge`), so a compromised script can't escalate.

Dashboard deploys are `git push` (Pages rebuilds in ~30s); the PWA on both phones picks up on next open. `sw.js` cache-busts on a version bump in `config.example.js`, mirrored into `config.js`.

## 7. Testing policy

These suites exist and stay green:

| Suite | Covers |
|---|---|
| `test_engine.py` | fire-reason matrix (overdue/lead/due-today), tombstone skip window incl. future-skew, recurrence bumps incl. Feb-29 clamp + Custom flagging, send-success stamping, Last-Sent rerun idempotency |
| `test_outbox.py` | budget ledger: 2-cap, critical bypass, briefing exemption, shared-ledger across senders, (id,target) dedup, quiet-hours hold |
| `test_summarizer.py` | the 5 hard rules, per-group routing incl. `none`→NEEDS-A-LOOK, keyword fallback without a key, dispatch through the outbox, Sheet-tab persistence + rerun dedup, JSON-parse tolerance |
| `test_render_golden.py` | weekly briefing + daily digest rendered against `tests/fixtures/*.md` golden files (byte-exact; update goldens deliberately) |
| `test_sheet.py` | row-parsing tolerance, schema-drift guard both directions + flag heal, batched write path incl. formula survival, Settings/UserMap, upsert |
| `test_property.py` | card parse/normalize, BlockedError, empty result, seen-diff, Sheet-dedup, digest section, junk rejection |
| `test_apify.py` | adapter field maps, backup vs gap-fill, primary-wins merge, per-search/per-kind cost gate, fail-loud-only-on-zero-usable, token-inert |
| `test_finance.py` | mock CSV → ingest → mock Sheet, Txn-ID dedup/idempotency, fail-loud on missing creds, account upsert preserving human fields, column-order pin |

**Tests are hermetic.** An autouse fixture blanks `FAMILY_INC_SHEET_ID`, the LLM keys, and the SMTP creds, so the appliance's `deploy.sh` pytest can never reach the live Sheet, a real model, or actually send email. LLM calls are never made in tests — `lib/llm.py` has a fake injected via env. The dashboard has a manual smoke checklist in `DESIGN.md` §9 (no JS harness — boring tech; revisit if `app.js` exceeds ~2,000 lines).

## 8. Observability

- journald per unit (`journalctl -u family-reminders`).
- `logs/reminders_log.csv`, `logs/wa_classifier.csv`, `logs/llm_costs.csv`, `logs/outbox_ledger/`, `logs/delivery_log.csv` (transport per send-run: baileys | smtp | queued-stale).
- Self-reporting: the weekly briefing carries one system line — "7/7 runs green · 41 messages classified · 2 tombstone skips (max age 1.4h) · ₪6.10 LLM spend". Any fail-flag, schema-drift, or stale heartbeat replaces it with a warning. The humans never check logs unless the briefing tells them to.
- External uptime ping (healthchecks.io free tier) is an accepted gap — a hard VPS-down is currently silent; listed v1.1.

**"No digest by 08:00" runbook** (the most likely 24h failure is a logged-out WhatsApp session on a healthy VPS):

1. Check email — if the digest arrived there, the bridge is down but the system is fine: SSH in, re-pair the QR (restore `auth_state/` first if post-rebuild).
2. No email either → the VPS is down: reboot from the provider console; `Persistent=true` timers fire the missed runs on boot.
3. Repeated same-week logouts → treat as a ban signal; invoke the `SPEC.md` §10 fallback decision.

## 9. Git & repo conventions

- `main` is deployable; small focused commits; imperative subjects; the body explains *why* when non-obvious.
- Sessions `git pull --ff-only` before any work (origin is the sync point between agents) and commit at session end (the leader pushes; Pages + `deploy.sh` consume `main`). Git operations run on the PO's machine, never in a sandbox.
- No long-lived branches — this is a two-committer repo (Adar + Claude-in-session).
- The Sheet schema only ever gains columns (additive, backwards-compatible); old rows without M/N/O are treated as never-tombstoned. Rollback at any point = `git revert` + redeploy.
- Tags: `v1-live` at acceptance, then `vX.Y` per milestone.

## 10. Review ritual

Reviews fire on **milestones**, not every session: a new spec, an architecture change, anything touching delivery/budget/privacy guarantees, and each milestone close. Mechanism: `automation/review.py` builds the prompt + attachment list; the reviewer is the best available external model (DeepSeek default; substitutions logged). Findings are resolved in-session as Apply / Defend / Open, and any directional outcome is recorded. Tiny edits never trigger a review. On a milestone-closing session the gate runs **blocking inside the handoff chain** (`… && review gate && git commit && git push`) — a MAJOR finding stops the commit until resolved or explicitly overridden by the PO. A failed or truncated review never blocks a milestone: log it, proceed, note it in `BACKLOG.md`.

## 11. Definition of done (any work item)

Code merged with tests for its logic · constants in config · errors either degrade or surface (no silent paths) · contracts updated in `SPEC.md`/`DESIGN.md` if changed · `BACKLOG.md` status flipped · deployed and observed green once on the appliance.

=== End: ENGINEERING.md ===

=== File: automation/lib/outbox.py ===
"""
Family inc. — THE outbox chokepoint (SPEC.md §7.5). The only path to a human.

    queue(to, body, kind, source=…, msg_id=…)
      briefing → exempt from budget, subject to quiet hours (22:00–07:00 → hold)
      alert    → consult ledger[date][recipient]; if ≥cap → defer to tomorrow's
                 digest + log alert_suppressed_by_budget; else queue + increment
      critical → queue immediately, any hour, log budget_bypassed_critical
      all      → idempotent by (id, target); ledger + queue are durable on disk

The ledger is shared across ALL senders (D-015) — engine and summarizer can no
longer each spend 2/day. Every sender goes through `queue()`; the pre-M1
`queue_message()` shim was deleted in M2. Do not add side doors.

Delivery is the bridge's job: it polls the outbox JSONL, refuses targets not in
its machine-local recipients.json, dedups per (id, target) against the sent
ledger, and skips rows whose `not_before` hasn't arrived.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from automation.lib import config

log = logging.getLogger("outbox")

VALID_RECIPIENTS = {"adar", "shanee", "both"}
KINDS = {"alert", "critical", "briefing"}


# ---------------------------------------------------------------------------
# Quiet hours (SPEC.md §8.2 — enforced here, nowhere else)
# ---------------------------------------------------------------------------
def is_quiet_hours(now: datetime) -> bool:
    """True inside the 22:00–07:00 window (straddles midnight)."""
    h = now.hour
    return h >= config.QUIET_HOURS_START or h < config.QUIET_HOURS_END


def quiet_hours_release(now: datetime) -> datetime:
    """The 07:00 that ends the quiet window containing `now`."""
    release = now.replace(hour=config.QUIET_HOURS_END, minute=0, second=0, microsecond=0)
    if now.hour >= config.QUIET_HOURS_START:
        release += timedelta(days=1)
    return release


# ---------------------------------------------------------------------------
# Durable state: ledger, dedup index, deferred queue
# ---------------------------------------------------------------------------
def _ledger_path(day: date):
    return config.OUTBOX_LEDGER_DIR / f"{day.isoformat()}.json"


def read_ledger(day: date) -> dict[str, int]:
    p = _ledger_path(day)
    if not p.exists():
        return {}
    try:
        return {k: int(v) for k, v in json.loads(p.read_text(encoding="utf-8")).items()}
    except (json.JSONDecodeError, OSError, ValueError):
        # FAIL-CLOSED (outbox-budget#1): a corrupt ledger must NOT silently reopen
        # the day's 2/day cap. Treat the day as already at cap so alerts defer
        # (never lost — they ride tomorrow's digest) instead of flooding. Loud so
        # the operator inspects/deletes the file to reset. Atomic writes below make
        # this rare (only true disk corruption, not a torn write).
        log.error("outbox ledger CORRUPT (%s) — fail-closed: treating today as cap-reached "
                  "(alerts will defer). Inspect and delete to reset.", p)
        return {r: config.ALERT_BUDGET_PER_DAY for r in ("adar", "shanee")}


def _write_ledger(day: date, ledger: dict[str, int]) -> None:
    config.OUTBOX_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    p = _ledger_path(day)
    # Atomic write (outbox-budget#1): tmp + replace, so a crash mid-write can't
    # leave a torn ledger that read_ledger would have to fail-closed on.
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    tmp.replace(p)


@contextlib.contextmanager
def _ledger_lock(day: date):
    """Exclusive lock around a day's ledger read-modify-write (outbox-budget#2),
    so two concurrent senders can't both pass the 2/day check and double-spend —
    the exact race the single-shared-ledger rule (D-015) exists to prevent."""
    config.OUTBOX_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = config.OUTBOX_LEDGER_DIR / f"{day.isoformat()}.lock"
    with open(lock_path, "w", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _log_event(event: str, **fields) -> None:
    """Append one audit line (criticals bypassing, alerts suppressed, …)."""
    config.OUTBOX_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now().isoformat(timespec="seconds"), "event": event, **fields}
    with (config.OUTBOX_LEDGER_DIR / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _jsonl_rows(path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue  # torn tail line self-heals next poll (SPEC §9)
    return rows


def _seen_pairs() -> set[tuple[str, str]]:
    """(id, target) pairs already queued or sent — the idempotency index."""
    seen: set[tuple[str, str]] = set()
    for row in _jsonl_rows(config.OUTBOX_FILE):
        targets = ["adar", "shanee"] if row.get("to") == "both" else [row.get("to", "")]
        for t in targets:
            seen.add((row.get("id", ""), t))
    for row in _jsonl_rows(config.SENT_FILE):
        seen.add((row.get("id", ""), row.get("target", row.get("to", ""))))
    return seen


def _append_outbox(row: dict) -> None:
    config.OUTBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.OUTBOX_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _append_deferred(row: dict) -> None:
    config.DEFERRED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.DEFERRED_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_deferred(upto: date) -> list[dict]:
    """Budget-deferred items due for inclusion in today's digest (SPEC §7.5:
    over-budget alerts 'append to tomorrow's digest'). Non-consuming peek."""
    return [r for r in _jsonl_rows(config.DEFERRED_FILE)
            if r.get("deferred_on", "") < upto.isoformat()]


def pop_deferred(upto: date) -> list[dict]:
    """Like read_deferred, but consumes what it returns (real digest runs)."""
    rows = _jsonl_rows(config.DEFERRED_FILE)
    take = [r for r in rows if r.get("deferred_on", "") < upto.isoformat()]
    keep = [r for r in rows if r.get("deferred_on", "") >= upto.isoformat()]
    if take:
        config.DEFERRED_FILE.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
    return take


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------
@dataclass
class QueueResult:
    queued: list[dict] = field(default_factory=list)      # rows appended
    deferred: list[str] = field(default_factory=list)     # targets pushed to tomorrow's digest
    duplicates: list[str] = field(default_factory=list)   # targets skipped by (id, target) dedup


def queue(to: str, body: str, kind: str = "alert", *, source: str = "unknown",
          msg_id: Optional[str] = None, now: Optional[datetime] = None) -> QueueResult:
    """Queue one message toward a phone. See module docstring for semantics.

    `msg_id` should be the stable id from SPEC §8.4 (rem-…, wa-…, brief-…);
    a uuid is generated when omitted, which forfeits cross-run idempotency.
    """
    if to not in VALID_RECIPIENTS:
        raise ValueError(f"recipient must be one of {sorted(VALID_RECIPIENTS)}, got {to!r}")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {sorted(KINDS)}, got {kind!r}")
    if not body or not body.strip():
        raise ValueError("empty message body")

    now = now or datetime.now()
    msg_id = msg_id or str(uuid.uuid4())
    targets = ["adar", "shanee"] if to == "both" else [to]
    result = QueueResult()

    # Idempotency first — a re-run must not consume budget twice.
    seen = _seen_pairs()
    fresh = []
    for t in targets:
        if (msg_id, t) in seen:
            result.duplicates.append(t)
        else:
            fresh.append(t)
    targets = fresh
    if not targets:
        log.info("outbox: %s duplicate for all targets — no-op", msg_id)
        return result

    # Budget (alerts only; briefings exempt by principle, criticals by design).
    # The whole check+increment runs under an exclusive lock (outbox-budget#2) so
    # concurrent senders can't each pass the 2/day check on a stale read.
    if kind == "alert":
        with _ledger_lock(now.date()):
            ledger = read_ledger(now.date())
            ok, over = [], []
            for t in targets:
                (ok if ledger.get(t, 0) < config.ALERT_BUDGET_PER_DAY else over).append(t)
            for t in over:
                _append_deferred({
                    "id": msg_id, "to": t, "body": body.strip(), "source": source,
                    "deferred_on": now.date().isoformat(),
                })
                _log_event("alert_suppressed_by_budget", id=msg_id, target=t, source=source)
                log.info("alert suppressed by budget → tomorrow's digest (%s → %s)", msg_id, t)
            result.deferred = over
            if not ok:
                return result
            for t in ok:
                ledger[t] = ledger.get(t, 0) + 1
            _write_ledger(now.date(), ledger)
            targets = ok

    # Quiet hours: alerts + briefings hold; criticals do not (SPEC §8.2).
    not_before = None
    if kind != "critical" and is_quiet_hours(now):
        not_before = quiet_hours_release(now).isoformat(timespec="seconds")
    if kind == "critical":
        _log_event("budget_bypassed_critical", id=msg_id, targets=targets, source=source)

    row = {
        "id": msg_id,
        "to": "both" if set(targets) == {"adar", "shanee"} else targets[0],
        "body": body.strip(),
        "kind": kind,
        "source": source,
        "queued_at": now.astimezone().isoformat(timespec="seconds"),
    }
    if not_before:
        row["not_before"] = not_before
    _append_outbox(row)
    result.queued.append(row)
    return result


# ---------------------------------------------------------------------------
# Bridge health + delivery introspection (unchanged from wa_outbox.py)
# ---------------------------------------------------------------------------
def bridge_alive(now: Optional[datetime] = None) -> bool:
    """True if the bridge heartbeat file's mtime is fresh. Callers surface a
    warning when False — queued messages still go out on reconnect."""
    try:
        mtime = config.HEARTBEAT_FILE.stat().st_mtime
    except OSError:
        return False
    ts = datetime.fromtimestamp(mtime)
    now = now or datetime.now()
    return (now - ts) <= timedelta(minutes=config.HEARTBEAT_STALE_MINUTES)


def heartbeat_age_hours(now: Optional[datetime] = None) -> Optional[float]:
    """Heartbeat age in hours; None = no heartbeat file (bridge never ran
    here). Wall-clock by default — infra health is never simulated under
    --as-of. Past config.EMAIL_FALLBACK_AFTER_HOURS the daily digest degrades
    to the SPEC §10.2 email fallback."""
    try:
        mtime = config.HEARTBEAT_FILE.stat().st_mtime
    except OSError:
        return None
    now = now or datetime.now()
    return max(0.0, (now - datetime.fromtimestamp(mtime)).total_seconds() / 3600.0)


def delivery_status(msg_id: str) -> list[dict]:
    """Sent-ledger rows for one message id (one per target). Empty = pending."""
    return [r for r in _jsonl_rows(config.SENT_FILE) if r.get("id") == msg_id]


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] in VALID_RECIPIENTS:
        res = queue(sys.argv[1], " ".join(sys.argv[2:]), "alert", source="cli")
        alive = bridge_alive()
        print(f"queued {len(res.queued)} row(s), deferred {res.deferred or 'none'} "
              f"(bridge {'alive' if alive else 'DOWN — will send on reconnect'})")
    else:
        print("usage: python -m automation.lib.outbox adar|shanee|both <message text>")

=== End: automation/lib/outbox.py ===

=== File: automation/bridge/baileys_listener.js ===
/**
 * Family inc. — WhatsApp group listener (self-hosted, free bridge)
 *
 * Pairs as a WhatsApp Web "companion" to Adar's main number using Baileys
 * (the same QR-code flow as web.whatsapp.com). Two jobs:
 *
 * 1. LISTEN — group messages, normalized into the WhatsApp_Inbox schema,
 *    appended as JSON lines to ./state/inbox/whatsapp_inbox.jsonl.
 *    ALSO logs 1:1 replies from Adar/Shanee (configurable JIDs) to
 *    ./state/inbox/replies.jsonl as raw material for the v1.1 reply-parsing
 *    feature — it does NOT act on them and NEVER acks (reply parsing is PARKED
 *    to v1.1; SPEC §7.4 / honest-affordance §3.7). The parse + ack helpers
 *    below are the v1.1 scaffold, intentionally not called.
 * 2. SEND — polls ./state/outbox/whatsapp_outbox.jsonl (written by the Python
 *    automations via lib/outbox.py, the single chokepoint) and delivers each
 *    queued message to Adar/Shanee 1:1 (D-010: Baileys-first delivery).
 *
 * SEND SCOPE GUARD: outbound goes ONLY to the recipients named in
 * recipients.json ({"adar": "9725...@s.whatsapp.net", "shanee": ...}),
 * read from /etc/family-inc/ (appliance) or ./ (dev fallback) — never
 * committed either way. Any outbox row addressed to anyone else is refused
 * and logged.
 *
 * REPLY SCOPE GUARD: inbound 1:1 replies are accepted ONLY from the JIDs
 * listed in recipients.json. Everything else from @s.whatsapp.net is dropped.
 *
 * Nothing leaves the machine. The Python classifier (whatsapp_summarizer.py)
 * reads the JSONL file on its hourly run. This is the privacy-first path of
 * SPEC.md §8.6 — plaintext stays in the house.
 *
 * COST: free software, runs on the appliance VPS (ENGINEERING.md §5). ~₪0/mo.
 *
 * --- Setup (full runbook: ENGINEERING.md §5) ---
 *   cd automation/bridge
 *   npm ci
 *   node baileys_listener.js            # scan the QR with Adar's phone once
 *   # auth persists in ./state/auth_state/ ; restart resumes without re-scanning
 *   # after a VPS rebuild, RESTORE state/auth_state/ from backup before re-pairing
 *
 * --- Scope guard ---
 * Group messages (jid ends in @g.us) are always accepted.
 * 1:1 chats (@s.whatsapp.net) are accepted ONLY from configured recipient JIDs
 * (Adar + Shanee) and are LOGGED to replies.jsonl (no ack, no action — v1.1,
 * SPEC §7.4). All other 1:1 messages are dropped.
 * Media bodies are never stored; only has_media=true is recorded.
 *
 * --- Baileys v7 / LID (D-029, 2026-06-12) ---
 * WhatsApp finalized its LID identity migration; the 6.7.x line predates it
 * and could no longer encrypt the SELF-SEND leg (companion → own primary, i.e.
 * bridge → Adar's phone) — Adar's copy of every digest sat as "waiting for
 * this message" while Shanee's delivered. v7 is LID-aware and fixes this.
 * Consequences carried here: ESM (v7 dropped CommonJS), auth_state gains new
 * key types (lid-mapping / device-list / tctoken) — wipe state/auth_state/ and
 * re-pair when upgrading across this boundary. recipients.json stays PN-form
 * (@s.whatsapp.net); v7 resolves PN→LID internally on send.
 */

import fs from 'fs';
import path from 'path';
import P from 'pino';
import qrterm from 'qrcode-terminal'; // printQRInTerminal is long gone — we render the QR ourselves (connection.update)
import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} from '@whiskeysockets/baileys';

const ROOT = import.meta.dirname; // ESM: no __dirname (needs Node ≥20.11)
const STATE_DIR = path.join(ROOT, 'state'); // gitignored runtime state
const AUTH_DIR = path.join(STATE_DIR, 'auth_state');
const INBOX_DIR = path.join(STATE_DIR, 'inbox');
const INBOX_FILE = path.join(INBOX_DIR, 'whatsapp_inbox.jsonl');
const REPLIES_FILE = path.join(INBOX_DIR, 'replies.jsonl');
const HEARTBEAT_FILE = path.join(INBOX_DIR, 'heartbeat.txt');
const OUTBOX_DIR = path.join(STATE_DIR, 'outbox');
const OUTBOX_FILE = path.join(OUTBOX_DIR, 'whatsapp_outbox.jsonl');
const SENT_FILE = path.join(OUTBOX_DIR, 'whatsapp_sent.jsonl');
// Secrets live in /etc/family-inc (ENGINEERING §2, mode 600); a local
// recipients.json next to this script is the creds-less-dev fallback only.
const ETC_RECIPIENTS = '/etc/family-inc/recipients.json';
const RECIPIENTS_FILE = fs.existsSync(ETC_RECIPIENTS)
  ? ETC_RECIPIENTS
  : path.join(ROOT, 'recipients.json'); // never committed
const OUTBOX_POLL_MS = 15 * 1000;

fs.mkdirSync(INBOX_DIR, { recursive: true });
fs.mkdirSync(OUTBOX_DIR, { recursive: true });

// Heartbeat: whatsapp_summarizer.py checks this file's timestamp and surfaces a
// "bridge may be down" warning in the daily digest when it goes stale.
// Written on connect + every message + every 15 min while connected.
function beat() {
  try { fs.writeFileSync(HEARTBEAT_FILE, new Date().toISOString(), 'utf-8'); } catch (e) { /* noop */ }
}

const logger = P({ level: 'warn' });

// In-memory cache of group subject lookups so we don't spam metadata calls.
const groupNameCache = new Map();

function isGroup(jid) {
  return typeof jid === 'string' && jid.endsWith('@g.us');
}

// Pull the human-readable body out of the many WA message shapes.
function extractText(msg) {
  const m = msg.message || {};
  return (
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.imageMessage?.caption ||
    m.videoMessage?.caption ||
    m.documentMessage?.caption ||
    ''
  ).trim();
}

function hasMedia(msg) {
  const m = msg.message || {};
  return Boolean(
    m.imageMessage || m.videoMessage || m.audioMessage ||
    m.stickerMessage || m.documentMessage,
  );
}

function appendInbox(row) {
  fs.appendFileSync(INBOX_FILE, JSON.stringify(row) + '\n', 'utf-8');
}

// --- Reply handling (02_Reminders_Engine_Spec.md §"Reply parsing") ----------

/**
 * Parse a reminder-reply command from inbound text.
 * Returns {cmd, index, n} or null if no command recognized.
 *
 * Commands understood:
 *   done, 1 done, 1 ✅         → cmd='done'
 *   +7, 1 +7, snooze 7d        → cmd='snooze' with n=7
 *   mute 30d, 1 mute           → cmd='mute' with n=30 (default 30)
 *   list, today, ?             → cmd='list'
 *   help                       → cmd='help'
 */
function parseReply(text) {
  const t = (text || '').trim().toLowerCase();
  if (!t) return null;

  // Strip WhatsApp bold/italic markers
  const clean = t.replace(/[*_~`]/g, '').trim();

  // Index prefix: "1 done", "2 +7", "3 mute"
  const indexMatch = clean.match(/^(\d+)\s+(.+)$/);
  const index = indexMatch ? parseInt(indexMatch[1], 10) : null;
  const cmdPart = indexMatch ? indexMatch[2] : clean;

  // done / ✅
  if (/^(done|✅)$/.test(cmdPart)) {
    return { cmd: 'done', index, n: null };
  }

  // snooze: +N, snooze Nd, +Nd
  const snoozeMatch = cmdPart.match(/^\+(\d+)$/);
  if (snoozeMatch) {
    return { cmd: 'snooze', index, n: parseInt(snoozeMatch[1], 10) };
  }
  const snoozeWordMatch = cmdPart.match(/^snooze\s+(\d+)d?$/);
  if (snoozeWordMatch) {
    return { cmd: 'snooze', index, n: parseInt(snoozeWordMatch[1], 10) };
  }

  // mute: mute, mute Nd
  if (/^mute$/.test(cmdPart)) {
    return { cmd: 'mute', index, n: 30 };
  }
  const muteMatch = cmdPart.match(/^mute\s+(\d+)d?$/);
  if (muteMatch) {
    return { cmd: 'mute', index, n: parseInt(muteMatch[1], 10) };
  }

  // list / today / ?
  if (/^(list|today|\?)$/.test(cmdPart)) {
    return { cmd: 'list', index: null, n: null };
  }

  // help
  if (cmdPart === 'help') {
    return { cmd: 'help', index: null, n: null };
  }

  return null; // unrecognized
}

/**
 * Build an immediate acknowledgment for recognized commands.
 * For done/snooze/mute this is a quick confirmation; the engine applies the
 * actual sheet change and may send a follow-up message.
 * For list/?, the engine will send the full digest separately.
 *
 * v1.1 STUB — intentionally NOT called: 1:1 replies are log-only until reply
 * parsing ships (SPEC §7.4). Kept (with parseReply) as the scaffold that path
 * will wire up; sending an ack today would promise an affordance that does
 * nothing (§3.7). (B1, 2026-06-18.)
 */
function ackText(parsed, rawText) {
  if (!parsed) {
    return "👋 Didn't catch that. Reply with:\n" +
           "• 1 ✅ to mark done\n" +
           "• 1 +7 to snooze 7 days\n" +
           "• 1 mute to mute 30 days\n" +
           "• ? to see today's list";
  }
  switch (parsed.cmd) {
    case 'done':
      return parsed.index
        ? `✅ Got it — marking #${parsed.index} as done`
        : '✅ Got it — marking as done';
    case 'snooze':
      return parsed.index
        ? `📆 Got it — snoozing #${parsed.index} by ${parsed.n} day(s)`
        : `📆 Got it — snoozing by ${parsed.n} day(s)`;
    case 'mute':
      return parsed.index
        ? `🤐 Got it — muting #${parsed.index} for ${parsed.n} day(s)`
        : `🤐 Got it — muting for ${parsed.n} day(s)`;
    case 'list':
    case '?':
    case 'today':
      return '📋 Fetching today\'s reminders…';
    case 'help':
      return 'Reply to reminder digests:\n' +
             '• N ✅ — mark #N done\n' +
             '• N +D — snooze #N by D days\n' +
             '• N mute — mute #N 30 days\n' +
             '• ? — show today\'s list';
    default:
      return null;
  }
}

// --- Outbound (Baileys-first delivery, decision 2026-06-04) ----------------

function loadRecipients() {
  try {
    const r = JSON.parse(fs.readFileSync(RECIPIENTS_FILE, 'utf-8'));
    // hard scope guard: exactly these two logical names, 1:1 JIDs only
    const out = {};
    for (const name of ['adar', 'shanee']) {
      if (typeof r[name] === 'string' && r[name].endsWith('@s.whatsapp.net')) {
        out[name] = r[name];
      }
    }
    return out;
  } catch (e) {
    return null; // missing/invalid -> sending disabled, listening unaffected
  }
}

/**
 * Return the set of JIDs that are allowed to send 1:1 replies.
 * These are the JIDs configured in recipients.json (Adar + Shanee).
 */
function replyJids() {
  const r = loadRecipients();
  if (!r) return new Set();
  return new Set(Object.values(r));
}

/**
 * Check if a JID is a configured reply sender.
 * Used to lift the groups-only guard for 1:1 messages from Adar/Shanee.
 */
function isReplySender(jid) {
  return replyJids().has(jid);
}

function readJsonl(file) {
  if (!fs.existsSync(file)) return [];
  return fs.readFileSync(file, 'utf-8')
    .split('\n')
    .filter(Boolean)
    .map((l) => { try { return JSON.parse(l); } catch (e) { return null; } })
    .filter(Boolean);
}

let outboxBusy = false;
async function processOutbox(sock) {
  if (outboxBusy) return; // don't overlap polls
  outboxBusy = true;
  try {
    const recipients = loadRecipients();
    const pending = readJsonl(OUTBOX_FILE);
    if (!pending.length) return;
    if (!recipients || !Object.keys(recipients).length) {
      console.log('[outbox] recipients.json missing/invalid — sending disabled');
      return;
    }
    // dedup per (id, target) so a crash mid-"both" still delivers the second leg.
    // Only TERMINAL outcomes (sent / refused) suppress a retry — a transient
    // 'send_failed' must NOT mark the pair done, or GAP-10's retry never happens.
    const done = new Set(readJsonl(SENT_FILE)
      .filter((r) => r.status === 'sent' || r.status === 'refused_unknown_recipient')
      .map((r) => `${r.id}:${r.to}`));
    for (const row of pending) {
      if (!row.id) continue;
      // Quiet-hours hold (lib/outbox.py stamps not_before as local-naive ISO;
      // JS parses offset-less date-times as local, and the appliance runs
      // Asia/Jerusalem — SPEC §8.2/§8.5)
      if (row.not_before && new Date(row.not_before) > new Date()) continue;
      const targets = row.to === 'both' ? ['adar', 'shanee'] : [row.to];
      for (const name of targets) {
        if (done.has(`${row.id}:${name}`)) continue;
        const jid = recipients[name];
        if (!jid) { // scope guard: refuse anything not adar/shanee
          fs.appendFileSync(SENT_FILE, JSON.stringify({
            id: row.id, to: name, status: 'refused_unknown_recipient',
            at: new Date().toISOString(),
          }) + '\n', 'utf-8');
          console.log(`[outbox] REFUSED ${row.id} → "${name}" (not a configured recipient)`);
          continue;
        }
        // GAP-10: per-row try/catch — one failed send must not abandon the rest of
        // the batch (head-of-line block). Record the failure (transient, so NOT in
        // `done` → retried next poll) and continue with the other rows/targets.
        try {
          await sock.sendMessage(jid, { text: String(row.body || '').slice(0, 4096) });
          fs.appendFileSync(SENT_FILE, JSON.stringify({
            id: row.id, to: name, status: 'sent', at: new Date().toISOString(),
          }) + '\n', 'utf-8');
          console.log(`[outbox] sent ${row.id} → ${name}`);
          done.add(`${row.id}:${name}`);
        } catch (e) {
          fs.appendFileSync(SENT_FILE, JSON.stringify({
            id: row.id, to: name, status: 'send_failed',
            at: new Date().toISOString(), error: String(e && e.message || e).slice(0, 200),
          }) + '\n', 'utf-8');
          console.log(`[outbox] send FAILED ${row.id} → ${name} (will retry next poll): ${e && e.message || e}`);
        }
      }
    }
  } catch (e) {
    console.log('[outbox] error (will retry next poll):', e.message || e);
  } finally {
    outboxBusy = false;
  }
}

async function resolveGroupName(sock, jid) {
  if (groupNameCache.has(jid)) return groupNameCache.get(jid);
  try {
    const meta = await sock.groupMetadata(jid);
    groupNameCache.set(jid, meta.subject || jid);
    return meta.subject || jid;
  } catch (e) {
    return jid;
  }
}

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
    logger,
    markOnlineOnConnect: false, // stay invisible except when delivering outbox
    syncFullHistory: false,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (u) => {
    const { connection, lastDisconnect, qr } = u;
    if (qr) {
      // Pairing only (no auth_state yet): scan once with Adar's phone ->
      // WhatsApp -> Linked devices. Re-renders if the code expires unscanned.
      qrterm.generate(qr, { small: true });
      console.log('[pair] scan the QR above: WhatsApp → Settings → Linked devices → Link a device');
    }
    if (connection === 'open') {
      console.log('[baileys] connected — listening to GROUP messages + logging 1:1 replies (v1.1, no ack); outbox sender armed');
      beat();
      processOutbox(sock); // flush anything queued while we were down
      if (!global._beatTimer) {
        global._beatTimer = setInterval(beat, 15 * 60 * 1000); // idle heartbeat
      }
      if (!global._outboxTimer) {
        global._outboxTimer = setInterval(() => processOutbox(sock), OUTBOX_POLL_MS);
      }
    } else if (connection === 'close') {
      // stop the timers so a dead bridge actually LOOKS dead (and can't "send")
      if (global._beatTimer) { clearInterval(global._beatTimer); global._beatTimer = null; }
      if (global._outboxTimer) { clearInterval(global._outboxTimer); global._outboxTimer = null; }
      const code = lastDisconnect?.error?.output?.statusCode;
      const loggedOut = code === DisconnectReason.loggedOut;
      console.log(`[baileys] connection closed (code ${code}); ${loggedOut ? 'logged out — delete auth_state and re-pair' : 'reconnecting…'}`);
      if (!loggedOut) start();
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    beat();
    if (type !== 'notify') return; // ignore history backfill
    for (const msg of messages) {
      try {
        const jid = msg.key?.remoteJid;
        if (msg.key?.fromMe) continue;     // ignore our own sends

        // --- 1:1 replies: LOG ONLY, parked to v1.1 (SPEC §7.4) ---
        // Reply *parsing* (acting on commands, acking the sender) is a v1.1
        // feature whose prerequisites aren't met (LID-addressing below;
        // reply_handler.py unwired). Until then the bridge only RECORDS replies
        // from known senders to replies.jsonl as raw material for that feature —
        // it never acts on them and NEVER acks. Acking would promise an
        // affordance that does nothing (SPEC §3.7 honest-affordance). (B1, PO
        // call 2026-06-18: "just log for now".)
        if (!isGroup(jid)) {
          // LID caveat (v7): inbound 1:1 chats may be addressed @lid while
          // recipients.json holds PN JIDs, so LID-addressed replies fall
          // through this guard and are DROPPED — resolve via
          // msg.key.remoteJidAlt when the v1.1 feature is built.
          if (!isReplySender(jid)) continue; // drop unknown 1:1 messages
          const text = extractText(msg);
          if (!text) continue; // empty message, skip
          const senderJid = msg.key?.participant || jid;
          const senderName = msg.pushName || senderJid.split('@')[0];
          const tsSec = Number(msg.messageTimestamp?.toNumber?.() ?? msg.messageTimestamp) || Math.floor(Date.now() / 1000); // v7 protos may carry Long

          const parsed = parseReply(text); // recorded for v1.1; NOT acted on

          // Append to replies.jsonl for the future reply-parsing feature. No
          // engine consumes this yet (reply_handler.py is unwired) and no ack
          // is sent — see the block comment above.
          const replyRow = {
            msg_id: msg.key?.id,
            sender_jid: senderJid,
            sender_name: senderName,
            received_at: new Date(tsSec * 1000).toISOString(),
            text: text,
            parsed: parsed ? { cmd: parsed.cmd, index: parsed.index, n: parsed.n } : null,
            recognized: !!parsed,
          };
          fs.appendFileSync(REPLIES_FILE, JSON.stringify(replyRow) + '\n', 'utf-8');
          console.log(`[reply-log] ${senderName}: "${text}" → ${parsed ? parsed.cmd : 'unrecognized'} (logged, not acted on — v1.1)`);
          continue;
        }

        // --- Group message handling (existing) ---
        const text = extractText(msg);
        const media = hasMedia(msg);
        if (!text && !media) continue;     // nothing to record

        const groupName = await resolveGroupName(sock, jid);
        const senderJid = msg.key?.participant || jid; // may be @lid post-v7 — stored as the opaque id it is
        const senderName = msg.pushName || senderJid.split('@')[0];
        const tsSec = Number(msg.messageTimestamp?.toNumber?.() ?? msg.messageTimestamp) || Math.floor(Date.now() / 1000); // v7 protos may carry Long

        appendInbox({
          msg_id: msg.key?.id,
          group_jid: jid,
          group_name: groupName,
          sender_jid: senderJid,
          sender_name: senderName,
          received_at: new Date(tsSec * 1000).toISOString(),
          text: media && !text ? '' : text, // never store media body
          has_media: media,
        });
        console.log(`[inbox] ${groupName} | ${senderName}: ${(text || '[media]').slice(0, 60)}`);
      } catch (e) {
        logger.warn({ e }, 'failed to process message');
      }
    }
  });
}

start().catch((e) => {
  console.error('[baileys] fatal', e);
  process.exit(1);
});

=== End: automation/bridge/baileys_listener.js ===

=== File: tests/test_outbox.py ===
"""Tests for automation/lib/outbox.py — THE chokepoint (SPEC §7.5, §8.1–8.4).

Covers the ENGINEERING §7 minimum bar: 2-cap, critical bypass, briefing
exemption, shared ledger across two sender sources, (id, target) dedup,
quiet-hours hold.
"""

import json
from datetime import date, datetime

import pytest

from automation.lib import config, outbox


DAY = date(2026, 6, 10)
MORNING = datetime(2026, 6, 10, 9, 30)   # inside send hours
NIGHT = datetime(2026, 6, 10, 23, 15)    # inside quiet hours (22:00–07:00)
EARLY = datetime(2026, 6, 10, 6, 20)     # quiet hours, before 07:00


def _outbox_rows():
    if not config.OUTBOX_FILE.exists():
        return []
    return [json.loads(l) for l in config.OUTBOX_FILE.read_text(encoding="utf-8").splitlines()]


def _events():
    p = config.OUTBOX_LEDGER_DIR / "events.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# Budget: 2/day cap, enforced per recipient at this single chokepoint
# ---------------------------------------------------------------------------
class TestBudget:
    def test_two_alerts_pass_third_defers(self, tmp_runtime):
        for i in range(2):
            res = outbox.queue("adar", f"alert {i}", "alert", msg_id=f"a{i}", now=MORNING)
            assert res.queued and not res.deferred
        res = outbox.queue("adar", "alert 2", "alert", msg_id="a2", now=MORNING)
        assert res.deferred == ["adar"]
        assert not res.queued
        assert len(_outbox_rows()) == 2
        assert outbox.read_ledger(DAY) == {"adar": 2}
        assert any(e["event"] == "alert_suppressed_by_budget" for e in _events())

    def test_corrupt_ledger_fails_closed(self, tmp_runtime):
        """outbox-budget#1: a torn/corrupt ledger must NOT silently reopen the
        day's cap (fail-OPEN flooded alerts). Fail CLOSED — read as cap-reached,
        so alerts defer (never lost) until the operator inspects + deletes it."""
        config.OUTBOX_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        (config.OUTBOX_LEDGER_DIR / f"{DAY.isoformat()}.json").write_text(
            "{ this is not valid json", encoding="utf-8")
        assert outbox.read_ledger(DAY) == {"adar": config.ALERT_BUDGET_PER_DAY,
                                           "shanee": config.ALERT_BUDGET_PER_DAY}
        res = outbox.queue("adar", "should defer", "alert", msg_id="z1", now=MORNING)
        assert res.deferred == ["adar"] and not res.queued      # deferred, not flooded
        # …but a critical still pierces — a corrupt ledger must never block safety.
        assert outbox.queue("adar", "emergency", "critical", msg_id="z2", now=MORNING).queued

    def test_ledger_is_per_recipient(self, tmp_runtime):
        outbox.queue("adar", "x", "alert", msg_id="a1", now=MORNING)
        outbox.queue("adar", "y", "alert", msg_id="a2", now=MORNING)
        res = outbox.queue("shanee", "z", "alert", msg_id="a3", now=MORNING)
        assert res.queued  # shanee's budget untouched by adar's spend

    def test_shared_ledger_across_sources(self, tmp_runtime):
        """The D-015 fix: engine + summarizer can no longer each spend 2/day."""
        outbox.queue("adar", "engine fire", "alert", source="daily_digest",
                     msg_id="rem-1", now=MORNING)
        outbox.queue("adar", "group alert", "alert", source="whatsapp_summarizer",
                     msg_id="wa-1", now=MORNING)
        res = outbox.queue("adar", "third", "alert", source="whatsapp_summarizer",
                           msg_id="wa-2", now=MORNING)
        assert res.deferred == ["adar"]

    def test_both_splits_when_one_recipient_capped(self, tmp_runtime):
        outbox.queue("adar", "x", "alert", msg_id="a1", now=MORNING)
        outbox.queue("adar", "y", "alert", msg_id="a2", now=MORNING)
        res = outbox.queue("both", "to everyone", "alert", msg_id="b1", now=MORNING)
        assert res.deferred == ["adar"]
        assert len(res.queued) == 1
        assert res.queued[0]["to"] == "shanee"

    def test_deferred_lands_in_tomorrows_digest(self, tmp_runtime):
        outbox.queue("adar", "x", "alert", msg_id="a1", now=MORNING)
        outbox.queue("adar", "y", "alert", msg_id="a2", now=MORNING)
        outbox.queue("adar", "held", "alert", msg_id="a3", now=MORNING)
        # same day: not yet visible
        assert outbox.read_deferred(DAY) == []
        # next morning: visible, then consumed exactly once
        tomorrow = date(2026, 6, 11)
        assert [r["body"] for r in outbox.read_deferred(tomorrow)] == ["held"]
        assert [r["body"] for r in outbox.pop_deferred(tomorrow)] == ["held"]
        assert outbox.pop_deferred(tomorrow) == []


# ---------------------------------------------------------------------------
# Critical: bypasses budget AND quiet hours, with an audit trail
# ---------------------------------------------------------------------------
class TestCritical:
    def test_critical_bypasses_spent_budget(self, tmp_runtime):
        outbox.queue("adar", "x", "alert", msg_id="a1", now=MORNING)
        outbox.queue("adar", "y", "alert", msg_id="a2", now=MORNING)
        res = outbox.queue("adar", "GAN CLOSED", "critical", msg_id="wa-crit", now=MORNING)
        assert res.queued
        assert any(e["event"] == "budget_bypassed_critical" for e in _events())

    def test_critical_ignores_quiet_hours(self, tmp_runtime):
        res = outbox.queue("both", "burst pipe", "critical", msg_id="c1", now=NIGHT)
        assert res.queued
        assert "not_before" not in res.queued[0]

    def test_critical_does_not_consume_budget(self, tmp_runtime):
        outbox.queue("adar", "emergency", "critical", msg_id="c1", now=MORNING)
        assert outbox.read_ledger(DAY).get("adar", 0) == 0


# ---------------------------------------------------------------------------
# Briefings: exempt from budget, held by quiet hours
# ---------------------------------------------------------------------------
class TestBriefing:
    def test_briefings_exempt_from_budget(self, tmp_runtime):
        for i in range(4):
            res = outbox.queue("adar", f"briefing {i}", "briefing",
                               msg_id=f"brief-{i}", now=MORNING)
            assert res.queued
        assert outbox.read_ledger(DAY) == {}

    def test_briefing_held_in_quiet_hours(self, tmp_runtime):
        res = outbox.queue("adar", "weekly", "briefing", msg_id="brief-w", now=NIGHT)
        assert res.queued[0]["not_before"] == "2026-06-11T07:00:00"


# ---------------------------------------------------------------------------
# Quiet hours (SPEC §8.2): 22:00–07:00, alerts hold to 07:00
# ---------------------------------------------------------------------------
class TestQuietHours:
    def test_alert_at_night_holds_to_next_morning(self, tmp_runtime):
        res = outbox.queue("adar", "late alert", "alert", msg_id="a1", now=NIGHT)
        assert res.queued[0]["not_before"] == "2026-06-11T07:00:00"

    def test_alert_before_dawn_holds_to_same_morning(self, tmp_runtime):
        res = outbox.queue("adar", "early alert", "alert", msg_id="a1", now=EARLY)
        assert res.queued[0]["not_before"] == "2026-06-10T07:00:00"

    def test_daytime_alert_has_no_hold(self, tmp_runtime):
        res = outbox.queue("adar", "day alert", "alert", msg_id="a1", now=MORNING)
        assert "not_before" not in res.queued[0]

    def test_is_quiet_hours_window(self):
        assert outbox.is_quiet_hours(datetime(2026, 6, 10, 22, 0))
        assert outbox.is_quiet_hours(datetime(2026, 6, 10, 3, 0))
        assert outbox.is_quiet_hours(datetime(2026, 6, 10, 6, 59))
        assert not outbox.is_quiet_hours(datetime(2026, 6, 10, 7, 0))
        assert not outbox.is_quiet_hours(datetime(2026, 6, 10, 21, 59))


# ---------------------------------------------------------------------------
# Idempotency (SPEC §8.4): (id, target) dedup against queue + sent ledger
# ---------------------------------------------------------------------------
class TestDedup:
    def test_requeue_same_id_is_noop(self, tmp_runtime):
        outbox.queue("adar", "digest", "alert", msg_id="brief-daily-2026-06-10", now=MORNING)
        res = outbox.queue("adar", "digest", "alert", msg_id="brief-daily-2026-06-10", now=MORNING)
        assert res.duplicates == ["adar"]
        assert not res.queued
        assert len(_outbox_rows()) == 1
        # budget charged once, not twice
        assert outbox.read_ledger(DAY) == {"adar": 1}

    def test_dedup_against_sent_ledger(self, tmp_runtime):
        config.SENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.SENT_FILE.write_text(
            json.dumps({"id": "rem-5-2026-06-10", "to": "adar", "status": "sent"}) + "\n",
            encoding="utf-8")
        res = outbox.queue("adar", "already sent", "alert", msg_id="rem-5-2026-06-10", now=MORNING)
        assert res.duplicates == ["adar"]
        assert not res.queued

    def test_both_dedups_per_target(self, tmp_runtime):
        outbox.queue("adar", "x", "alert", msg_id="m1", now=MORNING)
        res = outbox.queue("both", "x", "alert", msg_id="m1", now=MORNING)
        assert res.duplicates == ["adar"]
        assert len(res.queued) == 1
        assert res.queued[0]["to"] == "shanee"


# ---------------------------------------------------------------------------
# Validation + torn-line resilience
# ---------------------------------------------------------------------------
class TestValidation:
    def test_bad_recipient_raises(self, tmp_runtime):
        with pytest.raises(ValueError):
            outbox.queue("savta", "hi", "alert", now=MORNING)

    def test_bad_kind_raises(self, tmp_runtime):
        with pytest.raises(ValueError):
            outbox.queue("adar", "hi", "nudge", now=MORNING)

    def test_empty_body_raises(self, tmp_runtime):
        with pytest.raises(ValueError):
            outbox.queue("adar", "   ", "alert", now=MORNING)

    def test_torn_outbox_line_skipped(self, tmp_runtime):
        config.OUTBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.OUTBOX_FILE.write_text('{"id": "ok", "to": "adar"}\n{"id": "torn', encoding="utf-8")
        res = outbox.queue("adar", "after torn line", "alert", msg_id="new", now=MORNING)
        assert res.queued  # reader skipped the torn tail (SPEC §9)

=== End: tests/test_outbox.py ===


```

</details>
