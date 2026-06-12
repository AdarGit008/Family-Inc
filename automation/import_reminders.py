"""
Family inc. — one-shot Reminders bulk import (M3 seeding, BACKLOG M3).

Reads a SPEC §6.1-shaped CSV (cols A..P; K..O expected blank — K/L are sheet
formulas, M..O are dashboard-owned) and writes the rows into the live
Reminders tab starting at A2, through lib/sheet's backend — the only gspread
client (ENGINEERING §1). Columns K/L are never touched, so the Days-Until /
Auto-flag formulas survive. Rows below the imported block are cleared down to
--clear-through (sample remnants from the seed template), again skipping K/L.

Live-backend ONLY by design: a creds-less run aborts rather than mutate the
committed seed template (house rule; see lib/sheet.is_live()).

Usage (on the appliance):
    uv run --no-sync python automation/import_reminders.py --csv /tmp/Reminders_Import_M3.csv
    uv run --no-sync python automation/import_reminders.py --csv /tmp/Reminders_Import_M3.csv --yes

Default is a dry-run that prints the plan; --yes writes. Writes go USER_ENTERED,
so DD/MM/YYYY parses into real date cells — IF the spreadsheet locale is Israel
(File → Settings). After writing, eyeball column K: numbers = good; #VALUE! or
ERROR = the locale is wrong; fix it and re-run (the import is an idempotent
overwrite of the same range).
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/import_reminders.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import csv
from pathlib import Path

from automation.lib import config, sheet

# §6.1, 1-based columns. A..J + P are import-owned; K(11)/L(12) = formulas,
# never written; M(13)..O(15) are dashboard-owned — cleared on leftover sample
# rows only, never written on imported rows.
WRITE_COLS = list(range(1, 11)) + [16]
CLEAR_COLS = list(range(1, 11)) + [13, 14, 15, 16]


def load_csv(path: Path) -> list[list[str]]:
    """CSV rows (header validated against §6.1, blank lines dropped)."""
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise SystemExit(f"empty CSV: {path}")
    problems = sheet.validate_reminders_header(rows[0])
    if problems:
        raise SystemExit("CSV header does not match SPEC §6.1 — aborting:\n  "
                         + "\n  ".join(problems))
    return [r for r in rows[1:] if any(c.strip() for c in r)]


def plan_cells(rows: list[list[str]], clear_through: int) -> list[tuple[int, int, str]]:
    """(row, col, value) tuples for backend.batch_update: data at A2 down,
    then clears for leftover sample rows. K/L appear nowhere in the plan."""
    cells: list[tuple[int, int, str]] = []
    for i, row in enumerate(rows):
        sheet_row = 2 + i
        for col in WRITE_COLS:
            cells.append((sheet_row, col, row[col - 1] if col <= len(row) else ""))
    for sheet_row in range(2 + len(rows), clear_through + 1):
        for col in CLEAR_COLS:
            cells.append((sheet_row, col, ""))
    return cells


def fix_view(n_rows: int, clear_through: int) -> None:
    """One-off live-Sheet view repair (go-live 2026-06-12): the seed template
    carried column-D date formatting and the K/L formulas only down to its own
    sample rows. (a) format D as DATE dd/mm/yyyy (§6.1) through clear_through,
    (b) copyPaste K2:L2 → K3:L{data end} (PASTE_FORMULA — relative refs adjust
    like a manual ⌘C/⌘V fill-down).

    Reaches into GSheetBackend internals (ws/sh) deliberately: this is a
    maintenance tool, live-backend-only, and constructing no client of its own
    (the ENGINEERING §1 rule is about client construction, which stays in
    lib/sheet)."""
    be = sheet.backend()
    ws = be._ws(config.REMINDERS_TAB)
    ws.format(f"D2:D{clear_through}",
              {"numberFormat": {"type": "DATE", "pattern": "dd/mm/yyyy"}})
    last_data_row = 1 + n_rows
    be.sh.batch_update({"requests": [{
        "copyPaste": {
            "source": {"sheetId": ws.id, "startRowIndex": 1, "endRowIndex": 2,
                       "startColumnIndex": 10, "endColumnIndex": 12},
            "destination": {"sheetId": ws.id, "startRowIndex": 2,
                            "endRowIndex": last_data_row,
                            "startColumnIndex": 10, "endColumnIndex": 12},
            "pasteType": "PASTE_FORMULA",
        }}]})
    print(f"view fixed: D2:D{clear_through} formatted dd/mm/yyyy; "
          f"K/L formulas filled to row {last_data_row}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(config.SEEDS_DIR / "Reminders_Import_M3.csv"))
    ap.add_argument("--clear-through", type=int, default=60,
                    help="clear sample remnants down to this sheet row (default 60)")
    ap.add_argument("--fix-formats", action="store_true",
                    help="before writing: format col D as dd/mm/yyyy dates and "
                         "fill the K/L formulas down over the data rows")
    ap.add_argument("--yes", action="store_true", help="write (default: dry-run plan)")
    args = ap.parse_args()

    if not sheet.is_live():
        raise SystemExit("no FAMILY_INC_SHEET_ID in the environment — refusing to "
                         "write the seed template (this tool targets the live Sheet only)")

    rows = load_csv(Path(args.csv))

    # §7.1: never bulk-write a drifted sheet — validate the LIVE header too.
    grid = sheet.backend().grid(config.REMINDERS_TAB)
    problems = sheet.validate_reminders_header(grid[0] if grid else [])
    if problems:
        raise SystemExit("live Reminders header drifted — aborting:\n  "
                         + "\n  ".join(problems))

    cells = plan_cells(rows, args.clear_through)
    print(f"{len(rows)} rows → Reminders!A2 (cols A–J + P), leftovers cleared "
          f"through row {args.clear_through} — {len(cells)} cells, K/L untouched")
    for r in rows[:3]:
        print(f"  e.g. {r[0]} · {r[1]} · {r[2]} · due {r[3]}")
    if not args.yes:
        print("dry-run — rerun with --yes to write"
              + (" (+--fix-formats requested)" if args.fix_formats else ""))
        return
    if args.fix_formats:
        fix_view(len(rows), args.clear_through)  # format BEFORE writing → dates parse
    sheet.backend().batch_update(config.REMINDERS_TAB, cells)
    print(f"written: {len(rows)} reminders. Now eyeball column K in the tab — "
          "numbers mean the dates parsed; errors mean fix File→Settings→Locale "
          "to Israel and re-run.")


if __name__ == "__main__":
    main()
