// scrape.js — Family inc. bank scraper (SPEC §12.2, M6; appliance edition).
//
// Ported off the attic Render/Drive build (D-031): NO googleapis, NO Drive, NO
// Render — runs as a systemd oneshot on the one VPS (D-018) and writes one CSV
// per provider to the LOCAL staging dir. automation/finance_ingest.py then reads
// those CSVs and is the only thing that writes the Sheet (D-016). Node scrapes;
// Python owns every Sheet write.
//
// Read-only by nature (the §4 "no money movement" non-goal stays absolute — the
// library reads balances + transactions, it cannot transfer).
//
// Creds: /etc/family-inc/bank_creds.json (mode 600, D-049 amendment — never in
// the repo, never logged), override path via FAMILY_INC_BANK_CREDS. Shape:
//   { "mizrahi": {"username":"…","password":"…"},
//     "max":     {"username":"…","password":"…"},
//     "cal":     {"username":"…","password":"…"} }
// A provider absent from the file is skipped with a warning (roll out one
// institution at a time). The file MISSING/unreadable is fatal (exit 1 → the
// unit fails → OnFailure fail-flag → next digest reports it).
//
// Exit contract (so the two-step unit behaves): exit 1 only when there's nothing
// to ingest (creds file missing/unreadable, or no known provider configured) —
// the unit fails and the fail-flag fires. On a PARTIAL run (some providers OK,
// some errored) we still write the good CSVs, record the failures in
// _scrape_errors.json, and exit 0 so finance_ingest.py runs on the good data and
// then fails loud on the marker (CSVs/data are never lost to a single provider's
// OTP re-challenge).
//
// VPS-only in practice: needs the bundled Chromium (puppeteer) — `npm ci` in
// this dir installs it. Not exercised by the Python test suite (no banks, no
// browser); `node --check` guards syntax.

const fs = require('fs');
const path = require('path');
const { CompanyTypes, createScraper } = require('israeli-bank-scrapers');

const CREDS_FILE = process.env.FAMILY_INC_BANK_CREDS
  || '/etc/family-inc/bank_creds.json';
const OUT_DIR = process.env.FAMILY_INC_FINANCE_DIR || '/var/lib/family-inc/finance';
const WINDOW_DAYS = parseInt(process.env.FAMILY_INC_FINANCE_WINDOW_DAYS || '45', 10);

// provider key (in bank_creds.json) → israeli-bank-scrapers company id.
const COMPANY = {
  mizrahi: CompanyTypes.mizrahi,
  max: CompanyTypes.max,
  cal: CompanyTypes.visaCal,
};

function fail(msg) {
  console.error(`[fatal] ${msg}`);
  process.exit(1);
}

function loadCreds() {
  let raw;
  try {
    raw = fs.readFileSync(CREDS_FILE, 'utf-8');
  } catch (e) {
    fail(`bank_creds.json not readable at ${CREDS_FILE}: ${e.message}`);
  }
  try {
    return JSON.parse(raw);
  } catch (e) {
    fail(`bank_creds.json is not valid JSON: ${e.message}`);
  }
}

function stamp(d) {
  // Local Y-M-D (the unit runs TZ=Asia/Jerusalem) — matches the Sheet date form
  // and the budget SUMIFS, avoids a UTC off-by-one vs toISOString.
  const x = new Date(d);
  if (isNaN(x.getTime())) return String(d).slice(0, 10);
  const y = x.getFullYear();
  const m = String(x.getMonth() + 1).padStart(2, '0');
  const day = String(x.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function csvField(v) {
  const s = v === null || v === undefined ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// result.accounts → the CSV finance_ingest.py expects:
//   account,balance,date,identifier,amount,description
// balance repeats per row; an account with no txns gets one balance-only row.
function toCsv(accounts) {
  const rows = [['account', 'balance', 'date', 'identifier', 'amount', 'description']];
  let txnCount = 0;
  for (const acct of accounts || []) {
    const bal = acct.balance === undefined || acct.balance === null ? '' : acct.balance;
    const num = acct.accountNumber || '';
    const txns = acct.txns || [];
    if (txns.length === 0) {
      rows.push([num, bal, '', '', '', '']); // keep the balance even with no txns
      continue;
    }
    for (const t of txns) {
      rows.push([num, bal, stamp(t.date), t.identifier || '', t.chargedAmount,
        t.description || '']);
      txnCount += 1;
    }
  }
  return { csv: rows.map((r) => r.map(csvField).join(',')).join('\n') + '\n', txnCount };
}

async function scrapeProvider(name, creds) {
  const scraper = createScraper({
    companyId: COMPANY[name],
    startDate: new Date(Date.now() - WINDOW_DAYS * 24 * 60 * 60 * 1000),
    combineInstallments: false,
    showBrowser: false,
    args: ['--no-sandbox', '--disable-dev-shm-usage'], // unprivileged systemd unit
  });
  const result = await scraper.scrape(creds);
  if (!result.success) {
    throw new Error(`${result.errorType}: ${result.errorMessage || ''}`.trim());
  }
  return result.accounts;
}

(async () => {
  const creds = loadCreds();
  const configured = Object.keys(COMPANY).filter(
    (n) => creds[n] && creds[n].username && creds[n].password);
  if (configured.length === 0) {
    fail(`no known provider in ${CREDS_FILE} (expected any of: ${Object.keys(COMPANY).join(', ')})`);
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const today = stamp(new Date());
  const errors = [];

  for (const name of configured) {
    try {
      const accounts = await scrapeProvider(name, creds[name]);
      const { csv, txnCount } = toCsv(accounts);
      const file = path.join(OUT_DIR, `${name}_${today}.csv`);
      fs.writeFileSync(file, csv, { encoding: 'utf-8' });
      console.log(`[ok] ${name}: ${txnCount} txn(s) → ${file}`);
    } catch (err) {
      console.error(`[fail] ${name}: ${err.message}`);
      errors.push({ provider: name, error: err.message });
    }
  }

  // The marker is how the failure reaches the digest: finance_ingest.py reads
  // it, ingests the good CSVs, then raises → unit fails → OnFailure fail-flag.
  const marker = path.join(OUT_DIR, '_scrape_errors.json');
  if (errors.length > 0) {
    fs.writeFileSync(marker, JSON.stringify({ at: new Date().toISOString(), errors }, null, 1));
    console.error(`Scrape errors recorded for: ${errors.map((e) => e.provider).join(', ')}`);
  } else if (fs.existsSync(marker)) {
    fs.rmSync(marker); // clear a stale marker from a prior partial run
  }
  // Exit 0 even on partial failure (see the exit contract above) so the ingest
  // step runs on the good CSVs and surfaces the errors loudly itself.
  process.exit(0);
})();
