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

# Master data (D-016). When FAMILY_INC_SHEET_ID is set (the appliance), every
# read/write goes to the live Google Sheet via lib/sheet.py's gspread backend.
# Without it (tests, creds-less dev) lib/sheet.py falls back to the local seed
# xlsx — a TEMPLATE, never a source of truth, and never written by default.
SHEET_PATH = ROOT / "Family_OS.xlsx"
SHEET_ID_ENV = "FAMILY_INC_SHEET_ID"              # spreadsheet id → live backend on
SA_JSON_ENV = "FAMILY_INC_SA_JSON"                # optional override of the path below
SA_JSON_DEFAULT = Path("/etc/family-inc/service-account.json")

# Tab names with code contracts (SPEC §6) — one definition, both backends.
REMINDERS_TAB = "Reminders"
SETTINGS_TAB = "Settings"
WA_INBOX_SHEET_TAB = "WhatsApp_Inbox"
WA_ARCHIVE_SHEET_TAB = "WhatsApp_Archive"

# Runtime output (gitignored)
BRIEFINGS_DIR = ROOT / "Briefings"
LOGS_DIR = ROOT / "logs"
REMINDERS_LOG = LOGS_DIR / "reminders_log.csv"
LLM_COSTS_LOG = LOGS_DIR / "llm_costs.csv"
OUTBOX_LEDGER_DIR = LOGS_DIR / "outbox_ledger"
SCHEMA_DRIFT_FLAG = LOGS_DIR / "schema_drift.flag"   # written on §7.1 header mismatch;
                                                     # cleared by the next clean read;
                                                     # surfaced by the weekly briefing
ENGINE_FLAGS = LOGS_DIR / "engine_flags.jsonl"       # rows needing human review
                                                     # (Feb-29 clamps, Custom recurrence)

# Bridge state (gitignored; the Node listener shares these paths)
BRIDGE_DIR = AUTOMATION_DIR / "bridge"
BRIDGE_STATE_DIR = BRIDGE_DIR / "state"
OUTBOX_FILE = BRIDGE_STATE_DIR / "outbox" / "whatsapp_outbox.jsonl"
SENT_FILE = BRIDGE_STATE_DIR / "outbox" / "whatsapp_sent.jsonl"
DEFERRED_FILE = BRIDGE_STATE_DIR / "outbox" / "deferred.jsonl"
INBOX_FILE = BRIDGE_STATE_DIR / "inbox" / "whatsapp_inbox.jsonl"
HEARTBEAT_FILE = BRIDGE_STATE_DIR / "inbox" / "heartbeat.txt"

# Seeds (personal values → gitignored, stay on the machines that need them)
SEEDS_DIR = ROOT / "seeds"
WA_GROUP_CONFIG = SEEDS_DIR / "12_WhatsApp_Group_Config_Seed.csv"
# Sender → role roster (M4, D-044): maps a sender JID or display name to a role
# (teacher / vaad_bayit / …) so the §7.3 hard rules 2–3 don't depend on the
# bridge labelling sender_role — it only knows a JID and a push-name. PERSONAL →
# gitignored seed (format documented in seeds/README.md); absent → empty roster,
# and a message keeps whatever role it already carries.
SENDER_ROSTER = SEEDS_DIR / "13_Sender_Roster_Seed.csv"

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
NOTES_MAX_CHARS = 120                 # DESIGN §6: notes ride along only when short
# The two adults — the ONLY message recipients (SPEC §3: no messages beyond the
# two adults). A fully quiet day briefs both (D-036e/D-044: partner-symmetric —
# neither is left without the morning message).
DIGEST_RECIPIENTS = ("adar", "shanee")

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
WA_INBOX_RETENTION_DAYS = 30     # hot-tab rolloff horizon — 30d confirmed (D-036, 2026-06-15); SPEC §6.2 aligned. Rolloff implemented M4 (D-044, sheet.roll_off_old_rows).
DIGEST_GROUP_ORDER = ["daycare", "building", "family", "neighborhood", "student", "other"]
# Hebrew short labels, used inline per digest item (DESIGN §6: "גן — מחר יום פרי…").
# Real group names stay in the gitignored seed; these label the TYPE.
DIGEST_GROUP_LABEL = {
    "daycare": "גן", "building": "ועד", "family": "משפחה",
    "neighborhood": "שכונה", "student": "לימודים", "other": "אחר",
}

# ---------------------------------------------------------------------------
# Property tracker (SPEC.md §12.1, M5 — unfrozen D-034). Silent, digest-only:
# new listings land in the Sheet and surface in the 07:30 digest, never an
# alert, never a budget bypass (briefings > notifications).
# ---------------------------------------------------------------------------
PROPERTY_LISTINGS_TAB = "Property-Listings"   # scraper-written tab (SPEC §6 / §12.1)
# Saved-search URLs per portal — PERSONAL (area/price/rooms), mode 600, /etc only,
# NEVER in the repo (D-024). deploy/property_searches.example.json is the template.
PROPERTY_SEARCHES_FILE = Path("/etc/family-inc/property_searches.json")
# Last-seen listing_id set. VPS = /var/lib/family-inc/property (systemd
# StateDirectory, set via FAMILY_INC_PROPERTY_DIR in the unit); dev/tests fall
# back to the gitignored automation/cache so a local run never needs root.
PROPERTY_STATE_DIR = Path(os.environ.get("FAMILY_INC_PROPERTY_DIR")
                          or (CACHE_DIR / "property"))
