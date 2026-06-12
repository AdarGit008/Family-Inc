# Bank scraper — Render setup (10 manual steps, ~30 min)

Decision 2026-06-03: providers = **Mizrahi + Max + Cal**, runtime = **Render cron**.
Full runbook: `../../Setup/01_Israeli_Bank_Scrapers.md`.

## Adar's checklist

1. Create a private GitHub repo containing this `bank-scraper/` folder (it can live in the same repo as `Dashboard/` if you set Render's root directory to `Automation/bank-scraper`).
2. In Google Cloud Console: create a project → enable **Drive API** → create a **service account** → download its JSON key.
3. In Google Drive: share the `Finance_CSVs` folder with the service-account email (Editor). Copy the folder ID from its URL.
4. Sign in to [Render](https://render.com) → **New → Blueprint** → point at the repo (`render.yaml` is picked up automatically). Or create the Cron Job manually with `npm install` / `node scrape.js`, schedule `30 3 * * *` (= 06:30 Israel summer time).
5. Set env vars in the Render dashboard:
   - `MIZRAHI_USERNAME`, `MIZRAHI_PASSWORD`
   - `MAX_USERNAME`, `MAX_PASSWORD`
   - `CAL_USERNAME`, `CAL_PASSWORD`
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — paste the entire JSON key as one line
   - `FINANCE_CSV_FOLDER_ID` — from step 3
   You can set only one provider's creds to start; the script skips providers with missing vars.
6. Trigger a manual run from the Render dashboard ("Trigger Run").
7. Check the run log: expect `[ok] mizrahi: N txns → Drive (created)` per provider.
8. Confirm `mizrahi_<today>.csv` (etc.) appeared in Drive `Finance_CSVs`.
9. Confirm rows land in `Finance—Transactions` on the next sheet sync.
10. Turn on Render email notifications for failed runs (Settings → Notifications).

## Notes

- **No creds in source, ever.** Env vars only, `sync: false` in the blueprint so they're never committed.
- Filename pattern `<bank>_<YYYY-MM-DD>.csv` is load-bearing — the existing ingest watches for it. Don't change it.
- Reruns on the same day overwrite that day's file (idempotent), so a manual retry won't double-ingest.
- 2FA: Max and Cal occasionally challenge new devices. If a provider starts failing with an OTP error, run once with `showBrowser: true` locally to clear it, or check the israeli-bank-scrapers issue tracker for the provider.
- Cost: Render cron free tier covers a daily 2-minute job. ₪0.
