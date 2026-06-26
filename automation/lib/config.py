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
# Finance tabs (SPEC §6.4 / §12.2, M6). Standardized to full names 2026-06-17
# (D-052) — the as-built seed used the short Finance-Accts/Finance-Txns/
# Finance-Bdgt, which §6.4 already named Finance-Budget; the M6 build resolved
# the drift §12.2 flagged. lib/sheet owns the column maps (FINANCE_*_COLUMNS).
FINANCE_ACCOUNTS_TAB = "Finance-Accounts"
FINANCE_TRANSACTIONS_TAB = "Finance-Transactions"
FINANCE_BUDGET_TAB = "Finance-Budget"

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
# Pending bridge-digests awaiting delivery confirmation (GAP-2). The bridge
# delivers asynchronously and confirms in SENT_FILE; the daily digest does NOT
# stamp on queue — it records a pending row per recipient here and stamps Last
# Sent/Status at the next run's reconcile_deliveries() once the bridge confirms.
DIGEST_PENDING_FILE = BRIDGE_STATE_DIR / "outbox" / "digest_pending.jsonl"
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

# --- Weekly classifier accuracy review (Phase F, D-048) --------------------
# The summarizer records each message's classification + outcome in WhatsApp_Inbox
# but not the rule that fired (§6.2 schema). The review surface re-derives the
# triggering rule per ALERT from the persisted row by reusing the summarizer's
# own hard_rule_alert (single source of truth) — so no Inbox schema change is
# needed. The weekly briefing carries a compact pulse; automation/accuracy_review.py
# is the full operator surface (the recurring cadence reuses family-weekly.timer).
ACCURACY_REVIEW_DAYS = 7          # trailing window the weekly surface reviews
ALERT_FP_TARGET_PER_WEEK = 1      # the bar (original WhatsApp design, Phase F):
                                  # <1 ALERT-tier false positive per week
ACCURACY_REVIEW_MAX_BRIEF = 12    # cap ALERT lines folded inline into the briefing

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
# Finance ingestion (SPEC.md §12.2, M6 — unfrozen D-049/050/051). The Node
# scraper (automation/finance/scrape.js) writes one CSV per provider to the
# staging dir; finance_ingest.py reads them and writes via lib/sheet (the only
# Sheet writer, D-016). Silent like property — balances + spend surface in the
# weekly briefing Money section + dashboard drawer, never an alert.
# ---------------------------------------------------------------------------
# Read-only bank/card portal logins (D-049 amendment). PERSONAL, mode 600, /etc
# only, NEVER the repo. deploy/bank_creds.example.json is the template. Absent →
# the scraper fails loud (nothing to ingest), exactly like a missing config.
FINANCE_CREDS_FILE = Path("/etc/family-inc/bank_creds.json")
# Per-provider CSV staging. VPS = /var/lib/family-inc/finance (systemd
# StateDirectory, set via FAMILY_INC_FINANCE_DIR in the unit); dev/tests fall
# back to the gitignored automation/cache so a local run never needs root
# (mirrors PROPERTY_STATE_DIR). The scraper persists session state here too.
FINANCE_STATE_DIR = Path(os.environ.get("FAMILY_INC_FINANCE_DIR")
                         or (CACHE_DIR / "finance"))
# Provider → account Type label written to Finance-Accounts (bank vs card).
FINANCE_PROVIDER_TYPES = {"mizrahi": "bank", "max": "card", "cal": "card"}
# The briefing's data-hygiene line warns when an account hasn't imported in this
# many days (§12.2 stale-import). One definition — section_hygiene reads it.
FINANCE_STALE_IMPORT_DAYS = 35
# On-box categorization rules (M6.4, D-050): keyword→category, applied to every
# transaction at ingest so most never reach the LLM (§8.6). NON-personal (public
# merchant tokens + generic category labels) → committed, unlike the personal
# seeds (a `!`-exception in .gitignore overrides `seeds/*.csv`). PROVISIONAL
# vocab until Shanee's budget migration fixes the category set; the distinct
# categories here are also the only labels the gap-fill LLM may return.
FINANCE_CATEGORY_RULES = SEEDS_DIR / "14_Finance_Category_Rules.csv"

