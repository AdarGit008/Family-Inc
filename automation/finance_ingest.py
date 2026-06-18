"""
Family inc. — finance ingest (SPEC.md §12.2, M6; unfrozen D-049/050/051).

The Python half of the finance lane. The Node scraper (automation/finance/
scrape.js) logs into Mizrahi / Max / Cal read-only and writes one CSV per
provider to the staging dir (FAMILY_INC_FINANCE_DIR, /var/lib/family-inc/finance
on the box). This reads those CSVs, normalizes, dedups on Txn-ID, and writes via
lib/sheet — the ONLY Sheet writer (D-016): NEW transactions appended to
Finance-Transactions, account balances upserted into Finance-Accounts.

Node scrapes; Python owns every Sheet write (mirrors the bridge/summarizer
split). The local CSV is the only staging — no Drive (D-031).

Delivery is SILENT (§12.2): balances + spend surface in the weekly briefing
Money section + the dashboard Money drawer, never an alert, never the 2/day
budget. The only finance *message* is fail-loud — an OTP re-challenge or a
scrape failure (recorded by scrape.js in _scrape_errors.json) raises after the
good CSVs are ingested, so systemd OnFailure raises the fail-flag the next
digest reports (§9/§10.2).

Categorization (M6.4, D-050/051): `_parse_rows` writes Category + Cat-Source
BLANK; `lib/categorize` then fills them on the NEW (post-dedup) transactions —
on-box rules first, DeepSeek gap-fill on the rules-miss remainder (description +
amount only, §8.6). Degrade-quiet: keyless / off-vocab leaves a row blank.

CSV contract (written by scrape.js) — header, one row per transaction:
    account,balance,date,identifier,amount,description
`balance` repeats per row (the account's current balance); an account with no
transactions in the window emits a single balance-only row (date/identifier/
amount/description blank) so its balance still lands in Finance-Accounts.

Idempotency: same-day reruns overwrite the day's CSV and dedup on Txn-ID, and
the Sheet write is the gate — a creds-less/dev run (no live backend, no explicit
path) writes nothing and never touches the committed seed (mirrors §12.1/D-037).

Run:
  python3 automation/finance_ingest.py                 # mock (no CSVs, not live)
  python3 automation/finance_ingest.py --dir DIR
  python3 automation/finance_ingest.py --as-of 2026-06-17 --dry-run
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python3 automation/finance_ingest.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import argparse
import csv
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from automation.lib import categorize
from automation.lib import config as cfg
from automation.lib import sheet

log = logging.getLogger("finance")

SCRAPE_ERRORS_FILE = "_scrape_errors.json"   # written by scrape.js on a partial run


class FinanceError(RuntimeError):
    """Ingest failed — the run reports it and exits non-zero so the systemd
    OnFailure fail-flag fires (§10.2). Raised AFTER good CSVs are persisted."""


# ---------------------------------------------------------------------------
# Normalize helpers
# ---------------------------------------------------------------------------
def _to_amount(v) -> Optional[float]:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def _norm_date(v) -> Optional[str]:
    """Any parseable date → 'YYYY-MM-DD' (the Sheet/SUMIFS date form). Unparseable
    → None (the row is skipped, never invented)."""
    from automation.lib.dates import to_date
    d = to_date(v)
    return d.isoformat() if d else None


def _last4(account: str) -> str:
    digits = "".join(ch for ch in str(account) if ch.isdigit())
    tail = digits or str(account)
    return tail[-4:]


def txn_id(date_s: str, amount, description: str, account: str,
           identifier: str = "") -> str:
    """Provider id when present, else a stable hash of the natural key. The hash
    is deterministic so a re-fetched overlap window dedups to the same id.
    Limitation (no provider id): two genuinely distinct same-day charges with an
    identical merchant + amount hash to one id, so the second is deduped as a
    phantom duplicate. israeli-bank-scrapers supplies `identifier` for most
    providers, so this is rare; revisit if a provider returns id-less rows."""
    identifier = (identifier or "").strip()
    if identifier:
        return identifier
    key = f"{date_s}|{amount}|{(description or '').strip()}|{(account or '').strip()}"
    return "h:" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def provider_of(csv_path: Path) -> str:
    """`mizrahi_2026-06-17.csv` → `mizrahi` (stem before the first underscore)."""
    return csv_path.stem.split("_", 1)[0].lower()


# ---------------------------------------------------------------------------
# Parse one provider CSV → (transaction rows, account rows) in Sheet shape
# ---------------------------------------------------------------------------
@dataclass
class ParseResult:
    txns: list[dict] = field(default_factory=list)
    accounts: dict[str, dict] = field(default_factory=dict)   # account → row
    skipped: int = 0


def _parse_rows(reader, provider: str, today: date, now: datetime) -> ParseResult:
    """Shared core: a csv.DictReader (file or in-memory) → ParseResult. One
    Finance-Accounts row per account (balance, current-state) + the window's
    transactions; balance-only rows (blank date/amount) feed the account only."""
    acct_type = cfg.FINANCE_PROVIDER_TYPES.get(provider, "")
    imported_at = now.isoformat(timespec="seconds")
    res = ParseResult()
    for raw in reader:
        row = {(k or "").strip().lower(): v for k, v in raw.items()}
        account = str(row.get("account", "")).strip()
        if not account:
            res.skipped += 1
            continue
        # Account balance — current-state, upserted into Finance-Accounts.
        if account not in res.accounts:
            bal = _to_amount(row.get("balance"))
            res.accounts[account] = {
                "Account Name": account, "Type": acct_type,
                "Bank/Provider": provider, "Last 4": _last4(account),
                "Owner": "", "Currency": "ILS", "Last Imported": today.isoformat(),
                "Balance Snapshot": "" if bal is None else bal, "Notes": "",
            }
        # Transaction — skip the balance-only rows (blank date/amount).
        d = _norm_date(row.get("date"))
        amt = _to_amount(row.get("amount"))
        if d is None or amt is None:
            continue
        desc = str(row.get("description", "")).strip()
        res.txns.append({
            "Date": d, "Account": account, "Description": desc,
            "Amount (ILS)": amt,
            "Category": "",            # M6.4 fills (rules + DeepSeek, D-050/051)
            "Cat-Source": "",
            "Txn-ID": txn_id(d, amt, desc, account, str(row.get("identifier", ""))),
            "Imported-At": imported_at,
        })
    return res


def parse_csv(csv_path: Path, today: date, now: datetime) -> ParseResult:
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        return _parse_rows(csv.DictReader(fh), provider_of(csv_path), today, now)


# ---------------------------------------------------------------------------
# Mock sample — a dev smoke with no CSVs and no live backend (writes nothing).
# Generic placeholder values only — no real account numbers or merchants.
# ---------------------------------------------------------------------------
def _mock_csv_text() -> str:
    return ("account,balance,date,identifier,amount,description\n"
            "MOCK-001,12500.00,2026-06-15,,-432.50,SAMPLE GROCERY\n"
            "MOCK-001,12500.00,2026-06-16,,-89.90,SAMPLE PHARMACY\n"
            "MOCK-777,,2026-06-15,,-280.00,SAMPLE FUEL\n")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
@dataclass
class RunResult:
    txns_new: int = 0
    txns_seen: int = 0          # already on the durable tab (Txn-ID match)
    txns_phantom_dup: int = 0   # dropped as an in-batch id collision (id-less rows
                                # that hash alike) — NOT "already on the tab"
    accounts: int = 0
    is_mock: bool = False
    wrote: bool = False
    scrape_errors: list[str] = field(default_factory=list)


def _csv_paths(csv_dir: Path) -> list[Path]:
    return sorted(p for p in csv_dir.glob("*.csv") if not p.name.startswith("_"))


def _read_scrape_errors(csv_dir: Path) -> list[str]:
    p = csv_dir / SCRAPE_ERRORS_FILE
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return ["unreadable _scrape_errors.json"]
    items = data.get("errors", data) if isinstance(data, dict) else data
    out = []
    for e in items or []:
        if isinstance(e, dict):
            out.append(f"{e.get('provider', '?')}: {e.get('error', e)}")
        else:
            out.append(str(e))
    return out


def run(csv_dir: Optional[Path] = None, sheet_path: Optional[Path] = None,
        today: Optional[date] = None, now: Optional[datetime] = None,
        dry_run: bool = False, live_override: Optional[bool] = None) -> RunResult:
    today = today or date.today()
    now = now or datetime.now()
    csv_dir = Path(csv_dir) if csv_dir else cfg.FINANCE_STATE_DIR
    live = sheet.is_live() if live_override is None else live_override
    res = RunResult()

    paths = _csv_paths(csv_dir) if csv_dir.exists() else []
    res.scrape_errors = _read_scrape_errors(csv_dir) if csv_dir.exists() else []

    if not paths:
        # No CSVs. On a live/explicit run that means the scraper produced
        # nothing — bank_creds.json missing or the scrape failed: FAIL LOUD so
        # OnFailure raises the fail-flag (§10.2). Creds-less dev → MOCK.
        if live or sheet_path is not None:
            detail = ("; ".join(res.scrape_errors)
                      or "bank_creds.json missing or scrape produced no CSV")
            raise FinanceError(f"no finance CSVs in {csv_dir} — {detail}")
        print("RUNNING IN MOCK MODE — no finance CSVs; using sample data "
              "(nothing is written without a live Sheet)")
        res.is_mock = True
        parsed = _parse_text(_mock_csv_text(), "mizrahi", today, now)
        categorize.categorize_transactions(parsed.txns, allow_llm=False)  # rules-only smoke
        res.txns_new, res.accounts = len(parsed.txns), len(parsed.accounts)
        _print_summary(res, parsed)
        return res

    txns: list[dict] = []
    accounts: dict[str, dict] = {}
    for p in paths:
        pr = parse_csv(p, today, now)
        txns.extend(pr.txns)
        accounts.update(pr.accounts)      # current-state: latest file wins per account
    account_rows = list(accounts.values())

    # Dedup transactions: against the tab (durable record) + within this batch.
    seen = {str(v).strip()
            for v in sheet.read_column(cfg.FINANCE_TRANSACTIONS_TAB, "Txn-ID", sheet_path)}
    new_txns, batch = [], set()
    for t in txns:
        tid = t["Txn-ID"]
        if tid in seen:
            res.txns_seen += 1          # genuinely already on the tab
            continue
        if tid in batch:
            res.txns_phantom_dup += 1   # in-batch id collision (see Txn-ID docstring)
            continue
        batch.add(tid)
        new_txns.append(t)
    res.txns_new = len(new_txns)
    res.accounts = len(account_rows)

    # Categorize the NEW transactions in place before the write (M6.4, §12.2/
    # §8.6): on-box rules first, then DeepSeek gap-fills the rules-miss
    # remainder (description + amount only). Rules always run; the LLM stage is
    # skipped on a dry-run preview and whenever no provider key is configured.
    categorize.categorize_transactions(new_txns, allow_llm=not dry_run)

    print(f"\nParsed {len(txns)} transaction(s) from {len(paths)} CSV(s) · "
          f"{res.txns_new} new · {res.txns_seen} already on the tab · "
          f"{len(account_rows)} account(s)"
          + (f" · {res.txns_phantom_dup} in-batch dup(s) dropped" if res.txns_phantom_dup else "")
          + (f" · {len(res.scrape_errors)} scrape error(s)" if res.scrape_errors else ""))

    if dry_run:
        print("(dry-run — no Sheet write)")
    elif sheet_path is None and not live:
        print("(no live Sheet backend — Finance rows NOT written)")
    else:
        sheet.append_rows(cfg.FINANCE_TRANSACTIONS_TAB,
                          sheet.FINANCE_TRANSACTIONS_COLUMNS, new_txns, sheet_path)
        sheet.upsert_rows(cfg.FINANCE_ACCOUNTS_TAB, sheet.FINANCE_ACCOUNTS_COLUMNS,
                          account_rows, key_column="Account Name",
                          update_columns=sheet.FINANCE_ACCOUNTS_UPDATE_COLUMNS,
                          path=sheet_path)
        res.wrote = True
        print(f"wrote {res.txns_new} new transaction(s) + {res.accounts} account balance(s)")

    # Fail loud on scrape errors AFTER the good data is persisted — the OTP
    # re-challenge / site-change surfaces to the next digest, data isn't lost.
    if res.scrape_errors and not dry_run:
        raise FinanceError("scrape reported errors: " + "; ".join(res.scrape_errors))
    return res


def _parse_text(text: str, provider: str, today: date, now: datetime) -> ParseResult:
    """_parse_rows over an in-memory CSV string (mock + tests)."""
    import io
    return _parse_rows(csv.DictReader(io.StringIO(text)), provider, today, now)


def _print_summary(res: RunResult, parsed: ParseResult) -> None:
    print(f"\n[mock] {len(parsed.txns)} transaction(s), "
          f"{len(parsed.accounts)} account(s) — not written")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="CSV staging dir (default: FINANCE_STATE_DIR)")
    ap.add_argument("--as-of", help="YYYY-MM-DD, defaults to today")
    ap.add_argument("--dry-run", action="store_true", help="parse + print, write nothing")
    args = ap.parse_args()
    today = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    run(csv_dir=Path(args.dir) if args.dir else None, today=today, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
