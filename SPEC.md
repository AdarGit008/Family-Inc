# Family Inc. — System Specification

*What the system is: scope, architecture, data model, contracts, policies. v3.1 · 2026-06-20.*
*This is a present-tense snapshot — it describes how the system behaves today, not how it got here. The dated history (every prior "we changed X to Y" rationale) lives in `Archive/`. Companions: `ENGINEERING.md` (how it's built and run) · `DESIGN.md` (how it looks and reads) · `BACKLOG.md` (current status) · `ROADMAP.md` (the forward v1.1 plan + lane contracts).*

---

## 1. Overview

Family Inc. is a household operating system for a two-adult, two-child family in Israel. It watches the family's obligations — appointments, renewals, deadlines, school/daycare chatter — and reflects them back through **two calm surfaces**: a small number of WhatsApp messages, and a PWA dashboard pinned to both adults' iPhones. The master database is a single Google Sheet. The automation runs unattended on one small VPS ("the appliance").

The core promise: **nothing important gets dropped, without anyone having to watch a screen.**

### What it is not

- Not a chore-gamification app. No streaks, no scores, no nagging.
- Not a kid-facing product. Children's data is structured but adult-mediated.
- Not a finance robot. It never moves money; the only financial credentials it holds are appliance-local, read-only portal logins (and the per-provider device-trust browser profiles they authorize) used to *read* balances and transactions.
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
6. **Fail loud, degrade quiet.** Infrastructure failures surface in the next briefing ("bridge silent 14h"), never as silence. Feature degradation (LLM down → deterministic fallback) must not page anyone. **Time-critical, user-facing data is the exception to "degrade quiet":** when a fetch fails for a time-sensitive line — e.g. Shabbat/chag candle-lighting times — surface an explicit "unavailable" line, never silence, because a missing safety line that's indistinguishable from "nothing today" is itself a silent failure (GAP-7, 2026-06-20).
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

**Finance ingestion (M6, §12.2).** Read-only scrape → categorized transactions + balances in the Sheet → silent surfacing in the briefing and dashboard. **Live on Mizrahi (debit) since 2026-06-19**; the consumer wiring (M6.3) and analysis layer (M6.4) are landing. **Cal (Visa) hooked up 2026-06-23** — an immediate-debit card whose spend also lands merchant-less on the Mizrahi statement, so the Mizrahi-side Cal lines map to an excluded `Card Settlement` bucket (counted once via the card); more cards remain (M6.5). See `BACKLOG.md`.

**Love-notes (V3.7, §7.7).** A parent-to-parent ephemeral note over a small authenticated dashboard→appliance endpoint — the one dashboard datum that is **neither the Sheet nor the outbox**. The **text** phase is code-complete, deploy-gated on standing up the Cloudflare Tunnel + its `DASHBOARD_LOVENOTE_URL` secret; **voice** is a frozen phase-2 (below). See `BACKLOG.md`.

### Non-goals (permanent)

Money movement · credential storage *(except appliance-local, read-only financial portal logins and the device-trust browser profiles they authorize)* · messaging anyone beyond the two adults · posting into any group · kid-facing surfaces · medical advice (scheduling only).

### Frozen (out of scope until a stated condition is met)

Pediatric milestones, goal coaching, PDF/OCR/voice capture, Gmail bill parsing, Maccabi forwarders, WhatsApp reply parsing. Each unfreeze condition is in `BACKLOG.md`; frozen code lives in `attic/`, unmaintained. *(Voice capture's first bounded unfreeze is the love-note **voice memo** (§7.7 phase-2): ≤24h, appliance-local, the single exception to "media is never stored" — it graduates only with its own §4/§7.7 carve-out, which has not landed; the love-note text phase stores no media.)* Anomaly/subscription detection is **killed** (not frozen) — the false-positive cost isn't worth it. A keyword categorizer, also once killed, returns in a bounded form only as the on-box finance rules engine (§12.2).

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
│   ~06:00 finance scrape (M6: live)          │   │   WriteQueue_Tombstone   │
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
| D | Due Date | humans, engine + dashboard (recurrence bump / snooze) | a real Sheets **date** cell (he-IL renders it DD/MM); machine writes emit the **ISO `YYYY-MM-DD`** literal — Sheets parses ISO locale-unambiguously — and both surfaces **read** ISO *or* the DD/MM·DD.MM render (Lane C) |
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

**Dashboard write contract:** every write-back is one `batchUpdate` touching its intent columns **plus M, N (when completing), and always O.** A dashboard that doesn't stamp O is non-conformant. **Snooze writes an *absolute* future Due date** (today + the chosen offset, or a picked date — never `Due += N`), so an already-overdue row snoozed forward clears OVERDUE cleanly. The Today **desk** is select-to-act (V3.3): a multi-row selection fans its done / snooze / note out to **one** `batchUpdate`, every row's columns resolved by header name (Lane C, §7.6).

### 6.2 `WhatsApp_Inbox` (hot, 30-day rolloff) + `WhatsApp_Archive` (text-only, forever)

`WhatsApp_Inbox` columns: msg_id, group_name, group_type, sender_name, sender_role, received_at, text, has_media, classification, one_liner, action_required, action_owner, critical, dispatched, dispatched_at, digested_at. After each successful append, rows older than 30 days roll off (the Archive never rolls). `WhatsApp_Archive` keeps msg_id / group / sender / received_at / text / one_liner only. **Media is never stored** — only the fact that it existed. The `critical` / `dispatched` fields are the outbox *outcome* record; budget enforcement itself lives only in the outbox ledger.

### 6.3 `WhatsApp_Group_Config`

group_name · group_type · importance_default (alert_eligible / digest_only / mute) · alert_recipients (both / adar / shanee / none) · close_contacts · alert_keywords (regex `;`-list) · critical_keywords (regex `;`-list, budget-bypassing).

### 6.4 Other tabs

`People`, `Calendars`, `Calendar-Events`, `Finance-Budget`, `Finance-Accounts`, `Finance-Transactions` (finance landing zone — schema in §12.2), `Goals`, `Health`, `Education`, `Car`, `Contracts`, `Contacts`, `Lists`, `Settings` (Key|Value rows — keys containing `@` are UserMap entries email→display-name; key `lang` is the chrome default), `Reminders-Archive` (one-offs roll here monthly), `Property-Listings` (scraper-written — schema in §12.1). `Calendars` and `Lists` are human-only (no code contract; read loosely, out of code scope). Money values are **ILS only**.

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

**Weekly briefing:** read all tabs → render the **deterministic-template** sections — week ahead · reminders firing this week · overdue · Money · Goals · data hygiene · system self-report · classifier accuracy → write to `Briefings/` and queue `kind=briefing`. The **Classifier accuracy** section carries the week's WhatsApp ALERT-tier counts, by-rule tally, and the <1/week false-positive target; the **self-report** line carries runs-green, messages classified, tombstone skips, and LLM spend. *(Deterministic by design — no LLM call. An LLM-written "five-scene narrative" (the week's spend · a kids' moment · next week's three things · a goal line · a contract heads-up) over whole-Sheet context is a deferred v1.1 lane — `ROADMAP.md` §ai-briefing — not a gap: it needs a whole-Sheet→provider privacy call and keeps this template as its proven fallback.)*