PROPERTY_SEEN_FILE = PROPERTY_STATE_DIR / "seen.json"
PROPERTY_FETCH_TIMEOUT_S = 45     # per-URL headless-Chromium budget (the unit's
                                  # TimeoutStartSec/MemoryMax bound a stuck browser)
PROPERTY_MAX_PER_DIGEST = 8       # cap new-listing lines in one morning digest

# --- Apify secondary source (SPEC §12.1, D-040) ----------------------------
# SECONDARY/supplementary only: the on-box Chromium scraper above stays primary.
# Apify (its own residential proxy pool) is the backup that clears the anti-bot
# wall the VPS datacenter IP can't (D-039). Paid third party in the path → D-040
# amends D-010's "₪0 marginal" to the §11 monthly ceiling, which still governs.
APIFY_TOKEN_ENV = "FAMILY_INC_APIFY_TOKEN"   # SERVICE api key, NOT a portal login;
                                             # /etc/family-inc/env mode 600 (§8.6),
                                             # never the repo. Absent → path inert.
APIFY_BASE_URL = "https://api.apify.com/v2"
# Actor ids per portal (username~actorName) — non-secret, committed (D-040 picks).
# amit123 ingests Yad2 saved-search URLs directly; swerve is parametric (Madlan
# needs a city/dealType 'apify' block in property_searches.json — no URL input).
PROPERTY_APIFY_ACTORS = {
    "yad2": "amit123~yadscraper",
    "madlan": "swerve~madlan-scraper",
}
PROPERTY_APIFY_TIMEOUT_S = 180    # run-sync-get-dataset-items hard-caps at 300s;
                                  # the caps below keep real runs well under it
PROPERTY_APIFY_MAX_ITEMS = 100    # per-search cap for parametric actors (Madlan)
PROPERTY_APIFY_MAX_PAGES = 3      # per-search page cap for URL actors (Yad2) —
                                  # newest-first searches put new listings first
PROPERTY_APIFY_GAPFILL = True     # also fill missing fields on primary listings
                                  # from the same Apify call (D-040). False =
                                  # backup-only (blocked/empty) — the cheapest mode
PROPERTY_APIFY_ONCE_PER_DAY = True  # Apify lands at most once/calendar-day (cost:
                                  # priced per result; on-box primary stays free
                                  # 2×/day; digest is morning-only). False = every run
PROPERTY_APIFY_STAMP_FILE = PROPERTY_STATE_DIR / "apify_last_run.json"

# ---------------------------------------------------------------------------
# LLM (SPEC.md §8.6–8.7 — model ids live here, not at call sites)
#
# Provider direction (D-032, wired M4/D-044): DeepSeek is the single configured
# provider, reached over its OpenAI-compatible /chat/completions endpoint with
# stdlib urllib (no new dependency). lib/llm picks the provider by which key is
# present — DeepSeek first, Anthropic if only that key is set, neither → the
# deterministic fallback (the system stays useful keyless, SPEC §3.6/§5).
# Keys live in /etc/family-inc/env (mode 600), never the repo (SPEC §8.6).
# ---------------------------------------------------------------------------
DEEPSEEK_API_KEY_ENV = "FAMILY_INC_DEEPSEEK_API_KEY"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"   # OpenAI-compatible base URL
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"      # legacy / fallback provider
LLM_TIMEOUT_S = 30                               # per-call HTTP budget (seconds)
# Active-provider (DeepSeek) model ids, keyed by task.
MODELS = {
    "classify": "deepseek-chat",   # WhatsApp triage (DeepSeek-V3)
    "briefing": "deepseek-chat",   # weekly-briefing prose
}
# Fallback-provider (Anthropic, the v1 Haiku-class path, §8.7) model ids.
ANTHROPIC_MODELS = {
    "classify": "claude-haiku-4-5",
    "briefing": "claude-haiku-4-5",
}
LLM_FAKE_ENV = "FAMILY_INC_LLM_FAKE"  # tests inject a canned response here

# ---------------------------------------------------------------------------
# Hebcal
# ---------------------------------------------------------------------------
HEBCAL_GEONAME_ID = 294801   # nearest metro (Haifa) — same coastal zman as home
HEBCAL_TTL_SECONDS = 24 * 60 * 60

# ---------------------------------------------------------------------------
# Email fallback (SPEC §10.2 — delivery layer 2) + fail-loud flag (ENG §5)
# ---------------------------------------------------------------------------
EMAIL_FALLBACK_AFTER_HOURS = 24       # heartbeat staler than this → the daily
                                      # digest degrades to SMTP (lib/mailer.py)
SMTP_DEFAULT_HOST = "smtp.gmail.com"  # overridable via SMTP_HOST/SMTP_PORT env;
SMTP_DEFAULT_PORT = 587               # creds (SMTP_USER/SMTP_PASS) env-only
EMAIL_TO_ENV = "FAMILY_INC_EMAIL_TO"  # comma-separated fallback recipients;
                                      # unset → Settings.UserMap emails
FAIL_FLAG = LOGS_DIR / "fail.flag"    # appended by family-fail-flag@.service
                                      # (systemd OnFailure=); reported + cleared
                                      # by the next delivered daily digest
DELIVERY_LOG = LOGS_DIR / "delivery_log.csv"  # one line per digest --send run
                                      # (date, transport, recipients); weekly
                                      # briefing surfaces smtp-degraded days
                                      # (review 2026-06-12, D-028)

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
