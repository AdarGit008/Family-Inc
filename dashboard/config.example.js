// Family inc. dashboard — config TEMPLATE (ENGINEERING.md §3).
//
// Copy to config.js and fill in. The real config.js is gitignored — it carries
// your Sheet ID, OAuth client id, and account emails, which stay off the
// public repo by construction.

window.FAMILY_INC_CONFIG = {
  // From Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs.
  // Type must be "Web application". Authorized JS origins must include where
  // you serve the PWA from (e.g. http://localhost:5173 and your GitHub Pages URL).
  CLIENT_ID: "PASTE_YOUR_CLIENT_ID_HERE.apps.googleusercontent.com",

  // The Spreadsheet ID from the Google Sheets URL.
  // https://docs.google.com/spreadsheets/d/<THIS_PART>/edit
  SHEET_ID: "PASTE_YOUR_SHEET_ID_HERE",

  // Sheet tab names. Change only if you renamed tabs in Family_OS.
  TABS: {
    reminders: "Reminders",
    calendarEvents: "Calendar-Events",
    people: "People",
    finance_acct: "Finance-Accounts",
    finance_txns: "Finance-Transactions",
    finance_bdgt: "Finance-Budget",
    goals: "Goals",
    health: "Health",
    education: "Education",
    car: "Car",
    contracts: "Contracts",
    settings: "Settings",
  },

  // FALLBACK identity map (email → display name), used only until the Sheet's
  // Settings tab loads or when it has no UserMap rows. The live mapping is
  // Settings.UserMap in Family_OS (SPEC §7.6) — edit it there, not here.
  USERS: {
    "you@example.com": "Adar",
    "partner@example.com": "Shanee",
  },

  // Demo mode loads mock_data.json instead of talking to Google.
  DEMO_MODE: true,

  // Asia/Jerusalem matches the rest of Family inc.
  TIMEZONE: "Asia/Jerusalem",

  // Love-note endpoint (V3.7) — the public HTTPS URL of the appliance love-note
  // server, fronted by a Cloudflare Tunnel. Set at deploy time from the
  // DASHBOARD_LOVENOTE_URL secret (pages.yml). BLANK or left as the placeholder
  // → the love-note card/composer never renders (never promise a dead
  // affordance). No trailing slash; the dashboard appends "/lovenote".
  LOVENOTE_URL: "PASTE_YOUR_LOVENOTE_URL_HERE",
};
