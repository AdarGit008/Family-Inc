"""Shared fixtures for Family Inc engine tests."""

from datetime import date, datetime
from pathlib import Path

import pytest

# Make project root importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


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
    from reminders_engine import Reminder
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
