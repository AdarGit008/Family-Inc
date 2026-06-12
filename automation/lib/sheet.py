"""
Family inc. — master-DB read layer. The ONLY module that opens the workbook.

M1 shape: openpyxl against the local seed xlsx (scripts run dry/mock until M3).
M2 swaps the loader internals for gspread + service account (D-016) — the
public surface (`Reminder`, `read_reminders`, `load_workbook_data`) stays put,
which is the point of routing every read through here.

Row-parsing posture (SPEC.md §6 + §9): tolerate missing columns, return None
for bad dates, skip blank/templated rows. Bad data is skipped + reported in
data-hygiene lines — it never raises.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

from automation.lib.dates import to_date, to_datetime

# SPEC.md §6.1 column map (1-based). The schema-drift validation that aborts
# a run on header mismatch arrives with the M2 gspread port — the column
# contract is recorded here so both land in the same module.
REMINDERS_COLUMNS = {
    1: "Title", 2: "Domain", 3: "Owner", 4: "Due Date", 5: "Lead Times",
    6: "Recurrence", 7: "Status", 8: "Last Sent", 9: "Channel", 10: "Notes",
    11: "Days Until", 12: "Auto-flag", 13: "LastDoneBy", 14: "DoneAt",
    15: "WriteQueue_Tombstone", 16: "Guide URL",
}


@dataclass
class Reminder:
    row: int
    title: str
    domain: str
    owner: str
    due: date | None
    lead_times: list[int]
    recurrence: str
    status: str
    last_sent: date | None
    channel: str
    notes: str
    # Dashboard write-back columns M/N/O — blank on legacy sheets, that's fine.
    last_done_by: str = ""
    done_at: datetime | None = None
    write_queue_tombstone: datetime | None = None


def parse_lead_times(raw) -> list[int]:
    """Column E: CSV of day offsets ('60,30,7,1'). Junk filtered, sorted
    descending; default [7, 1] when empty/unparseable."""
    if raw is None:
        return [7, 1]
    if isinstance(raw, (int, float)):
        return [int(raw)]
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    out = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            pass
    return sorted(out, reverse=True) or [7, 1]


def load_workbook_data(path: Path):
    """data_only workbook handle. Keep all openpyxl imports behind this module."""
    return load_workbook(path, data_only=True)


def read_reminders(path: Path) -> list[Reminder]:
    """Reminders tab → dataclasses. Blank titles and templated `[...]` rows
    are skipped; unparseable dates become None (caller classifies them out)."""
    wb = load_workbook_data(path)
    ws = wb["Reminders"]
    out = []
    for row_idx in range(2, ws.max_row + 1):
        title = ws.cell(row_idx, 1).value
        if not title or str(title).startswith("["):  # skip blanks / templated rows
            continue
        out.append(Reminder(
            row=row_idx,
            title=str(title),
            domain=str(ws.cell(row_idx, 2).value or "Other"),
            owner=str(ws.cell(row_idx, 3).value or "Adar"),
            due=to_date(ws.cell(row_idx, 4).value),
            lead_times=parse_lead_times(ws.cell(row_idx, 5).value),
            recurrence=str(ws.cell(row_idx, 6).value or "One-off"),
            status=str(ws.cell(row_idx, 7).value or "Pending"),
            last_sent=to_date(ws.cell(row_idx, 8).value),
            channel=str(ws.cell(row_idx, 9).value or "WhatsApp"),
            notes=str(ws.cell(row_idx, 10).value or "").strip(),
            last_done_by=str(ws.cell(row_idx, 13).value or "").strip(),
            done_at=to_datetime(ws.cell(row_idx, 14).value),
            write_queue_tombstone=to_datetime(ws.cell(row_idx, 15).value),
        ))
    return out
