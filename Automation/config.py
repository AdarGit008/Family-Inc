"""
Family inc. — Shared configuration constants.

Constants that are referenced in multiple automation scripts live here
so changing them requires a single edit. The spec (02_Reminders_Engine_Spec.md)
should be the source-of-truth for their values; the code reflects it.

Usage:
    from config import ALERT_BUDGET_PER_DAY, OVERDUE_REPEAT_DAYS, ...
"""
from __future__ import annotations

# Alert budget — shared family-wide cap. Engine (reminders) and summarizer
# (WhatsApp) both enforce this independently per their own routing logic.
ALERT_BUDGET_PER_DAY = 2  # messages per recipient per day (hard cap)

# Tombstone race-guard window. Engine skips any row whose WriteQueue_Tombstone
# is within this many hours of the run time.
TOMBSTONE_SKIP_HOURS = 6

# Overdue reminders re-fire at most every N days.
OVERDUE_REPEAT_DAYS = 3

# Quiet hours: no outbound messages in this window (22:00 – 07:00).
QUIET_HOURS_START = 22  # 22:00 local time
QUIET_HOURS_END = 7     # 07:00 local time

# Batch window: fires for the same recipient arriving within this many minutes
# are merged into a single digest message.
BATCH_WINDOW_MINUTES = 5
