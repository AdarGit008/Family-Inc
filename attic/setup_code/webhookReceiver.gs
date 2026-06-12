// webhookReceiver.gs — iOS Shortcuts webhook for Family_OS
//
// Two payloads:
//   type=expense → {secret, vendor, amount_ils, category, date, note}
//   type=receipt → {secret, image_base64, mime_type}
//
// Required script properties:
//   SHORTCUTS_SECRET   — random shared secret matching the Shortcut config
//   MINDEE_API_KEY     — Mindee API token (only for receipt OCR path)
//
// Sheet contract (Finance—Transactions):
//   date | vendor | amount_ils | account | category | note | inserted_at

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    const props = PropertiesService.getScriptProperties();
    if (body.secret !== props.getProperty('SHORTCUTS_SECRET')) {
      return _json({ ok: false, error: 'bad secret' });
    }
    if (body.type === 'expense') return _expense(body);
    if (body.type === 'receipt') return _receipt(body);
    return _json({ ok: false, error: 'unknown type' });
  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

function _expense(b) {
  const sh = SpreadsheetApp.getActive().getSheetByName('Finance—Transactions');
  if (!sh) return _json({ ok: false, error: 'missing Finance—Transactions sheet' });
  sh.appendRow([
    b.date || _today(),
    b.vendor || '',
    Number(b.amount_ils) || 0,
    'Shortcut/Voice',
    b.category || '',
    b.note || '',
    new Date(),
  ]);
  return _json({ ok: true, vendor: b.vendor, amount: b.amount_ils });
}

function _receipt(b) {
  const props = PropertiesService.getScriptProperties();
  const mindeeKey = props.getProperty('MINDEE_API_KEY');
  if (!mindeeKey) return _json({ ok: false, error: 'MINDEE_API_KEY missing' });

  const blob = Utilities.newBlob(
    Utilities.base64Decode(b.image_base64),
    b.mime_type || 'image/jpeg',
    'receipt.jpg'
  );
  const res = UrlFetchApp.fetch(
    'https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict',
    {
      method: 'post',
      headers: { Authorization: 'Token ' + mindeeKey },
      payload: { document: blob },
      muteHttpExceptions: true,
    }
  );
  let pred;
  try {
    pred = JSON.parse(res.getContentText()).document.inference.prediction;
  } catch (err) {
    return _json({ ok: false, error: 'mindee parse failed' });
  }

  const sh = SpreadsheetApp.getActive().getSheetByName('Finance—Transactions');
  sh.appendRow([
    _val(pred.date) || _today(),
    _val(pred.supplier_name) || '',
    Number(_val(pred.total_amount)) || 0,
    'Shortcut/OCR',
    _val(pred.category) || '',
    'auto-parsed',
    new Date(),
  ]);
  return _json({
    ok: true,
    vendor: _val(pred.supplier_name),
    amount: _val(pred.total_amount),
  });
}

function _val(field) {
  return field && (field.value !== undefined ? field.value : null);
}

function _today() {
  return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
