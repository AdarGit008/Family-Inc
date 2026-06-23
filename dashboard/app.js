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
      'section.todayCalendar': 'יומן היום',
      'section.next7': 'השבוע הקרוב',
      'section.domains': 'תחומים',
      // Drawers
      'drawer.money': 'כספים',
      'drawer.health': 'בריאות',
      'drawer.goals': 'יעדים',
      'drawer.car': 'רכב',
      'drawer.contracts': 'מנויים וחוזים',
      'drawer.education': 'חינוך',
      // Banner
      'banner.allClear': '✅ אין דברים דחופים',
      'banner.overdueAndToday': '🔴 {overdue} באיחור · 🟠 {today} להיום',
      'banner.overdueOnly': '🔴 {overdue} באיחור',
      'banner.todayOnly': '🟠 {today} להיום',
      // Status pill
      'pill.overdue': '{n} באיחור',
      'pill.dueToday': '{n} להיום',
      'pill.sundayReady': 'סיכום ראשון מוכן',
      // Row actions
      'row.done': '✓ בוצע',
      'row.snooze': '+ דחה',
      'row.note': '+ הערה',
      'prompt.addNote': 'הוסף הערה (תתווסף לעמודת הערות):',
      // Empty states
      'empty.nothingOnFire': 'שום דבר לא בוער. ☕',
      'empty.nothingThisWeek': 'אין אירועים השבוע.',
      'empty.noEventsToday': 'אין אירועים היום.',
      'empty.noQueuedWrites': 'אין כתיבות בתור.',
      'empty.next60Days': 'אין אירועים בחודשיים הקרובים.',
      'empty.noBudget': 'אין תקציב עדיין.',
      'empty.noRecentTxns': 'אין עסקאות אחרונות.',
      'empty.noGoals': 'אין יעדים.',
      'empty.noVehicle': 'אין רכב.',
      'empty.noRenewals': 'אין חידושים בחודשיים הקרובים.',
      'empty.noUpcoming': 'אין פריטים קרובים.',
      'empty.noOverdue': 'אין פריטים באיחור.',
      'empty.allClean': 'הכל נקי.',
      'state.allGood': 'הכל בסדר',
      'state.loading': 'טוען…',
      // Calendar
      'cal.allDay': 'כל היום',
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
      // Action labels (used in toasts after write-back)
      'action.markedDone': 'בוצע: {title}',
      'action.snoozed': 'נדחה ב-+{days}d: {title}',
      'action.noteAdded': 'הערה נוספה',
    },
    en: {
      'tabbar.today': 'Today',
      'tabbar.sunday': 'Sunday',
      'tabbar.settings': 'Settings',
      'section.todayList': 'For today',
      'section.todayCalendar': "Today's calendar",
      'section.next7': 'This coming week',
      'section.domains': 'Domains',
      'drawer.money': 'Money',
      'drawer.health': 'Health',
      'drawer.goals': 'Goals',
      'drawer.car': 'Car',
      'drawer.contracts': 'Subscriptions & contracts',
      'drawer.education': 'Education',
      'banner.allClear': '✅ Nothing urgent',
      'banner.overdueAndToday': '🔴 {overdue} overdue · 🟠 {today} due today',
      'banner.overdueOnly': '🔴 {overdue} overdue',
      'banner.todayOnly': '🟠 {today} due today',
      'pill.overdue': '{n} overdue',
      'pill.dueToday': '{n} due today',
      'pill.sundayReady': 'Sunday briefing ready',
      'row.done': '✓ done',
      'row.snooze': '+ snooze',
      'row.note': '+ note',
      'prompt.addNote': 'Add a note (will be appended to the Notes column):',
      'empty.nothingOnFire': 'Nothing on fire. ☕',
      'empty.nothingThisWeek': 'Nothing scheduled this week.',
      'empty.noEventsToday': 'No events today.',
      'empty.noQueuedWrites': 'No queued writes.',
      'empty.next60Days': 'Nothing in the next two months.',
      'empty.noBudget': 'No budget yet.',
      'empty.noRecentTxns': 'No recent transactions.',
      'empty.noGoals': 'No goals yet.',
      'empty.noVehicle': 'No vehicle.',
      'empty.noRenewals': 'No renewals in the next two months.',
      'empty.noUpcoming': 'No upcoming items.',
      'empty.noOverdue': 'No overdue items.',
      'empty.allClean': 'All clean.',
      'state.allGood': 'All good',
      'state.loading': 'Loading…',
      'cal.allDay': 'all day',
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
      'action.markedDone': '{title} → done',
      'action.snoozed': '{title} → +{days}d',
      'action.noteAdded': 'Note added',
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
  function parseDate(v) {
    if (!v) return null;
    if (v instanceof Date) return isNaN(v) ? null : v;
    if (typeof v === 'number') {
      // Excel serial — used if we ever roundtrip from xlsx, but Sheets API
      // returns formatted strings, so this branch is rare.
      return new Date(Math.round((v - 25569) * 86400 * 1000));
    }
    const d = new Date(v);
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
    const calendarEvents = rowsToObjects(named.calendarEvents).map(r => ({
      _row: r._row,
      date: parseDate(r['Date']),
      start: r['Start'] || '',
      end: r['End'] || '',
      title: r['Title'] || '',
      owner: r['Owner'] || '',
      source: r['Source'] || '',
      location: r['Location'] || '',
      notes: r['Notes'] || '',
    }));
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

    return { reminders, calendarEvents, people, budget, txns, goals, health, education, car, contracts, settings };
  }

  // ---------------- Render ----------------
  function renderAll() {
    // Header date is chrome — route through currentLang() so the toggle
    // actually flips the most prominent label on the screen. he-IL and en-GB
    // both render DD/MM date order, which matches Israeli reading habits in
    // either language.
    const _hdrLocale = currentLang() === 'en' ? 'en-GB' : 'he-IL';
    document.getElementById('header-date').textContent = state.today.toLocaleDateString(_hdrLocale, { weekday: 'long', day: 'numeric', month: 'long' });
    renderBanner();
    renderStatusPill();
    renderToday();
    renderTodayCalendar();
    renderNext7();
    renderDrawers();
    renderSunday();
    renderSettings();
  }

  // ---------------- Status pill ----------------
  function setStatusPill(text) {
    const pill = document.getElementById('status-pill');
    const txt = document.getElementById('status-pill-text');
    if (!pill || !txt) return;
    if (!text) {
      pill.hidden = true;
      txt.textContent = '';
      return;
    }
    txt.textContent = text;
    pill.hidden = false;
  }
  function renderStatusPill() {
    const r = state.data.reminders;
    const overdue = r.filter(x => x.flag === 'OVERDUE').length;
    const todayCount = r.filter(x => x.flag === 'FIRE TODAY').length;
    const dow = state.today.getDay(); // 0 = Sunday
    let msg = '';
    if (overdue > 0) {
      msg = t('pill.overdue', { n: overdue });
    } else if (todayCount > 0) {
      msg = t('pill.dueToday', { n: todayCount });
    } else if (dow === 0) {
      msg = t('pill.sundayReady');
    }
    setStatusPill(msg);
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

  function renderBanner() {
    const r = state.data.reminders;
    const overdue = r.filter(x => x.flag === 'OVERDUE').length;
    const today = r.filter(x => x.flag === 'FIRE TODAY').length;
    const banner = document.getElementById('banner');
    if (overdue > 0 && today > 0) {
      banner.className = 'banner alert';
      banner.textContent = t('banner.overdueAndToday', { overdue, today });
    } else if (overdue > 0) {
      banner.className = 'banner alert';
      banner.textContent = t('banner.overdueOnly', { overdue });
    } else if (today > 0) {
      banner.className = 'banner warn';
      banner.textContent = t('banner.todayOnly', { today });
    } else {
      banner.className = 'banner clear';
      banner.textContent = t('banner.allClear');
    }
  }

  function renderToday() {
    const list = state.data.reminders
      .filter(r => r.flag === 'OVERDUE' || r.flag === 'FIRE TODAY')
      .sort((a, b) => (a.daysUntil ?? 9e9) - (b.daysUntil ?? 9e9));
    const el = document.getElementById('today-list');
    if (!list.length) {
      el.innerHTML = `<div class="empty-caught-up">${escapeHtml(t('empty.nothingOnFire'))} <span class="empty-date">${escapeHtml(formatDateHE(state.today))}</span></div>`;
      return;
    }
    el.innerHTML = list.map(renderReminderRow).join('');
    attachRowHandlers(el);
  }

  function renderNext7() {
    const list = state.data.reminders
      .filter(r => r.flag === 'WEEK OUT')
      .sort((a, b) => (a.daysUntil ?? 9e9) - (b.daysUntil ?? 9e9));
    const events = state.data.calendarEvents
      .filter(e => e.date && daysBetween(e.date, state.today) >= 1 && daysBetween(e.date, state.today) <= 7)
      .sort((a, b) => a.date - b.date);
    const el = document.getElementById('next7-list');
    let html = '';
    list.forEach(r => { html += renderReminderRow(r); });
    events.forEach(e => {
      const d = daysBetween(e.date, state.today);
      html += `<div class="row cal-event">
        <div class="row-top">
          <span class="row-title">📆 ${escapeHtml(e.title)}</span>
          <span class="row-meta">${fmtDate(e.date)} ${e.start || ''}</span>
        </div>
        ${e.location ? `<div class="row-note">${escapeHtml(e.location)}${e.owner ? ' · ' + escapeHtml(e.owner) : ''}</div>` : ''}
      </div>`;
    });
    el.innerHTML = html || `<div class="empty">${escapeHtml(t('empty.nothingThisWeek'))}</div>`;
    attachRowHandlers(el);
  }

  function renderTodayCalendar() {
    const todays = state.data.calendarEvents.filter(e => e.date && daysBetween(e.date, state.today) === 0);
    const el = document.getElementById('today-cal');
    if (!todays.length) {
      el.innerHTML = `<div class="empty">${escapeHtml(t('empty.noEventsToday'))}</div>`;
      return;
    }
    el.innerHTML = todays.map(e => `
      <div class="row cal-event">
        <div class="row-top">
          <span class="row-title">${escapeHtml(e.title)}</span>
          <span class="row-meta cal-time">${e.start || escapeHtml(t('cal.allDay'))}${e.end ? '–' + e.end : ''}</span>
        </div>
        ${e.location ? `<div class="row-note">${escapeHtml(e.location)}${e.owner ? ' · ' + escapeHtml(e.owner) : ''}</div>` : ''}
      </div>
    `).join('');
  }

  function renderReminderRow(r) {
    const emoji = flagEmoji(r.flag);
    const cls = flagClass(r.flag);
    return `<div class="row" data-row="${r._row}" data-id="${r._row}">
      <div class="row-top">
        <span class="row-title"><span class="flag ${cls}">${emoji}</span> ${escapeHtml(r.title)}</span>
        <span class="row-meta">${duePhrase(r.daysUntil)}</span>
      </div>
      ${r.notes ? `<div class="row-note">${escapeHtml(r.notes)}</div>` : ''}
      <div class="actions">
        <button class="action-btn primary" data-act="done">${escapeHtml(t('row.done'))}</button>
        <button class="action-btn" data-act="snooze">${escapeHtml(t('row.snooze'))}</button>
        <button class="action-btn" data-act="note">${escapeHtml(t('row.note'))}</button>
      </div>
      <div class="snooze-pills">
        ${[1,3,7,14,30].map(n => `<button class="snooze-pill" data-snooze="${n}">+${n}d</button>`).join('')}
      </div>
    </div>`;
  }

  function attachRowHandlers(container) {
    container.querySelectorAll('.row[data-row]').forEach(rowEl => {
      rowEl.addEventListener('click', (ev) => {
        const actBtn = ev.target.closest('[data-act]');
        const snoozeBtn = ev.target.closest('[data-snooze]');
        if (snoozeBtn) {
          ev.stopPropagation();
          const days = parseInt(snoozeBtn.dataset.snooze, 10);
          handleSnooze(rowEl.dataset.row, days);
          return;
        }
        if (actBtn) {
          ev.stopPropagation();
          const act = actBtn.dataset.act;
          if (act === 'done') handleDone(rowEl.dataset.row);
          else if (act === 'snooze') rowEl.classList.toggle('snoozing');
          else if (act === 'note') handleAddNote(rowEl.dataset.row);
          return;
        }
        rowEl.classList.toggle('expanded');
        rowEl.classList.remove('snoozing');
      });
    });
  }

  // ---------------- Drawers ----------------
  function renderDrawers() {
    // Money
    const totalTarget = state.data.budget.reduce((s, b) => s + b.target, 0);
    const totalActual = state.data.budget.reduce((s, b) => s + b.actual, 0);
    const overBudget = state.data.budget.filter(b => b.pct > 1.0);
    document.getElementById('money-summary').textContent = `${formatILS(totalActual)} / ${formatILS(totalTarget)}${overBudget.length ? ` · ${t('summary.over', { n: overBudget.length })}` : ''}`;
    document.getElementById('money-body').innerHTML = state.data.budget.map(b => `
      <div class="kv"><span>${escapeHtml(b.category)}</span><span class="v">${amountHtml(b.actual)} / ${amountHtml(b.target)} (${Math.round(b.pct * 100)}%)</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noBudget'))}</div>`;

    // D4: Surface recent transactions (last 10) below the budget breakdown.
    const recentTxns = (state.data.txns || [])
      .filter(tx => tx.date && isSpendTxn(tx))
      .sort((a, b) => b.date - a.date)
      .slice(0, 10);
    const txnHtml = recentTxns.map(tx => `
      <div class="kv"><span>${escapeHtml(formatDateHE(tx.date))} · ${escapeHtml(tx.desc || tx.account || '')}</span><span class="v">${amountHtml(tx.amount)}</span></div>
    `).join('');
    const recentEl = document.getElementById('money-recent-txns');
    if (recentEl) {
      recentEl.innerHTML = txnHtml || `<div class="empty">${escapeHtml(t('empty.noRecentTxns'))}</div>`;
    }

    // Money KPI: % of monthly target. Sparkline: last 7 days of txn totals.
    const moneyPct = totalTarget ? Math.round(100 * totalActual / totalTarget) : null;
    renderKpi('money', moneyPct == null ? '' : `${moneyPct}%`, moneyPct != null && moneyPct > 100 ? 'neg' : 'pos');
    renderSparkline(document.getElementById('money-spark'), txnTrend7d());

    // Health (next 60d)
    const upcomingHealth = state.data.health
      .filter(h => h.nextDue && daysBetween(h.nextDue, state.today) <= 60 && daysBetween(h.nextDue, state.today) >= -30)
      .sort((a, b) => a.nextDue - b.nextDue);
    document.getElementById('health-summary').textContent = upcomingHealth.length ? t('summary.upcoming', { n: upcomingHealth.length }) : t('state.allGood');
    document.getElementById('health-body').innerHTML = upcomingHealth.map(h => `
      <div class="kv"><span>${escapeHtml(h.person)} · ${escapeHtml(h.specialty || h.provider || '')}</span><span class="v">${escapeHtml(formatDateHE(h.nextDue))}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.next60Days'))}</div>`;
    renderKpi('health', upcomingHealth.length ? String(upcomingHealth.length) : '', upcomingHealth.length ? 'neg' : 'pos');
    // No numeric trend for health — leave sparkline empty.
    renderSparkline(document.getElementById('health-spark'), null);

    // Goals
    document.getElementById('goals-summary').textContent = t('summary.active', { n: state.data.goals.length });
    document.getElementById('goals-body').innerHTML = state.data.goals.map((g, i) => {
      const pctTimeElapsed = goalPctTimeElapsed(g);
      return `
      <div class="kv goal-kv" data-goal-idx="${i}"><span>${escapeHtml(g.goal)} <span class="row-meta">· ${escapeHtml(g.owner || '')}</span></span><span class="v">${g.pct}%</span></div>
      <svg class="goal-line" id="goal-line-${i}" viewBox="0 0 100 40" preserveAspectRatio="none"></svg>
      ${g.milestone ? `<div class="row-note" style="margin: -2px 0 6px">${escapeHtml(t('label.next'))} ${escapeHtml(g.milestone)}</div>` : ''}
    `;
    }).join('') || `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;
    // After insertion, draw each goal-line.
    state.data.goals.forEach((g, i) => {
      const svg = document.getElementById(`goal-line-${i}`);
      if (svg) renderGoalLine(svg, {
        targetStart: 0,
        targetEnd: 100,
        current: g.pct,
        pctTimeElapsed: goalPctTimeElapsed(g),
      });
    });
    const avgPct = state.data.goals.length ? Math.round(state.data.goals.reduce((s, g) => s + (g.pct || 0), 0) / state.data.goals.length) : null;
    renderKpi('goals', avgPct == null ? '' : `${avgPct}%`, 'pos');
    renderSparkline(document.getElementById('goals-spark'), state.data.goals.length ? state.data.goals.map(g => g.pct || 0) : null);

    // Car
    const car = state.data.car[0];
    if (car) {
      const items = [
        [t('car.annualTest'), car.test],
        [t('car.insurance'), car.insurance],
        [t('car.license'), car.license],
      ].filter(([, d]) => d).map(([k, d]) => `<div class="kv"><span>${escapeHtml(k)}</span><span class="v">${escapeHtml(formatDateHE(d))} (${duePhrase(daysBetween(d, state.today))})</span></div>`);
      const nextDate = [car.test, car.insurance, car.license].filter(Boolean).sort((a, b) => a - b)[0];
      const next = nextDate ? `${t('label.next')} ${formatDateHE(nextDate)}` : '—';
      document.getElementById('car-summary').textContent = next;
      document.getElementById('car-body').innerHTML = items.join('');
      // KPI: days to next test (or any next milestone).
      if (nextDate) {
        const days = daysBetween(nextDate, state.today);
        renderKpi('car', `${days}d`, days < 14 ? 'neg' : 'pos');
      } else {
        renderKpi('car', '', null);
      }
    } else {
      document.getElementById('car-summary').textContent = '—';
      document.getElementById('car-body').innerHTML = `<div class="empty">${escapeHtml(t('empty.noVehicle'))}</div>`;
      renderKpi('car', '', null);
    }
    renderSparkline(document.getElementById('car-spark'), null);

    // Contracts (renewals within 60d)
    const renewals = state.data.contracts
      .filter(c => c.renewal && daysBetween(c.renewal, state.today) <= 60 && daysBetween(c.renewal, state.today) >= -30)
      .sort((a, b) => a.renewal - b.renewal);
    document.getElementById('contracts-summary').textContent = renewals.length ? t('summary.within60', { n: renewals.length }) : t('state.allGood');
    document.getElementById('contracts-body').innerHTML = renewals.map(c => `
      <div class="kv"><span>${escapeHtml(c.contract)} · ${escapeHtml(c.provider || '')}</span><span class="v">${escapeHtml(formatDateHE(c.renewal))}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noRenewals'))}</div>`;
    renderKpi('contracts', renewals.length ? String(renewals.length) : '', renewals.length ? 'neg' : 'pos');
    renderSparkline(document.getElementById('contracts-spark'), null);

    // Education
    const eduUp = state.data.education
      .filter(e => e.nextDate && daysBetween(e.nextDate, state.today) <= 60 && daysBetween(e.nextDate, state.today) >= -7)
      .sort((a, b) => a.nextDate - b.nextDate);
    document.getElementById('education-summary').textContent = eduUp.length ? t('summary.upcoming', { n: eduUp.length }) : t('state.allGood');
    document.getElementById('education-body').innerHTML = eduUp.map(e => `
      <div class="kv"><span>${escapeHtml(e.child)} · ${escapeHtml(e.type || '')}</span><span class="v">${escapeHtml(formatDateHE(e.nextDate))}</span></div>
      ${e.action ? `<div class="row-note" style="margin:-2px 0 6px">${escapeHtml(e.action)}</div>` : ''}
    `).join('') || `<div class="empty">${escapeHtml(t('empty.next60Days'))}</div>`;
    renderKpi('education', eduUp.length ? String(eduUp.length) : '', eduUp.length ? 'neg' : 'pos');
    renderSparkline(document.getElementById('education-spark'), null);

    // Attach drawer toggle handlers
    document.querySelectorAll('.drawer').forEach(d => {
      const toggle = d.querySelector('.drawer-toggle');
      toggle.addEventListener('click', () => d.classList.toggle('open'));
    });
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

  async function handleDone(rowNum) {
    const r = findReminder(rowNum);
    if (!r) return;
    r.status = 'Done';
    r.flag = '';
    const now = new Date();
    const ts = fmtISOts(now);
    const userName = (state.user && state.user.name) || 'Dashboard';
    r.lastDoneBy = userName;
    r.doneAt = now;
    r.writeQueueTombstone = now;
    const colM = colLetter(13);  // LastDoneBy
    const colN = colLetter(14);  // DoneAt
    const colO = colLetter(15);  // WriteQueue_Tombstone
    // SPEC §6.1 write contract: intent columns + M, N (completion) + always O.
    // Col H (Last Sent) is ENGINE-owned — the dashboard never writes it,
    // except clearing it as part of the §7.1 recurrence bump below.
    const writes = [
      { range: `${cfg.TABS.reminders}!G${rowNum}`, value: 'Done' },
      { range: `${cfg.TABS.reminders}!${colM}${rowNum}`, value: userName },
      { range: `${cfg.TABS.reminders}!${colN}${rowNum}`, value: ts },
      { range: `${cfg.TABS.reminders}!${colO}${rowNum}`, value: ts },
    ];
    // Bump recurring (mirror of automation/lib/dates.bump_due — keep in sync)
    if (r.recurrence && r.recurrence !== 'One-off' && r.due) {
      const bumped = bumpDate(r.due, r.recurrence);
      if (bumped) {
        writes.push({ range: `${cfg.TABS.reminders}!D${rowNum}`, value: fmtISO(bumped) });
        writes.push({ range: `${cfg.TABS.reminders}!G${rowNum}`, value: 'Pending' });
        writes.push({ range: `${cfg.TABS.reminders}!H${rowNum}`, value: '' }); // Last Sent cleared (§7.1)
        r.due = bumped; r.status = 'Pending';
        r.daysUntil = daysBetween(bumped, state.today);
        r.flag = flagFor(r.daysUntil, r.status);
      }
      // Unbumpable period (Custom/unknown): row stays Done; the engine flags
      // it for review (logs/engine_flags.jsonl) instead of either side guessing.
    }
    await applyWrites(writes, t('action.markedDone', { title: r.title }));
    renderAll();
  }

  async function handleSnooze(rowNum, days) {
    const r = findReminder(rowNum);
    if (!r || !r.due) return;
    const newDate = new Date(r.due);
    newDate.setDate(newDate.getDate() + days);
    r.due = newDate;
    r.status = 'Snoozed';
    r.daysUntil = daysBetween(newDate, state.today);
    r.flag = flagFor(r.daysUntil, r.status);
    await applyWrites([
      { range: `${cfg.TABS.reminders}!D${rowNum}`, value: fmtISO(newDate) },
      { range: `${cfg.TABS.reminders}!G${rowNum}`, value: 'Snoozed' },
      { range: `${cfg.TABS.reminders}!O${rowNum}`, value: fmtISOts(new Date()) },
    ], t('action.snoozed', { title: r.title, days }));
    renderAll();
  }

  async function handleAddNote(rowNum) {
    const r = findReminder(rowNum);
    if (!r) return;
    const text = window.prompt(t('prompt.addNote'));
    if (!text) return;
    const stamp = `[${fmtISO(new Date())} ${state.user?.name || 'You'}]`;
    const newNotes = (r.notes ? r.notes + ' \n' : '') + `${stamp} ${text}`;
    r.notes = newNotes;
    await applyWrites([
      { range: `${cfg.TABS.reminders}!J${rowNum}`, value: newNotes },
      { range: `${cfg.TABS.reminders}!O${rowNum}`, value: fmtISOts(new Date()) },
    ], t('action.noteAdded'));
    renderAll();
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
    writes.forEach(w => state.pendingWrites.push({ kind: 'update', row: extractRow(w.range), range: w.range, value: w.value, queuedAt: new Date().toISOString() }));
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
    // tap happened. Refresh every col-O value to now; everything else flushes
    // as queued (in tap order).
    const flushTs = fmtISOts(new Date());
    const isTombstone = (range) => /!O\d+$/.test(range);
    try {
      await gapi.client.sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: cfg.SHEET_ID,
        resource: {
          valueInputOption: 'USER_ENTERED',
          data: queue.map(w => ({
            range: w.range,
            values: [[isTombstone(w.range) ? flushTs : w.value]],
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
    document.getElementById('signout-btn').addEventListener('click', signOut);
    document.getElementById('refresh-btn').addEventListener('click', loadAll);
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
