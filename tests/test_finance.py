"""Tests for automation/finance_ingest.py (SPEC §12.2, M6.1; D-049/050/051).

Hermetic: a mock per-provider CSV → ingest → a tmp xlsx Sheet (explicit path,
never the live Sheet / committed seed). No banks, no Node, no network — the
Node scraper (scrape.js) is VPS-only and node-checked, not unit-tested.
Covers: CSV → Sheet, Txn-ID dedup + rerun idempotency, balance-only rows,
natural-key hash ids (the provider `identifier` is ignored — non-unique on
Mizrahi), Finance-Accounts upsert (human fields preserved),
fail-loud on missing creds / scrape-error marker, and the seed-safety gate.
"""

import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from automation import finance_ingest as fin
from automation.lib import config as cfg
from automation.lib import sheet

SCRAPE_JS = Path(__file__).resolve().parents[1] / "automation" / "finance" / "scrape.js"

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


def test_txn_id_is_natural_key_hash():
    # The provider identifier is NOT part of the key (Mizrahi reuses it across
    # distinct charges — §12.2). Same natural key → same id; a different natural
    # key (here, a different amount) → a different id. Deterministic.
    h1 = fin.txn_id("2026-06-15", -10, "X", "A")
    h2 = fin.txn_id("2026-06-15", -10, "X", "A")
    h3 = fin.txn_id("2026-06-15", -11, "X", "A")
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
    # All Txn-IDs are natural-key hashes — the provider `identifier` (abc123 on
    # the first row) is ignored, since it is not unique per transaction (§12.2).
    assert all(str(t).startswith("h:") for t in _col(txns, "Txn-ID"))
    assert len(set(_col(txns, "Txn-ID"))) == 3          # 3 distinct natural keys
    # M6.4: the on-box rules engine categorizes at ingest (no LLM key in tests
    # → rules only). SHUFERSAL→Groceries, SUPERPHARM→Health, PAZ→Transport.
    cat_by_desc = dict(zip(_col(txns, "Description"), _col(txns, "Category")))
    assert cat_by_desc["SHUFERSAL DEAL"] == "Groceries"
    assert cat_by_desc["SUPERPHARM"] == "Health"
    assert cat_by_desc["PAZ GAS"] == "Transport"
    assert set(_col(txns, "Cat-Source")) == {"rules"}
    assert "abc123" not in _col(txns, "Txn-ID")         # identifier is not the key
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


def test_natural_key_collision_drops_second_charge_as_phantom_dup(tmp_path):
    """Accepted floor (finance_ingest.py txn_id docstring): two genuinely distinct
    same-day charges with an identical account+amount+description hash to one
    Txn-ID, so the dedup drops the second as a phantom dup. This LOCKS that
    behavior (it is silent data loss) — recovering both needs a richer key + a PO
    call. Rare for a bank; re-verify per card before trusting a provider field."""
    text = ("account,balance,date,identifier,amount,description\n"
            "MIZ-0001,9000,2026-06-15,,-12.00,COFFEE KIOSK\n"
            "MIZ-0001,9000,2026-06-15,,-12.00,COFFEE KIOSK\n")   # two real ₪12 coffees
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=_csv(tmp_path, text), sheet_path=sp, today=TODAY, now=NOW)
    # finance-ingest#3: the in-batch collision is a distinct counter, NOT
    # mislabeled "already on the tab" (txns_seen).
    assert res.txns_new == 1 and res.txns_phantom_dup == 1 and res.txns_seen == 0
    assert len(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)) - 1 == 1


