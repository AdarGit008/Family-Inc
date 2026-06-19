# Fix Brief 3 — GAP-2: deliver-confirmed stamping (Brief 2, Lane B finish)

## Session opener — read first (this brief is self-contained)

*Open a fresh Claude Code session in this repo and point it at this file. It carries all the context the fix needs — no prior conversation required.*

**You are opening a Family Inc fix session as Lead Architect.** `CLAUDE.md` auto-loads (roles, principles, guardrails) — read it. **The PO has authorized this lane as the session focus:** finishing Brief 2 **Lane B** by closing **GAP-2**, the one remaining **[high]** item in the audit — a silent-lost-reminder path. It is **review-triggering** (delivery/outbox guarantees).

**Where this came from.** The 2026-06-18 audit (`reviews/fix_brief_2_gaps_minor_disputed_2026-06-18.md`, Lane B). Lane B's bounded integrity cluster already landed (commit `67f970e`: outbox-budget#1 atomic+fail-closed ledger, #2 fcntl lock, GAP-10 bridge per-row try/catch, GAP-8 multi-timer race doc). **GAP-2 + outbox-budget#3 were deliberately deferred to this focused pass** because they change the *delivery contract*. Context artifacts: `reviews/lane_b_changes_2026-06-18.md` and the Lane B review `reviews/review_automation_2026-06-18_20-30.md` (its "one question" — acknowledge the interim risk window — is PO decision #2 below).

> **A first cut using a bounded in-run wait was written and REVERTED. Do not repeat it.** Polling `delivery_status` for ~30s inside the digest run and stamping only confirmed recipients risks *duplicate digests* if the bridge's real delivery latency ever exceeds the window, and it couples the Python run to the bridge's async timing (hard to test). **Use the cross-run reconcile below instead.**

**Current state (2026-06-18).** v1 live (`v1-live`); M6 finance ingestion building. Brief 1 ✅; Brief 2 Lanes A ✅, E-hygiene ✅, S ✅, B integrity-cluster ✅ (`67f970e`). **Test baseline: 358 passed, 0 failed.** The GAP-2 silent-loss path is still open.

**Read order:** `CLAUDE.md` (auto) → `BACKLOG.md` (the "Now" section has the Lane B status) → this brief → the cited code + `SPEC §7.1/§7.5/§8.4`.

**Run the tests** from the repo root (hermetic; an autouse fixture blanks live env): `uv run --frozen pytest -q` (or `.venv/bin/python -m pytest -q`).

**Session protocol (CLAUDE.md):** `git pull --ff-only` before work · constants → `automation/lib/config.py` (never a script) · a directional call **folds into the canon** (edit the doc to its new present-tense state + a short inline *why*; dated rationale in the commit) · git index ops run on the **PO's machine**, never the sandbox · end with ONE handoff terminal block.

