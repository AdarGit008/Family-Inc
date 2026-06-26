"""
Family inc. — finance categorization COVERAGE (SPEC §12.2, M6.4 acceptance).

A read-only measure of how much of `Finance-Transactions` carries a Category,
split into the three states that matter for the M6 milestone close:

  • categorized  — a Category that IS a budget row (Cat-Source rules | llm |
                   manual). These feed the actuals SUMIFS.
  • excluded     — a Category in `categorize.EXCLUDED_CATEGORIES`
                   ('Card Settlement', the Cal-mirror lines). DELIBERATELY not a
                   budget row — the spend counts once via the per-merchant card
                   scrape — so these are handled-by-design, neither a hit nor a
                   miss. They come OUT of the coverage denominator.
  • blank        — no Category. An honest unknown: a mix of merchants the engine
                   missed AND genuinely merchant-less wrappers (ATM, cheque,
                   inter-account) that have nothing to categorize.

The headline is COVERAGE OF BUDGET-ELIGIBLE ROWS = categorized / (total −
excluded). This is yield (did we put *a* category on it), NOT correctness (is
the category *right*) — a true false-positive rate needs a human-mark channel,
deferred to ROADMAP #12. So the milestone number this surface reports is
"X% categorized", and the accept bar is set report-first from the live read
(candidate ≥90% of budget-eligible rows; Cal already runs ~90%).

Pure: grid/rows in, numbers + a markdown render out. No Sheet I/O lives here
(the CLI, automation/finance_coverage.py, does the read through lib/sheet). The
render names the still-blank merchants so the operator can decide whether a new
rule is warranted — operator-only output (stdout or the gitignored Briefings/),
never a committed path, like accuracy_review.py's ALERT text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from automation.lib import config as cfg
from automation.lib.categorize import EXCLUDED_CATEGORIES

# Cat-Source values the categorizer writes; anything else a human typed → "manual".
KNOWN_SOURCES = ("rules", "llm")


def _norm(h) -> str:
    return str(h or "").strip().casefold()


# Canonical Finance-Transactions columns coverage reads — used to normalize a
# differently-cased/spaced live header to the canonical key, so a quirk like
# "Category " (trailing space) or "cat-source" can't make every row read as blank
# and report a false 0% on the milestone surface (the backfill already resolves by
# _norm; this gives the read path the same robustness).
_CANON_COLUMNS = ("Date", "Account", "Description", "Amount (ILS)",
                  "Category", "Cat-Source", "Txn-ID", "Imported-At")
_CANON_BY_NORM = {_norm(c): c for c in _CANON_COLUMNS}


def rows_from_grid(grid: list[list]) -> list[dict]:
    """A raw Finance-Transactions grid (header + rows) → header-keyed dicts (keys
    normalized to the canonical column names), skipping fully-blank rows. Tolerant
    of short rows (missing trailing cells)."""
    if not grid:
        return []
    header = [_CANON_BY_NORM.get(_norm(h), str(h or "").strip()) for h in grid[0]]
    out: list[dict] = []
    for row in grid[1:]:
        d = {h: (row[i] if i < len(row) else None) for i, h in enumerate(header)}
        if any(v not in (None, "") for v in d.values()):
            out.append(d)
    return out


def _category(row: dict) -> str:
    return str(row.get("Category", "") or "").strip()


def _source(row: dict) -> str:
    s = str(row.get("Cat-Source", "") or "").strip().casefold()
    return s if s in KNOWN_SOURCES else ("manual" if _category(row) else "")


def _clip(text: str, n: int = 48) -> str:
    t = re.sub(r"\s+", " ", str(text or "").strip())
    return (t[: n - 1] + "…") if len(t) > n else t


@dataclass
class AccountCoverage:
    total: int = 0
    categorized: int = 0
    excluded: int = 0
    blank: int = 0

    @property
    def eligible(self) -> int:
        return self.total - self.excluded

    @property
    def pct(self) -> float:
        return self.categorized / self.eligible if self.eligible else 0.0


@dataclass
class Coverage:
    total: int = 0
    categorized: int = 0          # non-blank Category that is NOT an excluded bucket
    excluded: int = 0             # Category in EXCLUDED_CATEGORIES (Card Settlement)
    blank: int = 0                # no Category
    by_source: dict = field(default_factory=dict)        # rules|llm|manual -> count (categorized rows only)
    by_account: dict = field(default_factory=dict)       # account -> AccountCoverage
    blank_samples: list = field(default_factory=list)    # (description_clip, count), desc

    @property
    def eligible(self) -> int:
        """Budget-eligible rows — the coverage denominator (excludes the
        by-design Card-Settlement mirror lines, which are neither hit nor miss)."""
        return self.total - self.excluded

    @property
    def coverage_pct(self) -> float:
        return self.categorized / self.eligible if self.eligible else 0.0

    @property
    def raw_pct(self) -> float:
        return self.categorized / self.total if self.total else 0.0


def coverage(rows: list[dict]) -> Coverage:
    """Pure compute over Finance-Transactions dict-rows → Coverage. Every row is
    exactly one of categorized / excluded / blank, so the three partition total."""
    c = Coverage()
    blank_counts: dict[str, int] = {}
    for r in rows:
        c.total += 1
        cat = _category(r)
        acct = str(r.get("Account", "") or "").strip() or "(unknown)"
        ac = c.by_account.setdefault(acct, AccountCoverage())
        ac.total += 1
        if not cat:
            c.blank += 1
            ac.blank += 1
            key = _clip(r.get("Description", "")) or "(no description)"
            blank_counts[key] = blank_counts.get(key, 0) + 1
        elif cat in EXCLUDED_CATEGORIES:
            c.excluded += 1
            ac.excluded += 1
        else:
            c.categorized += 1
            ac.categorized += 1
            # by_source is the breakdown render() prints UNDER `categorized`, so tally it
            # over categorized rows only — an excluded Card-Settlement line carries
            # Cat-Source "rules" too, and counting it here would make the rules sub-count
            # overshoot (and not sum to) the categorized total on every live run.
            c.by_source[_source(r)] = c.by_source.get(_source(r), 0) + 1
    c.blank_samples = sorted(blank_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return c


def render(c: Coverage, today: date, *, blank_top: int = 15) -> str:
    """Markdown operator surface (stdout / gitignored Briefings/). Names the
    still-blank merchants so the operator can judge whether a rule is warranted —
    NEVER a committed path (the descriptions are live merchant strings)."""
    if c.total == 0:
        return ("# 🏠 Family inc. — finance categorization coverage\n"
                f"_{today.isoformat()}_\n\n_No finance transactions yet._\n")
    src = c.by_source
    parts = [
        "# 🏠 Family inc. — finance categorization coverage",
        f"_{today.isoformat()} · Finance-Transactions ({c.total} rows)_\n",
        "## Summary",
        f"- **Coverage of budget-eligible rows: {c.coverage_pct * 100:.0f}%** "
        f"({c.categorized} of {c.eligible})  ← the milestone metric",
        f"- categorized: {c.categorized}  "
        f"(rules {src.get('rules', 0)} · llm {src.get('llm', 0)}"
        + (f" · manual {src['manual']}" if src.get('manual') else "") + ")",
        f"- excluded by design (Card Settlement mirror): {c.excluded}",
        f"- uncategorized (blank): {c.blank}",
        f"- raw coverage (incl. excluded in the base): {c.raw_pct * 100:.0f}%",
    ]
    parts.append("\n## By account")
    parts.append("| account | rows | categorized | excluded | blank | coverage |")
    parts.append("|---|--:|--:|--:|--:|--:|")
    for acct, ac in sorted(c.by_account.items(), key=lambda kv: -kv[1].total):
        parts.append(f"| {acct} | {ac.total} | {ac.categorized} | {ac.excluded} "
                     f"| {ac.blank} | {ac.pct * 100:.0f}% |")
    if c.blank_samples:
        parts.append("\n## Uncategorized — top descriptions (operator review)")
        parts.append("_A merchant here that recurs is a candidate for a new rule "
                     "(`seeds/14_Finance_Category_Rules.csv`); a merchant-less "
                     "wrapper (ATM/cheque/inter-account) is correctly blank._")
        for desc, n in c.blank_samples[:blank_top]:
            parts.append(f"- {desc}  ×{n}")
        if len(c.blank_samples) > blank_top:
            parts.append(f"- …and {len(c.blank_samples) - blank_top} more distinct.")
    parts.append(
        "\n---\n_Bar: report-first — set the accept threshold from this read "
        "(candidate ≥90% of budget-eligible rows; Cal runs ~90%). This is "
        "COVERAGE (did we tag it), not CORRECTNESS (is the tag right) — a true "
        "false-positive rate needs a human-mark channel, deferred to ROADMAP #12._")
    return "\n".join(parts) + "\n"
