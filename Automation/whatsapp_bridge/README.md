# WhatsApp bridge — self-hosted, free

The privacy-first bridge from `07_WhatsApp_Group_Summarizer_Spec.md`. Plaintext
group messages never leave the machine; only the Python classifier's per-message
LLM call leaves the house.

## What it does

Pairs as a WhatsApp Web **companion** to Adar's main number (same QR flow as
web.whatsapp.com → Linked devices). Two jobs:

1. **Listen** — group messages only; drops 1:1 chats and media bodies, appends
   each message as one JSON line to `../inbox/whatsapp_inbox.jsonl`.
   `whatsapp_summarizer.py` reads that file.
2. **Send** (added 2026-06-04, Baileys-first decision — Twilio dropped) — polls
   `../outbox/whatsapp_outbox.jsonl` every 15s and delivers each queued row 1:1
   to Adar/Shanee. Python side queues via `Automation/wa_outbox.py`. Delivery is
   recorded per (id, target) in `../outbox/whatsapp_sent.jsonl` (dedup ledger).

## recipients.json (required for sending)

Create next to `auth_state/` on the bridge machine — **never commit**:

```json
{
  "adar":   "9725XXXXXXXX@s.whatsapp.net",
  "shanee": "9725XXXXXXXX@s.whatsapp.net"
}
```

Sending is disabled (listening unaffected) if the file is missing. Any outbox
row addressed to anyone other than these two is refused and logged — that is
the "no messages outside Adar+Shanee" principle enforced in code.

## Run it (one-time pair, then leave running)

```bash
cd Automation/whatsapp_bridge
npm install
node baileys_listener.js     # scan the QR with Adar's phone (Linked devices)
```

Auth persists in `./auth_state/` — restart resumes without re-scanning.

## Where to host (all free)

- An always-on laptop or a Raspberry Pi on home Wi-Fi.
- A cheap second Android via Termux (`pkg install nodejs`).
- Any old phone kept plugged in running nothing else.

Keep it on the home network and the messages stay in the house.

## Notes / caveats

- **Groups are read-only forever** — the bridge never posts to a group. Outbound
  is 1:1 to the two configured recipients only.
- Unofficial WhatsApp Web automation is technically against WhatsApp ToS for
  high-volume commercial use; household volume (a few messages/day, person-to-
  person pattern) keeps the risk profile close to WhatsApp Web on a laptop.
  Sending raises it slightly vs read-only — accepted tradeoff (06-doc 2.5).
- If the bridge machine is down, outbox rows wait on disk and flush on
  reconnect; callers can check staleness via `wa_outbox.bridge_alive()`.
- If it logs out (code 401), delete `auth_state/` and re-pair.
- `auth_state/`, `inbox/`, `outbox/`, `recipients.json`, and `node_modules/`
  are git-ignored — never commit session credentials, numbers, or content.
