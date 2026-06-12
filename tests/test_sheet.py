"""Tests for automation/lib/sheet.py + lib/dates.py — row-parsing tolerance
(ENGINEERING §7: missing columns, bad dates → skipped/None + reported, never
raised)."""

from datetime import date, datetime

from openpyxl import Workbook

from automation.lib.dates import to_date, to_datetime
from automation.lib.sheet import parse_lead_times, read_reminders


# ---------------------------------------------------------------------------
# parse_lead_times
# ---------------------------------------------------------------------------
class TestParseLeadTimes:
    def test_none_defaults(self):
        assert parse_lead_times(None) == [7, 1]

    def test_single_int(self):
        assert parse_lead_times(14) == [14]

    def test_comma_string(self):
        assert parse_lead_times("14, 7, 1") == [14, 7, 1]

    def test_sorts_descending(self):
        assert parse_lead_times("1, 14, 7") == [14, 7, 1]

    def test_filters_junk(self):
        assert parse_lead_times("7, junk, 14") == [14, 7]

    def test_empty_defaults(self):
        assert parse_lead_times("") == [7, 1]


# ---------------------------------------------------------------------------
# to_date
# ---------------------------------------------------------------------------
class TestToDate:
    def test_python_date_passthrough(self):
        d = date(2026, 6, 1)
        assert to_date(d) == d

    def test_datetime_converted(self):
        assert to_date(datetime(2026, 6, 1, 12, 30)) == date(2026, 6, 1)

    def test_iso_string(self):
        assert to_date("2026-06-15") == date(2026, 6, 15)

    def test_sheet_contract_ddmmyyyy(self):
        """SPEC §6.1 col D is DD/MM/YYYY — the gspread port (M2) reads strings."""
        assert to_date("15/06/2026") == date(2026, 6, 15)

    def test_invalid_string_returns_none(self):
        assert to_date("not-a-date") is None

    def test_none_returns_none(self):
        assert to_date(None) is None


# ---------------------------------------------------------------------------
# to_datetime (dashboard write-back shapes)
# ---------------------------------------------------------------------------
class TestToDatetime:
    def test_iso_with_t(self):
        assert to_datetime("2026-06-10T09:30:00") == datetime(2026, 6, 10, 9, 30)

    def test_space_separator(self):
        assert to_datetime("2026-06-10 09:30:00") == datetime(2026, 6, 10, 9, 30)

    def test_date_only_string(self):
        assert to_datetime("2026-06-10") == datetime(2026, 6, 10)

    def test_garbage_returns_none(self):
        assert to_datetime("soonish") is None

    def test_empty_returns_none(self):
        assert to_datetime("  ") is None
        assert to_datetime(None) is None


# ---------------------------------------------------------------------------
# read_reminders — tolerance against real-world sheet mess
# ---------------------------------------------------------------------------
def _write_sheet(tmp_path, rows):
    """rows = list of value-lists laid into Reminders!A2:P…"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Reminders"
    ws.append(["Title", "Domain", "Owner", "Due Date", "Lead Times", "Recurrence",
               "Status", "Last Sent", "Channel", "Notes", "Days Until", "Auto-flag",
               "LastDoneBy", "DoneAt", "WriteQueue_Tombstone", "Guide URL"])
    for row in rows:
        ws.append(row)
    p = tmp_path / "sheet.xlsx"
    wb.save(p)
    return p


class TestReadReminders:
    def test_basic_row(self, tmp_path):
        p = _write_sheet(tmp_path, [
            ["Car test", "Car", "Both", date(2026, 7, 1), "14,7", "Yearly", "Pending"],
        ])
        out = read_reminders(p)
        assert len(out) == 1
        r = out[0]
        assert r.title == "Car test"
        assert r.due == date(2026, 7, 1)
        assert r.lead_times == [14, 7]
        assert r.owner == "Both"

    def test_blank_and_templated_rows_skipped(self, tmp_path):
        p = _write_sheet(tmp_path, [
            [None, "Car", "Adar", date(2026, 7, 1)],
            ["[Template] copy me", "Car", "Adar", date(2026, 7, 1)],
            ["Real", "Car", "Adar", date(2026, 7, 1)],
        ])
        out = read_reminders(p)
        assert [r.title for r in out] == ["Real"]

    def test_bad_date_becomes_none_not_raise(self, tmp_path):
        p = _write_sheet(tmp_path, [
            ["Fuzzy due", "Other", "Adar", "sometime in July"],
        ])
        out = read_reminders(p)
        assert len(out) == 1
        assert out[0].due is None  # engine classifies it out; hygiene reports it

    def test_missing_mno_columns_ok(self, tmp_path):
        """Legacy rows without LastDoneBy/DoneAt/Tombstone parse fine
        (SPEC §9: additive-only schema — old rows keep parsing)."""
        p = _write_sheet(tmp_path, [
            ["Old row", "Health", "Shanee", date(2026, 8, 1), "7"],
        ])
        r = read_reminders(p)[0]
        assert r.last_done_by == ""
        assert r.done_at is None
        assert r.write_queue_tombstone is None

    def test_defaults_for_empty_cells(self, tmp_path):
        p = _write_sheet(tmp_path, [
            ["Bare", None, None, date(2026, 8, 1)],
        ])
        r = read_reminders(p)[0]
        assert r.domain == "Other"
        assert r.owner == "Adar"
        assert r.status == "Pending"
        assert r.channel == "WhatsApp"
        assert r.lead_times == [7, 1]