Both message kinds are budget-exempt and subject only to quiet hours.

### 7.3 WhatsApp summarizer — hourly

Reads new inbox lines → classifies: **hard rules first** — a critical/safety keyword is a budget-exempt ALERT that **pierces even a muted group**; below that tier a **muted group raises nothing** (mute is itself a hard rule); otherwise, for non-muted groups, alert-keyword / teacher-evening / vaad-utilities → ALERT and media-only → ROUTINE — then the LLM (the configured provider) for the rest with up to 3 messages of group context, then a deterministic keyword fallback when no key is present → writes Inbox + Archive rows → ALERT rows route per group config → `outbox(kind=alert)`, or `kind=critical` on a critical-keyword match. A digest-only group with a critical match raises a "⚠ NEEDS A LOOK" block at the top of the next digest. Family-group criticals do **not** override digest-only routing (critical_keywords already bypass per group). *(Mute is the one knob that silences ordinary alerts entirely; a true safety keyword is the deliberate exception — PO call 2026-06-18.)*

A weekly accuracy pass (`automation/accuracy_review.py`) re-reads the week's Inbox rows and re-derives each ALERT's triggering rule by reusing the live `hard_rule_alert` function — so the review can't drift from the classifier, and needs no schema change. It surfaces ALERT-tier false positives against the **<1/week** bar, folds a compact pulse into the weekly briefing, and writes a full operator report to `Briefings/`. The "fix" for a false positive is narrowing the offending keyword pattern.

