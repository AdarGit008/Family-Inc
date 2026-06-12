# WhatsApp bridge — self-hosted, free

The privacy-first delivery path of `SPEC.md` §7.4/§8.6. Plaintext group
messages never leave the machine; only the classifier's per-message LLM call
(one message + ≤3 context lines) leaves the house.

## What it does

Pairs as a WhatsApp Web **companion** to Adar's main number (same QR flow as
web.whatsapp.com → Linked devices). Two jobs:

1. **Listen** — group messages only; drops 1:1 chats and media bodies, appends
   each message as one JSON line to `state/inbox/whatsapp_inbox.jsonl`.
   `whatsapp_summarizer.py` reads that file hourly.
2. **Send** (D-010: Baileys-first) — polls `state/outbox/whatsapp_outbox.jsonl`
   every 15s and delivers each queued row 1:1 to Adar/Shanee. The Python side
   queues ONLY via `automation/lib/outbox.py` (the chokepoint: budget ledger,
   dedup, quiet-hours `not_before`). Delivery is recorded per (id, target) in
   `state/outbox/whatsapp_sent.jsonl` (dedup ledger).

Reply parsing (1:1 commands) is PARKED until v1.1 — see `BACKLOG.md`.

## recipients.json (required for sending)

Create at `/etc/family-inc/recipients.json` on the appliance (mode 600 — all
secrets live there, ENGINEERING §2). A local `recipients.json` in this
directory still works as the creds-less-dev fallback — **never commit it**:

```json
{
  "adar":   "9725XXXXXXXX@s.whatsapp.net",
  "shanee": "9725XXXXXXXX@s.whatsapp.net"
}
```

Sending is disabled (listening unaffected) if the file is missing. Any outbox
row addressed to anyone other than these two is refused and logged — that is
the "no messages outside Adar+Shanee" principle enforced in code.

## Run it (full provisioning: ENGINEERING.md §5)

```bash
cd automation/bridge
npm ci
node baileys_listener.js     # scan the QR with Adar's phone (Linked devices)
```

Auth persists in `state/auth_state/` — restart resumes without re-scanning.
It is covered by the weekly backup; **after a VPS rebuild, restore it before
considering a re-pair** (a fresh QR scan is the fallback, not the default).

## Notes / caveats

- **Groups are read-only forever** — the bridge never posts to a group.
  Outbound is 1:1 to the two configured recipients only.
- Unofficial WhatsApp Web automation carries account-ban risk (SPEC §8.6,
  accepted); household volume + person-to-person pattern keep it low. The
  fallback chain is SPEC §10.
- If the bridge machine is down, outbox rows wait on disk and flush on
  reconnect; callers can check staleness via `lib/outbox.bridge_alive()`.
- If it logs out (code 401), restore or delete `state/auth_state/` and re-pair.
- `state/`, `recipients.json`, and `node_modules/` are git-ignored — never
  commit session credentials, numbers, or content.
