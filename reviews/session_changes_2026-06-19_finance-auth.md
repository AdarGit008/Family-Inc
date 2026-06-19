# Session changes — M6.2 finance interactive auth (2026-06-19)

PO call: build interactive OTP for the cards (option B) over fail-loud-and-skip.
Closing the SPEC §12.2 promise that "the operator re-runs interactively" — which
was previously **unbuilt**. This is a change to the §12.2 auth contract.

## What changed (and why)

- **Hard constraint established from the pinned library source** (`israeli-bank-scrapers`
  6.7.3 + `puppeteer-core` 24.43.1, read directly): Max (`MaxScraper`) and Cal
  (`VisaCalScraper`) accept `{username,password}` only and do **not** implement the
  OneZero-style `triggerTwoFactorAuth`/`otpCodeRetriever` path — so there is **no
  programmatic OTP entry** for them. A typed-OTP mode is impossible without forking.
  Therefore "interactive OTP" = **one-time operator device-trust persisted in a
  per-provider browser profile**, reused headlessly.

- **`automation/finance/scrape.js`:**
  - Daily path now passes a persistent per-provider Chromium profile via
    `--user-data-dir=<finance>/profiles/<provider>` (mode 700). Verified Puppeteer
    honors a `--user-data-dir` supplied in `args` (only fabricates a temp profile when
    none is present) — so the library's `args` channel suffices, no fork.
  - New headed `--auth <provider>` mode: drives its **own** Puppeteer (not
    `scraper.scrape()`, whose `terminate()` closes the page on the operator), navigates
    to the provider login, and waits for the operator to clear the OTP/device-trust once.
  - Heavy deps (`israeli-bank-scrapers`, `puppeteer`) **lazily required** so a bad
    invocation fails its usage check instantly without loading Chromium.
  - Argv dispatcher rejects any unrecognized invocation (typo/stray positional) with
    a loud usage error (exit 2) — never silently runs the daily scrape on a mistyped
    `--auth`. Exit contract documents exit 2.

- **Canon updated to the device-trust contract:** SPEC §12.2 (Auth model / Runtime /
  Failure rows); the "no credential storage" narrowing widened in SPEC §3/§overview,
  CLAUDE.md, and the secrets inventory to name the **device-trust browser profiles**
  (bearer artifacts) as appliance-local stored auth; ENGINEERING browser/toolchain row;
  BACKLOG M6.2.

- **`deploy/FINANCE.md`:** §0 pre-flight rewritten (capability now built); new §4 runbook
  for the one-time headed login on the headless VPS via **xvfb + x11vnc over an SSH
  tunnel**, run as `familyinc`. Notable fixes from internal adversarial review:
  - `xvfb-run` uses `-ac` so x11vnc (a different user, no xauth cookie) can attach to the
    cookie-locked display — without it the VNC window stays black (would have wasted the
    live hour). Safe: `:99` is ephemeral, single-user box, x11vnc binds localhost only.
  - `systemctl stop family-finance.timer` before the auth session (re-armed in §5) so the
    06:00 run can't open the same profile mid-auth (Chrome SingletonLock).

- **`deploy/systemd/family-finance.service`:** `StateDirectoryMode=0700` + `UMask=0077`
  so the finance state tree (now holding live bank session cookies + transaction CSVs) is
  owner-only.

- **Tests:** +7 node-level guards in `tests/test_finance.py` (the docstring claimed
  `node --check` but none existed): syntax parse, `--auth` usage guard, unknown-invocation
  rejection, missing-creds fail-loud. All run without `node_modules` (deps are lazy).
  Full suite **369 → 376 green**.

## For the reviewer — focus

1. Is device-trust persistence (vs typed-OTP) the correct read of the §12.2 auth contract,
   given the library has no OTP entry for Max/Cal? Any soundness gap in the persisted-profile
   approach?
2. Does widening the "no credential storage" non-goal to cover an on-disk bearer
   device-trust cookie jar stay faithful to the principle, or does it stretch it?
3. The `--auth`/headed-login + xvfb/x11vnc/SSH-tunnel runbook: any operational trap left
   that would fail on the live VPS hour?