### 7.4 Bridge — Baileys, Node, systemd service

Listens to **groups** → `inbox.jsonl`. Polls `outbox.jsonl` every 15s → sends **1:1 only** to JIDs present in `recipients.json` (machine-local, gitignored); any other target is refused and logged. Per-(id, target) dedup against a sent ledger. Heartbeat file on connect / message / 15-min idle. Never posts to groups. Inbound 1:1 chats from the two known senders (`recipients.json` JIDs) are **silently logged** to `replies.jsonl` as raw material for the v1.1 reply-parsing feature — the bridge does **not** act on them and **never acks** (no affordance it can't honor — §3.7); every other 1:1 sender is dropped. *(LID-addressed 1:1s fall through the known-sender guard and are dropped until v1.1. Self-hosted Baileys, not a paid API: ₪0 marginal, no business-API verification or template approval, free-form Hebrew. Pinned to Baileys 7.x on ESM — the pre-7 line broke companion self-sends after WhatsApp's LID identity migration.)*

### 7.5 Outbox (`lib/outbox.py`) — the chokepoint

```
queue(to: "adar"|"shanee"|"both", body, kind: "alert"|"critical"|"briefing", *, source, msg_id)
  briefing → exempt from budget; subject to quiet hours (22:00–07:00 → hold to 07:00)
  alert    → consult ledger[date][recipient]; if ≥2 → defer: append to tomorrow's
             digest, log alert_suppressed_by_budget; else send + increment
  critical → send immediately, any hour, log budget_bypassed_critical
  all      → idempotent by (id, target); ledger + queue are durable JSONL on disk
```

The ledger is shared across **all** senders — the engine and the summarizer can't each spend a separate 2/day. *(The daily digest is `kind=briefing`, not `alert`: as an alert it consumed a budget slot and, worse, an over-budget alert defers *into* the next digest — which is itself the message, a circular dependency.)*

