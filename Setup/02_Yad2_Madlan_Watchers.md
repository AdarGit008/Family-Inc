# 02 — Yad2 + Madlan Watchers

**Time budget: ~1h.**

## Why this matters

The house in ⟨town⟩ is a 12–18-month goal. Passive background scraping of Yad2 + Madlan analytics means by the time you're ready to buy, you already have months of comparable data — average price/m², which streets churn, how listings move. No daily checking.

## Prereqs

- [apify.com](https://apify.com) free account (covers ~5K actor minutes/month, more than enough at 4h cadence).
- API token: Apify Console → Settings → Integrations → API tokens → copy.
- The `Family_OS` Sheet open. You'll add a new tab `Real_Estate_Watch` with columns: `scraped_at, source, listing_id, url, city, neighborhood, price_ils, rooms, sqm, floor, raw_title, ppm_ils`.

## Step 1 — Set up the actors

In Apify Console → **Store**, search for and add:

1. `swerve/yad2-scraper`
2. `swerve/madlan-analytics`

(If the exact slugs are unavailable, search "Yad2" and "Madlan" — pick the most-recently-updated actor with >100 runs.)

## Step 2 — Yad2 input JSON

Open the Yad2 actor → **Input** tab → paste:

```json
{
  "category": "realestate/forsale",
  "filters": {
    "city": "Kiryat Tivon",
    "neighborhood": "⟨town⟩",
    "minRooms": 3,
    "maxPrice": 2500000,
    "propertyType": ["apartment", "house", "cottage"]
  },
  "maxItems": 200,
  "proxyConfiguration": { "useApifyProxy": true }
}
```

Also create a second Yad2 task targeting the wider area as a fallback comp pool:

```json
{
  "category": "realestate/forsale",
  "filters": {
    "city": "Kiryat Tivon",
    "minRooms": 3,
    "maxPrice": 3000000
  },
  "maxItems": 200,
  "proxyConfiguration": { "useApifyProxy": true }
}
```

## Step 3 — Madlan input JSON

```json
{
  "area": "Kiryat Tivon",
  "subArea": "⟨town⟩",
  "reportTypes": ["avgPricePerSqm", "transactionsLast12mo", "schoolsNearby"]
}
```

## Step 4 — Schedule

For each task: **Actions → Schedules → New schedule**.

- Cron: `0 */4 * * *` (every 4h)
- Timezone: `Asia/Jerusalem`

## Step 5 — Webhook → Apps Script

In each task: **Integrations → Webhooks → Add webhook**.

- Event type: `Run successfully finished`
- URL: paste your Apps Script Web App URL (from Step 6 below)
- Payload template (default is fine; the script reads `resource.defaultDatasetId` and pulls the items).

## Step 6 — Apps Script that appends to the Sheet

In `Family_OS` → Extensions → **Apps Script** → new file `appendListings.gs` → paste the contents of `code/appendListings.gs` (also inline below). Then **Deploy → New deployment → Web app → Execute as: me, Who has access: Anyone**. Copy the `/exec` URL into the Apify webhooks.

You also need an Apify token stored: **Project Settings → Script properties** → add `APIFY_TOKEN = <your-token>`.

```javascript
// appendListings.gs — receives Apify "run finished" webhook,
// pulls the dataset, appends rows to Real_Estate_Watch.

const SHEET_NAME = 'Real_Estate_Watch';

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  const datasetId = body.resource && body.resource.defaultDatasetId;
  const source = (body.eventData && body.eventData.actorTaskId) || 'unknown';
  if (!datasetId) return _json({ ok: false, error: 'no datasetId' });

  const token = PropertiesService.getScriptProperties().getProperty('APIFY_TOKEN');
  const url = `https://api.apify.com/v2/datasets/${datasetId}/items?token=${token}&clean=true&format=json`;
  const items = JSON.parse(UrlFetchApp.fetch(url).getContentText());

  const sh = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  const now = new Date();
  const rows = items.map((it) => ([
    now,
    source,
    it.id || it.listingId || '',
    it.url || '',
    it.city || '',
    it.neighborhood || '',
    Number(it.price || it.priceIls || 0),
    Number(it.rooms || 0),
    Number(it.sqm || it.squareMeters || 0),
    it.floor || '',
    it.title || '',
    it.sqm ? Math.round((it.price || 0) / it.sqm) : '',
  ]));
  if (rows.length) sh.getRange(sh.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);

  return _json({ ok: true, appended: rows.length });
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
```

## Verify it worked

- [ ] Each Apify task shows a successful run within 5 min of the schedule firing.
- [ ] `Real_Estate_Watch` tab has new rows with `scraped_at` matching the run time.
- [ ] `ppm_ils` column shows reasonable numbers (Kiryat Tivon is roughly 25–35K/m² in 2026).
- [ ] Re-running doesn't crash on duplicates (we just append; dedupe lives in a Sheet pivot, not here).
- [ ] Apify usage dashboard shows you're well under the free-tier ceiling.
