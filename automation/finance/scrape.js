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
// OTP re-challenge). Exit 2 = a usage error (an unrecognized invocation, or
// `--auth` without a valid provider) — no scrape attempted; operator-only, the
// systemd unit passes no args so it never sees exit 2.
//
// Two run modes (SPEC §12.2 auth model):
//   • default (no args) — the daily headless oneshot the timer fires.
//   • `--auth <provider>` — a one-time HEADED login the operator drives by hand
//     to clear an OTP / device-verification challenge. Mizrahi is password-only
//     and needs none; Max + Cal (visaCal) re-challenge a new browser, and the
//     library (israeli-bank-scrapers 6.7.3) has NO programmatic OTP entry for
//     them — their credentials are username+password only and they do not
//     implement the OneZero-style triggerTwoFactorAuth/otpCodeRetriever path.
//     So an OTP code cannot be typed in via the library; instead Max + Cal
//     (PERSIST_PROFILE) persist a browser PROFILE (Chromium --user-data-dir) and
//     the operator completes the challenge once in a headed session. The portal
//     then trusts that profile (a long-lived "remembered device" cookie), so the
//     daily headless run reuses the same profile and is not re-challenged. This
//     is the SPEC §12.2 "persist a login session to cut repeat OTPs" hardening.
//     The headed step needs an X display the operator can see — on the headless
//     VPS that is xvfb + x11vnc over an SSH tunnel (deploy/FINANCE.md §4).
//     If device-trust ever expires (re-challenge returns), re-run `--auth`.
//
// Why a persistent profile and not `scraper.scrape()` headed for auth: the
// library's terminate() closes the page/browser the moment login resolves, so
// it would close on the operator mid-OTP. Auth mode therefore drives its OWN
// puppeteer browser (headed, same profile dir) and waits on the operator.
//
// Why the profile rides on `args` and not a userDataDir option: createScraper()
// only forwards `args` to puppeteer.launch — but puppeteer honors a
// `--user-data-dir=` passed in args (it only fabricates a temp profile when
// none is present), so the daily path gets the persistent profile for free.
//
// VPS-only in practice: needs the bundled Chromium (puppeteer) — `npm ci` in
// this dir installs it. Not exercised by the Python test suite (no banks, no
// browser); `node --check` + an `--auth` usage-guard test guard it.

const fs = require('fs');
const path = require('path');
// israeli-bank-scrapers and puppeteer are required lazily (inside the run paths)
// so a bad invocation (e.g. `--auth typo`) fails its usage check instantly
// without loading Chromium, and the file stays node-checkable without node_modules.

const CREDS_FILE = process.env.FAMILY_INC_BANK_CREDS
  || '/etc/family-inc/bank_creds.json';
const OUT_DIR = process.env.FAMILY_INC_FINANCE_DIR || '/var/lib/family-inc/finance';
// Fixed lookback (NOT since-last-success): Txn-ID dedup on ingest makes an
// overlapping rerun idempotent, so a fixed window needs no persisted cursor
// (SPEC §12.2). 45d covers a missed run or two; widen via the env var if needed.
const WINDOW_DAYS = parseInt(process.env.FAMILY_INC_FINANCE_WINDOW_DAYS || '45', 10);

// provider keys (as they appear in bank_creds.json). The israeli-bank-scrapers
// company id is resolved lazily in companyId() so a usage check needs no library.
const PROVIDERS = ['mizrahi', 'max', 'cal'];
const companyId = (name) => {
  const { CompanyTypes } = require('israeli-bank-scrapers');
  return { mizrahi: CompanyTypes.mizrahi, max: CompanyTypes.max, cal: CompanyTypes.visaCal }[name];
};

// Only the providers that device-trust-challenge persist a Chromium profile.
// Mizrahi is password-only — it logs in fresh each run with no re-challenge, so a
// persistent profile would buy it nothing and only add an on-disk bank-session
// cookie surface; it stays ephemeral (a fresh temp profile per run, as before).
const PERSIST_PROFILE = ['max', 'cal'];
// Per-provider persistent Chromium profile (the device-trust cookie jar). Kept
// under the staging dir so it shares the unit's StateDirectory ownership.
const PROFILES_DIR = path.join(OUT_DIR, 'profiles');
const profileDir = (name) => path.join(PROFILES_DIR, name);

// `--auth` won't sit on a live banking session forever: if the operator doesn't
// press ENTER within this window the browser is closed and the run exits non-zero.
const AUTH_TIMEOUT_MS = parseInt(process.env.FAMILY_INC_AUTH_TIMEOUT_MS || `${20 * 60 * 1000}`, 10);

// Where `--auth` opens the headed browser so the operator can log in once. These
// mirror the library's own loginUrl constants (6.7.3) and are a convenience only
// — the profile is what matters, so if a portal moves its login the operator can
// navigate there by hand; reaching a logged-in state in this profile is the goal.
const LOGIN_URLS = {
  mizrahi: 'https://www.mizrahi-tefahot.co.il/login/index.html#/auth-page-he',
  max: 'https://www.max.co.il/login',
  cal: 'https://www.cal-online.co.il/',
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
  const args = ['--no-sandbox', '--disable-dev-shm-usage']; // unprivileged systemd unit
  // Max/Cal reuse the persistent device-trust profile so a once-authorized card is
  // not re-challenged (puppeteer honors a --user-data-dir passed via args). Mizrahi
  // stays ephemeral — no profile, no stored session (PERSIST_PROFILE).
  if (PERSIST_PROFILE.includes(name)) {
    const dir = profileDir(name);
    fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
    args.push(`--user-data-dir=${dir}`);
  }
  const { createScraper } = require('israeli-bank-scrapers');
  const scraper = createScraper({
    companyId: companyId(name),
    startDate: new Date(Date.now() - WINDOW_DAYS * 24 * 60 * 60 * 1000),
    combineInstallments: false, // stable per-charge ids: combined rows mutate
                                // their amount as installments post → hash churn

    showBrowser: false,   // headless daily run. An OTP / device re-challenge here
                          // still fails loud (next digest); the remedy is a
                          // one-time `--auth <provider>` headed login (SPEC §12.2).
    args,
  });
  const result = await scraper.scrape(creds);
  if (!result.success) {
    throw new Error(`${result.errorType}: ${result.errorMessage || ''}`.trim());
  }
  return result.accounts;
}

