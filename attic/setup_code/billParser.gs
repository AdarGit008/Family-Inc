// billParser.gs — Gmail → Contracts + Reminders, runs every 6h
//
// Trigger: Apps Script → Triggers → parseInbox, hours timer, every 6h.
// Required script properties:
//   ANTHROPIC_API_KEY  — sk-ant-...
//   CLAUDE_MODEL       — claude-opus-4-7 (or current opus)
//
// Sheet contract:
//   Contracts: vendor | category | amount_ils | due_date | period | email_id | raw_subject | parsed_at
//   Reminders: title | due_date | owner | category | source | status | guide_url

const VENDORS = [
  { match: 'noreply@iec.co.il',              vendor: 'IEC חברת חשמל', category: 'Utilities/Electricity' },
  { match: 'noreply@arnona.tel-aviv.gov.il', vendor: 'ארנונה',          category: 'Tax/Arnona' },
  { match: 'noreply@bezeqint.net',           vendor: 'Bezeq Int\'l',    category: 'Utilities/Internet' },
  { match: 'noreply@hot.net.il',             vendor: 'HOT',             category: 'Utilities/TV+Net' },
  { match: 'noreply@partner.co.il',          vendor: 'Partner',         category: 'Utilities/Mobile' },
  { match: 'pelephone.co.il',                vendor: 'Pelephone',       category: 'Utilities/Mobile' },
  { match: 'cellcom.co.il',                  vendor: 'Cellcom',         category: 'Utilities/Mobile' },
];

function parseInbox() {
  const ss = SpreadsheetApp.getActive();
  const contracts = ss.getSheetByName('Contracts');
  const reminders = ss.getSheetByName('Reminders');
  if (!contracts || !reminders) throw new Error('Contracts or Reminders sheet missing');

  const seen = new Set(_existingEmailIds(contracts));

  for (const v of VENDORS) {
    const q = `from:(${v.match}) newer_than:7d`;
    const threads = GmailApp.search(q, 0, 25);
    for (const th of threads) {
      for (const m of th.getMessages()) {
        const id = m.getId();
        if (seen.has(id)) continue;
        const body = m.getPlainBody();
        const parsed = _regexParse(body) || _claudeParse(body, v.vendor);
        if (!parsed || !parsed.amount_ils || !parsed.due_date) continue;

        contracts.appendRow([
          v.vendor, v.category, parsed.amount_ils, parsed.due_date,
          parsed.period || '', id, m.getSubject(), new Date(),
        ]);

        const remind = new Date(parsed.due_date);
        remind.setDate(remind.getDate() - 3);
        reminders.appendRow([
          `${v.vendor} — ${parsed.amount_ils} ₪`,
          remind, 'Adar', v.category, 'bill-parser', 'open', '',
        ]);
        seen.add(id);
      }
    }
  }
}

function _regexParse(body) {
  const amt = body.match(/(?:₪\s*|סה.?כ\s*לתשלום[:\s]*)([\d,]+\.?\d*)/);
  const due = body.match(/(?:לתאריך|עד\s*תאריך|עד)[:\s]*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})/);
  if (!amt || !due) return null;
  return {
    amount_ils: Number(amt[1].replace(/,/g, '')),
    due_date: _toIso(due[1]),
    period: '',
  };
}

function _claudeParse(body, vendor) {
  const props = PropertiesService.getScriptProperties();
  const key = props.getProperty('ANTHROPIC_API_KEY');
  const model = props.getProperty('CLAUDE_MODEL') || 'claude-opus-4-7';
  if (!key) return null;

  const prompt =
    'Extract bill info from this Hebrew/English utility email. ' +
    'Return strict JSON only: {"amount_ils": number, "due_date": "YYYY-MM-DD", "period": "string"}. ' +
    `Vendor=${vendor}. Email body:\n\n${body.substring(0, 4000)}`;

  const res = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
    method: 'post',
    contentType: 'application/json',
    headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01' },
    payload: JSON.stringify({
      model: model,
      max_tokens: 300,
      messages: [{ role: 'user', content: prompt }],
    }),
    muteHttpExceptions: true,
  });
  try {
    const out = JSON.parse(res.getContentText()).content[0].text;
    return JSON.parse(out.match(/\{[\s\S]*\}/)[0]);
  } catch (e) {
    Logger.log('claude fallback parse failed: ' + e);
    return null;
  }
}

function _existingEmailIds(sh) {
  const last = sh.getLastRow();
  if (last < 2) return [];
  return sh.getRange(2, 6, last - 1, 1).getValues().flat();
}

function _toIso(s) {
  const m = s.match(/(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})/);
  const y = m[3].length === 2 ? '20' + m[3] : m[3];
  return `${y}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
}