def test_distinct_identifiers_do_not_rescue_same_natural_key(tmp_path):
    """Inverts the pre-2026-06-19 behavior: distinct provider identifiers no
    longer keep two same-natural-key rows apart — `identifier` is out of the key
    (§12.2), so the second still drops. We stopped trusting identifier because
    Mizrahi reuses it; this same-day-collision merge is the symmetric cost."""
    text = ("account,balance,date,identifier,amount,description\n"
            "MIZ-0001,9000,2026-06-15,txn-a,-12.00,COFFEE KIOSK\n"
            "MIZ-0001,9000,2026-06-15,txn-b,-12.00,COFFEE KIOSK\n")
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=_csv(tmp_path, text), sheet_path=sp, today=TODAY, now=NOW)
    assert res.txns_new == 1 and res.txns_phantom_dup == 1
    assert all(str(t).startswith("h:")
               for t in _col(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB), "Txn-ID"))


def test_reused_identifier_across_distinct_charges_keeps_all(tmp_path):
    """Regression for the 2026-06-19 live data-loss bug: israeli-bank-scrapers
    hands Mizrahi a NON-unique identifier (one id shared across many distinct
    charges). The old `if identifier: return identifier` collapsed 96 real rows
    to 26 on the live tab. With the natural-key Txn-ID, distinct charges that
    happen to share an identifier are all kept (would FAIL on the old code:
    txns_new == 1, phantom_dup == 2)."""
    text = ("account,balance,date,identifier,amount,description\n"
            "MIZ-0001,9000,2026-06-10,dup-ref,-12.00,COFFEE\n"
            "MIZ-0001,9000,2026-06-11,dup-ref,-50.00,GROCERY\n"
            "MIZ-0001,9000,2026-06-12,dup-ref,-9.90,BAKERY\n")   # 3 distinct, 1 id
    sp = _sheet(tmp_path)
    res = fin.run(csv_dir=_csv(tmp_path, text), sheet_path=sp, today=TODAY, now=NOW)
    assert res.txns_new == 3 and res.txns_phantom_dup == 0       # all kept, no false dup
    assert len(_rows(sp, cfg.FINANCE_TRANSACTIONS_TAB)) - 1 == 3


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


def test_rules_vocab_within_budget_categories():
    """GAP-1 (single highest-value audit fix): every category the rules engine /
    LLM may emit MUST be a Finance-Budget row, or that category's actuals SUMIFS
    reads ₪0 and the spend is invisible. 'Dining'→'Dining out' is now aligned.
    KNOWN-PENDING — Shanee's budget-vocab migration is the authority: Fees/Income/
    Shopping have no budget row yet, held as an explicit allow-list so this test
    still catches any NEW drift and the gap can't be forgotten. When Shanee maps
    them (add rows, or remap the rules), shrink `pending` toward empty."""
    rules_vocab = set(categorize.vocabulary(categorize.load_rules()))
    budget = {r[0] for r in _rows(cfg.SHEET_PATH, cfg.FINANCE_BUDGET_TAB)[1:]
              if r[0] and r[0] != "TOTAL"}
    pending = {"Fees", "Income", "Shopping"}        # GAP-1: awaiting Shanee's budget rows
    unmapped = rules_vocab - budget - pending
    assert not unmapped, f"rules emit categories with no Finance-Budget row: {unmapped}"
    assert pending <= rules_vocab                   # keep the allow-list honest (no stale entries)
    assert "Dining out" in rules_vocab and "Dining" not in rules_vocab   # the GAP-1 rename


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