async function dailyRun() {
  const creds = loadCreds();
  const configured = PROVIDERS.filter(
    (n) => creds[n] && creds[n].username && creds[n].password);
  if (configured.length === 0) {
    fail(`no known provider in ${CREDS_FILE} (expected any of: ${PROVIDERS.join(', ')})`);
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
}

// Block until the operator presses ENTER, or reject after timeoutMs so a live
// banking session is never left open unattended on the VNC (the finally in
// authMode then closes the browser).
function waitForEnter(timeoutMs) {
  return new Promise((resolve, reject) => {
    process.stdin.resume();
    const onData = () => { cleanup(); resolve(); };
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error(`no ENTER within ${Math.round(timeoutMs / 60000)} min — closing the browser; re-run --auth when ready`));
    }, timeoutMs);
    function cleanup() {
      clearTimeout(timer);
      process.stdin.removeListener('data', onData);
      process.stdin.pause();
    }
    process.stdin.once('data', onData);
  });
}

// One-time headed login to bake the device-trust cookie into the provider's
// persistent profile. Drives its OWN puppeteer (NOT scraper.scrape(), whose
// terminate() would close the page on the operator) and waits for the human.
// Needs an X display (xvfb + x11vnc on the VPS — deploy/FINANCE.md §4). Creds
// are NOT read here: the operator types them into the browser, so `--auth` works
// before bank_creds.json is filled and never logs a secret.
async function authMode(provider) {
  if (!provider || !PROVIDERS.includes(provider)) {
    console.error(`usage: node scrape.js --auth <provider>   (one of: ${PROVIDERS.join(', ')})`);
    process.exit(2);
  }
  if (!PERSIST_PROFILE.includes(provider)) {
    // Mizrahi (password-only) has no device-trust to bake — a no-op, said plainly.
    console.log(`[auth] ${provider} is password-only — no device-trust login needed; just run the daily unit.`);
    process.exit(0);
  }
  const dir = profileDir(provider);
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  // Refuse to open the profile if a scrape is already holding it (fresh Chrome
  // SingletonLock) — racing the 06:00 daily run can corrupt the trust cookie.
  // The runbook stops the timer first (FINANCE.md §4a); this is the backstop.
  const lock = path.join(dir, 'SingletonLock');
  try {
    const ageMs = Date.now() - fs.lstatSync(lock).mtimeMs; // lstat: the lock is a symlink
    if (ageMs < 120000) {
      fail(`profile ${dir} has a fresh SingletonLock (${Math.round(ageMs / 1000)}s old) — a finance run may be using it. Stop family-finance.timer (FINANCE.md §4a), then retry.`);
    }
  } catch (e) {
    if (e.code !== 'ENOENT') throw e; // no lock → good to go
  }
  // Lazy-require so the usage guard above (and its test) never loads Chromium.
  const puppeteer = require('puppeteer');
  console.log(`[auth] ${provider}: opening a HEADED browser (profile: ${dir}).`);
  console.log('[auth] this needs an X display — run under xvfb-run and view via VNC.');
  const browser = await puppeteer.launch({
    headless: false,
    args: ['--no-sandbox', '--disable-dev-shm-usage', `--user-data-dir=${dir}`],
  });
  try {
    const page = (await browser.pages())[0] || await browser.newPage();
    await page.goto(LOGIN_URLS[provider], { waitUntil: 'load' })
      .catch((e) => console.error(`[auth] navigation warning (log in manually): ${e.message}`));
    console.log('\n=== ACTION REQUIRED ===');
    console.log(`Log into ${provider} in the browser, complete the SMS/OTP device-trust step`);
    console.log(`until you reach the account dashboard, then return here and press ENTER (within ${Math.round(AUTH_TIMEOUT_MS / 60000)} min).`);
    await waitForEnter(AUTH_TIMEOUT_MS);
  } finally {
    await browser.close();
  }
  console.log(`[auth] done — device-trust persisted in ${dir}.`);
  console.log('[auth] verify a headless run now succeeds: sudo systemctl start family-finance.service');
  process.exit(0);
}

// Dispatch on the exact shape — never silently fall through to a daily scrape on
// a typo (`--auht max`, a stray positional), which would run the wrong mode on the
// hand-typed `--auth` command this feature exists for. No args → daily oneshot;
// `--auth <provider>` → headed auth; anything else → loud usage error (exit 2).
const argv = process.argv.slice(2);
if (argv.length === 0) {
  dailyRun().catch((e) => fail(e.message));
} else if (argv[0] === '--auth' && argv.length <= 2) {
  // argv[1] may be undefined → authMode's own usage guard handles a missing/bad provider.
  authMode(argv[1]).catch((e) => fail(`auth: ${e.message}`));
} else {
  console.error(`usage: node scrape.js [--auth <provider>]   (provider one of: ${PROVIDERS.join(', ')})`);
  process.exit(2);
}
