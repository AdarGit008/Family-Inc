# Milestone review — milestone lane

- **When:** 2026-06-18T16:41:01
- **Provider:** DeepSeek (`deepseek-chat`)
- **Elapsed:** 32.4s
- **Attached files (17):**
  - `CLAUDE.md` (5,311 chars)
  - `SPEC.md` (34,644 chars)
  - `BACKLOG.md` (8,098 chars)
  - `ENGINEERING.md` (13,717 chars)
  - `DESIGN.md` (9,973 chars)
  - `automation/whatsapp_summarizer.py` (32,315 chars)
  - `automation/lib/categorize.py` (8,418 chars)
  - `automation/lib/llm.py` (7,955 chars)
  - `automation/weekly_briefing.py` (23,896 chars)
  - `automation/reminders_engine.py` (14,833 chars)
  - `automation/daily_digest.py` (19,288 chars)
  - `automation/hebcal_client.py` (9,845 chars)
  - `automation/templates.py` (4,289 chars)
  - `automation/lib/config.py` (17,062 chars)
  - `automation/bridge/baileys_listener.js` (18,359 chars)
  - `dashboard/app.js` (66,166 chars)
  - `deploy/deploy.sh` (802 chars)

---

## Response

### Concerns
1. **Critical: `automation/whatsapp_summarizer.py` `hard_rule_alert` returns `None, False` for muted groups before checking critical keywords (line ~220).**  
   The mute short-circuit fires before the critical-keyword loop, so a muted group with a safety keyword never reaches the critical match — **criticals do not pierce mute here**, contradicting B3/SPEC §7.3 (which says they should). The code says `if importance_default == "mute": return None, False` before the `for pat in c["critical_keywords"]:` loop. The PO call that criticals pierce mute is directly violated.  
   Fix: move the non-critical mute check *after* the critical loop.

2. **Major: `deploy.sh` runs `npm ci --omit=dev` in `automation/finance` but the finance scraper (`scrape.js`) may need devDependencies for Puppeteer's `puppeteer-core` browser download.**  
   The spec says `israeli-bank-scrapers` uses Puppeteer. If Puppeteer is in devDependencies, `--omit=dev` skips it → the scraper crashes. The M6.2 runbook must verify this, and the `--omit=dev` decision needs an explicit entry in `package.json`'s dependency tree, not an assumption that the browser binary ships in production deps.

3. **Major: `automation/lib/categorize.py` `_gapfill_batch` sends indexes (not Txn-IDs) to the LLM, but the prompt includes `amount` — which, combined with `description`, can re-identify a transaction across batches.**  
   SPEC §8.6 says "description + amount, never account numbers, balances, credentials, identifiers". The index is a positional identifier that, when combined with amount + description, effectively re-identifies the row to the model within that batch. This is a privacy boundary concern: the guarantee says "never identifiers", but a row's index within a batch + amount + description is itself identifying. Consider hashing the row to a per-batch ephemeral ID, or logging this as an accepted residual risk in §8.6.

4. **Major: `dashboard/app.js` `bumpDate` duplicates `automation/lib/dates.bump_due` (SPEC §7.1) with no cross-referencing.**  
   Two implementations of the same recurrence logic (month-end clamping, Feb-29 handling, Weekly/Monthly/Quarterly/Yearly periods) will diverge. The engine already flags Custom/unknown periods for review; the dashboard silently returns `null` for unknown periods and the row stays Done (no bump) — the engine then can't bump it later because the status is Done. Either both surfaces must agree on what "unbumpable" means, or the dashboard must not bump at all and leave it to the engine (which is what the SPEC says: §7.1 says "recurrence on Done" is the engine's job, not the dashboard's — the dashboard should only stamp Done + Tombstone).

5. **Medium: `automation/hebcal_client.py` `chag_candles` scans up to 3 days ahead for havdalah — but a 2-day yom-tov block could have the havdalah >3 days out (e.g., Shabbat + 2-day yom-tov).**  
   A Friday yom-tov eve followed by Shabbat + a 2-day chag = havdalah on Sunday night, which is ~3 days out. If the havdalah falls on day 4, `chag_candles` returns `None` (degrades quiet — acceptable), but the candle-lighting line fires without havdalah (shows `--`) or doesn't fire at all. This is a quiet failure that produces a wrong-or-missing line. The window should be `+4` or `+5` to cover edge cases, or the code should emit the candle line even without havdalah.

