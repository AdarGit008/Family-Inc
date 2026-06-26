"""
Family inc. — finance categorization coverage report (SPEC §12.2, M6.4).

The read-only standing surface for the M6 milestone metric: how much of the live
Finance-Transactions tab carries a Category, by-source and by-account, with the
still-blank merchants named for the operator. Pairs with the one-time
re-categorize backfill (automation/finance_recategorize.py), which PRINTS this
before/after; this script is the on-demand / pre-review read.

Read-only — never writes the Sheet. Output is operator-only: stdout, or
--write drops it into the gitignored Briefings/ (like accuracy_review.py),
because the blank-merchant list is live description text. Degrades quiet: no
live backend and no --sheet → nothing to read, a calm note.

  python3 automation/finance_coverage.py [--as-of YYYY-MM-DD] [--write]
                                         [--sheet path.xlsx]
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/finance_coverage.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from automation.lib import config as cfg
from automation.lib import finance_coverage as fc
from automation.lib import sheet

log = logging.getLogger("finance.coverage")


def run(today: date, write: bool = False,
        sheet_path: Optional[Path] = None) -> fc.Coverage:
    live = True if sheet_path is not None else sheet.is_live()
    if sheet_path is None and not live:
        print("(no live Sheet backend — nothing to measure, won't read the seed)")
        return fc.coverage([])
    grid = sheet.read_grid(cfg.FINANCE_TRANSACTIONS_TAB, sheet_path)
    cov = fc.coverage(fc.rows_from_grid(grid))
    body = fc.render(cov, today)
    if cov.total:
        print(f"finance coverage · {today}: {cov.coverage_pct * 100:.0f}% of "
              f"{cov.eligible} budget-eligible rows categorized "
              f"({cov.categorized} cat · {cov.excluded} excluded · {cov.blank} blank)")
    if write and cov.total:
        cfg.BRIEFINGS_DIR.mkdir(exist_ok=True)
        out = cfg.BRIEFINGS_DIR / f"{today.isoformat()}_finance_coverage.md"
        out.write_text(body, encoding="utf-8")
        print(f"wrote {out}")
    else:
        print("\n" + body)
    return cov


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    ap.add_argument("--write", action="store_true",
                    help="write the report to Briefings/ (gitignored) instead of stdout")
    ap.add_argument("--sheet", help="explicit xlsx path (tooling/tests)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, write=args.write,
        sheet_path=Path(args.sheet) if args.sheet else None)


if __name__ == "__main__":
    main()
