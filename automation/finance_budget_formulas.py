"""
Family inc. — install the Finance-Budget actuals formulas (SPEC §12.2, M6.3 — the
M6.4 reconciliation step gated to live data).

The budget actuals reconcile via a text-prefix-wildcard SUMIFS over the ISO-text
Date column (the M6.4 landmine: a serial DATE() window read ₪0). `lib/finance_budget`
is the single source of that formula text; this stamps it onto the live
`Finance-Budget` tab — idempotently, keyed off whatever category rows the tab
actually has, so a re-run after Shanee's budget migration just re-stamps for the
new rows. It writes only the machine-owned columns (Actual / Variance / % / YTD /
Last-Month + the I-helper date tags + TOTAL sums); a category row's Category and
Monthly Target, and every Notes cell, are human-owned and never touched (the only
Target it writes is the TOTAL row's =SUM) — so there is no manual copy to drag a
stray formula along.

Live backend or an explicit --path only — refuses to mutate the committed seed,
like every other writer (a creds-less dev run reads the seed but writes nothing).
Run on the box after the tab exists / after a budget-structure change:

  python3 automation/finance_budget_formulas.py --dry-run   # preview the cells
  python3 automation/finance_budget_formulas.py             # stamp them

Then verify the actuals go non-zero against live data — Groceries / Transport /
Health this month. The ₪0 buckets (Subscriptions / Savings / Other) await Shanee's
vocab migration; that is expected, not a bug (§12.2 / deploy/FINANCE.md §6).
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/finance_budget_formulas.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import logging
from pathlib import Path
from typing import Optional

from automation.lib import config as cfg
from automation.lib import finance_budget as fb
from automation.lib import sheet

log = logging.getLogger("finance-budget")


def run(path: Optional[Path] = None, dry_run: bool = False) -> list[tuple[int, int, str]]:
    """Read the budget grid, build the formula cells, and (unless --dry-run / no
    backend) stamp them. Returns the cells it built, for tests + the dry-run print."""
    live = sheet.is_live()
    grid = sheet.read_grid(cfg.FINANCE_BUDGET_TAB, path)
    if not grid:
        raise fb.BudgetHeaderError(
            f"{cfg.FINANCE_BUDGET_TAB} tab not found or empty "
            f"(live={live}; pass --path for an explicit xlsx)")
    cells = fb.budget_formula_cells(grid)
    print(f"{cfg.FINANCE_BUDGET_TAB}: {len(fb.category_rows(grid))} category row(s) "
          f"→ {len(cells)} formula cell(s)")

    if dry_run:
        for r, c, v in cells:
            print(f"  {fb.col_letter(c)}{r}: {v}")
        print("(dry-run — nothing written)")
        return cells
    if path is None and not live:
        print(f"(no live Sheet backend — formulas NOT written; set {cfg.SHEET_ID_ENV} "
              "on the box, or pass --path)")
        return cells

    sheet.write_cells(cfg.FINANCE_BUDGET_TAB, cells, path)
    print(f"stamped {len(cells)} formula cell(s) onto {cfg.FINANCE_BUDGET_TAB} — "
          "verify actuals go non-zero against live data")
    return cells


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(
        description="Install the Finance-Budget actuals SUMIFS on the live Sheet (M6.3)")
    ap.add_argument("--path", help="explicit xlsx (tests / tooling); default: the live Sheet")
    ap.add_argument("--dry-run", action="store_true", help="print the cells, write nothing")
    args = ap.parse_args()
    run(path=Path(args.path) if args.path else None, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
