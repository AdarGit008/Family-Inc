# 01 — Israeli Bank Scrapers

**Time budget: ~2h.**

> **Decision 2026-06-03 (Adar):** providers = **Mizrahi + Max + Cal** (not Hapoalim/Leumi); runtime = **Render cloud cron** (not launchd). The multi-provider script, `render.yaml` blueprint, and a 10-step setup checklist live in `../Automation/bank-scraper/`. Output goes to the **Drive** `Finance_CSVs` folder via a Google service account, keeping the `<bank>_<YYYY-MM-DD>.csv` ingest contract untouched. Steps 2–4 below (Keychain + launchd) are the superseded local path, kept for reference / fallback.
>
> **Tradeoff accepted:** Render env vars are weaker custody than macOS Keychain; accepted for always-on reliability (laptop-asleep misses were the failure mode). Mitigation: dedicated service account scoped to `drive.file`, Render failure emails on.

## Why this matters

Today every transaction reaches `Family_OS` through a manual CSV drop from the bank portal. That's the single biggest weekly chore. `eshaham/israeli-bank-scrapers` is a maintained Node library that logs in headless and exports the same CSV — on a schedule. Killing the manual drop unlocks weekday cashflow visibility in the PWA briefing.

See `../06_Lift_Recommendations_2026-05-30.md` for why this ranks #1 on the high-leverage list.

## Prereqs

- macOS with Node 20+ (`node -v` → v20.x). If missing: `brew install node@20`.
- One Israeli bank account (Hapoalim or Leumi for first pass — both well-supported).
- Optional but recommended: a free [Render](https://render.com) account for cloud cron later. For v1, macOS launchd is fine.

## Step 1 — Install

```bash
cd "$HOME/Documents/Claude/Family Inc/Automation"
mkdir -p bank-scraper && cd bank-scraper
npm init -y
npm install israeli-bank-scrapers keytar dayjs
```

## Step 2 — Store credentials in Keychain

We never want bank creds in source. `keytar` reads from macOS Keychain.

```bash
# Open Keychain Access.app → File → New Password Item
#   Keychain Item Name: family-inc-hapoalim
#   Account Name:       <your-hapoalim-username>
#   Password:           <your-hapoalim-password>
# Repeat for any extra creds (e.g. userCode, password for Leumi)
```

Test from Node:

```bash
node -e "require('keytar').getPassword('family-inc-hapoalim', '<username>').then(console.log)"
```

## Step 3 — The scraper script

Full template lives at `code/scrape.js`. Inline here for reference:

```javascript
// scrape.js — pulls last 30 days of transactions and writes a CSV
// into Finance_CSVs/ so the existing pipeline ingests it untouched.

const { CompanyTypes, createScraper } = require('israeli-bank-scrapers');
const keytar = require('keytar');
const dayjs = require('dayjs');
const fs = require('fs');
const path = require('path');

const COMPANY = CompanyTypes.hapoalim; // or .leumi, .discount, .max, .visaCal …
const KEYCHAIN_SERVICE = 'family-inc-hapoalim';
const USERNAME = process.env.BANK_USERNAME; // set in launchd plist
const OUT_DIR = path.join(
  process.env.HOME,
  'Documents/Claude/Family Inc/Finance_CSVs'
);

(async () => {
  const password = await keytar.getPassword(KEYCHAIN_SERVICE, USERNAME);
  if (!password) throw new Error('No password in Keychain for ' + USERNAME);

  const scraper = createScraper({
    companyId: COMPANY,
    startDate: dayjs().subtract(30, 'day').toDate(),
    combineInstallments: false,
    showBrowser: false,
  });

  const result = await scraper.scrape({ userCode: USERNAME, password });
  if (!result.success) {
    console.error('Scrape failed:', result.errorType, result.errorMessage);
    process.exit(1);
  }

  const rows = [['date', 'description', 'amount', 'account', 'category']];
  for (const account of result.accounts) {
    for (const txn of account.txns) {
      rows.push([
        dayjs(txn.date).format('YYYY-MM-DD'),
        (txn.description || '').replace(/,/g, ' '),
        txn.chargedAmount,
        account.accountNumber,
        '', // category — filled in by Sheets formula
      ]);
    }
  }

  const stamp = dayjs().format('YYYY-MM-DD');
  const outPath = path.join(OUT_DIR, `hapoalim_${stamp}.csv`);
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(outPath, rows.map((r) => r.join(',')).join('\n'));
  console.log('Wrote', outPath, 'rows:', rows.length - 1);
})();
```

### Join point with existing pipeline

The existing `Finance_CSVs/` folder is already watched by the import flow that feeds the `Finance—Transactions` tab. **Don't change the filename pattern** — `<bank>_<YYYY-MM-DD>.csv` is what the ingest expects.

## Step 4 — Schedule with launchd

Create `~/Library/LaunchAgents/com.familyinc.bankscraper.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.familyinc.bankscraper</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/node</string>
    <string>/Users/adaramir/Documents/Claude/Family Inc/Automation/bank-scraper/scrape.js</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>BANK_USERNAME</key><string>YOUR_USERNAME_HERE</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>6</integer>
    <key>Minute</key><integer>30</integer>
  </dict>
  <key>StandardOutPath</key><string>/tmp/familyinc-bankscraper.log</string>
  <key>StandardErrorPath</key><string>/tmp/familyinc-bankscraper.err</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.familyinc.bankscraper.plist
launchctl start com.familyinc.bankscraper
tail -f /tmp/familyinc-bankscraper.log
```

### Optional cloud path (Render)

If you want to move off your laptop, create a Render Cron Job, point it at the repo, set `BANK_USERNAME` + `BANK_PASSWORD` as env vars (no Keychain there), and use the same `scrape.js` but read `process.env.BANK_PASSWORD` directly. Schedule: `30 6 * * *`.

## Verify it worked

- [ ] `node scrape.js` runs to completion and prints `Wrote <path> rows: N` with N > 0.
- [ ] A fresh file appears in `Finance_CSVs/` named `<bank>_<date>.csv`.
- [ ] That file's rows show up in the `Finance—Transactions` tab on the next sync.
- [ ] `launchctl list | grep familyinc` shows the job loaded.
- [ ] After one overnight cycle, `/tmp/familyinc-bankscraper.log` has a fresh entry.
