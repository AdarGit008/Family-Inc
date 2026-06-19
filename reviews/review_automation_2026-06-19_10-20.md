# Milestone review — automation lane

- **When:** 2026-06-19T10:20:14
- **Provider:** DeepSeek (`deepseek-chat`)
- **Elapsed:** 30.7s
- **Attached files (8):**
  - `CLAUDE.md` (5,311 chars)
  - `SPEC.md` (37,779 chars)
  - `BACKLOG.md` (13,326 chars)
  - `ENGINEERING.md` (13,878 chars)
  - `automation/daily_digest.py` (29,066 chars)
  - `automation/lib/outbox.py` (14,880 chars)
  - `automation/lib/config.py` (17,838 chars)
  - `automation/reminders_engine.py` (15,157 chars)

---

## Response

### Concerns

1. **[HIGH] `daily_digest.py` — `reconcile_deliveries()` re-reads the Sheet but does not hold a `fcntl` lock on the digest-pending file.** Between `read_pending()` line ~310 and `rewrite_pending()` line ~393, a concurrent `--send` run (unlikely now with staggered timers, but possible during a manual re-run or a future timer overlap) would double-process the same pending entries. `outbox.py` has the right pattern (`_ledger_lock`) for exactly this class of race. Add the same lock discipline around the pending-file read–reconcile–rewrite cycle.

