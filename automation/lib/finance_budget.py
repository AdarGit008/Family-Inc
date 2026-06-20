"""
Family inc. — Finance-Budget actuals formulas (SPEC §12.2, M6.3/M6.4; D-050).

The budget actuals reconcile via a TEXT-PREFIX WILDCARD `SUMIFS` over the ISO-text
`Date` column (`<yyyy-mm>&"*"`), NOT a serial `DATE()` window — which read ₪0
against the RAW-appended text dates (the M6.4 landmine). This module is the SINGLE
SOURCE of that formula text: the committed seed carries it, the live installer
(`automation/finance_budget_formulas.py`) stamps it onto the live `Finance-Budget`
tab, and the tests pin both against `budget_formula_cells` so seed, installer and
live can't silently diverge.

Pure — grid in, cells out; no Sheet/backend I/O lives here (the CLI does the read
and write through `lib/sheet`). `budget_formula_cells(grid)` validates the header
(load-bearing column order, §12.2 — fail loud rather than stamp a formula into the
wrong column), discovers the category rows from column A, and returns the
`(row, col, formula)` cells for the MACHINE-owned columns only: Actual / Variance /
% / YTD / Last-Month per category, the `I`-helper date tags, and the TOTAL sums.
It never writes a category row's Category (A) or Monthly Target (B), and never any
Notes (G) — those are human-owned (Shanee's budget); the only Target cell it writes
is the TOTAL row's `=SUM` (machine-owned, matching the seed). So a re-run can't
clobber a human value, and the "stray Notes SUMIFS" copy-artifact class is
impossible by construction.
"""
from __future__ import annotations

from automation.lib import config as cfg

# Load-bearing column order (SPEC §12.2): 1-based physical positions. The SUMIFS
# and every consumer (briefing Money section, dashboard Money drawer) read these.
COL_CATEGORY = 1     # A — human (Shanee's budget vocab)
COL_TARGET = 2       # B — human (monthly target)
COL_ACTUAL = 3       # C — this-month actual    (SUMIFS, machine)
COL_VARIANCE = 4     # D — target − actual       (machine)
COL_PCT = 5          # E — actual / target       (machine)
COL_YTD = 6          # F — year-to-date actual   (SUMIFS, machine)
COL_NOTES = 7        # G — human (never written)
COL_ASOF = 8         # H — helper labels
COL_HELPER = 9       # I — helper date tags (=TODAY() + month tags)
COL_LASTMONTH = 10   # J — previous-month actual (SUMIFS, machine)

# The headers the installer validates before writing by position. Only the
# load-bearing columns (those a formula writes to or a consumer reads) are pinned;
# Notes/As-of are cosmetic. Drift here fails loud (mirrors validate_reminders_header).
EXPECTED_HEADERS = {
    COL_CATEGORY: "Category",
    COL_TARGET: "Monthly Target (ILS)",
    COL_ACTUAL: "Actual (current month)",
    COL_VARIANCE: "Variance",
    COL_PCT: "% of Target",
    COL_YTD: "YTD Actual",
    COL_LASTMONTH: "Last Month (ILS)",
}

TOTAL_LABEL = "TOTAL"


class BudgetHeaderError(RuntimeError):
    """The live Finance-Budget tab drifted from the load-bearing layout (§12.2),
    or has no category rows. Refuse to stamp formulas by position onto an unknown
    or empty tab — fail loud, never guess."""


def col_letter(idx: int) -> str:
    """1 → 'A', 26 → 'Z', 27 → 'AA'. Used to build A1 references in formula text."""
    s = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


_A, _B, _C, _F, _I = (col_letter(COL_CATEGORY), col_letter(COL_TARGET),
                      col_letter(COL_ACTUAL), col_letter(COL_YTD),
                      col_letter(COL_HELPER))


def _norm(h) -> str:
    return str(h or "").strip().casefold()


def validate_header(header_row: list) -> list[str]:
    """One problem string per drifted load-bearing column, [] when clean."""
    problems = []
    for col, expected in EXPECTED_HEADERS.items():
        got = header_row[col - 1] if col <= len(header_row) else None
        if _norm(got) != _norm(expected):
            problems.append(f"col {col}: expected {expected!r}, found {got!r}")
    return problems


def _cell_a(row: list):
    return row[COL_CATEGORY - 1] if COL_CATEGORY - 1 < len(row) else None


def category_rows(grid: list[list]) -> list[int]:
    """1-based row indices of the category rows: column A non-blank, not the
    TOTAL row, below the header."""
    return [idx for idx, row in enumerate(grid[1:], start=2)
            if _cell_a(row) not in (None, "") and _norm(_cell_a(row)) != _norm(TOTAL_LABEL)]


