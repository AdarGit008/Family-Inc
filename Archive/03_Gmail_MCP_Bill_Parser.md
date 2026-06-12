# 03 — Gmail Bill Parser (Apps Script)

**Time budget: ~1.5h.**

## Why this matters

Every month: IEC (חברת חשמל), arnona, Bezeq, HOT, Partner, mobile carrier. Each sends an email with an amount + due date. Today this turns into "did I pay X?" mental load. We let Apps Script read the inbox every 6h, parse the bill, write a row to the `Contracts` tab, and create a Reminder 3 days before due.

We use Apps Script (not MCP) for v1 because it runs server-side with no laptop dependency. Claude API is the fallback for unrecognized senders.

## Prereqs

- Adar's Gmail (the same account that owns `Family_OS`).
- An Anthropic API key (only used as a fallback parser — most regex hits succeed). Console → API Keys → copy.
- The `Family_OS` Sheet, with tabs `Contracts` and `Reminders` already present. Required columns:
  - `Contracts`: `vendor, category, amount_ils, due_date, period, email_id, raw_subject, parsed_at`
  - `Reminders`: `title, due_date, owner, category, source, status, guide_url`

## Step 1 — Open Apps Script

`Family_OS` Sheet → **Extensions → Apps Script**. Name the project `Family_OS_Backend`. Add a new file `billParser.gs` and paste `code/billParser.gs`.

## Step 2 — Script properties

Project Settings → **Script properties**:

| Key | Value |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-…` |
| `CLAUDE_MODEL` | `claude-opus-4-7` |

## Step 3 — Senders we recognize today

Inline list (also in the script). Regex first; Claude fallback if regex returns nothing.

| Sender | Vendor | Category |
|---|---|---|
| `noreply@iec.co.il` | חברת חשמל (IEC) | Utilities/Electricity |
| `noreply@arnona.tel-aviv.gov.il` | ארנונה | Tax/Arnona |
| `noreply@bezeqint.net` | Bezeq Int'l | Utilities/Internet |
| `noreply@hot.net.il` | HOT | Utilities/TV+Net |
| `noreply@partner.co.il` | Partner | Utilities/Mobile |
| `*@pelephone.co.il` | Pelephone | Utilities/Mobile |
| `*@cellcom.co.il` | Cellcom | Utilities/Mobile |

Add others as you discover them — search Gmail for `חשבונית OR לתשלום OR "עד לתאריך"` to find candidates.

## Step 4 — Inline parser

```javascript
// billParser.gs — runs every 6h.
// 1. queries Gmail for known bill senders received in last 7 days
// 2. for each thread, regex first, then Claude fallback
// 3. appends to Contracts, creates a Reminder 3 days before due

const VENDORS = [
  { match: 'noreply@iec.co.il',                  vendor: 'IEC חברת חשמל', category: 'Utilities/Electricity' },
  { match: 'noreply@arnona.tel-aviv.gov.il',     vendor: 'ארנונה',          category: 'Tax/Arnona' },
  { match: 'noreply@bezeqint.net',               vendor: 'Bezeq Int’l',     category: 'Utilities/Internet' },
  { match: 'noreply@hot.net.il',                 vendor: 'HOT',             category: 'Utilities/TV+Net' },
  { match: 'noreply@partner.co.il',              vendor: 'Partner',         category: 'Utilities/Mobile' },
  { match: 'pelephone.co.il',                    vendor: 'Pelephone',       category: 'Utilities/Mobile' },
  { match: 'cellcom.co.il',                      vendor: 'Cellcom',         category: 'Utilities/Mobile' },
];

function parseInbox() {
  const sheet = SpreadsheetApp.getActive();
  const contracts = sheet.getSheetByName('Contracts');
  const reminders = sheet.getSheetByName('Reminders');
  const seen = new Set(_existingEmailIds(contracts));

  for (const v of VENDORS) {
    const q = `from:(${v.match}) newer_than:7d`;
    const threads = GmailApp.search(q, 0, 25);
    for (const th of threads) {
      for (const m of th.getMessages()) {
        if (seen.has(m.getId())) continue;
        const body = m.getPlainBody();
        const parsed = _regexParse(body) || _claudeParse(body, v.vendor);
        if (!parsed || !parsed.amount_ils || !parsed.due_date) continue;
        contracts.appendRow([
          v.vendor, v.category, parsed.amount_ils, parsed.due_date,
          parsed.period || '', m.getId(), m.getSubject(), new Date(),
        ]);
        const remind = new Date(parsed.due_date);
        remind.setDate(remind.getDate() - 3);
        reminders.appendRow([
          `${v.vendor} — ${parsed.amount_ils} ₪`, remind, 'Adar',
          v.category, 'bill-parser', 'open', '',
        ]);
        seen.add(m.getId());
      }
    }
  }
}

function _regexParse(body) {
  // amount: look for "₪ 412.50" or "412.50 ₪" or "סה""כ לתשלום 412.50"
  const amt = body.match(/(?:₪\s*|סה.?כ\s*לתשלום[:\s]*)([\d,]+\.?\d*)/);
  // due: "לתאריך 15/06/2026" or "עד 15.06.2026"
  const due = body.match(/(?:לתאריך|עד\s*תאריך|עד)[:\s]*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})/);
  if (!amt || !due) return null;
  return {
    amount_ils: Number(amt[1].replace(/,/g, '')),
    due_date: _toIso(due[1]),
    period: '',
  };
}

function _claudeParse(body, vendor) {
  const key = PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');
  const model = PropertiesService.getScriptProperties().getProperty('CLAUDE_MODEL') || 'claude-opus-4-7';
  const prompt = `Extract bill info from this Hebrew/English email. Return strict JSON: ` +
    `{"amount_ils": number, "due_date": "YYYY-MM-DD", "period": "string"}. ` +
    `Vendor=${vendor}. Email body:\n\n${body.substring(0, 4000)}`;
  const res = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
    method: 'post', contentType: 'application/json',
    headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01' },
    payload: JSON.stringify({
      model, max_tokens: 300,
      messages: [{ role: 'user', content: prompt }],
    }),
    muteHttpExceptions: true,
  });
  try {
    const out = JSON.parse(res.getContentText()).content[0].text;
    return JSON.parse(out.match(/\{[\s\S]*\}/)[0]);
  } catch (e) { return null; }
}

function _existingEmailIds(sh) {
  const last = sh.getLastRow();
  if (last < 2) return [];
  return sh.getRange(2, 6, last - 1, 1).getValues().flat(); // col F = email_id
}

function _toIso(s) {
  const m = s.match(/(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})/);
  const y = m[3].length === 2 ? '20' + m[3] : m[3];
  return `${y}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
}
```

## Step 5 — Trigger

Apps Script → **Triggers (clock icon)** → Add Trigger:

- Function: `parseInbox`
- Event source: Time-driven
- Type: Hours timer → **Every 6 hours**

Run it once manually first (`Run → parseInbox`) and accept the Gmail + UrlFetch + Sheets scopes.

## Verify it worked

- [ ] Manual run completes without errors in Executions log.
- [ ] Send yourself a test bill (forward a real IEC mail to yourself) — within 6h it appears in `Contracts`.
- [ ] A matching row appears in `Reminders` 3 days before the due date.
- [ ] The same email is not double-imported on the next run (email_id dedupe works).
- [ ] The Reminder gets picked up by `reminders_engine.py` on its next cycle.
