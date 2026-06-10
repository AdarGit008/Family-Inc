# Family inc. — Reminders Engine (Phase 2 spec)

*Companion to `00_Architecture_and_Roadmap.md`. Living document.*

Last updated: 2026-05-27

---

## Purpose

One automation owns the entire "did we drop the ball?" surface of Family inc. It reads the **Reminders** tab of the master Sheet, decides what needs to fire today, and sends at most a few WhatsApp messages. Every domain (Car, Health, Education, Contracts, …) writes into the Reminders tab — nothing fires from anywhere else.

This is the keystone. Get this right and the rest of the system is plumbing.

---

## Inputs

### From the master Sheet — `Reminders` tab

Authoritative columns the engine reads:

| Col | Field | Notes |
|---|---|---|
| A | Title | Short, human-readable. Used verbatim in WhatsApp. |
| B | Domain | Validated dropdown (Calendar / Finance / … ) |
| C | Owner | Adar / Partner / Both / Child / System |
| D | Due Date | Real date. Anchors all lead-time math. |
| E | Lead Times (days) | Comma-separated, e.g. `60,30,7,1`. Each integer = one fire opportunity. |
| F | Recurrence | One-off / Yearly / Monthly / … — after Due Date passes, the engine bumps it. |
| G | Status | Pending / Snoozed / Sent / Done / Skipped / Overdue |
| H | Last Sent | Last datetime the engine sent a message for this row. |
| I | Channel | WhatsApp / Email / None |
| J | Notes | Free text. Appended to the WhatsApp message if short. |

Engine-derived helper columns (already added in the hardened sheet):

| Col | Field | Formula |
|---|---|---|
| K | Days until | `=D−TODAY()` |
| L | Auto-flag | `OVERDUE` / `FIRE TODAY` / `WEEK OUT` / `MONTH OUT` / blank |

