// scrape.js — Family inc. bank scraper (Render cloud cron edition)
//
// Pulls last 30 days of transactions for every configured provider and
// uploads one CSV per provider to the Finance_CSVs folder on Google Drive,
// named `<bank>_<YYYY-MM-DD>.csv` — the exact pattern the existing ingest
// into Finance—Transactions expects. DO NOT change the filename pattern.
//
// Decision 2026-06-03 (Adar): providers = Mizrahi + Max + Cal; runtime = Render
// cron (not launchd). Creds live as Render env vars — see README.md.
//
// Required env vars (set in Render dashboard, never in source):
//   MIZRAHI_USERNAME / MIZRAHI_PASSWORD
//   MAX_USERNAME     / MAX_PASSWORD
//   CAL_USERNAME     / CAL_PASSWORD
//   GOOGLE_SERVICE_ACCOUNT_JSON   — full JSON key of the Drive service account
//   FINANCE_CSV_FOLDER_ID         — Drive folder ID of Finance_CSVs
//
// A provider with missing env vars is skipped with a warning (lets you roll
// out one institution at a time). Any provider *failure* exits non-zero so
// Render marks the run failed and emails Adar.

const { CompanyTypes, createScraper } = require('israeli-bank-scrapers');
const { google } = require('googleapis');
const dayjs = require('dayjs');
const fs = require('fs');
const os = require('os');
const path = require('path');

const PROVIDERS = [
  {
    name: 'mizrahi',
    companyId: CompanyTypes.mizrahi,
    credentials: () =>
      env('MIZRAHI_USERNAME') && env('MIZRAHI_PASSWORD')
        ? { username: env('MIZRAHI_USERNAME'), password: env('MIZRAHI_PASSWORD') }
        : null,
  },
  {
    name: 'max',
    companyId: CompanyTypes.max,
    credentials: () =>
      env('MAX_USERNAME') && env('MAX_PASSWORD')
        ? { username: env('MAX_USERNAME'), password: env('MAX_PASSWORD') }
        : null,
  },
  {
    name: 'cal',
    companyId: CompanyTypes.visaCal,
    credentials: () =>
      env('CAL_USERNAME') && env('CAL_PASSWORD')
        ? { username: env('CAL_USERNAME'), password: env('CAL_PASSWORD') }
        : null,
  },
];

function env(key) {
  return process.env[key] || '';
}

function toCsv(accounts) {
  const rows = [['date', 'description', 'amount', 'account', 'category']];
  for (const account of accounts) {
    for (const txn of account.txns) {
      rows.push([
        dayjs(txn.date).format('YYYY-MM-DD'),
        (txn.description || '').replace(/,/g, ' '),
        txn.chargedAmount,
        account.accountNumber,
        '', // category — filled downstream by hebrew_categorizer / Sheets
      ]);
    }
  }
  return { csv: rows.map((r) => r.join(',')).join('\n'), count: rows.length - 1 };
}

async function driveClient() {
  const raw = env('GOOGLE_SERVICE_ACCOUNT_JSON');
  if (!raw) throw new Error('GOOGLE_SERVICE_ACCOUNT_JSON not set');
  const key = JSON.parse(raw);
  const auth = new google.auth.GoogleAuth({
    credentials: key,
    scopes: ['https://www.googleapis.com/auth/drive.file'],
  });
  return google.drive({ version: 'v3', auth });
}

async function uploadCsv(drive, filename, csvBody) {
  const folderId = env('FINANCE_CSV_FOLDER_ID');
  if (!folderId) throw new Error('FINANCE_CSV_FOLDER_ID not set');

  // Idempotent: if today's file already exists (rerun), overwrite it.
  const existing = await drive.files.list({
    q: `name = '${filename}' and '${folderId}' in parents and trashed = false`,
    fields: 'files(id)',
  });

  const media = { mimeType: 'text/csv', body: csvBody };
  if (existing.data.files.length > 0) {
    await drive.files.update({ fileId: existing.data.files[0].id, media });
    return 'updated';
  }
  await drive.files.create({
    requestBody: { name: filename, parents: [folderId] },
    media,
    fields: 'id',
  });
  return 'created';
}

async function scrapeProvider(provider) {
  const credentials = provider.credentials();
  if (!credentials) {
    console.warn(`[skip] ${provider.name}: env vars not set`);
    return { name: provider.name, skipped: true };
  }

  const scraper = createScraper({
    companyId: provider.companyId,
    startDate: dayjs().subtract(30, 'day').toDate(),
    combineInstallments: false,
    showBrowser: false,
    args: ['--no-sandbox', '--disable-setuid-sandbox'], // required on Render
  });

  const result = await scraper.scrape(credentials);
  if (!result.success) {
    throw new Error(
      `${provider.name} scrape failed: ${result.errorType} ${result.errorMessage}`
    );
  }
  return { name: provider.name, accounts: result.accounts };
}

(async () => {
  const stamp = dayjs().format('YYYY-MM-DD');
  const drive = await driveClient();
  const failures = [];

  for (const provider of PROVIDERS) {
    try {
      const result = await scrapeProvider(provider);
      if (result.skipped) continue;

      const { csv, count } = toCsv(result.accounts);
      const filename = `${provider.name}_${stamp}.csv`;

      // Keep a local copy in the ephemeral container for Render log debugging.
      const tmpPath = path.join(os.tmpdir(), filename);
      fs.writeFileSync(tmpPath, csv);

      const action = await uploadCsv(drive, filename, csv);
      console.log(`[ok] ${provider.name}: ${count} txns → Drive (${action})`);
    } catch (err) {
      console.error(`[fail] ${provider.name}:`, err.message);
      failures.push(provider.name);
    }
  }

  if (failures.length > 0) {
    console.error('Failed providers:', failures.join(', '));
    process.exit(1);
  }
  console.log('All providers done.');
})();
