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

## Review-gate dispositions (DeepSeek, 2026-06-19, PO-resolved)

Round 1 (`reviews/review_automation_2026-06-19_10-20.md`) — core design affirmed
(reject in-run wait · date Last Sent to send day · the Done/reschedule/tombstone
re-read guards · `stamp_cell_writes` factoring). Five concerns:

- **#1 [HIGH] no lock on the pending file → APPLIED.** Added `outbox.pending_lock()`
  (fcntl, mirroring `_ledger_lock`/outbox-budget#2) around reconcile's
  read→reconcile→rewrite and `record_pending`'s append, so a concurrent `--send`
  (manual re-run / future timer overlap) can't double-process or drop a
  freshly-recorded entry. Re-reviewed in round 2.
- **#2 [HIGH] `drop_deferred` crash-ordering → DEFENDED.** The premise conflates
  the reminder stamp (Reminders tab) with deferred-alert consumption
  (`deferred.jsonl` lines rendered into the digest text) — unrelated writes. And
  reconcile runs *before* assembly, so a crashed run never sent its digest; the
  next run re-reconciles, drops the alert, then assembles. No new duplicate beyond
  the already-accepted bridge-down->24h double-ride. The reviewer itself retracted
  this in its Suggestions section. Current settle-after-stamp order kept (nothing
  settles unless the stamp landed).
- **#3 [MEDIUM] recurrence Done→Pending stamp → DEFENDED.** Reviewer-retracted; the
  `cur.due.isoformat() != stored_due` guard already blocks it.
- **#4 [MEDIUM] fail-flag clear → DEFENDED.** Reviewer-retracted; the snapshot only
  removes the lines it captured (existing review-2026-06-12 C1 behavior).
- **#5 [LOW] SMTP stamps all recipients on a boolean → DEFENDED.** Pre-existing (not
  touched by GAP-2) and moot — `mailer.send_digest` sends ONE email to both adults
  (single `send_message`), so it's atomic, not per-recipient-partial.
- **Team question (48h horizon) → kept as-is + OPENED a follow-on.** Rejected the
  reviewer's "late-but-deliverable" tier (stamp-anyway would re-introduce a smaller
  silent-loss — the wrong safety direction). Kept drop + re-fire + loud log. OPEN
  (v1.1, with Shanee): surface stale-dropped digests in the weekly briefing's
  system-health line so the drop is family-visible, not just a log entry.

Round 2 (post-lock, `reviews/review_automation_2026-06-19_10-33.md`) — re-review
of the Applied lock; core design + lock affirmed; 5 fresh concerns, all DEFENDED
(no new Apply). One iteration is sufficient (the project is reviewed at many
stages); not re-run a third time.

- **#1 [HIGH] stale `current` snapshot across a digest's rows → DEFENDED.** No I/O
  between rows — the reconcile loop is in-memory; the only TOCTOU is the
  read→write span, which is the §8.3 accepted race (identical to the engine's own
  read-once-then-act). The reviewer's fix (re-read the *cached* dict) is a no-op,
  as it concedes in its Missed-alternatives.
- **#2 [MEDIUM] per-recipient fail-flag clear → DEFENDED.** The lines are prepended
  to BOTH adults' messages; once either delivers, a human saw them, so clearing is
  correct. Idempotent across the two entries.
- **#3 [MEDIUM] same-`msg_id` re-run resets the stale clock → DEFENDED.** Can't
  happen: a same-day re-run dedups at `outbox.queue`, so `queued_for` is empty and
  `_record_pending` never appends a second entry — original `queued_at` preserved.
- **#4 [MEDIUM] tombstone defers the whole confirmed set → DEFENDED.** Deliberate
  conservatism; cost is ≤1 extra duplicate for digest-mates (tombstone clears <6h →
  stamped next run), inside the §8.3 accepted-duplicate envelope. Per-row deferral
  is a possible future refinement, not taken now.
- **#5 [LOW] partial stamp (Status without Last Sent) → DEFENDED.** Reviewer-conceded;
  `sheet.update_reminders` is one atomic `batchUpdate`, so both cells land or neither.
