# Family inc. — Dashboard Setup

A single-file PWA that reads (and writes) your `Family_OS` Google Sheet, pinnable to the iPhone home screen.

Three modes:

- **Demo mode** — uses `mock_data.json` baked into the page. No Google account, no server. Open `index.html` in a browser and it just works. Use this to evaluate the UI.
- **Local live mode** — wired to your real Google Sheet, served from `localhost`. Good for development.
- **Deployed live mode** — same as above, served from a static host (GitHub Pages / Vercel / Netlify / Cloudflare Pages). What you actually pin to the iPhone.

## A. Try it now (demo, 30 seconds)

```bash
cd "/Users/adaramir/Documents/Claude/Family Inc/Dashboard"
python3 -m http.server 5173
```

Open `http://localhost:5173/` in a browser. `config.js` ships with `DEMO_MODE: true`, so it loads `mock_data.json` directly. Tap reminders, expand drawers, switch to the Sunday tab. Write-backs show a `(demo)` toast instead of touching anything.

## B. Wire it to your real Sheet (5 minutes)

### 1. Upload `Family_OS.xlsx` to Drive as a Google Sheet

1. Drive → New → File upload → pick `Family_OS.xlsx`.
2. Right-click the uploaded file → Open with → Google Sheets.
3. File → Save as Google Sheets. This makes a new `.gsheet` named `Family_OS` next to the xlsx. Delete the xlsx upload to keep the folder clean.
4. Share it with your partner's Google account (Editor permission). The dashboard does no own access control — Sheet permissions are it.
5. From the Sheet URL, copy the part between `/d/` and `/edit`. That's your **Sheet ID**.

### 2. Get a Google OAuth Client ID

1. Go to https://console.cloud.google.com/, create a new project (call it "family-inc").
2. APIs & Services → Library → search "Google Sheets API" → Enable.
3. APIs & Services → OAuth consent screen:
   - User type: **External**.
   - App name: `Family inc.`
   - User support email: your Gmail.
   - Scopes: add `.../auth/spreadsheets` (the only one we need).
   - Test users: add yourself and your partner's email. (Stays in Testing mode forever — it's a private app.)
4. APIs & Services → Credentials → Create credentials → OAuth client ID:
   - Application type: **Web application**.
   - Name: `family-inc-pwa`.
   - **Authorized JavaScript origins** (add all you'll use):
     - `http://localhost:5173`
     - Wherever you'll deploy (e.g. `https://adar.github.io`)
   - **Authorized redirect URIs**: leave empty (we use the implicit token flow).
   - Save. Copy the **Client ID** (ends in `.apps.googleusercontent.com`).

### 3. Paste credentials into `config.js`

Open `dashboard/config.js` (copied from `config.example.js`) and set:

```js
CLIENT_ID: "1234567890-abc.apps.googleusercontent.com",  // from step 2
SHEET_ID:  "1AbcDefGhIjKlMnOpQrStUv...",                  // from step 1
DEMO_MODE: false,                                          // turn off demo
USERS: {
  "you@example.com": "Adar",
  "partner@example.com": "Partner",
}
```

Reload `http://localhost:5173/`. Click "Sign in with Google", grant access. The dashboard now reads live.

### 4. Deploy to GitHub Pages (M3 wiring — `.github/workflows/pages.yml`)

Pages serves `dashboard/` straight from this repo via the Actions workflow
(branch-mode Pages can only serve `/` or `/docs`). `config.js` is gitignored —
the workflow **generates** it at deploy time from two repo Actions secrets.

1. Repo → Settings → Pages → Source: **GitHub Actions**.
2. Repo → Settings → Secrets and variables → Actions → add `DASHBOARD_CLIENT_ID` and `DASHBOARD_SHEET_ID`.
3. Push to `main` (or run the `pages` workflow manually). URL: `https://<your-user>.github.io/<repo>/`.
4. Add that origin to the OAuth client's **Authorized JavaScript origins** (step 2.4).
5. Visit the URL on each iPhone in Safari. Share → "Add to Home Screen"; it opens fullscreen, no Safari chrome.

Both you and your partner sign in with your own Google accounts. Both have full read/write because both are Editors on the Sheet.

## C. What write-back does

Tapping a reminder reveals three buttons:

- **✓ done** — sets `Status = Done`, stamps `Last Sent = today`. If the row is recurring (Yearly / Monthly / etc.), it also bumps `Due Date` and flips `Status` back to `Pending`. One API call (`spreadsheets.values.batchUpdate`).
- **+ snooze** — opens a row of pills (1d / 3d / 7d / 14d / 30d). Picking one writes a new `Due Date` and sets `Status = Snoozed`.
- **add note** — prompts for free text, appends to the `Notes` column with a `[2026-05-28 Adar]` prefix.

If you're offline (subway), writes are queued in `localStorage.family_inc_writequeue_v1` and flushed automatically when you're back online. The Settings tab shows the queue.

## D. Operating notes

- The dashboard never stores credentials. The OAuth token lives in `sessionStorage` and disappears when you close the tab.
- The OAuth `Client ID` is a public identifier — fine to commit. There is no client secret because this is a browser app using the implicit flow.
- Sheet API quota: free tier is generous (300 req/min). Even a heavy day is ~10 reads + 5 writes.
- iOS Safari PWA quirk: when you "Add to Home Screen", it caches the manifest; if you change the icon, you may need to remove and re-add.
- The Sunday tab is computed from the Sheet, not from `/Briefings/*.md`. This means it always reflects the latest Sheet state, but it diverges from what `sunday_briefing.py` wrote on the actual Sunday. If you'd rather render the markdown file verbatim, add a fetch in `renderSunday()` — left as a follow-up.

## E. Troubleshooting

| Symptom | Fix |
|---|---|
| "OAuth not configured" sign-in screen | `CLIENT_ID` still starts with `PASTE_` in `config.js`. |
| Sign-in popup blocked | Browser blocked the GIS popup. Allow popups for the dashboard's origin. |
| "Access blocked: family-inc has not completed verification" | Your Gmail isn't in OAuth consent screen → Test users. Add it. |
| Sheet loads empty | Make sure tab names match `cfg.TABS` exactly (case-sensitive, including the hyphen in `Calendar-Events`). |
| Write succeeds but UI doesn't update | The optimistic UI may have raced. Pull-to-refresh, or tap Settings → Force refresh. |
| iPhone home-screen icon is a generic globe | Re-deploy with the PNG icons present, remove from home screen, re-add. |

## F. File map

```
dashboard/
├── index.html              # app shell + view markup
├── styles.css              # all styles (light + dark)
├── app.js                  # all logic (~500 lines)
├── config.js               # CLIENT_ID, SHEET_ID, USERS, demo flag
├── manifest.webmanifest    # PWA manifest
├── sw.js                   # service worker (offline shell)
├── icon.svg                # vector icon (used everywhere)
├── icon-180.png            # apple-touch-icon
├── icon-192.png            # PWA icon (Android)
├── icon-512.png            # PWA icon (large)
├── mock_data.json          # demo data (generated from Family_OS.xlsx)
└── README_SETUP.md         # this file
```
