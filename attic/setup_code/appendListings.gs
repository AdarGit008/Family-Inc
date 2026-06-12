// appendListings.gs
// Apps Script Web App that receives Apify "run finished" webhooks for
// the Yad2 and Madlan watchers, pulls the dataset, and appends rows to
// the Real_Estate_Watch tab of Family_OS.
//
// Required Script Properties:
//   APIFY_TOKEN — Apify Console → Settings → Integrations → API tokens
//
// Deploy:
//   Deploy → New deployment → Web app
//     Execute as: me
//     Who has access: Anyone
//   Copy the /exec URL into each Apify task's webhook config.

const SHEET_NAME = 'Real_Estate_Watch';
const HEADERS = [
  'scraped_at', 'source', 'listing_id', 'url', 'city', 'neighborhood',
  'price_ils', 'rooms', 'sqm', 'floor', 'raw_title', 'ppm_ils',
];

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    const datasetId = body.resource && body.resource.defaultDatasetId;
    const source = (body.eventData && body.eventData.actorTaskId) || 'unknown';
    if (!datasetId) return _json({ ok: false, error: 'no datasetId in payload' });

    const token = PropertiesService.getScriptProperties().getProperty('APIFY_TOKEN');
    if (!token) return _json({ ok: false, error: 'APIFY_TOKEN script property missing' });

    const url = `https://api.apify.com/v2/datasets/${datasetId}/items?token=${token}&clean=true&format=json`;
    const items = JSON.parse(UrlFetchApp.fetch(url).getContentText());

    const sh = _ensureSheet();
    const now = new Date();
    const rows = items.map((it) => {
      const price = Number(it.price || it.priceIls || 0);
      const sqm = Number(it.sqm || it.squareMeters || 0);
      return [
        now,
        source,
        it.id || it.listingId || '',
        it.url || '',
        it.city || '',
        it.neighborhood || '',
        price,
        Number(it.rooms || 0),
        sqm,
        it.floor || '',
        it.title || '',
        sqm ? Math.round(price / sqm) : '',
      ];
    });
    if (rows.length) {
      sh.getRange(sh.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
    }
    return _json({ ok: true, appended: rows.length });
  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

function _ensureSheet() {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  return sh;
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
