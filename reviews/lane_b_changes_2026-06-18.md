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
