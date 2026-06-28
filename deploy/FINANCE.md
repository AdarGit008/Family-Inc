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

- **Mizrahi is password-only** → no `--auth` / device-trust step. *But* the portal may force a
  one-time **password change** (or a terms/confirm interstitial) that a headless run can't
  clear — it surfaces as a `TIMEOUT … #/change-pass` scrape error (seen on first go-live,
  2026-06-19). Clear it once by hand in a normal browser (change the password, then update
  `bank_creds.json`), and the headless run works. Do Mizrahi first and prove the whole pipe on
  it alone (§1–§3).
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

## 6. M6.3 — install the live budget formulas + close

The `Finance-Budget` actuals reconcile via a **text-prefix wildcard** `SUMIFS` on the
ISO-text `Date` (`<yyyy-mm>&"*"`), NOT a serial `DATE()` window (which reads ₪0 against
RAW-appended text dates). Don't hand-copy them — run the **installer**, which is the
single source of the formula text (`automation/lib/finance_budget.py`, pinned against the
committed seed by `tests/test_finance.py`):

```bash
# As familyinc, with the live Sheet env loaded (FAMILY_INC_SHEET_ID). Preview first.
python3 /opt/family-inc/automation/finance_budget_formulas.py --dry-run
python3 /opt/family-inc/automation/finance_budget_formulas.py            # stamp it
```

It reads the live `Finance-Budget` tab, validates the load-bearing column order (fails
loud on drift), and stamps **only** the machine columns — Actual/Variance/%/YTD/Last-Month
per category, the `I`-helper date tags, and the TOTAL sums — keyed off whatever category
rows the tab has. **A category row's Category and Monthly Target, and every Notes cell,
are never written** (the only Target it writes is the TOTAL row's `=SUM`), so it's
idempotent and re-running after a budget change just re-stamps for the new rows.
*(Re-stamps the current rows; it does not clear machine cells on a row you delete as a
category — clear those by hand.)* Then confirm actuals go **non-zero** on the first
real month (Groceries/Transport/Health).

- **Absent machine columns are auto-titled (hardened 2026-06-20):** the installer
  owns the machine columns (`Actual`/`Variance`/`%`/`YTD`/`J` Last-Month + the `H`/`I`
  helper block), so when a tab simply *lacks* one it **titles the column itself and
  stamps** — no hand-fix. This was the live 2026-06-20 case (the tab predated the M6.4
  block, so it was A–I only with no `J` `Last Month (ILS)`); it's also what a fresh
  budget from Shanee's migration looks like (only `Category`/`Monthly Target` filled).
  What it still **refuses** (fail loud): a *human* header (`Category` / `Monthly
  Target`) missing or renamed, or a machine header holding a *different* value (a real
  column shift). So before a fresh-tab stamp, ensure only the two human headers are
  present and exact — the installer provides the rest. (`deploy/FINANCE.md` was
  briefly amended 2026-06-20 to add `J1` by hand; the hardening superseded that.)
- **No stray-formula risk:** there's no manual copy, so the old "stray Notes-column
  `SUMIFS`" copy artifact can't happen — the installer emits no Notes cell (pinned by
  `test_budget_installer_never_writes_notes_column`).
- **Category-vocab gap (expected, not a bug yet):** the rules engine emits `Dining out`,
  `Health`, … but the budget also has rows `Subscriptions`, `Savings`, `Other` with no
  matching rules category — so those actuals read **₪0** even with perfect ingest. The
  vocab is **PROVISIONAL** pending Shanee's budget migration, which is the vocabulary
  authority. Don't unilaterally rename buckets to close this — it's a PO/Shanee call;
  when she maps them, just re-run the installer.

M6.3 acceptance is the first real **monthly** review (~30 days of live data).

### Budget-vocab migration — exactly what we need from Shanee

Shanee is the **vocabulary authority**: the `Finance-Budget` category list is what the
rules engine must map to (the actuals `SUMIFS` keys on the literal `Category` string, so
a label mismatch reads ₪0). She delivers it by filling **two columns of the live
`Finance-Budget` tab directly** — the installer titles + stamps every machine column
itself, so she touches only:

1. **Column A — `Category`:** the canonical list. Confirm / rename / split / merge / drop
   the provisional 11 the rules engine emits today — **Health, Groceries, Transport,
   Childcare, Utilities, Housing, Dining out, Entertainment, Shopping, Income, Fees**
   (pick a language per label; the briefing + dashboard render the string verbatim).
