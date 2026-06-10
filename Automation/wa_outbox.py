"""
Family inc. — WhatsApp outbox writer (Baileys-first delivery).

Decision 2026-06-04 (Adar): alerts + briefings go out through the self-hosted
Baileys bridge, NOT Twilio. Every automation that wants to send a WhatsApp
message calls queue_message() here; the bridge (whatsapp_bridge/
baileys_listener.js) polls the outbox and delivers within ~15s.

Contract
--------
Outbox file:  Automation/outbox/whatsapp_outbox.jsonl
Row:          {"id": uuid, "to": "adar"|"shanee"|"both", "body": str,
               "source": str, "queued_at": iso8601}
Sent ledger:  Automation/outbox/whatsapp_sent.jsonl (bridge-written; one row
              per (id, target): status sent | refused_unknown_recipient)

Delivery guarantee is at-least-once from this side's perspective: the queue is
durable on disk, the bridge dedups per (id, target) against the sent ledger.
If the bridge machine is down, rows wait. Callers that care should check
bridge_alive() and surface a warning instead of assuming delivery.

The 2/day alert BUDGET is NOT enforced here — it stays with the callers
(reminders engine, whatsapp_summarizer), same as in the Twilio design.
Briefings are exempt from the budget by principle ("briefings > notifications").
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTBOX_DIR = ROOT / "outbox"
OUTBOX_FILE = OUTBOX_DIR / "whatsapp_outbox.jsonl"
SENT_FILE = OUTBOX_DIR / "whatsapp_sent.jsonl"
HEARTBEAT_FILE = ROOT / "inbox" / "heartbeat.txt"

VALID_RECIPIENTS = {"adar", "shanee", "both"}
STALE_AFTER = timedelta(minutes=45)  # heartbeat is written at least every 15m


def queue_message(to: str, body: str, source: str = "unknown") -> str:
    """Append one message to the outbox. Returns the message id.

    `to` must be adar/shanee/both — anything else raises here, and the bridge
    refuses it again on its side (defense in depth).
    """
    if to not in VALID_RECIPIENTS:
        raise ValueError(f"recipient must be one of {VALID_RECIPIENTS}, got {to!r}")
    if not body or not body.strip():
        raise ValueError("empty message body")
    OUTBOX_DIR.mkdir(exist_ok=True)
    msg_id = str(uuid.uuid4())
    row = {
        "id": msg_id,
        "to": to,
        "body": body.strip(),
        "source": source,
        "queued_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with OUTBOX_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return msg_id


def bridge_alive(now: datetime | None = None) -> bool:
    """True if the bridge heartbeat is fresh. Callers surface a warning when
    False — queued messages will still go out when the bridge returns."""
    try:
        ts = datetime.fromisoformat(HEARTBEAT_FILE.read_text().strip().replace("Z", "+00:00"))
    except (OSError, ValueError):
        return False
    now = now or datetime.now(ts.tzinfo)
    return (now - ts) <= STALE_AFTER


def delivery_status(msg_id: str) -> list[dict]:
    """Sent-ledger rows for one message id (one per target). Empty = pending."""
    if not SENT_FILE.exists():
        return []
    rows = []
    for line in SENT_FILE.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("id") == msg_id:
            rows.append(row)
    return rows


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] in VALID_RECIPIENTS:
        mid = queue_message(sys.argv[1], " ".join(sys.argv[2:]), source="cli")
        alive = bridge_alive()
        print(f"queued {mid} → {sys.argv[1]} (bridge {'alive' if alive else 'DOWN — will send on reconnect'})")
    else:
        print("usage: python wa_outbox.py adar|shanee|both <message text>")
