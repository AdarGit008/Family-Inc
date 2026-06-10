"""
Family inc. — WhatsApp group summarizer

Reads normalized group messages (from the self-hosted Baileys bridge at
whatsapp_bridge/inbox/whatsapp_inbox.jsonl), classifies each into
ROUTINE / DIGEST / ALERT, applies hard-rule overrides, dispatches ALERTs to
the per-group recipients under the family's 2/day alert budget, and builds the
daily "WhatsApp groups (last 24h)" digest that prepends to the morning briefing.

Pipeline (Phases A–E of 07_WhatsApp_Group_Summarizer_Spec.md):
  inbox JSONL  ->  classify (hard rules -> Claude Haiku -> deterministic)
              ->  per-group routing + 2/day budget  ->  dispatch ALERTs
              ->  append WhatsApp_Inbox.csv + WhatsApp_Archive.csv
              ->  build digest markdown

Config: Setup/12_WhatsApp_Group_Config_Seed.csv (group routing + keywords).
List columns (close_contacts, alert_keywords) are ';'-separated.

Runs in MOCK MODE out-of-the-box (no inbox file, no API key needed): it loads a
sample of Hebrew group messages and prints "RUNNING IN MOCK MODE".

Run:
  python whatsapp_summarizer.py [--inbox path.jsonl] [--config path.csv]
                                [--as-of YYYY-MM-DD] [--dry-run]

Alert dispatch is a single function (`dispatch_alert`) — swap the mock body for
the Twilio WhatsApp send when provisioned, exactly like reminders_engine.py.
"""
from __future__ import annotations
import argparse
import csv
import json
import logging
import os
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent
SETUP_DIR = ROOT.parent / "Setup"
BRIEFINGS_DIR = ROOT.parent / "Briefings"
DATA_DIR = ROOT / "data"
INBOX_DEFAULT = ROOT / "whatsapp_bridge" / "inbox" / "whatsapp_inbox.jsonl"
CONFIG_DEFAULT = SETUP_DIR / "12_WhatsApp_Group_Config_Seed.csv"
INBOX_TAB = DATA_DIR / "WhatsApp_Inbox.csv"
ARCHIVE_TAB = DATA_DIR / "WhatsApp_Archive.csv"

log = logging.getLogger("wa")

