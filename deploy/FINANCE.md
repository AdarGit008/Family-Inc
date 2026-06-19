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

## 0. Pre-flight (read BEFORE you start)

- **Mizrahi is password-only** → it works end-to-end headless today. Do it first and prove
  the whole pipe on it alone (§1–§3). It needs no `--auth` step.
- **Max + Cal re-challenge a fresh browser, and `israeli-bank-scrapers` 6.7.3 has no
  programmatic OTP entry for them** (username+password only — there is no code path to type
  an OTP in). The mechanism is **device-trust persistence**: each provider has a persistent
  Chromium profile (`<finance-dir>/profiles/<provider>`), and a **one-time headed login you
  drive by hand** (`scrape.js --auth <provider>`) clears the challenge once. The portal then
  trusts that profile, so the daily headless run reuses it and is not re-challenged. On the
  headless VPS the headed browser is shown via **xvfb + x11vnc over an SSH tunnel** — the
  full procedure is **§4**. Do the cards there, after Mizrahi proves the pipe.
- **Run everything as `familyinc`** (the unit's user) so the profile the daily run reads is
  owned by the daily run. A profile authorized as `root` is unreadable by the timer.

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

## 4. Add the cards (Max + Cal) — one-time device-trust, then daily-headless

Add the `max` and `cal` blocks to `bank_creds.json` (§2). A first **headless** run will
likely fail loud on a device/OTP challenge for a card — that is expected; clear it once with
the headed `--auth` login, which trusts this box's browser profile so the daily run rides it.

**4a — install x11vnc and pause the daily timer (one-time):**

```bash
sudo apt-get install -y x11vnc          # xvfb is already present (property scraper)
sudo systemctl stop family-finance.timer  # so the 06:00 run can't open the same
                                          # profile mid-auth (Chrome SingletonLock).
                                          # Re-armed in §5; Persistent=true catches up.
```

**4b — run the headed login on the box, as `familyinc`, under xvfb.** Both terminals run
as `familyinc` and share a **pinned** xauth cookie, so x11vnc can attach to `:99` while the
display stays access-controlled (no `-ac` — `:99` will be showing a live banking session,
so it must not be open to every local process):

```bash
# Terminal A: headed Chrome on :99; -f pins the xauth cookie to a known path.
sudo -u familyinc xvfb-run -f /tmp/finance-xauth --server-num=99 \
  -s '-screen 0 1280x900x24' \
  node /opt/family-inc/automation/finance/scrape.js --auth max
# Terminal B (give A a second to bring :99 up): same user + pinned cookie, localhost only.
sudo -u familyinc env XAUTHORITY=/tmp/finance-xauth \
  x11vnc -display :99 -auth /tmp/finance-xauth -localhost -rfbport 5900 -nopw -forever
```

**4c — view + drive it from your laptop:**

```bash
ssh -L 5900:localhost:5900 <box>        # tunnel; then open any VNC viewer → localhost:5900
# In the VNC window: log into Max, complete the SMS/OTP "remember this device" step until
# you reach the account dashboard. Then go back to Terminal A and press ENTER to close it.
# (The session auto-closes after 20 min if you don't — just re-run --auth.)
```

> Alternative if you'd rather not run a VNC server: `ssh -X <box>` and run the same
> `sudo -u familyinc … --auth max` with the forwarded `DISPLAY` — the browser renders on
> your laptop, no xvfb/x11vnc. (You must `xauth add` the forwarded cookie for `familyinc`;
> we default to on-box VNC so the trusted browser is the same Chromium/IP as the daily run.)

The trust cookie is now persisted in `<finance-dir>/profiles/max/`. Repeat 4b–4c for `cal`.
Then re-run §3 (`systemctl start family-finance.service`) and confirm both cards land
**headless**. If a card still re-challenges, the trust didn't take — re-run `--auth` for it
(and see §12.2: cadence is the tuning knob — drop noisy cards to 2–3×/week).

> If device-trust ever expires (a card starts re-challenging weeks later), the fix is the
> same one-time `--auth` login — no creds change. A corrupt profile is recoverable by
> `rm -rf <finance-dir>/profiles/<provider>` then re-running `--auth`.

## 5. Enable the timer

`provision.sh` already `enable`d `family-finance.timer`. If you stopped it for the §4 auth,
re-arm it, then confirm it is active and the next fire is sane:

```bash
sudo systemctl start family-finance.timer                 # re-arm if §4a stopped it
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