def total_row(grid: list[list]) -> int | None:
    """1-based index of the TOTAL row, or None if the tab has none (optional)."""
    for idx, row in enumerate(grid[1:], start=2):
        if _norm(_cell_a(row)) == _norm(TOTAL_LABEL):
            return idx
    return None


def _actual(r: int, tag: str) -> str:
    """Signed-spend SUMIFS for category row `r`: −Σ Amount(D) where Category(E) is
    $A{r} and Date(A) text-prefix-matches `tag`. Negated so spend (stored negative)
    reads positive; IFERROR→0 so an empty month shows ₪0, not an error."""
    t = f"'{cfg.FINANCE_TRANSACTIONS_TAB}'"
    return f"=IFERROR(-SUMIFS({t}!D:D,{t}!E:E,${_A}{r},{t}!A:A,{tag}),0)"


def budget_formula_cells(grid: list[list]) -> list[tuple[int, int, str]]:
    """The (row, col, formula) cells to stamp onto Finance-Budget. Validates the
    header (raises BudgetHeaderError on load-bearing drift), discovers the category
    rows, and builds the machine-owned formulas only. Idempotent: same grid → same
    cells, so a re-run (e.g. after Shanee's budget migration adds rows) just
    re-stamps for the current layout. (It re-stamps the CURRENT category rows; it
    does not clear machine cells on a row that ceased to be a category — a removed
    category leaves stale actuals to clear by hand.)"""
    problems = validate_header(grid[0] if grid else [])
    if problems:
        raise BudgetHeaderError(
            "Finance-Budget header drifted from SPEC §12.2: " + "; ".join(problems))
    cats = category_rows(grid)
    if not cats:
        raise BudgetHeaderError(
            "Finance-Budget has no category rows — nothing to stamp (populate "
            "column A first: Shanee's budget migration is the vocab authority)")

    cells: list[tuple[int, int, str]] = []
    # Helper date tags (column I) — the SUMIFS criteria key off these; the H
    # labels document the block (cosmetic, carried from the seed).
    cells += [
        (1, COL_ASOF, "As-of date"),
        (1, COL_HELPER, "=TODAY()"),
        (2, COL_ASOF, "Current month tag"),
        (2, COL_HELPER, f'=TEXT({_I}1,"yyyy-mm")'),
        (3, COL_ASOF, "Prev month tag"),
        (3, COL_HELPER, f'=TEXT(EDATE(${_I}$1,-1),"yyyy-mm")'),
    ]
    # Per category row: Actual (this month) / YTD / Last month / Variance / %.
    for r in cats:
        cells += [
            (r, COL_ACTUAL, _actual(r, f'${_I}$2&"*"')),               # current month
            (r, COL_YTD, _actual(r, f'TEXT(${_I}$1,"yyyy")&"*"')),     # year-to-date
            (r, COL_LASTMONTH, _actual(r, f'${_I}$3&"*"')),            # previous month
            (r, COL_VARIANCE, f"={_B}{r}-{_C}{r}"),
            (r, COL_PCT, f"=IFERROR({_C}{r}/{_B}{r},0)"),
        ]
    # TOTAL row (optional) — sums over the category span + its own variance / %.
    # Every category must PRECEDE the TOTAL: a category below it would put the TOTAL
    # row inside its own SUM range (=SUM straddling t → circular #ERROR, and the
    # briefing/dashboard read the TOTAL), so refuse that layout (fail loud) rather
    # than emit a self-referential sum. The span is min..max of the category rows —
    # contiguous in the seed; a blank spacer row inside it just sums as 0.
    t = total_row(grid)
    if t is not None:
        below = [r for r in cats if r > t]
        if below:
            raise BudgetHeaderError(
                f"category row(s) {below} sit below the TOTAL row ({t}) — move them "
                "above TOTAL; the actuals + TOTAL sum assume every category precedes it")
        lo, hi = min(cats), max(cats)
        cells += [
            (t, COL_TARGET, f"=SUM({_B}{lo}:{_B}{hi})"),
            (t, COL_ACTUAL, f"=SUM({_C}{lo}:{_C}{hi})"),
            (t, COL_YTD, f"=SUM({_F}{lo}:{_F}{hi})"),
            (t, COL_VARIANCE, f"={_B}{t}-{_C}{t}"),
            (t, COL_PCT, f"=IFERROR({_C}{t}/{_B}{t},0)"),
        ]
    return cells
