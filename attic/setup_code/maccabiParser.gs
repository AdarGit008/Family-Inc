// maccabiParser.gs — parses Maccabi emails into Health + Reminders
//
// Trigger hourly. Reads threads with label "family-inc/maccabi-events"
// that haven't been processed (label "family-inc/maccabi-parsed" missing).
//
// Required script properties:
//   FAMILY_NAMES — JSON array of {hebrew, english} pairs, e.g.
//     [{"hebrew":"אדר","english":"Adar"},{"hebrew":"שני","english":"Shanee"},
//      {"hebrew":"ילד א","english":"Kid A"},{"hebrew":"ילד ב","english":"Kid B"}]
//
// Sheet contract (Health):
//   member | event_type | date_time | location | doctor | notes | email_id | parsed_at

const LABEL_INBOX = 'family-inc/maccabi-events';
const LABEL_DONE = 'family-inc/maccabi-parsed';

function parseMaccabi() {
  const inbox = GmailApp.getUserLabelByName(LABEL_INBOX);
  if (!inbox) throw new Error('Label "' + LABEL_INBOX + '" not found. Create the Gmail filter first.');
  const done = GmailApp.getUserLabelByName(LABEL_DONE) || GmailApp.createLabel(LABEL_DONE);

  const ss = SpreadsheetApp.getActive();
  const health = ss.getSheetByName('Health');
  const reminders = ss.getSheetByName('Reminders');
  if (!health || !reminders) throw new Error('Health or Reminders sheet missing');

  const seen = new Set(_existingEmailIds(health));
  const family = JSON.parse(
    PropertiesService.getScriptProperties().getProperty('FAMILY_NAMES') || '[]'
  );

  const threads = inbox.getThreads(0, 50);
  for (const th of threads) {
    if (th.getLabels().some((l) => l.getName() === LABEL_DONE)) continue;
    for (const m of th.getMessages()) {
      const id = m.getId();
      if (seen.has(id)) continue;
      const body = m.getPlainBody();
      const subject = m.getSubject();
      const parsed = _parseMaccabiBody(body, subject, family);
      if (!parsed) continue;

      health.appendRow([
        parsed.member, parsed.event_type, parsed.date_time,
        parsed.location, parsed.doctor, parsed.notes,
        id, new Date(),
      ]);

      if (parsed.date_time instanceof Date) {
        const r24 = new Date(parsed.date_time.getTime() - 24 * 3600 * 1000);
        reminders.appendRow([
          `[${parsed.member}] ${parsed.event_type} — ${parsed.location || ''}`.trim(),
          r24, parsed.member, 'Health/Maccabi', 'maccabi-parser', 'open',
          'https://www.maccabi4u.co.il/',
        ]);
        if (parsed.event_type === 'appointment') {
          const r2 = new Date(parsed.date_time.getTime() - 2 * 3600 * 1000);
          reminders.appendRow([
            `[${parsed.member}] תור היום — ${parsed.location || ''}`.trim(),
            r2, parsed.member, 'Health/Maccabi', 'maccabi-parser', 'open',
            'https://www.maccabi4u.co.il/',
          ]);
        }
      }
      seen.add(id);
    }
    th.addLabel(done);
    th.markRead();
  }
}

function _parseMaccabiBody(body, subject, family) {
  const text = subject + '\n' + body;

  // member: first family name found
  let member = 'Family';
  for (const p of family) {
    if (p.hebrew && text.indexOf(p.hebrew) !== -1) { member = p.english; break; }
    if (p.english && text.indexOf(p.english) !== -1) { member = p.english; break; }
  }

  let event_type = 'note';
  if (/חיסון|חיסונים/.test(text)) event_type = 'vaccine';
  else if (/תוצאות\s*בדיקה|מעבדה/.test(text)) event_type = 'lab';
  else if (/מרשם|תרופה/.test(text)) event_type = 'prescription';
  else if (/תור|פגישה|בדיקה/.test(text)) event_type = 'appointment';

  // date_time: dd/mm/yyyy HH:MM or dd.mm.yyyy
  const dt = text.match(/(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})(?:\s+(\d{1,2}):(\d{2}))?/);
  let date_time = '';
  if (dt) {
    const y = dt[3].length === 2 ? 2000 + Number(dt[3]) : Number(dt[3]);
    const h = dt[4] ? Number(dt[4]) : 9;
    const mi = dt[5] ? Number(dt[5]) : 0;
    date_time = new Date(y, Number(dt[2]) - 1, Number(dt[1]), h, mi);
  }

  const locMatch = text.match(/(?:סניף|מרפאה|כתובת)[:\s]*([^\n]{2,60})/);
  const docMatch = text.match(/(?:ד"ר|דר['׳]|רופא[ה]?)\s+([^\n,]{2,40})/);

  return {
    member,
    event_type,
    date_time,
    location: locMatch ? locMatch[1].trim() : '',
    doctor: docMatch ? docMatch[1].trim() : '',
    notes: subject,
  };
}

function _existingEmailIds(sh) {
  const last = sh.getLastRow();
  if (last < 2) return [];
  return sh.getRange(2, 7, last - 1, 1).getValues().flat(); // col G = email_id
}
