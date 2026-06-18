# deploy/FINANCE.md — the finance go-live hour (M6.2 + M6.3)

*Runbook = ordered commands. The "why" lives in `SPEC.md` §12.2 and `BACKLOG.md`
(M6); if they disagree, SPEC wins and the disagreement is a bug. This covers the
appliance side of M6 only — the repo half (scraper, ingest, rules engine, budget
formulas) ships and is tested. Everything below runs on the VPS as root / `familyinc`;
git operations stay on the PO's machine.*

Layout recap: `automation/finance/scrape.js` (Node, read-only login → one CSV per
provider) → `automation/finance_ingest.py` (Python, the only Sheet writer). Driven by
`systemd/family-finance.{service,timer}` (06:00 daily, before the 07:25 engine read).
`provision.sh` already ran `npm ci` in `automation/finance/` and enabled the timer — but
the lane is **inert until `bank_creds.json` is placed**, so a clean box is safe.

## 0. Pre-flight (decide BEFORE you start)

- **Mizrahi is password-only** → it works end-to-end today. Do it first and prove the
  whole pipe on it alone.
- **Max + Cal can OTP-challenge, and there is no interactive-OTP code yet.** `scrape.js`
  is headless-only (`showBrowser: false`, no headed/TTY/argv path); an OTP re-challenge
  **fails loud** (`_scrape_errors.json` → the next digest reports it) but cannot be
  answered interactively. SPEC §12.2 promises "the operator re-runs interactively" — that
  capability is **unbuilt**. Decide with the PO before the cards step: either accept
  fail-loud-and-skip on a challenge, or build a headed/interactive mode first (a code
  change to the §12.2 auth contract — needs a PO call).

## 1. Rename the 3 live-Sheet tabs (load-bearing)

In the **live `Family_OS` Google Sheet** (NOT the committed seed), rename the finance
tabs to the standardized full names the code reads:

| Old (as-built short) | New (standardized) |
|---|---|
| `Finance-Accts` | `Finance-Accounts` |
| `Finance-Txns`  | `Finance-Transactions` |
| `Finance-Bdgt`  | `Finance-Budget` |

These exact names are what `automation/lib/config.py` (`FINANCE_*_TAB`) and the dashboard
`config.js` `TABS` read. **Also update the live (gitignored) `dashboard/config.js`** so
`finance_acct/finance_txns/finance_bdgt` use the full names (the template
`config.example.js` already does) — otherwise the Money drawer reads a non-existent tab
after the rename. Renaming a tab preserves its data and formulas.

## 2. Place credentials (Mizrahi only, first)

```bash
# /etc/family-inc/bank_creds.json  (mode 600, owner familyinc)
# Copy deploy/bank_creds.example.json and fill ONLY the mizrahi block to start.
# Read-only portal logins. Omit a provider block to skip it.
sudo install -o familyinc -g familyinc -m 600 /dev/stdin /etc/family-inc/bank_creds.json <<'JSON'
{ "mizrahi": { "username": "…", "password": "…" } }
JSON
```

## 3. Verify the Mizrahi roundtrip (live)

```bash
# Run the oneshot by hand (node scrape → python ingest), then read the logs.
sudo systemctl start family-finance.service
journalctl -u family-finance.service -n 80 --no-pager
ls -l /var/lib/family-inc/finance/        # expect mizrahi_<date>.csv, no _scrape_errors.json
```

Confirm in the Sheet: `Finance-Transactions` gained rows (with `Category`/`Cat-Source`
populated by the rules engine), and `Finance-Accounts` shows Mizrahi with a fresh
`Last Imported`. A re-run must be idempotent (dedup → 0 new). If `_scrape_errors.json`
appears, the run **persisted the good data then failed loud** — read the marker.

## 4. Add the cards (Max + Cal) — only after the §0 OTP decision

Add the `max` and `cal` blocks to `bank_creds.json`, re-run §3. On a Max/Cal OTP
re-challenge the run fails loud and skips that provider; the good providers still land.
**Cadence is the first tuning knob** (§12.2): if the cards challenge often, drop them to
2–3×/week and keep the bank daily.

## 5. Enable the timer

`provision.sh` already `enable`d `family-finance.timer`. Confirm it is active and the next
fire is sane:

```bash
sudo systemctl list-timers 'family-finance*' --no-pager   # next ~06:00 Asia/Jerusalem
```

M6.2 closes once a live scrape→Sheet roundtrip is verified on at least Mizrahi.

## 6. M6.3 — apply the live budget formulas + close

The `Finance-Budget` actuals reconcile via a **text-prefix wildcard** `SUMIFS` on the
ISO-text `Date` (`<yyyy-mm>&"*"`), NOT a serial `DATE()` window (which reads ₪0 against
RAW-appended text dates). The committed seed (`Family_OS.xlsx` `Finance-Budget`) carries
the correct form (pinned by `tests/test_finance.py::test_seed_budget_uses_text_prefix_not_serial_sumifs`).
Copy those formulas onto the live `Finance-Budget` tab and verify actuals go **non-zero**
on the first real month.

Cautions when applying:
- **Do NOT propagate the seed's stray `SUMIFS` in the Transport-row Notes column** — it is
  a copy artifact, not a real actual. Apply only the intended `C`/`F`/`J` column formulas.
- **Category-vocab gap (expected, not a bug yet):** the rules engine emits `Dining`,
  `Entertainment`, … but the budget has rows `Dining out`, `Subscriptions`, `Savings`,
  `Other` with no matching rules category — so those actuals read **₪0** even with perfect
  ingest. The vocab is **PROVISIONAL** pending Shanee's budget migration, which is the
  vocabulary authority. Do not unilaterally rename buckets to close this — it's a PO/Shanee
  call.

M6.3 acceptance is the first real **monthly** review (~30 days of live data).

## Day-to-day

No digest/finance section by 08:00 → the fail-flag and `journalctl -u family-finance` tell
the story. Code reaches the box only via `deploy.sh`. The lane is silent by design — the
only finance *message* is fail-loud.
