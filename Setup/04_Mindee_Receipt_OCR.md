# 04 — Mindee Receipt OCR via Zapier

**Time budget: ~45min.**

## Why this matters

Paper and PDF receipts are the long tail of household expense tracking. Mindee's receipt API is multi-language (handles Hebrew well enough for Shufersal/Rami Levy/Victory) and Zapier handles the plumbing without writing any code. Mobile capture flow takes one tap.

## Prereqs

- [mindee.com](https://mindee.com) free account (250 docs/month free tier — fine for household).
  - Mindee Console → API Keys → copy. Store in macOS Keychain under service `family-inc-mindee` (reference only; Zapier holds the working copy).
- [Zapier](https://zapier.com) account, free tier supports 5 zaps which is plenty.
- Google Drive folder: create `Family inc./Receipts/Inbox/` and `Family inc./Receipts/Processed/`.

## Step 1 — The zap

Zapier → **Create Zap**.

### Trigger
- App: **Google Drive**
- Event: **New File in Folder**
- Folder: `/Family inc./Receipts/Inbox`
- Include deleted: No

### Action 1 — Mindee Receipt OCR
- App: **Mindee** (search "Mindee")
- Event: **Parse Receipt**
- API Key: paste from Mindee Console
- File: from trigger step (File field)

### Action 2 — Google Sheets append
- App: **Google Sheets**
- Event: **Create Spreadsheet Row**
- Spreadsheet: `Family_OS`
- Worksheet: `Finance—Transactions`
- Map fields per the table below.

### Action 3 — Move file (optional but recommended)
- App: **Google Drive**
- Event: **Move File**
- File: trigger step
- Destination folder: `/Family inc./Receipts/Processed`

## Step 2 — Field mapping

| `Finance—Transactions` column | Mindee field | Notes |
|---|---|---|
| `date` | `date` | Mindee returns `YYYY-MM-DD` |
| `description` | `supplier_name` | Hebrew names come through fine |
| `amount` | `total_amount` | Negative if you keep expense convention |
| `account` | static `"Cash/Card-OCR"` | So you can filter these vs. bank rows |
| `category` | `category` | Mindee buckets are coarse — refine in Sheets |
| `currency` | `currency` | Usually `ILS` |
| `source_file` | trigger → `webViewLink` | So you can click back to the original |

## Step 3 — Mobile capture flow

On both iPhones:

1. Open the receipt photo (or use **Files** for a PDF).
2. **Share → Drive**.
3. Pick destination: `Family inc./Receipts/Inbox`.
4. Tap **Save**.

That's it. Within ~1 minute the zap fires, Mindee parses, the row lands in the sheet.

Pro tip: in Drive iOS, long-press the `Receipts/Inbox` folder → **Add to Home Screen** for a one-tap shortcut.

## Step 4 — Hebrew-heavy fallback

For receipts where Mindee struggles (handwritten, faded, mostly-RTL text):

- Swap the parser action to **Klippa OCR** (free tier 50/mo, better Hebrew). Same trigger, same Sheet append; only the middle action changes.
- Or punt the file into `Receipts/Manual/` and let it sit; the Sunday briefing will surface unparsed items.

## Verify it worked

- [ ] Drop a test receipt photo into `Receipts/Inbox` from your phone.
- [ ] Within 2 min, the zap shows a successful run in Zapier history.
- [ ] A new row in `Finance—Transactions` has the vendor, total, and date.
- [ ] The original file moved to `Receipts/Processed`.
- [ ] Re-uploading the same file results in a second row (intended — Zapier doesn't dedupe; budget for an occasional manual cleanup).
