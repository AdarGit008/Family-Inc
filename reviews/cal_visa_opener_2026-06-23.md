# Cal/Visa session opener — add the credit card, fix the categorization picture

*Written 2026-06-23 at the close of the second VPS hour. Canon is authority —
`SPEC.md §12.2`, `ROADMAP.md §3.7` (finance-cards-unfreeze), `BACKLOG.md` (M6),
`deploy/FINANCE.md §4`. If this brief and canon disagree, canon wins.*

## The call (PO, 2026-06-23)

Add **Cal (Visa)** to the finance lane — this **un-defers the cards lane**
(ROADMAP §3.7; the "debit-only household, Mizrahi is the complete picture"
assumption is now revised). The `--auth` device-trust path is **built (2026-06-19)
but never exercised**, and `israeli-bank-scrapers` is now on 6.7.8 — so this is an
activation + first-auth job, not a build.

## Why this fixes (most of) the categorization gap — and the part it doesn't

The 06-23 VPS hour found live categorization ~77% blank (90/117 rows). The reframe:

- **The categorizable spend lives on the card, not the debit.** The Mizrahi debit's
  blank rows are largely **non-merchant** — the monthly Cal-bill payment, salary,
  transfers, mortgage/utility direct debits — with terse descriptions the LLM
  correctly returns UNKNOWN for. So much of the "77% blank" is **correctly** blank.
- **What the card fixes:** Cal/Visa rows are per-merchant with cleaner descriptions,
  so rules + LLM gap-fill categorize them far better and the budget actuals finally
  reflect real spend.
- **What it does NOT fix on its own:** the categorization **engine/vocab** still
  matters. RE-CHECK the yield on the first real Cal import; if it's still poor that's
  the rules-vocab / LLM-vocab problem → pair with **Shanee's budget-vocab migration**
  (the authority) + a one-time re-categorize backfill of the still-blank rows. Don't
  assume the card alone makes actuals correct — verify it.

## ⚠ THE double-count landmine — decide BEFORE the first Cal ingest

Once both sources flow, the **same spend is counted twice**: once as the aggregate
**Cal-bill charge** on the Mizrahi debit, and again as the **individual line items**
on the Cal card. The budget actuals would double. **Required design call:** exclude
the debit's Cal-bill line from the budget categories (e.g. a `Transfer`/excluded
bucket, or filter it out of the `SUMIFS`), so only the card line-items count. New for
this lane — settle the mechanism before ingesting Cal.

## The work (a VPS hour — headed device-trust login)

Mechanics verified in `automation/finance/scrape.js` (2026-06-23):
- Cal = `cal` in `bank_creds.json` → `CompanyTypes.visaCal`. `PERSIST_PROFILE`
  includes `cal` → device-trust profile at `<finance-dir>/profiles/cal` (mode 700).
- Cards re-challenge a fresh browser and the library has no programmatic OTP, so a
  one-time **headed `--auth cal`** login the operator drives persists a "remembered
  device" cookie; the daily headless run reuses it (20-min auth timeout).

Steps (`deploy/FINANCE.md §4`):
1. Add the `cal` block to `/etc/family-inc/bank_creds.json` (mode 600, owner familyinc).
2. `apt-get install x11vnc` (provision.sh installs only xvfb+xauth); `systemctl stop
   family-finance.timer` (so the 06:00 run can't grab the profile mid-auth).
3. Headed `--auth cal` under xvfb + x11vnc, viewed over an SSH tunnel; clear the
   SMS/OTP "remember this device" step to the account dashboard, then ENTER.
4. Re-run `family-finance.service`; confirm Cal lands **headless** (profile trusted);
   re-arm `family-finance.timer`.
5. Verify Cal CSV → `Finance-Transactions`, the categorization yield on card rows,
   and that the double-count handling holds.

## Open PO calls

- **Double-count mechanism** (exclude the debit Cal-bill line) — design before ingest.
- Per-card `Owner` default? · cadence (daily vs 2–3×/week — re-challenge noise)? ·
  does a card change the >35d stale-import expectation (a card may have no charges for
  a stretch)?
- After the first Cal import: is Shanee's vocab migration + a backfill still needed
  for completeness? (Likely yes.)

## Canon to update when it ships

- Revise "debit-only household, so Mizrahi is the complete picture" (CLAUDE.md
  current-state, BACKLOG M6.2).
- ROADMAP §3.7 graduates into SPEC §12.2; strike it from ROADMAP.
- BACKLOG: cards un-deferred (a new M6.5 / cards lane); the categorization finding
  revisited against the now-meaningful card data.

## Notes / context carried in

- 6.7.8 lib in place. If a `#/change-pass` timeout returns on Mizrahi, bump-first
  (the standing fragility — see memory / `BACKLOG.md` M6.2). A Cal re-challenge weeks
  later → re-run `--auth cal` (no creds change).
- Finance is fail-loud / no-data-loss; this is box work (a VPS hour): I navigate, the
  PO drives; live-Sheet reads run as `familyinc`.
- Watch the `fail.flag` cleared after the 06-23 07:30 digest (the 06-22 Mizrahi blip);
  if it lingered, that's a GAP-2 fail-flag-clearing-lag to look at.
