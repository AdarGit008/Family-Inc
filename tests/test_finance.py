"""Tests for automation/finance_ingest.py (SPEC §12.2, M6.1; D-049/050/051).

Hermetic: a mock per-provider CSV → ingest → a tmp xlsx Sheet (explicit path,
never the live Sheet / committed seed). No banks, no Node, no network — the
Node scraper (scrape.js) is VPS-only and node-checked, not unit-tested.
Covers: CSV → Sheet, Txn-ID dedup + rerun idempotency, balance-only rows,
provider-id vs hash ids, Finance-Accounts upsert (human fields preserved),
fail-loud on missing creds / scrape-error marker, and the seed-safety gate.
"""

from datetime import date, datetime

import pytest
from openpyxl import Workbook, load_workbook

from automation import finance_ingest as fin
from automation.lib import config as cfg
from automation.lib import sheet

TODAY = date(2026, 6, 17)
NOW = datetime(2026, 6, 17, 6, 0, 0)

CSV = (
    "account,balance,date,identifier,amount,description\n"
    "MIZ-0001,12500.00,2026-06-15,abc123,-432.50,SHUFERSAL DEAL\n"
    "MIZ-0001,12500.00,2026-06-16,,-89.90,SUPERPHARM\n"
    "MIZ-0777,,2026-06-15,,-280.00,PAZ GAS\n"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _csv(tmp_path, text=CSV, name="mizrahi_2026-06-17.csv"):
    d = tmp_path / "stage"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")
    return d


def _sheet(tmp_path, accounts_rows=None):
    """A tmp xlsx with a placeholder tab (so the file loads); optionally a
    pre-seeded Finance-Accounts tab to test upsert-preserves-human-fields."""
    wb = Workbook()
    wb.active.title = "Placeholder"
    if accounts_rows is not None:
        ws = wb.create_sheet(cfg.FINANCE_ACCOUNTS_TAB)
        ws.append(sheet.FINANCE_ACCOUNTS_COLUMNS)
        for r in accounts_rows:
            ws.append(r)
    p = tmp_path / "finance.xlsx"
    wb.save(p)
    return p


def _rows(path, tab):
    wb = load_workbook(path, data_only=True)
    if tab not in wb.sheetnames:
        return []
    return [[c.value for c in row] for row in wb[tab].iter_rows()]


def _col(tab_rows, name):
    """Values under a named column (skips header)."""
    i = tab_rows[0].index(name)
    return [r[i] for r in tab_rows[1:]]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def test_provider_of():
    from pathlib import Path
    assert fin.provider_of(Path("mizrahi_2026-06-17.csv")) == "mizrahi"
    assert fin.provider_of(Path("/var/x/MAX_2026-06-17.csv")) == "max"


def test_txn_id_prefers_identifier_then_stable_hash():
    assert fin.txn_id("2026-06-15", -10, "X", "A", "real-id") == "real-id"
    h1 = fin.txn_id("2026-06-15", -10, "X", "A", "")
    h2 = fin.txn_id("2026-06-15", -10, "X", "A", "")
    h3 = fin.txn_id("2026-06-15", -11, "X", "A", "")
    assert h1.startswith("h:") and h1 == h2 and h1 != h3


# ---------------------------------------------------------------------------
# CSV → Sheet
# ---------------------------------------------------------------------------
def test_mock_csv_ingests_to_sheet(tmp_path):
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=_csv(tmp_path), sheet_path=sp, today=TODAY, now=NOW)
    assert res.txns_new == 3 and res.accounts == 2 and res.wrote

    txns = _rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)
    assert txns[0] == sheet.FINANCE_TRANSACTIONS_COLUMNS          # header
    assert len(txns) - 1 == 3
    assert set(_col(txns, "Txn-ID")) == {"abc123"} | {
        t for t in _col(txns, "Txn-ID") if str(t).startswith("h:")}
    # M6.4: the on-box rules engine categorizes at ingest (no LLM key in tests
    # → rules only). SHUFERSAL→Groceries, SUPERPHARM→Health, PAZ→Transport.
    cat_by_desc = dict(zip(_col(txns, "Description"), _col(txns, "Category")))
    assert cat_by_desc["SHUFERSAL DEAL"] == "Groceries"
    assert cat_by_desc["SUPERPHARM"] == "Health"
    assert cat_by_desc["PAZ GAS"] == "Transport"
    assert set(_col(txns, "Cat-Source")) == {"rules"}
    assert "abc123" in _col(txns, "Txn-ID")
    assert -432.5 in _col(txns, "Amount (ILS)")

    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    assert len(accts) - 1 == 2
    miz1 = [r for r in accts[1:] if r[0] == "MIZ-0001"][0]
    assert miz1[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Type")] == "bank"
    assert miz1[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Balance Snapshot")] == 12500.0
    assert miz1[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Last Imported")] == "2026-06-17"
    assert miz1[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Last 4")] == "0001"


def test_dedup_rerun_is_idempotent(tmp_path):
    sp = _sheet(tmp_path)
    d = _csv(tmp_path)
    fin.run(csv_dir=d, sheet_path=sp, today=TODAY, now=NOW)
    res2 = fin.run(csv_dir=d, sheet_path=sp, today=TODAY, now=NOW)
    assert res2.txns_new == 0 and res2.txns_seen == 3
    assert len(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)) - 1 == 3   # no dupes
    assert len(_rows(sp, cfg.FINANCE_ACCOUNTS_TAB)) - 1 == 2       # upsert, not append


def test_balance_only_row_feeds_account_not_txn(tmp_path):
    sp = _sheet(tmp_path)
    text = ("account,balance,date,identifier,amount,description\n"
            "MIZ-0001,9000,2026-06-15,,-50,COFFEE\n"
            "SAV-0002,40000,,,,\n")          # balance-only: no date/amount
    res = fin.run(csv_dir=_csv(tmp_path, text), sheet_path=sp, today=TODAY, now=NOW)
    assert res.txns_new == 1 and res.accounts == 2
    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    sav = [r for r in accts[1:] if r[0] == "SAV-0002"][0]
    assert sav[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Balance Snapshot")] == 40000
    assert "SAV-0002" not in _col(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB), "Account")


def test_upsert_preserves_human_fields(tmp_path):
    # Pre-seed MIZ-0001 with human-edited Owner/Notes + a stale balance.
    pre = ["MIZ-0001", "bank", "mizrahi", "0001", "Adar", "ILS",
           "2026-01-01", 999, "my main account"]
    sp = _sheet(tmp_path, accounts_rows=[pre])
    fin.run(csv_dir=_csv(tmp_path), sheet_path=sp, today=TODAY, now=NOW)
    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    miz1 = [r for r in accts[1:] if r[0] == "MIZ-0001"][0]
    C = sheet.FINANCE_ACCOUNTS_COLUMNS
    assert miz1[C.index("Owner")] == "Adar"             # human field preserved
    assert miz1[C.index("Notes")] == "my main account"  # preserved
    assert miz1[C.index("Balance Snapshot")] == 12500.0  # refreshed
    assert miz1[C.index("Last Imported")] == "2026-06-17"  # refreshed
    # MIZ-0777 is new → appended (so 2 account rows total, no duplicate MIZ-0001)
    assert len(accts) - 1 == 2


# ---------------------------------------------------------------------------
# Fail-loud + seed-safety
# ---------------------------------------------------------------------------
def test_fail_loud_when_no_csvs_on_live(tmp_path):
    empty = tmp_path / "stage"
    empty.mkdir()
    with pytest.raises(fin.FinanceError, match="no finance CSVs"):
        fin.run(csv_dir=empty, today=TODAY, now=NOW, live_override=True)


def test_mock_mode_when_no_csvs_and_not_live(tmp_path):
    empty = tmp_path / "stage"
    empty.mkdir()
    res = fin.run(csv_dir=empty, today=TODAY, now=NOW, live_override=False)
    assert res.is_mock and not res.wrote


def test_scrape_error_marker_fails_loud_after_persisting(tmp_path):
    sp = _sheet(tmp_path)
    d = _csv(tmp_path)
    (d / fin.SCRAPE_ERRORS_FILE).write_text(
        '{"errors": [{"provider": "max", "error": "OTP re-challenge"}]}',
        encoding="utf-8")
    with pytest.raises(fin.FinanceError, match="OTP re-challenge"):
        fin.run(csv_dir=d, sheet_path=sp, today=TODAY, now=NOW)
    # the good CSV's transactions were persisted BEFORE the raise (no data lost)
    assert len(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)) - 1 == 3


def test_not_live_no_path_writes_nothing(tmp_path):
    # csvs present, but no live backend and no explicit path → parse, write
    # nothing (never touches the committed seed — D-038/M2 invariant).
    res = fin.run(csv_dir=_csv(tmp_path), today=TODAY, now=NOW, live_override=False)
    assert res.txns_new == 3 and not res.wrote


def test_dry_run_writes_nothing(tmp_path):
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=_csv(tmp_path), sheet_path=sp, today=TODAY, now=NOW,
                  dry_run=True)
    assert not res.wrote
    assert _rows(sp, cfg.FINANCE_TRANSACTIONS_TAB) == []   # tab never created


def test_amount_with_commas_and_iso_date(tmp_path):
    sp = _sheet(tmp_path)
    text = ("account,balance,date,identifier,amount,description\n"
            'MIZ-0001,"1,234.50",2026-06-15,,"-1,200.00",RENT\n')
    fin.run(csv_dir=_csv(tmp_path, text), sheet_path=sp, today=TODAY, now=NOW)
    txns = _rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)
    assert -1200.0 in _col(txns, "Amount (ILS)")
    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    assert accts[1][sheet.FINANCE_ACCOUNTS_COLUMNS.index("Balance Snapshot")] == 1234.5