2. **Column B — `Monthly Target (ILS)`:** a target per category (approximate is fine).
   Drives variance / % / over-budget; a row with no target is skipped by the Money
   section. *(These ₪ values live in the Sheet only — never the repo.)*
3. **The 3 currently-unmapped labels — `Fees`, `Income`, `Shopping`:** the rules emit
   them but no budget row exists yet (held as an allow-list, so their spend reads ₪0).
   For each: **add a row** (give it a target), **remap** the rule to another category, or
   **drop** it.
4. **Where `Income` lives:** it's positive (not spend) — decide a budget row (target =
   expected income) **or** out-of-grid (recommended; the actuals `SUMIFS` negates spend,
   so an income row reads oddly).

Then re-point the rules seed to her exact labels (if renamed), shrink the
`Fees/Income/Shopping` allow-list in `test_rules_vocab_within_budget_categories`, and
re-run the installer (§6) + the backfill (§7). No code from her — only A:B.

## 7. M6.4/M6.5 — re-categorize backfill + coverage (the 06-26 gate)

`finance_ingest` categorizes **new rows only**, so the rows that landed before the
M6.5 `Card Settlement` rule existed stay blank. Apply that rule (and any merchant
the engine now covers) to history with the **one-time backfill**, then read the
**coverage** the milestone accepts on. Run **as `familyinc`** (live Sheet env + the
project venv) — the same invocation the systemd units use: `uv run --no-sync python`,
from `/opt/family-inc`. Bare `python3` as `root` has neither the creds nor the deps.
From a **root** shell: `sudo -u familyinc -i sh -c 'cd /opt/family-inc && …'`. If you're
**already in the `familyinc` shell**, drop the `sudo` and run `uv run …` directly —
`familyinc` is not granted `sudo -u familyinc` (it would be denied).

```bash
# 1. Baseline coverage (read-only — writes nothing).
uv run --no-sync python automation/finance_coverage.py --write   # → Briefings/<date>_finance_coverage.md

# 2. Preview the backfill (rules-only, no write). Sanity-check: the Card Settlement
#    count is ~66 ONLY if history isn't already excluded — on the 06-28 run it was
#    (finance_ingest had tagged the mirrors), so the dry-run showed 0; the live run's
#    DeepSeek gap-fill is then the only lift.
uv run --no-sync python automation/finance_recategorize.py --dry-run

# 3. Run it for real (rules + DeepSeek gap-fill; --no-llm for rules-only).
uv run --no-sync python automation/finance_recategorize.py

# 4. Re-read coverage — confirm the lift + that excluded(Card Settlement) jumped.
uv run --no-sync python automation/finance_coverage.py --write
```

The backfill is **idempotent** (touches blank rows only) and **safe to re-run** —
re-run after Shanee's budget-vocab migration re-points the rules, or whenever a new
card's source comes online. **Accept bar set report-first 2026-06-28: coverage
landed at 88% (137/155 budget-eligible rows; +OBSIDIAN rule → ~89%).** The headline
is gated by *structure*, not classifier quality — of the 18 still-blank, ~12 are
merchant-less wrappers (Leumi ATM cash ×9, BIT/PAYBOX P2P, an ANOMALY) that are
**correctly** blank, so of genuinely-categorizable rows it's ~96%. Coverage is *not*
correctness — a true categorizer FP rate is deferred (`ROADMAP.md` rank 12). **One
residual class has no home:** a **household-specific local merchant** (e.g. a local
grocery) can't enter the public, portfolio-safe `seeds/14_…csv` (national brands +
generic labels only) and there's no box-local overlay yet → tracked as the
**finance-local-rules-overlay** forward item (`ROADMAP.md`); until it lands, such a
merchant stays blank by design.

**Summarizer accuracy (the other half of the gate):** run the weekly review over
≥1 week of live classifier output and confirm **< 1 ALERT-tier false positive/week**;
the fix for an over-firing pattern is narrowing it in the group-config seed.

```bash
uv run --no-sync python automation/accuracy_review.py --weeks 1   # → Briefings/<date>_accuracy_review.md
```

## Day-to-day

No digest/finance section by 08:00 → the fail-flag and `journalctl -u family-finance` tell
the story. Code reaches the box only via `deploy.sh`. The lane is silent by design — the
only finance *message* is fail-loud.