**Delivery confirmation (cross-run reconcile).** The bridge delivers asynchronously and records each confirmed send to `whatsapp_sent.jsonl`. So queueing is **not** delivery: the daily digest does not stamp on queue — it writes a pending row per recipient to `digest_pending.jsonl`, and at the start of every `--send` run `reconcile_deliveries()` stamps Last Sent / Status (§7.1), clears the reported fail-flag lines, and consumes the budget-deferred alerts that digest carried — but only for the entries the bridge has since confirmed. An entry left unconfirmed past 48h is dropped and logged; its reminders stay unstamped and re-fire (fail loud, degrade quiet). The §10.2 SMTP fallback is itself the confirmation, so it stamps and consumes inline. Because the stamp now lands a run *after* the digest, reconcile re-reads the Sheet and honors the engine's own write guards: it never overwrites a row the user has since completed (Status Done/Skipped), rescheduled, or that recurrence bumped, defers a row with a §8.3 write in flight, and dates Last Sent to the digest's own send day. *(A bounded in-run wait was tried and rejected: it duplicates digests if bridge latency ever exceeds the window and couples the run to the bridge's async timing. Reconcile stamps whenever the bridge eventually confirms — next run or the one after.)*

### 7.6 Dashboard (PWA)

Read: `batchGet` over all bound ranges (UI contract in `DESIGN.md`). Write: per the §6.1 write contract — optimistic UI, an offline queue in `localStorage.pendingWrites[]` (cap 50), flushed on reconnect in tap order, failed flushes retried on the next online event. The write surface resolves its target columns by **header name** (not a hardcoded letter) and **pauses writes on header drift** — the JS mirror of the engine's §7.1 schema guard (Lane C), so a restructured Reminders tab can't be written by position. Identity: Google sign-in → `Settings.UserMap` → display name. Demo mode renders `mock_data.json` and never calls gapi.

**Cross-domain timeline (read-only derived view, V3.6).** The Today *Timeline* tile flattens every dated row already read above into one chronology, governed by two ratified rules. **Milestone-inclusion:** one timeline item per dated field — `Reminders.Due Date` (excluding the terminal Status values {Done, Skipped}), `Calendar-Events.Date`, `Goals.Target Date`, `Health.Next Due`, `Car`'s {Annual Test, Insurance Renewal, License Expiry}, `Education.Next Key Date`, `Contracts.Renewal Date` — kept only within the window `today − 14d … today + 5y`; undated and out-of-window rows are excluded. **Domain→category** (the filter set): each item carries exactly one of `finance · health · car · education · goals · contracts · calendar · other`; calendar and other are assigned by source, every other source maps to its own domain, and a reminder's free-text `Domain` (§6.1 col B) maps near-identity (lower-cased) with any unrecognised value falling to `other` — **never dropped**. The view is read-only (no write contract — items are edited at their source tab) and fully Sheet-derived (no new tab). This timeline is **Education's only Today home** (Education has no portfolio tile).

### 7.7 Love-note endpoint (V3.7)

The one dashboard datum that is **neither the Sheet nor the outbox** — the sanctioned exception to §3.1 (its authoritative home is an appliance file, not a Sheet tab). A parent-to-parent ephemeral note over a small authenticated dashboard→appliance HTTP endpoint (`automation/love_note_server.py`, bound to localhost; a Cloudflare Tunnel fronts it). **One note per direction** (Adar→Shanee, Shanee→Adar), stored as one flat JSON file per direction under the appliance state dir (`/var/lib/family-inc/lovenote`, mode 700), **expiring at 24h-or-on-replacement** — lazy on read **plus** an hourly sweep (`sweep_love_notes.py`). **No push:** a note appears on the recipient's **next dashboard open**, spends **no alert budget**, never rides `lib/outbox.py`, never writes the Sheet, and carries **no delivery/"seen" signal** back to the sender (§3.7) — `DELETE` clears only the author's own note. **Auth:** the PWA forwards its live Google access_token; the server verifies it once against Google's **tokeninfo** endpoint (which also exposes the token's audience — so when the dashboard's OAuth client id is configured [`FAMILY_INC_LOVENOTE_AUD`] the server rejects a token minted for any *other* app, closing the confused-deputy gap), maps the verified email to a parent via `Settings.UserMap` (unknown → 403), then **drops the token — never logged, never persisted** (a short in-memory cache keyed by the token's SHA-256, never the raw token, avoids re-hitting Google under a burst). **CORS** is allow-listed to the Pages origin only; a blank/unset origin denies every browser, so the feature **self-disables fail-safe** (never promise a dead affordance, §3.7). The listener also caps request bodies (413) and rejects unframed (chunked) bodies pre-auth. **Text only** — voice is a frozen phase-2 (§4).

## 8. Cross-cutting policies

### 8.1 Alert budget

2 unsolicited messages / recipient / day, enforced only in `lib/outbox.py`. When over budget, trim priority: OVERDUE and kids' Health always survive; **Goals are de-prioritised first** (`DROP_FIRST_DOMAINS` — sorted out ahead of WEEK/MONTH-OUT, since the weekly briefing already covers them; not a hard exclusion — a Goals fire still rides along when there is room under the per-digest cap), then WEEK/MONTH-OUT. If >10% of fires are suppressed over a rolling 14 days, the next weekly briefing says "budget is biting — raise the cap or tighten the rules?".

### 8.2 Quiet hours

22:00–07:00 Asia/Jerusalem. Alerts and briefings hold; criticals do not.

### 8.3 Offline write / engine race (tombstone)

The dashboard stamps `WriteQueue_Tombstone` (ISO-T datetime) on every write; queued offline writes re-stamp it **at flush time**, so the cell always carries the moment the write *landed* on the Sheet. The engine skips a row while `tombstone + 6h > now()` (one clock: the window starts at flush, not at the tap). *(Date-only tombstones had silently disabled this guard — the hour resolution is load-bearing.)* Residual accepted race: a phone that flushes a queued tap inside the same minute the engine reads → at most one duplicate alert; the flush itself is idempotent. Every skip is logged with the tombstone age, and the weekly briefing reports "N tombstone skips · max age seen" — widen the window from data, not anecdote. **Background-timer races (accepted):** the Sheet-writing timers are deliberately staggered — finance 06:00, reminders 07:25, digest 07:30, property on its own slot — so they don't run concurrently, and each writes a disjoint tab/column set (finance → `Finance-*`; engine + digest → `Reminders`; property → `Property-Listings`); `gspread` batch updates are atomic per call. v1 attempts no cross-timer transaction: the residual is a run that overran into the next timer's window, at most a stale read that self-heals next run.