# ---------------------------------------------------------------------------
# lib/sheet.upsert_rows — direct unit (seed-safety gate)
# ---------------------------------------------------------------------------
def test_upsert_rows_skips_without_live_or_path(tmp_path, monkeypatch):
    # No path + not live → must not write anything (won't touch the seed).
    monkeypatch.setattr(sheet, "is_live", lambda: False)
    sheet.upsert_rows("Whatever", ["Account Name", "Balance Snapshot"],
                      [{"Account Name": "X", "Balance Snapshot": 1}],
                      key_column="Account Name")   # path=None → no-op, no crash


# ---------------------------------------------------------------------------
# Schema contract — column ORDER is load-bearing (review S3, D-052)
# ---------------------------------------------------------------------------
def test_transactions_column_order_is_load_bearing():
    # The seed's Finance-Budget actuals are SUMIFS over Date(A)/Amount(D)/
    # Category(E). A reorder here silently breaks the live budget formulas —
    # pin it so that can't happen without a failing test.
    cols = sheet.FINANCE_TRANSACTIONS_COLUMNS
    assert cols[0] == "Date"          # column A
    assert cols[3] == "Amount (ILS)"  # column D
    assert cols[4] == "Category"      # column E


def test_upsert_creates_accounts_tab_when_absent(tmp_path):
    # The new-tab branch of upsert_rows (no pre-seeded Finance-Accounts).
    sp = _sheet(tmp_path)   # only a Placeholder tab exists
    fin.run(csv_dir=_csv(tmp_path), sheet_path=sp, today=TODAY, now=NOW)
    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    assert accts[0] == sheet.FINANCE_ACCOUNTS_COLUMNS   # header created
    assert len(accts) - 1 == 2


