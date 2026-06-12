"""
Family inc. — configuration. ALL constants live here (ENGINEERING.md §3).

No constant may be defined in a script: the 2026-06-11 audit found
`ALERT_BUDGET_PER_DAY` defined twice with independent ledgers — the class of
bug this rule exists to prevent.

Secrets are NEVER here. They live in `/etc/family-inc/env` on the appliance
(`load_env()` reads it when present) or in the developer's shell env.
Values in this file are committed and must stay non-personal.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — lib/ → automation/ → repo root
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_DIR = ROOT / "automation"

# Master data. The local xlsx is a SEED TEMPLATE only (D-016) — the gspread
# port (M2) replaces these reads with the live Google Sheet.
SHEET_PATH = ROOT / "Family_OS.xlsx"

# Runtime output (gitignored)
BRIEFINGS_DIR = ROOT / "Briefings"
LOGS_DIR = ROOT / "logs"
REMINDERS_LOG = LOGS_DIR / "reminders_log.csv"
LLM_COSTS_LOG = LOGS_DIR / "llm_costs.csv"
OUTBOX_LEDGER_DIR = LOGS_DIR / "outbox_ledger"

# Bridge state (gitignored; the Node listener shares these paths)
BRIDGE_DIR = AUTOMATION_DIR / "bridge"
BRIDGE_STATE_DIR = BRIDGE_DIR / "state"
OUTBOX_FILE = BRIDGE_STATE_DIR / "outbox" / "whatsapp_outbox.jsonl"
SENT_FILE = BRIDGE_STATE_DIR / "outbox" / "whatsapp_sent.jsonl"
DEFERRED_FILE = BRIDGE_STATE_DIR / "outbox" / "deferred.jsonl"
INBOX_FILE = BRIDGE_STATE_DIR / "inbox" / "whatsapp_inbox.jsonl"
HEARTBEAT_FILE = BRIDGE_STATE_DIR / "inbox" / "heartbeat.txt"

# Summarizer staging CSVs (interim until the M2 gspread port; gitignored)
DATA_DIR = AUTOMATION_DIR / "data"
WA_INBOX_TAB = DATA_DIR / "WhatsApp_Inbox.csv"
WA_ARCHIVE_TAB = DATA_DIR / "WhatsApp_Archive.csv"

# Seeds (personal values → gitignored, stay on the machines that need them)
SEEDS_DIR = ROOT / "seeds"
WA_GROUP_CONFIG = SEEDS_DIR / "12_WhatsApp_Group_Config_Seed.csv"

# Misc caches (gitignored)
CACHE_DIR = AUTOMATION_DIR / "cache"

# ---------------------------------------------------------------------------
# Alerting policy (SPEC.md §8.1–8.3)
# ---------------------------------------------------------------------------
ALERT_BUDGET_PER_DAY = 2     # unsolicited messages / recipient / day (hard cap)
TOMBSTONE_SKIP_HOURS = 6     # engine skips rows tombstoned within this window
OVERDUE_REPEAT_DAYS = 3      # overdue reminders re-fire at most every N days
QUIET_HOURS_START = 22       # 22:00 local — alerts + briefings hold
QUIET_HOURS_END = 7          # 07:00 local — held messages release
BATCH_WINDOW_MINUTES = 5     # rerun-within-window fires are deduplicated

# Digest shaping (reminders engine → daily digest)
DIGEST_MAX_ITEMS = 5                  # keep the morning message short
DROP_FIRST_DOMAINS = {"Goals"}        # de-prioritised — covered by the weekly briefing
ALWAYS_INCLUDE_DOMAINS = {"Health"}   # never trimmed

# ---------------------------------------------------------------------------
# Weekly briefing
# ---------------------------------------------------------------------------
WEEK_AHEAD_DAYS = 7
GOAL_MILESTONE_FLAG_DAYS = 30   # flag goals whose target date is within 30 days
STALE_GOAL_UPDATE_DAYS = 21     # warn if goal Last Update older than 3 weeks

# ---------------------------------------------------------------------------
# WhatsApp summarizer
# ---------------------------------------------------------------------------
BRIDGE_STALE_HOURS = 12          # group silence this long is suspect
HEARTBEAT_STALE_MINUTES = 45     # bridge heartbeat is written at least every 15m
WA_INBOX_RETENTION_DAYS = 30     # inbox CSV rows roll to monthly archives
DIGEST_GROUP_ORDER = ["daycare", "building", "family", "neighborhood", "student", "other"]
DIGEST_GROUP_LABEL = {
    "daycare": "DAYCARE", "building": "BUILDING", "family": "FAMILY",
    "neighborhood": "NEIGHBORHOOD", "student": "STUDENT", "other": "OTHER",
}

# ---------------------------------------------------------------------------
# LLM (SPEC.md §8.7 — model ids live here, not at call sites)
# ---------------------------------------------------------------------------
MODELS = {
    "classify": "claude-haiku-4-5",   # WhatsApp triage
    "briefing": "claude-haiku-4-5",   # weekly-briefing prose (wired at M2)
}
LLM_FAKE_ENV = "FAMILY_INC_LLM_FAKE"  # tests inject a canned response here

# ---------------------------------------------------------------------------
# Hebcal
# ---------------------------------------------------------------------------
HEBCAL_GEONAME_ID = 294801   # nearest metro (Haifa) — same coastal zman as home
HEBCAL_TTL_SECONDS = 24 * 60 * 60

# ---------------------------------------------------------------------------
# Secrets loading (appliance: /etc/family-inc/env, mode 600)
# ---------------------------------------------------------------------------
ENV_FILE = Path("/etc/family-inc/env")


def load_env(path: Path = ENV_FILE) -> None:
    """Load KEY=VALUE lines into os.environ (existing env wins). No-op when
    the file is absent — dev machines use their shell env instead."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"'))
