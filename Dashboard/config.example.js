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
    finance_acct: "Finance-Accts",
    finance_txns: "Finance-Txns",
    finance_bdgt: "Finance-Bdgt",
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
};