**Review gate:** Lane B touches **delivery + budget** guarantees → run `automation/review.py` at close (blocking inside the handoff chain; resolve a MAJOR as Apply / Defend / Open). See ENGINEERING §10. (`--lane automation --provider deepseek`; `DEEPSEEK_API_KEY` is in the PO's shell env.)

---

## The bug (GAP-2)

`daily_digest.run(..., send=True)` stamps `Last Sent` + `Status` onto the reminder rows **the instant it queues** the digest (`outbox.queue()` just *appends* to `whatsapp_outbox.jsonl`). The **Baileys bridge** delivers asynchronously on its own 15s poll and records the real outcome (`{id, to, status:'sent'}`) to `whatsapp_sent.jsonl`. So "queued" ≠ "delivered": if the bridge is logged out / crashes / drops the session after the queue but before delivering, the reminder reads **"Sent"** on the Sheet, the engine's **Last-Sent guard blocks re-firing**, and the reminder is **silently lost** — violating "fail loud, degrade quiet."

- The **SMTP fallback path is fine** — `mailer.send_digest()` returns `True` only on a real send, so stamping after it means delivered. **The hole is the bridge path.**
- Two siblings share the flaw — they also fire on queue, not delivery: **clearing the fail-flag** (`_clear_fail_flag`) and **consuming budget-deferred alerts** (`outbox.pop_deferred` — this is **outbox-budget#3**). Fix all three on the same confirmation.

**Key anchors** (grep — line numbers drift): `automation/daily_digest.py` `run()` send block (~`if send:` through the `stamp_sent` / `_clear_fail_flag` calls), `stamp_sent()`, and the `deferred = … pop_deferred(today)` line near the top of `run()`. `automation/lib/outbox.py` `delivery_status(msg_id)` (already reads `whatsapp_sent.jsonl`), `pop_deferred()`, `read_deferred()`. `automation/reminders_engine.py` `stamp_writes(fires, now)` → `CellWrite(row,"Last Sent",now)` + `CellWrite(row,"Status","Overdue" if days_until<0 else "Sent")`. Bridge sent-ledger shape in `automation/bridge/baileys_listener.js` `processOutbox` (`status` ∈ `sent` | `refused_unknown_recipient` | `send_failed`).

## The fix — cross-run reconcile (stamp on the bridge's CONFIRMED delivery)

1. **On the bridge path (queue), don't stamp.** Instead, after queueing, record a **pending** entry per recipient to a new durable file — e.g. `config.DIGEST_PENDING_FILE` (suggest `state/outbox/digest_pending.jsonl`; add it to `config.py` and to the `tmp_runtime` fixture in `tests/conftest.py` alongside the other state paths). Each entry: `{msg_id, recipient, rows: [{row, overdue}], reported_fail_lines: [...], deferred_consumed: bool/marker, queued_at}`. The rows come from `assembly.digests[rcpt].fires` (`.reminder.row`, and `days_until < 0` for `overdue`). Do **not** stamp / clear the fail-flag / consume deferred here.
2. **At the START of each run, reconcile** (a new `reconcile_deliveries(now, sheet_path)` called before today's send): for each pending entry, check `outbox.delivery_status(msg_id)` for a row with **`status == "sent"`** to that `recipient`. If delivered → rebuild the `CellWrite`s from the persisted `{row, overdue}` (same shape as `stamp_writes`) and `sheet.update_reminders(...)`; clear that entry's `reported_fail_lines` from `fail.flag`; consume its deferred; **drop the entry**. If not delivered and `queued_at` is older than the **stale-expiry horizon** (PO decision #1) → drop it and **log loud** (the reminders stay unstamped → they re-fire, which is the safe outcome).
3. **Email path unchanged** — `mailer.send_digest()` is the confirmation, so stamp / clear / consume **inline** there (keep current behavior).
4. **outbox-budget#3 folds in:** stop consuming deferred at run start (`read_deferred` peek for assembly), and consume (`pop_deferred`, already made atomic in `67f970e`) only when the carrying digest is **confirmed** (in reconcile, or inline on the SMTP path).

**Why this design:** "Sent" on the Sheet now means *the bridge confirmed delivery*. No timing coupling and no duplicate-on-slow-bridge problem — reconcile stamps whenever the bridge *eventually* confirms (next run, or the one after). A digest that never delivers leaves its reminders unstamped → they re-fire → no silent loss.

**Gotchas (learned the hard way):**
- The digest is queued **per-recipient with the SAME `msg_id`** `brief-daily-{date}`, `to=rcpt`. So `delivery_status("brief-daily-{date}")` returns rows for *both* adar and shanee; match on `to == recipient` **and** `status == "sent"` (the bridge also writes `refused_unknown_recipient` / `send_failed` — those are NOT delivery).
- Recipient ids are `"adar"` / `"shanee"` (`OWNER_TO_RECIPIENTS`, `config.DIGEST_RECIPIENTS`).
- A rerun of the same day is a `queue()` duplicate (idempotent by `(id,target)`); reconcile keys on `msg_id`, so it's naturally idempotent too — guard against double-stamping (drop the pending entry once stamped).

## Tests

**Adapt (4 existing — they encode the OLD "queue = sent" contract and will fail under the new one):**
- `tests/test_engine.py` `TestSendStamping::test_send_stamps_then_rerun_is_noop`, `::test_overdue_send_stamps_overdue_status`
- `tests/test_mailer.py` `TestFailFlag::test_reported_and_cleared_when_queued`, `TestReviewD028::test_delivery_log_baileys_and_rerun_adds_nothing`

These now need to **simulate confirmed delivery** — which is *clean* under cross-run reconcile (no in-run sleep): run once (queues + records pending, no stamp), seed `whatsapp_sent.jsonl` with `{id:"brief-daily-{date}", to:rcpt, status:"sent"}` for the recipients, then call `reconcile_deliveries()` (or run again) and assert the stamp/clear/log. The transport-log expectation also shifts: a queued-but-unconfirmed run is `queued-stale`, a confirmed one is `baileys`.

**Add:**
- confirmed delivery → reminders stamped (`Last Sent` + `Status`).
- unconfirmed (empty `whatsapp_sent.jsonl`) → NOT stamped, reminder stays eligible (re-fires next run).
- a stale pending entry past the horizon → dropped + logged, not stamped.
- **outbox-budget#3:** a budget-deferred alert is consumed only after the carrying digest is confirmed; on an unconfirmed run it remains and re-rides next digest.

## Canon
- **SPEC §7.1** — "Last Sent / Status on send success" → reword to **on confirmed delivery** (the bridge's `whatsapp_sent.jsonl`, reconciled at the next run; the SMTP fallback confirms inline). Add a one-line *why* (the queue-≠-delivered silent-loss this closes).
- **SPEC §7.5** — note the reconcile step + the new pending file.
- **BACKLOG.md** — flip the Lane B status (the "Now" section already tracks it): GAP-2 + budget#3 done; GAP-3 + bridge-node#2 the remaining Lane B.

## PO decisions needed up front
1. **Stale-expiry horizon** for an unconfirmed pending entry. Recommend **48h** (covers a weekend bridge outage; beyond that the email fallback would have taken over on subsequent runs, and the reminders simply re-fire). Pick the number.
2. **Interim-risk-window acknowledgment** (the Lane B review's open question): the silent-loss path has been open since v1; this lane closes it. Just confirm both POs are aware it was a known, accepted gap until now — no action, a note for the record.

## Optional same-lane follow-on (lower priority — a later session is fine)
- **GAP-3** — rotate/compact `whatsapp_sent.jsonl`/`whatsapp_outbox.jsonl` and bound the bridge's per-poll rescan + Python's `_seen_pairs` scan (they grow unbounded). The reconcile's pending file wants the same bounded-history hygiene.
- **bridge-node#2** — a minimal Node test (or documented harness) proving the bridge's scope guard refuses a non-`recipients.json` target and drops a duplicate `(id,target)` — guards the §7.4 hard boundary.

## Definition of done (ENGINEERING §11)
Tests for the new logic green (+ the 4 adapted) · the new constant/path in `config.py` (+ `conftest` tmp_runtime) · errors degrade or surface · `SPEC §7.1/§7.5` + `BACKLOG` updated · **review gate run at close** (delivery/budget touched).

## Handoff (session end → PO runs on their machine)
ONE terminal block: `pytest -q` → `review.py` gate (`--lane automation --provider deepseek`; resolve MAJOR as Apply/Defend/Open) → `git add -A && git reset -q -- .claude` → `git commit` → `git push`. A MAJOR review finding stops the commit until resolved or PO-overridden.