# ---------------------------------------------------------------------------
# Love-notes (V3.7, SPEC §7.7 — the one dashboard datum that is neither the
# Sheet nor the outbox). A tiny authenticated dashboard→appliance endpoint
# (love_note_server.py) holds ONE ephemeral note per direction (Adar→Shanee,
# Shanee→Adar), dies at 24h-or-on-replacement, shows on the recipient's next
# dashboard open — no push, no alert-budget spend, never the Sheet, never the
# outbox, never a stored OAuth token. Voice is a frozen phase-2 (SPEC §4).
# ---------------------------------------------------------------------------
# One JSON file per direction ({slug(from)}__to__{slug(to)}.json). VPS =
# /var/lib/family-inc/lovenote (systemd StateDirectory, set via
# FAMILY_INC_LOVENOTE_DIR in the unit); dev/tests fall back to the gitignored
# automation/cache so a local run never needs root (mirrors PROPERTY/FINANCE).
LOVENOTE_STATE_DIR = Path(os.environ.get("FAMILY_INC_LOVENOTE_DIR")
                          or (CACHE_DIR / "lovenote"))
LOVENOTE_TTL_HOURS = 24            # a note expires this long after it is sent
LOVENOTE_MAX_CHARS = 500          # cap one note (a love-note, not a letter)
# The server binds localhost; a Cloudflare Tunnel fronts it (ENGINEERING §5).
LOVENOTE_PORT = int(os.environ.get("FAMILY_INC_LOVENOTE_PORT") or 8787)
# CORS allow-origin — the GitHub-Pages origin the PWA is served from. PERSONAL-
# ish (public github user) → kept out of this committed file: set in
# /etc/family-inc/env. BLANK → CORS denies every browser origin, so the feature
# self-disables fail-safe (never promise an affordance that doesn't exist, §3).
LOVENOTE_ALLOWED_ORIGIN = os.environ.get("FAMILY_INC_LOVENOTE_ORIGIN", "").strip()
LOVENOTE_SETTINGS_TTL_S = 300     # re-read Settings.UserMap at most this often
LOVENOTE_HTTP_TIMEOUT_S = 10      # per Google token-verification call
LOVENOTE_MAX_BODY_BYTES = 8192    # reject a request body larger than this (pre-auth, 413)
LOVENOTE_VERIFY_CACHE_TTL_S = 120 # cache a verified token-hash→email this long (cuts Google calls under a burst; in-memory only, keyed by SHA-256 of the token so no raw token is held)
# Token verification uses Google's tokeninfo endpoint — unlike userinfo it returns
# the token's `aud` (the OAuth client it was minted for), so the server can reject
# a token issued to a DIFFERENT app (the confused-deputy / token-substitution gap).
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
# The OAuth client id the dashboard signs in with (= the GitHub `DASHBOARD_CLIENT_ID`
# secret). Set it in /etc/family-inc/env to ENFORCE the audience check; BLANK = email
# verification only (no aud check) — non-personal default, so it stays out of the repo.
LOVENOTE_ALLOWED_AUD = os.environ.get("FAMILY_INC_LOVENOTE_AUD", "").strip()

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
    "classify": "deepseek-chat",    # WhatsApp triage (DeepSeek-V3)
    "briefing": "deepseek-chat",    # weekly-briefing prose
    "categorize": "deepseek-chat",  # finance gap-fill — rules-miss remainder (§8.6)
}
# Fallback-provider (Anthropic, the v1 Haiku-class path, §8.7) model ids.
ANTHROPIC_MODELS = {
    "classify": "claude-haiku-4-5",
    "briefing": "claude-haiku-4-5",
    "categorize": "claude-haiku-4-5",
}
LLM_FAKE_ENV = "FAMILY_INC_LLM_FAKE"  # tests inject a canned response here

# Indicative LLM list prices (USD per 1M tokens, (input, output)) for the weekly
# self-report spend line (ENGINEERING §8) — a health figure, NOT accounting.
# Unknown models fall back to the default. Update when a provider reprices.
LLM_PRICE_USD_PER_MTOK = {
    "deepseek-chat": (0.27, 1.10),      # DeepSeek-V3 standard tier
    "claude-haiku-4-5": (1.00, 5.00),   # Anthropic fallback (§8.7)
}
LLM_PRICE_DEFAULT_USD_PER_MTOK = (1.00, 5.00)
USD_TO_ILS = 3.7                         # coarse FX — the spend line is indicative

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
# GAP-2 cross-run reconcile: a queued bridge-digest that the bridge never
# confirms delivering within this horizon is dropped (its reminders stay
# unstamped → they re-fire — fail loud, degrade quiet) and logged. 48h covers a
# weekend bridge outage; beyond that the §10.2 email fallback would have taken
# over on subsequent runs (PO call 2026-06-19).
DIGEST_PENDING_STALE_HOURS = 48
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