6. **Medium: `automation/weekly_briefing.py` `section_system` reads `reminders_log.csv` with `csv.DictReader` but the log format is append-only — a truncated final line (from a power loss or concurrent append) silently skips the last row, and an empty log file raises `StopIteration`-like state on first read.**  
   The `try/except OSError` covers missing file, but a corrupted final line causes `csv.DictReader` to skip it entirely (which is acceptable for a heartbeat — one run's data lost). However, `_file_not_found` and `_torn_line` are indistinguishable: a missing log means "first run" (zero data), but a torn log also returns zero data. The weekly briefing then reports "No system activity logged this week yet" on the first normal run after a torn write. This is a degrade-quiet failure that hides the system-health line. Add a sentinel: if the file exists but is empty or the last line is truncated, log a warning and still report zero runs (do not crash).

7. **Low: `automation/bridge/baileys_listener.js` `processOutbox` does not trim `row.body` before sending — the header comment says `String(row.body || '').slice(0, 4096)` but WhatsApp may refuse a blank body (empty briefing).**  
   A queued message with `body = ""` (from a code bug, not current code) would send an empty text message. Add a `if (!row.body?.trim()) continue` guard.

### Missed alternatives
- Hard-rule mute check could be a single `if` at the top of `classify()` instead of inside `hard_rule_alert`, making the control flow linear.
- Dashboard recurrence bump could be removed entirely, deferring to the engine's 07:25 bump (SPEC §7.1 already says the engine bumps on Done — the dashboard is racing it).
- The finance gap-fill batch size (`GAPFILL_MAX_BATCH = 80`) could be adaptive: half the remaining misses, so the last tiny batch doesn't waste an LLM call.
- The Hebcal `chag_candles` 3-day window could be replaced with a single API call that returns the next havdalah after a given date, avoiding the arbitrary bound.
- The `deploy.sh` `--omit=dev` line for `automation/finance` could be omitted and let `npm ci` pull everything; the lockfile already controls what ships — `--omit=dev` is only a disk-space optimization.

### Affirmations
- **B5 chunk-loop design** is correct: a 45-day backlog is >80 txns, and the old fixed-600-token reply truncated the JSON array mid-stream, losing data permanently. The per-chunk token budget (`len(batch)*24`) is the right fix — proportional, self-healing.
- **B1 bridge log-only handler** is principled: logging to `replies.jsonl` with no ack is the minimal viable scaffold for v1.1, and the public code is easier to reason about with the dead `reply_handler.py` unwired.
- **B4 provider-agnostic privacy guarantee** avoids the asymmetry trap: treating every provider as DeepSeek (minimal payload) means switching providers is a key swap, not a privacy review — which matches the "boring tech" principle (no policy changes at a config boundary).
- **B8 queue cap at 50 with one-shot warning** is well-engineered: the queue is already persisted to `localStorage`, so an unbounded queue would grow silently across days, then flush 500+ writes on reconnect, consuming the API quota. The one-shot warning re-armed after a flush is the right UX pattern.
- **`deploy.sh` restores `--frozen`** on the `pytest` line — the reappearance of this flag after it was accidentally removed is the kind of audit artifact that justifies the adversarial review process.

### Concrete suggestions
1. **`automation/whatsapp_summarizer.py` `hard_rule_alert` (line ~215–225):**  
   Replace the current mute block:  
   ```python
   # Mute is otherwise a hard rule: below the critical tier a muted group raises
   # NO alert (no alert-keyword / teacher-evening / vaad ALERT, no budget spend).
   ```
   with:  
   ```python
   # Mute short-circuit: AFTER the critical check so criticals pierce mute (SPEC §7.3 B3).
   if c["importance_default"] == "mute":
       return None, False
   ```  
   And move this block to after the critical-keyword loop (lines ~223–227).  
   *Severity: critical (functional bug).

2. **`dashboard/app.js` `bumpDate` (around line ~850):**  
   Remove `bumpDate` entirely and stop doing recurrence bumps in `handleDone`. Only stamp Status=Done, DoneAt, LastDoneBy, Tombstone — leave the recurrence bump to the engine (07:25), which already handles Feb-29 clamping, Custom-flagging, and tombstone-guard skipping.  
   *Severity: major (divergent implementations, SPEC violation: §7.1 says engine bumps, not dashboard).

3. **`automation/hebcal_client.py` `chag_candles` (line ~280):**  
   Change `d + timedelta(days=3)` to `d + timedelta(days=5)` to cover the Shabbat + 2-day-yom-tov edge case.  
   *Severity: medium (quiet degradation on a known calendar edge case).

### One question for the team
**SPEC §7.1 says "recurrence on Done: bump Due Date by the period" and places this in the engine (07:25), but the dashboard also bumps on tap (`bumpDate` in `handleDone`).**  
   One side is wrong: either the SPEC (the dashboard should not bump — it races the engine and causes the engine to double-bump on the next 07:25 run), or the dashboard (the bump should be instantaneous, and the engine should skip rows that were bumped by the dashboard). Which is the intended behavior — and if the dashboard is allowed to bump, how do we prevent the engine from bumping the same row again? (It currently skips done rows in `classify()` but the engine's `recurrence_writes` runs BEFORE `classify` and would see the Done status and bump again.)

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
# Session changes — Brief 1 fix lane (blocker + 7 majors)

Source: `reviews/fix_brief_1_blocker_major_2026-06-18.md` (from the 2026-06-18 audit).
Test baseline 341 → **355 green**. Three PO decisions were taken up front (B1/B3/B4).

## What this session changed

- **B1 (blocker, SPEC §7.4):** the Baileys bridge no longer acks 1:1 chats. Inbound 1:1s from known senders are **logged** to `replies.jsonl` (raw material for the parked v1.1 reply feature); the bridge never acts on them and never acks (honest-affordance §3.7). `reply_handler.py` stays unwired; `ackText`/`parseReply` kept as documented v1.1 stubs. SPEC §7.4 + the file docstrings updated to match. *PO call: "just log for now."*
- **B3 (major, budget, SPEC §7.3):** muted groups — a **critical/safety keyword still pierces mute** (budget-exempt ALERT); every non-critical hard rule (alert-keyword/teacher-evening/vaad) is now suppressed in a muted group, closing the budget-bypass leak. `hard_rule_alert` gained a mute short-circuit after the critical check. SPEC §7.3 + comments updated. *PO call: criticals pierce mute.*
- **B4 (major, privacy, SPEC §8.6/§8.7):** reconciled the "DeepSeek only" vs Anthropic-fallback contradiction **provider-agnostically** — the guarantee is the minimal payload (one msg + ≤3 context; finance = description+amount), identical for whichever single provider is configured. **No code change** to `lib/llm.py` (already provider-symmetric). §12.2 phrasing aligned. *PO call: every provider treated like DeepSeek (divergence from the brief's "gate" recommendation, approved).*
- **B5 (major, M6):** finance gap-fill now **chunk-loops** over `GAPFILL_MAX_BATCH`, so a >80-txn first import (45-day backlog) is fully categorized before the write — previously the overflow was written blank with real Txn-IDs and excluded from dedup forever (permanent loss). The per-chunk reply budget is **sized to the chunk** (`len(batch)*24`), not a fixed 600 that truncated a full chunk's JSON to nothing (caught in adversarial verification).
- **B7 (major, M6):** `deploy.sh` now runs `npm ci --omit=dev` in `automation/finance` (was bridge-only) and restored `--frozen` on the pytest line — unblocks M6.2.
- **B2 (major):** the candle-lighting digest line fires on **erev-chag** (yom-tov eve), not only Fridays — new `hebcal_client.chag_candles()` reads the calendar endpoint's candles/havdalah items; `_hebcal_line` picks Shabbat ("צאת שבת") vs chag ("צאת החג"). Degrade-quiet preserved.
- **B6 (major, ENGINEERING §8 / SPEC §8.3):** the weekly briefing now carries the **system self-report line** (`N/N runs green · M classified · K tombstone skips (max age Xh) · ₪Y LLM spend`), with `_system_flags` warnings replacing it. Added the additive `tombstone_max_age_h` column to `reminders_log.csv` (makes §8.3 "max age seen" real) and indicative LLM ₪ pricing constants in config. New `## System` section; all four metrics share the trailing-7-day window.
- **B8 (major, SPEC §7.6 / DESIGN §6):** dashboard offline queue **caps at 50** with a one-shot loss warning (he+en), re-armed after a flush.

## Canon touched
SPEC §7.3, §7.4, §8.6, §8.7, §12.2; ENGINEERING §8 (already matched); DESIGN §9 smoke checklist; BACKLOG (fix-lane status + reply-parsing entry).

## Ride-along (pre-existing uncommitted WIP, PO-approved for this commit)
SPEC §12.2 M6.3 wording; `config.example.js` finance-tab rename; two id-less-collision tests in `test_finance.py`; new `deploy/FINANCE.md` runbook.

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

The dashboard stamps `WriteQueue_Tombstone` (ISO-T datetime) on every write; queued offline writes re-stamp it **at flush time**, so the cell always carries the moment the write *landed* on the Sheet. The engine skips a row while `tombstone + 6h > now()` (one clock: the window starts at flush, not at the tap). *(Date-only tombstones had silently disabled this guard — the hour resolution is load-bearing.)* Residual accepted race: a phone that flushes a queued tap inside the same minute the engine reads → at most one duplicate alert; the flush itself is idempotent. Every skip is logged with the tombstone age, and the weekly briefing reports "N tombstone skips · max age seen" — widen the window from data, not anecdote.

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
| **Source** | The online portals of Mizrahi-Tefahot + Max + Cal, read via `israeli-bank-scrapers` (Puppeteer/headless-Linux, pinned 6.7.3, Node ≥ 22.12). No public API; the library drives each portal's web session. **Read-only by nature** — it fetches balances + transactions and cannot move money. |
| **Mechanism** | A systemd timer runs `automation/finance/scrape.js`: logs into each provider with creds from `/etc/family-inc/bank_creds.json`, fetches balances + the transaction window (since last success, with a few-days overlap), writes one CSV per provider to `/var/lib/family-inc/finance/`. `automation/finance_ingest.py` then normalizes, dedups on `Txn-ID`, and writes via `lib/sheet`. Node scrapes; **Python owns every Sheet write.** The local CSV is the only staging — no Drive. Same-day reruns overwrite the day's CSV and dedup on ingest → idempotent; the import advance gates on a successful Sheet write. **Categorization:** an on-box keyword→category rules engine tags each transaction at ingest; the configured LLM provider assigns categories the rules miss (description + amount on the rules-miss remainder only — §8.6). |
| **Runtime** | One systemd timer (`family-finance.timer`), **~06:00 daily** — before the 07:25 engine read, so fresh balances feed the digest and briefing and the >35d staleness stays accurate. Headless Puppeteer (no Xvfb — the anti-bot is clean for this mix). Cadence is the first tuning knob: if Max/Cal OTP challenges prove noisy, drop the cards to 2–3×/week and keep the bank daily. |
| **Auth model** | Read-only portal logins live at `/etc/family-inc/bank_creds.json` (mode 600, never in the repo, never logged). This is the one place the "no credential storage" non-goal is narrowed — *appliance-local, read-only financial logins* — while "no money movement" stays absolute (the scrapers cannot transfer). **2FA:** the scraper logs in fresh each run; an OTP re-challenge **fails loud** (next digest), and the operator re-runs interactively. Persisting a login session to cut repeat OTPs is a later hardening, taken only if the cards prove noisy. |
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

**✅ Audit fix lane — Brief 1 (blocker + 7 majors), landed 2026-06-18** (from the 2026-06-18 full-project audit in `reviews/`): bridge 1:1 chats are now **log-only, no ack** (B1, SPEC §7.4); the candle-lighting line fires on **erev-chag** too (B2); **criticals pierce mute** while non-critical rules are suppressed in muted groups, closing the budget-bypass (B3, SPEC §7.3); LLM privacy reconciled **provider-agnostic** (B4, SPEC §8.6/§8.7); finance gap-fill **chunk-loops** so a large first import is fully categorized (B5, M6); `deploy.sh` installs the **finance Node deps** + restores `--frozen` (B7, M6 — unblocks M6.2); the weekly briefing carries the **ENGINEERING §8 self-report line** (B6); the dashboard offline queue **caps at 50 with a one-shot warning** (B8). Tests green (350). **Brief 2** (10 gaps + minors + disputed) remains open. The fix touched privacy/delivery/budget → the `review.py` gate runs at commit.

## Shipped

- **Keystone loop** — reminders engine (07:25) → daily digest (07:30) → WhatsApp, with dashboard write-back, the outbox budget chokepoint, quiet hours, and the offline-write tombstone guard.
- **Weekly briefing** (Sat 21:00) — deterministic template, Hebcal lines, the system self-report, and a classifier-accuracy section.
- **WhatsApp summarizer** — 5 hard rules + DeepSeek (with keyless keyword fallback), per-group routing, critical-keyword bypass.
- **Daily digest is partner-symmetric** — both adults briefed every day; the empty-handed adult gets the quiet-day line + shared sections, budget-free.
- **Property tracker** — saved-search scrape (headed Chromium under Xvfb) + Apify secondary (backup + gap-fill, primary always wins), silent `Property-Listings` landing + morning digest section.
- **Delivery hardening** — email (SMTP) fallback when the bridge is silent >24h, fail-flag → next-digest reporting, transport logging; email days count as degraded, not green.
- **Go-live + publication** — VPS provisioned, Baileys paired (7.x/ESM), GitHub Pages + PWA pinned to both phones, repo history rewritten clean and made public.
- **Classifier-accuracy surface** — `accuracy_review.py` re-derives each ALERT's rule from persisted Inbox fields (no schema change); a compact pulse folds into the weekly briefing.

## In progress — M6 finance ingestion

Banks + cards, categorized + trends, delivered silently. Read-only logins permitted on the appliance; "no money movement" unchanged. Full contract: `SPEC.md` §12.2.

- ✅ **M6.1 — repo port + schema (hermetic, no appliance).** `automation/finance/scrape.js` (read-only login → CSV) + `finance_ingest.py` (CSV → normalize → Txn-ID dedup → `lib/sheet`: append `Finance-Transactions`, upsert `Finance-Accounts`). Finance tabs standardized to `Finance-Budget`/`Finance-Accounts`/`Finance-Transactions`; `Category`/`Cat-Source` ship present-but-blank (the budget `SUMIFS` keys on the Category column position). `family-finance.{service,timer}` + provision wiring. Tests green; no live bank contact.
- ⬜ **M6.2 — appliance deploy + first interactive auth (the "VPS hour").** Place `bank_creds.json` (mode 600); rename the 3 live-Sheet tabs to the full names; Mizrahi first → verify CSV→Sheet roundtrip live → Max + Cal (interactive OTP once each); enable the timer.
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

Boundary rules (CI greps enforce the first): scripts never define a utility that belongs in `lib/` (no redefining `to_date`/`fmt_money`). Nothing outside `bridge/` and `finance/` touches a third-party site. Nothing outside `lib/sheet.py` constructs a gspread client. Nothing outside `lib/llm.py` imports an LLM SDK. Nothing outside `lib/outbox.py` reaches a human.

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

=== File: DESIGN.md ===
# Family Inc. — Design Specification

*The product has two surfaces: WhatsApp messages and the dashboard PWA. Both are designed here. v3.0 · 2026-06-17. The single offline model is queue + tombstone everywhere.*

---

## 1. Design principles

1. **Calm tech.** The system reports what happened and what's next; it never scolds, streaks, paces, or counts what you missed. Quiet days are a success state, not an empty state.
2. **The message is the product.** Most days the family touches Family Inc. only through WhatsApp. Message copy gets the same design rigor as pixels.
3. **Dense, then disclosed.** Today shows every domain at a glance; detail hides behind one tap. Linear/Notion density, not wellness-app whitespace.
4. **Partner-symmetric surfaces.** Attribution without scoring: domain leads, names follow. No passive "recently completed" surface either — even a neutral one risks reading as a scoreboard between partners.
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

- **Progress arc** (fixed 56px strip): ring + "N completed · last 7 days" + seven weekday ticks (✓/·). A rolling count, never a streak; never shows a target or deficit. Tap → per-domain mini-arcs.
- **Status banner**: one line — red if any overdue, amber if any fire-today, sage "all clear" otherwise.
- **Reminder row**: flag dot · title · due phrase; tap reveals `✓ done` `+Nd` `note` pills. Snooze pills: 1/3/7/14/30.
- **Domain drawers** (Money/Health/Goals/Car/Contracts): closed = one big KPI + sparkline; open = detail list.
- **Bright-line goal viz**: target line + actual line + safety band (ahead/on-pace/behind) for multi-year goals — progress bars are banned for anything >90 days.
- **Connection pill**: 🟢 live / ⛔ offline — N queued. The only place sync state appears.
- **Sticky status pill** (top): one-liner like "Weekly briefing ready · 2 alerts" — our budget-friendly stand-in for OS-level notifications.

## 3. Information architecture (Today-first)

```
Today (home)
├── Header: Family inc. · date · sticky status pill · connection pill
├── Progress arc strip
├── Banner (overdue / today / all-clear)
├── TODAY — reminders where Auto-flag ∈ {OVERDUE, FIRE TODAY}
├── CALENDAR — today's Calendar-Events
├── NEXT 7 DAYS — week-out reminders + events
└── ▸ Drawers: Money · Health · Goals · Car · Contracts
Briefing tab — latest weekly briefing rendered
Settings tab — sign-in · Sheet ID · language toggle · demo toggle · queue inspector
```

Today-first wins the 8 AM glance; tiles demote to drawers; the briefing gets a tab, not the home.

## 4. States

- **Loading**: skeleton shell <50ms with cached-snapshot shapes (counts from cache, else 3/2/3/4 rows); shimmer 1.6s; header/pills/tabs are real from t=0; cached values replace skeletons, live values cross-fade 120ms. Skeletons never shimmer while offline — static gray is more honest.
- **Quiet day**: the arc keeps its ticks, the banner shows sage "all clear", TODAY renders "(nothing urgent)". The screen is never blank.
- **Offline**: the pill flips to "⛔ offline — N queued"; rows keep working; a queued row shows "⏳ queued — will sync on reconnect". **Buttons never disable offline.**
- **Write failure (online)**: optimistic UI rolls back; inline "Couldn't save — retry?"; token expiry → silent refresh once, then a re-sign-in banner.
- **Back from vacation (30 overdue)**: top 10 by due date + "+20 more" expander; the banner offers bulk-done multi-select; the arc shows the honest low count with zero commentary.

## 5. Interaction contract (write-back)

Every tap maps to one batched Sheet write per SPEC §6.1 (intent columns + `DoneAt`/`LastDoneBy` on completion + `WriteQueue_Tombstone` always):

| Action | Writes | UI |
|---|---|---|
| ✓ done | Status=Done, DoneAt, LastDoneBy, Tombstone (+ recurrence bump) | row clears from its list |
| +Nd | Due+=N, Status=Snoozed, Tombstone (no DoneAt — snooze isn't completion) | row re-sorts |
| note | append to Notes with `[date name]` prefix, Tombstone | inline confirm |

Offline: the same writes queue (`localStorage.pendingWrites[]`, cap 50 with a one-shot loss warning at the cap); flush in tap order on reconnect; idempotent via tombstone (re-stamped at flush time).

## 6. WhatsApp message design system

The most-used UI in the product. Rules:

- **One morning message.** Engine fires, group digest, new-property listings, and the Hebcal line are assembled into a single 07:30 message per recipient — never 2–3 separate sends.
- **Both adults, every day.** Each adult gets their own 07:30 message every day — partner-symmetric. An adult with no reminders of their own still receives the briefing: the quiet-day line `אין תזכורות להיום — יום שקט.` followed by whatever shared groups / property sections exist. A truly empty day is just the head + quiet-day line — never *no* message (silence must stay distinguishable from a broken digest) and never a scold (quiet is a success state).
- **Line economy.** One line per item: flag emoji · title · due phrase. Notes only if ≤120 chars. >5 items → top 5 by priority + "+N more — בלוח" (in the dashboard).
- **Emoji are semantics, not decoration**: 🔴 overdue · 🟠 today · 🟡 week-out · 🟢 month-out · ⚠ needs-a-look · 🕯 Shabbat line · 🏠 new listings. No other emoji in generated copy.
- **No reply affordances** until reply parsing ships. Messages end with content, not instructions. When v1.1 lands, the reply grammar returns as a single footer line.
- **Hebrew copy register**: short, warm, zero exclamation marks, no imperatives toward a person ("לקבוע תור" not "תקבעי תור!"). Dates as "יום ג׳ 17/6". Money as ₪ with a thousands separator.
- **Attribution**: domain first, name inline.

### Templates

Daily digest (the only routine alert-channel message):

```
🏠 Family inc. · יום ו׳ 12/6
🔴 טסט שנתי לרכב — באיחור 3 ימים
🟠 תור שיניים לילד — היום
🟡 ביטוח דירה — בעוד 6 ימים

קבוצות (24ש׳):
גן — מחר יום פרי, להביא 🍐 (גננת, 22:14)
ועד — מעלית מושבתת חמישי 09:00–12:00

🏠 דירות חדשות:
4 חד׳ · ₪2,450,000 · רמת גן

🕯 הדלקת נרות 19:24 · צאת שבת 20:35
```

Quiet day for this adult (no reminders of their own; shared sections still ride along):

```
🏠 Family inc. · יום ג׳ 17/6
אין תזכורות להיום — יום שקט.

קבוצות (24ש׳):
ועד — מעלית מושבתת חמישי 09:00–12:00
```

Critical (budget-bypassing, rare): a single line, no frame — `⚠ {group}: {one_liner} ({sender}, {time})`.

Weekly briefing (Sat 21:00): five scenes, vertical, one line each opener — *the week's spend · kids' moment · next week's three things · one goal line · one contract heads-up* — then short sections, then the system self-report and classifier-accuracy lines. Strava-year-in-review meets Morning Brew; the typography is the design. **Rendered from a deterministic template** (no LLM call); that voice is the template's design target.

Bridge-health warning prepends, never replaces: `⚠ הגשר שקט 14 שעות — ייתכן שפספסנו הודעות`.

## 7. i18n rules

- `<html lang="he" dir="rtl">` default; `localStorage.familyinc.lang="en"` flips lang/dir + chrome strings (pre-paint, no flash).
- Logical CSS properties only (`padding-inline-start`); no left/right literals.
- Chrome strings in the parallel STRINGS table; data values (merchants, group names, guide links) render Hebrew regardless of the toggle.
- Dates `DD/MM`, week starts Sunday, `he-IL` number formatting in both languages (the audience is Israeli in either chrome).
- The brand stays Latin "Family inc." everywhere, including the home-screen title.
- WhatsApp messages are Hebrew-only (no toggle exists there; the recipients are known).

## 8. Accessibility & ergonomics

Tap targets ≥44px; contrast AA against both surfaces (the muted zinc fails on dark — use `#A1A1AA` minimum); focus-visible outlines on; a reduced-motion media query kills the shimmer + cross-fades; the PWA `apple-touch-icon` relies on the OS glass treatment, no fake translucency in-app; thumb-zone — action pills render below the row, not above.

## 9. Manual smoke checklist (per dashboard deploy)

1. Cold load <1s on phone over LTE; skeletons → live without layout shift.
2. Hebrew default renders RTL with no mirrored numerals; the toggle flips chrome only.
3. Mark done online → row clears, the Sheet shows M/N/O stamped.
4. Airplane mode → tap done → pill shows queued → reconnect → flush; the engine log shows a tombstone skip if within the window.
5. The demo toggle never touches the live Sheet.
6. Lighthouse PWA installable; an offline reload serves the shell + cached data.
7. Offline, tap until the queue hits 50 → a one-shot "queue full" warning shows; further taps don't grow the queue; reconnect → flush re-arms the warning.
8. (bridge) A 1:1 message to the bridge number from a known sender is logged to `replies.jsonl` but gets **no reply/ack** (reply-parsing is v1.1, SPEC §7.4); an unknown 1:1 sender is dropped.

=== End: DESIGN.md ===

=== File: automation/whatsapp_summarizer.py ===
"""
Family inc. — WhatsApp group summarizer (SPEC.md §7.3: hourly)

Reads normalized group messages (from the self-hosted Baileys bridge at
bridge/state/inbox/whatsapp_inbox.jsonl), classifies each into
ROUTINE / DIGEST / ALERT, applies hard-rule overrides, dispatches ALERTs to
the per-group recipients under the family's 2/day alert budget, and builds the
daily "WhatsApp groups (last 24h)" digest that daily_digest.py folds into the
morning message.

Pipeline:
  inbox JSONL  ->  classify (hard rules -> lib/llm.py Haiku -> deterministic)
              ->  per-group routing -> dispatch ALERTs via lib/outbox.queue()
                  (kind=alert|critical, id=wa-{msg_id}; the outbox ledger is
                  the ONLY budget enforcement — D-015. Over-budget alerts are
                  deferred to tomorrow's digest by the outbox itself.)
              ->  append WhatsApp_Inbox + WhatsApp_Archive tabs via lib/sheet
                  (live Sheet when configured; skipped loudly otherwise), then
                  roll the Inbox tab's 30-day window (SPEC §6.2; Archive keeps
                  text forever — D-044)
              ->  build digest markdown (Hebrew, DESIGN §6)

Sender roles (the §7.3 hard rules 2–3 key off them) are resolved from a roster
(seeds/13_Sender_Roster_Seed.csv, gitignored) when the bridge can't label them
— it only knows a JID and a push-name. See load_roster/resolve_role (D-044).

Config: seeds/12_WhatsApp_Group_Config_Seed.csv (group routing + keywords;
gitignored — group names are personal). List columns are ';'-separated.

Runs in MOCK MODE out-of-the-box (no inbox file, no API key needed): it loads a
sample of Hebrew group messages and prints "RUNNING IN MOCK MODE".

Run:
  python3 automation/whatsapp_summarizer.py [--inbox path.jsonl] [--config path.csv]
                                            [--as-of YYYY-MM-DD] [--dry-run]
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/whatsapp_summarizer.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import csv
import json
import logging
import os
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional

from automation import templates as T
from automation.lib import config as cfg
from automation.lib import llm, sheet
from automation.lib.config import DIGEST_GROUP_LABEL, DIGEST_GROUP_ORDER

INBOX_DEFAULT = cfg.INBOX_FILE
CONFIG_DEFAULT = cfg.WA_GROUP_CONFIG
ROSTER_DEFAULT = cfg.SENDER_ROSTER
BRIEFINGS_DIR = cfg.BRIEFINGS_DIR

log = logging.getLogger("wa")

CLASSES = ("ROUTINE", "DIGEST", "ALERT")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def _split_list(cell: str) -> list[str]:
    return [x.strip() for x in (cell or "").split(";") if x.strip()]

def load_config(path: Path) -> dict[str, dict]:
    """group_name -> config dict. alert_keywords pre-compiled."""
    cfg: dict[str, dict] = {}
    if not path.exists():
        log.warning("config %s missing — every group defaults to digest_only", path)
        return cfg
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("group_name") or "").strip()
            if not name:
                continue
            cfg[name] = {
                "group_type": (row.get("group_type") or "other").strip(),
                "importance_default": (row.get("importance_default") or "digest_only").strip(),
                "alert_recipients": (row.get("alert_recipients") or "none").strip(),
                "close_contacts": _split_list(row.get("close_contacts", "")),
                "alert_keywords": [re.compile(p) for p in _split_list(row.get("alert_keywords", ""))],
                # critical keywords BYPASS the daily budget (tiered budget,
                # applied from Gemini review 2026-06-02): 2 standard alerts/day
                # + unlimited safety alerts
                "critical_keywords": [re.compile(p) for p in _split_list(row.get("critical_keywords", ""))],
            }
    return cfg

def group_cfg(cfg: dict, group_name: str) -> dict:
    return cfg.get(group_name, {
        "group_type": "other", "importance_default": "digest_only",
        "alert_recipients": "none", "close_contacts": [],
        "alert_keywords": [], "critical_keywords": [],
    })

# ---------------------------------------------------------------------------
# Sender → role roster (M4, D-044). The §7.3 hard rules 2–3 fire on sender_role
# (daycare teacher in the evening; vaad_bayit utility), but the Baileys bridge
# can't reliably label a sender's role — it knows a JID and a push-name. The
# roster maps either to a role so the rules trip on real traffic. Personal →
# gitignored seed (seeds/README.md documents the format); absent → empty roster,
# and a message simply keeps whatever role it already carries.
# ---------------------------------------------------------------------------
def load_roster(path: Path) -> dict[str, str]:
    """sender JID OR display name -> role. Blank-role rows are skipped."""
    roster: dict[str, str] = {}
    if not path.exists():
        return roster
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            role = (row.get("role") or "").strip()
            if not role:
                continue
            for key in (row.get("sender_jid"), row.get("sender_name")):
                key = (key or "").strip()
                if key:
                    roster[key] = role
    return roster

def resolve_role(msg: dict, roster: dict[str, str]) -> str:
    """The message's own role wins when it is a real one; otherwise fill it from
    the roster (JID before display name). Messages that already carry an explicit
    role (mock data, tests, a future smarter bridge) are left untouched."""
    have = (msg.get("sender_role") or "").strip()
    if have and have != "unknown":
        return have
    jid = (msg.get("sender_jid") or "").strip()
    name = (msg.get("sender_name") or "").strip()
    return roster.get(jid) or roster.get(name) or have or "unknown"

# ---------------------------------------------------------------------------
# Inbox loading (real JSONL from Baileys, or mock)
# ---------------------------------------------------------------------------
def load_inbox(path: Path) -> tuple[list[dict], bool]:
    """Returns (messages, is_mock).

    Concurrency note (Gemini review 2026-06-02, defended): the Node listener is
    the single writer (atomic line appends); this is the single reader. A torn
    final line mid-append fails json.loads and is skipped THIS run — the next
    run rereads the whole file and picks it up complete (dedup by msg_id keeps
    everything exactly-once). Self-healing; no SQLite needed at ~200 msg/day."""
    if not path.exists():
        log.warning("RUNNING IN MOCK MODE — no inbox at %s; using sample messages", path)
        return MOCK_MESSAGES, True
    msgs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msgs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return msgs, False

# ---------------------------------------------------------------------------
# Mock data — realistic Israeli group traffic spanning all 5 configured groups
# (generic names only — real group names live in the gitignored seed CSV)
# ---------------------------------------------------------------------------
MOCK_MESSAGES = [
    {"msg_id": "m1", "group_name": "גן עידן הורים תשפ\"ז", "sender_name": "הילה הגננת",
     "sender_role": "teacher", "received_at": "2026-06-01T22:14:00",
     "text": "היי הורים יקרים, מחר יום פירות בגן - נא להביא פרי חתוך 🍎", "has_media": False},
    {"msg_id": "m2", "group_name": "גן עידן הורים תשפ\"ז", "sender_name": "אמא של נועה",
     "sender_role": "parent_distant", "received_at": "2026-06-01T22:40:00",
     "text": "מישהו יודע אם יש גן מחר או שזה יום בחירות?", "has_media": False},
    {"msg_id": "m3", "group_name": "גן עידן הורים תשפ\"ז", "sender_name": "הילה הגננת",
     "sender_role": "teacher", "received_at": "2026-06-02T14:02:00",
     "text": "מסיבת סוף שנה ביום שישי מתחילים ב16:00, הורים מוזמנים", "has_media": False},
    {"msg_id": "m4", "group_name": "ועד הבית - הרצל 12", "sender_name": "דני ועד",
     "sender_role": "vaad_bayit", "received_at": "2026-06-02T11:30:00",
     "text": "תיקון מעלית ביום חמישי 09:00-12:00, המעלית מושבתת בשעות אלו", "has_media": False},
    {"msg_id": "m5", "group_name": "ועד הבית - הרצל 12", "sender_name": "שכן קומה 2",
     "sender_role": "unknown", "received_at": "2026-06-02T07:10:00",
     "text": "בוקר טוב, מישהו ראה את החתול שלי?", "has_media": False},
    {"msg_id": "m6", "group_name": "משפחה ❤", "sender_name": "אמא",
     "sender_role": "family", "received_at": "2026-06-01T19:30:00",
     "text": "", "has_media": True},  # photos, no caption -> ROUTINE
    {"msg_id": "m7", "group_name": "משפחה ❤", "sender_name": "ליאורה",
     "sender_role": "family", "received_at": "2026-06-01T19:45:00",
     "text": "שמרו את התאריך - בר מצווה של יונתן ב-14 ביוני!", "has_media": False},
    {"msg_id": "m8", "group_name": "שכונה שלנו", "sender_name": "עידן",
     "sender_role": "unknown", "received_at": "2026-06-01T20:11:00",
     "text": "מחפשים המלצה על בייביסיטר באזור, תודה", "has_media": False},
    {"msg_id": "m9", "group_name": "סטודנטים - הקורס", "sender_name": "מתרגל הקורס",
     "sender_role": "unknown", "received_at": "2026-06-02T07:45:00",
     "text": "תזכורת: הגשת תרגיל 4 מחר בחצות, דדליין קשיח", "has_media": False},
    {"msg_id": "m10", "group_name": "סטודנטים - הקורס", "sender_name": "סטודנט",
     "sender_role": "unknown", "received_at": "2026-06-01T23:50:00",
     "text": "מישהו הבין את שאלה 3?", "has_media": False},
    # arrives AFTER the daily budget is exhausted — must still fire (critical tier)
    {"msg_id": "m11", "group_name": "גן עידן הורים תשפ\"ז", "sender_name": "הילה הגננת",
     "sender_role": "teacher", "received_at": "2026-06-02T15:00:00",
     "text": "חירום: הגן סגור מחר עקב תקלת מים, עדכון בהמשך", "has_media": False},
]

# ---------------------------------------------------------------------------
# Classification — hard rules first, then LLM, then deterministic fallback
# ---------------------------------------------------------------------------
VAAD_UTILITY_RE = re.compile(r"מים|חשמל|תיקון|מעלית")
ACTIONY_RE = re.compile(r"מחר|להביא|צריך|תזכורת|דדליין|הגשה|מסיבה|שמרו את התאריך|save the date", re.IGNORECASE)

def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s.replace("Z", "").split("+")[0])
    except (ValueError, AttributeError):
        log.warning("_parse_dt: could not parse %r — falling back to datetime.now()", s)
        return datetime.now()

def _in_evening(dt: datetime) -> bool:
    """18:00–08:00 window (teacher 'tomorrow bring X' tends to land here)."""
    return dt.time() >= time(18, 0) or dt.time() < time(8, 0)

def hard_rule_alert(msg: dict, cfg: dict) -> tuple[Optional[str], bool]:
    """Return (reason, is_critical) if a hard rule forces ALERT, else (None, False).
    Critical matches bypass the daily alert budget (tiered budget)."""
    c = group_cfg(cfg, msg["group_name"])
    text = msg.get("text", "") or ""
    role = msg.get("sender_role", "unknown")
    gtype = c["group_type"]
    when = _parse_dt(msg.get("received_at", ""))

    # Rule 0 — critical/safety keywords: budget-exempt, and they PIERCE a mute.
    # A critical match is the ONE signal a muted group still surfaces (SPEC §7.3).
    for pat in c["critical_keywords"]:
        if pat.search(text):
            return f"CRITICAL keyword /{pat.pattern}/", True
    # Mute is otherwise a hard rule: below the critical tier a muted group raises
    # NO alert (no alert-keyword / teacher-evening / vaad ALERT, no budget spend).
    # This is what closes the "muted group still fires (and bypasses budget)" leak
    # while honoring the PO call that criticals pierce mute (B3, SPEC §7.3).
    if c["importance_default"] == "mute":
        return None, False
    # Rule 1 — any alert_keyword regex match
    for pat in c["alert_keywords"]:
        if pat.search(text):
            return f"keyword match /{pat.pattern}/", False
    # Rule 2 — daycare teacher in the evening window
    if role == "teacher" and gtype == "daycare" and _in_evening(when):
        return "daycare teacher, evening window", False
    # Rule 3 — vaad bayit utility/maintenance terms
    if role == "vaad_bayit" and VAAD_UTILITY_RE.search(text):
        return "vaad bayit utility/maintenance", False
    return None, False

def _one_liner_fallback(text: str) -> str:
    t = re.sub(r"\s+", " ", text.strip())
    return t[:117] + "…" if len(t) > 120 else t

def _first_json_obj(raw: str) -> tuple[Optional[dict], bool]:
    """First JSON object in an LLM reply, tolerating ```fences``` and surrounding
    prose. DeepSeek occasionally wraps the object in commentary; a plain
    json.loads then raises 'Extra data' and we'd needlessly drop to the keyword
    fallback (observed live 2026-06-17, D-046). raw_decode reads just the first
    object and ignores the rest. Returns (obj, had_prose) — had_prose flags
    leading/trailing non-JSON so the caller can surface a json_mode regression
    instead of letting the safety net swallow it (review D-047). (None, False)
    when there is no JSON object."""
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start = s.find("{")
    if start == -1:
        return None, False
    try:
        obj, end = json.JSONDecoder().raw_decode(s[start:])
    except ValueError:
        return None, False
    if not isinstance(obj, dict):
        return None, False
    had_prose = start > 0 or bool(s[start + end:].strip())
    return obj, had_prose

def llm_classify(msg: dict, cfg: dict, recent: list[dict]) -> Optional[dict]:
    """LLM classification via lib/llm.py (the one provider wrapper — DeepSeek by
    default, Anthropic fallback). None if unavailable or unparseable (caller
    falls back). Sends one message + ≤3 context messages, never whole threads
    (SPEC §8.6)."""
    c = group_cfg(cfg, msg["group_name"])
    is_close = msg.get("sender_name", "") in c["close_contacts"] or \
        msg.get("sender_jid", "") in c["close_contacts"]
    context = "\n".join(f"- {m.get('sender_name','?')}: {m.get('text','')}" for m in recent[-3:])
    prompt = (
        "You triage WhatsApp group messages for a busy Israeli family (Adar + Shanee, "
        "two young kids). Decide if a message is ROUTINE (no action, skip), "
        "DIGEST (worth a one-line mention in the morning summary), or ALERT "
        "(time-sensitive, someone must act soon).\n"
        f"Group type: {c['group_type']}. Group default importance: {c['importance_default']}. "
        f"Sender is a close contact: {is_close}.\n"
        f"Recent context:\n{context or '(none)'}\n\n"
        f"Message from {msg.get('sender_name','?')}: {msg.get('text','')}\n\n"
        "Reply with ONLY a JSON object: "
        '{"classification":"ROUTINE|DIGEST|ALERT","one_liner":"<=120 char Hebrew or English summary",'
        '"action_required":true|false,"reason":"short"}'
    )
    raw = llm.complete(prompt, task="classify", max_tokens=200,
                       source="whatsapp_summarizer", json_mode=True)
    if raw is None:
        return None
    data, had_prose = _first_json_obj(raw)
    if data is None:
        log.warning("classify reply not JSON-parseable — deterministic fallback")
        return None
    if had_prose:
        # json_mode (D-046) asks DeepSeek for a bare object; surrounding prose
        # means the provider ignored response_format. We recovered via raw_decode,
        # but surface it so a silent json_mode regression stays visible (D-047).
        log.warning("classify: json_mode reply carried prose around the JSON "
                    "(recovered) — response_format may not be honored")
    if data.get("classification") not in CLASSES:
        return None
    return data

def deterministic_classify(msg: dict, cfg: dict) -> dict:
    """No-LLM fallback. Conservative: never invents an ALERT (hard rules do that)."""
    c = group_cfg(cfg, msg["group_name"])
    text = msg.get("text", "") or ""
    if c["importance_default"] == "mute":
        return {"classification": "ROUTINE", "one_liner": "", "action_required": False,
                "reason": "muted group"}
    if ACTIONY_RE.search(text):
        return {"classification": "DIGEST", "one_liner": _one_liner_fallback(text),
                "action_required": True, "reason": "action keyword"}
    if "?" in text:
        return {"classification": "DIGEST", "one_liner": _one_liner_fallback(text),
                "action_required": False, "reason": "question"}
    return {"classification": "ROUTINE", "one_liner": "", "action_required": False,
            "reason": "no signal"}

def classify(msg: dict, cfg: dict, recent: list[dict], use_llm: bool) -> dict:
    c = group_cfg(cfg, msg["group_name"])
    text = msg.get("text", "") or ""

    # Rule 4 — media-only, no caption -> ROUTINE, no LLM call
    if msg.get("has_media") and not text:
        return {"classification": "ROUTINE", "one_liner": "shared media",
                "action_required": False, "reason": "media-only", "rule": "media-only"}

    # Hard ALERT rules (override LLM)
    reason, critical = hard_rule_alert(msg, cfg)
    if reason:
        result = (llm_classify(msg, cfg, recent) if use_llm else None) \
            or deterministic_classify(msg, cfg)
        result["classification"] = "ALERT"
        result["action_required"] = True
        result["critical"] = critical
        if not result.get("one_liner"):
            result["one_liner"] = _one_liner_fallback(text)
        result["reason"] = f"hard rule: {reason}"
        result["rule"] = reason
        return result

    # Rule 5 — non-critical path. A muted group only reaches here for non-critical
    # messages (a critical keyword already returned an ALERT above, piercing the
    # mute); deterministic_classify then yields ROUTINE for the muted group, so no
    # non-critical alert escapes a mute (SPEC §7.3).
    result = (llm_classify(msg, cfg, recent) if use_llm else None) \
        or deterministic_classify(msg, cfg)
    # digest_only groups can't auto-escalate to ALERT without a hard rule
    if c["importance_default"] == "digest_only" and result["classification"] == "ALERT":
        result["classification"] = "DIGEST"
        result["reason"] = (result.get("reason", "") + "; downgraded (digest_only group)").strip("; ")
    if result["classification"] in ("DIGEST", "ALERT") and not result.get("one_liner"):
        result["one_liner"] = _one_liner_fallback(text)
    result.setdefault("rule", "")
    result.setdefault("critical", False)
    return result

# ---------------------------------------------------------------------------
# Per-group routing + alert dispatch (budget enforced ONLY by the outbox
# ledger — D-015; this script keeps no counter of its own)
# ---------------------------------------------------------------------------
def owner_from_recipients(recipients: str) -> str:
    return {"both": "both", "adar": "adar", "shanee": "shanee"}.get(recipients, "none")


def alert_body(msg: dict, one_liner: str, group_type: str, critical: bool) -> str:
    """DESIGN §6 single-line shape: Hebrew type label, sender, HH:MM."""
    tpl = T.CRITICAL_LINE if critical else T.ALERT_LINE
    return tpl.format(
        group=DIGEST_GROUP_LABEL.get(group_type, msg["group_name"]),
        one_liner=one_liner,
        sender=msg.get("sender_name", "?"),
        time=f"{_parse_dt(msg.get('received_at', '')):%H:%M}",
    )


def dispatch_alert(msg: dict, one_liner: str, recipients: str, group_type: str,
                   dry_run: bool, critical: bool = False) -> bool:
    """Queue toward the phones via lib/outbox.queue() (D-010: Baileys-first).
    kind=critical bypasses budget + quiet hours; kind=alert is subject to the
    shared 2/day ledger — over-budget targets are deferred by the OUTBOX into
    tomorrow's digest (SPEC §7.5), not downgraded here. Stable id wa-{msg_id}
    keeps reruns idempotent. Returns True if at least one target was queued."""
    tag = "CRITICAL " if critical else ""
    line = f"[{tag}ALERT → {recipients}] {msg['group_name']}: {one_liner}"
    print("  " + line)
    if dry_run:
        return False
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    log_path = BRIEFINGS_DIR / f"whatsapp_alerts_{date.today().isoformat()}.md"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"- {datetime.now():%H:%M} {line}\n")
    from automation.lib.outbox import bridge_alive, queue
    to = recipients if recipients in ("adar", "shanee", "both") else "both"
    res = queue(to, alert_body(msg, one_liner, group_type, critical),
                "critical" if critical else "alert",
                source="whatsapp_summarizer", msg_id=f"wa-{msg.get('msg_id', '')}")
    if res.deferred:
        print(f"  (budget: deferred to tomorrow's digest for {res.deferred})")
    if res.queued and not bridge_alive():
        print("  [warn] bridge heartbeat stale — alert queued, delivery waits for reconnect")
    return bool(res.queued)

# ---------------------------------------------------------------------------
# Persistence — WhatsApp_Inbox + WhatsApp_Archive tabs of the master Sheet
# (lib/sheet.py; the CSV staging buffer is gone since M2). Without a live
# backend (mock/dev) appends are skipped loudly — never written to the seed
# template. The Inbox tab's 30-day rolloff (SPEC §6.2) runs in run() after a
# successful append (sheet.roll_off_old_rows; D-044) — Archive is never rolled.
# ---------------------------------------------------------------------------
INBOX_COLS = sheet.WA_INBOX_COLUMNS
ARCHIVE_COLS = sheet.WA_ARCHIVE_COLUMNS


def _processed_ids(sheet_path: Optional[Path] = None) -> set[str]:
    """msg_ids already written to the WhatsApp_Inbox tab, so reruns don't
    double-process (exactly-once together with the outbox wa-{msg_id} dedup)."""
    return {str(v).strip()
            for v in sheet.read_column(cfg.WA_INBOX_SHEET_TAB, "msg_id", sheet_path)}


def persist_rows(processed: list[dict], sheet_path: Optional[Path] = None,
                 live_override: Optional[bool] = None) -> bool:
    """Append this run's rows to the Inbox (full row) + Archive (text-forever
    subset) tabs in two batched calls. Returns False when skipped (no live
    backend and no explicit path)."""
    live = sheet.is_live() if live_override is None else live_override
    if sheet_path is None and not live:
        print("(no live Sheet backend — Inbox/Archive rows NOT appended)")
        return False
    sheet.append_rows(cfg.WA_INBOX_SHEET_TAB, INBOX_COLS, processed, sheet_path)
    sheet.append_rows(cfg.WA_ARCHIVE_SHEET_TAB, ARCHIVE_COLS, processed, sheet_path)
    return True

# ---------------------------------------------------------------------------
# Bridge health (applied from Gemini review 2026-06-02)
# ---------------------------------------------------------------------------
BRIDGE_STALE_HOURS = cfg.BRIDGE_STALE_HOURS  # group silence this long is suspect

def bridge_staleness_warning(inbox_path: Path) -> Optional[str]:
    """The Baileys listener writes inbox/heartbeat.txt on connect, every message,
    and every 15 min while connected (the timer stops on disconnect). If the
    heartbeat goes stale the bridge is down — surface it instead of failing silent."""
    hb = inbox_path.parent / "heartbeat.txt"
    ref = hb if hb.exists() else (inbox_path if inbox_path.exists() else None)
    if ref is None:
        return None  # mock mode / bridge never started — nothing to judge
    age_h = (datetime.now() - datetime.fromtimestamp(ref.stat().st_mtime)).total_seconds() / 3600
    if age_h > BRIDGE_STALE_HOURS:
        return T.BRIDGE_SILENT.format(hours=age_h)
    return None

# ---------------------------------------------------------------------------
# Digest builder — the קבוצות section of the morning message (DESIGN §6:
# flat list, Hebrew type label inline, ordered by group type then time;
# warnings prepend, never replace; counts live in console/logs, not copy)
# ---------------------------------------------------------------------------
def build_digest(processed: list[dict], today: date, warning: Optional[str] = None) -> str:
    window_start = datetime.combine(today, time.min) - timedelta(hours=24)
    shown = [p for p in processed
             if p["classification"] in ("DIGEST", "ALERT")
             and _parse_dt(p["received_at"]) >= window_start]

    lines = []
    if warning:
        lines += [warning, ""]
    # ALERTs with nobody to route to (digest_only groups) float to the top
    floated = [p for p in shown if p["classification"] == "ALERT" and p["action_owner"] == "none"]
    if floated:
        lines.append(T.WA_NEEDS_A_LOOK)
        for p in floated:
            lines.append(T.WA_NEEDS_A_LOOK_ITEM.format(
                one_liner=p["one_liner"], sender=p["sender_name"],
                time=f"{_parse_dt(p['received_at']):%H:%M}"))
        lines.append("")
    body = [p for p in shown if p not in floated]
    if body:
        lines.append(T.WA_SECTION_HEAD)
        order = {g: i for i, g in enumerate(DIGEST_GROUP_ORDER)}
        body.sort(key=lambda p: (order.get(p["group_type"], len(order)),
                                 _parse_dt(p["received_at"])))
        for p in body:
            lines.append(T.WA_ITEM.format(
                group=DIGEST_GROUP_LABEL.get(p["group_type"], p["group_type"]),
                one_liner=p["one_liner"], sender=p["sender_name"],
                time=f"{_parse_dt(p['received_at']):%H:%M}"))
    return "\n".join(lines).rstrip() + ("\n" if lines else "")

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run(inbox_path: Path, config_path: Path, today: date, dry_run: bool,
        sheet_path: Optional[Path] = None, roster_path: Optional[Path] = None) -> Path:
    cfg_groups = load_config(config_path)
    roster = load_roster(roster_path or ROSTER_DEFAULT)
    messages, is_mock = load_inbox(inbox_path)
    use_llm = llm.available()
    if not use_llm:
        print("(no LLM provider key — using deterministic classifier; hard rules still fire)")

    # process in chronological order so 'recent context' is correct
    messages = sorted(messages, key=lambda m: _parse_dt(m.get("received_at", "")))

    # skip messages already in the Inbox tab (avoids re-alerting on rerun)
    already = _processed_ids(sheet_path) if (sheet_path or sheet.is_live()) else set()
    if already:
        before = len(messages)
        messages = [m for m in messages if m.get("msg_id") not in already]
        if before != len(messages):
            print(f"(skipping {before - len(messages)} already-processed messages)")

    seen_by_group: dict[str, list[dict]] = {}
    processed: list[dict] = []
    alerts_queued = 0

    for msg in messages:
        msg["sender_role"] = resolve_role(msg, roster)  # roster fills what the bridge can't
        gname = msg["group_name"]
        c = group_cfg(cfg_groups, gname)
        recent = seen_by_group.get(gname, [])
        result = classify(msg, cfg_groups, recent, use_llm)
        seen_by_group.setdefault(gname, []).append(msg)

        recipients = c["alert_recipients"]
        dispatched = False
        dispatched_at = ""
        action_owner = "none"
        critical = result.get("critical", False)
        if result["classification"] == "ALERT":
            if recipients == "none":
                action_owner = "none"  # float to digest "needs a look"
            else:
                action_owner = owner_from_recipients(recipients)
                # The outbox is the only budget authority (D-015): in-budget →
                # queued now; over-budget → it defers the body to tomorrow's
                # digest and logs alert_suppressed_by_budget. Either way the
                # row stays classified ALERT here — what happened to it is the
                # outbox ledger's record, not a reclassification.
                dispatched = dispatch_alert(msg, result["one_liner"], recipients,
                                            c["group_type"], dry_run, critical=critical)
                if dispatched:
                    alerts_queued += 1
                    dispatched_at = datetime.combine(
                        today, datetime.now().time()).isoformat(timespec="seconds")

        row = {
            "msg_id": msg.get("msg_id", ""), "group_name": gname,
            "group_type": c["group_type"], "sender_name": msg.get("sender_name", ""),
            "sender_role": msg.get("sender_role", "unknown"),
            "received_at": msg.get("received_at", ""), "text": msg.get("text", ""),
            "has_media": msg.get("has_media", False),
            "classification": result["classification"], "one_liner": result.get("one_liner", ""),
            "action_required": result.get("action_required", False),
            "action_owner": action_owner, "critical": critical,
            "dispatched": dispatched,
            "dispatched_at": dispatched_at, "digested_at": "",
        }
        processed.append(row)

    # console summary (budget state lives in the outbox ledger, logs/outbox_ledger/)
    print(f"\nProcessed {len(processed)} messages "
          f"({'MOCK' if is_mock else 'live'}) · alerts queued this run: {alerts_queued}")
    counts = {k: sum(1 for p in processed if p["classification"] == k) for k in CLASSES}
    print(f"  ROUTINE={counts['ROUTINE']} DIGEST={counts['DIGEST']} ALERT={counts['ALERT']}")

    # build + write digest (with bridge-health warning if the listener is silent)
    warning = bridge_staleness_warning(inbox_path)
    if warning:
        log.warning(warning)
    digest = build_digest(processed, today, warning)
    print("\n" + digest)
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    digest_path = BRIEFINGS_DIR / f"whatsapp_digest_{today.isoformat()}.md"
    if not dry_run:
        digest_path.write_text(digest, encoding="utf-8")
        for p in processed:
            if p["classification"] in ("DIGEST", "ALERT"):
                p["digested_at"] = datetime.now().isoformat(timespec="seconds")
        if persist_rows(processed, sheet_path):
            print(f"appended {len(processed)} row(s) to "
                  f"{cfg.WA_INBOX_SHEET_TAB} + {cfg.WA_ARCHIVE_SHEET_TAB}")
            # 30-day hot-tab rolloff (SPEC §6.2) — only after a real append, so
            # the seed is never touched; Archive keeps text forever.
            cutoff = today - timedelta(days=cfg.WA_INBOX_RETENTION_DAYS)
            rolled = sheet.roll_off_old_rows(
                cfg.WA_INBOX_SHEET_TAB, "received_at", cutoff, sheet_path)
            if rolled:
                print(f"rolled off {rolled} {cfg.WA_INBOX_SHEET_TAB} row(s) "
                      f"older than {cutoff} ({cfg.WA_INBOX_RETENTION_DAYS}d)")
        print(f"wrote {digest_path}")
    else:
        print("(dry-run — no files written)")
    return digest_path

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", help="path to whatsapp_inbox.jsonl from the Baileys bridge")
    ap.add_argument("--config", help="path to WhatsApp_Group_Config CSV")
    ap.add_argument("--as-of", help="YYYY-MM-DD, defaults to today")
    ap.add_argument("--dry-run", action="store_true", help="classify + print, write nothing")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(Path(args.inbox) if args.inbox else INBOX_DEFAULT,
        Path(args.config) if args.config else CONFIG_DEFAULT,
        today, args.dry_run)

if __name__ == "__main__":
    main()

=== End: automation/whatsapp_summarizer.py ===

=== File: automation/lib/categorize.py ===
"""
Family inc. — finance categorization (SPEC §12.2 / §8.6, M6.4; D-050/051).

Two stages, both degrade-quiet (§3.6):

  1. On-box rules engine — seeds/14_Finance_Category_Rules.csv maps a keyword
     (case-insensitive SUBSTRING, Hebrew or English) to a category. Applied to
     EVERY transaction; first match wins (rows are ordered specific→general).
     Most transactions are tagged here and never leave the box.

  2. DeepSeek gap-fill (lib/llm) — ONLY the rules-miss remainder, and ONLY each
     transaction's DESCRIPTION + AMOUNT (never the account, balance, Txn-ID,
     identifier, or the whole ledger — §8.6). The model must answer with a
     category from the rules file's own vocabulary or "UNKNOWN"; anything else
     leaves the transaction blank.

Cat-Source: "rules" | "llm" | "" (blank = uncategorized — the budget SUMIFS
just won't bucket it, and a human can fill it later). Nothing here raises into
the ingest: a missing rules file, a missing key, an LLM error, or an off-vocab
answer all collapse to "leave it blank".
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from automation.lib import config

log = logging.getLogger("finance.categorize")

# Per-prompt cap so a pathological import can't balloon a single LLM request.
# It is a CHUNK size, not a ceiling: `_gapfill` loops over all rules-misses in
# batches of this size, so every miss is categorized before the write. (A miss
# left blank would be appended with its real Txn-ID, then excluded from dedup
# forever — never re-presented to the LLM — so a one-shot 80-cap was permanent
# data loss on the first 45-day backlog. B5, audit 2026-06-18.)
GAPFILL_MAX_BATCH = 80


# ---------------------------------------------------------------------------
# Rules (stage 1) — pure, on-box
# ---------------------------------------------------------------------------
def load_rules(path: Optional[Path] = None) -> list[tuple[str, str]]:
    """Parse the rules CSV → [(pattern_casefolded, category)], file order kept.
    Comment (#) / blank / header lines are skipped; a missing file → [] (the
    rules engine no-ops, degrade quiet). Patterns are casefolded once here so
    matching is a plain case-insensitive substring test."""
    path = Path(path or config.FINANCE_CATEGORY_RULES)
    if not path.exists():
        log.warning("no finance category rules at %s — rules engine no-ops", path)
        return []
    rules: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.casefold().startswith("pattern,"):
            continue
        pat, _, cat = s.partition(",")
        pat, cat = pat.strip(), cat.strip()
        if pat and cat:
            rules.append((pat.casefold(), cat))
    return rules


def vocabulary(rules: list[tuple[str, str]]) -> list[str]:
    """Distinct categories in file order — the ONLY labels gap-fill may use."""
    seen: set[str] = set()
    out: list[str] = []
    for _, cat in rules:
        if cat not in seen:
            seen.add(cat)
            out.append(cat)
    return out


def apply_rules(description: str, rules: list[tuple[str, str]]) -> Optional[str]:
    """First category whose keyword is a substring of the description, else None."""
    d = (description or "").casefold()
    if not d:
        return None
    for pat, cat in rules:
        if pat in d:
            return cat
    return None


# ---------------------------------------------------------------------------
# Orchestration — rules first, then the bounded gap-fill
# ---------------------------------------------------------------------------
def categorize_transactions(txns: list[dict], *, allow_llm: bool = True,
                            rules_path: Optional[Path] = None) -> None:
    """Populate Category + Cat-Source on each txn dict IN PLACE (Finance-
    Transactions shape). Rules run on every still-blank txn; then, when
    `allow_llm` and a provider key is configured, the LLM gap-fills the
    rules-miss remainder. A txn that already carries a Category is left as-is."""
    if not txns:
        return
    rules = load_rules(rules_path)
    misses: list[dict] = []
    for t in txns:
        if str(t.get("Category", "") or "").strip():   # already categorized
            continue
        cat = apply_rules(t.get("Description", ""), rules)
        if cat:
            t["Category"], t["Cat-Source"] = cat, "rules"
        else:
            misses.append(t)
    if allow_llm and misses:
        _gapfill(misses, vocabulary(rules))


def _gapfill(misses: list[dict], vocab: list[str]) -> None:
    """DeepSeek (or the configured fallback) over the rules-miss remainder, in
    chunks of GAPFILL_MAX_BATCH so the WHOLE remainder is categorized before the
    write — a large first import (the 45-day backlog) is fully covered, not
    truncated at the per-prompt cap. No vocab / no key → no-op. lib/llm is
    imported lazily so a keyless box pays nothing and the import never hinges on
    the LLM module."""
    if not vocab:
        return
    from automation.lib import llm
    if not llm.available():
        return
    for start in range(0, len(misses), GAPFILL_MAX_BATCH):
        _gapfill_batch(misses[start:start + GAPFILL_MAX_BATCH], vocab, llm)


def _gapfill_batch(batch: list[dict], vocab: list[str], llm) -> None:
    """One LLM request over <= GAPFILL_MAX_BATCH rules-misses. A failed/empty
    reply leaves THIS chunk blank (degrade quiet, §3.6) without aborting the
    other chunks — those rows can still be filled by a human or a later run."""
    # Privacy seam: each line carries a within-batch INDEX (not the Txn-ID), the
    # amount, and the description — nothing else from the row ever leaves the box.
    lines = []
    for i, t in enumerate(batch):
        amt = t.get("Amount (ILS)", "")
        desc = str(t.get("Description", "") or "").replace("\n", " ").strip()
        lines.append(f"{i}\t{amt}\t{desc}")
    system = (
        "You categorize Israeli household bank and credit-card transactions. "
        "For each line choose EXACTLY ONE category from this list:\n"
        f"{', '.join(vocab)}\n"
        'If none clearly fits, use "UNKNOWN". Decide from the description and '
        "amount only. Reply with a JSON object of the form "
        '{"results":[{"i":<index>,"category":"<one listed category or UNKNOWN>"}]}.'
    )
    prompt = "index\tamount\tdescription\n" + "\n".join(lines)
    # Size the reply budget to the chunk. A full GAPFILL_MAX_BATCH reply of
    # {"i":N,"category":"…"} items runs ~1.5k tokens — a fixed 600 truncates the
    # JSON array mid-stream, and a truncated object recovers NOTHING, so the
    # WHOLE chunk would land blank with real Txn-IDs and never be re-presented
    # (the very B5 data-loss this loop closes). ~24 tok/row + floor.
    raw = llm.complete(prompt, task="categorize", system=system,
                       max_tokens=max(256, len(batch) * 24),
                       source="finance.categorize", json_mode=True)
    if not raw:
        return
    for i, cat in _parse_gapfill(raw, vocab, len(batch)).items():
        batch[i]["Category"], batch[i]["Cat-Source"] = cat, "llm"


def _parse_gapfill(raw: str, vocab: list[str], n: int) -> dict[int, str]:
    """Tolerant parse: the first JSON object in the reply (DeepSeek json_mode is
    clean; the Anthropic fallback may wrap prose). Keep only in-range indices
    mapped to an in-vocab category (case-insensitive); drop UNKNOWN / off-vocab."""
    obj = _first_json_object(raw)
    if not isinstance(obj, dict):
        return {}
    canon = {c.casefold(): c for c in vocab}
    out: dict[int, str] = {}
    for item in obj.get("results") or []:
        if not isinstance(item, dict):
            continue
        try:
            i = int(item["i"])
        except (KeyError, TypeError, ValueError):
            continue
        cat = canon.get(str(item.get("category", "")).strip().casefold())
        if cat is not None and 0 <= i < n:
            out[i] = cat
    return out


def _first_json_object(raw: str):
    try:
        return json.loads(raw)
    except ValueError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except ValueError:
            return None

=== End: automation/lib/categorize.py ===

=== File: automation/lib/llm.py ===
"""
Family inc. — the ONE LLM wrapper (SPEC.md §8.6–8.7).

Provider (D-032, wired M4/D-044): DeepSeek is the single configured provider,
reached over its OpenAI-compatible /chat/completions endpoint with stdlib
urllib (no third-party SDK). The Anthropic path is kept as a fallback provider.
The active provider is chosen by which key is present — DeepSeek first, then
Anthropic, then neither.

Model ids live in `config.MODELS` (+ `config.ANTHROPIC_MODELS`), never at call
sites. Every call logs usage to `logs/llm_costs.csv`. LLM calls are decoration,
not structure: `complete()` returns None on any failure (no key, network/API
error, empty or garbled answer) and the caller takes its deterministic fallback
— degrade quiet, per SPEC §3.6.

Tests NEVER hit the network (ENGINEERING.md §7): set FAMILY_INC_LLM_FAKE to a
canned response and `complete()` returns it verbatim, before any provider is
consulted. The single network seam is `_http_post()`, which tests monkeypatch;
conftest also blanks both provider keys so the appliance's /etc/family-inc/env
can't pull a real call into a test (D-038/D-041/D-044).
"""
from __future__ import annotations

import csv
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional

from automation.lib import config

log = logging.getLogger("llm")


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------
def _provider() -> Optional[str]:
    """The active provider name, or None for the deterministic fallback.
    DeepSeek is the configured provider (D-032); Anthropic is the fallback when
    only that key is set. load_env() first so the appliance's
    /etc/family-inc/env keys are seen even before sheet.is_live() runs."""
    config.load_env()
    if os.environ.get(config.DEEPSEEK_API_KEY_ENV):
        return "deepseek"
    if os.environ.get(config.ANTHROPIC_API_KEY_ENV):
        return "anthropic"
    return None


def available() -> bool:
    """True when a call would do something: a fake is injected, or a provider
    key is configured."""
    if os.environ.get(config.LLM_FAKE_ENV):
        return True
    return _provider() is not None


def complete(prompt: str, *, task: str = "classify", system: Optional[str] = None,
             max_tokens: int = 400, source: str = "", json_mode: bool = False) -> Optional[str]:
    """One completion. None means 'use your deterministic fallback'.
    json_mode=True asks the provider for a strict JSON object (DeepSeek
    response_format); callers that parse JSON should set it AND still tolerate
    stray prose on parse, since the Anthropic fallback has no such switch."""
    fake = os.environ.get(config.LLM_FAKE_ENV)
    if fake:
        _log_cost(source or task, task, "fake", 0, 0)
        return fake
    provider = _provider()
    if provider == "deepseek":
        return _complete_deepseek(prompt, task, system, max_tokens, source, json_mode)
    if provider == "anthropic":
        return _complete_anthropic(prompt, task, system, max_tokens, source)
    return None


# ---------------------------------------------------------------------------
# DeepSeek — OpenAI-compatible /chat/completions over stdlib urllib
# ---------------------------------------------------------------------------
def _http_post(url: str, body: bytes, headers: dict, timeout: int) -> dict:
    """POST JSON, return the parsed response dict. This is the ONLY network
    seam — tests monkeypatch THIS, never the real endpoint (ENGINEERING §7)."""
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _complete_deepseek(prompt, task, system, max_tokens, source, json_mode=False) -> Optional[str]:
    model = config.MODELS.get(task)
    if not model:
        log.warning("unknown LLM task %r (config.MODELS) — deterministic fallback", task)
        return None
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    payload = {"model": model, "messages": messages,
               "max_tokens": max_tokens, "stream": False}
    if json_mode:  # strict JSON object — kills the trailing-prose parse failures (D-046)
        payload["response_format"] = {"type": "json_object"}
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {os.environ[config.DEEPSEEK_API_KEY_ENV]}"}
    try:
        data = _http_post(f"{config.DEEPSEEK_BASE_URL}/chat/completions",
                          body, headers, config.LLM_TIMEOUT_S)
    except (urllib.error.URLError, OSError, ValueError) as e:  # degrade quiet
        log.warning("DeepSeek call failed (%s: %s) — deterministic fallback",
                    type(e).__name__, e)
        return None
    try:
        text = (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as e:
        log.warning("DeepSeek response unparseable (%s) — deterministic fallback", e)
        return None
    usage = data.get("usage") or {}
    _log_cost(source or task, task, model,
              usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    return text or None


# ---------------------------------------------------------------------------
# Anthropic — fallback provider (SDK, lazy import)
# ---------------------------------------------------------------------------
def _complete_anthropic(prompt, task, system, max_tokens, source) -> Optional[str]:
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed — deterministic fallback")
        return None
    model = config.ANTHROPIC_MODELS.get(task)
    if not model:
        log.warning("unknown LLM task %r (config.ANTHROPIC_MODELS) — fallback", task)
        return None
    kwargs = {"model": model, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    try:
        client = anthropic.Anthropic(api_key=os.environ[config.ANTHROPIC_API_KEY_ENV])
        resp = client.messages.create(**kwargs)
        text = (resp.content[0].text or "").strip() if resp.content else ""
        usage = getattr(resp, "usage", None)
        _log_cost(source or task, task, model,
                  getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0))
        return text or None
    except Exception as e:  # degrade quiet: log with context, fall back
        log.warning("Anthropic call failed (%s: %s) — deterministic fallback",
                    type(e).__name__, e)
        return None


# ---------------------------------------------------------------------------
# Cost log (monthly ₪ totals derived from this at briefing time, SPEC §8.7)
# ---------------------------------------------------------------------------
_COST_HEADER = ["at", "source", "task", "model", "input_tokens", "output_tokens"]


def _log_cost(source: str, task: str, model: str, tokens_in: int, tokens_out: int) -> None:
    """Per-call usage line. Monthly ₪ totals are derived from this at briefing
    time (first weekly briefing of each month, SPEC §8.7)."""
    try:
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        new = not config.LLM_COSTS_LOG.exists()
        with config.LLM_COSTS_LOG.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(_COST_HEADER)
            w.writerow([datetime.now().isoformat(timespec="seconds"),
                        source, task, model, tokens_in, tokens_out])
    except OSError as e:
        log.warning("could not write llm cost log: %s", e)

=== End: automation/lib/llm.py ===

=== File: automation/weekly_briefing.py ===
"""
Family inc. — Weekly Briefing (SPEC.md §7.2: Sat 21:00, D-011)

Renamed from sunday_briefing.py in M1 — it runs Saturday evening. Generates
the cross-domain weekly briefing from the master workbook (lib/sheet.py — the
live Google Sheet when configured) and writes
Briefings/{date}_weekly_briefing.md; with --send it also queues through
lib/outbox.py (kind=briefing: budget-exempt, quiet-hours held; SPEC §7.2,
id=brief-weekly-{date}).

Sections (in order): week ahead · reminders firing this week · overdue ·
money · goals · data hygiene (which also surfaces schema-drift flags and
engine review flags — ENGINEERING §8 self-reporting: humans never read logs
unless the briefing says to).

The SPEC §7.2 LLM-written five-scene narrative (DESIGN.md §6) with this
deterministic template as its fallback is still an open lane — what follows
IS the fallback path.

Run modes:
  python3 automation/weekly_briefing.py             # today's date, writes file
  python3 automation/weekly_briefing.py --dry-run   # print only
  python3 automation/weekly_briefing.py --send      # also queue to the outbox (M3)
  python3 automation/weekly_briefing.py --as-of 2026-05-31
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/weekly_briefing.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import csv
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from automation import templates as T
from automation.lib import config, outbox, sheet
from automation.lib.dates import fmt_date, to_date
from automation.lib.money import fmt_money, pct

log = logging.getLogger("briefing")


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------
def section_week_ahead(wb, today: date, end: date) -> str:
    ws = wb["Calendar-Events"]
    rows = []
    for r in range(2, ws.max_row + 1):
        d = to_date(ws.cell(r, 1).value)
        if not d or d < today or d > end:
            continue
        title = ws.cell(r, 4).value
        if not title:
            continue
        rows.append({
            "date": d,
            "start": ws.cell(r, 2).value,
            "end": ws.cell(r, 3).value,
            "title": title,
            "owner": ws.cell(r, 5).value or "",
            "location": ws.cell(r, 7).value or "",
        })
    rows.sort(key=lambda x: (x["date"], x["start"] or ""))
    if not rows:
        return "_Quiet week ahead — no events scheduled._"
    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r)
    lines = []
    for d in sorted(by_day):
        marker = " **(today)**" if d == today else ""
        lines.append(f"\n**{fmt_date(d)}**{marker}")
        for r in by_day[d]:
            time = ""
            if r["start"]:
                time = f"{r['start']}"
            if r["start"] and r["end"]:
                time += f"–{r['end']}"
            if not time:
                time = "all day"
            who = f" · {r['owner']}" if r["owner"] else ""
            loc = f" · {r['location']}" if r["location"] else ""
            lines.append(f"- {time} — {r['title']}{who}{loc}")
    return "\n".join(lines).lstrip()


def section_reminders_week(wb, today: date, end: date) -> tuple[str, str]:
    """Returns (upcoming_section, overdue_section)."""
    ws = wb["Reminders"]
    upcoming, overdue = [], []
    for r in range(2, ws.max_row + 1):
        title = ws.cell(r, 1).value
        if not title or str(title).startswith("["):
            continue
        status = ws.cell(r, 7).value or "Pending"
        if status in {"Done", "Skipped"}:
            continue
        due = to_date(ws.cell(r, 4).value)
        if not due:
            continue
        owner = ws.cell(r, 3).value or ""
        domain = ws.cell(r, 2).value or ""
        days = (due - today).days
        if days < 0:
            overdue.append((due, days, title, owner, domain))
        elif days <= config.WEEK_AHEAD_DAYS:
            upcoming.append((due, days, title, owner, domain))
    upcoming.sort(key=lambda x: x[0])
    overdue.sort(key=lambda x: x[0])

    def render(rows, kind: str) -> str:
        if not rows:
            return f"_No {kind} items._"
        lines = []
        for due, days, title, owner, domain in rows:
            if days < 0:
                tag = f"🔴 overdue {-days}d"
            elif days == 0:
                tag = "🟠 today"
            elif days <= 1:
                tag = "🟠 tomorrow"
            elif days <= 7:
                tag = f"🟡 in {days}d"
            else:
                tag = f"in {days}d"
            who = f" · {owner}" if owner else ""
            dom = f" [{domain}]" if domain else ""
            lines.append(f"- {tag} — {title}{who}{dom}  ({due.isoformat()})")
        return "\n".join(lines)

    return render(upcoming, "upcoming"), render(overdue, "overdue")


def section_money(wb, today: date) -> str:
    """Read the budget tab (Finance-Budget; standardized from the as-built
    Finance-Bdgt at the M6 build, D-052 — SPEC §6.4 already named it). Tolerates
    an absent tab (a Sheet not yet renamed / no budget yet) — degrade, don't
    take the briefing down."""
    if config.FINANCE_BUDGET_TAB not in wb.sheetnames:
        return "_No budget data yet._"
    ws = wb[config.FINANCE_BUDGET_TAB]
    # Optional month-over-month column, located by HEADER (the live read handle
    # has no .max_column — scan a bounded range and stop at the name). Older
    # sheets / test stubs lack it → no MoM lines, output stays byte-identical.
    prev_col = None
    for c in range(1, 21):
        h = ws.cell(1, c).value
        if h and str(h).strip().casefold() == "last month (ils)":
            prev_col = c
            break
    rows = []
    for r in range(2, ws.max_row + 1):
        cat = ws.cell(r, 1).value
        if not cat or cat == "TOTAL":
            continue
        target = ws.cell(r, 2).value
        actual = ws.cell(r, 3).value
        if target in (None, 0):
            continue
        prev = ws.cell(r, prev_col).value if prev_col else None
        rows.append({
            "cat": cat,
            "target": float(target),
            "actual": float(actual or 0),
            "prev": float(prev) if prev not in (None, "") else None,
        })
    # Show top 3 over-budget and totals
    over = sorted([r for r in rows if r["actual"] > r["target"]],
                  key=lambda r: r["actual"] - r["target"], reverse=True)[:3]
    total_target = sum(r["target"] for r in rows)
    total_actual = sum(r["actual"] for r in rows)
    p = pct(total_actual, total_target)
    lines = [f"**Month-to-date:** {fmt_money(total_actual)} of {fmt_money(total_target)} target  ({(p or 0)*100:.0f}%)"]
    if over:
        lines.append("\n**Over-budget categories:**")
        for r in over:
            o = r["actual"] - r["target"]
            lines.append(f"- {r['cat']}: {fmt_money(r['actual'])} / {fmt_money(r['target'])}  (+{fmt_money(o)})")
    else:
        lines.append("\nNo categories over budget this month.")
    movers = _money_movers(rows)
    if movers:
        lines.append("\n**vs. last month:**")
        lines.extend(movers)
    return "\n".join(lines)


def _money_movers(rows, top: int = 3) -> list[str]:
    """Per-category month-over-month lines (M6.4) — the biggest absolute ₪ moves
    among categories whose last-month spend is known and non-zero. Empty when no
    'Last Month (ILS)' column is present (older sheets / stubs), so the Money
    section renders byte-identically there."""
    cand = sorted((r for r in rows if r["prev"] not in (None, 0)),
                  key=lambda r: abs(r["actual"] - r["prev"]), reverse=True)
    out = []
    for r in cand[:top]:
        delta = r["actual"] - r["prev"]
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "→")
        change = pct(abs(delta), r["prev"])
        out.append(f"- {r['cat']}: {fmt_money(r['actual'])} "
                   f"({arrow} {(change or 0)*100:.0f}% from {fmt_money(r['prev'])})")
    return out


def section_goals(wb, today: date) -> str:
    ws = wb["Goals"]
    rows = []
    for r in range(2, ws.max_row + 1):
        goal = ws.cell(r, 1).value
        if not goal:
            continue
        target = to_date(ws.cell(r, 4).value)
        milestone = ws.cell(r, 5).value or ""
        pct_done = ws.cell(r, 6).value
        last_update = to_date(ws.cell(r, 7).value)
        status = ws.cell(r, 8).value or "Not started"
        owner = ws.cell(r, 2).value or ""
        rows.append({
            "goal": goal, "owner": owner, "target": target, "milestone": milestone,
            "pct": pct_done, "last_update": last_update, "status": status
        })
    if not rows:
        return "_No goals tracked yet._"
    lines = []
    for r in rows:
        flags = []
        if r["target"] and (r["target"] - today).days <= config.GOAL_MILESTONE_FLAG_DAYS \
                and (r["target"] - today).days >= 0:
            flags.append(f"⏰ milestone in {(r['target']-today).days}d")
        if r["last_update"] and (today - r["last_update"]).days > config.STALE_GOAL_UPDATE_DAYS:
            flags.append(f"⚠️ no update in {(today - r['last_update']).days}d")
        pct_str = f"{int(r['pct'])}%" if isinstance(r["pct"], (int, float)) else "—"
        flag_str = ("  " + " · ".join(flags)) if flags else ""
        line = f"- **{r['goal']}** ({r['owner']}, {r['status']}, {pct_str})"
        if r["milestone"]:
            line += f"\n  next: {r['milestone']}"
        line += flag_str
        lines.append(line)
    return "\n".join(lines)


def _system_flags(today: "date | None" = None) -> list[str]:
    """Fail-loud surfacing (ENGINEERING §8): schema drift aborts engine runs
    silently from the humans' perspective — the briefing is where they hear
    about it. Engine review flags (Feb-29 clamps, Custom recurrence) ride
    along until someone clears the file."""
    issues = []
    drift = sheet.schema_drift_flag()
    if drift:
        issues.append("- ⚠ **schema drift**: Reminders header no longer matches "
                      f"SPEC §6.1 — engine runs are aborting ({'; '.join(drift.get('problems', []))})")
    if config.ENGINE_FLAGS.exists():
        flags = [json.loads(ln) for ln in
                 config.ENGINE_FLAGS.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for f in flags[-5:]:
            issues.append(f"- ⚠ engine flag: {f.get('reason', '?')} — row {f.get('row', '?')} "
                          f"`{f.get('title', '')}`")
        if len(flags) > 5:
            issues.append(f"- (+{len(flags) - 5} older engine flags in logs/engine_flags.jsonl)")
    if config.FAIL_FLAG.exists():
        # Normally reported + cleared by the next delivered daily digest; still
        # present on Saturday means digests aren't landing — say so here too.
        units = sorted({ln.strip().split()[-1] for ln in
                        config.FAIL_FLAG.read_text(encoding="utf-8").splitlines() if ln.strip()})
        issues.append("- ⚠ **unit failures unreported**: " + ", ".join(units) +
                      " — fail.flag uncleared, are digests being delivered? (journalctl)")
    # Email-fallback days are DEGRADED, not green (PO call 2026-06-12, D-028):
    # a slowly dying bridge must not hide behind a working fallback.
    if today is not None and config.DELIVERY_LOG.exists():
        smtp_days, queued_days = set(), set()
        for ln in config.DELIVERY_LOG.read_text(encoding="utf-8").splitlines()[1:]:
            parts = ln.split(",")
            if len(parts) < 2:
                continue
            d = to_date(parts[0])
            if d is None or (today - d).days > 7 or (today - d).days < 0:
                continue
            if parts[1] == "smtp":
                smtp_days.add(d)
            elif parts[1] == "queued-stale":
                queued_days.add(d)
        if smtp_days:
            issues.append(f"- ⚠ **bridge degraded**: {len(smtp_days)} of the last 7 digests "
                          "arrived by email fallback (bridge down >24h each time, SPEC §10.2) "
                          "— `journalctl -u family-bridge`, re-pair if logged out")
        if queued_days:
            issues.append(f"- ⚠ **delivery lagging**: {len(queued_days)} digest(s) this week "
                          "queued against a stale bridge and waited for reconnect")
    return issues


def section_hygiene(wb, today: date) -> str:
    # System flags (drift / engine-review / fail-flag / delivery) now live in
    # section_system (ENGINEERING §8) — this section is Sheet-data hygiene only.
    issues: list[str] = []
    # Reminders missing due date
    r_ws = wb["Reminders"]
    missing = 0
    for row in range(2, r_ws.max_row + 1):
        if r_ws.cell(row, 1).value and not r_ws.cell(row, 4).value:
            missing += 1
    if missing:
        issues.append(f"- {missing} reminder(s) missing a Due Date")
    # Stale Last Imported on accounts (col 7 — Finance-Accounts §12.2 schema).
    # Tolerate an absent tab (Sheet not yet renamed / finance not yet live).
    if config.FINANCE_ACCOUNTS_TAB in wb.sheetnames:
        fa_ws = wb[config.FINANCE_ACCOUNTS_TAB]
        for row in range(2, fa_ws.max_row + 1):
            if fa_ws.cell(row, 1).value and not fa_ws.cell(row, 1).value.startswith("["):
                last_imp = to_date(fa_ws.cell(row, 7).value)
                if not last_imp:
                    issues.append(f"- Account `{fa_ws.cell(row, 1).value}` has no Last Imported date")
                elif (today - last_imp).days > config.FINANCE_STALE_IMPORT_DAYS:
                    issues.append(f"- Account `{fa_ws.cell(row, 1).value}` not imported in {(today-last_imp).days}d")
    # Placeholder rows still in People/Health/etc.
    p_ws = wb["People"]
    placeholders = sum(1 for r in range(2, p_ws.max_row + 1)
                       if p_ws.cell(r, 1).value and str(p_ws.cell(r, 1).value).startswith("["))
    if placeholders:
        issues.append(f"- {placeholders} People row(s) still using placeholder names")
    if not issues:
        return "_All clean._"
    return "\n".join(issues)


# ---------------------------------------------------------------------------
# System self-report line (ENGINEERING §8 / SPEC §8.3) — the one health line.
# Reads the runtime logs; each helper degrades to zero when its log is absent so
# a fresh box renders a benign "no activity yet" line, never a crash.
# ---------------------------------------------------------------------------
def _in_week(d, today: date) -> bool:
    # Trailing 7-day window [today-6 .. today]; ACCURACY_REVIEW_DAYS is the named
    # "trailing window the weekly surface reviews" — the same window every
    # self-report metric uses (runs, tombstones, classified, spend).
    return d is not None and 0 <= (today - d).days < config.ACCURACY_REVIEW_DAYS


def _runs_logged_this_week(today: date) -> tuple[int, int]:
    """(distinct REAL run-dates logged in the trailing week, expected). The engine
    logs one heartbeat row per run — a logged non-dry-run date is a green run; a
    dry-run-only date doesn't count toward green."""
    expected = config.ACCURACY_REVIEW_DAYS
    if not config.REMINDERS_LOG.exists():
        return 0, expected
    seen: set = set()
    try:
        with config.REMINDERS_LOG.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                d = to_date(row.get("run_date"))
                if _in_week(d, today) and (row.get("dry_run") or "no").strip().lower() != "yes":
                    seen.add(d)
    except OSError:
        return 0, expected
    return len(seen), expected


def _tombstone_stats(today: date) -> tuple[int, float]:
    """(tombstone skips this week, max skip age in hours). `skipped_due_to_tombstone`
    is a per-run count repeated on each recipient row → counted once per run-date;
    `tombstone_max_age_h` is the additive age column (0 on pre-B6 rows)."""
    if not config.REMINDERS_LOG.exists():
        return 0, 0.0
    per_run: dict = {}
    max_age = 0.0
    try:
        with config.REMINDERS_LOG.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                d = to_date(row.get("run_date"))
                if not _in_week(d, today):
                    continue
                try:
                    per_run[d] = int(row.get("skipped_due_to_tombstone") or 0)
                except (TypeError, ValueError):
                    pass
                try:
                    max_age = max(max_age, float(row.get("tombstone_max_age_h") or 0))
                except (TypeError, ValueError):
                    pass
    except OSError:
        return 0, 0.0
    return sum(per_run.values()), max_age


def _llm_spend_ils(today: date) -> float:
    """Indicative ₪ LLM spend (a health figure, not accounting): the trailing
    week's logged tokens priced via config.LLM_PRICE_USD_PER_MTOK × FX, or
    month-to-date on the first weekly briefing of the month (SPEC §8.7)."""
    if not config.LLM_COSTS_LOG.exists():
        return 0.0
    # Same trailing 7-day window as the other metrics ([today-6 .. today]) — or
    # month-to-date on the month's one first-week briefing (SPEC §8.7).
    start = (today.replace(day=1) if today.day <= 7
             else today - timedelta(days=config.ACCURACY_REVIEW_DAYS - 1))
    usd = 0.0
    try:
        with config.LLM_COSTS_LOG.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                d = to_date((row.get("at") or "")[:10])
                if d is None or d < start or d > today:
                    continue
                pin, pout = config.LLM_PRICE_USD_PER_MTOK.get(
                    row.get("model", ""), config.LLM_PRICE_DEFAULT_USD_PER_MTOK)
                try:
                    usd += int(row.get("input_tokens") or 0) / 1e6 * pin
                    usd += int(row.get("output_tokens") or 0) / 1e6 * pout
                except (TypeError, ValueError):
                    pass
    except OSError:
        return 0.0
    return usd * config.USD_TO_ILS


def _classified_count(wb, today: date) -> int:
    """WhatsApp messages classified in the trailing week — the summarizer's count,
    read off the WhatsApp_Inbox tab via accuracy_review. 0 / degrade-quiet when the
    tab or module is unavailable (an aux metric must never break the briefing)."""
    try:
        from automation import accuracy_review as ar
        from automation.whatsapp_summarizer import CONFIG_DEFAULT, load_config
        if config.WA_INBOX_SHEET_TAB not in wb.sheetnames:
            return 0
        rows = ar._tab_rows(wb, config.WA_INBOX_SHEET_TAB)
        m = ar.collect(rows, today, config.ACCURACY_REVIEW_DAYS, load_config(CONFIG_DEFAULT))
        return m.total_in_window
    except Exception as e:  # noqa: BLE001 — aux metric, never break the briefing
        log.warning("self-report classified count skipped: %s", e)
        return 0


def section_system(wb, today: date) -> str:
    """The one system-health line (ENGINEERING §8): runs-green · messages
    classified · tombstone skips (max age) · ₪ LLM spend. A fail-flag,
    schema-drift, or stale-heartbeat warning REPLACES it — the humans only read
    logs when the briefing tells them to."""
    flags = _system_flags(today)
    if flags:
        return "\n".join(flags)
    runs, expected = _runs_logged_this_week(today)
    classified = _classified_count(wb, today)
    skips, max_age = _tombstone_stats(today)
    spend = _llm_spend_ils(today)
    if not (runs or classified or skips or spend):
        return T.SELF_REPORT_NO_DATA
    skips_phrase = (f"{skips} tombstone skips (max age {max_age:.1f}h)"
                    if skips else "0 tombstone skips")
    return T.SELF_REPORT_LINE.format(runs=runs, expected=expected,
                                     classified=classified, skips_phrase=skips_phrase,
                                     spend=f"{spend:.2f}")


def section_classifier_accuracy(wb, today: date) -> str:
    """Phase F (D-048): a compact pulse of the WhatsApp classifier's week —
    counts + ALERTs-by-rule + the <1/week false-positive target. The full
    operator surface lives in automation/accuracy_review.py. Auxiliary and
    fail-safe: the briefing carries load-bearing content, so any error here
    degrades to a quiet line rather than taking the briefing down."""
    try:
        from automation import accuracy_review as ar
        from automation.whatsapp_summarizer import CONFIG_DEFAULT, load_config
        if config.WA_INBOX_SHEET_TAB not in wb.sheetnames:
            return "_No classifier data yet._"
        rows = ar._tab_rows(wb, config.WA_INBOX_SHEET_TAB)
        m = ar.collect(rows, today, config.ACCURACY_REVIEW_DAYS, load_config(CONFIG_DEFAULT))
        return ar.render_brief(m)
    except Exception as e:  # noqa: BLE001 — an aux section must never break the briefing
        log.warning("classifier-accuracy section skipped: %s", e)
        return "_Classifier accuracy unavailable this week._"


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render_briefing(wb, today: date) -> str:
    end = today + timedelta(days=config.WEEK_AHEAD_DAYS)
    parts = []
    parts.append(T.WEEKLY_TITLE)
    parts.append(f"_{today.strftime('%A, %B %-d, %Y')}_  ·  week of {today.isoformat()} → {end.isoformat()}\n")

    parts.append("## Week ahead")
    parts.append(section_week_ahead(wb, today, end))

    upcoming, overdue = section_reminders_week(wb, today, end)
    parts.append("\n## Reminders firing this week")
    parts.append(upcoming)
    parts.append("\n## Overdue")
    parts.append(overdue)

    parts.append("\n## Money")
    parts.append(section_money(wb, today))

    parts.append("\n## Goals")
    parts.append(section_goals(wb, today))

    parts.append("\n## Data hygiene")
    parts.append(section_hygiene(wb, today))

    parts.append("\n## System")
    parts.append(section_system(wb, today))

    parts.append("\n## Classifier accuracy")
    parts.append(section_classifier_accuracy(wb, today))

    parts.append(T.WEEKLY_FOOTER)
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(today: date, dry_run: bool = False, send: bool = False,
        sheet_path: Path | None = None) -> Path | None:
    wb = sheet.workbook(sheet_path)  # live Sheet when configured (D-016)
    body = render_briefing(wb, today)
    if dry_run:
        print(body)
        return None
    config.BRIEFINGS_DIR.mkdir(exist_ok=True)
    out = config.BRIEFINGS_DIR / f"{today.isoformat()}_weekly_briefing.md"
    out.write_text(body, encoding="utf-8")
    print(f"wrote {out}")
    if send:
        res = outbox.queue("both", body, "briefing", source="weekly_briefing",
                           msg_id=f"brief-weekly-{today.isoformat()}")
        print(f"queued briefing → both: {len(res.queued)} row(s)"
              + (f", duplicate {res.duplicates}" if res.duplicates else ""))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--send", action="store_true",
                    help="queue to the bridge outbox (M3 timers use this)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, dry_run=args.dry_run, send=args.send)


if __name__ == "__main__":
    main()

=== End: automation/weekly_briefing.py ===

=== File: automation/reminders_engine.py ===
"""
Family inc. — Reminders Engine (SPEC.md §7.1: daily 07:25 — computes, does not send)

Reads the Reminders tab (via lib/sheet.py — the live Google Sheet when
FAMILY_INC_SHEET_ID is configured, the seed xlsx otherwise), applies the
tombstone guard and fire rules, and returns one Digest per recipient.
Delivery belongs to daily_digest.py (07:30), which renders ONE morning
message per recipient, queues it through lib/outbox.py, and stamps
Last Sent / Status back to the Sheet on send success.

This run's own write-back (M2): recurrence on Done — rows the dashboard
marked Done with a recurrence period get their Due Date bumped, Status →
Pending, Last Sent cleared (SPEC §7.1). Feb-29-class clamps and Custom
periods are flagged for review in logs/engine_flags.jsonl, surfaced by the
weekly briefing. Tombstoned rows (<6h) are skipped here exactly like fires —
write-backs honor the same race guard. Writes only happen against the live
backend (or an explicit --apply-writes for a local xlsx) so a creds-less run
never mutates the committed seed template.

Every run appends a heartbeat line to logs/reminders_log.csv (fired/dropped/
skipped + reasons).

Run modes:
  python3 automation/reminders_engine.py            # compute + log heartbeat (+ bumps when live)
  python3 automation/reminders_engine.py --dry-run  # compute + print, still logs (flagged)
  python3 automation/reminders_engine.py --as-of 2026-06-15  # simulate any date
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/reminders_engine.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import csv
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

from automation.lib import config, sheet
from automation.lib.dates import bump_due
from automation.lib.sheet import CellWrite, Reminder, read_reminders

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Fire:
    reminder: Reminder
    reason: str       # OVERDUE / FIRE TODAY / WEEK OUT / MONTH OUT / LEAD-{n}
    days_until: int


@dataclass
class Digest:
    recipient: str    # logical id: "adar" | "shanee" (numbers live in recipients.json)
    fires: list[Fire] = field(default_factory=list)
    dropped: list[Fire] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tombstone guard (SPEC.md §8.3 — offline-queue race window)
# ---------------------------------------------------------------------------
def is_tombstoned(r: Reminder, now: datetime,
                  window_hours: int = config.TOMBSTONE_SKIP_HOURS) -> bool:
    """True if the dashboard wrote (or flushed a queued write) within the last
    `window_hours`. When True, the engine MUST skip this row — the sheet state
    may be one hop behind reality."""
    if r.write_queue_tombstone is None:
        return False
    age = now - r.write_queue_tombstone
    if age.total_seconds() < 0:
        # Future-dated tombstone — treat as fresh, not as expired (SPEC §9).
        return True
    return age < timedelta(hours=window_hours)


# ---------------------------------------------------------------------------
# Decide-what-fires (SPEC.md §7.1)
# ---------------------------------------------------------------------------
def classify(r: Reminder, today: date) -> Fire | None:
    # SPEC §7.1 reads "Status ∉ {Done, Skipped}" — Sent rows stay eligible so a
    # 60,30,7,1 lead-time chain keeps firing after its first fire stamps Sent.
    if r.status in {"Done", "Skipped"}:
        return None
    if r.due is None:
        return None
    # Last-Sent guard (SPEC §8.4): a row already stamped today never re-fires —
    # engine/digest re-runs on the same day are no-ops at compute level.
    if r.last_sent == today:
        return None
    days = (r.due - today).days

    # Overdue cooldown
    if days < 0:
        if r.last_sent and (today - r.last_sent).days < config.OVERDUE_REPEAT_DAYS:
            return None
        return Fire(r, "OVERDUE", days)

    if days == 0:
        return Fire(r, "FIRE TODAY", 0)
    if days in r.lead_times:
        if days <= 1:
            return Fire(r, "FIRE TODAY", days)
        if days <= 7:
            return Fire(r, "WEEK OUT", days)
        if days <= 30:
            return Fire(r, "MONTH OUT", days)
        return Fire(r, f"LEAD-{days}", days)
    return None


# ---------------------------------------------------------------------------
# Route to recipients — logical ids only; Owner column is display-cased
# ---------------------------------------------------------------------------
OWNER_TO_RECIPIENTS = {
    "adar": ["adar"],
    "shanee": ["shanee"],
    "partner": ["shanee"],          # legacy rows from the pre-remake sheet
    "both": ["adar", "shanee"],
}


def route(fires: list[Fire]) -> dict[str, Digest]:
    digests: dict[str, Digest] = {}
    for f in fires:
        recipients = OWNER_TO_RECIPIENTS.get(f.reminder.owner.strip().lower(), ["adar"])
        for r in recipients:
            digests.setdefault(r, Digest(recipient=r)).fires.append(f)
    return digests


# ---------------------------------------------------------------------------
# Digest shaping (priority-aware trimming — keeps the morning message short)
# ---------------------------------------------------------------------------
PRIORITY = {"OVERDUE": 0, "FIRE TODAY": 1, "WEEK OUT": 2, "MONTH OUT": 3}


def apply_budget(d: Digest, max_items: int = config.DIGEST_MAX_ITEMS) -> None:
    """Trim to `max_items`: OVERDUE / FIRE TODAY / Health always survive;
    Goals bump first (SPEC §8.1 trim priority)."""
    must = [f for f in d.fires if f.reason == "OVERDUE"
            or f.reason == "FIRE TODAY"
            or f.reminder.domain in config.ALWAYS_INCLUDE_DOMAINS]
    rest = [f for f in d.fires if f not in must]
    rest.sort(key=lambda f: (PRIORITY.get(f.reason, 9),
                             f.reminder.domain in config.DROP_FIRST_DOMAINS,
                             f.days_until))
    keep = must + rest
    if len(keep) > max_items:
        d.dropped = keep[max_items:]
        keep = keep[:max_items]
    d.fires = keep


# ---------------------------------------------------------------------------
# Heartbeat log (SPEC §7.1: one line per run, always)
# ---------------------------------------------------------------------------
LOG_HEADER = [
    "run_date", "recipient", "fires_sent", "fires_dropped",
    "skipped_due_to_tombstone", "dry_run", "titles_sent",
    "tombstone_max_age_h",   # additive (B6): max skip age this run, for the
                             # weekly self-report "max age seen" (SPEC §8.3)
]


def append_log(today: date, digests: dict[str, Digest], log_path: Path | None = None,
               skipped_tombstone: int = 0, dry_run: bool = False,
               tombstone_max_age_h: float = 0.0) -> None:
    """One row per recipient per run. `skipped_due_to_tombstone` /
    `tombstone_max_age_h` are per-run metrics, repeated on each recipient row
    (older rows predate the age column → read as 0)."""
    log_path = log_path or config.REMINDERS_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not log_path.exists()
    with log_path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new_file:
            w.writerow(LOG_HEADER)
        # If there are no digests but the run still happened (all tombstoned
        # or genuinely quiet), emit one heartbeat row so log analysis sees the run.
        rows_to_emit = list(digests.items()) or [("(none)", Digest(recipient="(none)"))]
        for r, d in rows_to_emit:
            titles = " | ".join(f.reminder.title for f in d.fires)
            w.writerow([
                today.isoformat(), r,
                len(d.fires), len(d.dropped),
                skipped_tombstone, "yes" if dry_run else "no",
                titles, f"{tombstone_max_age_h:.2f}",
            ])


# ---------------------------------------------------------------------------
# Compute (pure; the 07:30 digest assembler calls this)
# ---------------------------------------------------------------------------
@dataclass
class ComputeResult:
    digests: dict[str, Digest]
    tombstoned: list[tuple[Reminder, float]]   # (reminder, age_hours)


def compute(today: date, now: datetime | None = None,
            sheet_path: Path | None = None) -> ComputeResult:
    """Read → tombstone-guard → classify → route → trim. No side effects."""
    if now is None:
        now = datetime.now() if today == date.today() else datetime.combine(today, time(7, 30))
    reminders = read_reminders(sheet_path)  # None → live Sheet when configured

    active: list[Reminder] = []
    tombstoned: list[tuple[Reminder, float]] = []
    for r in reminders:
        if is_tombstoned(r, now):
            age_h = (now - r.write_queue_tombstone).total_seconds() / 3600.0
            tombstoned.append((r, age_h))
        else:
            active.append(r)

    fires = [f for f in (classify(r, today) for r in active) if f]
    digests = route(fires)
    for d in digests.values():
        apply_budget(d)
    return ComputeResult(digests=digests, tombstoned=tombstoned)


# ---------------------------------------------------------------------------
# Write-backs (M2, SPEC §7.1) — the engine's only Sheet writes
# ---------------------------------------------------------------------------
def _flag_for_review(reason: str, r: Reminder, **fields) -> None:
    """Append one review line to logs/engine_flags.jsonl (weekly briefing
    surfaces unreviewed flags in data hygiene)."""
    config.ENGINE_FLAGS.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now().isoformat(timespec="seconds"), "reason": reason,
           "row": r.row, "title": r.title, **fields}
    with config.ENGINE_FLAGS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def recurrence_writes(reminders: list[Reminder], now: datetime) -> list[CellWrite]:
    """Recurrence on Done (SPEC §7.1): bump Due Date by the period, Status →
    Pending, Last Sent cleared. DoneAt/LastDoneBy stay — the dashboard arc and
    ticker read them. Tombstoned rows (<6h) wait for the next run; clamped
    dates (Feb-29 class) and Custom periods are flagged for review."""
    writes: list[CellWrite] = []
    for r in reminders:
        if r.status != "Done" or r.recurrence in ("", "One-off"):
            continue
        if is_tombstoned(r, now):
            continue  # same race guard as fires — the dashboard may still be writing
        if r.due is None:
            _flag_for_review("recurring_done_without_due", r)
            continue
        new_due, clamped = bump_due(r.due, r.recurrence)
        if new_due is None:
            _flag_for_review("unbumpable_recurrence", r, recurrence=r.recurrence)
            continue
        if clamped:
            _flag_for_review("recurrence_clamped_to_month_end", r,
                             old_due=r.due.isoformat(), new_due=new_due.isoformat())
        writes += [
            CellWrite(r.row, "Due Date", new_due),
            CellWrite(r.row, "Status", "Pending"),
            CellWrite(r.row, "Last Sent", None),
        ]
    return writes


def stamp_writes(fires: list[Fire], now: datetime) -> list[CellWrite]:
    """On send success (daily_digest --send): Last Sent = now,
    Status = Sent | Overdue (SPEC §7.1)."""
    writes: list[CellWrite] = []
    for f in {f.reminder.row: f for f in fires}.values():  # one stamp per row
        writes += [
            CellWrite(f.reminder.row, "Last Sent", now),
            CellWrite(f.reminder.row, "Status",
                      "Overdue" if f.days_until < 0 else "Sent"),
        ]
    return writes


def apply_recurrence(today: date, now: datetime | None = None,
                     sheet_path: Path | None = None) -> int:
    """Read → bump Done recurring rows → one batched write. Returns rows bumped."""
    now = now or datetime.now()
    reminders = read_reminders(sheet_path)
    writes = recurrence_writes(reminders, now)
    if writes:
        sheet.update_reminders(writes, sheet_path)
    return len({w.row for w in writes})


def run(today: date, dry_run: bool = False, now: datetime | None = None,
        sheet_path: Path | None = None, apply_writes: bool | None = None) -> dict[str, Digest]:
    """CLI entry: compute + recurrence write-back + heartbeat log + console
    summary. Rendering and delivery live in daily_digest.py — this engine
    never messages anyone.

    `apply_writes`: None → write only against the live backend (sheet.is_live());
    True forces writes (tests, against an explicit sheet_path); dry_run always
    suppresses them."""
    if apply_writes is None:
        apply_writes = sheet.is_live() and sheet_path is None
    if apply_writes and not dry_run:
        bumped = apply_recurrence(today, now=now, sheet_path=sheet_path)
        if bumped:
            print(f"recurrence: bumped {bumped} Done row(s) to their next due date")

    result = compute(today, now=now, sheet_path=sheet_path)

    if result.tombstoned:
        print(f"tombstone-guard: skipped {len(result.tombstoned)} row(s) "
              f"(window={config.TOMBSTONE_SKIP_HOURS}h)")
        for r, age_h in result.tombstoned:
            print(f"  row {r.row} '{r.title}' — tombstone age {age_h:.2f}h")

    if not result.digests:
        print(f"{today}: quiet day — no fires")
    for rcpt, d in result.digests.items():
        print(f"{today}: {rcpt} ← {len(d.fires)} fire(s), {len(d.dropped)} dropped")
        if dry_run:
            for f in d.fires:
                print(f"    {f.reason:<10} {f.reminder.title}")

    append_log(today, result.digests, skipped_tombstone=len(result.tombstoned),
               dry_run=dry_run,
               tombstone_max_age_h=max((a for _, a in result.tombstoned), default=0.0))
    return result.digests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply-writes", action="store_true",
                    help="force recurrence write-backs without a live backend "
                         "(normally implied by FAMILY_INC_SHEET_ID)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, dry_run=args.dry_run,
        apply_writes=True if args.apply_writes else None)


if __name__ == "__main__":
    main()

=== End: automation/reminders_engine.py ===

=== File: automation/daily_digest.py ===
"""
Family inc. — Daily digest assembly (SPEC.md §7.2: 07:30 — ONE morning message
per recipient, not several)

Carved out of the engine's send path in M1 (ENGINEERING.md §9). Assembles, in
order: reminders fires (engine compute) · alerts held by yesterday's budget ·
the WhatsApp groups digest (written hourly by whatsapp_summarizer) · new
property listings (written by property_scrape, M5/§12.1 — silent, no alert) ·
a Hebcal candle-lighting line on Fridays. Renders with `templates.py` copy and writes
one file per recipient to Briefings/; with --send it also queues through
lib/outbox.py (kind=briefing per SPEC §7.2 — budget-exempt, never deferrable;
was kind=alert until D-027 — id=brief-daily-{date}).

Delivery degrades per SPEC §10.2: heartbeat stale >24h → the identical
rendered content goes by SMTP (lib/mailer.py) instead of queueing rows the
bridge can't deliver. It also reports + clears logs/fail.flag (the systemd
OnFailure= hook, ENGINEERING §5) — fail loud, in the message humans read.

Until M3 go-live, run WITHOUT --send: files are written, nobody is messaged,
and nothing accumulates in the bridge outbox.

On send success (--send, rows actually queued this run) the digest stamps each
fired row back to the Sheet: Last Sent = now, Status = Sent | Overdue (SPEC
§7.1/§7.2). Stamping is skipped — loudly — when no live backend is configured,
so a dev-machine --send can never mutate the committed seed xlsx.

Run modes:
  python3 automation/daily_digest.py             # write Briefings/ files
  python3 automation/daily_digest.py --dry-run   # print only
  python3 automation/daily_digest.py --send      # also queue to the outbox (M3)
  python3 automation/daily_digest.py --as-of 2026-06-15
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/daily_digest.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import csv
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Callable, Optional

from automation import templates as T
from automation import reminders_engine as engine
from automation.lib import config, mailer, outbox, sheet
from automation.lib.dates import fmt_date_he

# ---------------------------------------------------------------------------
# Reminders section (DESIGN §6 v1: one line per item — flag emoji · title ·
# due phrase; notes ride along only when ≤120 chars; no reply footers, D-014.
# Byte-stability is locked by tests/test_render_golden.py)
# ---------------------------------------------------------------------------
def due_phrase(f: engine.Fire) -> str:
    n = f.days_until
    if n < 0:
        if n == -1:
            return T.DUE_OVERDUE_1
        if n == -2:
            return T.DUE_OVERDUE_2
        return T.DUE_OVERDUE_N.format(n=-n)
    if n == 0:
        return T.DUE_TODAY
    if n == 1:
        return T.DUE_TOMORROW
    if n == 2:
        return T.DUE_IN_2
    return T.DUE_IN_N.format(n=n)


def render_digest(d: engine.Digest, today: date) -> str:
    head = T.DIGEST_HEAD.format(date=fmt_date_he(today))
    if not d.fires:
        return f"{head}\n{T.DIGEST_QUIET_DAY}"
    lines = [head]
    for f in d.fires:
        lines.append(T.DIGEST_ITEM.format(
            emoji=T.FLAG_EMOJI.get(f.reason, "•"),
            title=f.reminder.title, due_phrase=due_phrase(f)))
        notes = f.reminder.notes.strip()
        if notes and len(notes) <= config.NOTES_MAX_CHARS:
            lines.append(notes)
    if d.dropped:
        lines.append(T.DIGEST_MORE_IN_DASHBOARD.format(n=len(d.dropped)))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Batch-window dedup (guards a rerun/retry within BATCH_WINDOW_MINUTES;
# lives here because it is a send-path concern)
# ---------------------------------------------------------------------------
def batch_deduplicate(digests: dict[str, engine.Digest], now: datetime,
                      window_minutes: int = config.BATCH_WINDOW_MINUTES,
                      log_path: Optional[Path] = None) -> dict[str, engine.Digest]:
    """Suppress fires whose titles already appear in log rows inside the batch
    window, so a forced rerun doesn't message the same alert twice."""
    log_path = log_path or config.REMINDERS_LOG
    cutoff = now - timedelta(minutes=window_minutes)
    if not log_path.exists():
        return digests  # no history, nothing to dedup

    sent_recently: set[str] = set()
    try:
        with log_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    run_dt = datetime.fromisoformat(row.get("run_date", ""))
                    if run_dt >= cutoff:
                        for title in (row.get("titles_sent") or "").split(" | "):
                            if title.strip():
                                sent_recently.add(title.strip())
                except (ValueError, TypeError):
                    pass
    except OSError:
        return digests

    if not sent_recently:
        return digests

    deduped: dict[str, engine.Digest] = {}
    for recipient, d in digests.items():
        kept = [f for f in d.fires if f.reminder.title not in sent_recently]
        dropped = [f for f in d.fires if f.reminder.title in sent_recently]
        deduped[recipient] = engine.Digest(recipient=recipient, fires=kept,
                                           dropped=d.dropped + dropped)
    return deduped


# ---------------------------------------------------------------------------
# Assembly (SPEC §7.2): reminders · budget-deferred · WA digest · Hebcal
# ---------------------------------------------------------------------------
def _wa_digest_text(today: date, briefings_dir: Path) -> str:
    p = briefings_dir / f"whatsapp_digest_{today.isoformat()}.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


def _property_text(today: date, briefings_dir: Path) -> str:
    """The "🏠 דירות חדשות" section written by property_scrape (M5, §12.1).
    Absent on days with no new listings → contributes nothing (silent)."""
    p = briefings_dir / f"property_listings_{today.isoformat()}.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


def _hebcal_line(today: date, shabbat_times: Optional[Callable],
                 chag_candles: Optional[Callable] = None) -> str:
    """Candle-lighting line on erev-Shabbat (Fridays) AND erev-chag (yom-tov eves)
    — SPEC §7.2/§4. Fridays read shabbat_times(); other days read chag_candles(),
    which returns None on a plain (non-eve) day. Degrades to nothing — a missing
    Hebcal answer must not page anyone, and a non-eve simply renders no line."""
    if shabbat_times is None:
        return ""
    # A chag whose eve falls on a Friday is handled as Shabbat (candle time is
    # correct; for a Sat+Sun yom-tov block the havdalah shown is Saturday night).
    is_friday = today.weekday() == 4  # 4 = Friday
    try:
        if is_friday:
            st = shabbat_times(today)
        elif chag_candles is not None:
            st = chag_candles(today)
        else:
            st = None
    except Exception:
        return ""
    if not st:
        return ""
    candles, havdalah = st.get("candle_lighting"), st.get("havdalah")
    if not candles or not havdalah:
        return ""
    def hhmm(iso: str) -> str:
        try:
            return datetime.fromisoformat(iso).strftime("%H:%M")
        except ValueError:
            return iso
    tmpl = T.HEBCAL_LINE if is_friday else T.HEBCAL_LINE_CHAG  # "צאת שבת" vs "צאת החג"
    return tmpl.format(candles=hhmm(candles), havdalah=hhmm(havdalah))


_DEFAULT = object()  # sentinel: "use the real hebcal client"


@dataclass
class Assembly:
    """Rendered messages plus the digests they were rendered from — the send
    path stamps Last Sent/Status for exactly the fires that went out."""
    messages: dict[str, str] = field(default_factory=dict)
    digests: dict[str, engine.Digest] = field(default_factory=dict)


def assemble(today: date, now: Optional[datetime] = None,
             sheet_path: Optional[Path] = None,
             briefings_dir: Optional[Path] = None,
             shabbat_times: Optional[Callable] = _DEFAULT,
             chag_candles: Optional[Callable] = _DEFAULT,
             deferred: Optional[list[dict]] = None,
             failed_units: Optional[list[str]] = None) -> Assembly:
    """One rendered message per recipient. Pure given its inputs (the Hebcal
    fetchers and the deferred list are injectable so tests stay deterministic
    and dry runs never consume the deferred queue)."""
    if now is None:
        now = datetime.now() if today == date.today() else datetime.combine(today, time(7, 30))
    if shabbat_times is _DEFAULT or chag_candles is _DEFAULT:
        from automation import hebcal_client
        if shabbat_times is _DEFAULT:
            shabbat_times = hebcal_client.shabbat_times
        if chag_candles is _DEFAULT:
            chag_candles = hebcal_client.chag_candles
    briefings_dir = briefings_dir or config.BRIEFINGS_DIR

    result = engine.compute(today, now=now, sheet_path=sheet_path)
    digests = batch_deduplicate(result.digests, now)

    # Brief BOTH adults EVERY day (D-045). A recipient with no fires today still
    # gets the morning briefing — the quiet-day line plus the shared WA-groups /
    # property sections. This generalizes the partner-symmetric quiet-day rule
    # (D-036e/D-044, which only covered a FULLY-quiet day) to the asymmetric day:
    # when one adult has fires and the other none, the empty-handed adult is no
    # longer left with no morning message at all. Briefings are budget-exempt
    # (kind=briefing), so the extra message never spends an alert slot, and the
    # message's silence stays distinguishable from a broken digest. Canonical
    # (adar, shanee) order; engine.compute only ever keys these two (§7.3 routing).
    digests = {r: digests[r] if r in digests else engine.Digest(recipient=r)
               for r in config.DIGEST_RECIPIENTS}

    if deferred is None:
        deferred = outbox.read_deferred(today)
    wa_text = _wa_digest_text(today, briefings_dir)
    property_text = _property_text(today, briefings_dir)
    hebcal = _hebcal_line(today, shabbat_times, chag_candles)

    # Overnight unit failures prepend, never replace (DESIGN §6) — the humans
    # never check journald unless a message tells them to (ENGINEERING §8).
    fail_line = (T.FAIL_FLAG_LINE.format(units=", ".join(failed_units))
                 if failed_units else None)

    messages: dict[str, str] = {}
    for rcpt, d in digests.items():
        parts = ([fail_line] if fail_line else []) + [render_digest(d, today)]
        mine = [r for r in deferred if r.get("to") in (rcpt, "both")]
        if mine:
            parts.append("\n".join([T.SECTION_DEFERRED] +
                                   [T.DEFERRED_ITEM.format(body=r["body"]) for r in mine]))
        if wa_text:
            parts.append(wa_text)
        if property_text:
            parts.append(property_text)
        if hebcal:
            parts.append(hebcal)
        messages[rcpt] = "\n\n".join(parts) + "\n"
    return Assembly(messages=messages, digests=digests)


# ---------------------------------------------------------------------------
# Persist + queue
# ---------------------------------------------------------------------------
def write_briefing_files(messages: dict[str, str], today: date,
                         briefings_dir: Optional[Path] = None) -> list[Path]:
    briefings_dir = briefings_dir or config.BRIEFINGS_DIR
    briefings_dir.mkdir(exist_ok=True)
    out = []
    for rcpt, body in messages.items():
        p = briefings_dir / f"{today.isoformat()}_briefing_{rcpt}.md"
        p.write_text(body, encoding="utf-8")
        out.append(p)
    return out


def stamp_sent(assembly: Assembly, queued_for: set[str], now: datetime,
               sheet_path: Optional[Path] = None) -> int:
    """Write Last Sent/Status for every row that reached at least one phone
    this run (SPEC §7.1 'on send success'). Returns rows stamped. Deferred or
    duplicate targets don't count as sent — their rows stay eligible."""
    fires = [f for rcpt in queued_for
             for f in assembly.digests.get(rcpt, engine.Digest(rcpt)).fires]
    writes = engine.stamp_writes(fires, now)
    if not writes:
        return 0
    if sheet_path is None and not sheet.is_live():
        print("[warn] no live Sheet backend — Last Sent/Status NOT stamped "
              "(refusing to write the seed xlsx)")
        return 0
    sheet.update_reminders(writes, sheet_path)
    return len({w.row for w in writes})


def _read_fail_flag_lines() -> list[str]:
    """Raw non-empty lines of logs/fail.flag — captured once per run so the
    clear can remove exactly what was reported (review 2026-06-12 C1, D-028)."""
    try:
        return [ln for ln in config.FAIL_FLAG.read_text(encoding="utf-8").splitlines()
                if ln.strip()]
    except OSError:
        return []


def read_fail_flag(lines: Optional[list[str]] = None) -> list[str]:
    """Failed unit names from logs/fail.flag — one line per OnFailure= firing
    ("<iso-ts> <unit>", ENGINEERING §5). Sorted unique; [] when absent."""
    src = _read_fail_flag_lines() if lines is None else lines
    return sorted({ln.strip().split()[-1] for ln in src})


def _log_delivery(today: date, transport: str, recipients: set[str]) -> None:
    """One line per --send run: baileys | smtp | queued-stale (review
    2026-06-12 C2, D-028). The weekly briefing reads this to surface
    email-degraded mornings — a slowly dying bridge must not hide behind a
    working fallback."""
    config.DELIVERY_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not config.DELIVERY_LOG.exists()
    with config.DELIVERY_LOG.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "transport", "recipients"])
        w.writerow([today.isoformat(), transport, "|".join(sorted(recipients))])


def run(today: date, dry_run: bool = False, send: bool = False,
        sheet_path: Optional[Path] = None) -> dict[str, str]:
    # The run's clock: wall time normally, 07:30 of the simulated day under
    # --as-of — stamps must carry the day they speak about, or the Last-Sent
    # rerun guard can't see them.
    now = datetime.now() if today == date.today() else datetime.combine(today, time(7, 30))
    # Real runs consume the deferred queue; dry runs only peek.
    deferred = outbox.read_deferred(today) if dry_run else outbox.pop_deferred(today)
    fail_lines = _read_fail_flag_lines()
    failed_units = read_fail_flag(fail_lines)
    assembly = assemble(today, now=now, deferred=deferred, sheet_path=sheet_path,
                        failed_units=failed_units)
    messages = assembly.messages
    if dry_run:
        for rcpt, body in messages.items():
            print(f"\n=== to {rcpt} ===\n{body}")
        return messages
    for p in write_briefing_files(messages, today):
        print(f"wrote {p}")
    if send:
        delivered = False
        stale = outbox.heartbeat_age_hours()
        if stale is None or stale > config.EMAIL_FALLBACK_AFTER_HOURS:
            # SPEC §10.2 layer 2: the sender itself degrades — identical
            # content by SMTP instead of queueing rows the bridge can't deliver.
            if mailer.send_digest(messages, stale, today):
                hours = "?" if stale is None else f"{stale:.0f}"
                print(f"[email-fallback] bridge down {hours}h — digest delivered by SMTP")
                stamped = stamp_sent(assembly, set(messages), now, sheet_path)
                if stamped:
                    print(f"stamped Last Sent/Status on {stamped} row(s)")
                _log_delivery(today, "smtp", set(messages))
                _clear_fail_flag(fail_lines)
                return messages
            # Both transports down: queue anyway (bridge delivers on reconnect),
            # shout, and leave the fail flag for a digest that actually lands.
            print("[error] email fallback failed — queueing to the bridge outbox; "
                  "delivery waits for reconnect")
        elif not outbox.bridge_alive():
            print("[warn] bridge heartbeat stale — digest queued, delivery waits for reconnect")
            delivered = True  # <24h blip: queued rows go out on reconnect
        else:
            delivered = True
        queued_for: set[str] = set()
        for rcpt, body in messages.items():
            # kind=briefing (SPEC §7.2, D-027): budget-exempt, never deferrable —
            # over-budget alerts defer INTO the digest, so the digest itself
            # must be undeferrable or the ledger goes circular.
            res = outbox.queue(rcpt, body, "briefing", source="daily_digest",
                               msg_id=f"brief-daily-{today.isoformat()}")
            if res.queued:
                queued_for.add(rcpt)
            print(f"queued → {rcpt}: {len(res.queued)} row(s)"
                  + (f", deferred {res.deferred}" if res.deferred else "")
                  + (f", duplicate {res.duplicates}" if res.duplicates else ""))
        stamped = stamp_sent(assembly, queued_for, now, sheet_path)
        if stamped:
            print(f"stamped Last Sent/Status on {stamped} row(s)")
        if queued_for:
            _log_delivery(today, "baileys" if delivered else "queued-stale", queued_for)
        if delivered and queued_for:
            _clear_fail_flag(fail_lines)
    return messages


def _clear_fail_flag(reported_lines: list[str]) -> None:
    """Reported-in-a-delivered-digest → cleared (ENGINEERING §5). Removes
    exactly the lines that were read at run start: a failure appended WHILE
    this digest was running survives for the next one to report (review
    2026-06-12 C1, D-028). Journald keeps the detail; the flag only exists
    to get a human to look."""
    if not reported_lines:
        return
    try:
        current = [ln for ln in config.FAIL_FLAG.read_text(encoding="utf-8").splitlines()
                   if ln.strip()]
    except OSError:
        return
    remaining = current.copy()
    for ln in reported_lines:
        if ln in remaining:
            remaining.remove(ln)
    if remaining:
        config.FAIL_FLAG.write_text("\n".join(remaining) + "\n", encoding="utf-8")
    else:
        config.FAIL_FLAG.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--dry-run", action="store_true", help="print only, write nothing")
    ap.add_argument("--send", action="store_true",
                    help="queue to the bridge outbox (M3 timers use this)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, dry_run=args.dry_run, send=args.send)


if __name__ == "__main__":
    main()

=== End: automation/daily_digest.py ===

=== File: automation/hebcal_client.py ===
"""
Family inc. — Hebcal client

Thin wrapper around Hebcal's JSON endpoints for Shabbat candle-lighting /
havdalah times and chag (festival) windows.

The geoname id lives in lib/config.py (nearest metro to home — Hebcal has no
entry for the family's town, and the coastal zman matches to ~1 minute).

Endpoints used:
  - Shabbat:  https://www.hebcal.com/shabbat/?cfg=json&geonameid=…&M=on
  - Calendar: https://www.hebcal.com/hebcal?v=1&cfg=json&maj=on&min=on&mod=on
              &nx=on&year=now&month=x&ss=on&mf=on&c=on&geo=geoname&geonameid=…

Cache: automation/cache/hebcal_cache.json — keyed by ISO week / month
window with a 24h TTL so we don't hammer the API.

Public API:
  shabbat_times(date=None) -> dict
  is_chag(date)           -> bool
  chagim_in_range(start, end) -> list[dict]

Run modes:
  python3 automation/hebcal_client.py   # smoke test: this Shabbat + 30d chagim
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/hebcal_client.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests

from automation.lib import config

CACHE_DIR = config.CACHE_DIR
CACHE_PATH = CACHE_DIR / "hebcal_cache.json"
TTL_SECONDS = config.HEBCAL_TTL_SECONDS
GEONAME_ID = config.HEBCAL_GEONAME_ID

SHABBAT_URL = "https://www.hebcal.com/shabbat/"
HEBCAL_URL = "https://www.hebcal.com/hebcal"

log = logging.getLogger("hebcal")

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

def _save_cache(cache: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")

def _cache_get(key: str) -> Optional[dict]:
    cache = _load_cache()
    entry = cache.get(key)
    if not entry:
        return None
    ts = entry.get("_fetched_at", 0)
    if (datetime.now(timezone.utc).timestamp() - ts) > TTL_SECONDS:
        return None
    return entry.get("data")

def _cache_put(key: str, data: dict) -> None:
    cache = _load_cache()
    cache[key] = {"_fetched_at": datetime.now(timezone.utc).timestamp(), "data": data}
    _save_cache(cache)

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
def _fetch_shabbat(d: date) -> dict:
    params = {"cfg": "json", "geonameid": GEONAME_ID, "M": "on", "gy": d.year, "gm": d.month, "gd": d.day}
    r = requests.get(SHABBAT_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def _fetch_hebcal_month(year: int, month: int) -> dict:
    params = {
        "v": 1, "cfg": "json", "maj": "on", "min": "on", "mod": "on",
        "nx": "on", "year": year, "month": month, "ss": "on", "mf": "on",
        "c": "on", "geo": "geoname", "geonameid": GEONAME_ID,
    }
    r = requests.get(HEBCAL_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def shabbat_times(d: Optional[date] = None) -> dict:
    """Return {candle_lighting, havdalah, parasha} for the Shabbat of the
    week containing `d` (Israel time strings, ISO 8601)."""
    d = d or date.today()
    # ISO week as cache key: same Shabbat for any day in that week
    iso_year, iso_week, _ = d.isocalendar()
    key = f"shabbat:{iso_year}-W{iso_week:02d}"
    cached = _cache_get(key)
    if cached:
        return cached

    try:
        payload = _fetch_shabbat(d)
    except requests.RequestException as e:
        log.warning("hebcal fetch failed (%s) — returning stub", e)
        return {"candle_lighting": None, "havdalah": None, "parasha": None,
                "_stub": True, "_reason": str(e)}

    out = {"candle_lighting": None, "havdalah": None, "parasha": None}
    for item in payload.get("items", []):
        cat = item.get("category")
        if cat == "candles" and not out["candle_lighting"]:
            out["candle_lighting"] = item.get("date")
        elif cat == "havdalah" and not out["havdalah"]:
            out["havdalah"] = item.get("date")
        elif cat == "parashat" and not out["parasha"]:
            out["parasha"] = item.get("hebrew") or item.get("title")
    _cache_put(key, out)
    return out

def chagim_in_range(start: date, end: date) -> list[dict]:
    """List chagim (major / minor / modern holidays) overlapping [start, end]."""
    months_needed = set()
    cur = date(start.year, start.month, 1)
    while cur <= end:
        months_needed.add((cur.year, cur.month))
        # next month
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)

    holidays: list[dict] = []
    for y, m in sorted(months_needed):
        key = f"hebcal:{y}-{m:02d}"
        data = _cache_get(key)
        if data is None:
            try:
                data = _fetch_hebcal_month(y, m)
                _cache_put(key, data)
            except requests.RequestException as e:
                log.warning("hebcal month fetch failed %s-%02d: %s", y, m, e)
                continue
        for item in data.get("items", []):
            if item.get("category") not in {"holiday", "roshchodesh"}:
                continue
            try:
                d = datetime.fromisoformat(item["date"]).date()
            except (KeyError, ValueError):
                continue
            if start <= d <= end:
                holidays.append({
                    "date": d.isoformat(),
                    "title": item.get("title"),
                    "hebrew": item.get("hebrew"),
                    "subcat": item.get("subcat"),
                    "yomtov": item.get("yomtov", False),
                })
    holidays.sort(key=lambda h: h["date"])
    return holidays

def is_chag(d: date) -> bool:
    """True if `d` is a yom-tov (work-forbidden chag) in Israel."""
    chagim = chagim_in_range(d, d)
    return any(h.get("yomtov") for h in chagim)


def _candle_items(start: date, end: date) -> list[dict]:
    """Sorted 'candles'/'havdalah' calendar items overlapping [start, end], each
    {category, dt, iso}. The calendar endpoint emits these for chag eves too (it
    is fetched with c=on) — chagim_in_range filters them out, so this is the seam
    that surfaces them. Degrade quiet: a month that fails to fetch is skipped."""
    months: set = set()
    cur = date(start.year, start.month, 1)
    while cur <= end:
        months.add((cur.year, cur.month))
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    out: list[dict] = []
    for y, m in sorted(months):
        key = f"hebcal:{y}-{m:02d}"
        data = _cache_get(key)
        if data is None:
            try:
                data = _fetch_hebcal_month(y, m)
                _cache_put(key, data)
            except requests.RequestException as e:
                log.warning("hebcal month fetch failed %s-%02d: %s", y, m, e)
                continue
        for item in data.get("items", []):
            if item.get("category") not in {"candles", "havdalah"}:
                continue
            iso = item.get("date")
            try:
                dt = datetime.fromisoformat(iso)
            except (TypeError, ValueError):
                continue
            if start <= dt.date() <= end:
                out.append({"category": item["category"], "dt": dt, "iso": iso})
    out.sort(key=lambda x: x["dt"])
    return out


def chag_candles(d: date) -> Optional[dict]:
    """Candle-lighting + havdalah bracketing a CHAG whose candle-lighting falls on
    `d` — a non-Shabbat yom-tov eve (Shabbat candles come from shabbat_times()).
    Returns {candle_lighting, havdalah} ISO strings when `d` is such an eve, else
    None. None also on a fetch failure: indistinguishable from no-chag here is
    acceptable — the digest simply renders no candle line, never a wrong one
    (degrade quiet, §3.6). Havdalah can be up to ~3 days out (a 2-day yom tov)."""
    items = _candle_items(d, d + timedelta(days=3))
    candle = next((it for it in items
                   if it["category"] == "candles" and it["dt"].date() == d), None)
    if candle is None:
        return None
    havdalah = next((it for it in items
                     if it["category"] == "havdalah" and it["dt"] > candle["dt"]), None)
    if havdalah is None:
        return None
    return {"candle_lighting": candle["iso"], "havdalah": havdalah["iso"]}

# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    today = date.today()
    print(f"Shabbat times around {today.isoformat()} (geoname {GEONAME_ID}):")
    st = shabbat_times(today)
    for k, v in st.items():
        print(f"  {k}: {v}")
    print(f"\nChagim in next 30 days ({today} → {today + timedelta(days=30)}):")
    chs = chagim_in_range(today, today + timedelta(days=30))
    if not chs:
        print("  (none)")
    for c in chs:
        flag = " [yom tov]" if c.get("yomtov") else ""
        print(f"  {c['date']}  {c.get('title','?')}{flag}")

=== End: automation/hebcal_client.py ===

=== File: automation/templates.py ===
"""
Family inc. — WhatsApp message copy. ALL phone-bound strings live here so
`DESIGN.md` §6 can be reviewed against one file (session protocol step 3).

M2: the DESIGN.md §6 Hebrew v1 templates. Register (DESIGN §6): short, warm,
zero exclamation marks, no imperatives toward a person; emoji are semantics,
not decoration; messages end with content, not instructions — the reply
footers are GONE per D-014 (reinstated in v1.1 with reply parsing). Dates as
"יום ו׳ 12/6" (lib/dates.fmt_date_he). Byte-stability is locked by
tests/test_render_golden.py; copy changes re-cut the goldens deliberately.

Copy lines marked [Shanee review] had no literal in DESIGN §6 and were written
to its register — fair game to reword (then regen goldens).
"""
from __future__ import annotations

# --- Daily digest (reminders section, DESIGN §6 template) -------------------
DIGEST_HEAD = "🏠 Family inc. · {date}"
DIGEST_QUIET_DAY = "אין תזכורות להיום — יום שקט."          # [Shanee review]
DIGEST_ITEM = "{emoji} {title} — {due_phrase}"
DIGEST_MORE_IN_DASHBOARD = "+{n} more — בלוח"

# Due phrases — DESIGN §6 wording; singular/dual mirror the dashboard's
# duePhrase() grammar (the two surfaces must read the same).
DUE_OVERDUE_1 = "באיחור יום"
DUE_OVERDUE_2 = "באיחור יומיים"
DUE_OVERDUE_N = "באיחור {n} ימים"
DUE_TODAY = "היום"
DUE_TOMORROW = "מחר"
DUE_IN_2 = "בעוד יומיים"
DUE_IN_N = "בעוד {n} ימים"

FLAG_EMOJI = {
    "OVERDUE":    "🔴",
    "FIRE TODAY": "🟠",
    "WEEK OUT":   "🟡",
    "MONTH OUT":  "🟢",
}

# --- Daily digest (assembled sections, SPEC §7.2) ---------------------------
SECTION_DEFERRED = "נשמרו מאתמול (מכסת הודעות):"            # [Shanee review]
DEFERRED_ITEM = "• {body}"
HEBCAL_LINE = "🕯 הדלקת נרות {candles} · צאת שבת {havdalah}"
HEBCAL_LINE_CHAG = "🕯 הדלקת נרות {candles} · צאת החג {havdalah}"      # [Shanee review]

# --- WhatsApp groups section (built hourly, folded into the digest) ---------
WA_SECTION_HEAD = "קבוצות (24ש׳):"
WA_ITEM = "{group} — {one_liner} ({sender}, {time})"
WA_NEEDS_A_LOOK = "⚠ דורש מבט"                              # [Shanee review]
WA_NEEDS_A_LOOK_ITEM = "• {one_liner} ({sender}, {time})"

# --- Property tracker section (M5, SPEC §12.1: silent landing in the digest) -
# No DESIGN §6 literal yet — written to the §6 register; the section layout +
# which facets to show is a design call. [Shanee review: head + line shape]
PROPERTY_SECTION_HEAD = "🏠 דירות חדשות"
PROPERTY_ITEM = "{location} — ₪{price}{rooms}{size} ({portal})"
PROPERTY_ROOMS = " · {rooms} חד׳"      # appended only when rooms is known
PROPERTY_SIZE = " · {size} מ״ר"        # appended only when size is known

# --- Alerts (unsolicited, in-budget) and criticals (budget-bypassing) -------
# DESIGN §6: critical is a single line, no frame. The standard alert shares
# the shape minus the warning glyph. [Shanee review: alert shape]
ALERT_LINE = "{group}: {one_liner} ({sender}, {time})"
CRITICAL_LINE = "⚠ {group}: {one_liner} ({sender}, {time})"

# --- Bridge health (prepends, never replaces — DESIGN §6) --------------------
BRIDGE_SILENT = "⚠ הגשר שקט {hours:.0f} שעות — ייתכן שפספסנו הודעות"
FAIL_FLAG_LINE = "⚠ תקלה טכנית הלילה: {units} — נרשם ביומן"   # [Shanee review]

# --- Email fallback (SPEC §10.2 — body note copy is spec'd verbatim) ---------
EMAIL_FALLBACK_SUBJECT = "Family inc. — digest {date} (bridge down)"
EMAIL_FALLBACK_NOTE = "delivered by email — bridge down {hours}h"
EMAIL_SECTION_HEAD = "— {recipient} —"

# --- Weekly briefing ---------------------------------------------------------
# Deterministic fallback copy (SPEC §7.2); the LLM five-scene narrative and a
# Hebrew pass are still open — this stays the as-built English markdown until
# that lane is scheduled.
WEEKLY_TITLE = "# 🏠 Family inc. — Weekly Briefing"
# System self-report (ENGINEERING §8): the one health line, shown when nothing
# is wrong; a fail-flag / drift / stale-heartbeat warning replaces it.
SELF_REPORT_LINE = ("{runs}/{expected} runs green · {classified} messages classified · "
                    "{skips_phrase} · ₪{spend} LLM spend")
SELF_REPORT_NO_DATA = "_No system activity logged this week yet._"
WEEKLY_FOOTER = ("\n---\n_Read together with coffee, ~20 minutes. Edits go into "
                 "Family_OS — next week's briefing reflects them automatically._")

=== End: automation/templates.py ===

=== File: automation/lib/config.py ===
"""
Family inc. — configuration. ALL constants live here (ENGINEERING.md §3).

No constant may be defined in a script: the 2026-06-11 audit found
`ALERT_BUDGET_PER_DAY` defined twice with independent ledgers — the class of
bug this rule exists to prevent.

Secrets are NEVER here. They live in `/etc/family-inc/env` on the appliance
(`load_env()` reads it when present) or in the developer's shell env.
Values in this file are committed and must stay non-personal.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — lib/ → automation/ → repo root
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_DIR = ROOT / "automation"

# Master data (D-016). When FAMILY_INC_SHEET_ID is set (the appliance), every
# read/write goes to the live Google Sheet via lib/sheet.py's gspread backend.
# Without it (tests, creds-less dev) lib/sheet.py falls back to the local seed
# xlsx — a TEMPLATE, never a source of truth, and never written by default.
SHEET_PATH = ROOT / "Family_OS.xlsx"
SHEET_ID_ENV = "FAMILY_INC_SHEET_ID"              # spreadsheet id → live backend on
SA_JSON_ENV = "FAMILY_INC_SA_JSON"                # optional override of the path below
SA_JSON_DEFAULT = Path("/etc/family-inc/service-account.json")

# Tab names with code contracts (SPEC §6) — one definition, both backends.
REMINDERS_TAB = "Reminders"
SETTINGS_TAB = "Settings"
WA_INBOX_SHEET_TAB = "WhatsApp_Inbox"
WA_ARCHIVE_SHEET_TAB = "WhatsApp_Archive"
# Finance tabs (SPEC §6.4 / §12.2, M6). Standardized to full names 2026-06-17
# (D-052) — the as-built seed used the short Finance-Accts/Finance-Txns/
# Finance-Bdgt, which §6.4 already named Finance-Budget; the M6 build resolved
# the drift §12.2 flagged. lib/sheet owns the column maps (FINANCE_*_COLUMNS).
FINANCE_ACCOUNTS_TAB = "Finance-Accounts"
FINANCE_TRANSACTIONS_TAB = "Finance-Transactions"
FINANCE_BUDGET_TAB = "Finance-Budget"

# Runtime output (gitignored)
BRIEFINGS_DIR = ROOT / "Briefings"
LOGS_DIR = ROOT / "logs"
REMINDERS_LOG = LOGS_DIR / "reminders_log.csv"
LLM_COSTS_LOG = LOGS_DIR / "llm_costs.csv"
OUTBOX_LEDGER_DIR = LOGS_DIR / "outbox_ledger"
SCHEMA_DRIFT_FLAG = LOGS_DIR / "schema_drift.flag"   # written on §7.1 header mismatch;
                                                     # cleared by the next clean read;
                                                     # surfaced by the weekly briefing
ENGINE_FLAGS = LOGS_DIR / "engine_flags.jsonl"       # rows needing human review
                                                     # (Feb-29 clamps, Custom recurrence)

# Bridge state (gitignored; the Node listener shares these paths)
BRIDGE_DIR = AUTOMATION_DIR / "bridge"
BRIDGE_STATE_DIR = BRIDGE_DIR / "state"
OUTBOX_FILE = BRIDGE_STATE_DIR / "outbox" / "whatsapp_outbox.jsonl"
SENT_FILE = BRIDGE_STATE_DIR / "outbox" / "whatsapp_sent.jsonl"
DEFERRED_FILE = BRIDGE_STATE_DIR / "outbox" / "deferred.jsonl"
INBOX_FILE = BRIDGE_STATE_DIR / "inbox" / "whatsapp_inbox.jsonl"
HEARTBEAT_FILE = BRIDGE_STATE_DIR / "inbox" / "heartbeat.txt"

# Seeds (personal values → gitignored, stay on the machines that need them)
SEEDS_DIR = ROOT / "seeds"
WA_GROUP_CONFIG = SEEDS_DIR / "12_WhatsApp_Group_Config_Seed.csv"
# Sender → role roster (M4, D-044): maps a sender JID or display name to a role
# (teacher / vaad_bayit / …) so the §7.3 hard rules 2–3 don't depend on the
# bridge labelling sender_role — it only knows a JID and a push-name. PERSONAL →
# gitignored seed (format documented in seeds/README.md); absent → empty roster,
# and a message keeps whatever role it already carries.
SENDER_ROSTER = SEEDS_DIR / "13_Sender_Roster_Seed.csv"

# Misc caches (gitignored)
CACHE_DIR = AUTOMATION_DIR / "cache"

# ---------------------------------------------------------------------------
# Alerting policy (SPEC.md §8.1–8.3)
# ---------------------------------------------------------------------------
ALERT_BUDGET_PER_DAY = 2     # unsolicited messages / recipient / day (hard cap)
TOMBSTONE_SKIP_HOURS = 6     # engine skips rows tombstoned within this window
OVERDUE_REPEAT_DAYS = 3      # overdue reminders re-fire at most every N days
QUIET_HOURS_START = 22       # 22:00 local — alerts + briefings hold
QUIET_HOURS_END = 7          # 07:00 local — held messages release
BATCH_WINDOW_MINUTES = 5     # rerun-within-window fires are deduplicated

# Digest shaping (reminders engine → daily digest)
DIGEST_MAX_ITEMS = 5                  # keep the morning message short
DROP_FIRST_DOMAINS = {"Goals"}        # de-prioritised — covered by the weekly briefing
ALWAYS_INCLUDE_DOMAINS = {"Health"}   # never trimmed
NOTES_MAX_CHARS = 120                 # DESIGN §6: notes ride along only when short
# The two adults — the ONLY message recipients (SPEC §3: no messages beyond the
# two adults). A fully quiet day briefs both (D-036e/D-044: partner-symmetric —
# neither is left without the morning message).
DIGEST_RECIPIENTS = ("adar", "shanee")

# ---------------------------------------------------------------------------
# Weekly briefing
# ---------------------------------------------------------------------------
WEEK_AHEAD_DAYS = 7
GOAL_MILESTONE_FLAG_DAYS = 30   # flag goals whose target date is within 30 days
STALE_GOAL_UPDATE_DAYS = 21     # warn if goal Last Update older than 3 weeks

# ---------------------------------------------------------------------------
# WhatsApp summarizer
# ---------------------------------------------------------------------------
BRIDGE_STALE_HOURS = 12          # group silence this long is suspect
HEARTBEAT_STALE_MINUTES = 45     # bridge heartbeat is written at least every 15m
WA_INBOX_RETENTION_DAYS = 30     # hot-tab rolloff horizon — 30d confirmed (D-036, 2026-06-15); SPEC §6.2 aligned. Rolloff implemented M4 (D-044, sheet.roll_off_old_rows).
DIGEST_GROUP_ORDER = ["daycare", "building", "family", "neighborhood", "student", "other"]
# Hebrew short labels, used inline per digest item (DESIGN §6: "גן — מחר יום פרי…").
# Real group names stay in the gitignored seed; these label the TYPE.
DIGEST_GROUP_LABEL = {
    "daycare": "גן", "building": "ועד", "family": "משפחה",
    "neighborhood": "שכונה", "student": "לימודים", "other": "אחר",
}

# --- Weekly classifier accuracy review (Phase F, D-048) --------------------
# The summarizer records each message's classification + outcome in WhatsApp_Inbox
# but not the rule that fired (§6.2 schema). The review surface re-derives the
# triggering rule per ALERT from the persisted row by reusing the summarizer's
# own hard_rule_alert (single source of truth) — so no Inbox schema change is
# needed. The weekly briefing carries a compact pulse; automation/accuracy_review.py
# is the full operator surface (the recurring cadence reuses family-weekly.timer).
ACCURACY_REVIEW_DAYS = 7          # trailing window the weekly surface reviews
ALERT_FP_TARGET_PER_WEEK = 1      # the bar (original WhatsApp design, Phase F):
                                  # <1 ALERT-tier false positive per week
ACCURACY_REVIEW_MAX_BRIEF = 12    # cap ALERT lines folded inline into the briefing

# ---------------------------------------------------------------------------
# Property tracker (SPEC.md §12.1, M5 — unfrozen D-034). Silent, digest-only:
# new listings land in the Sheet and surface in the 07:30 digest, never an
# alert, never a budget bypass (briefings > notifications).
# ---------------------------------------------------------------------------
PROPERTY_LISTINGS_TAB = "Property-Listings"   # scraper-written tab (SPEC §6 / §12.1)
# Saved-search URLs per portal — PERSONAL (area/price/rooms), mode 600, /etc only,
# NEVER in the repo (D-024). deploy/property_searches.example.json is the template.
PROPERTY_SEARCHES_FILE = Path("/etc/family-inc/property_searches.json")
# Last-seen listing_id set. VPS = /var/lib/family-inc/property (systemd
# StateDirectory, set via FAMILY_INC_PROPERTY_DIR in the unit); dev/tests fall
# back to the gitignored automation/cache so a local run never needs root.
PROPERTY_STATE_DIR = Path(os.environ.get("FAMILY_INC_PROPERTY_DIR")
                          or (CACHE_DIR / "property"))
PROPERTY_SEEN_FILE = PROPERTY_STATE_DIR / "seen.json"
PROPERTY_FETCH_TIMEOUT_S = 45     # per-URL headless-Chromium budget (the unit's
                                  # TimeoutStartSec/MemoryMax bound a stuck browser)
PROPERTY_MAX_PER_DIGEST = 8       # cap new-listing lines in one morning digest

# --- Apify secondary source (SPEC §12.1, D-040) ----------------------------
# SECONDARY/supplementary only: the on-box Chromium scraper above stays primary.
# Apify (its own residential proxy pool) is the backup that clears the anti-bot
# wall the VPS datacenter IP can't (D-039). Paid third party in the path → D-040
# amends D-010's "₪0 marginal" to the §11 monthly ceiling, which still governs.
APIFY_TOKEN_ENV = "FAMILY_INC_APIFY_TOKEN"   # SERVICE api key, NOT a portal login;
                                             # /etc/family-inc/env mode 600 (§8.6),
                                             # never the repo. Absent → path inert.
APIFY_BASE_URL = "https://api.apify.com/v2"
# Actor ids per portal (username~actorName) — non-secret, committed (D-040 picks).
# amit123 ingests Yad2 saved-search URLs directly; swerve is parametric (Madlan
# needs a city/dealType 'apify' block in property_searches.json — no URL input).
PROPERTY_APIFY_ACTORS = {
    "yad2": "amit123~yadscraper",
    "madlan": "swerve~madlan-scraper",
}
PROPERTY_APIFY_TIMEOUT_S = 180    # run-sync-get-dataset-items hard-caps at 300s;
                                  # the caps below keep real runs well under it
PROPERTY_APIFY_MAX_ITEMS = 100    # per-search cap for parametric actors (Madlan)
PROPERTY_APIFY_MAX_PAGES = 3      # per-search page cap for URL actors (Yad2) —
                                  # newest-first searches put new listings first
PROPERTY_APIFY_GAPFILL = True     # also fill missing fields on primary listings
                                  # from the same Apify call (D-040). False =
                                  # backup-only (blocked/empty) — the cheapest mode
PROPERTY_APIFY_ONCE_PER_DAY = True  # Apify lands at most once/calendar-day (cost:
                                  # priced per result; on-box primary stays free
                                  # 2×/day; digest is morning-only). False = every run
PROPERTY_APIFY_STAMP_FILE = PROPERTY_STATE_DIR / "apify_last_run.json"

# ---------------------------------------------------------------------------
# Finance ingestion (SPEC.md §12.2, M6 — unfrozen D-049/050/051). The Node
# scraper (automation/finance/scrape.js) writes one CSV per provider to the
# staging dir; finance_ingest.py reads them and writes via lib/sheet (the only
# Sheet writer, D-016). Silent like property — balances + spend surface in the
# weekly briefing Money section + dashboard drawer, never an alert.
# ---------------------------------------------------------------------------
# Read-only bank/card portal logins (D-049 amendment). PERSONAL, mode 600, /etc
# only, NEVER the repo. deploy/bank_creds.example.json is the template. Absent →
# the scraper fails loud (nothing to ingest), exactly like a missing config.
FINANCE_CREDS_FILE = Path("/etc/family-inc/bank_creds.json")
# Per-provider CSV staging. VPS = /var/lib/family-inc/finance (systemd
# StateDirectory, set via FAMILY_INC_FINANCE_DIR in the unit); dev/tests fall
# back to the gitignored automation/cache so a local run never needs root
# (mirrors PROPERTY_STATE_DIR). The scraper persists session state here too.
FINANCE_STATE_DIR = Path(os.environ.get("FAMILY_INC_FINANCE_DIR")
                         or (CACHE_DIR / "finance"))
# Provider → account Type label written to Finance-Accounts (bank vs card).
FINANCE_PROVIDER_TYPES = {"mizrahi": "bank", "max": "card", "cal": "card"}
# The briefing's data-hygiene line warns when an account hasn't imported in this
# many days (§12.2 stale-import). One definition — section_hygiene reads it.
FINANCE_STALE_IMPORT_DAYS = 35
# On-box categorization rules (M6.4, D-050): keyword→category, applied to every
# transaction at ingest so most never reach the LLM (§8.6). NON-personal (public
# merchant tokens + generic category labels) → committed, unlike the personal
# seeds (a `!`-exception in .gitignore overrides `seeds/*.csv`). PROVISIONAL
# vocab until Shanee's budget migration fixes the category set; the distinct
# categories here are also the only labels the gap-fill LLM may return.
FINANCE_CATEGORY_RULES = SEEDS_DIR / "14_Finance_Category_Rules.csv"

# ---------------------------------------------------------------------------
# LLM (SPEC.md §8.6–8.7 — model ids live here, not at call sites)
#
# Provider direction (D-032, wired M4/D-044): DeepSeek is the single configured
# provider, reached over its OpenAI-compatible /chat/completions endpoint with
# stdlib urllib (no new dependency). lib/llm picks the provider by which key is
# present — DeepSeek first, Anthropic if only that key is set, neither → the
# deterministic fallback (the system stays useful keyless, SPEC §3.6/§5).
# Keys live in /etc/family-inc/env (mode 600), never the repo (SPEC §8.6).
# ---------------------------------------------------------------------------
DEEPSEEK_API_KEY_ENV = "FAMILY_INC_DEEPSEEK_API_KEY"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"   # OpenAI-compatible base URL
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"      # legacy / fallback provider
LLM_TIMEOUT_S = 30                               # per-call HTTP budget (seconds)
# Active-provider (DeepSeek) model ids, keyed by task.
MODELS = {
    "classify": "deepseek-chat",    # WhatsApp triage (DeepSeek-V3)
    "briefing": "deepseek-chat",    # weekly-briefing prose
    "categorize": "deepseek-chat",  # finance gap-fill — rules-miss remainder (§8.6)
}
# Fallback-provider (Anthropic, the v1 Haiku-class path, §8.7) model ids.
ANTHROPIC_MODELS = {
    "classify": "claude-haiku-4-5",
    "briefing": "claude-haiku-4-5",
    "categorize": "claude-haiku-4-5",
}
LLM_FAKE_ENV = "FAMILY_INC_LLM_FAKE"  # tests inject a canned response here

# Indicative LLM list prices (USD per 1M tokens, (input, output)) for the weekly
# self-report spend line (ENGINEERING §8) — a health figure, NOT accounting.
# Unknown models fall back to the default. Update when a provider reprices.
LLM_PRICE_USD_PER_MTOK = {
    "deepseek-chat": (0.27, 1.10),      # DeepSeek-V3 standard tier
    "claude-haiku-4-5": (1.00, 5.00),   # Anthropic fallback (§8.7)
}
LLM_PRICE_DEFAULT_USD_PER_MTOK = (1.00, 5.00)
USD_TO_ILS = 3.7                         # coarse FX — the spend line is indicative

# ---------------------------------------------------------------------------
# Hebcal
# ---------------------------------------------------------------------------
HEBCAL_GEONAME_ID = 294801   # nearest metro (Haifa) — same coastal zman as home
HEBCAL_TTL_SECONDS = 24 * 60 * 60

# ---------------------------------------------------------------------------
# Email fallback (SPEC §10.2 — delivery layer 2) + fail-loud flag (ENG §5)
# ---------------------------------------------------------------------------
EMAIL_FALLBACK_AFTER_HOURS = 24       # heartbeat staler than this → the daily
                                      # digest degrades to SMTP (lib/mailer.py)
SMTP_DEFAULT_HOST = "smtp.gmail.com"  # overridable via SMTP_HOST/SMTP_PORT env;
SMTP_DEFAULT_PORT = 587               # creds (SMTP_USER/SMTP_PASS) env-only
EMAIL_TO_ENV = "FAMILY_INC_EMAIL_TO"  # comma-separated fallback recipients;
                                      # unset → Settings.UserMap emails
FAIL_FLAG = LOGS_DIR / "fail.flag"    # appended by family-fail-flag@.service
                                      # (systemd OnFailure=); reported + cleared
                                      # by the next delivered daily digest
DELIVERY_LOG = LOGS_DIR / "delivery_log.csv"  # one line per digest --send run
                                      # (date, transport, recipients); weekly
                                      # briefing surfaces smtp-degraded days
                                      # (review 2026-06-12, D-028)

# ---------------------------------------------------------------------------
# Secrets loading (appliance: /etc/family-inc/env, mode 600)
# ---------------------------------------------------------------------------
ENV_FILE = Path("/etc/family-inc/env")


def load_env(path: Path = ENV_FILE) -> None:
    """Load KEY=VALUE lines into os.environ (existing env wins). No-op when
    the file is absent — dev machines use their shell env instead."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

=== End: automation/lib/config.py ===

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
    // dedup per (id, target) so a crash mid-"both" still delivers the second leg
    const done = new Set(readJsonl(SENT_FILE).map((r) => `${r.id}:${r.to}`));
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
        await sock.sendMessage(jid, { text: String(row.body || '').slice(0, 4096) });
        fs.appendFileSync(SENT_FILE, JSON.stringify({
          id: row.id, to: name, status: 'sent', at: new Date().toISOString(),
        }) + '\n', 'utf-8');
        console.log(`[outbox] sent ${row.id} → ${name}`);
        done.add(`${row.id}:${name}`);
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

=== File: dashboard/app.js ===
// Family inc. dashboard — single-file SPA.
// Boring tech: vanilla JS, no build step, no framework.

(() => {
  'use strict';

  const cfg = window.FAMILY_INC_CONFIG;
  // spreadsheets: data; userinfo.email: who is tapping, so write-backs are
  // attributed via Settings.UserMap (SPEC §7.6) instead of a config guess.
  const SCOPES = 'https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/userinfo.email';
  const DISCOVERY = 'https://sheets.googleapis.com/$discovery/rest?version=v4';
  const CACHE_KEY = 'family_inc_cache_v1';
  const QUEUE_KEY = 'family_inc_writequeue_v1';
  const TOKEN_KEY = 'family_inc_token_v1';
  const MAX_PENDING_WRITES = 50;   // offline-queue cap (SPEC §7.6 / DESIGN §6) —
                                   // a one-shot warning fires at the cap, then
                                   // further taps are dropped, not silently lost

  // ---------------- i18n ----------------
  // Single source of truth for chrome strings. Hebrew is canonical; English
  // mirrors meaning, not literal legacy text. To add a key: drop it here and
  // tag the element with data-i18n="<key>" OR call t('<key>', {vars}) in JS.
  const STRINGS = {
    he: {
      // Tabbar
      'tabbar.today': 'היום',
      'tabbar.sunday': 'ראשון',
      'tabbar.settings': 'הגדרות',
      // Today screen sections
      'section.todayList': 'להיום',
      'section.todayCalendar': 'יומן היום',
      'section.next7': 'השבוע הקרוב',
      'section.domains': 'תחומים',
      // Drawers
      'drawer.money': 'כספים',
      'drawer.health': 'בריאות',
      'drawer.goals': 'יעדים',
      'drawer.car': 'רכב',
      'drawer.contracts': 'מנויים וחוזים',
      'drawer.education': 'חינוך',
      // Banner
      'banner.allClear': '✅ אין דברים דחופים',
      'banner.overdueAndToday': '🔴 {overdue} באיחור · 🟠 {today} להיום',
      'banner.overdueOnly': '🔴 {overdue} באיחור',
      'banner.todayOnly': '🟠 {today} להיום',
      // Status pill
      'pill.overdue': '{n} באיחור',
      'pill.dueToday': '{n} להיום',
      'pill.sundayReady': 'סיכום ראשון מוכן',
      // Row actions
      'row.done': '✓ בוצע',
      'row.snooze': '+ דחה',
      'row.note': '+ הערה',
      'prompt.addNote': 'הוסף הערה (תתווסף לעמודת הערות):',
      // Empty states
      'empty.nothingOnFire': 'שום דבר לא בוער. ☕',
      'empty.nothingThisWeek': 'אין אירועים השבוע.',
      'empty.noEventsToday': 'אין אירועים היום.',
      'empty.noQueuedWrites': 'אין כתיבות בתור.',
      'empty.next60Days': 'אין אירועים בחודשיים הקרובים.',
      'empty.noBudget': 'אין תקציב עדיין.',
      'empty.noRecentTxns': 'אין עסקאות אחרונות.',
      'empty.noGoals': 'אין יעדים.',
      'empty.noVehicle': 'אין רכב.',
      'empty.noRenewals': 'אין חידושים בחודשיים הקרובים.',
      'empty.noUpcoming': 'אין פריטים קרובים.',
      'empty.noOverdue': 'אין פריטים באיחור.',
      'empty.allClean': 'הכל נקי.',
      'state.allGood': 'הכל בסדר',
      'state.loading': 'טוען…',
      // Calendar
      'cal.allDay': 'כל היום',
      // Car field labels
      'car.annualTest': 'טסט שנתי',
      'car.insurance': 'ביטוח',
      'car.license': 'רישיון',
      // Generic chrome
      'label.next': 'הבא:',
      // Drawer summary templates
      'summary.upcoming': '{n} בקרוב',
      'summary.active': '{n} פעילים',
      'summary.over': '{n} חורגות',
      'summary.within60': '{n} בחודשיים הקרובים',
      // Sunday view
      'sunday.title': 'סיכום ראשון',
      'sunday.weekAhead': 'השבוע הקרוב',
      'sunday.remindersThisWeek': 'תזכורות לשבוע',
      'sunday.overdue': 'באיחור',
      'sunday.money': 'כספים',
      'sunday.goals': 'יעדים',
      'sunday.hygiene': 'תחזוקת נתונים',
      'sunday.monthToDate': 'מתחילת החודש',
      'sunday.noOverBudget': 'אף קטגוריה לא חרגה.',
      'sunday.hygienePeople': '{n} שורות באנשים עם שמות לדוגמה',
      'sunday.hygieneGoals': '{n} יעדים עם טקסט לדוגמה',
      // Settings
      'settings.account': 'חשבון',
      'settings.sheet': 'גיליון',
      'settings.language': 'שפה',
      'settings.appearance': 'מראה',
      'settings.themeLight': '☀️ בהיר',
      'settings.themeDark': '🌙 כהה',
      'settings.themeAuto': '🔄 אוטומטי',
      'settings.pendingWrites': 'כתיבות בתור',
      'settings.about': 'אודות',
      'settings.sheetIdLabel': 'מזהה הגיליון',
      'settings.sheetIdPlaceholder': 'מתוך כתובת ה-Google Sheet',
      'settings.demoModeLabel': 'מצב הדגמה',
      'settings.demoOn': 'דלוק (נתוני הדגמה)',
      'settings.demoOff': 'כבוי (גיליון אמיתי)',
      'settings.signOut': 'התנתק',
      'settings.forceRefresh': 'רענן עכשיו',
      'settings.saveReload': 'שמור וטען מחדש',
      'settings.aboutBody': 'Family inc. dashboard · v0.1 · אב-טיפוס שלב 6',
      'settings.aboutNote': 'המידע יושב בגיליון Google שלך. הדף הזה הוא תצוגה מקומית.',
      'settings.demoModeStatus': 'מצב הדגמה',
      'settings.demoNoAccount': 'לא מחובר חשבון Google.',
      'settings.signedInAs': 'מחובר כ-{name}',
      'settings.notSignedIn': 'לא מחובר.',
      'settings.langHebrew': 'עברית',
      'settings.langEnglish': 'English',
      // Stale / offline
      'stale.offline': 'לא מקוון — נתונים מ-{when}',
      // Sign-in screen
      'signin.prompt': 'התחבר עם חשבון Google שיש לו גישה לגיליון <code>Family_OS</code> שלך.',
      'signin.button': 'התחבר עם Google',
      'signin.notConfigured': 'OAuth לא מוגדר',
      'signin.demoLine': 'או <a href="#" id="demo-link">נסה עם נתוני הדגמה</a>.',
      // Error toasts
      'toast.signinFailed': 'ההתחברות נכשלה: {err}',
      'toast.oauthNotConfigured': 'OAuth לא מוגדר — ראה README_SETUP.md',
      'toast.loadFailed': 'לא הצלחתי לטעון נתונים ואין מטמון זמין.',
      'toast.gapiLoadError': 'לא הצלחתי לטעון את Google API. בדוק את החיבור לאינטרנט.',
      'toast.gisLoadError': 'לא הצלחתי לטעון את Google Sign-In. בדוק את החיבור לאינטרנט.',
      'signin.gapiLoadError': 'שגיאה בטעינת Google API',
      'signin.gisLoadError': 'שגיאה בטעינת Google Sign-In',
      'toast.sheetIdInvalid': 'מזהה גיליון לא תקין — בדוק שהוא בפורמט הנכון.',
      'toast.sheetIdTestFailed': 'לא הצלחתי לאמת את מזהה הגיליון: {err}',
      'toast.demoPrefix': '(הדגמה) {label}',
      'toast.queuedOffline': 'נשמר בתור לא מקוון: {label}',
      'toast.queued': 'נשמר בתור: {label}',
      'toast.queueFull': 'התור מלא ({max}) — התחברו לאינטרנט כדי לסנכרן לפני שמירת פעולות נוספות',
      'toast.flushed': 'הוזרמו {n} פעולות מהתור',
      // Action labels (used in toasts after write-back)
      'action.markedDone': 'בוצע: {title}',
      'action.snoozed': 'נדחה ב-+{days}d: {title}',
      'action.noteAdded': 'הערה נוספה',
    },
    en: {
      'tabbar.today': 'Today',
      'tabbar.sunday': 'Sunday',
      'tabbar.settings': 'Settings',
      'section.todayList': 'For today',
      'section.todayCalendar': "Today's calendar",
      'section.next7': 'This coming week',
      'section.domains': 'Domains',
      'drawer.money': 'Money',
      'drawer.health': 'Health',
      'drawer.goals': 'Goals',
      'drawer.car': 'Car',
      'drawer.contracts': 'Subscriptions & contracts',
      'drawer.education': 'Education',
      'banner.allClear': '✅ Nothing urgent',
      'banner.overdueAndToday': '🔴 {overdue} overdue · 🟠 {today} due today',
      'banner.overdueOnly': '🔴 {overdue} overdue',
      'banner.todayOnly': '🟠 {today} due today',
      'pill.overdue': '{n} overdue',
      'pill.dueToday': '{n} due today',
      'pill.sundayReady': 'Sunday briefing ready',
      'row.done': '✓ done',
      'row.snooze': '+ snooze',
      'row.note': '+ note',
      'prompt.addNote': 'Add a note (will be appended to the Notes column):',
      'empty.nothingOnFire': 'Nothing on fire. ☕',
      'empty.nothingThisWeek': 'Nothing scheduled this week.',
      'empty.noEventsToday': 'No events today.',
      'empty.noQueuedWrites': 'No queued writes.',
      'empty.next60Days': 'Nothing in the next two months.',
      'empty.noBudget': 'No budget yet.',
      'empty.noRecentTxns': 'No recent transactions.',
      'empty.noGoals': 'No goals yet.',
      'empty.noVehicle': 'No vehicle.',
      'empty.noRenewals': 'No renewals in the next two months.',
      'empty.noUpcoming': 'No upcoming items.',
      'empty.noOverdue': 'No overdue items.',
      'empty.allClean': 'All clean.',
      'state.allGood': 'All good',
      'state.loading': 'Loading…',
      'cal.allDay': 'all day',
      'car.annualTest': 'Annual test',
      'car.insurance': 'Insurance',
      'car.license': 'License',
      'label.next': 'next:',
      'summary.upcoming': '{n} upcoming',
      'summary.active': '{n} active',
      'summary.over': '{n} over',
      'summary.within60': '{n} in next two months',
      'sunday.title': 'Sunday Briefing',
      'sunday.weekAhead': 'Week ahead',
      'sunday.remindersThisWeek': 'Reminders this week',
      'sunday.overdue': 'Overdue',
      'sunday.money': 'Money',
      'sunday.goals': 'Goals',
      'sunday.hygiene': 'Data hygiene',
      'sunday.monthToDate': 'Month-to-date',
      'sunday.noOverBudget': 'No categories over budget.',
      'sunday.hygienePeople': '{n} People row(s) using placeholder names',
      'sunday.hygieneGoals': '{n} Goal(s) using placeholder text',
      'settings.account': 'Account',
      'settings.sheet': 'Sheet',
      'settings.language': 'Language',
      'settings.appearance': 'Appearance',
      'settings.themeLight': '☀️ Light',
      'settings.themeDark': '🌙 Dark',
      'settings.themeAuto': '🔄 Auto',
      'settings.pendingWrites': 'Pending writes',
      'settings.about': 'About',
      'settings.sheetIdLabel': 'Sheet ID',
      'settings.sheetIdPlaceholder': 'from Google Sheet URL',
      'settings.demoModeLabel': 'Demo mode',
      'settings.demoOn': 'On (use mock data)',
      'settings.demoOff': 'Off (live Google Sheet)',
      'settings.signOut': 'Sign out',
      'settings.forceRefresh': 'Force refresh',
      'settings.saveReload': 'Save & reload',
      'settings.aboutBody': 'Family inc. dashboard · v0.1 · Phase 6 prototype',
      'settings.aboutNote': 'Data lives in your Google Sheet. This page is a local view.',
      'settings.demoModeStatus': 'Demo mode',
      'settings.demoNoAccount': 'No Google account is connected.',
      'settings.signedInAs': 'Signed in as {name}',
      'settings.notSignedIn': 'Not signed in.',
      'settings.langHebrew': 'עברית',
      'settings.langEnglish': 'English',
      'stale.offline': 'Offline — data from {when}',
      'signin.prompt': 'Sign in with the Google account that has access to your <code>Family_OS</code> sheet.',
      'signin.button': 'Sign in with Google',
      'signin.notConfigured': 'OAuth not configured',
      'signin.demoLine': 'Or <a href="#" id="demo-link">try with demo data</a>.',
      'toast.signinFailed': 'Sign-in failed: {err}',
      'toast.oauthNotConfigured': 'OAuth not configured — see README_SETUP.md',
      'toast.loadFailed': 'Could not load data and no cache available.',
      'toast.gapiLoadError': 'Could not load Google sign-in. Check your connection.',
      'toast.gisLoadError': 'Could not load Google sign-in. Check your connection.',
      'signin.gapiLoadError': 'Could not load Google sign-in',
      'signin.gisLoadError': 'Could not load Google sign-in',
      'toast.sheetIdInvalid': 'Invalid Sheet ID — check the format and try again.',
      'toast.sheetIdTestFailed': 'Could not verify Sheet ID: {err}',
      'toast.demoPrefix': '(demo) {label}',
      'toast.queuedOffline': 'Queued offline: {label}',
      'toast.queued': 'Queued: {label}',
      'toast.queueFull': 'Queue full ({max}) — reconnect to sync before queuing more',
      'toast.flushed': 'Flushed {n} queued action(s)',
      'action.markedDone': '{title} → done',
      'action.snoozed': '{title} → +{days}d',
      'action.noteAdded': 'Note added',
    },
  };
  function currentLang() {
    return document.documentElement.lang === 'en' ? 'en' : 'he';
  }
  function t(key, vars) {
    const dict = STRINGS[currentLang()] || STRINGS.he;
    let s = dict[key];
    if (s == null) s = key; // fail visibly if a key is missing
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        s = s.split(`{${k}}`).join(String(v));
      }
    }
    return s;
  }
  // Walks the DOM once at boot and replaces text content of any element tagged
  // with data-i18n="<key>". The English text in index.html is a fallback that
  // shows if JS fails to run. data-i18n-html does innerHTML — use only for keys
  // we control (e.g. signin.demoLine which embeds a known anchor).
  function applyChromeStrings() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const v = t(key);
      if (v != null && v !== key) el.textContent = v;
    });
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const key = el.dataset.i18nHtml;
      const v = t(key);
      if (v != null && v !== key) el.innerHTML = v;
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.dataset.i18nPlaceholder;
      const v = t(key);
      if (v != null && v !== key) el.setAttribute('placeholder', v);
    });
  }

  // ---------------- State ----------------
  const state = {
    user: null,           // {email, name}
    token: null,
    data: null,           // parsed sheet data
    cachedAt: null,
    tab: 'today',
    pendingWrites: [],
    queueFullWarned: false,   // one-shot: warn once at the cap, reset after a flush
    today: stripTime(new Date()),
    tokenClient: null,
    gapiReady: false,
    gisReady: false,
  };

  // ---------------- Utilities ----------------
  function stripTime(d) {
    const x = new Date(d);
    x.setHours(0, 0, 0, 0);
    return x;
  }
  function daysBetween(a, b) {
    return Math.round((stripTime(a) - stripTime(b)) / (1000 * 60 * 60 * 24));
  }
  // Intl-based formatters (Hebrew locale). Defined as helpers so RTL copy "just works".
  const _ilsFmt = new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });
  const _dateHEFmt = new Intl.DateTimeFormat('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const _dateHEShortFmt = new Intl.DateTimeFormat('he-IL', { day: '2-digit', month: '2-digit' });

  function formatILS(n) {
    if (n == null || isNaN(n)) return '';
    return _ilsFmt.format(Math.round(n));
  }
  function formatDateHE(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return _dateHEFmt.format(d);
  }
  // Back-compat wrappers — old call sites still work, now wired to Hebrew formatting.
  function fmtDate(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return _dateHEShortFmt.format(d);
  }
  // Sub-shorthand: just "D.M" (e.g. "7.6") for the Sunday header date range.
  // Intl emits a trailing dot in he-IL for this style; we hand-format to skip it.
  function fmtDateShort(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return `${d.getDate()}.${d.getMonth() + 1}`;
  }
  function fmtILS(n) { return formatILS(n); }
  // Wraps an amount string in an isolated bidi span so ₪ + Hebrew text don't reorder.
  function amountHtml(n) {
    const s = formatILS(n);
    if (!s) return '';
    return `<span class="amount bidi-amount">${escapeHtml(s)}</span>`;
  }
  function fmtISO(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
  // Full local ISO datetime (with T, no timezone — naive local, matching the
  // engine). Used for the machine stamps DoneAt + WriteQueue_Tombstone: the
  // T-form stays a TEXT cell in Sheets, so it round-trips byte-exact and the
  // 6h tombstone window keeps hour resolution (a date-only tombstone looks
  // hours old the moment it's written — that race guard was dead, SPEC §8.3).
  function fmtISOts(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    const p = (n) => String(n).padStart(2, '0');
    return `${fmtISO(d)}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }
  function parseDate(v) {
    if (!v) return null;
    if (v instanceof Date) return isNaN(v) ? null : v;
    if (typeof v === 'number') {
      // Excel serial — used if we ever roundtrip from xlsx, but Sheets API
      // returns formatted strings, so this branch is rare.
      return new Date(Math.round((v - 25569) * 86400 * 1000));
    }
    const d = new Date(v);
    return isNaN(d) ? null : d;
  }
  function flagFor(daysUntil, status) {
    if (status === 'Done' || status === 'Skipped') return '';
    if (daysUntil == null || isNaN(daysUntil)) return '';
    if (daysUntil < 0) return 'OVERDUE';
    if (daysUntil <= 1) return 'FIRE TODAY';
    if (daysUntil <= 7) return 'WEEK OUT';
    if (daysUntil <= 30) return 'MONTH OUT';
    return '';
  }
  function flagEmoji(f) {
    return { 'OVERDUE': '🔴', 'FIRE TODAY': '🟠', 'WEEK OUT': '🟡', 'MONTH OUT': '🟢' }[f] || '·';
  }
  function flagClass(f) {
    return { 'OVERDUE': 'flag-OVERDUE', 'FIRE TODAY': 'flag-FIRE', 'WEEK OUT': 'flag-WEEK', 'MONTH OUT': 'flag-MONTH' }[f] || '';
  }
  function duePhrase(daysUntil) {
    if (daysUntil == null) return '';
    if (currentLang() === 'he') {
      // Hebrew grammar: singular (יום), dual (יומיים), plural (ימים).
      if (daysUntil < 0) {
        const abs = -daysUntil;
        if (abs === 1) return 'באיחור של יום';
        if (abs === 2) return 'באיחור של יומיים';
        return `באיחור של ${abs} ימים`;
      }
      if (daysUntil === 0) return 'להיום';
      if (daysUntil === 1) return 'מחר';
      if (daysUntil === 2) return 'בעוד יומיים';
      return `בעוד ${daysUntil} ימים`;
    }
    if (daysUntil < 0) return `overdue by ${-daysUntil}d`;
    if (daysUntil === 0) return 'due today';
    if (daysUntil === 1) return 'due tomorrow';
    return `in ${daysUntil}d`;
  }
  function toast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2200);
  }
  function colLetter(n) {
    // 1 → A, 27 → AA
    let s = '';
    while (n > 0) {
      const r = (n - 1) % 26;
      s = String.fromCharCode(65 + r) + s;
      n = Math.floor((n - 1) / 26);
    }
    return s;
  }

  // ---------------- Auth ----------------
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src; s.async = true; s.defer = true;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Failed to load ' + src));
      document.head.appendChild(s);
    });
  }

  async function initAuth() {
    if (cfg.DEMO_MODE) return;
    if (!cfg.CLIENT_ID || cfg.CLIENT_ID.startsWith('PASTE_')) return;

    try {
      await loadScript('https://apis.google.com/js/api.js');
    } catch {
      const btn = document.getElementById('signin-btn');
      if (btn) { btn.textContent = t('signin.gapiLoadError'); btn.disabled = true; }
      toast(t('toast.gapiLoadError'));
      return;
    }
    await new Promise((resolve) => gapi.load('client', resolve));
    await gapi.client.init({ discoveryDocs: [DISCOVERY] });
    state.gapiReady = true;

    try {
      await loadScript('https://accounts.google.com/gsi/client');
    } catch {
      const btn = document.getElementById('signin-btn');
      if (btn) { btn.textContent = t('signin.gisLoadError'); btn.disabled = true; }
      toast(t('toast.gisLoadError'));
      return;
    }
    state.tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: cfg.CLIENT_ID,
      scope: SCOPES,
      callback: (resp) => {
        if (resp.error) { toast(t('toast.signinFailed', { err: resp.error })); return; }
        state.token = resp;
         localStorage.setItem(TOKEN_KEY, JSON.stringify({ access_token: resp.access_token, expires_at: Date.now() + (resp.expires_in * 1000) }));
        afterSignIn();
      },
    });
    state.gisReady = true;

    // Restore session token if still valid (avoids forcing sign-in every reload).
    const saved = localStorage.getItem(TOKEN_KEY);
    if (saved) {
      try {
        const t = JSON.parse(saved);
        if (t.expires_at > Date.now() + 60000) {
          gapi.client.setToken({ access_token: t.access_token });
          state.token = t;
          afterSignIn();
        }
      } catch {}
    }
  }

  function requestSignIn() {
    if (!state.tokenClient) {
      toast(t('toast.oauthNotConfigured'));
      return;
    }
    state.tokenClient.requestAccessToken({ prompt: 'consent' });
  }

  function signOut() {
    localStorage.removeItem(TOKEN_KEY);
    state.token = null;
    state.user = null;
    if (window.google?.accounts?.oauth2) {
      google.accounts.oauth2.revoke(gapi.client.getToken()?.access_token, () => {});
    }
    showSignIn();
  }

  async function afterSignIn() {
    // Who signed in? userinfo.email scope → email; the display name comes
    // from Settings.UserMap once the Sheet loads (SPEC §7.6: Google sign-in
    // → Settings.UserMap → display name). cfg.USERS stays as the offline /
    // pre-Settings fallback.
    try {
      const token = gapi.client.getToken()?.access_token;
      const resp = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const info = resp.ok ? await resp.json() : {};
      const email = (info.email || '').toLowerCase();
      state.user = { email: email || 'unknown', name: resolveDisplayName(email) };
    } catch (e) {
      console.warn('Could not resolve signed-in identity', e);
      const emails = Object.keys(cfg.USERS || {});
      state.user = { email: emails[0] || 'unknown', name: (cfg.USERS || {})[emails[0]] || 'You' };
    }
    showApp();
    await loadAll();
    // Settings tab is loaded now — upgrade the display name if UserMap knows us.
    if (state.user) state.user.name = resolveDisplayName(state.user.email);
  }

  // Settings.UserMap (email → display name) → cfg.USERS fallback → 'You'.
  function resolveDisplayName(email) {
    const fromSheet = state.data?.settings?.userMap?.[email];
    if (fromSheet) return fromSheet;
    const fromCfg = (cfg.USERS || {})[email];
    if (fromCfg) return fromCfg;
    // Unknown signer: fall back to the first configured user (pre-M2 behavior)
    const emails = Object.keys(cfg.USERS || {});
    return (cfg.USERS || {})[emails[0]] || 'You';
  }

  // ---------------- Data load ----------------
  async function loadAll() {
    if (cfg.DEMO_MODE) {
      const resp = await fetch('mock_data.json');
      const json = await resp.json();
      state.data = parseAll(json);
      state.cachedAt = new Date();
      renderAll();
      return;
    }
    try {
      const tabs = cfg.TABS;
      // Order matters — keep in sync with `named` below.
      const ranges = [
        `${tabs.reminders}!A:O`,
        `${tabs.calendarEvents}!A:H`,
        `${tabs.people}!A:I`,
        `${tabs.finance_bdgt}!A:I`,
        `${tabs.finance_txns}!A:I`,
        `${tabs.goals}!A:I`,
        `${tabs.health}!A:I`,
        `${tabs.education}!A:I`,
        `${tabs.car}!A:I`,
        `${tabs.contracts}!A:I`,
        `${tabs.settings || 'Settings'}!A:B`,
      ];
      const resp = await gapi.client.sheets.spreadsheets.values.batchGet({
        spreadsheetId: cfg.SHEET_ID,
        ranges,
        valueRenderOption: 'UNFORMATTED_VALUE',
        dateTimeRenderOption: 'FORMATTED_STRING',
      });
      const named = {
        reminders: resp.result.valueRanges[0].values || [],
        calendarEvents: resp.result.valueRanges[1].values || [],
        people: resp.result.valueRanges[2].values || [],
        finance_bdgt: resp.result.valueRanges[3].values || [],
        finance_txns: resp.result.valueRanges[4].values || [],
        goals: resp.result.valueRanges[5].values || [],
        health: resp.result.valueRanges[6].values || [],
        education: resp.result.valueRanges[7].values || [],
        car: resp.result.valueRanges[8].values || [],
        contracts: resp.result.valueRanges[9].values || [],
        settings: resp.result.valueRanges[10]?.values || [],
      };
      state.data = parseAll(named);
      state.cachedAt = new Date();
      localStorage.setItem(CACHE_KEY, JSON.stringify({ raw: named, at: state.cachedAt.toISOString() }));
      applySheetLang();
      renderAll();
      await flushQueue();
    } catch (e) {
      console.error('Live load failed', e);
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const { raw, at } = JSON.parse(cached);
        state.data = parseAll(raw);
        state.cachedAt = new Date(at);
        document.getElementById('stale-badge').hidden = false;
        document.getElementById('stale-badge').textContent = t('stale.offline', { when: state.cachedAt.toLocaleString() });
        renderAll();
      } else {
        toast(t('toast.loadFailed'));
      }
    }
  }

  // Settings.lang is the cross-device DEFAULT chrome language; an explicit
  // local toggle (localStorage.familyinc.lang) always wins (DESIGN §7).
  function applySheetLang() {
    let saved = null;
    try { saved = localStorage.getItem('familyinc.lang'); } catch {}
    if (saved) return; // personal preference wins
    const sheetLang = state.data?.settings?.lang;
    if ((sheetLang === 'en' || sheetLang === 'he') && sheetLang !== currentLang()) {
      document.documentElement.setAttribute('lang', sheetLang);
      document.documentElement.setAttribute('dir', sheetLang === 'en' ? 'ltr' : 'rtl');
      applyChromeStrings();
    }
  }

  // ---------------- Parsers ----------------
  // Sheet tab → header row (row 1) + data rows (row 2+).
  // Each parsed row carries its 1-based sheet row number as `_row` so writes
  // can target the right cell.
  function rowsToObjects(rows) {
    if (!rows || rows.length < 2) return [];
    const headers = rows[0];
    return rows.slice(1).map((r, i) => {
      const o = { _row: i + 2 };
      headers.forEach((h, j) => { o[h] = r[j] ?? null; });
      return o;
    });
  }

  function parseAll(named) {
    const reminders = rowsToObjects(named.reminders).map(r => {
      const due = parseDate(r['Due Date']);
      const daysUntil = due ? daysBetween(due, state.today) : null;
      const status = r['Status'] || 'Pending';
      return {
        _row: r._row,
        title: r['Title'] || '',
        domain: r['Domain'] || '',
        owner: r['Owner'] || '',
        due,
        leads: (r['Lead Times'] ?? r['Lead Times (days)'] ?? '').toString().split(',').map(x => parseInt(x, 10)).filter(x => !isNaN(x)),
        recurrence: r['Recurrence'] || 'One-off',
        status,
        lastSent: parseDate(r['Last Sent']),
        channel: r['Channel'] || '',
        notes: r['Notes'] || '',
        daysUntil,
        flag: flagFor(daysUntil, status),
        // Phase 6.1 columns (cols M, N, O) — may be blank on legacy sheets
        lastDoneBy: (r['LastDoneBy'] || '').trim(),
        doneAt: parseDate(r['DoneAt']),
        writeQueueTombstone: parseDate(r['WriteQueue_Tombstone']),
      };
    });
    const calendarEvents = rowsToObjects(named.calendarEvents).map(r => ({
      _row: r._row,
      date: parseDate(r['Date']),
      start: r['Start'] || '',
      end: r['End'] || '',
      title: r['Title'] || '',
      owner: r['Owner'] || '',
      source: r['Source'] || '',
      location: r['Location'] || '',
      notes: r['Notes'] || '',
    }));
    const people = rowsToObjects(named.people);
    // Settings tab (SPEC §6.4): Key|Value rows — keys containing '@' build
    // UserMap (email → display name); key 'lang' is the chrome default.
    const settings = { userMap: {}, lang: null };
    (named.settings || []).slice(1).forEach(row => {
      const key = String(row?.[0] ?? '').trim();
      const value = String(row?.[1] ?? '').trim();
      if (!key || !value) return;
      if (key.includes('@')) settings.userMap[key.toLowerCase()] = value;
      else if (key.toLowerCase() === 'lang') settings.lang = value;
    });
    const budget = rowsToObjects(named.finance_bdgt).map(r => ({
      category: r['Category'],
      target: parseFloat(r['Monthly Target (ILS)']) || 0,
      actual: parseFloat(r['Actual (current month)']) || 0,
      pct: parseFloat(r['% of Target']) || 0,
    })).filter(b => b.category && b.category !== 'Category');
    const txns = rowsToObjects(named.finance_txns).map(r => ({
      date: parseDate(r['Date']),
      account: r['Account'],
      desc: r['Description'],
      amount: parseFloat(r['Amount (ILS)']) || 0,
      category: r['Category'],
    }));
    const goals = rowsToObjects(named.goals).map(r => ({
      _row: r._row,
      goal: r['Goal'],
      owner: r['Owner'],
      horizon: r['Horizon'],
      targetDate: parseDate(r['Target Date']),
      milestone: r['90-Day Milestone'],
      pct: parseFloat(r['% Complete']) || 0,
      status: r['Status'],
    })).filter(g => g.goal);
    const health = rowsToObjects(named.health).map(r => ({
      person: r['Person'],
      provider: r['Provider'],
      specialty: r['Specialty'],
      nextDue: parseDate(r['Next Due']),
      action: r['Action Needed'],
    })).filter(h => h.person);
    const education = rowsToObjects(named.education).map(r => ({
      child: r['Child'],
      institution: r['Institution'],
      nextDate: parseDate(r['Next Key Date']),
      type: r['Type'],
      action: r['Action Needed'],
    })).filter(e => e.child);
    const car = rowsToObjects(named.car).map(r => ({
      vehicle: r['Vehicle'],
      plate: r['Plate'],
      test: parseDate(r['Annual Test (Rishui)']),
      insurance: parseDate(r['Insurance Renewal']),
      license: parseDate(r['License Expiry']),
    })).filter(c => c.vehicle);
    const contracts = rowsToObjects(named.contracts).map(r => ({
      contract: r['Contract'],
      provider: r['Provider'],
      type: r['Type'],
      renewal: parseDate(r['Renewal Date']),
      monthly: parseFloat(r['Monthly Cost (ILS)']) || 0,
    })).filter(c => c.contract);

    return { reminders, calendarEvents, people, budget, txns, goals, health, education, car, contracts, settings };
  }

  // ---------------- Render ----------------
  function renderAll() {
    // Header date is chrome — route through currentLang() so the toggle
    // actually flips the most prominent label on the screen. he-IL and en-GB
    // both render DD/MM date order, which matches Israeli reading habits in
    // either language.
    const _hdrLocale = currentLang() === 'en' ? 'en-GB' : 'he-IL';
    document.getElementById('header-date').textContent = state.today.toLocaleDateString(_hdrLocale, { weekday: 'long', day: 'numeric', month: 'long' });
    renderBanner();
    renderStatusPill();
    renderToday();
    renderTodayCalendar();
    renderNext7();
    renderDrawers();
    renderSunday();
    renderSettings();
  }

  // ---------------- Status pill ----------------
  function setStatusPill(text) {
    const pill = document.getElementById('status-pill');
    const txt = document.getElementById('status-pill-text');
    if (!pill || !txt) return;
    if (!text) {
      pill.hidden = true;
      txt.textContent = '';
      return;
    }
    txt.textContent = text;
    pill.hidden = false;
  }
  function renderStatusPill() {
    const r = state.data.reminders;
    const overdue = r.filter(x => x.flag === 'OVERDUE').length;
    const todayCount = r.filter(x => x.flag === 'FIRE TODAY').length;
    const dow = state.today.getDay(); // 0 = Sunday
    let msg = '';
    if (overdue > 0) {
      msg = t('pill.overdue', { n: overdue });
    } else if (todayCount > 0) {
      msg = t('pill.dueToday', { n: todayCount });
    } else if (dow === 0) {
      msg = t('pill.sundayReady');
    }
    setStatusPill(msg);
  }

  // ---------------- Sparkline + KPI ----------------
  function renderSparkline(svgEl, points) {
    if (!svgEl) return;
    if (!points || points.length < 2) { svgEl.innerHTML = ''; return; }
    const w = 80, h = 24, pad = 2;
    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = max - min || 1;
    const step = (w - pad * 2) / (points.length - 1);
    const coords = points.map((p, i) => {
      const x = pad + i * step;
      const y = h - pad - ((p - min) / range) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    svgEl.innerHTML = `<polyline points="${coords}" />`;
  }
  function renderKpi(drawerName, value, trend) {
    const kpiEl = document.getElementById(`${drawerName}-kpi`);
    if (!kpiEl) return;
    if (value == null || value === '') {
      kpiEl.textContent = '';
      kpiEl.classList.remove('kpi-pos', 'kpi-neg');
      return;
    }
    kpiEl.textContent = value;
    kpiEl.classList.toggle('kpi-pos', trend === 'pos');
    kpiEl.classList.toggle('kpi-neg', trend === 'neg');
  }

  // ---------------- Goal bright-line viz ----------------
  // Renders a small Beeminder-style chart:
  //   - target band (straight line from targetStart at t=0 → targetEnd at t=100%)
  //   - actual line (from 0 at start to `current` at pctTimeElapsed)
  //   - safety bands tinted around the target line
  function renderGoalLine(svgEl, { targetStart = 0, targetEnd = 100, current = 0, pctTimeElapsed = 0 } = {}) {
    if (!svgEl) return;
    const w = 100, h = 40, pad = 2;
    const yFor = (v) => {
      const clamped = Math.max(0, Math.min(100, v));
      return h - pad - (clamped / 100) * (h - pad * 2);
    };
    const xNow = Math.max(0, Math.min(100, pctTimeElapsed));
    const yT0 = yFor(targetStart);
    const yT1 = yFor(targetEnd);
    const yA0 = yFor(targetStart);
    const yA1 = yFor(current);
    // Safety bands (±5% of target line). Build as polygons spanning full width.
    const targetTopBand = `M 0,${yFor(Math.min(100, targetStart + 5))} L 100,${yFor(Math.min(100, targetEnd + 5))} L 100,0 L 0,0 Z`;
    const okBand        = `M 0,${yFor(Math.min(100, targetStart + 5))} L 100,${yFor(Math.min(100, targetEnd + 5))} L 100,${yFor(Math.max(0, targetEnd - 5))} L 0,${yFor(Math.max(0, targetStart - 5))} Z`;
    const badBand       = `M 0,${yFor(Math.max(0, targetStart - 5))} L 100,${yFor(Math.max(0, targetEnd - 5))} L 100,${h} L 0,${h} Z`;
    svgEl.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svgEl.setAttribute('preserveAspectRatio', 'none');
    svgEl.innerHTML = `
      <path class="band-ok"   d="${targetTopBand}" />
      <path class="band-warn" d="${okBand}" />
      <path class="band-bad"  d="${badBand}" />
      <polyline class="target-line" points="0,${yT0} 100,${yT1}" />
      <polyline class="actual-line" points="0,${yA0} ${xNow},${yA1}" />
      <circle class="now-dot" cx="${xNow}" cy="${yA1}" r="2" />
    `;
  }

  function renderBanner() {
    const r = state.data.reminders;
    const overdue = r.filter(x => x.flag === 'OVERDUE').length;
    const today = r.filter(x => x.flag === 'FIRE TODAY').length;
    const banner = document.getElementById('banner');
    if (overdue > 0 && today > 0) {
      banner.className = 'banner alert';
      banner.textContent = t('banner.overdueAndToday', { overdue, today });
    } else if (overdue > 0) {
      banner.className = 'banner alert';
      banner.textContent = t('banner.overdueOnly', { overdue });
    } else if (today > 0) {
      banner.className = 'banner warn';
      banner.textContent = t('banner.todayOnly', { today });
    } else {
      banner.className = 'banner clear';
      banner.textContent = t('banner.allClear');
    }
  }

  function renderToday() {
    const list = state.data.reminders
      .filter(r => r.flag === 'OVERDUE' || r.flag === 'FIRE TODAY')
      .sort((a, b) => (a.daysUntil ?? 9e9) - (b.daysUntil ?? 9e9));
    const el = document.getElementById('today-list');
    if (!list.length) {
      el.innerHTML = `<div class="empty-caught-up">${escapeHtml(t('empty.nothingOnFire'))} <span class="empty-date">${escapeHtml(formatDateHE(state.today))}</span></div>`;
      return;
    }
    el.innerHTML = list.map(renderReminderRow).join('');
    attachRowHandlers(el);
  }

  function renderNext7() {
    const list = state.data.reminders
      .filter(r => r.flag === 'WEEK OUT')
      .sort((a, b) => (a.daysUntil ?? 9e9) - (b.daysUntil ?? 9e9));
    const events = state.data.calendarEvents
      .filter(e => e.date && daysBetween(e.date, state.today) >= 1 && daysBetween(e.date, state.today) <= 7)
      .sort((a, b) => a.date - b.date);
    const el = document.getElementById('next7-list');
    let html = '';
    list.forEach(r => { html += renderReminderRow(r); });
    events.forEach(e => {
      const d = daysBetween(e.date, state.today);
      html += `<div class="row cal-event">
        <div class="row-top">
          <span class="row-title">📆 ${escapeHtml(e.title)}</span>
          <span class="row-meta">${fmtDate(e.date)} ${e.start || ''}</span>
        </div>
        ${e.location ? `<div class="row-note">${escapeHtml(e.location)}${e.owner ? ' · ' + escapeHtml(e.owner) : ''}</div>` : ''}
      </div>`;
    });
    el.innerHTML = html || `<div class="empty">${escapeHtml(t('empty.nothingThisWeek'))}</div>`;
    attachRowHandlers(el);
  }

  function renderTodayCalendar() {
    const todays = state.data.calendarEvents.filter(e => e.date && daysBetween(e.date, state.today) === 0);
    const el = document.getElementById('today-cal');
    if (!todays.length) {
      el.innerHTML = `<div class="empty">${escapeHtml(t('empty.noEventsToday'))}</div>`;
      return;
    }
    el.innerHTML = todays.map(e => `
      <div class="row cal-event">
        <div class="row-top">
          <span class="row-title">${escapeHtml(e.title)}</span>
          <span class="row-meta cal-time">${e.start || escapeHtml(t('cal.allDay'))}${e.end ? '–' + e.end : ''}</span>
        </div>
        ${e.location ? `<div class="row-note">${escapeHtml(e.location)}${e.owner ? ' · ' + escapeHtml(e.owner) : ''}</div>` : ''}
      </div>
    `).join('');
  }

  function renderReminderRow(r) {
    const emoji = flagEmoji(r.flag);
    const cls = flagClass(r.flag);
    return `<div class="row" data-row="${r._row}" data-id="${r._row}">
      <div class="row-top">
        <span class="row-title"><span class="flag ${cls}">${emoji}</span> ${escapeHtml(r.title)}</span>
        <span class="row-meta">${duePhrase(r.daysUntil)}</span>
      </div>
      ${r.notes ? `<div class="row-note">${escapeHtml(r.notes)}</div>` : ''}
      <div class="actions">
        <button class="action-btn primary" data-act="done">${escapeHtml(t('row.done'))}</button>
        <button class="action-btn" data-act="snooze">${escapeHtml(t('row.snooze'))}</button>
        <button class="action-btn" data-act="note">${escapeHtml(t('row.note'))}</button>
      </div>
      <div class="snooze-pills">
        ${[1,3,7,14,30].map(n => `<button class="snooze-pill" data-snooze="${n}">+${n}d</button>`).join('')}
      </div>
    </div>`;
  }

  function attachRowHandlers(container) {
    container.querySelectorAll('.row[data-row]').forEach(rowEl => {
      rowEl.addEventListener('click', (ev) => {
        const actBtn = ev.target.closest('[data-act]');
        const snoozeBtn = ev.target.closest('[data-snooze]');
        if (snoozeBtn) {
          ev.stopPropagation();
          const days = parseInt(snoozeBtn.dataset.snooze, 10);
          handleSnooze(rowEl.dataset.row, days);
          return;
        }
        if (actBtn) {
          ev.stopPropagation();
          const act = actBtn.dataset.act;
          if (act === 'done') handleDone(rowEl.dataset.row);
          else if (act === 'snooze') rowEl.classList.toggle('snoozing');
          else if (act === 'note') handleAddNote(rowEl.dataset.row);
          return;
        }
        rowEl.classList.toggle('expanded');
        rowEl.classList.remove('snoozing');
      });
    });
  }

  // ---------------- Drawers ----------------
  function renderDrawers() {
    // Money
    const totalTarget = state.data.budget.reduce((s, b) => s + b.target, 0);
    const totalActual = state.data.budget.reduce((s, b) => s + b.actual, 0);
    const overBudget = state.data.budget.filter(b => b.pct > 1.0);
    document.getElementById('money-summary').textContent = `${formatILS(totalActual)} / ${formatILS(totalTarget)}${overBudget.length ? ` · ${t('summary.over', { n: overBudget.length })}` : ''}`;
    document.getElementById('money-body').innerHTML = state.data.budget.map(b => `
      <div class="kv"><span>${escapeHtml(b.category)}</span><span class="v">${amountHtml(b.actual)} / ${amountHtml(b.target)} (${Math.round(b.pct * 100)}%)</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noBudget'))}</div>`;

    // D4: Surface recent transactions (last 10) below the budget breakdown.
    const recentTxns = (state.data.txns || [])
      .filter(tx => tx.date)
      .sort((a, b) => b.date - a.date)
      .slice(0, 10);
    const txnHtml = recentTxns.map(tx => `
      <div class="kv"><span>${escapeHtml(formatDateHE(tx.date))} · ${escapeHtml(tx.desc || tx.account || '')}</span><span class="v">${amountHtml(tx.amount)}</span></div>
    `).join('');
    const recentEl = document.getElementById('money-recent-txns');
    if (recentEl) {
      recentEl.innerHTML = txnHtml || `<div class="empty">${escapeHtml(t('empty.noRecentTxns'))}</div>`;
    }

    // Money KPI: % of monthly target. Sparkline: last 7 days of txn totals.
    const moneyPct = totalTarget ? Math.round(100 * totalActual / totalTarget) : null;
    renderKpi('money', moneyPct == null ? '' : `${moneyPct}%`, moneyPct != null && moneyPct > 100 ? 'neg' : 'pos');
    renderSparkline(document.getElementById('money-spark'), txnTrend7d());

    // Health (next 60d)
    const upcomingHealth = state.data.health
      .filter(h => h.nextDue && daysBetween(h.nextDue, state.today) <= 60 && daysBetween(h.nextDue, state.today) >= -30)
      .sort((a, b) => a.nextDue - b.nextDue);
    document.getElementById('health-summary').textContent = upcomingHealth.length ? t('summary.upcoming', { n: upcomingHealth.length }) : t('state.allGood');
    document.getElementById('health-body').innerHTML = upcomingHealth.map(h => `
      <div class="kv"><span>${escapeHtml(h.person)} · ${escapeHtml(h.specialty || h.provider || '')}</span><span class="v">${escapeHtml(formatDateHE(h.nextDue))}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.next60Days'))}</div>`;
    renderKpi('health', upcomingHealth.length ? String(upcomingHealth.length) : '', upcomingHealth.length ? 'neg' : 'pos');
    // No numeric trend for health — leave sparkline empty.
    renderSparkline(document.getElementById('health-spark'), null);

    // Goals
    document.getElementById('goals-summary').textContent = t('summary.active', { n: state.data.goals.length });
    document.getElementById('goals-body').innerHTML = state.data.goals.map((g, i) => {
      const pctTimeElapsed = goalPctTimeElapsed(g);
      return `
      <div class="kv goal-kv" data-goal-idx="${i}"><span>${escapeHtml(g.goal)} <span class="row-meta">· ${escapeHtml(g.owner || '')}</span></span><span class="v">${g.pct}%</span></div>
      <svg class="goal-line" id="goal-line-${i}" viewBox="0 0 100 40" preserveAspectRatio="none"></svg>
      ${g.milestone ? `<div class="row-note" style="margin: -2px 0 6px">${escapeHtml(t('label.next'))} ${escapeHtml(g.milestone)}</div>` : ''}
    `;
    }).join('') || `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;
    // After insertion, draw each goal-line.
    state.data.goals.forEach((g, i) => {
      const svg = document.getElementById(`goal-line-${i}`);
      if (svg) renderGoalLine(svg, {
        targetStart: 0,
        targetEnd: 100,
        current: g.pct,
        pctTimeElapsed: goalPctTimeElapsed(g),
      });
    });
    const avgPct = state.data.goals.length ? Math.round(state.data.goals.reduce((s, g) => s + (g.pct || 0), 0) / state.data.goals.length) : null;
    renderKpi('goals', avgPct == null ? '' : `${avgPct}%`, 'pos');
    renderSparkline(document.getElementById('goals-spark'), state.data.goals.length ? state.data.goals.map(g => g.pct || 0) : null);

    // Car
    const car = state.data.car[0];
    if (car) {
      const items = [
        [t('car.annualTest'), car.test],
        [t('car.insurance'), car.insurance],
        [t('car.license'), car.license],
      ].filter(([, d]) => d).map(([k, d]) => `<div class="kv"><span>${escapeHtml(k)}</span><span class="v">${escapeHtml(formatDateHE(d))} (${duePhrase(daysBetween(d, state.today))})</span></div>`);
      const nextDate = [car.test, car.insurance, car.license].filter(Boolean).sort((a, b) => a - b)[0];
      const next = nextDate ? `${t('label.next')} ${formatDateHE(nextDate)}` : '—';
      document.getElementById('car-summary').textContent = next;
      document.getElementById('car-body').innerHTML = items.join('');
      // KPI: days to next test (or any next milestone).
      if (nextDate) {
        const days = daysBetween(nextDate, state.today);
        renderKpi('car', `${days}d`, days < 14 ? 'neg' : 'pos');
      } else {
        renderKpi('car', '', null);
      }
    } else {
      document.getElementById('car-summary').textContent = '—';
      document.getElementById('car-body').innerHTML = `<div class="empty">${escapeHtml(t('empty.noVehicle'))}</div>`;
      renderKpi('car', '', null);
    }
    renderSparkline(document.getElementById('car-spark'), null);

    // Contracts (renewals within 60d)
    const renewals = state.data.contracts
      .filter(c => c.renewal && daysBetween(c.renewal, state.today) <= 60 && daysBetween(c.renewal, state.today) >= -30)
      .sort((a, b) => a.renewal - b.renewal);
    document.getElementById('contracts-summary').textContent = renewals.length ? t('summary.within60', { n: renewals.length }) : t('state.allGood');
    document.getElementById('contracts-body').innerHTML = renewals.map(c => `
      <div class="kv"><span>${escapeHtml(c.contract)} · ${escapeHtml(c.provider || '')}</span><span class="v">${escapeHtml(formatDateHE(c.renewal))}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noRenewals'))}</div>`;
    renderKpi('contracts', renewals.length ? String(renewals.length) : '', renewals.length ? 'neg' : 'pos');
    renderSparkline(document.getElementById('contracts-spark'), null);

    // Education
    const eduUp = state.data.education
      .filter(e => e.nextDate && daysBetween(e.nextDate, state.today) <= 60 && daysBetween(e.nextDate, state.today) >= -7)
      .sort((a, b) => a.nextDate - b.nextDate);
    document.getElementById('education-summary').textContent = eduUp.length ? t('summary.upcoming', { n: eduUp.length }) : t('state.allGood');
    document.getElementById('education-body').innerHTML = eduUp.map(e => `
      <div class="kv"><span>${escapeHtml(e.child)} · ${escapeHtml(e.type || '')}</span><span class="v">${escapeHtml(formatDateHE(e.nextDate))}</span></div>
      ${e.action ? `<div class="row-note" style="margin:-2px 0 6px">${escapeHtml(e.action)}</div>` : ''}
    `).join('') || `<div class="empty">${escapeHtml(t('empty.next60Days'))}</div>`;
    renderKpi('education', eduUp.length ? String(eduUp.length) : '', eduUp.length ? 'neg' : 'pos');
    renderSparkline(document.getElementById('education-spark'), null);

    // Attach drawer toggle handlers
    document.querySelectorAll('.drawer').forEach(d => {
      const toggle = d.querySelector('.drawer-toggle');
      toggle.addEventListener('click', () => d.classList.toggle('open'));
    });
  }

  // Build a last-7-day spending series from transactions (signed-amount sum per day).
  // Falls back to null if no transactions are available.
  function txnTrend7d() {
    const txns = state.data.txns || [];
    if (!txns.length) return null;
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(state.today);
      d.setDate(d.getDate() - i);
      const sum = txns
        .filter(t => t.date && daysBetween(t.date, d) === 0)
        .reduce((s, t) => s + Math.abs(t.amount || 0), 0);
      days.push(sum);
    }
    if (days.every(v => v === 0)) return null;
    return days;
  }

  // Estimate % of the goal's time window that has elapsed (0..100).
  function goalPctTimeElapsed(g) {
    if (!g.targetDate) return 0;
    const total = Math.max(1, daysBetween(g.targetDate, new Date(g.targetDate.getFullYear(), g.targetDate.getMonth() - 3, g.targetDate.getDate())));
    const elapsed = total - Math.max(0, daysBetween(g.targetDate, state.today));
    return Math.max(0, Math.min(100, Math.round((elapsed / total) * 100)));
  }

  // ---------------- Sunday view ----------------
  function renderSunday() {
    const start = new Date(state.today);
    const dow = start.getDay();
    // Sunday = 0; Israeli week starts Sunday.
    const daysToSunday = dow === 0 ? 0 : 7 - dow;
    const sundayStart = new Date(start);
    sundayStart.setDate(start.getDate() + daysToSunday);
    const weekEnd = new Date(sundayStart);
    weekEnd.setDate(sundayStart.getDate() + 7);

    document.getElementById('sunday-week').textContent = `${fmtDateShort(sundayStart)} — ${fmtDateShort(weekEnd)}`;

    // Week ahead
    const events = state.data.calendarEvents
      .filter(e => e.date && e.date >= sundayStart && e.date < weekEnd)
      .sort((a, b) => a.date - b.date);
    document.getElementById('sunday-week-ahead').innerHTML = events.length
      ? events.map(e => `<div class="kv"><span>${fmtDate(e.date)} ${e.start ? '· ' + e.start : ''} — ${escapeHtml(e.title)}</span><span class="v">${escapeHtml(e.owner || '')}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.nothingThisWeek'))}</div>`;

    // Reminders firing this week
    const weekRem = state.data.reminders
      .filter(r => r.daysUntil != null && r.daysUntil >= 0 && r.daysUntil <= 7 && r.status !== 'Done')
      .sort((a, b) => a.daysUntil - b.daysUntil);
    document.getElementById('sunday-reminders').innerHTML = weekRem.length
      ? weekRem.map(r => `<div class="kv"><span>${flagEmoji(r.flag)} ${escapeHtml(r.title)}</span><span class="v">${fmtDate(r.due)}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.noUpcoming'))}</div>`;

    // Overdue
    const overdue = state.data.reminders.filter(r => r.flag === 'OVERDUE').sort((a, b) => a.daysUntil - b.daysUntil);
    document.getElementById('sunday-overdue').innerHTML = overdue.length
      ? overdue.map(r => `<div class="kv"><span>🔴 ${escapeHtml(r.title)}</span><span class="v">${duePhrase(r.daysUntil)}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.noOverdue'))}</div>`;

    // Money
    const totalT = state.data.budget.reduce((s, b) => s + b.target, 0);
    const totalA = state.data.budget.reduce((s, b) => s + b.actual, 0);
    const over = state.data.budget.filter(b => b.pct > 1.0);
    document.getElementById('sunday-money').innerHTML = `
      <div class="kv"><span>${escapeHtml(t('sunday.monthToDate'))}</span><span class="v">${amountHtml(totalA)} / ${amountHtml(totalT)} (${totalT ? Math.round(100 * totalA / totalT) : 0}%)</span></div>
      ${over.length ? over.map(b => `<div class="kv"><span>⚠ ${escapeHtml(b.category)}</span><span class="v">${Math.round(b.pct * 100)}%</span></div>`).join('') : `<div class="row-note" style="padding:6px 0">${escapeHtml(t('sunday.noOverBudget'))}</div>`}
    `;

    // Goals
    document.getElementById('sunday-goals').innerHTML = state.data.goals.map(g => `
      <div class="kv"><span>${escapeHtml(g.goal)} <span class="pill">${escapeHtml(g.owner || '')}</span><span class="pill">${escapeHtml(g.status || '')}</span></span><span class="v">${g.pct}%</span></div>
      ${g.milestone ? `<div class="row-note" style="padding: 0 0 6px">${escapeHtml(t('label.next'))} ${escapeHtml(g.milestone)}</div>` : ''}
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;

    // Data hygiene
    const placeholderPeople = state.data.people.filter(p => (p['Name'] || '').startsWith('['));
    const placeholderGoals = state.data.goals.filter(g => g.goal.startsWith('['));
    const hygiene = [];
    if (placeholderPeople.length) hygiene.push(t('sunday.hygienePeople', { n: placeholderPeople.length }));
    if (placeholderGoals.length) hygiene.push(t('sunday.hygieneGoals', { n: placeholderGoals.length }));
    document.getElementById('sunday-hygiene').innerHTML = hygiene.length
      ? hygiene.map(h => `<div class="kv"><span>${escapeHtml(h)}</span><span class="v">—</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.allClean'))}</div>`;
  }

  // ---------------- Settings ----------------
  function renderSettings() {
    const acc = document.getElementById('settings-account');
    if (cfg.DEMO_MODE) {
      acc.innerHTML = `${escapeHtml(t('settings.demoModeStatus'))}<div class="row-note">${escapeHtml(t('settings.demoNoAccount'))}</div>`;
    } else if (state.user) {
      acc.innerHTML = `${escapeHtml(t('settings.signedInAs', { name: state.user.name }))}<div class="row-note">${escapeHtml(state.user.email)}</div>`;
    } else {
      acc.innerHTML = escapeHtml(t('settings.notSignedIn'));
    }
    document.getElementById('settings-sheetid').value = cfg.SHEET_ID;
    document.getElementById('settings-demo').value = String(cfg.DEMO_MODE);
    // Language toggle active state.
    const lang = currentLang();
    document.querySelectorAll('[data-lang]').forEach(b => {
      b.classList.toggle('primary', b.dataset.lang === lang);
    });
    // Theme toggle active state.
    const theme = localStorage.getItem('familyinc.theme') || 'auto';
    document.querySelectorAll('[data-theme]').forEach(b => {
      b.classList.toggle('primary', b.dataset.theme === theme);
    });
    renderQueue();
  }

  function renderQueue() {
    const q = document.getElementById('settings-queue');
    if (!state.pendingWrites.length) { q.textContent = t('empty.noQueuedWrites'); return; }
    q.innerHTML = state.pendingWrites.map(w => `<div class="kv"><span>${w.kind} · row ${w.row}</span><span class="v">${w.queuedAt}</span></div>`).join('');
  }

  // ---------------- Write-back ----------------
  function findReminder(rowNum) {
    return state.data.reminders.find(r => String(r._row) === String(rowNum));
  }

  async function handleDone(rowNum) {
    const r = findReminder(rowNum);
    if (!r) return;
    r.status = 'Done';
    r.flag = '';
    const now = new Date();
    const ts = fmtISOts(now);
    const userName = (state.user && state.user.name) || 'Dashboard';
    r.lastDoneBy = userName;
    r.doneAt = now;
    r.writeQueueTombstone = now;
    const colM = colLetter(13);  // LastDoneBy
    const colN = colLetter(14);  // DoneAt
    const colO = colLetter(15);  // WriteQueue_Tombstone
    // SPEC §6.1 write contract: intent columns + M, N (completion) + always O.
    // Col H (Last Sent) is ENGINE-owned — the dashboard never writes it,
    // except clearing it as part of the §7.1 recurrence bump below.
    const writes = [
      { range: `${cfg.TABS.reminders}!G${rowNum}`, value: 'Done' },
      { range: `${cfg.TABS.reminders}!${colM}${rowNum}`, value: userName },
      { range: `${cfg.TABS.reminders}!${colN}${rowNum}`, value: ts },
      { range: `${cfg.TABS.reminders}!${colO}${rowNum}`, value: ts },
    ];
    // Bump recurring (mirror of automation/lib/dates.bump_due — keep in sync)
    if (r.recurrence && r.recurrence !== 'One-off' && r.due) {
      const bumped = bumpDate(r.due, r.recurrence);
      if (bumped) {
        writes.push({ range: `${cfg.TABS.reminders}!D${rowNum}`, value: fmtISO(bumped) });
        writes.push({ range: `${cfg.TABS.reminders}!G${rowNum}`, value: 'Pending' });
        writes.push({ range: `${cfg.TABS.reminders}!H${rowNum}`, value: '' }); // Last Sent cleared (§7.1)
        r.due = bumped; r.status = 'Pending';
        r.daysUntil = daysBetween(bumped, state.today);
        r.flag = flagFor(r.daysUntil, r.status);
      }
      // Unbumpable period (Custom/unknown): row stays Done; the engine flags
      // it for review (logs/engine_flags.jsonl) instead of either side guessing.
    }
    await applyWrites(writes, t('action.markedDone', { title: r.title }));
    renderAll();
  }

  async function handleSnooze(rowNum, days) {
    const r = findReminder(rowNum);
    if (!r || !r.due) return;
    const newDate = new Date(r.due);
    newDate.setDate(newDate.getDate() + days);
    r.due = newDate;
    r.status = 'Snoozed';
    r.daysUntil = daysBetween(newDate, state.today);
    r.flag = flagFor(r.daysUntil, r.status);
    await applyWrites([
      { range: `${cfg.TABS.reminders}!D${rowNum}`, value: fmtISO(newDate) },
      { range: `${cfg.TABS.reminders}!G${rowNum}`, value: 'Snoozed' },
      { range: `${cfg.TABS.reminders}!O${rowNum}`, value: fmtISOts(new Date()) },
    ], t('action.snoozed', { title: r.title, days }));
    renderAll();
  }

  async function handleAddNote(rowNum) {
    const r = findReminder(rowNum);
    if (!r) return;
    const text = window.prompt(t('prompt.addNote'));
    if (!text) return;
    const stamp = `[${fmtISO(new Date())} ${state.user?.name || 'You'}]`;
    const newNotes = (r.notes ? r.notes + ' \n' : '') + `${stamp} ${text}`;
    r.notes = newNotes;
    await applyWrites([
      { range: `${cfg.TABS.reminders}!J${rowNum}`, value: newNotes },
      { range: `${cfg.TABS.reminders}!O${rowNum}`, value: fmtISOts(new Date()) },
    ], t('action.noteAdded'));
    renderAll();
  }

  // Mirror of automation/lib/dates.bump_due (SPEC §7.1) — same periods, same
  // clamp-to-month-end rule (Feb-29 → Feb-28, Jan-31 +1mo → Feb-28/29). JS
  // setMonth() overflows instead of clamping, so we clamp by hand. Unknown
  // periods (incl. Custom) return null: no bump, engine flags for review.
  function bumpDate(d, recurrence) {
    const months = { Monthly: 1, Quarterly: 3, Yearly: 12 }[recurrence];
    if (recurrence === 'Weekly') {
      const x = new Date(d);
      x.setDate(x.getDate() + 7);
      return x;
    }
    if (!months) return null;
    const total = d.getFullYear() * 12 + d.getMonth() + months;
    const y = Math.floor(total / 12), m = total % 12;
    const lastDay = new Date(y, m + 1, 0).getDate();
    return new Date(y, m, Math.min(d.getDate(), lastDay));
  }

  // Push writes onto the offline queue, capped at MAX_PENDING_WRITES (SPEC §7.6
  // / DESIGN §6). At the cap we warn ONCE and drop the writes rather than grow
  // the queue unboundedly — silent unbounded growth was the prior bug (B8).
  // Returns true if the writes were queued, false if dropped at the cap.
  function enqueueWrites(writes) {
    if (state.pendingWrites.length >= MAX_PENDING_WRITES) {
      if (!state.queueFullWarned) {
        toast(t('toast.queueFull', { max: MAX_PENDING_WRITES }));
        state.queueFullWarned = true;
      }
      return false;
    }
    writes.forEach(w => state.pendingWrites.push({ kind: 'update', row: extractRow(w.range), range: w.range, value: w.value, queuedAt: new Date().toISOString() }));
    localStorage.setItem(QUEUE_KEY, JSON.stringify(state.pendingWrites));
    renderQueue();
    return true;
  }

  async function applyWrites(writes, label) {
    if (cfg.DEMO_MODE) {
      toast(t('toast.demoPrefix', { label }));
      return;
    }
    if (!navigator.onLine || !state.gapiReady) {
      if (enqueueWrites(writes)) toast(t('toast.queuedOffline', { label }));
      return;
    }
    try {
      const data = writes.map(w => ({ range: w.range, values: [[w.value]] }));
      await gapi.client.sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: cfg.SHEET_ID,
        resource: { valueInputOption: 'USER_ENTERED', data },
      });
      toast(label);
    } catch (e) {
      console.error('Write failed', e);
      if (enqueueWrites(writes)) toast(t('toast.queued', { label }));
    }
  }
  function extractRow(range) { return (range.match(/(\d+)$/) || [])[1] || ''; }

  async function flushQueue() {
    if (!state.pendingWrites.length || cfg.DEMO_MODE) return;
    const queue = state.pendingWrites.slice();
    // SPEC §8.3: the tombstone is written AT FLUSH — the engine's 6h race
    // window starts when the write lands on the Sheet, not when the offline
    // tap happened. Refresh every col-O value to now; everything else flushes
    // as queued (in tap order).
    const flushTs = fmtISOts(new Date());
    const isTombstone = (range) => /!O\d+$/.test(range);
    try {
      await gapi.client.sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: cfg.SHEET_ID,
        resource: {
          valueInputOption: 'USER_ENTERED',
          data: queue.map(w => ({
            range: w.range,
            values: [[isTombstone(w.range) ? flushTs : w.value]],
          })),
        },
      });
      state.pendingWrites = [];
      state.queueFullWarned = false;   // queue drained — re-arm the one-shot cap warning
      localStorage.setItem(QUEUE_KEY, JSON.stringify([]));
      toast(t('toast.flushed', { n: queue.length }));
      renderQueue();
    } catch (e) {
      console.warn('Queue flush failed', e);
    }
  }

  // ---------------- HTML helpers ----------------
  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ---------------- Tabs & UI shell ----------------
  function switchTab(name) {
    state.tab = name;
    document.querySelectorAll('nav.tabbar button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
  }
  function showApp() {
    document.getElementById('signin-screen').hidden = true;
    document.getElementById('app').hidden = false;
  }
  function showSignIn() {
    document.getElementById('signin-screen').hidden = false;
    document.getElementById('app').hidden = true;
  }

  // ---------------- Boot ----------------
  async function boot() {
    // Apply chrome strings to static markup BEFORE first paint of the shell.
    applyChromeStrings();

    // Restore queue
    try { state.pendingWrites = JSON.parse(localStorage.getItem(QUEUE_KEY)) || []; } catch {}

    // Tab clicks
    document.querySelectorAll('nav.tabbar button').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));

    // Sign-in screen buttons
    document.getElementById('signin-btn').addEventListener('click', requestSignIn);
    document.getElementById('demo-link').addEventListener('click', (e) => {
      e.preventDefault();
      cfg.DEMO_MODE = true;
      showApp();
      loadAll();
    });

    // Settings buttons
    document.getElementById('signout-btn').addEventListener('click', signOut);
    document.getElementById('refresh-btn').addEventListener('click', loadAll);
    document.getElementById('settings-save').addEventListener('click', async () => {
      const newSheetId = document.getElementById('settings-sheetid').value.trim();
      const newDemoMode = document.getElementById('settings-demo').value === 'true';

      // D3: Validate Sheet ID format before saving (unless demo mode or blank/unchanged).
      if (!newDemoMode && newSheetId && newSheetId !== cfg.SHEET_ID) {
        // Google Sheets IDs are 44-char base64url strings.
        if (!/^[A-Za-z0-9_-]{10,}$/.test(newSheetId)) {
          toast(t('toast.sheetIdInvalid'));
          return;
        }
        // Test-read one cell to catch typos before committing.
        if (state.gapiReady) {
          const saveBtn = document.getElementById('settings-save');
          saveBtn.disabled = true;
          try {
            await gapi.client.sheets.spreadsheets.values.get({
              spreadsheetId: newSheetId,
              range: 'A1',
            });
          } catch (e) {
            toast(t('toast.sheetIdTestFailed', { err: e.result?.error?.message || e.message || 'unknown' }));
            saveBtn.disabled = false;
            return;
          } finally {
            saveBtn.disabled = false;
          }
        }
      }

      cfg.SHEET_ID = newSheetId;
      cfg.DEMO_MODE = newDemoMode;
      localStorage.setItem('family_inc_config_override', JSON.stringify({ SHEET_ID: cfg.SHEET_ID, DEMO_MODE: cfg.DEMO_MODE }));
      location.reload();
    });

    // Restore config overrides (Sheet ID / demo flag) from a previous Settings save
    try {
      const o = JSON.parse(localStorage.getItem('family_inc_config_override'));
      if (o) Object.assign(cfg, o);
    } catch {}

    // Language toggle clicks (Settings → Language section).
    // Persist preference to localStorage then reload so the pre-paint script
    // applies the correct lang/dir on next boot.
    document.querySelectorAll('[data-lang]').forEach(b => {
      b.addEventListener('click', () => {
        const newLang = b.dataset.lang;
        try { localStorage.setItem('familyinc.lang', newLang); } catch {}
        location.reload();
      });
    });

    // Theme toggle clicks (Settings → Appearance section).
    // Persist preference to localStorage; 'auto' removes the attribute entirely
    // so the CSS media query takes over. Reload for clean pre-paint application.
    document.querySelectorAll('[data-theme]').forEach(b => {
      b.addEventListener('click', () => {
        const val = b.dataset.theme;
        try {
          if (val === 'auto') { localStorage.removeItem('familyinc.theme'); }
          else { localStorage.setItem('familyinc.theme', val); }
        } catch {}
        location.reload();
      });
    });

    // Online → flush queue
    window.addEventListener('online', () => flushQueue());

    if (cfg.DEMO_MODE) {
      showApp();
      await loadAll();
      return;
    }
    if (!cfg.CLIENT_ID || cfg.CLIENT_ID.startsWith('PASTE_')) {
      showSignIn();
      document.getElementById('signin-btn').textContent = t('signin.notConfigured');
      document.getElementById('signin-btn').disabled = true;
      return;
    }
    await initAuth();
    if (!state.token) showSignIn();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();

=== End: dashboard/app.js ===

=== File: deploy/deploy.sh ===
#!/usr/bin/env bash
# Family inc. — the only way code reaches the box (ENGINEERING §6).
# Run as familyinc: ssh familyinc@appliance /opt/family-inc/deploy/deploy.sh
# Red tests abort the deploy; running code is untouched.
set -euo pipefail
cd /opt/family-inc

git pull --ff-only
uv sync --frozen
(cd automation/bridge && npm ci --omit=dev)
(cd automation/finance && npm ci --omit=dev)   # bank scrapers (ENGINEERING §6) — was missing; M6.2 needs it
FAMILY_INC_SHEET_ID= uv run --frozen pytest -q   # empty, NOT -u: load_env "existing env wins" keeps the suite off the live Sheet (D-038); --frozen matches the documented appliance path
sudo /usr/bin/systemctl restart family-bridge   # the one whitelisted sudoers line
echo "deployed $(git rev-parse --short HEAD); timers pick up new code on next fire"

=== End: deploy/deploy.sh ===


```

</details>