### 8.4 Idempotency & dedup

Outbox messages carry stable ids: summarizer `wa-{msg_id}`, briefings `brief-{type}-{date}` — the daily digest queues once per recipient as `brief-daily-{date}`; **individual reminders carry no outbox id** (the engine computes, the digest delivers). The bridge dedups per (id, target). Engine re-runs on the same day are no-ops (the Last-Sent guard). The digest's confirmed-delivery stamp (§7.5) keys its pending rows on the same `brief-{type}-{date}` id and drops a settled row once stamped, so reconcile is idempotent — a re-run never double-stamps or re-consumes a deferred alert.

### 8.5 Time & locale

All schedules in Asia/Jerusalem (DST-correct via system TZ, never UTC offsets). Dates are **displayed** DD/MM/YYYY; week starts Sunday; money `Intl.NumberFormat('he-IL', ILS)` / `₪{n:,}` in Python. The one **stored** date both surfaces write, `Reminders.Due Date` (§6.1 col D), is a real Sheets date — machine writes emit the **ISO** literal (locale-safe) and the reads accept ISO or the he-IL DD/MM·DD.MM render (Lane C), so it round-trips regardless of the Sheet's locale. Chrome strings are Hebrew-default with an English fallback; data values stay Hebrew always. Machine-written datetime stamps (Last Sent, DoneAt, WriteQueue_Tombstone) are ISO-8601 `T`-form **text** on both surfaces — the `T` stops Sheets from coercing them into locale date cells, so they round-trip byte-exact and keep the hour resolution the 6h tombstone window needs.

### 8.6 Privacy & security

- WhatsApp plaintext exists in places we don't fully control — Meta's servers (inherent) and the configured LLM provider — plus the VPS we do. Exactly **one** LLM provider is configured at a time (DeepSeek by default — §8.7), and **every provider is treated identically**: the privacy guarantee is not *which* vendor may see the text but *how little it ever sees* — LLM classification sends one message + up to 3 context messages, never whole threads or cross-group context, whichever provider is active. Switching providers is an operator key-swap, not a policy change. *(DeepSeek is the default on cost; it routes group plaintext through PRC-jurisdiction infra — a deliberate privacy-vs-jurisdiction call by the POs, accepted because volume is negligible, every path has a keyless fallback, and the operator may swap providers at will.)*
- **Finance categorization:** the configured LLM provider may assign a category to the **rules-miss remainder only** — a transaction's **description + amount**, never account numbers, balances, credentials, identifiers, or the whole ledger. The on-box rules engine tags first, so most transactions never leave the box.
- **Love-notes (§7.7):** the appliance holds one ephemeral text note per direction (`/var/lib/family-inc/lovenote`, mode 700, never in the repo/backups); the caller's Google OAuth access_token is verified once against Google and then **dropped — never logged or persisted**, and CORS is allow-listed to the Pages origin. No voice/media is stored (text only) until the §4 carve-out.
- Secrets — `recipients.json`, the service-account JSON, `FAMILY_INC_DEEPSEEK_API_KEY`, `FAMILY_INC_APIFY_TOKEN` (property secondary source), `bank_creds.json` (read-only finance logins), SMTP password — live in `/etc/family-inc/`, mode 600, never in the repo. The **device-trust browser profiles** (Max/Cal only; `/var/lib/family-inc/finance/profiles/<provider>`, mode 700) are appliance-local bearer state — not in `/etc`, never in the repo or backups.
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

### 12.2 Finance — Mizrahi / Max / Cal (live on Mizrahi + Cal, M6)