2. **[HIGH] `outbox.py` `drop_deferred()` (line ~260) — no transactional guarantee that the deferred consumption survives a crash after the stamp writes land.** `reconcile_deliveries()` in `daily_digest.py` applies the stamp writes first, then calls `drop_deferred()`. If the process crashes after the stamp (Sheet write committed) but before `drop_deferred()` writes, the deferred alerts are consumed on the Sheet side but remain in `deferred.jsonl`, and will be re-consumed on the next run — the deferred items duplicate into the next digest. The intent (settle only after the stamp lands) is correct for the stamp, but deferred consumption needs to be part of the same atomic unit or the deferred-file rewrite must be robust to replay (idempotent on the digest side). Fix: either move the `drop_deferred()` call *before* the stamp write (safe: a crash then leaves both unapplied, and the entire entry retries), or make the digest renderer idempotent against re-consumed deferred keys (e.g., the digest's `_deferred_for` filter checks a "already included" set).

3. **[MEDIUM] `daily_digest.py` `reconcile_deliveries()` — the per-row guard against resurrecting Done/Skipped rows checks `current[row["row"]]` against the *full* pending entry's rows, but a single run may reconcile multiple pending entries that share the same row number (same reminder, two different digest days).** If the row was Done between digest day 1 and digest day 2, the first reconcile would correctly skip it, but the second reconcile (entry 2, processed in the same call) would also correctly skip it — that's fine. What is *not* handled: a row that transitions from Done → Pending (recurrence bump) between digest day 1 and digest day 2. The second reconcile would see `status == "Pending"` and a due date that matches the stored `due`, so it would stamp over the *bumped* due date's last-sent with the older digest's timestamp. This is a narrow edge case (recurrence bumps only at 07:25, reconcile runs before 07:25 on subsequent days), but the guard should also check that the stored `due` matches the *current* row's due, not just that the current due is non-None and differs. The code already does this (`cur.due.isoformat() != stored_due`), so this is correct — removing the concern as written. Retracted.

4. **[MEDIUM] `daily_digest.py` `_clear_fail_flag()` (line ~535) — operates on `reported_lines` captured at run start, but `_read_fail_flag_lines()` is called again inside `run()` at line ~420 (and again inside `reconcile_deliveries()` via `_clear_fail_flag` at line ~355).** If a failure fires between the snapshot at line ~420 and the clear call at line ~355 (or between reconcile and the SMTP path's clear at line ~454), that new failure line was never reported but gets cleared anyway because `reported_lines` doesn't include it, and the line-by-line removal only removes lines present in `reported_lines`. Actually, this is safe — the code only removes lines that were in `reported_lines`. If a new line appeared after the snapshot, it's not in `reported_lines`, so it survives. **Retracted** — the resilience is correct.

5. **[LOW] `daily_digest.py` `stamp_sent()` (line ~265) — called by the SMTP fallback path at line ~451, but the SMTP path also calls `outbox.pop_deferred(today)` at line ~453.** The SMTP path confirms inline, so it correctly stamps and consumes deferred. However, `stamp_sent()` builds its fires list from `assembly.digests`, which was computed before the SMTP send. If the SMTP send fails partially (some recipients got the email, some didn't), `stamp_sent()` stamps all recipients' fires regardless. The SMTP `mailer.send_digest()` returns a boolean, not per-recipient success. Widen the SMTP return to per-recipient status, or only stamp on a fully-successful SMTP round.

### Missed alternatives

1. **Use a single `confirm.jsonl` written by the bridge** instead of re-reading `whatsapp_sent.jsonl` on every reconcile — the bridge could write `{msg_id, recipient, status}` immediately on delivery, removing the reconcile step's need to filter `status=='sent'` from a multi-status file.

2. **Key the pending file on `(msg_id, recipient)` with an upsert** instead of append-then-rewrite — a single row per (msg_id, recipient) updated in-place atomically (sqlite or a simple key-value store) would eliminate the whole rewrite-and-keep cycle.

3. **Let the bridge call a webhook on the automation box** to trigger reconciliation immediately on delivery, rather than waiting for the next 07:30 timer — this would close the confirmation window to seconds instead of up to 24 hours.

4. **Stamp on queue but with a new `Pending` intermediate status** on the Sheet — the engine would treat `Pending` rows the same as unstamped ones (re-fire eligible), and the bridge confirmation would flip `Pending` → `Sent`. This avoids the entire cross-run reconcile infrastructure and the pending-file complexity.

### Affirmations

1. **Rejecting the in-run wait** is the right call — coupling automation timing to bridge async delivery is a classic brittle design, and the bounded-wait approach would fail silently when the bridge is slow (duplicate digest) or unresponsive (delayed stamp).

2. **Dating Last Sent to the digest's own send day (`queued_at`) instead of the reconcile day** is correct — a +1-day skew would cause overdue reminders to re-fire one day early, violating the OVERDUE_REPEAT_DAYS guard.

3. **The per-row guards against resurrecting Done/Skipped/rescheduled rows** are thorough — re-reading the Sheet at reconcile time and checking individual row state avoids the clobber that a naive stamp of the queue-time snapshot would cause.

4. **`stamp_cell_writes()` factored out of both the engine and the reconcile path** is good — one source of truth for the stamp shape.

### Concrete suggestions

1. **`daily_digest.py` `reconcile_deliveries()` line ~310–393: wrap the pending-file read–process–rewrite in a `fcntl` lock, following the `_ledger_lock` pattern in `outbox.py`.** Add `_pending_lock()` around the critical section to prevent a concurrent run from double-processing entries.

2. **`daily_digest.py` `reconcile_deliveries()` line ~354: move `drop_deferred()` to *before* the `_apply_reminder_writes()` call.** If the process crashes after dropping deferred keys but before writing stamps, both are unapplied and the whole entry retries next run — correct behavior. If it crashes after stamps but before drop, the deferred keys remain and the entry's deferred alerts re-ride the next digest — a one-duplicate risk, but bounded and loud (duplicate deferred items render in the next digest). Current ordering is the opposite: stamps survive a crash, deferred lines don't drop, and the next run's reconcile finds them already stamped (so `writes` is empty) but still calls `drop_deferred()` with the same keys — this is a no-op on drop (atomic rewrite with the same keep set), so the only cost is a no-op reconcile cycle. This is actually benign. **Retract the suggestion** — the current ordering is safe (drop is idempotent and the deferred keys are computed from the same entry; a crash-before-drop means next run drops them while the stamp is already set, which is fine because the row is now `status=Sent` and the pending entry's rows will be skipped by the `cur.status in {"Done", "Skipped"}` guard. Actually, the stamp sets status to `Sent` or `Overdue`, not `Done`/`Skipped`, so the guard would NOT skip it on the next reconcile — the stamp would be re-applied (idempotent). But the deferred drop would still be called with the same keys, which is also idempotent. So the crash only costs a re-apply of the stamp (a no-op write). No change needed.

3. **`daily_digest.py` `stamp_sent()` call at line ~451 — replace the blanket boolean return from `mailer.send_digest()` with per-recipient success tuples.** Until then, only stamp on a full-success, and log the partial-failure case for operator review. Change `mailer.send_digest()` to return `set[str]` of successfully-delivered recipients.

### One question for the team

**Adar+Shanee: Is the 48-hour pending horizon strictly a budget/risk call, or does it embed a product assumption that a two-day-old digest is never worth delivering even if the bridge recovers?** If the latter, consider a "late but still deliverable" tier — stamp the reminders (so they don't re-fire) but mark the digest's own line as stale in the next briefing, rather than dropping unconfirmed entries silently (even with the loud log line, the human-facing loss is only a log file the family doesn't check).

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
# Session changes — Brief 3, Lane B finish: GAP-2 + outbox-budget#3

Source: `reviews/fix_brief_3_gap2_delivery_reconcile_2026-06-18.md` (the session
opener). **Review-triggering** — touches the delivery + budget chokepoint
(`lib/outbox.py`, `daily_digest.py`). Tests 358→369. This closes the one
remaining `[high]` audit item; the bounded Lane B integrity cluster landed
earlier in commit `67f970e`.

## The bug (GAP-2)

`daily_digest.run(send=True)` stamped `Last Sent` + `Status` the instant it
**queued** the WhatsApp digest. But `outbox.queue()` only appends to
`whatsapp_outbox.jsonl`; the Baileys bridge delivers asynchronously and records
the real outcome to `whatsapp_sent.jsonl`. So queued ≠ delivered: a bridge that
dropped its session after queue left a reminder reading "Sent" while it never
arrived, and the Last-Sent guard then silently suppressed the re-fire —
violating "fail loud, degrade quiet." Two siblings shared the flaw: clearing the
fail flag and consuming budget-deferred alerts (outbox-budget#3).

## The fix — cross-run reconcile (NOT an in-run wait)

A bounded in-run wait was rejected (duplicate-digest risk; couples the run to
bridge timing). Instead:

- **`lib/config.py`** — `DIGEST_PENDING_FILE` (`state/outbox/digest_pending.jsonl`)
  + `DIGEST_PENDING_STALE_HOURS = 48` (PO call 2026-06-19: covers a weekend
  outage; beyond that §10.2 email takes over and reminders re-fire).
- **`lib/outbox.py`** — `record_pending` / `read_pending` / `rewrite_pending`
  (atomic tmp+replace) and `drop_deferred({(id,to)})` (atomic, idempotent);
  factored `_rewrite_deferred`.
- **`reminders_engine.py`** — `stamp_cell_writes(row, now, overdue)` so the
  Sent|Overdue cell shape has one source of truth (engine fires + reconcile both
  build through it).
- **`daily_digest.py`** —
  - `run()` now **peeks** the deferred queue (`read_deferred`) instead of
    consuming it; consumption moves to confirmation.
  - The bridge path no longer stamps: it records a pending row per recipient
    (`{msg_id, digest_date, recipient, rows:[{row,overdue,due}], deferred_keys,
    reported_fail_lines, queued_at}`).
  - `reconcile_deliveries(now, sheet_path)` runs at the **start** of every
    `--send` run (before compute) and, per pending entry confirmed by a
    `status=='sent'` row to that recipient in `whatsapp_sent.jsonl`: stamps Last
    Sent/Status, clears the entry's fail-flag lines, consumes the deferred it
    carried (budget#3), drops it. Unconfirmed past 48h → dropped + logged loud
    (reminders stay unstamped → re-fire). The SMTP fallback confirms inline
    (stamp + `pop_deferred(today)` + clear).
  - Transport log moved to confirmation time: `baileys` on confirm,
    `queued-stale` at queue **only** when the bridge is visibly down (both
    transports), or on a stale-drop — so the weekly briefing's per-day
    aggregation isn't falsely flagged "lagging" on a normal morning.

"Sent" on the Sheet now means *the bridge confirmed delivery*.

## Blocker caught by adversarial review (fixed)

Because the stamp now lands a run *after* the digest, a naive replay of the
queue-time snapshot would clobber a row the user **completes / reschedules /
recurrence-bumps** between queue and confirm — resurrecting a Done one-off as
"Sent". Fix: `reconcile_deliveries` re-reads the Sheet and honors the engine's
own write guards — skips rows now `Status ∈ {Done, Skipped}`, skips a row whose
`Due` moved since queue (stored `due` per pending row), defers a row with a §8.3
tombstone (write in flight), and dates `Last Sent` to the digest's send day
(`queued_at`), not the reconcile day (no +1-day skew). Settle (clear/consume)
only **after** the stamp write lands, so a Sheet-write error retries the whole
entry. Two independent re-verifiers then found no remaining defect.

## Canon

- **SPEC §7.1** — "on send success" → "on CONFIRMED delivery" + the silent-loss
  *why*.
- **SPEC §7.2** — async note (stamped at the reconciling run).
- **SPEC §7.5** — the reconcile step, the pending file, the 48h horizon, the
  no-clobber guard, and the rejected in-run-wait.
- **SPEC §8.4** — reconcile keys on `brief-{type}-{date}`, idempotent (a settled
  pending row is dropped → no double-stamp).
- **BACKLOG** — Lane B flipped (GAP-2 + budget#3 done; GAP-3 + bridge-node#2
  remain).

## Tests (358→369)

Adapted 4 (encoded the old queue=sent contract): `TestSendStamping`
(stamps-on-confirm, overdue), `TestFailFlag::…_when_confirmed`,
`TestReviewD028::…_baileys_on_confirm`. Added 7: confirmed→stamped,
unconfirmed→not-stamped+re-fires, stale→dropped+logged, within-horizon-kept,
budget#3 (consumed only on confirm) + per-recipient, non-`sent`-status doesn't
confirm, single-recipient confirm leaves the other pending, **Done not
resurrected**, **rescheduled row not stamped**, tombstone defers, stamp dated to
digest day.

## Open question for the reviewer

The interim-risk window (this silent-loss path has been open since v1) is
**PO-acknowledged** (joint, 2026-06-19) — closed by this lane, noted for the
record.

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
on CONFIRMED delivery (in the digest): Last Sent = now; Status = Sent | Overdue.
  (Confirmed = the bridge's whatsapp_sent.jsonl, reconciled at the next run; the
  §10.2 SMTP fallback confirms inline. NOT on queue — the bridge delivers
  asynchronously, so stamping a merely-queued digest let a bridge that dropped
  its session read "Sent" while the reminder never arrived, and the Last-Sent
  guard then silently suppressed the re-fire. Stamping on confirmation closes
  that silent-loss; an unconfirmed digest leaves its rows unstamped → they
  re-fire. See §7.5.)
recurrence on Done: bump Due Date by the period, Status → Pending, Last Sent
  cleared; Feb-29-class dates clamp to the last day of the target month + a
  review flag; Custom is flagged, never guessed.
heartbeat: append one line to logs/reminders_log.csv every run.
```

### 7.2 Daily digest (07:30) + weekly briefing (Sat 21:00)

**Daily digest:** one short message assembled from engine fires + the WhatsApp digest section + new-property listings + a Hebcal line (Fridays / erev chag), queued as `kind=briefing`. **One morning message, not several** — assembly happens before queuing. On **confirmed delivery** the digest stamps each fired row's Last Sent / Status per §7.1 (the bridge delivers asynchronously, so a digest queued one morning is stamped when the next run reconciles its confirmation; the SMTP fallback stamps inline).

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

**Delivery confirmation (cross-run reconcile).** The bridge delivers asynchronously and records each confirmed send to `whatsapp_sent.jsonl`. So queueing is **not** delivery: the daily digest does not stamp on queue — it writes a pending row per recipient to `digest_pending.jsonl`, and at the start of every `--send` run `reconcile_deliveries()` stamps Last Sent / Status (§7.1), clears the reported fail-flag lines, and consumes the budget-deferred alerts that digest carried — but only for the entries the bridge has since confirmed. An entry left unconfirmed past 48h is dropped and logged; its reminders stay unstamped and re-fire (fail loud, degrade quiet). The §10.2 SMTP fallback is itself the confirmation, so it stamps and consumes inline. Because the stamp now lands a run *after* the digest, reconcile re-reads the Sheet and honors the engine's own write guards: it never overwrites a row the user has since completed (Status Done/Skipped), rescheduled, or that recurrence bumped, defers a row with a §8.3 write in flight, and dates Last Sent to the digest's own send day. *(A bounded in-run wait was tried and rejected: it duplicates digests if bridge latency ever exceeds the window and couples the run to the bridge's async timing. Reconcile stamps whenever the bridge eventually confirms — next run or the one after.)*

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

Outbox messages carry stable ids: engine `rem-{row}-{date}`, summarizer `wa-{msg_id}`, briefings `brief-{type}-{date}`. The bridge dedups per (id, target). Engine re-runs on the same day are no-ops (the Last-Sent guard). The digest's confirmed-delivery stamp (§7.5) keys its pending rows on the same `brief-{type}-{date}` id and drops a settled row once stamped, so reconcile is idempotent — a re-run never double-stamps or re-consumes a deferred alert.

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

**🔵 Lane B (robustness seams) — GAP-2 + budget#3 landed 2026-06-19; GAP-3 + bridge-node#2 remain.** Earlier (2026-06-18) the bounded outbox-integrity cluster landed: **outbox-budget#1** — the budget ledger now writes atomically (tmp+replace) and reads **fail-CLOSED** (a corrupt ledger reads as cap-reached → alerts defer, never flood; loud for the operator); **outbox-budget#2** — an `fcntl` lock around the ledger read-modify-write so concurrent senders can't double-spend the 2/day cap; **GAP-10** — the bridge's `processOutbox` got per-row try/catch (one failed `sendMessage` no longer abandons the rest of the batch; transient failures retry, only terminal sent/refused suppress); **GAP-8** — the multi-timer Sheet race documented as accepted (SPEC §8.3). **✅ GAP-2 (the [high] silent-loss path) + outbox-budget#3 — cross-run reconcile, 2026-06-19.** The digest no longer stamps Last Sent/Status when it *queues*; it records a pending row per recipient (`digest_pending.jsonl`) and `reconcile_deliveries()` (start of each `--send` run) stamps — and clears the fail flag, and consumes the budget-deferred alerts the digest carried (budget#3) — only for the entries the bridge has **confirmed** in `whatsapp_sent.jsonl`. Unconfirmed past **48h** (PO call) → dropped + logged, reminders re-fire (no silent loss). The SMTP fallback confirms inline. "Sent" on the Sheet now means *delivered*. Because the stamp lands a run after the digest, reconcile re-reads the Sheet and never resurrects a row the user has since completed/rescheduled/recurrence-bumped (or one with a §8.3 write in flight), and dates Last Sent to the digest's send day — a blocker the adversarial review caught and that now has its own regression tests. The rejected bounded-in-run-wait is documented in SPEC §7.5. Transport log moved to confirmation time (`baileys` on confirm; `queued-stale` at queue only when the bridge is visibly down, or on stale-drop). The interim-risk window (silent-loss open since v1) is **PO-acknowledged**. Tests 358→369. Canon: SPEC §7.1/§7.2/§7.5/§8.4. **Review gate (delivery+budget) runs at close.** Remaining Lane B: GAP-3 (JSONL rotation), bridge-node#2 (bridge scope-guard test harness).

**Deferred** (next sessions): **Lane B remainder** (GAP-3 JSONL rotation, bridge-node#2 scope-guard harness), Lane C (dashboard), and Lane E's code-correctness + test-gap items (digest >30d flag, derive_rule, property-apify, OVERDUE-overflow test, reply_handler stub flags, the deferred "budget is biting" line — decision #3).

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

On CONFIRMED delivery the digest stamps each fired row back to the Sheet: Last
Sent = now, Status = Sent | Overdue (SPEC §7.1/§7.2). The bridge delivers
asynchronously, so a bridge-queued digest is not stamped on queue — it records a
pending row per recipient and reconcile_deliveries() (start of the next --send
run) stamps once whatsapp_sent.jsonl confirms (GAP-2: queue ≠ delivered, closing
a silent-loss path). The SMTP fallback's return value IS the confirmation, so it
stamps inline. Stamping is skipped — loudly — when no live backend is configured,
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


def _deferred_for(deferred: list[dict], rcpt: str) -> list[dict]:
    """The budget-deferred alerts that ride this recipient's digest (SPEC §7.5).
    One filter, used by assembly (to render them) and the send path (to record
    which (id, to) keys the digest carries, so reconcile consumes them only on
    confirmed delivery). Deferred rows are single-target — `both` is defensive."""
    return [r for r in deferred if r.get("to") in (rcpt, "both")]


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
        mine = _deferred_for(deferred, rcpt)
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


def _apply_reminder_writes(writes: list, sheet_path: Optional[Path]) -> int:
    """Issue Last Sent/Status writes, refusing to mutate the committed seed xlsx
    when no live backend is configured (a dev-machine --send must stay inert).
    Returns the number of distinct rows written."""
    if not writes:
        return 0
    if sheet_path is None and not sheet.is_live():
        print("[warn] no live Sheet backend — Last Sent/Status NOT stamped "
              "(refusing to write the seed xlsx)")
        return 0
    sheet.update_reminders(writes, sheet_path)
    return len({w.row for w in writes})


def stamp_sent(assembly: Assembly, queued_for: set[str], now: datetime,
               sheet_path: Optional[Path] = None) -> int:
    """Write Last Sent/Status for every row that reached at least one phone this
    run (SPEC §7.1). Used by the SMTP fallback, whose return value IS the
    confirmation, so it stamps inline. The bridge path defers to
    reconcile_deliveries() instead (queue ≠ delivered). Deferred or duplicate
    targets don't count as sent — their rows stay eligible."""
    fires = [f for rcpt in queued_for
             for f in assembly.digests.get(rcpt, engine.Digest(rcpt)).fires]
    return _apply_reminder_writes(engine.stamp_writes(fires, now), sheet_path)


def _record_pending(assembly: Assembly, rcpt: str, today: date, now: datetime,
                    deferred: list[dict], fail_lines: list[str], msg_id: str) -> None:
    """Persist what this recipient's just-queued bridge-digest carries, so the
    next run's reconcile can stamp / clear / consume on confirmed delivery
    (GAP-2). Rows + overdue rebuild the §7.1 stamp; deferred_keys are the
    (id, to) of the budget-deferred alerts the digest rode (outbox-budget#3);
    reported_fail_lines are cleared from the fail flag on confirm."""
    d = assembly.digests.get(rcpt, engine.Digest(rcpt))
    outbox.record_pending({
        "msg_id": msg_id,
        "digest_date": today.isoformat(),
        "recipient": rcpt,
        # `due` lets reconcile detect a row that moved (reschedule / recurrence
        # bump) between queue and confirm and decline to stamp a stale snapshot.
        "rows": [{"row": f.reminder.row, "overdue": f.days_until < 0,
                  "due": f.reminder.due.isoformat() if f.reminder.due else None}
                 for f in d.fires],
        "deferred_keys": [[r.get("id", ""), r.get("to", "")]
                          for r in _deferred_for(deferred, rcpt)],
        "reported_fail_lines": fail_lines,
        "queued_at": now.isoformat(timespec="seconds"),
    })


def _pending_age_hours(entry: dict, now: datetime) -> float:
    """Hours since the digest was queued; +inf for an unparseable stamp so a
    corrupt entry is dropped (loudly) rather than pinned forever."""
    try:
        return (now - datetime.fromisoformat(entry.get("queued_at", ""))).total_seconds() / 3600.0
    except (ValueError, TypeError):
        return float("inf")


def _digest_sent_at(entry: dict, now: datetime) -> datetime:
    """The moment the digest actually went out (its queue time) — the truthful
    Last Sent, even when reconcile confirms it a run (or days) later. Falls back
    to `now` only for an unparseable stamp."""
    try:
        return datetime.fromisoformat(entry.get("queued_at", ""))
    except (ValueError, TypeError):
        return now


def reconcile_deliveries(now: datetime, sheet_path: Optional[Path] = None) -> int:
    """Stamp reminders for bridge-digests the bridge has since CONFIRMED
    delivering (GAP-2). Runs at the START of every --send run, before today's
    compute, so a just-confirmed row is seen as stamped and never re-fires.

    Per pending entry: if SENT_FILE shows a `status=='sent'` row to that
    recipient → apply the §7.1 Last Sent/Status writes (dated to the digest's
    own send day, not this run), clear the entry's reported fail-flag lines,
    consume the budget-deferred alerts it carried (outbox-budget#3), and drop it.
    An entry unconfirmed past DIGEST_PENDING_STALE_HOURS is dropped and logged
    loud — its reminders stay unstamped, so they re-fire (fail loud, degrade
    quiet). Confirmed/stale outcomes write the transport log (`baileys`/
    `queued-stale`) dated to the digest's day, grouped per digest so a normal
    morning is one line. Returns rows stamped.

    Because the stamp now lands a run later than the digest, reconcile re-reads
    the Sheet and honors the engine's own write guards: a row the user has since
    completed (Status Done/Skipped) is NOT resurrected, and an entry whose row
    has a dashboard write in flight (§8.3 tombstone) is deferred to the next run
    — never clobbered."""
    pending = outbox.read_pending()
    if not pending:
        return 0
    # Current Sheet state, so a confirmed stamp can't overwrite a completion or
    # recurrence-bump made between queue and confirm (the cross-run clobber).
    current = {r.row: r for r in sheet.read_reminders(sheet_path)}

    by_digest: dict[str, list[dict]] = {}
    for e in pending:
        by_digest.setdefault(e.get("msg_id", ""), []).append(e)

    keep: list[dict] = []
    total_stamped = 0
    for msg_id, entries in by_digest.items():
        digest_date = entries[0].get("digest_date", "")
        confirmed: list[dict] = []
        stale_rcpts: set[str] = set()
        for e in entries:
            rcpt = e.get("recipient", "")
            delivered = any(r.get("to") == rcpt and r.get("status") == "sent"
                            for r in outbox.delivery_status(msg_id))
            if delivered:
                confirmed.append(e)
            elif _pending_age_hours(e, now) > config.DIGEST_PENDING_STALE_HOURS:
                stale_rcpts.add(rcpt)
                print(f"[warn] digest {msg_id} → {rcpt} unconfirmed after "
                      f">{config.DIGEST_PENDING_STALE_HOURS}h — DROPPING the pending stamp; "
                      "its reminders stay unstamped and will re-fire (fail loud)")
            else:
                keep.append(e)  # still inside the horizon — wait for confirmation
        # A dashboard write landing on a confirmed digest's row (§8.3) — defer
        # the whole confirmed set and re-check next run once the tombstone clears.
        if confirmed and any(
                row["row"] in current and engine.is_tombstoned(current[row["row"]], now)
                for e in confirmed for row in e.get("rows", [])):
            keep.extend(confirmed)
            confirmed = []

        writes: list = []
        for e in confirmed:
            sent_at = _digest_sent_at(e, now)
            for row in e.get("rows", []):
                cur = current.get(row["row"])
                if cur is None:
                    continue  # row deleted since the digest — nothing to stamp
                if cur.status in {"Done", "Skipped"}:
                    continue  # user acted on the delivered reminder — keep their state
                stored_due = row.get("due")
                if stored_due is not None and (cur.due is None or cur.due.isoformat() != stored_due):
                    continue  # row rescheduled / recurrence-bumped since queue — don't stamp a stale snapshot
                writes += engine.stamp_cell_writes(row["row"], sent_at, bool(row.get("overdue")))
        total_stamped += _apply_reminder_writes(writes, sheet_path)
        # Settle (clear flag / consume deferred) only after the stamp lands, so a
        # Sheet-write failure retries the whole entry next run instead of
        # half-clearing the flag or losing a deferred alert.
        for e in confirmed:
            _clear_fail_flag(e.get("reported_fail_lines", []))
            outbox.drop_deferred({tuple(k) for k in e.get("deferred_keys", [])})

        try:
            d = date.fromisoformat(digest_date)
        except ValueError:
            d = now.date()
        confirmed_rcpts = {e.get("recipient", "") for e in confirmed}
        if confirmed_rcpts:
            _log_delivery(d, "baileys", confirmed_rcpts)
        if stale_rcpts:
            _log_delivery(d, "queued-stale", stale_rcpts)
    outbox.rewrite_pending(keep)
    return total_stamped


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
    """One transport line per digest-day: smtp (inline, SPEC §10.2) | baileys
    (reconcile, on confirmation) | queued-stale (queue time when the bridge is
    visibly down, or reconcile when a pending digest is stale-dropped) — review
    2026-06-12 C2, D-028; GAP-2 moved baileys/queued-stale to confirmation time.
    The weekly briefing reads this (per-day) to surface degraded mornings — a
    slowly dying bridge must not hide behind a working fallback."""
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
    # GAP-2: before today's compute, stamp any prior bridge-digests the bridge
    # has since confirmed delivering (and drop the ones it never did). Running
    # first means a just-confirmed row reads as stamped and won't re-fire today.
    if send and not dry_run:
        reconciled = reconcile_deliveries(now, sheet_path)
        if reconciled:
            print(f"reconciled {reconciled} confirmed-delivery stamp(s) from prior digest(s)")
    # Peek the deferred queue — it is consumed only on CONFIRMED delivery
    # (outbox-budget#3): the SMTP path inline, the bridge path at reconcile. An
    # unconfirmed digest leaves its deferred alerts to re-ride the next one.
    deferred = outbox.read_deferred(today)
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
            # send_digest returns True only on a real send, so this IS the
            # confirmation: stamp / consume deferred / clear the flag inline.
            if mailer.send_digest(messages, stale, today):
                hours = "?" if stale is None else f"{stale:.0f}"
                print(f"[email-fallback] bridge down {hours}h — digest delivered by SMTP")
                stamped = stamp_sent(assembly, set(messages), now, sheet_path)
                if stamped:
                    print(f"stamped Last Sent/Status on {stamped} row(s)")
                outbox.pop_deferred(today)  # confirmed → consume what it carried (budget#3)
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
        msg_id = f"brief-daily-{today.isoformat()}"
        queued_for: set[str] = set()
        for rcpt, body in messages.items():
            # kind=briefing (SPEC §7.2, D-027): budget-exempt, never deferrable —
            # over-budget alerts defer INTO the digest, so the digest itself
            # must be undeferrable or the ledger goes circular.
            res = outbox.queue(rcpt, body, "briefing", source="daily_digest", msg_id=msg_id)
            if res.queued:
                queued_for.add(rcpt)
            print(f"queued → {rcpt}: {len(res.queued)} row(s)"
                  + (f", deferred {res.deferred}" if res.deferred else "")
                  + (f", duplicate {res.duplicates}" if res.duplicates else ""))
        # GAP-2: queueing is NOT delivery. Record a pending entry per recipient;
        # the next run's reconcile stamps Last Sent/Status (+ clears the fail
        # flag, + consumes the deferred this digest carried) once the bridge
        # confirms in whatsapp_sent.jsonl. Stamping on queue let a bridge that
        # dropped its session read "Sent" while the reminder never arrived — the
        # silent loss this closes. No transport line yet on a healthy queue;
        # reconcile logs `baileys` on confirmation.
        for rcpt in queued_for:
            _record_pending(assembly, rcpt, today, now, deferred, fail_lines, msg_id)
        # A digest queued against a visibly-down bridge (both transports down) is
        # a known-degraded delivery — surface it now (weekly "delivery lagging");
        # reconcile still stamps it later if the bridge reconnects and confirms.
        if queued_for and not delivered:
            _log_delivery(today, "queued-stale", queued_for)
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


def _rewrite_deferred(keep: list[dict]) -> None:
    # Atomic rewrite (tmp + replace), same discipline as the ledger
    # (outbox-budget#1) — a crash mid-rewrite must not corrupt the deferred
    # queue and lose alerts that haven't ridden a digest yet.
    tmp = config.DEFERRED_FILE.with_name(config.DEFERRED_FILE.name + ".tmp")
    tmp.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
    tmp.replace(config.DEFERRED_FILE)


def pop_deferred(upto: date) -> list[dict]:
    """Like read_deferred, but consumes what it returns (real digest runs)."""
    rows = _jsonl_rows(config.DEFERRED_FILE)
    take = [r for r in rows if r.get("deferred_on", "") < upto.isoformat()]
    keep = [r for r in rows if r.get("deferred_on", "") >= upto.isoformat()]
    if take:
        _rewrite_deferred(keep)
    return take


def drop_deferred(keys: set[tuple[str, str]]) -> None:
    """Consume specific deferred rows by (id, to) — called when the digest that
    carried them is CONFIRMED delivered (outbox-budget#3, GAP-2). Idempotent:
    keys already absent are a no-op, so a re-run never loses a different
    recipient's still-pending alert (deferred rows are single-target)."""
    if not keys:
        return
    rows = _jsonl_rows(config.DEFERRED_FILE)
    keep = [r for r in rows if (r.get("id", ""), r.get("to", "")) not in keys]
    if len(keep) != len(rows):
        _rewrite_deferred(keep)


# ---------------------------------------------------------------------------
# Pending bridge-digests awaiting delivery confirmation (GAP-2 cross-run
# reconcile). The bridge delivers asynchronously, so "queued" ≠ "delivered":
# the digest records a pending row per recipient here and the next run's
# reconcile stamps Last Sent/Status once SENT_FILE confirms the delivery.
# ---------------------------------------------------------------------------
def record_pending(entry: dict) -> None:
    """Append one pending-digest row (one per recipient queued this run)."""
    config.DIGEST_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.DIGEST_PENDING_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_pending() -> list[dict]:
    """Every pending-digest row not yet settled by reconcile."""
    return _jsonl_rows(config.DIGEST_PENDING_FILE)


def rewrite_pending(rows: list[dict]) -> None:
    """Atomic rewrite after reconcile drops settled entries; removes the file
    when nothing is left waiting."""
    if not rows:
        config.DIGEST_PENDING_FILE.unlink(missing_ok=True)
        return
    config.DIGEST_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.DIGEST_PENDING_FILE.with_name(config.DIGEST_PENDING_FILE.name + ".tmp")
    tmp.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(config.DIGEST_PENDING_FILE)


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
# Pending bridge-digests awaiting delivery confirmation (GAP-2). The bridge
# delivers asynchronously and confirms in SENT_FILE; the daily digest does NOT
# stamp on queue — it records a pending row per recipient here and stamps Last
# Sent/Status at the next run's reconcile_deliveries() once the bridge confirms.
DIGEST_PENDING_FILE = BRIDGE_STATE_DIR / "outbox" / "digest_pending.jsonl"
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
# GAP-2 cross-run reconcile: a queued bridge-digest that the bridge never
# confirms delivering within this horizon is dropped (its reminders stay
# unstamped → they re-fire — fail loud, degrade quiet) and logged. 48h covers a
# weekend bridge outage; beyond that the §10.2 email fallback would have taken
# over on subsequent runs (PO call 2026-06-19).
DIGEST_PENDING_STALE_HOURS = 48
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


def stamp_cell_writes(row: int, now: datetime, overdue: bool) -> list[CellWrite]:
    """The Last Sent/Status cell pair for one row (SPEC §7.1). One source of
    truth for the stamp shape — stamp_writes (live fires) and the digest's
    cross-run reconcile (persisted {row, overdue}) both build through here."""
    return [
        CellWrite(row, "Last Sent", now),
        CellWrite(row, "Status", "Overdue" if overdue else "Sent"),
    ]


def stamp_writes(fires: list[Fire], now: datetime) -> list[CellWrite]:
    """On confirmed delivery (daily_digest --send): Last Sent = now,
    Status = Sent | Overdue (SPEC §7.1)."""
    writes: list[CellWrite] = []
    for f in {f.reminder.row: f for f in fires}.values():  # one stamp per row
        writes += stamp_cell_writes(f.reminder.row, now, f.days_until < 0)
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


```

</details>
