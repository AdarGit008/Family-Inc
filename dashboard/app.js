// Family inc. dashboard — single-file SPA.
// Boring tech: vanilla JS, no build step, no framework.

(() => {
  'use strict';

  const cfg = window.FAMILY_INC_CONFIG;
  // spreadsheets: data; userinfo.email: who is tapping, so write-backs are
  // attributed via Settings.UserMap (SPEC §7.6) instead of a config guess.
  const SCOPES = 'https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/userinfo.email';
  const DISCOVERY = 'https://sheets.googleapis.com/$discovery/rest?version=v4';
  const CACHE_KEY = 'family_inc_cache_v1';
  const QUEUE_KEY = 'family_inc_writequeue_v1';
  const TOKEN_KEY = 'family_inc_token_v1';
  const MAX_PENDING_WRITES = 50;   // offline-queue cap (SPEC §7.6 / DESIGN §6) —
                                   // a one-shot warning fires at the cap, then
                                   // further taps are dropped, not silently lost
  // Lane C — the §6.1 Reminders columns the dashboard WRITES, resolved by header
  // NAME at load so a column insert can't corrupt a position-write; writes pause
  // if any is missing (the JS half of the engine's §7.1 schema-drift guard).
  const REMINDER_WRITE_COLS = ['Due Date', 'Status', 'Last Sent', 'Notes', 'LastDoneBy', 'DoneAt', 'WriteQueue_Tombstone'];

  // ---------------- i18n ----------------
  // Single source of truth for chrome strings. Hebrew is canonical; English
  // mirrors meaning, not literal legacy text. To add a key: drop it here and
  // tag the element with data-i18n="<key>" OR call t('<key>', {vars}) in JS.
  const STRINGS = {
    he: {
      // Tabbar
      'tabbar.today': 'היום',
      'tabbar.sunday': 'ראשון',
      'tabbar.settings': 'הגדרות',
      // Today screen sections
      'section.todayList': 'להיום',
      'section.calendar': 'יומן',
      'section.comingUp': 'בקרוב',
      'section.domains': 'תחומים',
      // Drawers
      'drawer.money': 'כספים',
      'drawer.health': 'בריאות',
      'drawer.goals': 'יעדים',
      'drawer.car': 'רכב',
      'drawer.contracts': 'מנויים וחוזים',
      'drawer.education': 'חינוך',
      'drawer.timeline': 'ציר זמן',
      // Status pill (3-tier; V3.2 replaced the status banner). Labels are
      // count-free — the count renders as its own mono span beside the label.
      'pill.overdue': 'באיחור',
      'pill.dueToday': 'להיום',
      'pill.allClear': 'אין דברים דחופים',
      'pill.sundayReady': 'סיכום ראשון מוכן',
      // Desk batch actions (V3.3 select-to-act). row.* double as the batch-bar labels.
      'row.done': '✓ בוצע',
      'row.snooze': '+ דחה',
      'row.note': '+ הערה',
      'desk.selected': 'נבחרו: {n}',
      'desk.notePlaceholder': 'כתבו הערה…',
      // Absolute-snooze chips (V3.3) — each resolves to an absolute Due date.
      'snooze.tomorrow': 'מחר',
      'snooze.in3': '+3',
      'snooze.week': 'שבוע',
      'snooze.twoweeks': 'שבועיים',
      'snooze.month': 'חודש',
      'snooze.pickDate': 'בחר תאריך',
      'snooze.label': 'דחה ל…',
      // Empty states
      'empty.nothingOnFire': 'שום דבר לא בוער. ☕',
      'empty.nothingThisWeek': 'אין אירועים השבוע.',
      'empty.noEventsDay': 'אין אירועים.',
      'empty.noQueuedWrites': 'אין כתיבות בתור.',
      'empty.next60Days': 'אין אירועים בחודשיים הקרובים.',
      'empty.noBudget': 'אין תקציב עדיין.',
      'empty.noRecentTxns': 'אין עסקאות אחרונות.',
      'empty.noGoals': 'אין יעדים.',
      'empty.noVehicle': 'אין רכב.',
      'empty.noRenewals': 'אין חידושים בחודשיים הקרובים.',
      'empty.noMilestones': 'אין אבני דרך בטווח שנבחר.',
      'empty.noUpcoming': 'אין פריטים קרובים.',
      'empty.noOverdue': 'אין פריטים באיחור.',
      'empty.allClean': 'הכל נקי.',
      'state.allGood': 'הכל בסדר',
      'state.loading': 'טוען…',
      // Calendar
      'cal.allDay': 'כל היום',
      'cal.today': 'היום',
      'cal.tomorrow': 'מחר',
      // Portfolio bottom-sheet
      'sheet.close': 'סגור',
      'sheet.recentTxns': 'עסקאות אחרונות',
      // Cross-domain timeline (V3.6) — zoom rungs + category-filter chips
      'timeline.zoomLabel': 'טווח זמן',
      'timeline.filterLabel': 'סינון לפי תחום',
      'timeline.now': 'עכשיו',
      'timeline.zoom.1wk': 'שבוע',
      'timeline.zoom.1mo': 'חודש',
      'timeline.zoom.3mo': '3 ח׳',
      'timeline.zoom.1yr': 'שנה',
      'timeline.zoom.5yr': '5 ש׳',
      'timeline.cat.all': 'הכל',
      'timeline.cat.finance': 'כספים',
      'timeline.cat.health': 'בריאות',
      'timeline.cat.car': 'רכב',
      'timeline.cat.education': 'חינוך',
      'timeline.cat.goals': 'יעדים',
      'timeline.cat.contracts': 'חוזים',
      'timeline.cat.calendar': 'יומן',
      'timeline.cat.other': 'אחר',
      // Love-note (V3.7) — parent-to-parent ephemeral note
      'lovenote.heading': 'פתק',
      'lovenote.inboundFrom': 'פתק מ{name}',
      'lovenote.composePlaceholder': 'פתק ל{name}…',
      'lovenote.composeGeneric': 'השאר פתק…',
      'lovenote.send': 'שלח',
      'lovenote.clear': 'מחק',
      'lovenote.waiting': 'ממתין ל{name}',
      'lovenote.sentToast': 'הפתק נשלח ל{name}',
      'lovenote.clearedToast': 'הפתק נמחק',
      'lovenote.failedToast': 'שליחת הפתק נכשלה — נסו שוב',
      // Car field labels
      'car.annualTest': 'טסט שנתי',
      'car.insurance': 'ביטוח',
      'car.license': 'רישיון',
      // Generic chrome
      'label.next': 'הבא:',
      // Drawer summary templates
      'summary.upcoming': '{n} בקרוב',
      'summary.active': '{n} פעילים',
      'summary.over': '{n} חורגות',
      'summary.within60': '{n} בחודשיים הקרובים',
      // Sunday view
      'sunday.title': 'סיכום ראשון',
      'sunday.weekAhead': 'השבוע הקרוב',
      'sunday.remindersThisWeek': 'תזכורות לשבוע',
      'sunday.overdue': 'באיחור',
      'sunday.money': 'כספים',
      'sunday.goals': 'יעדים',
      'sunday.hygiene': 'תחזוקת נתונים',
      'sunday.monthToDate': 'מתחילת החודש',
      'sunday.noOverBudget': 'אף קטגוריה לא חרגה.',
      'sunday.hygienePeople': '{n} שורות באנשים עם שמות לדוגמה',
      'sunday.hygieneGoals': '{n} יעדים עם טקסט לדוגמה',
      // Settings
      'settings.account': 'חשבון',
      'settings.sheet': 'גיליון',
      'settings.language': 'שפה',
      'settings.appearance': 'מראה',
      'settings.themeLight': '☀️ בהיר',
      'settings.themeDark': '🌙 כהה',
      'settings.themeAuto': '🔄 אוטומטי',
      'settings.pendingWrites': 'כתיבות בתור',
      'settings.about': 'אודות',
      'settings.sheetIdLabel': 'מזהה הגיליון',
      'settings.sheetIdPlaceholder': 'מתוך כתובת ה-Google Sheet',
      'settings.demoModeLabel': 'מצב הדגמה',
      'settings.demoOn': 'דלוק (נתוני הדגמה)',
      'settings.demoOff': 'כבוי (גיליון אמיתי)',
      'settings.switchAccount': 'החלף חשבון',
      'settings.signOut': 'התנתק',
      'settings.forceRefresh': 'רענן עכשיו',
      'settings.saveReload': 'שמור וטען מחדש',
      'settings.aboutBody': 'Family inc. dashboard · v0.1 · אב-טיפוס שלב 6',
      'settings.aboutNote': 'המידע יושב בגיליון Google שלך. הדף הזה הוא תצוגה מקומית.',
      'settings.demoModeStatus': 'מצב הדגמה',
      'settings.demoNoAccount': 'לא מחובר חשבון Google.',
      'settings.signedInAs': 'מחובר כ-{name}',
      'settings.notSignedIn': 'לא מחובר.',
      'settings.langHebrew': 'עברית',
      'settings.langEnglish': 'English',
      // Stale / offline
      'stale.offline': 'לא מקוון — נתונים מ-{when}',
      // Sign-in screen
      'signin.prompt': 'התחבר עם חשבון Google שיש לו גישה לגיליון <code>Family_OS</code> שלך.',
      'signin.button': 'התחבר עם Google',
      'signin.notConfigured': 'OAuth לא מוגדר',
      'signin.demoLine': 'או <a href="#" id="demo-link">נסה עם נתוני הדגמה</a>.',
      // Error toasts
      'toast.signinFailed': 'ההתחברות נכשלה: {err}',
      'toast.oauthNotConfigured': 'OAuth לא מוגדר — ראה README_SETUP.md',
      'toast.loadFailed': 'לא הצלחתי לטעון נתונים ואין מטמון זמין.',
      'toast.gapiLoadError': 'לא הצלחתי לטעון את Google API. בדוק את החיבור לאינטרנט.',
      'toast.gisLoadError': 'לא הצלחתי לטעון את Google Sign-In. בדוק את החיבור לאינטרנט.',
      'signin.gapiLoadError': 'שגיאה בטעינת Google API',
      'signin.gisLoadError': 'שגיאה בטעינת Google Sign-In',
      'toast.sheetIdInvalid': 'מזהה גיליון לא תקין — בדוק שהוא בפורמט הנכון.',
      'toast.sheetIdTestFailed': 'לא הצלחתי לאמת את מזהה הגיליון: {err}',
      'toast.demoPrefix': '(הדגמה) {label}',
      'toast.queuedOffline': 'נשמר בתור לא מקוון: {label}',
      'toast.queued': 'נשמר בתור: {label}',
      'toast.queueFull': 'התור מלא ({max}) — התחברו לאינטרנט כדי לסנכרן לפני שמירת פעולות נוספות',
      'toast.flushed': 'הוזרמו {n} פעולות מהתור',
      'toast.writesPaused': 'מבנה הגיליון השתנה — כתיבות מושהות (בדקו את כותרות העמודות)',
      // Action labels (used in toasts after write-back)
      'action.markedDone': 'בוצע: {title}',
      'action.doneN': '{n} בוצעו',
      'action.snoozedTo': 'נדחה ל-{date}: {title}',
      'action.snoozedN': '{n} נדחו ל-{date}',
      'action.noteAdded': 'הערה נוספה',
      'action.noteAddedN': 'הערה נוספה ל-{n}',
    },
    en: {
      'tabbar.today': 'Today',
      'tabbar.sunday': 'Sunday',
      'tabbar.settings': 'Settings',
      'section.todayList': 'For today',
      'section.calendar': 'Calendar',
      'section.comingUp': 'Coming up',
      'section.domains': 'Domains',
      'drawer.money': 'Money',
      'drawer.health': 'Health',
      'drawer.goals': 'Goals',
      'drawer.car': 'Car',
      'drawer.contracts': 'Subscriptions & contracts',
      'drawer.education': 'Education',
      'drawer.timeline': 'Timeline',
      'pill.overdue': 'overdue',
      'pill.dueToday': 'due today',
      'pill.allClear': 'Nothing urgent',
      'pill.sundayReady': 'Sunday briefing ready',
      'row.done': '✓ done',
      'row.snooze': '+ snooze',
      'row.note': '+ note',
      'desk.selected': '{n} selected',
      'desk.notePlaceholder': 'Write a note…',
      'snooze.tomorrow': 'Tomorrow',
      'snooze.in3': '+3d',
      'snooze.week': '1 week',
      'snooze.twoweeks': '2 weeks',
      'snooze.month': '1 month',
      'snooze.pickDate': 'Pick a date',
      'snooze.label': 'Snooze to…',
      'empty.nothingOnFire': 'Nothing on fire. ☕',
      'empty.nothingThisWeek': 'Nothing scheduled this week.',
      'empty.noEventsDay': 'No events.',
      'empty.noQueuedWrites': 'No queued writes.',
      'empty.next60Days': 'Nothing in the next two months.',
      'empty.noBudget': 'No budget yet.',
      'empty.noRecentTxns': 'No recent transactions.',
      'empty.noGoals': 'No goals yet.',
      'empty.noVehicle': 'No vehicle.',
      'empty.noRenewals': 'No renewals in the next two months.',
      'empty.noMilestones': 'Nothing in the selected range.',
      'empty.noUpcoming': 'No upcoming items.',
      'empty.noOverdue': 'No overdue items.',
      'empty.allClean': 'All clean.',
      'state.allGood': 'All good',
      'state.loading': 'Loading…',
      'cal.allDay': 'all day',
      'cal.today': 'Today',
      'cal.tomorrow': 'Tomorrow',
      'sheet.close': 'Close',
      'sheet.recentTxns': 'Recent transactions',
      'timeline.zoomLabel': 'Time range',
      'timeline.filterLabel': 'Filter by domain',
      'timeline.now': 'now',
      'timeline.zoom.1wk': '1wk',
      'timeline.zoom.1mo': '1mo',
      'timeline.zoom.3mo': '3mo',
      'timeline.zoom.1yr': '1yr',
      'timeline.zoom.5yr': '5yr',
      'timeline.cat.all': 'all',
      'timeline.cat.finance': 'finance',
      'timeline.cat.health': 'health',
      'timeline.cat.car': 'car',
      'timeline.cat.education': 'education',
      'timeline.cat.goals': 'goals',
      'timeline.cat.contracts': 'contracts',
      'timeline.cat.calendar': 'calendar',
      'timeline.cat.other': 'other',
      // Love-note (V3.7) — parent-to-parent ephemeral note
      'lovenote.heading': 'Note',
      'lovenote.inboundFrom': 'A note from {name}',
      'lovenote.composePlaceholder': 'Leave a note for {name}…',
      'lovenote.composeGeneric': 'Leave a note…',
      'lovenote.send': 'Send',
      'lovenote.clear': 'Clear',
      'lovenote.waiting': 'Waiting for {name}',
      'lovenote.sentToast': 'Note sent to {name}',
      'lovenote.clearedToast': 'Note cleared',
      'lovenote.failedToast': 'Couldn’t send — try again',
      'car.annualTest': 'Annual test',
      'car.insurance': 'Insurance',
      'car.license': 'License',
      'label.next': 'next:',
      'summary.upcoming': '{n} upcoming',
      'summary.active': '{n} active',
      'summary.over': '{n} over',
      'summary.within60': '{n} in next two months',
      'sunday.title': 'Sunday Briefing',
      'sunday.weekAhead': 'Week ahead',
      'sunday.remindersThisWeek': 'Reminders this week',
      'sunday.overdue': 'Overdue',
      'sunday.money': 'Money',
      'sunday.goals': 'Goals',
      'sunday.hygiene': 'Data hygiene',
      'sunday.monthToDate': 'Month-to-date',
      'sunday.noOverBudget': 'No categories over budget.',
      'sunday.hygienePeople': '{n} People row(s) using placeholder names',
      'sunday.hygieneGoals': '{n} Goal(s) using placeholder text',
      'settings.account': 'Account',
      'settings.sheet': 'Sheet',
      'settings.language': 'Language',
      'settings.appearance': 'Appearance',
      'settings.themeLight': '☀️ Light',
      'settings.themeDark': '🌙 Dark',
      'settings.themeAuto': '🔄 Auto',
      'settings.pendingWrites': 'Pending writes',
      'settings.about': 'About',
      'settings.sheetIdLabel': 'Sheet ID',
      'settings.sheetIdPlaceholder': 'from Google Sheet URL',
      'settings.demoModeLabel': 'Demo mode',
      'settings.demoOn': 'On (use mock data)',
      'settings.demoOff': 'Off (live Google Sheet)',
      'settings.switchAccount': 'Switch account',
      'settings.signOut': 'Sign out',
      'settings.forceRefresh': 'Force refresh',
      'settings.saveReload': 'Save & reload',
      'settings.aboutBody': 'Family inc. dashboard · v0.1 · Phase 6 prototype',
      'settings.aboutNote': 'Data lives in your Google Sheet. This page is a local view.',
      'settings.demoModeStatus': 'Demo mode',
      'settings.demoNoAccount': 'No Google account is connected.',
      'settings.signedInAs': 'Signed in as {name}',
      'settings.notSignedIn': 'Not signed in.',
      'settings.langHebrew': 'עברית',
      'settings.langEnglish': 'English',
      'stale.offline': 'Offline — data from {when}',
      'signin.prompt': 'Sign in with the Google account that has access to your <code>Family_OS</code> sheet.',
      'signin.button': 'Sign in with Google',
      'signin.notConfigured': 'OAuth not configured',
      'signin.demoLine': 'Or <a href="#" id="demo-link">try with demo data</a>.',
      'toast.signinFailed': 'Sign-in failed: {err}',
      'toast.oauthNotConfigured': 'OAuth not configured — see README_SETUP.md',
      'toast.loadFailed': 'Could not load data and no cache available.',
      'toast.gapiLoadError': 'Could not load Google sign-in. Check your connection.',
      'toast.gisLoadError': 'Could not load Google sign-in. Check your connection.',
      'signin.gapiLoadError': 'Could not load Google sign-in',
      'signin.gisLoadError': 'Could not load Google sign-in',
      'toast.sheetIdInvalid': 'Invalid Sheet ID — check the format and try again.',
      'toast.sheetIdTestFailed': 'Could not verify Sheet ID: {err}',
      'toast.demoPrefix': '(demo) {label}',
      'toast.queuedOffline': 'Queued offline: {label}',
      'toast.queued': 'Queued: {label}',
      'toast.queueFull': 'Queue full ({max}) — reconnect to sync before queuing more',
      'toast.flushed': 'Flushed {n} queued action(s)',
      'toast.writesPaused': 'Sheet structure changed — writes paused (check the column headers)',
      'action.markedDone': '{title} → done',
      'action.doneN': '{n} → done',
      'action.snoozedTo': '{title} → {date}',
      'action.snoozedN': '{n} → {date}',
      'action.noteAdded': 'Note added',
      'action.noteAddedN': 'Note added to {n}',
    },
  };
  function currentLang() {
    return document.documentElement.lang === 'en' ? 'en' : 'he';
  }
  function t(key, vars) {
    const dict = STRINGS[currentLang()] || STRINGS.he;
    let s = dict[key];
    if (s == null) s = key; // fail visibly if a key is missing
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        s = s.split(`{${k}}`).join(String(v));
      }
    }
    return s;
  }
  // Walks the DOM once at boot and replaces text content of any element tagged
  // with data-i18n="<key>". The English text in index.html is a fallback that
  // shows if JS fails to run. data-i18n-html does innerHTML — use only for keys
  // we control (e.g. signin.demoLine which embeds a known anchor).
  function applyChromeStrings() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const v = t(key);
      if (v != null && v !== key) el.textContent = v;
    });
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const key = el.dataset.i18nHtml;
      const v = t(key);
      if (v != null && v !== key) el.innerHTML = v;
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.dataset.i18nPlaceholder;
      const v = t(key);
      if (v != null && v !== key) el.setAttribute('placeholder', v);
    });
    // data-i18n-aria → aria-label, so icon-only / unlabelled controls (the sheet
    // close ✕, the coming-up scroll region, the snooze date picker + note textarea)
    // are named in the active language declaratively — replacing the hand-rolled
    // setAttribute calls the earlier slices scattered through boot() (V3.8).
    document.querySelectorAll('[data-i18n-aria]').forEach(el => {
      const key = el.dataset.i18nAria;
      const v = t(key);
      if (v != null && v !== key) el.setAttribute('aria-label', v);
    });
  }

  // ---------------- State ----------------
  const state = {
    user: null,           // {email, name}
    token: null,
    data: null,           // parsed sheet data
    cachedAt: null,
    tab: 'today',
    pendingWrites: [],
    queueFullWarned: false,   // one-shot: warn once at the cap, reset after a flush
    today: stripTime(new Date()),
    tokenClient: null,
    gapiReady: false,
    gisReady: false,
    activeSheet: null,        // domain key of the open bottom-sheet, or null
    sheetReturnFocus: null,   // domain key whose tile regains focus on close (NOT a
                              // node ref — a bg reload rebuilds the grid; re-resolve live)
    timeline: { zoom: '3mo', filter: 'all' },  // V3.6 cross-domain timeline view state
    loveNote: { inbound: null, outbound: null },  // V3.7 — note FROM partner / note I left
    loveNoteSending: false,                       // one-shot guard while a PUT/DELETE is in flight
    driftWarned: false,                           // Lane C — one-shot "writes paused" toast on header drift
    deskSelection: new Set(),                     // V3.3 — selected desk row numbers (strings); ephemeral,
                                                  // cleared on every renderToday rebuild + after each batch
  };

  // ---------------- Utilities ----------------
  function stripTime(d) {
    const x = new Date(d);
    x.setHours(0, 0, 0, 0);
    return x;
  }
  function daysBetween(a, b) {
    return Math.round((stripTime(a) - stripTime(b)) / (1000 * 60 * 60 * 24));
  }
  // Intl-based formatters (Hebrew locale). Defined as helpers so RTL copy "just works".
  const _ilsFmt = new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });
  const _dateHEFmt = new Intl.DateTimeFormat('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const _dateHEShortFmt = new Intl.DateTimeFormat('he-IL', { day: '2-digit', month: '2-digit' });

  function formatILS(n) {
    if (n == null || isNaN(n)) return '';
    return _ilsFmt.format(Math.round(n));
  }
  function formatDateHE(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return _dateHEFmt.format(d);
  }
  // Back-compat wrappers — old call sites still work, now wired to Hebrew formatting.
  function fmtDate(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return _dateHEShortFmt.format(d);
  }
  // Sub-shorthand: just "D.M" (e.g. "7.6") for the Sunday header date range.
  // Intl emits a trailing dot in he-IL for this style; we hand-format to skip it.
  function fmtDateShort(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return `${d.getDate()}.${d.getMonth() + 1}`;
  }
  function fmtILS(n) { return formatILS(n); }
  // Wraps an amount string in an isolated bidi span so ₪ + Hebrew text don't reorder.
  function amountHtml(n) {
    const s = formatILS(n);
    if (!s) return '';
    return `<span class="amount bidi-amount">${escapeHtml(s)}</span>`;
  }
  function fmtISO(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
  // Full local ISO datetime (with T, no timezone — naive local, matching the
  // engine). Used for the machine stamps DoneAt + WriteQueue_Tombstone: the
  // T-form stays a TEXT cell in Sheets, so it round-trips byte-exact and the
  // 6h tombstone window keeps hour resolution (a date-only tombstone looks
  // hours old the moment it's written — that race guard was dead, SPEC §8.3).
  function fmtISOts(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    const p = (n) => String(n).padStart(2, '0');
    return `${fmtISO(d)}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }
  // Lane C: col-D (Due Date) is a real Sheets date cell, so the API renders it
  // back in the he-IL locale (DD/MM/YYYY or DD.MM.YYYY) even when we WRITE ISO.
  // parseDate therefore reads BOTH: ISO (incl. the ISO-T stamps + calendar dates)
  // first — unambiguous — then the locale day-first render. A bare `new Date()`
  // alone returns Invalid for "25/06/2026", which would silently drop a snoozed/
  // recurrence-bumped reminder from Today; this is the read half of that fix.
  function parseDate(v) {
    if (!v) return null;
    if (v instanceof Date) return isNaN(v) ? null : v;
    if (typeof v === 'number') {
      // Excel serial — used if we ever roundtrip from xlsx, but Sheets API
      // returns formatted strings, so this branch is rare.
      return new Date(Math.round((v - 25569) * 86400 * 1000));
    }
    const s = String(v).trim();
    if (!s) return null;
    // ISO YYYY-MM-DD (optionally with a time/stamp) — let Date parse it.
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
      const d = new Date(s);
      return isNaN(d) ? null : d;
    }
    // he-IL date render: DD/MM/YYYY or DD.MM.YYYY (day-first; the Sheet locale).
    const m = s.match(/^(\d{1,2})[./](\d{1,2})[./](\d{2,4})$/);
    if (m) {
      const dd = +m[1], mm = +m[2];
      const yy = +m[3] < 100 ? 2000 + +m[3] : +m[3];
      const d = new Date(yy, mm - 1, dd);
      // Reject impossible dates (e.g. 31/02): Date rolls them over, so verify.
      return (isNaN(d) || d.getMonth() !== mm - 1 || d.getDate() !== dd) ? null : d;
    }
    const d = new Date(s);   // last resort (other ISO-ish shapes)
    return isNaN(d) ? null : d;
  }
  function flagFor(daysUntil, status) {
    if (status === 'Done' || status === 'Skipped') return '';
    if (daysUntil == null || isNaN(daysUntil)) return '';
    if (daysUntil < 0) return 'OVERDUE';
    if (daysUntil <= 1) return 'FIRE TODAY';
    if (daysUntil <= 7) return 'WEEK OUT';
    if (daysUntil <= 30) return 'MONTH OUT';
    return '';
  }
  function flagEmoji(f) {
    return { 'OVERDUE': '🔴', 'FIRE TODAY': '🟠', 'WEEK OUT': '🟡', 'MONTH OUT': '🟢' }[f] || '·';
  }
  function flagClass(f) {
    return { 'OVERDUE': 'flag-OVERDUE', 'FIRE TODAY': 'flag-FIRE', 'WEEK OUT': 'flag-WEEK', 'MONTH OUT': 'flag-MONTH' }[f] || '';
  }
  function duePhrase(daysUntil) {
    if (daysUntil == null) return '';
    if (currentLang() === 'he') {
      // Hebrew grammar: singular (יום), dual (יומיים), plural (ימים).
      if (daysUntil < 0) {
        const abs = -daysUntil;
        if (abs === 1) return 'באיחור של יום';
        if (abs === 2) return 'באיחור של יומיים';
        return `באיחור של ${abs} ימים`;
      }
      if (daysUntil === 0) return 'להיום';
      if (daysUntil === 1) return 'מחר';
      if (daysUntil === 2) return 'בעוד יומיים';
      return `בעוד ${daysUntil} ימים`;
    }
    if (daysUntil < 0) return `overdue by ${-daysUntil}d`;
    if (daysUntil === 0) return 'due today';
    if (daysUntil === 1) return 'due tomorrow';
    return `in ${daysUntil}d`;
  }
  function toast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2200);
  }
  function colLetter(n) {
    // 1 → A, 27 → AA
    let s = '';
    while (n > 0) {
      const r = (n - 1) % 26;
      s = String.fromCharCode(65 + r) + s;
      n = Math.floor((n - 1) / 26);
    }
    return s;
  }

  // ---------------- Auth ----------------
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src; s.async = true; s.defer = true;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Failed to load ' + src));
      document.head.appendChild(s);
    });
  }

  async function initAuth() {
    if (cfg.DEMO_MODE) return;
    if (!cfg.CLIENT_ID || cfg.CLIENT_ID.startsWith('PASTE_')) return;

    try {
      await loadScript('https://apis.google.com/js/api.js');
    } catch {
      const btn = document.getElementById('signin-btn');
      if (btn) { btn.textContent = t('signin.gapiLoadError'); btn.disabled = true; }
      toast(t('toast.gapiLoadError'));
      return;
    }
    await new Promise((resolve) => gapi.load('client', resolve));
    await gapi.client.init({ discoveryDocs: [DISCOVERY] });
    state.gapiReady = true;

    try {
      await loadScript('https://accounts.google.com/gsi/client');
    } catch {
      const btn = document.getElementById('signin-btn');
      if (btn) { btn.textContent = t('signin.gisLoadError'); btn.disabled = true; }
      toast(t('toast.gisLoadError'));
      return;
    }
    state.tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: cfg.CLIENT_ID,
      scope: SCOPES,
      callback: (resp) => {
        if (resp.error) { toast(t('toast.signinFailed', { err: resp.error })); return; }
        state.token = resp;
         localStorage.setItem(TOKEN_KEY, JSON.stringify({ access_token: resp.access_token, expires_at: Date.now() + (resp.expires_in * 1000) }));
        afterSignIn();
      },
    });
    state.gisReady = true;

    // Restore session token if still valid (avoids forcing sign-in every reload).
    const saved = localStorage.getItem(TOKEN_KEY);
    if (saved) {
      try {
        const t = JSON.parse(saved);
        if (t.expires_at > Date.now() + 60000) {
          gapi.client.setToken({ access_token: t.access_token });
          state.token = t;
          afterSignIn();
        }
      } catch {}
    }
  }

  function requestSignIn() {
    if (!state.tokenClient) {
      toast(t('toast.oauthNotConfigured'));
      return;
    }
    state.tokenClient.requestAccessToken({ prompt: 'consent' });
  }

  function signOut() {
    localStorage.removeItem(TOKEN_KEY);
    state.token = null;
    state.user = null;
    if (window.google?.accounts?.oauth2) {
      google.accounts.oauth2.revoke(gapi.client.getToken()?.access_token, () => {});
    }
    showSignIn();
  }

  // D3 — switch the signed-in Google account for real (SPEC §7.6): force the account
  // chooser (prompt:'select_account', not 'consent'), so the OTHER parent can sign in.
  // Identity is always the live OAuth session, never a label flip — the token callback
  // → afterSignIn re-resolves the new email → UserMap name, so col-M LastDoneBy stays
  // truthful. Cancelling the chooser is a no-op (the callback never fires; the current
  // session is untouched). We deliberately do NOT revoke the prior token: revoke() drops
  // the whole user+client GRANT, which would both force the other parent to re-consent
  // next time AND kill the new session if the user re-picks the SAME account (a fresh
  // token over the same grant). The superseded token is dropped from the app and expires.
  function switchAccount() {
    if (!state.tokenClient) { toast(t('toast.oauthNotConfigured')); return; }
    state.tokenClient.requestAccessToken({ prompt: 'select_account' });
  }

  async function afterSignIn() {
    // Who signed in? userinfo.email scope → email; the display name comes
    // from Settings.UserMap once the Sheet loads (SPEC §7.6: Google sign-in
    // → Settings.UserMap → display name). cfg.USERS stays as the offline /
    // pre-Settings fallback.
    try {
      const token = gapi.client.getToken()?.access_token;
      const resp = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const info = resp.ok ? await resp.json() : {};
      const email = (info.email || '').toLowerCase();
      state.user = { email: email || 'unknown', name: resolveDisplayName(email) };
    } catch (e) {
      console.warn('Could not resolve signed-in identity', e);
      const emails = Object.keys(cfg.USERS || {});
      state.user = { email: emails[0] || 'unknown', name: (cfg.USERS || {})[emails[0]] || 'You' };
    }
    showApp();
    await loadAll();
    // Settings tab is loaded now — upgrade the display name if UserMap knows us.
    if (state.user) state.user.name = resolveDisplayName(state.user.email);
  }

  // Settings.UserMap (email → display name) → cfg.USERS fallback → 'You'.
  function resolveDisplayName(email) {
    const fromSheet = state.data?.settings?.userMap?.[email];
    if (fromSheet) return fromSheet;
    const fromCfg = (cfg.USERS || {})[email];
    if (fromCfg) return fromCfg;
    // Unknown signer: fall back to the first configured user (pre-M2 behavior)
    const emails = Object.keys(cfg.USERS || {});
    return (cfg.USERS || {})[emails[0]] || 'You';
  }

  // ---------------- Data load ----------------
  async function loadAll() {
    if (cfg.DEMO_MODE) {
      const resp = await fetch('mock_data.json');
      const json = await resp.json();
      state.data = parseAll(json);
      state.cachedAt = new Date();
      state.loveNote = state.data.loveNote || { inbound: null, outbound: null };  // V3.7 demo fixture
      renderAll();
      return;
    }
    try {
      const tabs = cfg.TABS;
      // Order matters — keep in sync with `named` below.
      const ranges = [
        `${tabs.reminders}!A:O`,
        `${tabs.calendarEvents}!A:H`,
        `${tabs.people}!A:I`,
        `${tabs.finance_bdgt}!A:I`,
        `${tabs.finance_txns}!A:I`,
        `${tabs.goals}!A:I`,
        `${tabs.health}!A:I`,
        `${tabs.education}!A:I`,
        `${tabs.car}!A:I`,
        `${tabs.contracts}!A:I`,
        `${tabs.settings || 'Settings'}!A:B`,
      ];
      const resp = await gapi.client.sheets.spreadsheets.values.batchGet({
        spreadsheetId: cfg.SHEET_ID,
        ranges,
        valueRenderOption: 'UNFORMATTED_VALUE',
        dateTimeRenderOption: 'FORMATTED_STRING',
      });
      const named = {
        reminders: resp.result.valueRanges[0].values || [],
        calendarEvents: resp.result.valueRanges[1].values || [],
        people: resp.result.valueRanges[2].values || [],
        finance_bdgt: resp.result.valueRanges[3].values || [],
        finance_txns: resp.result.valueRanges[4].values || [],
        goals: resp.result.valueRanges[5].values || [],
        health: resp.result.valueRanges[6].values || [],
        education: resp.result.valueRanges[7].values || [],
        car: resp.result.valueRanges[8].values || [],
        contracts: resp.result.valueRanges[9].values || [],
        settings: resp.result.valueRanges[10]?.values || [],
      };
      state.data = parseAll(named);
      state.cachedAt = new Date();
      localStorage.setItem(CACHE_KEY, JSON.stringify({ raw: named, at: state.cachedAt.toISOString() }));
      applySheetLang();
      renderAll();
      await flushQueue();
      loadLoveNote();   // V3.7 — the appliance endpoint, not the Sheet; re-renders the slot when it lands
    } catch (e) {
      console.error('Live load failed', e);
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const { raw, at } = JSON.parse(cached);
        state.data = parseAll(raw);
        state.cachedAt = new Date(at);
        document.getElementById('stale-badge').hidden = false;
        document.getElementById('stale-badge').textContent = t('stale.offline', { when: state.cachedAt.toLocaleString() });
        renderAll();
      } else {
        toast(t('toast.loadFailed'));
      }
    }
  }

  // Settings.lang is the cross-device DEFAULT chrome language; an explicit
  // local toggle (localStorage.familyinc.lang) always wins (DESIGN §7).
  function applySheetLang() {
    let saved = null;
    try { saved = localStorage.getItem('familyinc.lang'); } catch {}
    if (saved) return; // personal preference wins
    const sheetLang = state.data?.settings?.lang;
    if ((sheetLang === 'en' || sheetLang === 'he') && sheetLang !== currentLang()) {
      document.documentElement.setAttribute('lang', sheetLang);
      document.documentElement.setAttribute('dir', sheetLang === 'en' ? 'ltr' : 'rtl');
      applyChromeStrings();
    }
  }

  // ---------------- Parsers ----------------
  // Sheet tab → header row (row 1) + data rows (row 2+).
  // Each parsed row carries its 1-based sheet row number as `_row` so writes
  // can target the right cell.
  function rowsToObjects(rows) {
    if (!rows || rows.length < 2) return [];
    const headers = rows[0];
    return rows.slice(1).map((r, i) => {
      const o = { _row: i + 2 };
      headers.forEach((h, j) => { o[h] = r[j] ?? null; });
      return o;
    });
  }

  // V3.2 forward seam (consumed by V3.4's 3-day calendar): collapse a candle-
  // lighting Calendar-Events row to the canonical source token 'shabbat' so the
  // calendar can tag it (🕯) without re-deriving. No-op on current data — candle-
  // lighting is a digest-only Hebcal line (automation/daily_digest.py), not a
  // Calendar-Events row — so this only fires if such a row is ever added. Matched
  // PRECISELY, not broadly: only an explicit 'shabbat' Source token OR a candle-
  // lighting title. NOT the generic 'hebcal' feed marker (it would mis-tag every
  // chag/parsha/omer row) and NOT the bare word 'שבת' (would over-tag a Shabbat-
  // dinner event).
  const _SHABBAT_SOURCE_RE = /\bshabbat\b/i;
  const _SHABBAT_TITLE_RE = /הדלקת נרות|candle[\s-]?lighting/i;
  function normalizeCalendarSource(rawSource, title) {
    if (_SHABBAT_SOURCE_RE.test(rawSource) || _SHABBAT_TITLE_RE.test(title)) return 'shabbat';
    return rawSource;
  }

  function parseAll(named) {
    const reminders = rowsToObjects(named.reminders).map(r => {
      const due = parseDate(r['Due Date']);
      const daysUntil = due ? daysBetween(due, state.today) : null;
      const status = r['Status'] || 'Pending';
      return {
        _row: r._row,
        title: r['Title'] || '',
        domain: r['Domain'] || '',
        owner: r['Owner'] || '',
        due,
        leads: (r['Lead Times'] ?? r['Lead Times (days)'] ?? '').toString().split(',').map(x => parseInt(x, 10)).filter(x => !isNaN(x)),
        recurrence: r['Recurrence'] || 'One-off',
        status,
        lastSent: parseDate(r['Last Sent']),
        channel: r['Channel'] || '',
        notes: r['Notes'] || '',
        daysUntil,
        flag: flagFor(daysUntil, status),
        // Phase 6.1 columns (cols M, N, O) — may be blank on legacy sheets
        lastDoneBy: (r['LastDoneBy'] || '').trim(),
        doneAt: parseDate(r['DoneAt']),
        writeQueueTombstone: parseDate(r['WriteQueue_Tombstone']),
      };
    });
    const calendarEvents = rowsToObjects(named.calendarEvents).map(r => {
      const title = r['Title'] || '';
      return {
        _row: r._row,
        date: parseDate(r['Date']),
        start: r['Start'] || '',
        end: r['End'] || '',
        title,
        owner: r['Owner'] || '',
        source: normalizeCalendarSource(r['Source'] || '', title),
        location: r['Location'] || '',
        notes: r['Notes'] || '',
      };
    });
    const people = rowsToObjects(named.people);
    // Settings tab (SPEC §6.4): Key|Value rows — keys containing '@' build
    // UserMap (email → display name); key 'lang' is the chrome default.
    const settings = { userMap: {}, lang: null };
    (named.settings || []).slice(1).forEach(row => {
      const key = String(row?.[0] ?? '').trim();
      const value = String(row?.[1] ?? '').trim();
      if (!key || !value) return;
      if (key.includes('@')) settings.userMap[key.toLowerCase()] = value;
      else if (key.toLowerCase() === 'lang') settings.lang = value;
    });
    const budget = rowsToObjects(named.finance_bdgt).map(r => ({
      category: r['Category'],
      target: parseFloat(r['Monthly Target (ILS)']) || 0,
      actual: parseFloat(r['Actual (current month)']) || 0,
      pct: parseFloat(r['% of Target']) || 0,
      // Drop the header echo and the TOTAL row: TOTAL is a SUM of the categories,
      // so including it would double-count the money-summary totals, list a
      // phantom "TOTAL" line, and miscount over-budget categories. The weekly
      // briefing's section_money skips it the same way (keep the two surfaces in
      // agreement — both read this one tab).
    })).filter(b => b.category && b.category !== 'Category' && b.category !== 'TOTAL');
    const txns = rowsToObjects(named.finance_txns).map(r => ({
      date: parseDate(r['Date']),
      account: r['Account'],
      desc: r['Description'],
      amount: parseFloat(r['Amount (ILS)']) || 0,
      category: r['Category'],
    }));
    const goals = rowsToObjects(named.goals).map(r => ({
      _row: r._row,
      goal: r['Goal'],
      owner: r['Owner'],
      horizon: r['Horizon'],
      targetDate: parseDate(r['Target Date']),
      milestone: r['90-Day Milestone'],
      pct: parseFloat(r['% Complete']) || 0,
      status: r['Status'],
    })).filter(g => g.goal);
    const health = rowsToObjects(named.health).map(r => ({
      person: r['Person'],
      provider: r['Provider'],
      specialty: r['Specialty'],
      nextDue: parseDate(r['Next Due']),
      action: r['Action Needed'],
    })).filter(h => h.person);
    const education = rowsToObjects(named.education).map(r => ({
      child: r['Child'],
      institution: r['Institution'],
      nextDate: parseDate(r['Next Key Date']),
      type: r['Type'],
      action: r['Action Needed'],
    })).filter(e => e.child);
    const car = rowsToObjects(named.car).map(r => ({
      vehicle: r['Vehicle'],
      plate: r['Plate'],
      test: parseDate(r['Annual Test (Rishui)']),
      insurance: parseDate(r['Insurance Renewal']),
      license: parseDate(r['License Expiry']),
    })).filter(c => c.vehicle);
    const contracts = rowsToObjects(named.contracts).map(r => ({
      contract: r['Contract'],
      provider: r['Provider'],
      type: r['Type'],
      renewal: parseDate(r['Renewal Date']),
      monthly: parseFloat(r['Monthly Cost (ILS)']) || 0,
    })).filter(c => c.contract);

    // V3.7 love-note: live data comes from the appliance endpoint (loadLoveNote),
    // NOT the Sheet; in DEMO_MODE the fixture rides along in mock_data.json.
    const loveNote = named.loveNote || null;
    // Lane C: resolve the Reminders write columns by header name (row 1) so a
    // drifted/inserted column pauses writes instead of corrupting the wrong cell.
    const reminderCols = resolveReminderCols(named.reminders && named.reminders[0]);
    return { reminders, calendarEvents, people, budget, txns, goals, health, education, car, contracts, settings, loveNote, reminderCols };
  }

  // Build {name → 1-based column index} for the columns the dashboard writes,
  // from the actual header row. ok=false when any required write column is absent
  // (a renamed/removed/shifted-out header) → writes pause.
  function resolveReminderCols(headerRow) {
    const byName = {};
    (headerRow || []).forEach((h, i) => {
      const key = String(h ?? '').trim().toLowerCase();
      if (key && !(key in byName)) byName[key] = i + 1;
    });
    const cols = {};
    let ok = true;
    REMINDER_WRITE_COLS.forEach(name => {
      const idx = byName[name.toLowerCase()];
      if (idx) cols[name] = idx; else ok = false;
    });
    return { cols, ok };
  }

  // ---------------- Render ----------------
  function renderAll() {
    // Header date is chrome — route through currentLang() so the toggle
    // actually flips the most prominent label on the screen. he-IL and en-GB
    // both render DD/MM date order, which matches Israeli reading habits in
    // either language.
    const _hdrLocale = currentLang() === 'en' ? 'en-GB' : 'he-IL';
    document.getElementById('header-date').textContent = state.today.toLocaleDateString(_hdrLocale, { weekday: 'long', day: 'numeric', month: 'long' });
    // Lane C: surface a header-drift "writes paused" once (re-arms when resolved).
    if (state.data && state.data.reminderCols && !state.data.reminderCols.ok) {
      if (!state.driftWarned) { state.driftWarned = true; toast(t('toast.writesPaused')); }
    } else {
      state.driftWarned = false;
    }
    renderStatusPill();
    renderLoveNote();
    renderToday();
    render3DayCalendar();
    renderComingUp();
    renderPortfolios();
    renderSunday();
    renderSettings();
  }

  // ---------------- Status pill ----------------
  // Shared count helper (V3.2). The status pill consumes it now; V3.3's desk
  // reuses the same numbers (deskCount = overdue + fire-today) so the pill and
  // the desk can never disagree. Reads the parsed r.flag, exactly as the deleted
  // inline banner/pill filters did.
  function computeCounts() {
    const r = (state.data && state.data.reminders) || [];
    const overdue = r.filter(x => x.flag === 'OVERDUE').length;
    const today = r.filter(x => x.flag === 'FIRE TODAY').length;
    return { overdue, today, deskCount: overdue + today };
  }

  // The pill is a single 3-tier signal (overdue > today > clear), always visible
  // (clear is a resting state, never hidden) — plus a loading tier before data
  // lands so it never reads as a premature "all clear". data-tier carries color;
  // the count + label carry the meaning (never color-only, DESIGN §8). The glyph
  // is decorative (aria-hidden in the markup); the count is a mono span.
  function setStatusPill({ tier, glyph = '', count = null, label = '' }) {
    const pill = document.getElementById('status-pill');
    const glyphEl = document.getElementById('status-pill-glyph');
    const countEl = document.getElementById('status-pill-count');
    const labelEl = document.getElementById('status-pill-text');
    if (!pill || !glyphEl || !countEl || !labelEl) return;
    pill.setAttribute('data-tier', tier);
    glyphEl.textContent = glyph;
    glyphEl.hidden = !glyph;   // an empty glyph must not reserve a flex gap (loading tier)
    if (count == null) {
      countEl.hidden = true;
      countEl.textContent = '';
    } else {
      countEl.hidden = false;
      countEl.textContent = String(count);
    }
    labelEl.textContent = label;
  }
  function renderStatusPill() {
    if (!state.data) { setStatusPill({ tier: 'loading', label: t('state.loading') }); return; }
    const { overdue, today } = computeCounts();
    if (overdue > 0) {
      setStatusPill({ tier: 'overdue', glyph: '🔴', count: overdue, label: t('pill.overdue') });
    } else if (today > 0) {
      setStatusPill({ tier: 'today', glyph: '🟠', count: today, label: t('pill.dueToday') });
    } else if (state.today.getDay() === 0) { // Sunday — clear tier, briefing-ready label
      setStatusPill({ tier: 'clear', glyph: '✅', label: t('pill.sundayReady') });
    } else {
      setStatusPill({ tier: 'clear', glyph: '✅', label: t('pill.allClear') });
    }
  }

  // ---------------- Love-note (V3.7) ----------------
  // The one dashboard datum that is neither the Sheet nor the outbox: a parent-
  // to-parent ephemeral note over a small authenticated appliance endpoint
  // (automation/love_note_server.py), fronted by a Cloudflare Tunnel. ONE note
  // per direction, 24h-or-on-replacement; it shows on the recipient's NEXT open
  // — no push, and no "seen"/delivery signal back to the sender (SPEC §3.7).
  // Text-only here; voice is a frozen phase-2 (SPEC §4 carve-out).

  // The endpoint base (no trailing slash), or null when unconfigured — in which
  // case the whole slot stays hidden (never promise an affordance that's dead).
  function loveNoteBase() {
    const u = String(cfg.LOVENOTE_URL || '').trim();
    if (!u || u.startsWith('PASTE_')) return null;
    return u.replace(/\/+$/, '');
  }
  // The live Google access_token the server re-verifies against Google userinfo.
  function loveNoteToken() {
    try {
      return (window.gapi && gapi.client && gapi.client.getToken && gapi.client.getToken()?.access_token)
        || state.token?.access_token || null;
    } catch { return null; }
  }
  // Is the signed-in account actually one of the two parents in UserMap (with a
  // distinct partner to address)? A non-parent viewer with Sheet access would
  // otherwise be shown a live composer the server 403s — a dead affordance.
  function loveNoteIsParent() {
    const um = (state.data && state.data.settings && state.data.settings.userMap) || {};
    const me = ((state.user && state.user.email) || '').toLowerCase();
    if (!me) return false;
    const keys = Object.keys(um).map(e => e.toLowerCase());
    return keys.includes(me) && keys.some(e => e !== me);
  }
  // Demo always shows the component (so the card + composer can be reviewed);
  // live needs the endpoint configured AND the signer to be a known parent.
  function loveNoteEnabled() {
    if (cfg.DEMO_MODE) return true;
    return !!(loveNoteBase() && state.user && loveNoteToken() && loveNoteIsParent());
  }
  // The other adult — the note's recipient. Live: the UserMap entry that isn't
  // me. Fallback (incl. demo, where no one is signed in): whoever wrote to me /
  // whom I last wrote to / the configured pair.
  function loveNotePartnerName() {
    const um = (state.data && state.data.settings && state.data.settings.userMap) || {};
    const me = ((state.user && state.user.email) || '').toLowerCase();
    if (me) { for (const [email, name] of Object.entries(um)) { if (email.toLowerCase() !== me) return name; } }
    if (state.loveNote.inbound?.from) return state.loveNote.inbound.from;
    if (state.loveNote.outbound?.to) return state.loveNote.outbound.to;
    const vals = Object.values(cfg.USERS || {});
    return vals[vals.length - 1] || '';
  }
  // A short, localized "when" for the note timestamp (time if today, else date).
  function loveNoteWhen(iso) {
    const d = parseDate(iso);
    if (!d) return '';
    const locale = currentLang() === 'en' ? 'en-GB' : 'he-IL';
    return daysBetween(d, state.today) === 0
      ? d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
      : d.toLocaleDateString(locale, { day: '2-digit', month: '2-digit' });
  }

  // Fetch the note pair {inbound, outbound} for the signed-in user from the
  // appliance endpoint, then re-render the slot. Failures degrade quiet.
  async function loadLoveNote() {
    if (cfg.DEMO_MODE) {
      state.loveNote = (state.data && state.data.loveNote) || { inbound: null, outbound: null };
      renderLoveNote();
      return;
    }
    const base = loveNoteBase(), token = loveNoteToken();
    if (!base || !token) { renderLoveNote(); return; }
    try {
      const resp = await fetch(`${base}/lovenote`, { headers: { Authorization: `Bearer ${token}` } });
      if (resp.ok) state.loveNote = await resp.json();
    } catch (e) {
      console.warn('love-note load failed', e);   // slot just stays empty
    }
    renderLoveNote();
  }

  function renderLoveNote() {
    const slot = document.getElementById('love-note-slot');
    if (!slot) return;
    // Preserve an in-progress draft across this full-innerHTML rebuild: a
    // background re-render (e.g. tapping done/snooze on a reminder while
    // composing) must not wipe unsent text the user is still typing.
    const prevInput = document.getElementById('love-note-input');
    const draft = prevInput ? prevInput.value : null;
    const hadFocus = !!prevInput && document.activeElement === prevInput;
    if (!loveNoteEnabled()) { slot.hidden = true; slot.innerHTML = ''; return; }
    const partner = loveNotePartnerName();
    const inbound = state.loveNote.inbound;
    const outbound = state.loveNote.outbound;
    const placeholder = partner ? t('lovenote.composePlaceholder', { name: partner }) : t('lovenote.composeGeneric');
    // Inbound card: hidden when empty. The 💌 glyph + the "from {name}" label +
    // the wash/border carry it — never color alone (DESIGN §8).
    const inboundCard = inbound ? `
      <div class="love-note-card">
        <div class="love-note-from"><span aria-hidden="true">💌</span> ${escapeHtml(t('lovenote.inboundFrom', { name: inbound.from || partner }))}</div>
        <div class="love-note-text">${escapeHtml(inbound.text || '')}</div>
        ${inbound.sent_at ? `<div class="love-note-when num">${escapeHtml(loveNoteWhen(inbound.sent_at))}</div>` : ''}
      </div>` : '';
    const waiting = outbound
      ? `<span class="love-note-waiting">${escapeHtml(t('lovenote.waiting', { name: partner || outbound.to || '' }))}${outbound.sent_at ? ' · ' + escapeHtml(loveNoteWhen(outbound.sent_at)) : ''}</span>`
      : '';
    const clearBtn = outbound ? `<button class="action-btn danger" id="love-note-clear" type="button">${escapeHtml(t('lovenote.clear'))}</button>` : '';
    slot.innerHTML = `
      <div class="love-note">
        <h2 class="love-note-heading"><span aria-hidden="true">💌</span> ${escapeHtml(t('lovenote.heading'))}</h2>
        ${inboundCard}
        <div class="love-note-compose">
          <textarea id="love-note-input" class="love-note-input" rows="2" maxlength="500"
            placeholder="${escapeHtml(placeholder)}" aria-label="${escapeHtml(placeholder)}">${escapeHtml(outbound?.text || '')}</textarea>
          <div class="love-note-actions">
            ${waiting}
            ${clearBtn}
            <button class="action-btn primary" id="love-note-send" type="button">${escapeHtml(t('lovenote.send'))}</button>
          </div>
        </div>
      </div>`;
    slot.hidden = false;
    const send = document.getElementById('love-note-send');
    if (send) send.addEventListener('click', () => handleSendLoveNote());
    const clear = document.getElementById('love-note-clear');
    if (clear) clear.addEventListener('click', () => handleClearLoveNote());
    // Restore a divergent unsent draft the rebuild would otherwise have wiped.
    const input = document.getElementById('love-note-input');
    if (input && draft != null && draft !== input.value) {
      input.value = draft;
      if (hadFocus) { input.focus(); try { const n = draft.length; input.setSelectionRange(n, n); } catch (_) {} }
    }
  }

  async function handleSendLoveNote() {
    if (state.loveNoteSending) return;
    const input = document.getElementById('love-note-input');
    const text = ((input && input.value) || '').trim();
    if (!text) return;
    const partner = loveNotePartnerName();
    if (cfg.DEMO_MODE) {
      state.loveNote.outbound = { to: partner, text, sent_at: new Date().toISOString() };
      toast(t('toast.demoPrefix', { label: t('lovenote.sentToast', { name: partner }) }));
      renderLoveNote();
      return;
    }
    const base = loveNoteBase(), token = loveNoteToken();
    if (!base || !token) return;
    state.loveNoteSending = true;
    try {
      const resp = await fetch(`${base}/lovenote`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (resp.ok) { toast(t('lovenote.sentToast', { name: partner })); await loadLoveNote(); }
      else toast(t('lovenote.failedToast'));
    } catch (e) {
      console.warn('love-note send failed', e);
      toast(t('lovenote.failedToast'));
    } finally {
      state.loveNoteSending = false;
    }
  }

  async function handleClearLoveNote() {
    if (state.loveNoteSending) return;
    if (cfg.DEMO_MODE) {
      state.loveNote.outbound = null;
      toast(t('toast.demoPrefix', { label: t('lovenote.clearedToast') }));
      renderLoveNote();
      return;
    }
    const base = loveNoteBase(), token = loveNoteToken();
    if (!base || !token) return;
    state.loveNoteSending = true;
    try {
      const resp = await fetch(`${base}/lovenote`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
      if (resp.ok) { toast(t('lovenote.clearedToast')); await loadLoveNote(); }
      else toast(t('lovenote.failedToast'));
    } catch (e) {
      console.warn('love-note clear failed', e);
      toast(t('lovenote.failedToast'));
    } finally {
      state.loveNoteSending = false;
    }
  }

  // ---------------- Sparkline + KPI ----------------
  function renderSparkline(svgEl, points) {
    if (!svgEl) return;
    if (!points || points.length < 2) { svgEl.innerHTML = ''; return; }
    const w = 80, h = 24, pad = 2;
    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = max - min || 1;
    const step = (w - pad * 2) / (points.length - 1);
    const coords = points.map((p, i) => {
      const x = pad + i * step;
      const y = h - pad - ((p - min) / range) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    svgEl.innerHTML = `<polyline points="${coords}" />`;
  }
  function renderKpi(drawerName, value, trend) {
    const kpiEl = document.getElementById(`${drawerName}-kpi`);
    if (!kpiEl) return;
    if (value == null || value === '') {
      kpiEl.textContent = '';
      kpiEl.classList.remove('kpi-pos', 'kpi-neg');
      return;
    }
    kpiEl.textContent = value;
    kpiEl.classList.toggle('kpi-pos', trend === 'pos');
    kpiEl.classList.toggle('kpi-neg', trend === 'neg');
  }

  // ---------------- Goal bright-line viz ----------------
  // Renders a small Beeminder-style chart:
  //   - target band (straight line from targetStart at t=0 → targetEnd at t=100%)
  //   - actual line (from 0 at start to `current` at pctTimeElapsed)
  //   - safety bands tinted around the target line
  function renderGoalLine(svgEl, { targetStart = 0, targetEnd = 100, current = 0, pctTimeElapsed = 0 } = {}) {
    if (!svgEl) return;
    const w = 100, h = 40, pad = 2;
    const yFor = (v) => {
      const clamped = Math.max(0, Math.min(100, v));
      return h - pad - (clamped / 100) * (h - pad * 2);
    };
    const xNow = Math.max(0, Math.min(100, pctTimeElapsed));
    const yT0 = yFor(targetStart);
    const yT1 = yFor(targetEnd);
    const yA0 = yFor(targetStart);
    const yA1 = yFor(current);
    // Safety bands (±5% of target line). Build as polygons spanning full width.
    const targetTopBand = `M 0,${yFor(Math.min(100, targetStart + 5))} L 100,${yFor(Math.min(100, targetEnd + 5))} L 100,0 L 0,0 Z`;
    const okBand        = `M 0,${yFor(Math.min(100, targetStart + 5))} L 100,${yFor(Math.min(100, targetEnd + 5))} L 100,${yFor(Math.max(0, targetEnd - 5))} L 0,${yFor(Math.max(0, targetStart - 5))} Z`;
    const badBand       = `M 0,${yFor(Math.max(0, targetStart - 5))} L 100,${yFor(Math.max(0, targetEnd - 5))} L 100,${h} L 0,${h} Z`;
    svgEl.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svgEl.setAttribute('preserveAspectRatio', 'none');
    svgEl.innerHTML = `
      <path class="band-ok"   d="${targetTopBand}" />
      <path class="band-warn" d="${okBand}" />
      <path class="band-bad"  d="${badBand}" />
      <polyline class="target-line" points="0,${yT0} 100,${yT1}" />
      <polyline class="actual-line" points="0,${yA0} ${xNow},${yA1}" />
      <circle class="now-dot" cx="${xNow}" cy="${yA1}" r="2" />
    `;
  }

  // ---------------- Desk (V3.3 select-to-act) ----------------
  // The Today desk: OVERDUE + FIRE-TODAY reminders as checkbox-semantics rows.
  // Selecting ≥1 reveals a sticky batch bar (done / snooze / note) that fans out
  // to ONE applyWrites batch. Selection is ephemeral — cleared on every rebuild
  // (a background reload can re-number _row) and after each batch.
  function renderToday() {
    state.deskSelection.clear();
    const list = state.data.reminders
      .filter(r => r.flag === 'OVERDUE' || r.flag === 'FIRE TODAY')
      .sort((a, b) => (a.daysUntil ?? 9e9) - (b.daysUntil ?? 9e9));
    const el = document.getElementById('today-list');
    if (!list.length) {
      el.innerHTML = `<div class="empty-caught-up">${escapeHtml(t('empty.nothingOnFire'))} <span class="empty-date">${escapeHtml(formatDateHE(state.today))}</span></div>`;
      syncDeskActionbar();
      return;
    }
    el.innerHTML = list.map(deskRow).join('');
    attachRowHandlers(el);
    syncDeskActionbar();
  }

  // A desk row is a checkbox (keyboard-operable; non-color selection = a ✓ box +
  // wash + aria-checked). NO inline done/snooze/note — action lives in the shared
  // batch bar so one tap acts on the whole selection.
  function deskRow(r) {
    const emoji = flagEmoji(r.flag);
    const cls = flagClass(r.flag);
    return `<div class="row desk-row" data-row="${r._row}" role="checkbox" aria-checked="false" tabindex="0">
      <span class="desk-check" aria-hidden="true"></span>
      <div class="desk-row-body">
        <div class="row-top">
          <span class="row-title"><span class="flag ${cls}" aria-hidden="true">${emoji}</span> ${escapeHtml(r.title)}</span>
          <span class="row-meta">${duePhrase(r.daysUntil)}</span>
        </div>
        ${r.notes ? `<div class="row-note">${escapeHtml(r.notes)}</div>` : ''}
      </div>
    </div>`;
  }

  // Selection toggles (click + Space/Enter). V3.3 replaced the .expanded/.snoozing
  // accordion with desk selection — the inline per-row actions are gone.
  function attachRowHandlers(container) {
    container.querySelectorAll('.desk-row[data-row]').forEach(rowEl => {
      rowEl.addEventListener('click', () => toggleDeskSelection(rowEl));
      rowEl.addEventListener('keydown', (ev) => {
        if (ev.key === ' ' || ev.key === 'Enter') { ev.preventDefault(); toggleDeskSelection(rowEl); }
      });
    });
  }
  function toggleDeskSelection(rowEl) {
    const row = rowEl.dataset.row;
    const sel = state.deskSelection;
    const on = !sel.has(row);
    if (on) sel.add(row); else sel.delete(row);
    rowEl.classList.toggle('selected', on);
    rowEl.setAttribute('aria-checked', String(on));
    syncDeskActionbar();
  }
  // Show/hide the batch bar + count from the live selection; collapse the snooze/
  // note sub-rows whenever the selection empties.
  function syncDeskActionbar() {
    const bar = document.getElementById('desk-actionbar');
    if (!bar) return;
    const n = state.deskSelection.size;
    bar.hidden = n === 0;
    const countEl = document.getElementById('desk-sel-count');
    if (countEl) countEl.textContent = n ? t('desk.selected', { n }) : '';
    if (n === 0) collapseDeskSubrows();
  }
  function collapseDeskSubrows() {
    const s = document.getElementById('desk-snooze-row'); if (s) s.hidden = true;
    const nr = document.getElementById('desk-note-row'); if (nr) nr.hidden = true;
  }
  // Toggle one sub-row (snooze chips OR the note composer), never both at once.
  function toggleDeskSubrow(which) {
    const s = document.getElementById('desk-snooze-row');
    const nr = document.getElementById('desk-note-row');
    if (!s || !nr) return;
    if (which === 'snooze') { const open = s.hidden; nr.hidden = true; s.hidden = !open; }
    else { const open = nr.hidden; s.hidden = true; nr.hidden = !open; if (open) document.getElementById('desk-note-input')?.focus(); }
  }
  function selectedReminders() {
    return [...state.deskSelection].map(findReminder).filter(Boolean);
  }
  // After a batch, focus would otherwise fall to <body> (the batch bar that held
  // it is now hidden + the desk re-rendered). Move it to a stable desk anchor so a
  // keyboard/SR user keeps their place. Programmatic focus after a pointer tap
  // won't trip :focus-visible, so touch users see no stray ring.
  function focusDeskAfterBatch() {
    const list = document.getElementById('today-list');
    if (!list) return;
    const firstRow = list.querySelector('.desk-row');
    if (firstRow) { firstRow.focus(); return; }
    list.setAttribute('tabindex', '-1');
    list.focus();
  }

  // ---------------- Coming-up strip (V3.3) ----------------
  // A read-only ±30-day horizontal scroll band with a now-marker. Two sources,
  // date-sorted: WEEK-OUT/MONTH-OUT reminders (the future side) + calendar events
  // (past 30d ↔ +30d, minus today/+1/+2 which the 3-day strip owns). The desk owns
  // overdue/today reminders, so they are NOT repeated here (PO call 2026-06-26:
  // the back-scroll shows past EVENTS only). Opens positioned at "now"; scroll
  // back for the past, forward for what's coming. No write affordance.
  function renderComingUp() {
    const el = document.getElementById('coming-up-strip');
    if (!el) return;
    const items = comingUpItems();
    if (!items.length) {
      el.innerHTML = `<div class="empty">${escapeHtml(t('empty.noUpcoming'))}</div>`;
      return;
    }
    let html = '', placed = false;
    items.forEach(it => {
      if (!placed && it.daysUntil >= 0) { html += comingUpNowMarker(); placed = true; }
      html += comingUpChip(it);
    });
    if (!placed) html += comingUpNowMarker();   // everything is past → marker at the end
    el.innerHTML = html;
    scrollComingUpToNow(el);
  }

  function comingUpItems() {
    const out = [];
    // Future reminders only (WEEK-OUT/MONTH-OUT = daysUntil 2..30). Overdue +
    // fire-today live on the desk; Done/Skipped carry no flag.
    (state.data.reminders || []).forEach(r => {
      if (!r.due) return;
      if (r.flag === 'WEEK OUT' || r.flag === 'MONTH OUT') {
        out.push({ date: r.due, daysUntil: r.daysUntil, kind: 'reminder', glyph: flagEmoji(r.flag), title: r.title });
      }
    });
    // Calendar events across ±30d, EXCEPT today/+1/+2 (owned by the 3-day strip).
    (state.data.calendarEvents || []).forEach(e => {
      if (!e.date) return;
      const du = daysBetween(e.date, state.today);
      if (du < -30 || du > 30 || (du >= 0 && du <= 2)) return;
      out.push({ date: e.date, daysUntil: du, kind: 'event', glyph: '📆', title: e.title, shabbat: e.source === 'shabbat' });
    });
    return out.sort((a, b) => a.date - b.date);
  }

  function comingUpChip(it) {
    const glyph = it.shabbat ? '🕯' : it.glyph;
    return `<div class="coming-up-chip coming-up-${it.kind}${it.shabbat ? ' shabbat' : ''}">
      <div class="cu-top"><span class="cu-glyph" aria-hidden="true">${glyph}</span><span class="cu-date num">${escapeHtml(fmtDate(it.date))}</span></div>
      <div class="cu-title">${escapeHtml(it.title)}</div>
      <div class="cu-due num">${escapeHtml(relDayPhrase(it.daysUntil))}</div>
    </div>`;
  }
  function comingUpNowMarker() {
    return `<div class="coming-up-now" data-now="1"><span class="cu-now-bar" aria-hidden="true"></span><span class="cu-now-label">${escapeHtml(t('timeline.now'))}</span></div>`;
  }
  // Relative-day phrase for the band: future reuses duePhrase (today/tomorrow/in
  // Nd); past reads "yesterday / N days ago" (a past EVENT is not "overdue").
  function relDayPhrase(daysUntil) {
    if (daysUntil == null) return '';
    if (daysUntil >= 0) return duePhrase(daysUntil);
    const abs = -daysUntil;
    if (currentLang() === 'he') {
      if (abs === 1) return 'אתמול';
      if (abs === 2) return 'לפני יומיים';
      return `לפני ${abs} ימים`;
    }
    if (abs === 1) return 'yesterday';
    return `${abs}d ago`;
  }
  // Position the now-marker near the inline-start so the future is the default
  // view and the past is a scroll-back — horizontal only (never scrollIntoView,
  // which would scroll the PAGE to this below-the-fold strip on load). Uses a
  // bounding-rect delta + scrollBy (the modern unified RTL scrollLeft model:
  // 0 = inline-start, negative toward inline-end), so it works in he-RTL + en-LTR.
  function scrollComingUpToNow(el) {
    requestAnimationFrame(() => {
      const marker = el.querySelector('[data-now="1"]');
      if (!marker) return;
      const isRtl = getComputedStyle(el).direction === 'rtl';
      const er = el.getBoundingClientRect();
      const mr = marker.getBoundingClientRect();
      const PEEK = 48;   // leave a sliver of the immediate past visible past the marker
      const delta = isRtl ? (mr.right - er.right) + PEEK : (mr.left - er.left) - PEEK;
      if (Math.abs(delta) > 1) el.scrollBy({ left: delta, behavior: 'auto' });
    });
  }

  // Minutes-since-midnight for an 'HH:MM' start; all-day ('') sorts first as -1.
  // Robust to an un-padded hour ('9:00') a hand-edited Sheet row might carry,
  // which a lexical string sort would mis-order.
  function calMinutes(s) {
    if (!s) return -1;
    const [h, m] = String(s).split(':');
    return (+h || 0) * 60 + (+m || 0);
  }

  // V3.4: the calendar slot is a 3-day scroll-snap strip (today, +1, +2),
  // replacing the single-day list. Exactly 3 panes ALWAYS render so an empty day
  // never collapses the strip and the horizontal snap keeps stable geometry.
  // Read-only — no data-row, no write affordances; events are edited at their
  // source, the strip is a glance surface. Days 3–7 live in the coming-up/Next-7
  // list (📆-tagged), so this stays today+2 with no overlap.
  function render3DayCalendar() {
    const el = document.getElementById('today-cal-strip');
    if (!el) return;
    const locale = currentLang() === 'en' ? 'en-GB' : 'he-IL';
    el.innerHTML = [0, 1, 2].map(offset => {
      const day = new Date(state.today);
      day.setDate(day.getDate() + offset);
      const events = state.data.calendarEvents
        .filter(e => e.date && daysBetween(e.date, day) === 0)
        .sort((a, b) => calMinutes(a.start) - calMinutes(b.start)); // all-day ('') sorts first
      const body = events.length
        ? events.map(renderCalEvent).join('')
        : `<div class="empty">${escapeHtml(t('empty.noEventsDay'))}</div>`;
      return `<div class="cal-day">
        <div class="cal-day-head">
          <span class="cal-day-name">${escapeHtml(dayLabel(offset, day, locale))}</span>
          <span class="cal-day-date num">${escapeHtml(fmtDate(day))}</span>
        </div>
        ${body}
      </div>`;
    }).join('');
  }

  // Day-head label: today / tomorrow / the weekday name for +2 (locale-aware).
  function dayLabel(offset, day, locale) {
    if (offset === 0) return t('cal.today');
    if (offset === 1) return t('cal.tomorrow');
    return day.toLocaleDateString(locale, { weekday: 'long' });
  }

  // One read-only calendar-event card. A Shabbat line (the V3.2 'shabbat' source
  // seam — also covers erev-chag candle-lighting, same 🕯 treatment) gets a 🕯
  // glyph (aria-hidden, decorative — the title + border carry the meaning) + a
  // non-color inline-start border, never hue alone (DESIGN §8). Times are mono (.num).
  function renderCalEvent(e) {
    const isShabbat = e.source === 'shabbat';
    const time = e.start
      ? escapeHtml(e.start) + (e.end ? '–' + escapeHtml(e.end) : '')
      : escapeHtml(t('cal.allDay'));
    return `<div class="row cal-event${isShabbat ? ' shabbat' : ''}">
      <div class="row-top">
        <span class="row-title">${isShabbat ? '<span aria-hidden="true">🕯 </span>' : ''}${escapeHtml(e.title)}</span>
        <span class="row-meta cal-time num">${time}</span>
      </div>
      ${e.location ? `<div class="row-note">${escapeHtml(e.location)}${e.owner ? ' · ' + escapeHtml(e.owner) : ''}</div>` : ''}
    </div>`;
  }

  // ---------------- Drawers ----------------
  // ---------------- Portfolios + bottom-sheet ----------------
  // V3.5: the six domain accordions become a grid of portfolio TILES (glanceable
  // faces) that open ONE shared, data-driven bottom-sheet on tap — never six
  // panels. Money is the hero (overall-% donut + category bar + 7-day sparkline);
  // Health shows initials-avatars with non-color urgency; Goals a simple % bar
  // (the bright-line lives in the sheet, D8); Car/Contracts a next-date count.
  // Education has no Today tile (its data stays parsed, folds into the V3.6
  // timeline). Tiles are <button>s (native keyboard + role); status is never
  // color-only — text + glyph carry it (DESIGN §8).
  function renderPortfolios() {
    const grid = document.getElementById('portfolio-grid');
    if (!grid) return;
    grid.innerHTML = [moneyTile(), timelineTile(), healthTile(), goalsTile(), carTile(), contractsTile()].join('');
    // The money sparkline needs a live <svg> (renderSparkline writes into it).
    renderSparkline(document.getElementById('money-tile-spark'), txnTrend7d());
    grid.querySelectorAll('.tile[data-portfolio]').forEach(tile => {
      tile.addEventListener('click', () => openSheet(tile.dataset.portfolio));
    });
    // A sheet left open across a background reload rebuilds from fresh state.
    if (state.activeSheet) refreshSheetBody();
  }

  // ---- domain selectors (shared by the tile face + the sheet body) ----
  function upcomingHealth() {
    return state.data.health
      .filter(h => h.nextDue && daysBetween(h.nextDue, state.today) <= 60 && daysBetween(h.nextDue, state.today) >= -30)
      .sort((a, b) => a.nextDue - b.nextDue);
  }
  function upcomingRenewals() {
    return state.data.contracts
      .filter(c => c.renewal && daysBetween(c.renewal, state.today) <= 60 && daysBetween(c.renewal, state.today) >= -30)
      .sort((a, b) => a.renewal - b.renewal);
  }
  function moneyTotals() {
    const b = state.data.budget;
    const target = b.reduce((s, x) => s + x.target, 0);
    const actual = b.reduce((s, x) => s + x.actual, 0);
    return { target, actual, over: b.filter(x => x.pct > 1.0), pct: target ? Math.round(100 * actual / target) : 0 };
  }
  function carNextDate() {
    const car = state.data.car[0];
    if (!car) return null;
    return [car.test, car.insurance, car.license].filter(Boolean).sort((a, b) => a - b)[0] || null;
  }
  function goalsAvgPct() {
    const g = state.data.goals;
    return g.length ? Math.round(g.reduce((s, x) => s + (x.pct || 0), 0) / g.length) : null;
  }

  // ---- tile faces ----
  function moneyTile() {
    const m = moneyTotals();
    const status = m.over.length
      ? `<span class="tile-flag" aria-hidden="true">▲</span> ${escapeHtml(t('summary.over', { n: m.over.length }))}`
      : escapeHtml(t('state.allGood'));
    return `<button class="tile tile-money" data-portfolio="money" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.money'))}</span>
        <span class="tile-status${m.over.length ? ' is-warn' : ''}">${status}</span>
      </div>
      <div class="tile-money-viz">
        ${donut(m.pct)}
        <div class="tile-money-side">
          <div class="tile-amount">${amountHtml(m.actual)} <span class="tile-amount-of">/ ${amountHtml(m.target)}</span></div>
          ${catBar(state.data.budget)}
          <svg class="sparkline" id="money-tile-spark" viewBox="0 0 80 24"></svg>
        </div>
      </div>
    </button>`;
  }
  function healthTile() {
    const up = upcomingHealth();
    const status = up.length ? t('summary.upcoming', { n: up.length }) : t('state.allGood');
    const avatars = up.slice(0, 5).map(healthAvatar).join('');
    return `<button class="tile" data-portfolio="health" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.health'))}</span>
        <span class="tile-status${up.length ? ' is-warn' : ''}">${escapeHtml(status)}</span>
      </div>
      <div class="avatar-row">${avatars || `<span class="tile-allgood" aria-hidden="true">✓</span>`}</div>
    </button>`;
  }
  function goalsTile() {
    const g = state.data.goals;
    const avg = goalsAvgPct();
    const status = t('summary.active', { n: g.length });
    const body = g.length
      ? `<div class="goal-bar" aria-hidden="true"><span class="goal-bar-fill" style="inline-size:${avg}%"></span></div>
         <div class="tile-sub num">${avg}%</div>`
      : `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;
    return `<button class="tile" data-portfolio="goals" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.goals'))}</span>
        <span class="tile-status">${escapeHtml(status)}</span>
      </div>
      ${body}
    </button>`;
  }
  function carTile() {
    const nd = carNextDate();
    const days = nd ? daysBetween(nd, state.today) : null;
    const warn = days != null && days < 14;
    // Warn carries a glyph + a due PHRASE (overdue/today/soon) — never color alone.
    // Pre-escaped here, so it's interpolated raw below.
    const status = nd
      ? (warn ? `<span class="tile-flag" aria-hidden="true">▲</span> ${escapeHtml(duePhrase(days))}`
              : `${escapeHtml(t('label.next'))} ${escapeHtml(formatDateHE(nd))}`)
      : '—';
    return `<button class="tile" data-portfolio="car" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.car'))}</span>
        <span class="tile-status${warn ? ' is-warn' : ''}">${status}</span>
      </div>
      <div class="tile-kpi num">${days != null ? Math.abs(days) + 'd' : '—'}</div>
    </button>`;
  }
  function contractsTile() {
    const n = upcomingRenewals().length;
    const status = n ? t('summary.within60', { n }) : t('state.allGood');
    return `<button class="tile" data-portfolio="contracts" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.contracts'))}</span>
        <span class="tile-status${n ? ' is-warn' : ''}">${escapeHtml(status)}</span>
      </div>
      <div class="tile-kpi num">${n || '—'}</div>
    </button>`;
  }

  // ---- tile viz primitives (all aria-hidden; meaning lives in the adjacent text) ----
  // Single-ring donut: arc = pct of circumference; the % numeral inside carries the
  // meaning (so the ring is non-color-only); >100% reads 'over' via numeral + ▲.
  function donut(pct) {
    const r = 26, c = 2 * Math.PI * r;
    const frac = Math.max(0, Math.min(1, (pct || 0) / 100));
    return `<svg class="donut${pct > 100 ? ' donut-over' : ''}" viewBox="0 0 64 64" aria-hidden="true">
      <circle class="donut-track" cx="32" cy="32" r="${r}" />
      <circle class="donut-fill" cx="32" cy="32" r="${r}" transform="rotate(-90 32 32)" stroke-dasharray="${(frac * c).toFixed(1)} ${c.toFixed(1)}" />
      <text class="donut-pct" x="32" y="33" text-anchor="middle" dominant-baseline="middle">${Math.round(pct || 0)}%</text>
    </svg>`;
  }
  // Proportional bar of the top categories by spend — informational, not urgency,
  // so neutral fills are fine (over-budget is flagged with ▲ in the sheet).
  function catBar(budget) {
    const cats = (budget || []).filter(b => b.actual > 0).sort((a, b) => b.actual - a.actual).slice(0, 6);
    if (!cats.length) return '';
    const total = cats.reduce((s, b) => s + b.actual, 0) || 1;
    const segs = cats.map((b, i) => `<span class="cat-seg cat-seg-${i % 4}" style="flex:${(b.actual / total).toFixed(3)}"></span>`).join('');
    return `<div class="cat-bar" aria-hidden="true">${segs}</div>`;
  }
  // Initials avatar (NO photo — no stored media) + a non-color urgency badge: a
  // glyph + a day-count (3 buckets: overdue / ≤14d / later), never color alone.
  function healthAvatar(h) {
    const initials = (h.person || '?').trim().slice(0, 2);
    const d = daysBetween(h.nextDue, state.today);
    const bucket = d < 0 ? 'over' : d <= 14 ? 'soon' : 'ok';
    const glyph = { over: '🔴', soon: '⚠', ok: '·' }[bucket];
    return `<span class="avatar avatar-${bucket}" title="${escapeHtml(h.person)}">
      <span class="avatar-initials">${escapeHtml(initials)}</span>
      <span class="avatar-badge"><span aria-hidden="true">${glyph}</span><span class="num">${Math.abs(d)}d</span></span>
    </span>`;
  }

  // ---- the shared bottom-sheet body, per domain (reuses the accordions' detail
  // logic: kv lists, recent-txns, the goal bright-line). Rebuilt on every open and
  // on background reload — one instance, never six. ----
  function buildSheet(domain) {
    switch (domain) {
      case 'money': return moneySheet();
      case 'health': return healthSheet();
      case 'goals': return goalsSheet();
      case 'car': return carSheet();
      case 'contracts': return contractsSheet();
      case 'timeline': return timelineSheet();
      default: return '';
    }
  }
  function moneySheet() {
    const budgetRows = state.data.budget.map(b => `
      <div class="kv"><span>${escapeHtml(b.category)}${b.pct > 1.0 ? ' <span class="tile-flag" aria-hidden="true">▲</span>' : ''}</span><span class="v">${amountHtml(b.actual)} / ${amountHtml(b.target)} (${Math.round(b.pct * 100)}%)</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noBudget'))}</div>`;
    const recent = (state.data.txns || []).filter(tx => tx.date && isSpendTxn(tx)).sort((a, b) => b.date - a.date).slice(0, 10);
    const txnRows = recent.map(tx => `
      <div class="kv"><span>${escapeHtml(formatDateHE(tx.date))} · ${escapeHtml(tx.desc || tx.account || '')}</span><span class="v">${amountHtml(tx.amount)}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noRecentTxns'))}</div>`;
    return `${budgetRows}<div class="sheet-sub">${escapeHtml(t('sheet.recentTxns'))}</div>${txnRows}`;
  }
  function healthSheet() {
    return upcomingHealth().map(h => `
      <div class="kv"><span>${escapeHtml(h.person)} · ${escapeHtml(h.specialty || h.provider || '')}</span><span class="v">${escapeHtml(formatDateHE(h.nextDue))}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.next60Days'))}</div>`;
  }
  function goalsSheet() {
    return state.data.goals.map((g, i) => `
      <div class="kv"><span>${escapeHtml(g.goal)} <span class="row-meta">· ${escapeHtml(g.owner || '')}</span></span><span class="v num">${g.pct}%</span></div>
      <svg class="goal-line" id="sheet-goal-line-${i}" viewBox="0 0 100 40" preserveAspectRatio="none"></svg>
      ${g.milestone ? `<div class="row-note" style="margin:-2px 0 6px">${escapeHtml(t('label.next'))} ${escapeHtml(g.milestone)}</div>` : ''}
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;
  }
  function drawSheetGoalLines() {
    state.data.goals.forEach((g, i) => {
      const svg = document.getElementById(`sheet-goal-line-${i}`);
      if (svg) renderGoalLine(svg, { targetStart: 0, targetEnd: 100, current: g.pct, pctTimeElapsed: goalPctTimeElapsed(g) });
    });
  }
  function carSheet() {
    const car = state.data.car[0];
    if (!car) return `<div class="empty">${escapeHtml(t('empty.noVehicle'))}</div>`;
    const rows = [[t('car.annualTest'), car.test], [t('car.insurance'), car.insurance], [t('car.license'), car.license]]
      .filter(([, d]) => d)
      .map(([k, d]) => `<div class="kv"><span>${escapeHtml(k)}</span><span class="v">${escapeHtml(formatDateHE(d))} (${escapeHtml(duePhrase(daysBetween(d, state.today)))})</span></div>`)
      .join('');
    return rows || `<div class="empty">${escapeHtml(t('empty.noVehicle'))}</div>`;
  }
  function contractsSheet() {
    return upcomingRenewals().map(c => `
      <div class="kv"><span>${escapeHtml(c.contract)} · ${escapeHtml(c.provider || '')}</span><span class="v">${escapeHtml(formatDateHE(c.renewal))}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noRenewals'))}</div>`;
  }
  // Headline metric shown in the sheet head (reuses renderKpi).
  function sheetKpi(domain) {
    if (domain === 'money') { const m = moneyTotals(); return { value: m.target ? `${m.pct}%` : '', trend: m.pct > 100 ? 'neg' : 'pos' }; }
    if (domain === 'health') { const n = upcomingHealth().length; return { value: n ? String(n) : '', trend: n ? 'neg' : 'pos' }; }
    if (domain === 'goals') { const a = goalsAvgPct(); return { value: a == null ? '' : `${a}%`, trend: 'pos' }; }
    if (domain === 'car') { const nd = carNextDate(); const d = nd ? daysBetween(nd, state.today) : null; return { value: d == null ? '' : `${d}d`, trend: d != null && d < 14 ? 'neg' : 'pos' }; }
    if (domain === 'contracts') { const n = upcomingRenewals().length; return { value: n ? String(n) : '', trend: n ? 'neg' : 'pos' }; }
    if (domain === 'timeline') { const n = buildTimelineItems().filter(i => i.daysUntil >= 0).length; return { value: n ? String(n) : '', trend: 'pos' }; }
    return { value: '', trend: null };
  }

  // ---- sheet open/close machinery (focus-trap + scroll-lock + focus-return) ----
  function openSheet(domain) {
    state.activeSheet = domain;
    // Each open lands on the documented default lens (DESIGN §2/§9.13: zoom 3mo,
    // all categories) rather than a stale zoom/filter from a previous open.
    if (domain === 'timeline') state.timeline = { zoom: '3mo', filter: 'all' };
    state.sheetReturnFocus = domain;   // re-resolved to a live tile on close (grid may rebuild)
    document.getElementById('sheet-title').textContent = t('drawer.' + domain);
    refreshSheetBody();
    document.getElementById('sheet-scrim').hidden = false;
    const sheet = document.getElementById('sheet');
    sheet.hidden = false;
    requestAnimationFrame(() => sheet.classList.add('open'));   // slide up from hidden
    document.body.classList.add('sheet-open');                  // scroll-lock the page
    const app = document.getElementById('app');
    if (app) app.inert = true;          // background out of the AT/focus tree (aria-modal alone doesn't)
    document.getElementById('sheet-close').focus();
    document.addEventListener('keydown', onSheetKeydown, true);
  }
  function refreshSheetBody() {
    const domain = state.activeSheet;
    if (!domain) return;
    const body = document.getElementById('sheet-body');
    if (body) {
      const st = body.scrollTop;            // preserve read position + the focused control across a bg-reload rebuild
      const tlSel = _timelineFocusSelector();  // the timeline is the only sheet with focusables in its body
      body.innerHTML = buildSheet(domain);
      body.scrollTop = st;
      if (tlSel) { const b = body.querySelector(tlSel); if (b) b.focus(); }
    }
    if (domain === 'goals') drawSheetGoalLines();
    if (domain === 'timeline') wireTimeline();
    const k = sheetKpi(domain);
    renderKpi('sheet', k.value, k.trend);
  }
  // If a timeline zoom/filter control holds focus, return a selector to re-find it
  // after #sheet-body is rebuilt — so a background reload doesn't drop keyboard focus.
  function _timelineFocusSelector() {
    const a = document.activeElement;
    if (!a || !a.dataset) return null;
    if (a.dataset.tlZoom) return `[data-tl-zoom="${a.dataset.tlZoom}"]`;
    if (a.dataset.tlFilter) return `[data-tl-filter="${a.dataset.tlFilter}"]`;
    return null;
  }
  function closeSheet() {
    if (!state.activeSheet) return;
    const sheet = document.getElementById('sheet');
    sheet.classList.remove('open');
    sheet.hidden = true;
    document.getElementById('sheet-scrim').hidden = true;
    document.body.classList.remove('sheet-open');
    const app = document.getElementById('app');
    if (app) app.inert = false;
    document.removeEventListener('keydown', onSheetKeydown, true);
    state.activeSheet = null;
    const dom = state.sheetReturnFocus;
    state.sheetReturnFocus = null;
    // Re-resolve the launching tile live — a background reload may have rebuilt the
    // grid, detaching the node we opened from; query the fresh button by domain.
    const tile = dom && document.querySelector(`.tile[data-portfolio="${dom}"]`);
    if (tile) tile.focus();
  }
  function onSheetKeydown(e) {
    if (e.key === 'Escape') { e.preventDefault(); closeSheet(); return; }
    if (e.key !== 'Tab') return;
    const sheet = document.getElementById('sheet');
    const f = sheet.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  // Card-settlement mirror lines (an immediate-debit card's spend also lands on the
  // bank statement as a merchant-less settlement) are excluded from raw-transaction
  // SPEND views — the per-merchant card line is the real spend, counted once; summing
  // the mirror too would ~double it. Mirrors automation/lib/categorize.EXCLUDED_CATEGORIES.
  function isSpendTxn(tx) { return tx.category !== 'Card Settlement'; }

  // Build a last-7-day spending series from transactions (signed-amount sum per day).
  // Falls back to null if no transactions are available.
  function txnTrend7d() {
    const txns = state.data.txns || [];
    if (!txns.length) return null;
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(state.today);
      d.setDate(d.getDate() - i);
      const sum = txns
        .filter(t => t.date && daysBetween(t.date, d) === 0 && isSpendTxn(t))
        .reduce((s, t) => s + Math.abs(t.amount || 0), 0);
      days.push(sum);
    }
    if (days.every(v => v === 0)) return null;
    return days;
  }

  // ---------------- Cross-domain timeline (V3.6) ----------------
  // A read-only chronological flattening of every dated row across the Sheet's
  // domains into one time axis, opened from the Timeline portfolio tile. The two
  // pure functions below are the ratified contract (graduated to SPEC §7.6):
  // domainCategory (the filter map) + buildTimelineItems (the milestone-inclusion
  // rule). Read-only — items are edited at their source tab, never here.

  // Filterable categories. The reminder Domain is free text (SPEC §6.1 col B:
  // Car/Health/Education/Finance/Contracts/Goals/Other) and maps near-identity
  // (lowercased); calendar/other are assigned by source. Anything unrecognised
  // falls to 'other' and is STILL shown — never dropped.
  const TIMELINE_CATEGORIES = ['finance', 'health', 'car', 'education', 'goals', 'contracts', 'calendar', 'other'];
  function domainCategory(domain) {
    const d = String(domain || '').trim().toLowerCase();
    return TIMELINE_CATEGORIES.includes(d) ? d : 'other';
  }

  // Zoom rungs (exponential 1wk→5yr). The visible window is today−tail … today+days;
  // a short recent-past tail gives the now-marker context without burying the future.
  const TIMELINE_ZOOMS = [
    { key: '1wk', days: 7 },
    { key: '1mo', days: 31 },
    { key: '3mo', days: 92 },
    { key: '1yr', days: 366 },
    { key: '5yr', days: 1830 },
  ];
  const TIMELINE_PAST_TAIL = 14;   // days of recent past kept above the now-marker
  const TIMELINE_MAX_DAYS = 1830;  // +5y horizon (5×366 — a deliberate round over-approximation of 5y); the hard inclusion ceiling

  // The milestone-inclusion rule (SPEC §7.6): one item per dated field across every
  // domain — done/skipped/archived reminders, undated rows, and dates outside
  // [−tail, +5y] excluded. An unmapped reminder Domain still appears (→ 'other').
  function buildTimelineItems() {
    const d = state.data;
    if (!d) return [];
    const items = [];
    const add = (date, title, category, meta) => {
      if (!(date instanceof Date) || isNaN(date)) return;
      if (!String(title || '').trim()) return;   // a dated row with no label is not a useful milestone
      const daysUntil = daysBetween(date, state.today);
      if (daysUntil < -TIMELINE_PAST_TAIL || daysUntil > TIMELINE_MAX_DAYS) return;
      items.push({ date, daysUntil, title, category, meta: meta || '' });
    };
    (d.reminders || []).forEach(r => {
      const st = String(r.status || '').toLowerCase();
      if (st === 'done' || st === 'skipped') return;   // terminal statuses — matches flagFor (Sent/Snoozed/Overdue stay)
      add(r.due, r.title, domainCategory(r.domain), r.owner);
    });
    (d.calendarEvents || []).forEach(e => add(e.date, e.title, 'calendar', e.start || ''));
    (d.goals || []).forEach(g => add(g.targetDate, g.goal, 'goals', g.pct != null ? g.pct + '%' : ''));
    (d.health || []).forEach(h => add(h.nextDue, [h.person, h.specialty || h.provider].filter(Boolean).join(' · '), 'health', h.action));
    (d.car || []).forEach(c => {
      add(c.test, t('car.annualTest'), 'car', c.vehicle);
      add(c.insurance, t('car.insurance'), 'car', c.vehicle);
      add(c.license, t('car.license'), 'car', c.vehicle);
    });
    (d.education || []).forEach(e => add(e.nextDate, [e.child, e.type].filter(Boolean).join(' · '), 'education', e.action));
    (d.contracts || []).forEach(c => add(c.renewal, [c.contract, c.provider].filter(Boolean).join(' · '), 'contracts', ''));
    return items.sort((a, b) => a.date - b.date);
  }

  // ---- timeline tile face (count of upcoming items + the nearest one) ----
  function timelineTile() {
    const upcoming = buildTimelineItems().filter(i => i.daysUntil >= 0);
    const next = upcoming[0];
    const warn = !!next && next.daysUntil <= 14;   // 'soon' boundary — matches timelineItemHtml + healthAvatar
    const status = next
      ? (warn ? `<span class="tile-flag" aria-hidden="true">▲</span> ${escapeHtml(duePhrase(next.daysUntil))}`
              : `${escapeHtml(t('label.next'))} ${escapeHtml(formatDateHE(next.date))}`)
      : '—';
    return `<button class="tile" data-portfolio="timeline" type="button">
      <div class="tile-head">
        <span class="tile-name">${escapeHtml(t('drawer.timeline'))}</span>
        <span class="tile-status${warn ? ' is-warn' : ''}">${status}</span>
      </div>
      <div class="tile-kpi num">${upcoming.length || '—'}</div>
    </button>`;
  }

  // ---- timeline sheet body: sticky controls (zoom rungs + filter chips) + the track ----
  function timelineSheet() {
    const zooms = TIMELINE_ZOOMS.map(z =>
      `<button class="tl-zoom" type="button" data-tl-zoom="${z.key}" aria-pressed="${state.timeline.zoom === z.key}">${escapeHtml(t('timeline.zoom.' + z.key))}</button>`
    ).join('');
    const chips = ['all', ...TIMELINE_CATEGORIES].map(c =>
      `<button class="tl-chip" type="button" data-tl-filter="${c}" aria-pressed="${state.timeline.filter === c}">${escapeHtml(t('timeline.cat.' + c))}</button>`
    ).join('');
    return `<div class="tl-controls">
      <div class="tl-zooms" role="group" aria-label="${escapeHtml(t('timeline.zoomLabel'))}">${zooms}</div>
      <div class="tl-chips" role="group" aria-label="${escapeHtml(t('timeline.filterLabel'))}">${chips}</div>
    </div>
    <div id="tl-track" class="tl-track">${timelineTrackHtml()}</div>`;
  }
  function timelineTrackHtml() {
    const z = TIMELINE_ZOOMS.find(x => x.key === state.timeline.zoom) || TIMELINE_ZOOMS[2];
    const f = state.timeline.filter;
    const items = buildTimelineItems().filter(i => i.daysUntil <= z.days && (f === 'all' || i.category === f));
    if (!items.length) return `<div class="empty">${escapeHtml(t('empty.noMilestones'))}</div>`;
    const nowMarker = `<div class="tl-now"><span class="tl-now-label">${escapeHtml(t('timeline.now'))}</span></div>`;
    let html = '', placed = false;
    items.forEach(i => {
      if (!placed && i.daysUntil >= 0) { html += nowMarker; placed = true; }   // marker before the first future/today item
      html += timelineItemHtml(i);
    });
    if (!placed) html += nowMarker;   // every shown item is in the past tail → marker at the foot
    return html;
  }
  // One read-only timeline row. Urgency is carried by the glyph + the due phrase
  // (text), never color alone (DESIGN §8); the inline-start border is a redundant
  // cue. The muted category tag keeps the cross-domain mix legible at a glance.
  function timelineItemHtml(i) {
    const bucket = i.daysUntil < 0 ? 'over' : i.daysUntil <= 14 ? 'soon' : 'ok';
    const glyph = { over: '🔴', soon: '⚠', ok: '·' }[bucket];
    return `<div class="tl-item tl-${bucket}">
      <span class="tl-glyph" aria-hidden="true">${glyph}</span>
      <span class="tl-date num">${escapeHtml(fmtDate(i.date))}</span>
      <span class="tl-body">
        <span class="tl-title">${escapeHtml(i.title)}</span>
        <span class="tl-cat">${escapeHtml(t('timeline.cat.' + i.category))}${i.meta ? ' · ' + escapeHtml(i.meta) : ''}</span>
      </span>
      <span class="tl-due num">${escapeHtml(duePhrase(i.daysUntil))}</span>
    </div>`;
  }
  // Wire the zoom/filter controls each time the sheet body is built. A control
  // click mutates view state and swaps ONLY #tl-track (+ the aria-pressed flags),
  // so the clicked button keeps focus — never rebuilds the whole body (which would
  // drop focus). innerHTML rebuilds discard old buttons, so re-binding can't leak.
  function wireTimeline() {
    const body = document.getElementById('sheet-body');
    if (!body) return;
    body.querySelectorAll('[data-tl-zoom]').forEach(b =>
      b.addEventListener('click', () => { state.timeline.zoom = b.dataset.tlZoom; updateTimelineView(); }));
    body.querySelectorAll('[data-tl-filter]').forEach(b =>
      b.addEventListener('click', () => { state.timeline.filter = b.dataset.tlFilter; updateTimelineView(); }));
  }
  function updateTimelineView() {
    const body = document.getElementById('sheet-body');
    if (!body) return;
    body.querySelectorAll('[data-tl-zoom]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tlZoom === state.timeline.zoom)));
    body.querySelectorAll('[data-tl-filter]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tlFilter === state.timeline.filter)));
    const track = document.getElementById('tl-track');
    if (track) track.innerHTML = timelineTrackHtml();
  }

  // Estimate % of the goal's time window that has elapsed (0..100).
  function goalPctTimeElapsed(g) {
    if (!g.targetDate) return 0;
    const total = Math.max(1, daysBetween(g.targetDate, new Date(g.targetDate.getFullYear(), g.targetDate.getMonth() - 3, g.targetDate.getDate())));
    const elapsed = total - Math.max(0, daysBetween(g.targetDate, state.today));
    return Math.max(0, Math.min(100, Math.round((elapsed / total) * 100)));
  }

  // ---------------- Sunday view ----------------
  function renderSunday() {
    const start = new Date(state.today);
    const dow = start.getDay();
    // Sunday = 0; Israeli week starts Sunday.
    const daysToSunday = dow === 0 ? 0 : 7 - dow;
    const sundayStart = new Date(start);
    sundayStart.setDate(start.getDate() + daysToSunday);
    const weekEnd = new Date(sundayStart);
    weekEnd.setDate(sundayStart.getDate() + 7);

    document.getElementById('sunday-week').textContent = `${fmtDateShort(sundayStart)} — ${fmtDateShort(weekEnd)}`;

    // Week ahead
    const events = state.data.calendarEvents
      .filter(e => e.date && e.date >= sundayStart && e.date < weekEnd)
      .sort((a, b) => a.date - b.date);
    document.getElementById('sunday-week-ahead').innerHTML = events.length
      ? events.map(e => `<div class="kv"><span>${fmtDate(e.date)} ${e.start ? '· ' + e.start : ''} — ${escapeHtml(e.title)}</span><span class="v">${escapeHtml(e.owner || '')}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.nothingThisWeek'))}</div>`;

    // Reminders firing this week
    const weekRem = state.data.reminders
      .filter(r => r.daysUntil != null && r.daysUntil >= 0 && r.daysUntil <= 7 && r.status !== 'Done')
      .sort((a, b) => a.daysUntil - b.daysUntil);
    document.getElementById('sunday-reminders').innerHTML = weekRem.length
      ? weekRem.map(r => `<div class="kv"><span>${flagEmoji(r.flag)} ${escapeHtml(r.title)}</span><span class="v">${fmtDate(r.due)}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.noUpcoming'))}</div>`;

    // Overdue
    const overdue = state.data.reminders.filter(r => r.flag === 'OVERDUE').sort((a, b) => a.daysUntil - b.daysUntil);
    document.getElementById('sunday-overdue').innerHTML = overdue.length
      ? overdue.map(r => `<div class="kv"><span>🔴 ${escapeHtml(r.title)}</span><span class="v">${duePhrase(r.daysUntil)}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.noOverdue'))}</div>`;

    // Money
    const totalT = state.data.budget.reduce((s, b) => s + b.target, 0);
    const totalA = state.data.budget.reduce((s, b) => s + b.actual, 0);
    const over = state.data.budget.filter(b => b.pct > 1.0);
    document.getElementById('sunday-money').innerHTML = `
      <div class="kv"><span>${escapeHtml(t('sunday.monthToDate'))}</span><span class="v">${amountHtml(totalA)} / ${amountHtml(totalT)} (${totalT ? Math.round(100 * totalA / totalT) : 0}%)</span></div>
      ${over.length ? over.map(b => `<div class="kv"><span>⚠ ${escapeHtml(b.category)}</span><span class="v">${Math.round(b.pct * 100)}%</span></div>`).join('') : `<div class="row-note" style="padding:6px 0">${escapeHtml(t('sunday.noOverBudget'))}</div>`}
    `;

    // Goals
    document.getElementById('sunday-goals').innerHTML = state.data.goals.map(g => `
      <div class="kv"><span>${escapeHtml(g.goal)} <span class="pill">${escapeHtml(g.owner || '')}</span><span class="pill">${escapeHtml(g.status || '')}</span></span><span class="v">${g.pct}%</span></div>
      ${g.milestone ? `<div class="row-note" style="padding: 0 0 6px">${escapeHtml(t('label.next'))} ${escapeHtml(g.milestone)}</div>` : ''}
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;

    // Data hygiene
    const placeholderPeople = state.data.people.filter(p => (p['Name'] || '').startsWith('['));
    const placeholderGoals = state.data.goals.filter(g => g.goal.startsWith('['));
    const hygiene = [];
    if (placeholderPeople.length) hygiene.push(t('sunday.hygienePeople', { n: placeholderPeople.length }));
    if (placeholderGoals.length) hygiene.push(t('sunday.hygieneGoals', { n: placeholderGoals.length }));
    document.getElementById('sunday-hygiene').innerHTML = hygiene.length
      ? hygiene.map(h => `<div class="kv"><span>${escapeHtml(h)}</span><span class="v">—</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.allClean'))}</div>`;
  }

  // ---------------- Settings ----------------
  function renderSettings() {
    const acc = document.getElementById('settings-account');
    if (cfg.DEMO_MODE) {
      acc.innerHTML = `${escapeHtml(t('settings.demoModeStatus'))}<div class="row-note">${escapeHtml(t('settings.demoNoAccount'))}</div>`;
    } else if (state.user) {
      acc.innerHTML = `${escapeHtml(t('settings.signedInAs', { name: state.user.name }))}<div class="row-note">${escapeHtml(state.user.email)}</div>`;
    } else {
      acc.innerHTML = escapeHtml(t('settings.notSignedIn'));
    }
    document.getElementById('settings-sheetid').value = cfg.SHEET_ID;
    document.getElementById('settings-demo').value = String(cfg.DEMO_MODE);
    // Language toggle active state.
    const lang = currentLang();
    document.querySelectorAll('[data-lang]').forEach(b => {
      b.classList.toggle('primary', b.dataset.lang === lang);
    });
    // Theme toggle active state.
    const theme = localStorage.getItem('familyinc.theme') || 'auto';
    document.querySelectorAll('[data-theme]').forEach(b => {
      b.classList.toggle('primary', b.dataset.theme === theme);
    });
    renderQueue();
  }

  function renderQueue() {
    const q = document.getElementById('settings-queue');
    if (!state.pendingWrites.length) { q.textContent = t('empty.noQueuedWrites'); return; }
    q.innerHTML = state.pendingWrites.map(w => `<div class="kv"><span>${w.kind} · row ${w.row}</span><span class="v">${w.queuedAt}</span></div>`).join('');
  }

  // ---------------- Write-back ----------------
  function findReminder(rowNum) {
    return state.data.reminders.find(r => String(r._row) === String(rowNum));
  }

  // Lane C — true only when the Reminders columns resolved cleanly. Fails CLOSED
  // (absent data/cols → not writable): a write guard must pause, never assume.
  // Write handlers no-op + toast rather than hit the wrong column.
  function remindersWritable() {
    return !!(state.data && state.data.reminderCols && state.data.reminderCols.ok);
  }
  // Resolve a Reminders write range by HEADER NAME, e.g. remRange('Due Date', 7)
  // → 'Reminders!D7' — never a hardcoded column letter.
  function remRange(name, rowNum) {
    const cols = state.data && state.data.reminderCols && state.data.reminderCols.cols;
    const idx = cols && cols[name];
    return idx ? `${cfg.TABS.reminders}!${colLetter(idx)}${rowNum}` : null;
  }

  // ---- Desk batch write-backs (V3.3) ----
  // Each fans the current desk selection out to ONE applyWrites batch. SPEC §6.1
  // write contract: intent columns + M, N (on completion) + always O, every
  // column resolved by HEADER NAME (Lane C), never a hardcoded letter. A selection
  // of one is just the n=1 case — there is no separate single-row path anymore.

  async function handleBatchDone() {
    if (!remindersWritable()) { toast(t('toast.writesPaused')); return; }
    const rows = selectedReminders();
    if (!rows.length) return;
    const now = new Date();
    const ts = fmtISOts(now);
    const userName = (state.user && state.user.name) || 'Dashboard';
    const writes = [];
    rows.forEach(r => {
      const rowNum = r._row;
      r.status = 'Done'; r.flag = '';
      r.lastDoneBy = userName; r.doneAt = now; r.writeQueueTombstone = now;
      // Col H (Last Sent) is ENGINE-owned — never written except to clear it on the
      // §7.1 recurrence bump below.
      writes.push({ range: remRange('Status', rowNum), value: 'Done' });
      writes.push({ range: remRange('LastDoneBy', rowNum), value: userName });
      writes.push({ range: remRange('DoneAt', rowNum), value: ts });
      writes.push({ range: remRange('WriteQueue_Tombstone', rowNum), value: ts, tomb: true });
      // Bump recurring (mirror of automation/lib/dates.bump_due — keep in sync).
      // Each recurring row adds its own bump triplet to the batch (the build-plan
      // "batch-done multiplies the bump write set" note — handled per row here).
      if (r.recurrence && r.recurrence !== 'One-off' && r.due) {
        const bumped = bumpDate(r.due, r.recurrence);
        if (bumped) {
          writes.push({ range: remRange('Due Date', rowNum), value: fmtISO(bumped) });
          writes.push({ range: remRange('Status', rowNum), value: 'Pending' });
          writes.push({ range: remRange('Last Sent', rowNum), value: '' });
          r.due = bumped; r.status = 'Pending';
          r.daysUntil = daysBetween(bumped, state.today);
          r.flag = flagFor(r.daysUntil, r.status);
        }
        // Unbumpable period (Custom/unknown): row stays Done; the engine flags it
        // for review (logs/engine_flags.jsonl) instead of either side guessing.
      }
    });
    state.deskSelection.clear();
    await applyWrites(writes, batchLabel('done', rows));
    renderAll();
    focusDeskAfterBatch();
  }

  // Absolute snooze (V3.3, D4): write Due = an ABSOLUTE date (today + offset, or a
  // picked date), NOT Due += N. So an overdue row's daysUntil goes ≥ 0 and flagFor
  // drops OVERDUE — the +Nd-from-due path could leave an already-late row overdue.
  async function handleBatchSnooze(absDate) {
    if (!remindersWritable()) { toast(t('toast.writesPaused')); return; }
    if (!(absDate instanceof Date) || isNaN(absDate)) return;
    const rows = selectedReminders();
    if (!rows.length) return;
    const iso = fmtISO(absDate);
    const ts = fmtISOts(new Date());
    const writes = [];
    rows.forEach(r => {
      const rowNum = r._row;
      r.due = absDate; r.status = 'Snoozed';
      r.daysUntil = daysBetween(absDate, state.today);
      r.flag = flagFor(r.daysUntil, r.status);
      writes.push({ range: remRange('Due Date', rowNum), value: iso });
      writes.push({ range: remRange('Status', rowNum), value: 'Snoozed' });
      writes.push({ range: remRange('WriteQueue_Tombstone', rowNum), value: ts, tomb: true });
    });
    const di = document.getElementById('desk-snooze-date'); if (di) di.value = '';   // re-arm the picker (a repeat of the same date fires no 'change')
    state.deskSelection.clear();
    await applyWrites(writes, batchLabel('snooze', rows, absDate));
    renderAll();
    focusDeskAfterBatch();
  }

  async function handleBatchNote() {
    if (!remindersWritable()) { toast(t('toast.writesPaused')); return; }
    const input = document.getElementById('desk-note-input');
    const text = ((input && input.value) || '').trim();
    if (!text) return;
    const rows = selectedReminders();
    if (!rows.length) return;
    const stamp = `[${fmtISO(new Date())} ${state.user?.name || 'You'}]`;
    const ts = fmtISOts(new Date());
    const writes = [];
    rows.forEach(r => {
      const rowNum = r._row;
      const newNotes = (r.notes ? r.notes + ' \n' : '') + `${stamp} ${text}`;
      r.notes = newNotes;
      writes.push({ range: remRange('Notes', rowNum), value: newNotes });
      writes.push({ range: remRange('WriteQueue_Tombstone', rowNum), value: ts, tomb: true });
    });
    if (input) input.value = '';
    state.deskSelection.clear();
    await applyWrites(writes, batchLabel('note', rows));
    renderAll();
    focusDeskAfterBatch();
  }

  // One toast label for the batch — n=1 names the row, n>1 counts.
  function batchLabel(kind, rows, date) {
    const n = rows.length;
    if (kind === 'done') return n === 1 ? t('action.markedDone', { title: rows[0].title }) : t('action.doneN', { n });
    if (kind === 'snooze') {
      const ds = formatDateHE(date);
      return n === 1 ? t('action.snoozedTo', { title: rows[0].title, date: ds }) : t('action.snoozedN', { n, date: ds });
    }
    if (kind === 'note') return n === 1 ? t('action.noteAdded') : t('action.noteAddedN', { n });
    return '';
  }

  // Mirror of automation/lib/dates.bump_due (SPEC §7.1) — same periods, same
  // clamp-to-month-end rule (Feb-29 → Feb-28, Jan-31 +1mo → Feb-28/29). JS
  // setMonth() overflows instead of clamping, so we clamp by hand. Unknown
  // periods (incl. Custom) return null: no bump, engine flags for review.
  function bumpDate(d, recurrence) {
    const months = { Monthly: 1, Quarterly: 3, Yearly: 12 }[recurrence];
    if (recurrence === 'Weekly') {
      const x = new Date(d);
      x.setDate(x.getDate() + 7);
      return x;
    }
    if (!months) return null;
    const total = d.getFullYear() * 12 + d.getMonth() + months;
    const y = Math.floor(total / 12), m = total % 12;
    const lastDay = new Date(y, m + 1, 0).getDate();
    return new Date(y, m, Math.min(d.getDate(), lastDay));
  }

  // Push writes onto the offline queue, capped at MAX_PENDING_WRITES (SPEC §7.6
  // / DESIGN §6). At the cap we warn ONCE and drop the writes rather than grow
  // the queue unboundedly — silent unbounded growth was the prior bug (B8).
  // Returns true if the writes were queued, false if dropped at the cap.
  function enqueueWrites(writes) {
    if (state.pendingWrites.length >= MAX_PENDING_WRITES) {
      if (!state.queueFullWarned) {
        toast(t('toast.queueFull', { max: MAX_PENDING_WRITES }));
        state.queueFullWarned = true;
      }
      return false;
    }
    writes.forEach(w => state.pendingWrites.push({ kind: 'update', row: extractRow(w.range), range: w.range, value: w.value, tomb: !!w.tomb, queuedAt: new Date().toISOString() }));
    localStorage.setItem(QUEUE_KEY, JSON.stringify(state.pendingWrites));
    renderQueue();
    return true;
  }

  async function applyWrites(writes, label) {
    if (cfg.DEMO_MODE) {
      toast(t('toast.demoPrefix', { label }));
      return;
    }
    if (!navigator.onLine || !state.gapiReady) {
      if (enqueueWrites(writes)) toast(t('toast.queuedOffline', { label }));
      return;
    }
    try {
      const data = writes.map(w => ({ range: w.range, values: [[w.value]] }));
      await gapi.client.sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: cfg.SHEET_ID,
        resource: { valueInputOption: 'USER_ENTERED', data },
      });
      toast(label);
    } catch (e) {
      console.error('Write failed', e);
      if (enqueueWrites(writes)) toast(t('toast.queued', { label }));
    }
  }
  function extractRow(range) { return (range.match(/(\d+)$/) || [])[1] || ''; }

  async function flushQueue() {
    if (!state.pendingWrites.length || cfg.DEMO_MODE) return;
    const queue = state.pendingWrites.slice();
    // SPEC §8.3: the tombstone is written AT FLUSH — the engine's 6h race
    // window starts when the write lands on the Sheet, not when the offline
    // tap happened. Refresh every tombstone value to now; everything else
    // flushes as queued (in tap order). The tombstone is flagged at enqueue by
    // FIELD (w.tomb, Lane C) — never a hardcoded column letter, which could
    // shift if a non-write column left of it is removed.
    const flushTs = fmtISOts(new Date());
    try {
      await gapi.client.sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: cfg.SHEET_ID,
        resource: {
          valueInputOption: 'USER_ENTERED',
          data: queue.map(w => ({
            range: w.range,
            values: [[w.tomb ? flushTs : w.value]],
          })),
        },
      });
      state.pendingWrites = [];
      state.queueFullWarned = false;   // queue drained — re-arm the one-shot cap warning
      localStorage.setItem(QUEUE_KEY, JSON.stringify([]));
      toast(t('toast.flushed', { n: queue.length }));
      renderQueue();
    } catch (e) {
      console.warn('Queue flush failed', e);
    }
  }

  // ---------------- HTML helpers ----------------
  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ---------------- Tabs & UI shell ----------------
  function switchTab(name) {
    state.tab = name;
    document.querySelectorAll('nav.tabbar button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
  }
  function showApp() {
    document.getElementById('signin-screen').hidden = true;
    document.getElementById('app').hidden = false;
  }
  function showSignIn() {
    document.getElementById('signin-screen').hidden = false;
    document.getElementById('app').hidden = true;
  }

  // ---------------- Boot ----------------
  async function boot() {
    // Apply chrome strings to static markup BEFORE first paint of the shell.
    applyChromeStrings();

    // Restore queue
    try { state.pendingWrites = JSON.parse(localStorage.getItem(QUEUE_KEY)) || []; } catch {}

    // Tab clicks
    document.querySelectorAll('nav.tabbar button').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));

    // Sign-in screen buttons
    document.getElementById('signin-btn').addEventListener('click', requestSignIn);
    document.getElementById('demo-link').addEventListener('click', (e) => {
      e.preventDefault();
      cfg.DEMO_MODE = true;
      showApp();
      loadAll();
    });

    // Settings buttons
    document.getElementById('switch-account-btn').addEventListener('click', switchAccount);
    document.getElementById('signout-btn').addEventListener('click', signOut);
    document.getElementById('refresh-btn').addEventListener('click', loadAll);

    // Bottom-sheet dismissers (V3.5): the close button + tapping the scrim. The
    // icon-only close button is named via data-i18n-aria (the V3.8 aria walker).
    document.getElementById('sheet-close').addEventListener('click', closeSheet);
    document.getElementById('sheet-scrim').addEventListener('click', closeSheet);

    // Desk batch action bar (V3.3). The bar markup is static, so wire it ONCE here;
    // renderToday only fills #today-list + toggles the bar's visibility/count. The
    // snooze chips resolve to ABSOLUTE dates (today + offset); the date picker any day.
    const deskBar = document.getElementById('desk-actionbar');
    if (deskBar) {
      deskBar.querySelector('[data-batch="done"]')?.addEventListener('click', handleBatchDone);
      deskBar.querySelector('[data-batch="snooze"]')?.addEventListener('click', () => toggleDeskSubrow('snooze'));
      deskBar.querySelector('[data-batch="note"]')?.addEventListener('click', () => toggleDeskSubrow('note'));
      deskBar.querySelectorAll('[data-snooze-days]').forEach(chip =>
        chip.addEventListener('click', () => {
          const target = new Date(state.today);
          target.setDate(target.getDate() + parseInt(chip.dataset.snoozeDays, 10));
          handleBatchSnooze(target);
        }));
      const dateInput = document.getElementById('desk-snooze-date');
      if (dateInput) {
        dateInput.min = fmtISO(state.today);   // discourage snoozing into the past
        // Reject a past date even if a UA lets one slip past the min guard (DESIGN §9 #17).
        dateInput.addEventListener('change', () => { const d = parseDate(dateInput.value); if (d && daysBetween(d, state.today) >= 0) handleBatchSnooze(d); });
      }
      // aria-labels for the snooze row, date picker, and note textarea are now
      // declarative (data-i18n-aria, applied by applyChromeStrings at boot).
      document.getElementById('desk-note-send')?.addEventListener('click', handleBatchNote);
    }
    document.getElementById('settings-save').addEventListener('click', async () => {
      const newSheetId = document.getElementById('settings-sheetid').value.trim();
      const newDemoMode = document.getElementById('settings-demo').value === 'true';

      // D3: Validate Sheet ID format before saving (unless demo mode or blank/unchanged).
      if (!newDemoMode && newSheetId && newSheetId !== cfg.SHEET_ID) {
        // Google Sheets IDs are 44-char base64url strings.
        if (!/^[A-Za-z0-9_-]{10,}$/.test(newSheetId)) {
          toast(t('toast.sheetIdInvalid'));
          return;
        }
        // Test-read one cell to catch typos before committing.
        if (state.gapiReady) {
          const saveBtn = document.getElementById('settings-save');
          saveBtn.disabled = true;
          try {
            await gapi.client.sheets.spreadsheets.values.get({
              spreadsheetId: newSheetId,
              range: 'A1',
            });
          } catch (e) {
            toast(t('toast.sheetIdTestFailed', { err: e.result?.error?.message || e.message || 'unknown' }));
            saveBtn.disabled = false;
            return;
          } finally {
            saveBtn.disabled = false;
          }
        }
      }

      cfg.SHEET_ID = newSheetId;
      cfg.DEMO_MODE = newDemoMode;
      localStorage.setItem('family_inc_config_override', JSON.stringify({ SHEET_ID: cfg.SHEET_ID, DEMO_MODE: cfg.DEMO_MODE }));
      location.reload();
    });

    // Restore config overrides (Sheet ID / demo flag) from a previous Settings save
    try {
      const o = JSON.parse(localStorage.getItem('family_inc_config_override'));
      if (o) Object.assign(cfg, o);
    } catch {}

    // Language toggle clicks (Settings → Language section).
    // Persist preference to localStorage then reload so the pre-paint script
    // applies the correct lang/dir on next boot.
    document.querySelectorAll('[data-lang]').forEach(b => {
      b.addEventListener('click', () => {
        const newLang = b.dataset.lang;
        try { localStorage.setItem('familyinc.lang', newLang); } catch {}
        location.reload();
      });
    });

    // Theme toggle clicks (Settings → Appearance section).
    // Persist preference to localStorage; 'auto' removes the attribute entirely
    // so the CSS media query takes over. Reload for clean pre-paint application.
    document.querySelectorAll('[data-theme]').forEach(b => {
      b.addEventListener('click', () => {
        const val = b.dataset.theme;
        try {
          if (val === 'auto') { localStorage.removeItem('familyinc.theme'); }
          else { localStorage.setItem('familyinc.theme', val); }
        } catch {}
        location.reload();
      });
    });

    // Online → flush queue
    window.addEventListener('online', () => flushQueue());

    if (cfg.DEMO_MODE) {
      showApp();
      await loadAll();
      return;
    }
    if (!cfg.CLIENT_ID || cfg.CLIENT_ID.startsWith('PASTE_')) {
      showSignIn();
      document.getElementById('signin-btn').textContent = t('signin.notConfigured');
      document.getElementById('signin-btn').disabled = true;
      return;
    }
    await initAuth();
    if (!state.token) showSignIn();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
