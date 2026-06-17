"""
Family inc. — WhatsApp group summarizer (SPEC.md §7.3: hourly)

Reads normalized group messages (from the self-hosted Baileys bridge at
bridge/state/inbox/whatsapp_inbox.jsonl), classifies each into
ROUTINE / DIGEST / ALERT, applies hard-rule overrides, dispatches ALERTs to
the per-group recipients under the family's 2/day alert budget, and builds the
daily "WhatsApp groups (last 24h)" digest that daily_digest.py folds into the
morning message.

Pipeline:
  inbox JSONL  ->  classify (hard rules -> lib/llm.py Haiku -> deterministic)
              ->  per-group routing -> dispatch ALERTs via lib/outbox.queue()
                  (kind=alert|critical, id=wa-{msg_id}; the outbox ledger is
                  the ONLY budget enforcement — D-015. Over-budget alerts are
                  deferred to tomorrow's digest by the outbox itself.)
              ->  append WhatsApp_Inbox + WhatsApp_Archive tabs via lib/sheet
                  (live Sheet when configured; skipped loudly otherwise), then
                  roll the Inbox tab's 30-day window (SPEC §6.2; Archive keeps
                  text forever — D-044)
              ->  build digest markdown (Hebrew, DESIGN §6)

Sender roles (the §7.3 hard rules 2–3 key off them) are resolved from a roster
(seeds/13_Sender_Roster_Seed.csv, gitignored) when the bridge can't label them
— it only knows a JID and a push-name. See load_roster/resolve_role (D-044).

Config: seeds/12_WhatsApp_Group_Config_Seed.csv (group routing + keywords;
gitignored — group names are personal). List columns are ';'-separated.

Runs in MOCK MODE out-of-the-box (no inbox file, no API key needed): it loads a
sample of Hebrew group messages and prints "RUNNING IN MOCK MODE".

Run:
  python3 automation/whatsapp_summarizer.py [--inbox path.jsonl] [--config path.csv]
                                            [--as-of YYYY-MM-DD] [--dry-run]
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/whatsapp_summarizer.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import csv
import json
import logging
import os
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional

from automation import templates as T
from automation.lib import config as cfg
from automation.lib import llm, sheet
from automation.lib.config import DIGEST_GROUP_LABEL, DIGEST_GROUP_ORDER

INBOX_DEFAULT = cfg.INBOX_FILE
CONFIG_DEFAULT = cfg.WA_GROUP_CONFIG
ROSTER_DEFAULT = cfg.SENDER_ROSTER
BRIEFINGS_DIR = cfg.BRIEFINGS_DIR

log = logging.getLogger("wa")

CLASSES = ("ROUTINE", "DIGEST", "ALERT")

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
# Sender → role roster (M4, D-044). The §7.3 hard rules 2–3 fire on sender_role
# (daycare teacher in the evening; vaad_bayit utility), but the Baileys bridge
# can't reliably label a sender's role — it knows a JID and a push-name. The
# roster maps either to a role so the rules trip on real traffic. Personal →
# gitignored seed (seeds/README.md documents the format); absent → empty roster,
# and a message simply keeps whatever role it already carries.
# ---------------------------------------------------------------------------
def load_roster(path: Path) -> dict[str, str]:
    """sender JID OR display name -> role. Blank-role rows are skipped."""
    roster: dict[str, str] = {}
    if not path.exists():
        return roster
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            role = (row.get("role") or "").strip()
            if not role:
                continue
            for key in (row.get("sender_jid"), row.get("sender_name")):
                key = (key or "").strip()
                if key:
                    roster[key] = role
    return roster

def resolve_role(msg: dict, roster: dict[str, str]) -> str:
    """The message's own role wins when it is a real one; otherwise fill it from
    the roster (JID before display name). Messages that already carry an explicit
    role (mock data, tests, a future smarter bridge) are left untouched."""
    have = (msg.get("sender_role") or "").strip()
    if have and have != "unknown":
        return have
    jid = (msg.get("sender_jid") or "").strip()
    name = (msg.get("sender_name") or "").strip()
    return roster.get(jid) or roster.get(name) or have or "unknown"

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
# (generic names only — real group names live in the gitignored seed CSV)
# ---------------------------------------------------------------------------
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
    {"msg_id": "m8", "group_name": "שכונה שלנו", "sender_name": "עידן",
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
    except (ValueError, AttributeError):
        log.warning("_parse_dt: could not parse %r — falling back to datetime.now()", s)
        return datetime.now()

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

def _first_json_obj(raw: str) -> Optional[dict]:
    """First JSON object in an LLM reply, tolerating ```fences``` and trailing
    prose. DeepSeek occasionally appends commentary after the object; a plain
    json.loads then raises 'Extra data' and we'd needlessly drop to the keyword
    fallback (observed live 2026-06-17, D-046). raw_decode reads just the leading
    object and ignores the rest. None when there is no JSON object."""
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start = s.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(s[start:])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None

def llm_classify(msg: dict, cfg: dict, recent: list[dict]) -> Optional[dict]:
    """LLM classification via lib/llm.py (the one provider wrapper — DeepSeek by
    default, Anthropic fallback). None if unavailable or unparseable (caller
    falls back). Sends one message + ≤3 context messages, never whole threads
    (SPEC §8.6)."""
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
    raw = llm.complete(prompt, task="classify", max_tokens=200,
                       source="whatsapp_summarizer", json_mode=True)
    if raw is None:
        return None
    data = _first_json_obj(raw)
    if data is None:
        log.warning("classify reply not JSON-parseable — deterministic fallback")
        return None
    if data.get("classification") not in CLASSES:
        return None
    return data

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
# Per-group routing + alert dispatch (budget enforced ONLY by the outbox
# ledger — D-015; this script keeps no counter of its own)
# ---------------------------------------------------------------------------
def owner_from_recipients(recipients: str) -> str:
    return {"both": "both", "adar": "adar", "shanee": "shanee"}.get(recipients, "none")


def alert_body(msg: dict, one_liner: str, group_type: str, critical: bool) -> str:
    """DESIGN §6 single-line shape: Hebrew type label, sender, HH:MM."""
    tpl = T.CRITICAL_LINE if critical else T.ALERT_LINE
    return tpl.format(
        group=DIGEST_GROUP_LABEL.get(group_type, msg["group_name"]),
        one_liner=one_liner,
        sender=msg.get("sender_name", "?"),
        time=f"{_parse_dt(msg.get('received_at', '')):%H:%M}",
    )


def dispatch_alert(msg: dict, one_liner: str, recipients: str, group_type: str,
                   dry_run: bool, critical: bool = False) -> bool:
    """Queue toward the phones via lib/outbox.queue() (D-010: Baileys-first).
    kind=critical bypasses budget + quiet hours; kind=alert is subject to the
    shared 2/day ledger — over-budget targets are deferred by the OUTBOX into
    tomorrow's digest (SPEC §7.5), not downgraded here. Stable id wa-{msg_id}
    keeps reruns idempotent. Returns True if at least one target was queued."""
    tag = "CRITICAL " if critical else ""
    line = f"[{tag}ALERT → {recipients}] {msg['group_name']}: {one_liner}"
    print("  " + line)
    if dry_run:
        return False
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    log_path = BRIEFINGS_DIR / f"whatsapp_alerts_{date.today().isoformat()}.md"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"- {datetime.now():%H:%M} {line}\n")
    from automation.lib.outbox import bridge_alive, queue
    to = recipients if recipients in ("adar", "shanee", "both") else "both"
    res = queue(to, alert_body(msg, one_liner, group_type, critical),
                "critical" if critical else "alert",
                source="whatsapp_summarizer", msg_id=f"wa-{msg.get('msg_id', '')}")
    if res.deferred:
        print(f"  (budget: deferred to tomorrow's digest for {res.deferred})")
    if res.queued and not bridge_alive():
        print("  [warn] bridge heartbeat stale — alert queued, delivery waits for reconnect")
    return bool(res.queued)

# ---------------------------------------------------------------------------
# Persistence — WhatsApp_Inbox + WhatsApp_Archive tabs of the master Sheet
# (lib/sheet.py; the CSV staging buffer is gone since M2). Without a live
# backend (mock/dev) appends are skipped loudly — never written to the seed
# template. The Inbox tab's 30-day rolloff (SPEC §6.2) runs in run() after a
# successful append (sheet.roll_off_old_rows; D-044) — Archive is never rolled.
# ---------------------------------------------------------------------------
INBOX_COLS = sheet.WA_INBOX_COLUMNS
ARCHIVE_COLS = sheet.WA_ARCHIVE_COLUMNS


def _processed_ids(sheet_path: Optional[Path] = None) -> set[str]:
    """msg_ids already written to the WhatsApp_Inbox tab, so reruns don't
    double-process (exactly-once together with the outbox wa-{msg_id} dedup)."""
    return {str(v).strip()
            for v in sheet.read_column(cfg.WA_INBOX_SHEET_TAB, "msg_id", sheet_path)}


def persist_rows(processed: list[dict], sheet_path: Optional[Path] = None,
                 live_override: Optional[bool] = None) -> bool:
    """Append this run's rows to the Inbox (full row) + Archive (text-forever
    subset) tabs in two batched calls. Returns False when skipped (no live
    backend and no explicit path)."""
    live = sheet.is_live() if live_override is None else live_override
    if sheet_path is None and not live:
        print("(no live Sheet backend — Inbox/Archive rows NOT appended)")
        return False
    sheet.append_rows(cfg.WA_INBOX_SHEET_TAB, INBOX_COLS, processed, sheet_path)
    sheet.append_rows(cfg.WA_ARCHIVE_SHEET_TAB, ARCHIVE_COLS, processed, sheet_path)
    return True

# ---------------------------------------------------------------------------
# Bridge health (applied from Gemini review 2026-06-02)
# ---------------------------------------------------------------------------
BRIDGE_STALE_HOURS = cfg.BRIDGE_STALE_HOURS  # group silence this long is suspect

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
        return T.BRIDGE_SILENT.format(hours=age_h)
    return None

# ---------------------------------------------------------------------------
# Digest builder — the קבוצות section of the morning message (DESIGN §6:
# flat list, Hebrew type label inline, ordered by group type then time;
# warnings prepend, never replace; counts live in console/logs, not copy)
# ---------------------------------------------------------------------------
def build_digest(processed: list[dict], today: date, warning: Optional[str] = None) -> str:
    window_start = datetime.combine(today, time.min) - timedelta(hours=24)
    shown = [p for p in processed
             if p["classification"] in ("DIGEST", "ALERT")
             and _parse_dt(p["received_at"]) >= window_start]

    lines = []
    if warning:
        lines += [warning, ""]
    # ALERTs with nobody to route to (digest_only groups) float to the top
    floated = [p for p in shown if p["classification"] == "ALERT" and p["action_owner"] == "none"]
    if floated:
        lines.append(T.WA_NEEDS_A_LOOK)
        for p in floated:
            lines.append(T.WA_NEEDS_A_LOOK_ITEM.format(
                one_liner=p["one_liner"], sender=p["sender_name"],
                time=f"{_parse_dt(p['received_at']):%H:%M}"))
        lines.append("")
    body = [p for p in shown if p not in floated]
    if body:
        lines.append(T.WA_SECTION_HEAD)
        order = {g: i for i, g in enumerate(DIGEST_GROUP_ORDER)}
        body.sort(key=lambda p: (order.get(p["group_type"], len(order)),
                                 _parse_dt(p["received_at"])))
        for p in body:
            lines.append(T.WA_ITEM.format(
                group=DIGEST_GROUP_LABEL.get(p["group_type"], p["group_type"]),
                one_liner=p["one_liner"], sender=p["sender_name"],
                time=f"{_parse_dt(p['received_at']):%H:%M}"))
    return "\n".join(lines).rstrip() + ("\n" if lines else "")

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def run(inbox_path: Path, config_path: Path, today: date, dry_run: bool,
        sheet_path: Optional[Path] = None, roster_path: Optional[Path] = None) -> Path:
    cfg_groups = load_config(config_path)
    roster = load_roster(roster_path or ROSTER_DEFAULT)
    messages, is_mock = load_inbox(inbox_path)
    use_llm = llm.available()
    if not use_llm:
        print("(no LLM provider key — using deterministic classifier; hard rules still fire)")

    # process in chronological order so 'recent context' is correct
    messages = sorted(messages, key=lambda m: _parse_dt(m.get("received_at", "")))

    # skip messages already in the Inbox tab (avoids re-alerting on rerun)
    already = _processed_ids(sheet_path) if (sheet_path or sheet.is_live()) else set()
    if already:
        before = len(messages)
        messages = [m for m in messages if m.get("msg_id") not in already]
        if before != len(messages):
            print(f"(skipping {before - len(messages)} already-processed messages)")

    seen_by_group: dict[str, list[dict]] = {}
    processed: list[dict] = []
    alerts_queued = 0

    for msg in messages:
        msg["sender_role"] = resolve_role(msg, roster)  # roster fills what the bridge can't
        gname = msg["group_name"]
        c = group_cfg(cfg_groups, gname)
        recent = seen_by_group.get(gname, [])
        result = classify(msg, cfg_groups, recent, use_llm)
        seen_by_group.setdefault(gname, []).append(msg)

        recipients = c["alert_recipients"]
        dispatched = False
        dispatched_at = ""
        action_owner = "none"
        critical = result.get("critical", False)
        if result["classification"] == "ALERT":
            if recipients == "none":
                action_owner = "none"  # float to digest "needs a look"
            else:
                action_owner = owner_from_recipients(recipients)
                # The outbox is the only budget authority (D-015): in-budget →
                # queued now; over-budget → it defers the body to tomorrow's
                # digest and logs alert_suppressed_by_budget. Either way the
                # row stays classified ALERT here — what happened to it is the
                # outbox ledger's record, not a reclassification.
                dispatched = dispatch_alert(msg, result["one_liner"], recipients,
                                            c["group_type"], dry_run, critical=critical)
                if dispatched:
                    alerts_queued += 1
                    dispatched_at = datetime.combine(
                        today, datetime.now().time()).isoformat(timespec="seconds")

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

    # console summary (budget state lives in the outbox ledger, logs/outbox_ledger/)
    print(f"\nProcessed {len(processed)} messages "
          f"({'MOCK' if is_mock else 'live'}) · alerts queued this run: {alerts_queued}")
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
        if persist_rows(processed, sheet_path):
            print(f"appended {len(processed)} row(s) to "
                  f"{cfg.WA_INBOX_SHEET_TAB} + {cfg.WA_ARCHIVE_SHEET_TAB}")
            # 30-day hot-tab rolloff (SPEC §6.2) — only after a real append, so
            # the seed is never touched; Archive keeps text forever.
            cutoff = today - timedelta(days=cfg.WA_INBOX_RETENTION_DAYS)
            rolled = sheet.roll_off_old_rows(
                cfg.WA_INBOX_SHEET_TAB, "received_at", cutoff, sheet_path)
            if rolled:
                print(f"rolled off {rolled} {cfg.WA_INBOX_SHEET_TAB} row(s) "
                      f"older than {cutoff} ({cfg.WA_INBOX_RETENTION_DAYS}d)")
        print(f"wrote {digest_path}")
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
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(Path(args.inbox) if args.inbox else INBOX_DEFAULT,
        Path(args.config) if args.config else CONFIG_DEFAULT,
        today, args.dry_run)

if __name__ == "__main__":
    main()
