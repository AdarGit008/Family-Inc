"""
Family inc. — one-time finance re-categorize backfill (SPEC §12.2, M6.4/M6.5).

`finance_ingest` categorizes only the NEW (post-dedup) rows of each run, so the
historical backlog never re-enters the engine — by design (idempotency). When a
RULE changes (the M6.5 `Card Settlement` exclusion was added 2026-06-23, after
the first Mizrahi imports), the already-landed rows that the new rule would now
match stay BLANK. This is the deliberate seam to apply a rules change to history:
re-run the categorizer over the currently-BLANK rows and write the results back.

It is exactly the categorizer ingest runs (`lib/categorize`, rules + DeepSeek
gap-fill, description + amount only — §8.6), pointed at the live tab instead of a
fresh CSV. Two effects, one pass:
  • the ~66 Cal-mirror lines (`כא"ל`/`ויזה כאל`/`רכישה בכרטיס דביט`) match the
    Card Settlement rule → move blank → excluded (out of the actuals SUMIFS);
  • any genuine merchant the rules now cover, or the LLM can place, gets a
    category. A genuinely merchant-less wrapper (ATM/cheque) stays blank.

SAFETY:
  • Scope is BLANK rows only — a row that already carries a Category (rules, llm,
    or a human's manual edit) is never touched, so the backfill can't clobber a
    correction. Re-running is therefore idempotent: a second run finds nothing.
  • Writes are SURGICAL — `sheet.write_cells` to the exact (row, Category-col) and
    (row, Cat-Source-col) of each changed row, discovered by reading the tab. No
    append path exists, so a stray Txn-ID can never spawn a partial row (the one
    risk an upsert-by-key would carry).
  • Header-guarded (mirrors §7.1): a Finance-Transactions tab missing Category /
    Cat-Source / Description fails loud rather than writing by guessed position.
  • Live backend or explicit --sheet only — refuses to touch the committed seed,
    exactly like the ingest write path.

  python3 automation/finance_recategorize.py --dry-run     # preview (rules-only), no write
  python3 automation/finance_recategorize.py               # rules + DeepSeek, writes live
  python3 automation/finance_recategorize.py --no-llm      # rules-only, writes live
  python3 automation/finance_recategorize.py --sheet x.xlsx --dry-run
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/finance_recategorize.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from automation.lib import categorize
from automation.lib import config as cfg
from automation.lib import finance_coverage as fc
from automation.lib import sheet

log = logging.getLogger("finance.recategorize")

# Canonical keys the categorizer + coverage read — sourced by header position so a
# differently-cased live header still maps correctly (the guard below confirms the
# load-bearing ones exist first).
CANON = ["Date", "Account", "Description", "Amount (ILS)",
         "Category", "Cat-Source", "Txn-ID"]
REQUIRED = ("Category", "Cat-Source", "Description")


class RecategorizeError(RuntimeError):
    """The live Finance-Transactions tab lacks a load-bearing column (§7.1) —
    refuse to write Category/Cat-Source by guessed position. Fail loud."""


def _norm(h) -> str:
    return str(h or "").strip().casefold()


def _cell(raw: list, i: Optional[int]):
    if i is None or i >= len(raw):
        return ""
    v = raw[i]
    return "" if v is None else v


@dataclass
class RunResult:
    total: int = 0
    blank_before: int = 0
    recategorized: int = 0       # blank rows that gained a Category this run
    now_rules: int = 0
    now_llm: int = 0
    still_blank: int = 0
    wrote: bool = False
    before: Optional[fc.Coverage] = None
    after: Optional[fc.Coverage] = None


def run(today: Optional[date] = None, dry_run: bool = False, allow_llm: bool = True,
        sheet_path: Optional[Path] = None) -> RunResult:
    today = today or date.today()
    live = True if sheet_path is not None else sheet.is_live()
    res = RunResult()

    if sheet_path is None and not live:
        print("(no live Sheet backend — nothing to recategorize, won't touch the seed)")
        return res

    grid = sheet.read_grid(cfg.FINANCE_TRANSACTIONS_TAB, sheet_path)
    if not grid:
        print(f"(no {cfg.FINANCE_TRANSACTIONS_TAB} rows — nothing to recategorize)")
        return res

    header = [str(h or "").strip() for h in grid[0]]
    norm = [_norm(h) for h in header]
    idx = {name: (norm.index(_norm(name)) if _norm(name) in norm else None)
           for name in CANON}
    missing = [c for c in REQUIRED if idx[c] is None]
    if missing:
        raise RecategorizeError(
            f"{cfg.FINANCE_TRANSACTIONS_TAB} missing load-bearing column(s) "
            f"{missing} — refusing to write by position (SPEC §7.1)")

    # One pass: canonical-keyed dicts (decoupled from raw header casing) + the
    # physical 1-based row index for the surgical write. Skip fully-blank rows
    # (matches lib/finance_coverage.rows_from_grid).
    rows_all: list[dict] = []
    cand: list[tuple[int, dict]] = []          # (physical row, dict) for blank rows
    for phys, raw in enumerate(grid[1:], start=2):
        if not any(v not in (None, "") for v in raw):
            continue
        d = {name: _cell(raw, idx[name]) for name in CANON}
        rows_all.append(d)
        if not str(d.get("Category", "") or "").strip():
            cand.append((phys, d))

    res.total = len(rows_all)
    res.blank_before = len(cand)
    res.before = fc.coverage(rows_all)

    # Re-run the engine over the blank rows IN PLACE (same dict objects sit in
    # rows_all, so the AFTER coverage reflects the result). A dry-run previews the
    # rules stage only — deterministic, no API spend; the live run adds the LLM
    # gap-fill (§8.6). Already-categorized rows are absent from `cand`, untouched.
    categorize.categorize_transactions([d for _, d in cand],
                                       allow_llm=allow_llm and not dry_run)

    changed = [(phys, d) for phys, d in cand
               if str(d.get("Category", "") or "").strip()]
    res.recategorized = len(changed)
    res.now_rules = sum(1 for _, d in changed if d.get("Cat-Source") == "rules")
    res.now_llm = sum(1 for _, d in changed if d.get("Cat-Source") == "llm")
    res.still_blank = res.blank_before - res.recategorized
    res.after = fc.coverage(rows_all)

    cat_col, src_col = idx["Category"] + 1, idx["Cat-Source"] + 1
    cells = []
    for phys, d in changed:
        cells.append((phys, cat_col, d["Category"]))
        cells.append((phys, src_col, d["Cat-Source"]))

    _print_summary(res, changed, dry_run, allow_llm)

    if dry_run:
        note = ("; rules-only preview — the live run's DeepSeek gap-fill will "
                "categorize more" if res.recategorized or allow_llm else "")
        print(f"(dry-run — no Sheet write{note})")
    elif cells:
        _reverify_columns(idx, sheet_path)   # header may have drifted since the read (§7.1)
        sheet.write_cells(cfg.FINANCE_TRANSACTIONS_TAB, cells, sheet_path)
        res.wrote = True
        print(f"wrote Category/Cat-Source for {res.recategorized} row(s)")
    else:
        print("nothing to write — every blank row stayed blank")
    return res


def _reverify_columns(idx: dict, sheet_path: Optional[Path]) -> None:
    """Re-read the header immediately before writing and confirm the write columns
    have not shifted since the initial read — a drift (e.g. a column inserted before
    Category/Cat-Source) would otherwise stamp the wrong column. Fail loud (§7.1)
    rather than corrupt the live ledger; cheap on a once-per-gate run."""
    grid = sheet.read_grid(cfg.FINANCE_TRANSACTIONS_TAB, sheet_path)
    header = [_norm(h) for h in (grid[0] if grid else [])]
    for name in ("Category", "Cat-Source"):
        i = idx[name]
        if i >= len(header) or header[i] != _norm(name):
            raise RecategorizeError(
                f"{cfg.FINANCE_TRANSACTIONS_TAB} header shifted between read and write "
                f"(col {i + 1} is no longer {name!r}) — aborted before writing (§7.1)")


def _print_summary(res: RunResult, changed, dry_run: bool, allow_llm: bool) -> None:
    b, a = res.before, res.after
    print(f"\nFinance-Transactions: {res.total} rows · {res.blank_before} blank")
    stage = "rules-only (dry-run preview)" if dry_run else (
        "rules + DeepSeek" if allow_llm else "rules-only")
    print(f"recategorized [{stage}]: {res.recategorized} "
          f"(rules {res.now_rules} · llm {res.now_llm}) · {res.still_blank} still blank")
    print(f"coverage of budget-eligible rows: "
          f"{b.coverage_pct * 100:.0f}% → {a.coverage_pct * 100:.0f}%  "
          f"(excluded/Card-Settlement {b.excluded} → {a.excluded})")
    if changed:
        shown = changed[:25]
        print(f"\nchanges{' (first 25)' if len(changed) > 25 else ''}:")
        for _, d in shown:
            tid = str(d.get("Txn-ID", "") or "")[:10]
            desc = fc._clip(d.get("Description", ""), 40)
            print(f"  {tid:<10}  {desc:<41} → {d['Category']} [{d['Cat-Source']}]")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="preview the rules-stage reclassification, write nothing")
    ap.add_argument("--no-llm", action="store_true",
                    help="rules-only (skip the DeepSeek gap-fill) even on a live write")
    ap.add_argument("--as-of", help="YYYY-MM-DD; defaults to today (cosmetic, logging)")
    ap.add_argument("--sheet", help="explicit xlsx path (tooling/tests)")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(today, dry_run=args.dry_run, allow_llm=not args.no_llm,
        sheet_path=Path(args.sheet) if args.sheet else None)


if __name__ == "__main__":
    main()