def test_imported_at_is_populated_from_now(tmp_path):
    sp = _sheet(tmp_path)
    fin.run(csv_dir=_csv(tmp_path), sheet_path=sp, today=TODAY, now=NOW)
    txns = _rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)
    assert all(v == NOW.isoformat(timespec="seconds")
               for v in _col(txns, "Imported-At"))


def test_multiple_provider_csvs_merge_in_one_run(tmp_path):
    d = _csv(tmp_path)   # mizrahi_… → MIZ-0001, MIZ-0777
    (d / "max_2026-06-17.csv").write_text(
        "account,balance,date,identifier,amount,description\n"
        "MAX-1234,,2026-06-15,maxid1,-150.00,SHOP\n", encoding="utf-8")
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=d, sheet_path=sp, today=TODAY, now=NOW)
    assert res.accounts == 3   # MIZ-0001, MIZ-0777, MAX-1234
    accts = _rows(sp, cfg.FINANCE_ACCOUNTS_TAB)
    max_row = [r for r in accts[1:] if r[0] == "MAX-1234"][0]
    assert max_row[sheet.FINANCE_ACCOUNTS_COLUMNS.index("Type")] == "card"


# ---------------------------------------------------------------------------
# Categorization — on-box rules + DeepSeek gap-fill (M6.4, §8.6; D-050/051)
# ---------------------------------------------------------------------------
from automation.lib import categorize  # noqa: E402
from automation.lib import llm  # noqa: E402


def test_rules_engine_maps_known_merchants():
    rules = categorize.load_rules()
    assert categorize.apply_rules("SHUFERSAL DEAL TLV", rules) == "Groceries"
    assert categorize.apply_rules("פז חיפה דרום", rules) == "Transport"
    # Ordering is load-bearing: SUPERPHARM must resolve to Health, not Groceries.
    assert categorize.apply_rules("SUPERPHARM 123", rules) == "Health"
    assert categorize.apply_rules("totally unknown vendor", rules) is None


def test_rules_vocabulary_is_distinct_and_seeded():
    vocab = categorize.vocabulary(categorize.load_rules())
    assert {"Groceries", "Health", "Transport"} <= set(vocab)
    assert len(vocab) == len(set(vocab))            # no dupes — the LLM vocab