ALERT_BUDGET_PER_DAY = 2  # shared family-wide cap (operating principle)
CLASSES = ("ROUTINE", "DIGEST", "ALERT")
DIGEST_GROUP_ORDER = ["daycare", "building", "family", "neighborhood", "student", "other"]
DIGEST_GROUP_LABEL = {
    "daycare": "DAYCARE", "building": "BUILDING", "family": "FAMILY",
    "neighborhood": "NEIGHBORHOOD", "student": "STUDENT", "other": "OTHER",
}

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
# ---------------------------------------------------------------------------
_NOW = datetime(2026, 6, 2, 8, 0)  # overridden by --as-of
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
    {"msg_id": "m8", "group_name": "שכונה - ⟨town⟩", "sender_name": "עידן",
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
    except ValueError:
        return _NOW

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

    # Rule 0 — critical/safety keywords: budget-exempt
    for pat in c["critical_keywords"]:
        if pat.search(text):
            return f"CRITICAL keyword /{pat.pattern}/", True
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

def llm_classify(msg: dict, cfg: dict, recent: list[dict]) -> Optional[dict]:
    """Claude Haiku classification. None if unavailable (caller falls back)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed — deterministic fallback")
        return None
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
    try:
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model="claude-haiku-4-5", max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (resp.content[0].text or "").strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
        if data.get("classification") not in CLASSES:
            return None
        return data
    except Exception as e:
        log.warning("Haiku classify failed (%s) — deterministic fallback", e)
        return None

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

    # Rule 5 — muted group never alerts (handled in deterministic too)
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
# Per-group routing + alert dispatch (budget-aware)
# ---------------------------------------------------------------------------
def owner_from_recipients(recipients: str) -> str:
    return {"both": "both", "adar": "adar", "shanee": "shanee"}.get(recipients, "none")

def dispatch_alert(msg: dict, one_liner: str, recipients: str, dry_run: bool,
                   critical: bool = False) -> None:
    """LIVE: queue to the Baileys outbox (decision 2026-06-04: Baileys-first,
    no Twilio). Dry-run prints only; non-dry-run also logs + queues."""
    tag = "CRITICAL " if critical else ""
    line = f"[{tag}ALERT → {recipients}] {msg['group_name']}: {one_liner}"
    print("  " + line)
    if dry_run:
        return
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    log_path = BRIEFINGS_DIR / f"whatsapp_alerts_{date.today().isoformat()}.md"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"- {datetime.now():%H:%M} {line}\n")
    # --- Baileys outbox (was: Twilio swap point) ---
    from wa_outbox import bridge_alive, queue_message
    body = f"{'🚨 ' if critical else ''}{msg['group_name']}: {one_liner}"
    to = recipients if recipients in ("adar", "shanee", "both") else "both"
    queue_message(to, body, source="whatsapp_summarizer")
    if not bridge_alive():
        print("  [warn] bridge heartbeat stale — alert queued, delivery waits for reconnect")

# ---------------------------------------------------------------------------
# Persistence — local CSV STAGING for the two Family_OS tabs
#
# Source-of-truth note (Gemini review 2026-06-02, defended): Family_OS (Google
# Sheets) remains the master DB. These CSVs are an interim staging buffer —
# the same pre-credentials posture as reminders_engine.py's email fallback.
# TODO(gspread): when FAMILY_INC_SHEET creds are wired, _append_csv becomes a
# Sheets append to the WhatsApp_Inbox / WhatsApp_Archive tabs and these files
# go away. Until then nothing else reads them, so no second source of truth.
# ---------------------------------------------------------------------------
INBOX_COLS = ["msg_id", "group_name", "group_type", "sender_name", "sender_role",
              "received_at", "text", "has_media", "classification", "one_liner",
              "action_required", "action_owner", "critical", "dispatched",
              "dispatched_at", "digested_at"]
ARCHIVE_COLS = ["msg_id", "group_name", "sender_name", "received_at", "text", "one_liner"]

def _processed_ids(path: Path) -> set[str]:
    """msg_ids already written to the inbox tab, so reruns don't double-process."""
    if not path.exists():
        return set()
    ids: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            mid = (row.get("msg_id") or "").strip()
            if mid:
                ids.add(mid)
    return ids

def alerts_dispatched_today(path: Path, today: date) -> int:
    """Count ALERTs actually *sent* today (keyed on dispatch time, not message
    receipt) so the hourly run honors the daily budget across runs — and so a
    late-night message processed after midnight counts against the right day."""
    if not path.exists():
        return 0
    n = 0
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("dispatched", "")).strip().lower() != "true":
                continue
            if str(row.get("critical", "")).strip().lower() == "true":
                continue  # critical alerts are budget-exempt
            try:
                if _parse_dt(row.get("dispatched_at", "")).date() == today:
                    n += 1
            except Exception:
                continue
    return n

def _append_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})

# ---------------------------------------------------------------------------
# Bridge health (applied from Gemini review 2026-06-02)
# ---------------------------------------------------------------------------
BRIDGE_STALE_HOURS = 12  # daycare/building groups are chatty; silence this long is suspect

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
        return (f"⚠ BRIDGE SILENT {age_h:.0f}h — baileys_listener may be down "
                f"(check the always-on machine / re-pair QR)")
    return None