A committed monthly finance review is the standing consumer. Scope = Mizrahi (bank) + Max + Cal (cards); **categorized + month-over-month trends**; investments/brokerage out of scope. Anomaly detection stays killed. Delivery is silent. **Live on Mizrahi (debit) since 2026-06-19** (daily read-only scrape → categorized, idempotent Sheet write); the consumer wiring (M6.3) + analysis layer (M6.4) are landing. **Cal (Visa) live since 2026-06-23** — an *immediate-debit* card whose spend also lands merchant-less on the Mizrahi statement, so its own scrape supplies the per-merchant detail and the Mizrahi-side Cal settlement lines map to an excluded **`Card Settlement`** category (not a `Finance-Budget` row → out of the actuals `SUMIFS`) so each purchase counts **once**, via the card. More cards remain — Shanee's debit card + others (`BACKLOG.md` M6.5).

| Facet | Spec |
|---|---|
| **Source** | The online portals of Mizrahi-Tefahot + Max + Cal, read via `israeli-bank-scrapers` (Puppeteer/headless-Linux, pinned 6.7.8, Node ≥ 22.13 — the library's own `engines` floor). No public API; the library drives each portal's web session. **Read-only by nature** — it fetches balances + transactions and cannot move money. |
| **Mechanism** | A systemd timer runs `automation/finance/scrape.js`: logs into each provider with creds from `/etc/family-inc/bank_creds.json`, fetches balances + a **fixed ~45-day** transaction window (`FAMILY_INC_FINANCE_WINDOW_DAYS`; `Txn-ID` dedup makes overlapping reruns idempotent, so a fixed window is simpler and correct — no since-last-success state to keep), writes one CSV per provider to `/var/lib/family-inc/finance/`. `automation/finance_ingest.py` then normalizes, dedups on `Txn-ID`, and writes via `lib/sheet`. Node scrapes; **Python owns every Sheet write.** The local CSV is the only staging — no Drive. Same-day reruns overwrite the day's CSV and dedup on ingest → idempotent; the import advance gates on a successful Sheet write. **Categorization:** an on-box keyword→category rules engine tags each transaction at ingest; the configured LLM provider assigns categories the rules miss (description + amount on the rules-miss remainder only — §8.6). |
| **Runtime** | One systemd timer (`family-finance.timer`), **~06:00 daily** — ahead of the 07:25/07:30 morning runs so balances are fresh for the M6.3 finance consumers (the weekly briefing Money section + dashboard drawer + the >35d stale-import line). The **daily run is headless** Puppeteer (no Xvfb). The one-time `--auth` device-trust login (Auth model, below) runs **headed under xvfb + x11vnc** — the box already runs xvfb for the property scraper. Cadence is the first tuning knob: if Max/Cal re-challenges prove noisy, drop the cards to 2–3×/week and keep the bank daily. |
| **Auth model** | Read-only portal logins live at `/etc/family-inc/bank_creds.json` (mode 600, never in the repo, never logged). This is where the "no credential storage" non-goal is narrowed — *appliance-local, read-only financial logins*: this creds file **and** the per-provider device-trust browser profiles it authorizes (below), both appliance-local — while "no money movement" stays absolute (the scrapers cannot transfer). **2FA / device-trust:** Mizrahi is password-only. Max + Cal can re-challenge a fresh browser, and `israeli-bank-scrapers` 6.7.8 has **no programmatic OTP entry** for them (their credentials are username+password only; the library's `triggerTwoFactorAuth`/`otpCodeRetriever` path is OneZero-only). So **Max + Cal** each get a **persistent browser profile** (a Chromium `--user-data-dir`, mode 700, under the finance staging dir) — the device-trust cookie jar, a bearer artifact, hence covered by the narrowing above; **Mizrahi**, password-only, stays ephemeral (no stored session). A **one-time operator-driven headed login** — `node automation/finance/scrape.js --auth <provider>`, run on-box under xvfb+x11vnc viewed over an SSH tunnel (`deploy/FINANCE.md` §4) — clears the challenge once by hand; the portal then trusts that profile and the **daily headless run reuses it** and is not re-challenged. A re-challenge still **fails loud** (next digest); the remedy is re-running `--auth` (a same-window rerun stays idempotent via `Txn-ID` dedup). This is the persisted-session hardening, **brought forward to M6.2** because the cards need it to run unattended. **Cal live (2026-06-23):** the debit-only assumption was wrong — Cal was hooked up via the headed `--auth cal` login (the **first** real exercise of this path; verified daily-headless after), confirming the spec above against a live card. Remaining cards split by portal: one on a **new** portal needs a ~20-min `--auth` of its own; one on an **already-connected** login needs **no new auth** — it rides the existing scrape. **Shanee's debit card (M6.5, 2026-06-23) is the latter** — a Cal-cleared immediate-debit card on the connected Cal login, so its only repo change was the mirror token, no `--auth`; pending the 06-26 box-verify that her per-merchant rows actually ride that connected login (else a second `cal`-keyed provider). Either way each immediate-debit card also gets a **`Card Settlement`** mirror token (the Mizrahi side maps there so the spend isn't double-counted); the exclusion tokens sit **below** the merchant rules (a last-resort fallback) so a merchant-bearing line always categorizes by its merchant first — no other code change. |
| **Sheet landing zone** | Two tabs via `lib/sheet`. **`Finance-Accounts`** — one row per account/card, current-state (upserted on `Account Name`): `Account Name` · `Type` · `Bank/Provider` · `Last 4` · `Owner` · `Currency` · `Last Imported` (drives the >35d stale-import warning) · `Balance Snapshot` · `Notes`. The importer overwrites only the machine-owned columns, so a human's `Owner`/`Notes` survive a re-import. **`Finance-Transactions`** — one row per transaction, append-only, `Txn-ID` dedup: `Date` · `Account` · `Description` · `Amount (ILS)` (signed) · `Category` · `Cat-Source` (rule/llm) · `Txn-ID` · `Imported-At`. `Txn-ID` is a **stable hash of `Date|Amount|Description|Account`** (the natural key) — the provider `identifier` is recorded in the CSV but is **not** the key, because `israeli-bank-scrapers` reuses one identifier across distinct Mizrahi charges (trusting it dropped ~70% of rows on the first live import, 2026-06-19); the natural key separated every transaction with zero collisions and is stable across re-fetches. **Column order is load-bearing** — the `Finance-Budget` actuals `SUMIFS` over Date (A) / Amount (D) / Category (E). The date criteria are a **text-prefix wildcard** on the ISO-text `Date` (`<yyyy-mm>&"*"` for the month, `<yyyy>&"*"` for YTD, plus a `Last Month (ILS)` column for month-over-month): a serial `DATE()` window read ₪0 against the RAW-appended text dates, and keeping the append RAW leaves `Txn-ID` dedup intact — so text-prefix is chosen over a `USER_ENTERED` append, which would coerce `Txn-ID`/`Account` (M6.4). M6.3 installs the same formulas onto the live `Finance-Budget` tab via an idempotent installer (`automation/finance_budget_formulas.py`, single-sourced from `lib/finance_budget` and pinned against the seed) that stamps the machine columns only — a category row's Category/Target and every Notes cell are human-owned and never written (only the TOTAL row's Target is a machine `=SUM`), so there's no hand-copy and the stray-formula class is impossible — then verifies actuals go non-zero on the first real month. Retention: keep all (low volume; the monthly review wants history). |
| **Delivery** | Finance lands **silently**: balances, per-category spend, month-over-month trends, and actuals-vs-`Finance-Budget` surface in the weekly briefing **Money** section + the dashboard **Money** drawer, alongside the >35d stale-import line — **never an alert, never a budget bypass.** The only finance *message* is fail-loud. A ">₪500 single charge" alert is deliberately not wired (it's an alert path that brushes the killed anomaly lane — deferred to a deliberate PO call). |
| **Failure handling** | An OTP / device re-challenge (remedy: re-run `--auth <provider>`), a site-change error, or a Sheet-write failure sets the fail-flag; the next digest reports it ("⚠ <provider> צריך אימות מחדש" / "finance scrape failed") and the weekly briefing surfaces persistent failures + the >35d stale line. CSVs are retained on a Sheet-write failure (no data loss; retry next run). If a Cloudflare wall ever appears, the escape hatch is the maintained anti-detect fork on-box, then a managed-proxy pivot. A box compromise leaks read-only visibility only — no transfer capability. |

## 13. References

`ENGINEERING.md` — runtime, repo layout, testing, ops. `DESIGN.md` — dashboard UI, message design system, i18n. `BACKLOG.md` — current status; what's frozen. `ROADMAP.md` — the sequenced forward plan + v1.1 lane contracts. `Archive/` — the dated decision history and superseded docs.