def test_missing_rules_file_degrades_quiet(tmp_path):
    # No file → rules engine no-ops (returns []), categorize leaves blanks.
    txns = [{"Description": "SHUFERSAL", "Amount (ILS)": -10,
             "Category": "", "Cat-Source": ""}]
    categorize.categorize_transactions(
        txns, allow_llm=False, rules_path=tmp_path / "nope.csv")
    assert txns[0]["Category"] == "" and txns[0]["Cat-Source"] == ""


def test_unknown_stays_blank_without_llm(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    txns = [{"Description": "ZZZ MYSTERY", "Amount (ILS)": -10,
             "Category": "", "Cat-Source": ""}]
    categorize.categorize_transactions(txns, allow_llm=True)   # key-less → rules only
    assert txns[0]["Category"] == "" and txns[0]["Cat-Source"] == ""


def test_gapfill_sends_only_description_and_amount(monkeypatch):
    """§8.6 privacy: the gap-fill prompt carries description + amount only —
    never the account, the Txn-ID, or any other field of the row."""
    seen = {}

    def fake_complete(prompt, **kw):
        seen["prompt"] = prompt
        seen["system"] = kw.get("system", "")
        return '{"results":[{"i":0,"category":"Shopping"}]}'

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete", fake_complete)
    txns = [{
        "Date": "2026-06-15", "Account": "MIZ-SECRET-9999",
        "Description": "MYSTERY VENDOR QX", "Amount (ILS)": -54.30,
        "Category": "", "Cat-Source": "",
        "Txn-ID": "secret-identifier-123", "Imported-At": "z",
    }]
    categorize.categorize_transactions(txns, allow_llm=True)
    assert txns[0]["Category"] == "Shopping" and txns[0]["Cat-Source"] == "llm"
    blob = seen["prompt"] + seen["system"]
    assert "MYSTERY VENDOR QX" in blob          # description: allowed
    assert "54.3" in blob                        # amount: allowed
    assert "MIZ-SECRET-9999" not in blob         # account: NEVER leaves the box
    assert "secret-identifier-123" not in blob   # Txn-ID: NEVER leaves the box


def test_gapfill_rejects_offvocab_answer(monkeypatch):
    # A category not in the rules vocab is dropped — the txn stays blank.
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete",
                        lambda p, **k: '{"results":[{"i":0,"category":"Crypto"}]}')
    txns = [{"Description": "ZZZ MYSTERY", "Amount (ILS)": -10,
             "Category": "", "Cat-Source": ""}]
    categorize.categorize_transactions(txns, allow_llm=True)
    assert txns[0]["Category"] == "" and txns[0]["Cat-Source"] == ""


# ---------------------------------------------------------------------------
# Budget reconciliation — the SUMIFS landmine (M6.4 build note; D-050)
# ---------------------------------------------------------------------------
def test_seed_budget_uses_text_prefix_not_serial_sumifs():
    """The landmine: a serial DATE() window over the RAW ISO-text Date column
    reads ₪0. Pin the seed's actuals to the locale-independent text-prefix form
    so the serial form can't silently return, and pin the MoM column."""
    b = load_workbook(cfg.SHEET_PATH)[cfg.FINANCE_BUDGET_TAB]
    c2 = b["C2"].value
    assert '$I$2&"*"' in c2               # current-month TEXT prefix
    assert '">="&DATE(' not in c2         # NOT the broken serial window
    assert 'TEXT($I$1,"yyyy")&"*"' in b["F2"].value          # YTD = year prefix
    assert b["J1"].value == "Last Month (ILS)"               # MoM column present
    assert b["I3"].value == '=TEXT(EDATE($I$1,-1),"yyyy-mm")'  # prev-month tag


def test_text_prefix_month_window_sums_iso_text_dates():
    """Prove the LOGIC the SUMIFS encodes works on the ISO-TEXT dates ingest
    writes (openpyxl can't evaluate formulas; live evaluation is the M6.3
    check). This is the value that read ₪0 before the fix."""
    txns = [
        {"Date": "2026-06-03", "Category": "Groceries", "Amount (ILS)": -432.50},
        {"Date": "2026-06-20", "Category": "Groceries", "Amount (ILS)": -100.00},
        {"Date": "2026-05-28", "Category": "Groceries", "Amount (ILS)": -999.00},
        {"Date": "2026-06-10", "Category": "Transport", "Amount (ILS)": -280.00},
    ]

    def month_actual(cat, tag):   # mirrors -SUMIFS(D, E=cat, A like tag&"*")
        return -sum(t["Amount (ILS)"] for t in txns
                    if t["Category"] == cat and t["Date"].startswith(tag))

    assert month_actual("Groceries", "2026-06") == 532.50   # non-zero, this month
    assert month_actual("Groceries", "2026-05") == 999.00   # prev month isolated
    assert month_actual("Transport", "2026-06") == 280.00