Phase 6.1 columns (added 2026-05-30 for the dashboard's offline-queue race guard):

| Col | Field | Notes |
|---|---|---|
| M | LastDoneBy | Name of whoever marked Done. Set by dashboard write-back. |
| N | DoneAt | ISO datetime the dashboard recorded the completion. Engine uses it for the rolling 7-day count surfaced in the dashboard arc. |
| O | WriteQueue_Tombstone | ISO datetime stamped on every dashboard write (including the flush of a queued offline tap). **Engine reads this on startup and skips any row whose tombstone is within the last 6 hours.** Prevents the "engine fires before the queued completion flushes" race. |

### From config (constants in code, not the Sheet)

- `DAILY_RUN_TIME` = 07:30 local (Asia/Jerusalem)
- `ALERT_BUDGET_PER_DAY` = 2 messages per recipient (hard cap)
- `QUIET_HOURS` = 22:00–07:00 — no messages sent inside this window even if budget allows
- `BATCH_WINDOW_MINUTES` = 5 — multiple fires within this window are merged into one message
- `OVERDUE_REPEAT_DAYS` = 3 — an overdue item re-fires at most every 3 days
- `TOMBSTONE_SKIP_HOURS` = 6 — skip any row whose `WriteQueue_Tombstone` is within this window (the offline-queue race guard; tunable)

---

## The daily run

Triggered by a Hermes scheduled task at 07:30 local.

```
1. Refresh Reminders tab (read from Google Sheets API)
2. For each row where Status ∈ {Pending, Snoozed, Overdue}:
     a. TOMBSTONE GUARD (Phase 6.1):
        if WriteQueue_Tombstone is not blank AND
           (now − WriteQueue_Tombstone) < TOMBSTONE_SKIP_HOURS:
          → SKIP this row this run
          → log entry "skipped_due_to_tombstone" with row id + tombstone age
          → continue to next row
        (Rationale: the dashboard wrote — or is about to flush a queued write —
        within the last 6h. The row state we're reading may already be stale.
        Better to wait one cycle than re-alert something already closed.)
     b. compute days_until = Due Date − today
     c. determine fire reason:
          - OVERDUE                if days_until < 0 and (today − Last Sent) >= OVERDUE_REPEAT_DAYS
          - LEAD-TIME HIT          if days_until ∈ Lead Times (e.g. exactly 30, 7, or 1)
          - DUE TODAY              if days_until == 0
          - otherwise skip
3. Group fires by recipient (per Owner → WhatsApp number map)
4. For each recipient:
     a. Apply alert budget (see "Alert budget" below)
     b. Render the digest message (see "Message templates")
     c. Send via the Baileys outbox (`Automation/wa_outbox.queue_message()` — decision 2026-06-04, Twilio dropped)
     d. On success: stamp Last Sent = now, Status = Sent (or Overdue if still past due)
5. Update Goals.LastUpdate "system_reminders_run" to now (heartbeat)
6. Write a one-line entry to /Briefings/reminders_log.csv (date, fires, sent, skipped_due_to_budget, skipped_due_to_tombstone)
```

**Residual race the tombstone guard doesn't cover:** if a phone is offline for more than 6 hours with a queued completion, the tombstone hasn't been written yet (it's set on flush, not on tap). Engine may then send one extra alert before the queue flushes. Acceptable trade for household scale; window is tunable via `TOMBSTONE_SKIP_HOURS`. Worth widening to 12h if the dashboard's queue-flush time turns out to vary widely with morning connectivity.

### Escalation tiers

Lead Times in column E are the only place tiers are defined — per row. Suggested defaults:

| Domain | Default lead times | Why |
|---|---|---|
| Car (annual test, insurance) | `60, 30, 7, 1` | Catastrophic if missed, but bookable months ahead |
| Contracts (renewals) | `45, 14, 1` | Enough runway to shop alternatives |
| Health (annual checkups, vaccines) | `30, 7, 1` | Provider lead time is usually 1–2 weeks |
| Education (registry, parent-teacher) | `30, 14, 7, 1` | Hard deadlines, often immovable |
| Finance (bill due, CSV import) | `7, 1` | Short cycle, monthly cadence |
| Goals (90-day milestone check) | `14, 1` | Soft deadlines; nudge, don't nag |
| One-off / Other | `7, 1` | Safe default |

Owners can override per row in column E.

### Recurrence handling

When `Status` flips to `Done`, the engine looks at `Recurrence`:

| Recurrence | Action on completion |
|---|---|
| One-off | Status stays Done; row is archived to a `Reminders-Archive` tab on the 1st of next month |
| Yearly / Monthly / Quarterly / Weekly / Daily | `Due Date += period`, `Status → Pending`, `Last Sent → blank` |
| Custom | Engine flags row for human review (sends a message: "this one needs your re-scheduling") |

---

## Alert budget

The hard cap is 2 WhatsApp messages per recipient per day. Enforced in this order:

1. **Coalesce first.** All fires for one recipient in one daily run produce **one** digest message, not N messages. This is the main reason the budget rarely bites.
2. **Within-day re-fires.** If a non-scheduled fire happens later (e.g. an emergency on-demand reminder added manually), it counts as message #2. Anything beyond #2 is queued for tomorrow.
3. **Priority order** when trimming:
   - Always include: OVERDUE, FIRE TODAY, Domain = Health for kids
   - Bumpable: WEEK OUT, MONTH OUT
   - Dropped first: notes-only reminders, Domain = Goals (these get the Friday report instead)
4. **Quiet hours win.** If the daily run is delayed past 22:00 (rare), the digest is held until 07:00.
5. **Audit trail.** Every coalesced/dropped fire is written to `/Briefings/reminders_log.csv` with reason — so we can tell if the budget is too tight.

If the log shows >10% of fires dropped over a rolling 14-day window, the system surfaces "alert budget is being hit — consider raising cap or splitting recipients" in the Sunday briefing.

---

## Message templates

WhatsApp via the self-hosted Baileys bridge (decision 2026-06-04). Sender is the bridge's paired number; recipient resolution = logical `adar`/`shanee`/`both` in the outbox row, mapped to numbers only on the bridge machine (`recipients.json`). Free-form text — no Meta template approval applies, so Hebrew copy is unconstrained.

### Single-fire digest (most common — 1 item)

```
🏠 Family inc. — {date}
{flag emoji} {title}  ·  {due_phrase}
{notes if short}

Reply:
  ✅ done    📆 +N days    🤐 mute 30d
```

`{flag emoji}` map:
- OVERDUE → 🔴
- FIRE TODAY → 🟠
- WEEK OUT → 🟡
- MONTH OUT → 🟢

`{due_phrase}` examples: "due today", "due in 7 days (2026-06-03)", "overdue by 4 days".

### Multi-fire digest (2–5 items)

```
🏠 Family inc. — {date}
You have {N} reminders today:

🔴 Car annual test — overdue by 3 days
🟠 Dentist for Child 1 — due today
🟡 Mortgage payment — due in 7 days

Reply 1/2/3 ✅ to mark done, or 1/2/3 +N to snooze.
```

If N > 5, the engine sends the top 5 by priority and notes "+{N−5} more in the dashboard".

### Reply parsing

Inbound replies arrive through the same bridge (1:1 messages from Adar/Shanee to the paired number; requires lifting the bridge's groups-only read guard for exactly those two JIDs — not built yet). The parser understands:

- `done`, `1 done`, `1 ✅` → set Status = Done on the indexed row
- `+7`, `1 +7`, `snooze 7d` → push Due Date by N days, Status = Snoozed, decrement remaining lead times that have already passed
- `mute 30d`, `1 mute` → Status = Snoozed for 30d; doesn't change Due Date
- `list`, `today`, `?` → bot replies with the current digest re-rendered

Anything else → bot replies: "Didn't catch that. Send `?` to see today's list."

---

## Failure modes & guardrails

| Failure | Detection | Fallback |
|---|---|---|
| Bridge down (machine off / WA protocol break / logged out) | `wa_outbox.bridge_alive()` False — heartbeat stale | Message stays durable in the outbox; bridge flushes on reconnect. Engine logs a warning; if stale >24h, surface in Sunday briefing + fall back to email digest. Inforu SMS is the deep fallback (06-doc 1.12). |
| Sheet not reachable | API 5xx | Engine skips the run; alerts Adar at next successful run with "missed yesterday" line |
| Row has invalid date | Parse fails | Skip row, write to log; surfaced in weekly briefing under "data hygiene" |
| Two recipients, same item | Owner = "Both" | One message per recipient; replies are independent (each can mark done) |
| Budget exhausted | Queue overflow | Held items roll to next day; if held >2 days the engine escalates them to priority |
| Recurrence math wrong (Feb 29 etc.) | Sanity check after bump | Falls back to last day of target month; flags for human review |
| Phone offline >6h with queued write | Tombstone not yet set | Engine fires one extra alert; queue flushes correctly on reconnect (idempotent). Widen `TOMBSTONE_SKIP_HOURS` if this surfaces in real use. |
| Tombstone in the future (clock skew) | `tombstone > now()` | Treat as valid for the full skip window; log anomaly to weekly briefing data-hygiene section. |

---

## Out of scope (for Phase 2)

- Two-way Sheet writes from WhatsApp replies → planned, but Phase 2 ships with read-only sends. Replies parsed and logged but not yet written back to Status. Phase 2.5.
- Per-kid recipient routing (e.g., only Partner gets kids' health reminders) → schema supports it via Owner column, but routing rules live in Phase 3.
- Anomaly detection (transaction over ouch threshold) → Phase 3, separate engine.
- Calendar-derived reminders (Phase 1's briefing already covers these) → not duplicated here.

---

## Definition of done (Phase 2)

- [ ] Baileys bridge paired (one QR scan) on an always-on machine; `recipients.json` placed next to `auth_state/` (numbers never in the Sheet or the repo).
- [ ] Hermes scheduled task running daily at 07:30 Asia/Jerusalem.
- [ ] At least 20 seed reminders in the Sheet across Car, Health, Education, Contracts.
- [ ] First real digest received on a real phone by both Adar and Partner.
- [ ] `/Briefings/reminders_log.csv` accumulating entries for ≥7 days.
- [ ] One full overdue-snooze-done cycle completed end-to-end and visible in the log.

When all six boxes are ticked, Phase 2 closes and Phase 3 (Finance) starts.

### Phase 2 DoD — status & blockers

*Last updated: 2026-06-10*

| # | Checkbox | Status | Blockers & notes |
|---|---|---|---|
| 1 | Baileys bridge paired | ❌ | Bridge code (`whatsapp_bridge/baileys_listener.js`) exists and `wa_outbox.py` is wired for it. Needs: (a) an always-on Linux machine to host the bridge, (b) a spare WhatsApp number to pair as the Family inc. bot, (c) one QR scan to pair. `recipients.json` maps logical names → numbers — create from `Setup/12_WhatsApp_Group_Config_Seed.csv` recipients. |
| 2 | Daily cron at 07:30 | ❌ | `reminders_engine.py` is complete (reads Sheet, classifies, renders, logs). Needs a scheduled task — either a system cron (`0 7 * * * python reminders_engine.py`) or a Hermes cron job. The engine already has `--dry-run` for testing. It currently reads `Family_OS.xlsx` from disk; when the Sheet moves to Google Drive, `read_reminders()` swaps to the Sheets API. |
| 3 | 20 seed reminders | ~ | The `Reminders` tab schema exists in `Family_OS.xlsx` with the 15 columns. Need to do a count: how many non-template rows exist across Car, Health, Education, Contracts domains? Templates (rows starting with `[`) don't count. The spec's escalation tiers table (above) defines per-domain lead times — use those as defaults when seeding. |
| 4 | First real digest received | ❌ | Blocked by (1) and (2). Once the bridge is paired and the daily cron fires, `wa_outbox.queue_message()` will deliver the digest. Dry-runs already produce correct output (verified via `python reminders_engine.py --dry-run`). The Baileys outbox is durable — queued messages survive bridge restarts. |
| 5 | 7-day log | ❌ | Blocked by (2). `reminders_log.csv` has the columns and `append_log()` appends correctly. Once the daily cron runs for 7 consecutive days, this box auto-ticks. The log includes `skipped_due_to_tombstone` per the Phase 6.1 addendum. |
| 6 | End-to-end cycle | ❌ | Blocked by (1), (2), and dashboard write-back. The dashboard can mark items done (Phase 6.1), but the reply-parsing loop (WhatsApp `done`/`snooze`/`mute` replies back to Status changes) is specified but not built. The log shows fires and dropped items; a full cycle means: engine fires → user acts → status updates → next run recognizes the change. Earliest credible path: use the dashboard for Done marking + the engine for firing — the reply parser can come later. |

**Nearest path to first tick:** (3) can be done now — seed 20+ real reminders. (2) can be wired with a system cron today. (1) needs the always-on machine and phone number. With (1)+(2)+(3) done, each daily run produces a real digest → (4) ticks within 1 day, (5) within 7 days, and (6) within ~2 weeks of normal use.

---

## Phase 6.1 addendum — Tombstone race guard (added 2026-05-30)

The dashboard's offline behavior changed from "lock buttons" to "queue + per-row tombstone" in the 2026-05-30 review resolution. To support that, the engine must:

- Read the new column `O` (`WriteQueue_Tombstone`) on each `Pending`/`Snoozed`/`Overdue` row.
- Skip any row whose tombstone is within `TOMBSTONE_SKIP_HOURS` (default 6h).
- Log skipped rows separately in `/Briefings/reminders_log.csv` as `skipped_due_to_tombstone` with the tombstone age — so the column "is it firing too aggressively or too cautiously?" can be answered from the log.

Implementation: ~30 lines in `reminders_engine.py`. Definition of done for the addendum:

- [ ] Column `O` (`WriteQueue_Tombstone`) added to the Reminders tab.
- [ ] Engine reads + skips rows with tombstones < 6h old.
- [ ] `reminders_log.csv` includes `skipped_due_to_tombstone` count column.
- [ ] One end-to-end test: dashboard taps `✓ done` offline → reconnects → engine runs → row not re-alerted; tombstone visible in log.

See `05_Dashboard_Design.md` §"Refresh / loading model" and §"Edge cases" for the dashboard-side contract.
