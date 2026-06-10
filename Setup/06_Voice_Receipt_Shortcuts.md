# 06 — Voice + Receipt Apple Shortcuts

**Time budget: ~1.5h** (split across building the two shortcuts and the Apps Script receiver).

## Why this matters

This is the capture surface Shanee will actually use. Both shortcuts hit the same Apps Script webhook, which writes to `Finance—Transactions`. One is voice-first ("I spent 38 shekels at Aroma"), the other is camera-first (snap, parse, done). Both install on Adar's and Shanee's iPhones with the same webhook URL.

## Part A — Apps Script webhook receiver

In `Family_OS` → Extensions → Apps Script → add file `webhookReceiver.gs` → paste `code/webhookReceiver.gs`. Inline below:

```javascript
// webhookReceiver.gs
// Accepts JSON POST from iOS Shortcuts.
// type=expense  → {vendor, amount_ils, category, date, note}
// type=receipt  → {image_base64, mime_type}    (sent to Mindee server-side)

const SHARED_SECRET = PropertiesService.getScriptProperties().getProperty('SHORTCUTS_SECRET');
const MINDEE_API_KEY = PropertiesService.getScriptProperties().getProperty('MINDEE_API_KEY');

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    if (body.secret !== SHARED_SECRET) return _json({ ok: false, error: 'bad secret' });
    if (body.type === 'expense') return _expense(body);
    if (body.type === 'receipt') return _receipt(body);
    return _json({ ok: false, error: 'unknown type' });
  } catch (err) { return _json({ ok: false, error: String(err) }); }
}

function _expense(b) {
  const sh = SpreadsheetApp.getActive().getSheetByName('Finance—Transactions');
  sh.appendRow([
    b.date || _today(), b.vendor || '', Number(b.amount_ils) || 0,
    'Shortcut/Voice', b.category || '', b.note || '', new Date(),
  ]);
  return _json({ ok: true, vendor: b.vendor, amount: b.amount_ils });
}

function _receipt(b) {
  const blob = Utilities.newBlob(
    Utilities.base64Decode(b.image_base64), b.mime_type || 'image/jpeg', 'receipt.jpg'
  );
  const res = UrlFetchApp.fetch(
    'https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict',
    {
      method: 'post', headers: { Authorization: 'Token ' + MINDEE_API_KEY },
      payload: { document: blob }, muteHttpExceptions: true,
    }
  );
  const r = JSON.parse(res.getContentText()).document.inference.prediction;
  const sh = SpreadsheetApp.getActive().getSheetByName('Finance—Transactions');
  sh.appendRow([
    (r.date && r.date.value) || _today(),
    (r.supplier_name && r.supplier_name.value) || '',
    (r.total_amount && r.total_amount.value) || 0,
    'Shortcut/OCR',
    (r.category && r.category.value) || '',
    'auto-parsed', new Date(),
  ]);
  return _json({ ok: true, vendor: r.supplier_name && r.supplier_name.value, amount: r.total_amount && r.total_amount.value });
}

function _today() {
  return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
}
function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
```

### Deploy

- Apps Script → **Deploy → New deployment → Web app**.
- Execute as: **Me**.
- Who has access: **Anyone**.
- Copy the `/exec` URL — that's `WEBHOOK_URL` for the shortcuts.
- Script properties:
  - `SHORTCUTS_SECRET` = generate any random string (e.g. `openssl rand -hex 24`).
  - `MINDEE_API_KEY` = your Mindee token (from doc 04).
  - `ANTHROPIC_API_KEY` = (you already added this for the bill parser).

## Part B — Shortcut #1: "Log expense" (voice)

iPhone → Shortcuts app → **+ New Shortcut** → name: **Log expense**.

Actions in order:

1. **Dictate Text** — Language: Hebrew (or auto). Stop on pause.
2. **Get Contents of URL**:
   - URL: `https://api.anthropic.com/v1/messages`
   - Method: POST
   - Headers:
     - `x-api-key`: your Anthropic key
     - `anthropic-version`: `2023-06-01`
     - `content-type`: `application/json`
   - Request Body (JSON):
     ```json
     {
       "model": "claude-opus-4-7",
       "max_tokens": 200,
       "messages": [{
         "role": "user",
         "content": "Extract from this Hebrew/English utterance and return strict JSON only: {\"vendor\":string,\"amount_ils\":number,\"category\":string,\"date\":\"YYYY-MM-DD\",\"note\":string}. Today is [Current Date]. Utterance: [Dictated Text]"
       }]
     }
     ```
3. **Get Dictionary Value** → Key: `content` → first item → `text`.
4. **Match Text** → regex `\{[\s\S]*\}` to isolate JSON.
5. **Get Dictionary from Input** (treat matched text as JSON).
6. **Get Contents of URL** (the Apps Script webhook):
   - URL: paste your `WEBHOOK_URL`
   - Method: POST
   - Request Body (JSON):
     ```json
     {
       "secret": "[your SHORTCUTS_SECRET]",
       "type": "expense",
       "vendor": "[vendor from dict]",
       "amount_ils": "[amount_ils]",
       "category": "[category]",
       "date": "[date]",
       "note": "[note]"
     }
     ```
7. **Show Notification** → "Logged: [vendor] — [amount_ils] ₪".

Test phrases:
- "Aroma, thirty-eight shekels, coffee."
- "Shufersal four hundred twelve thirty, groceries, yesterday."

## Part C — Shortcut #2: "Snap receipt"

Actions:

1. **Take Photo** → Show camera preview: on; Quality: medium.
2. **Base64 Encode** the photo (action: Base64 Encode → mode: Encode).
3. **Get Contents of URL** (webhook):
   - Method: POST
   - Request Body (JSON):
     ```json
     {
       "secret": "[SHORTCUTS_SECRET]",
       "type": "receipt",
       "image_base64": "[Base64 Encoded]",
       "mime_type": "image/jpeg"
     }
     ```
4. **Get Dictionary Value** → `vendor` and `amount`.
5. **Show Notification** → "Receipt: [vendor] — [amount] ₪. Tap to edit row.".

## Part D — Distribute to both phones

For each shortcut: tap **(i) → Share → iCloud Link → send to Shanee**. She opens, taps **Add Shortcut**, then in the shortcut's settings edits **SHORTCUTS_SECRET** + **WEBHOOK_URL** if you parameterized them (recommended: store both in an "Ask Each Time?" → set once → use as variables).

## Verify it worked

- [ ] Voice: "Cofix, 12 shekels, coffee" → row appears with vendor=Cofix, amount=12, category=coffee.
- [ ] Receipt: snap a Shufersal receipt → row appears with the right supplier and total within 10s.
- [ ] Wrong secret returns `{ok:false}` and no row.
- [ ] Shanee's identical shortcut writes to the same sheet (no separate config).
- [ ] Apps Script Executions log shows clean `doPost` runs with 200s.
