// scrape.js — Israeli bank scraper runner for Family_OS
//
// Pulls last 30 days of transactions from one Israeli bank and writes a
// CSV into Finance_CSVs/ so the existing import pipeline ingests it
// without changes. Filename pattern: <bank>_<YYYY-MM-DD>.csv
//
// Setup:
//   1. npm install israeli-bank-scrapers keytar dayjs
//   2. Store the password in macOS Keychain under service
//      "family-inc-hapoalim" with account = your bank username.
//   3. Set env BANK_USERNAME when invoking (launchd plist or shell).
//
// Schedule via ~/Library/LaunchAgents/com.familyinc.bankscraper.plist
// (see 01_Israeli_Bank_Scrapers.md).

const { CompanyTypes, createScraper } = require('israeli-bank-scrapers');
const keytar = require('keytar');
const dayjs = require('dayjs');
const fs = require('fs');
const path = require('path');

// ----- config -----
const COMPANY = CompanyTypes.hapoalim; // .leumi | .discount | .max | .visaCal | .isracard
const KEYCHAIN_SERVICE = 'family-inc-hapoalim';
const USERNAME = process.env.BANK_USERNAME;
const LOOKBACK_DAYS = 30;
const OUT_DIR = path.join(
  process.env.HOME,
  'Documents/Claude/Family Inc/Finance_CSVs'
);
// ------------------

async function main() {
  if (!USERNAME) throw new Error('BANK_USERNAME env var is required');

  const password = await keytar.getPassword(KEYCHAIN_SERVICE, USERNAME);
  if (!password) {
    throw new Error(
      `No password in Keychain for service="${KEYCHAIN_SERVICE}" account="${USERNAME}"`
    );
  }

  const scraper = createScraper({
    companyId: COMPANY,
    startDate: dayjs().subtract(LOOKBACK_DAYS, 'day').toDate(),
    combineInstallments: false,
    showBrowser: false,
    defaultTimeout: 60000,
  });

  const credentials = { userCode: USERNAME, password };
  // Leumi wants { username, password } instead — adjust per provider.

  const result = await scraper.scrape(credentials);
  if (!result.success) {
    console.error('Scrape failed:', result.errorType, result.errorMessage);
    process.exit(1);
  }

  const rows = [['date', 'description', 'amount', 'account', 'category']];
  let total = 0;
  for (const account of result.accounts) {
    for (const txn of account.txns) {
      rows.push([
        dayjs(txn.date).format('YYYY-MM-DD'),
        (txn.description || '').replace(/,/g, ' ').trim(),
        txn.chargedAmount,
        account.accountNumber,
        '', // category — filled by Sheets formula
      ]);
      total += 1;
    }
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const stamp = dayjs().format('YYYY-MM-DD');
  const outPath = path.join(OUT_DIR, `hapoalim_${stamp}.csv`);
  fs.writeFileSync(outPath, rows.map((r) => r.join(',')).join('\n'));
  console.log(`Wrote ${outPath} rows: ${total}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
