"""Shared fixtures for Family Inc tests.

LLM calls are never made here (ENGINEERING.md §7): nothing sets
ANTHROPIC_API_KEY, and the fake hook is FAMILY_INC_LLM_FAKE.
"""

from datetime import date, datetime
from pathlib import Path

import pytest

# Make the repo root importable (`import automation...`)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automation.lib import config  # noqa: E402


@pytest.fixture(autouse=True)
def _hermetic_no_live_sheet(monkeypatch):
    """Tests must NEVER reach live I/O selected from /etc/family-inc/env. That
    file is loaded by `config.load_env()` (setdefault → "existing env wins"),
    reached via BOTH `sheet.is_live()` and `mailer.send_digest()`, so on the
    appliance `deploy.sh`'s pytest otherwise picks up the box's live creds:
      • FAMILY_INC_SHEET_ID → the live Google Sheet backend. D-038: a no-backend
        test once appended the 3 mock listings to the live Property-Listings tab.
      • SMTP_USER/SMTP_PASS (+FAMILY_INC_EMAIL_TO) → the digest's §10.2
        email-fallback path really SENDS, so the send-stamping tests take the
        SMTP branch instead of the WhatsApp outbox. D-041: 2 TestSendStamping
        failures surfaced at the M5 deploy — green on every dev box, red only on
        the appliance, where the env file exists.
    Setting each EMPTY (not delenv / `-u`) makes load_env's setdefault keep it
    empty so the file can't repopulate it. Tests that need a backend pass an
    explicit xlsx path / live_override=; the email-path tests (test_mailer) set
    SMTP creds themselves and run after this autouse, so they still win."""
    monkeypatch.setenv(config.SHEET_ID_ENV, "")
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASS", "")
    monkeypatch.setenv(config.EMAIL_TO_ENV, "")
    from automation.lib import sheet
    sheet.reset_backend()


@pytest.fixture
def today() -> date:
    """Fixed test date: a Wednesday so we can test week and month boundaries."""
    return date(2026, 6, 10)


@pytest.fixture
def now() -> datetime:
    """Wall-clock moment matching `today`, mid-morning."""
    return datetime(2026, 6, 10, 9, 30)


@pytest.fixture
def sample_reminder_kwargs():
    """Returns a minimal valid kwargs dict for a Reminder. Tests override fields."""
    return {
        "row": 2,
        "title": "Test item",
        "domain": "Kids",
        "owner": "Adar",
        "due": date(2026, 6, 15),
        "lead_times": [7, 1],
        "recurrence": "One-off",
        "status": "Pending",
        "last_sent": None,
        "channel": "WhatsApp",
        "notes": "",
    }


# SPEC §6.1 header — the one the schema guard enforces.
REMINDERS_HEADER = [
    "Title", "Domain", "Owner", "Due Date", "Lead Times", "Recurrence",
    "Status", "Last Sent", "Channel", "Notes", "Days Until", "Auto-flag",
    "LastDoneBy", "DoneAt", "WriteQueue_Tombstone", "Guide URL",
]


@pytest.fixture
def make_sheet(tmp_path):
    """Factory: rows (lists laid into Reminders!A2:P…) → tmp xlsx path with a
    conformant §6.1 header. The write-path tests mutate these copies — never
    the committed seed."""
    from openpyxl import Workbook

    def _make(rows, name="sheet.xlsx"):
        wb = Workbook()
        ws = wb.active
        ws.title = "Reminders"
        ws.append(REMINDERS_HEADER)
        for row in rows:
            ws.append(row)
        p = tmp_path / name
        wb.save(p)
        return p

    return _make


@pytest.fixture
def tmp_runtime(tmp_path, monkeypatch):
    """Redirect every runtime path in lib/config to a tmp sandbox, so tests
    touch no real state (outbox, ledgers, logs, briefings, staging CSVs)."""
    monkeypatch.setattr(config, "BRIEFINGS_DIR", tmp_path / "Briefings")
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "REMINDERS_LOG", tmp_path / "logs" / "reminders_log.csv")
    monkeypatch.setattr(config, "LLM_COSTS_LOG", tmp_path / "logs" / "llm_costs.csv")
    monkeypatch.setattr(config, "OUTBOX_LEDGER_DIR", tmp_path / "logs" / "outbox_ledger")
    monkeypatch.setattr(config, "BRIDGE_STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(config, "OUTBOX_FILE", tmp_path / "state" / "outbox" / "whatsapp_outbox.jsonl")
    monkeypatch.setattr(config, "SENT_FILE", tmp_path / "state" / "outbox" / "whatsapp_sent.jsonl")
    monkeypatch.setattr(config, "DEFERRED_FILE", tmp_path / "state" / "outbox" / "deferred.jsonl")
    monkeypatch.setattr(config, "INBOX_FILE", tmp_path / "state" / "inbox" / "whatsapp_inbox.jsonl")
    monkeypatch.setattr(config, "HEARTBEAT_FILE", tmp_path / "state" / "inbox" / "heartbeat.txt")
    monkeypatch.setattr(config, "SCHEMA_DRIFT_FLAG", tmp_path / "logs" / "schema_drift.flag")
    monkeypatch.setattr(config, "ENGINE_FLAGS", tmp_path / "logs" / "engine_flags.jsonl")
    monkeypatch.setattr(config, "FAIL_FLAG", tmp_path / "logs" / "fail.flag")
    monkeypatch.setattr(config, "DELIVERY_LOG", tmp_path / "logs" / "delivery_log.csv")
    # Property tracker (M5) — keep the scraper's state + (absent) searches file
    # inside the sandbox so a test run never reads /etc or writes /var/lib.
    monkeypatch.setattr(config, "PROPERTY_STATE_DIR", tmp_path / "state" / "property")
    monkeypatch.setattr(config, "PROPERTY_SEEN_FILE", tmp_path / "state" / "property" / "seen.json")
    monkeypatch.setattr(config, "PROPERTY_SEARCHES_FILE", tmp_path / "etc" / "property_searches.json")
    return tmp_path