def test_gapfill_chunks_so_large_import_is_fully_categorized(monkeypatch):
    """B5: a rules-miss batch larger than GAPFILL_MAX_BATCH must be FULLY
    categorized before the write — chunk-looped, not truncated at the per-prompt
    cap. A blank-Category row keeps its real Txn-ID and is then excluded from
    dedup forever (never re-presented to the LLM), so an overflow left blank was
    permanent data loss on the first 45-day backlog."""
    import json
    budgets = []

    def fake_complete(prompt, **kw):
        budgets.append(kw.get("max_tokens"))
        # Cover every within-chunk index (a chunk is <= GAPFILL_MAX_BATCH rows).
        return json.dumps({"results": [{"i": i, "category": "Shopping"}
                                       for i in range(categorize.GAPFILL_MAX_BATCH)]})

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete", fake_complete)
    n = categorize.GAPFILL_MAX_BATCH * 2 + 5    # 165 — well over one prompt's cap
    txns = [{"Description": f"ZZZ MYSTERY {i}", "Amount (ILS)": -10,
             "Category": "", "Cat-Source": ""} for i in range(n)]
    categorize.categorize_transactions(txns, allow_llm=True)
    assert all(t["Category"] == "Shopping" and t["Cat-Source"] == "llm" for t in txns)
    assert len(budgets) == 3                     # ceil(165/80) chunks, not one truncated call
    # A full 80-row chunk's reply (~1.5k tokens) must not be truncated by a fixed
    # small cap — the reply budget scales with the chunk (else the whole chunk
    # parses to {} and lands blank: the B5 data-loss in disguise).
    assert max(budgets) >= categorize.GAPFILL_MAX_BATCH * 16


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
    writes. This Python re-implementation is DELIBERATE (tests-quality#3 / GAP-6):
    the seed backend reads formula cells as None offline (lib/sheet XlsxBackend
    data_only caveat), so the real SUMIFS can't be evaluated here — it's verified
    live at M6.3. This is the value that read ₪0 before the fix."""
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


# ---------------------------------------------------------------------------
# scrape.js — the Node scraper is VPS-only (banks + bundled Chromium), so these
# guard only the parts that need neither: it parses, and its argv/fail-loud
# contract holds. The deps (israeli-bank-scrapers, puppeteer) are required
# lazily, so these run green without `npm ci` having been done.
# ---------------------------------------------------------------------------
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node not installed (scrape.js is VPS-only)"
)


def _node(*args, env=None):
    return subprocess.run(
        ["node", str(SCRAPE_JS), *args],
        capture_output=True, text=True, env=env, timeout=30,
    )


@requires_node
def test_scrape_js_node_check_parses():
    """The syntax guard the module docstring promises (no test existed before)."""
    res = subprocess.run(
        ["node", "--check", str(SCRAPE_JS)], capture_output=True, text=True, timeout=30
    )
    assert res.returncode == 0, res.stderr


@requires_node
@pytest.mark.parametrize("args", [["--auth"], ["--auth", "bogus"]])
def test_scrape_js_auth_usage_guard(args):
    """`--auth` without a known provider exits 2 with usage and loads no Chromium
    (the guard runs before puppeteer is required, so it passes with no node_modules)."""
    res = _node(*args)
    assert res.returncode == 2
    assert "usage: node scrape.js --auth <provider>" in res.stderr
    assert "mizrahi, max, cal" in res.stderr


@requires_node
def test_scrape_js_auth_mizrahi_is_noop():
    """Mizrahi is password-only — `--auth mizrahi` is a clean no-op (exit 0), not a
    browser launch; only Max/Cal persist a device-trust profile."""
    res = _node("--auth", "mizrahi")
    assert res.returncode == 0
    assert "password-only" in res.stdout


@requires_node
@pytest.mark.parametrize("args", [["--foo"], ["mizrahi"], ["--auth", "max", "extra"]])
def test_scrape_js_rejects_unknown_invocation(args):
    """A typo or stray positional must fail loud (exit 2), never silently take the
    daily-scrape branch — fail-loud on the hand-typed `--auth` command."""
    res = _node(*args)
    assert res.returncode == 2
    assert "usage: node scrape.js" in res.stderr


@requires_node
def test_scrape_js_missing_creds_fails_loud():
    """A daily run with no creds file fails loud (exit 1) — the unit-fails →
    fail-flag contract. Lazy require means this hits loadCreds() before the lib."""
    import os
    env = {**os.environ, "FAMILY_INC_BANK_CREDS": "/nonexistent/bank_creds.json"}
    res = _node(env=env)
    assert res.returncode == 1
    assert "[fatal]" in res.stderr and "bank_creds.json" in res.stderr