# ---------------------------------------------------------------------------
# Digest builder (Phase E)
# ---------------------------------------------------------------------------
def build_digest(processed: list[dict], today: date, warning: Optional[str] = None) -> str:
    """Grouped 'WhatsApp groups (last 24h)' digest, spec format."""
    window_start = datetime.combine(today, time.min) - timedelta(hours=24)
    shown = [p for p in processed
             if p["classification"] in ("DIGEST", "ALERT")
             and _parse_dt(p["received_at"]) >= window_start]

    by_type: dict[str, list[dict]] = {}
    for p in shown:
        by_type.setdefault(p["group_type"], []).append(p)

    lines = ["WhatsApp groups (last 24h)", "─" * 26]
    if warning:
        lines += [warning, ""]
    # Flag any ALERT that had nobody to route to (digest_only groups) up top
    floated = [p for p in shown if p["classification"] == "ALERT" and p["action_owner"] == "none"]
    if floated:
        lines.append("⚠ NEEDS A LOOK")
        for p in floated:
            lines.append(f"  • {p['one_liner']} ({p['sender_name']}, {_parse_dt(p['received_at']):%H:%M})")
        lines.append("")
    for gtype in DIGEST_GROUP_ORDER:
        items = by_type.get(gtype)
        if not items:
            continue
        lines.append(DIGEST_GROUP_LABEL.get(gtype, gtype.upper()))
        for p in sorted(items, key=lambda x: _parse_dt(x["received_at"])):
            tag = "" if p["classification"] != "ALERT" else " [alert]"
            lines.append(f"  • {p['one_liner']} ({p['sender_name']}, {_parse_dt(p['received_at']):%H:%M}){tag}")
        lines.append("")
    alerts_fired = sum(1 for p in processed if p.get("dispatched"))
    digested = len(shown)
    lines.append(f"{alerts_fired} alerts fired today · {digested} messages digested")
    return "\n".join(lines).rstrip() + "\n"

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run(inbox_path: Path, config_path: Path, today: date, dry_run: bool) -> Path:
    cfg = load_config(config_path)
    messages, is_mock = load_inbox(inbox_path)
    use_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not use_llm:
        print("(no ANTHROPIC_API_KEY — using deterministic classifier; hard rules still fire)")

    # process in chronological order so 'recent context' is correct
    messages = sorted(messages, key=lambda m: _parse_dt(m.get("received_at", "")))

    # skip messages already processed in a previous run (avoids re-alerting)
    already = _processed_ids(INBOX_TAB)
    if already:
        before = len(messages)
        messages = [m for m in messages if m.get("msg_id") not in already]
        if before != len(messages):
            print(f"(skipping {before - len(messages)} already-processed messages)")

    seen_by_group: dict[str, list[dict]] = {}
    # seed today's alert budget from what's already been dispatched today
    budget_used = alerts_dispatched_today(INBOX_TAB, today)
    if budget_used:
        print(f"(already dispatched {budget_used} alert(s) today — {ALERT_BUDGET_PER_DAY - budget_used} left in budget)")
    processed: list[dict] = []

    for msg in messages:
        gname = msg["group_name"]
        c = group_cfg(cfg, gname)
        recent = seen_by_group.get(gname, [])
        result = classify(msg, cfg, recent, use_llm)
        seen_by_group.setdefault(gname, []).append(msg)

        recipients = c["alert_recipients"]
        dispatched = False
        dispatched_at = ""
        action_owner = "none"
        critical = result.get("critical", False)
        if result["classification"] == "ALERT":
            if recipients == "none":
                action_owner = "none"  # float to digest "needs a look"
            elif not critical and budget_used >= ALERT_BUDGET_PER_DAY:
                # tiered budget: standard alerts capped at 2/day; critical bypasses
                result["classification"] = "DIGEST"
                result["reason"] = (result.get("reason", "") + "; alert suppressed by budget").strip("; ")
                log.info("alert suppressed by budget: %s", result["one_liner"])
            else:
                action_owner = owner_from_recipients(recipients)
                dispatch_alert(msg, result["one_liner"], recipients, dry_run,
                               critical=critical)
                if not critical:
                    budget_used += 1  # critical alerts don't consume the budget
                dispatched = True
                # pin to the run's calendar day so budget is keyed on send-day
                dispatched_at = datetime.combine(today, datetime.now().time()).isoformat(timespec="seconds")

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

    # console summary
    print(f"\nProcessed {len(processed)} messages "
          f"({'MOCK' if is_mock else 'live'}) · alerts fired: {budget_used}/{ALERT_BUDGET_PER_DAY}")
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
        _append_csv(INBOX_TAB, INBOX_COLS, processed)
        _append_csv(ARCHIVE_TAB, ARCHIVE_COLS, processed)  # text+summary, never rolls off
        print(f"wrote {digest_path}")
        print(f"appended {INBOX_TAB} and {ARCHIVE_TAB}")
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
    global _NOW
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    _NOW = datetime.combine(today, time(8, 0))
    run(Path(args.inbox) if args.inbox else INBOX_DEFAULT,
        Path(args.config) if args.config else CONFIG_DEFAULT,
        today, args.dry_run)

if __name__ == "__main__":
    main()
