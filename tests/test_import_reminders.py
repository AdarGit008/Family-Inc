"""automation/import_reminders.py — M3 seeding tool: pure-logic coverage.

No backend, no network: load_csv + plan_cells only. The write path is
lib/sheet.batch_update, already covered by test_sheet.py.
"""

import pytest

from automation.import_reminders import CLEAR_COLS, WRITE_COLS, load_csv, plan_cells
from tests.conftest import REMINDERS_HEADER


def _csv(tmp_path, header, rows):
    import csv
    p = tmp_path / "import.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return p


ROW = ["Car test", "Car", "Adar", "01/09/2026", "30,7,1", "Yearly", "Pending",
       "", "WhatsApp", "note", "", "", "", "", "", "https://example.org"]


class TestLoadCsv:
    def test_valid_header_and_blank_rows_dropped(self, tmp_path):
        p = _csv(tmp_path, REMINDERS_HEADER, [ROW, ["" for _ in range(16)]])
        rows = load_csv(p)
        assert len(rows) == 1 and rows[0][0] == "Car test"

    def test_wrong_header_aborts(self, tmp_path):
        bad = list(REMINDERS_HEADER)
        bad[3] = "Deadline"  # col D must be "Due Date"
        p = _csv(tmp_path, bad, [ROW])
        with pytest.raises(SystemExit, match="§6.1"):
            load_csv(p)


class TestPlanCells:
    def test_rows_land_at_a2_and_kl_never_written(self):
        cells = plan_cells([list(ROW), list(ROW)], clear_through=5)
        assert (2, 1, "Car test") in cells          # A2 = first title
        assert (3, 4, "01/09/2026") in cells        # D3 = second row due
        assert all(col not in (11, 12) for _, col, _ in cells)  # K/L sacred

    def test_leftovers_cleared_after_data(self):
        cells = plan_cells([list(ROW)], clear_through=4)
        # data row = 2; rows 3..4 cleared in A..J + M..P
        cleared = {(r, c) for r, c, v in cells if v == "" and r >= 3}
        for r in (3, 4):
            for c in CLEAR_COLS:
                assert (r, c) in cleared

    def test_no_clear_rows_when_data_fills_range(self):
        rows = [list(ROW)] * 3
        cells = plan_cells(rows, clear_through=4)  # data occupies 2..4
        assert not [c for c in cells if c[2] == "" and c[1] == 1 and c[0] > 4]
        assert len([c for c in cells if c[0] == 4 and c[2] != ""]) > 0
