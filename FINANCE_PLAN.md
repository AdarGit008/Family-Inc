# Finance Ingestion — Build Plan (M6)

*Output of the 2026-06-17 finance planning session (Adar leading; **plan-only** — no appliance touch, no code lane opened). Executes the pre-resolved D-031 architecture, now thawing. The joint calls below were **co-signed by Shanee on 2026-06-17** (she'll refine later if needed) — ready to land as D-049. A future build session lands the code + the canon edits; this doc is consumed then (cf. `DATA_FETCHING_SESSION_PROMPT.md`, removed at D-035).*

---

## 1. Decisions taken this session → draft **D-049** (pending Shanee co-sign)

These are **major directional, joint** calls (a frozen lane + a non-goal amendment). Adar took them as session lead; banks/budget is Shanee's domain (kickoff), so the thaw and the credential amendment are not live until she co-signs and the row lands in `DECISIONS.md`.

| Field | Content |
|---|---|
| **Decision** | (a) **Finance-ingestion lane UNFROZEN** — the unfreeze condition (a real ~20–30 min/month finance review) is committed. (b) **The "no credential storage" non-goal is amended**: the appliance MAY store **read-only** bank/card portal logins, on the one box, mode 600. "No money movement" is **unchanged** — the scrapers are read-only by nature and cannot transfer. (c) **Scope:** Mizrahi-Tefahot (bank) + Max + Cal (cards); **raw, uncategorized** transactions only (D-033 — categorization/anomaly stay killed). Investments/brokerage explicitly **out of scope** this round. |
| **Why** | The data finally has a standing consumer (committed monthly review + the already-built briefing Money section + dashboard drawer). The amendment is narrow and defensible: service keys were always stored (Apify/DeepSeek/SMTP, D-040); the line held until now was a *portal login*, and a read-only login keeps the load-bearing "no money movement" principle fully intact. |
| **Supersedes** | The `Finance ingestion` frozen-lane row in `BACKLOG.md`; D-033(a) "stays frozen"; the `credential storage` absolute in SPEC §4 Non-goals + the §1 "never stores bank credentials" line (both narrowed, not deleted). |
| **Status** | **Co-signed (Adar + Shanee), 2026-06-17.** Ready to land as the D-049 row below, on Adar's machine. |

**Guardrails the "permit fully" posture implies** (Adar chose full creds for all three up front, not the minimal-start option — so the blast radius is larger on day one and these matter more):

- `/etc/family-inc/bank_creds.json`, **mode 600**, family-inc-owned, never in git (it's in `/etc`, outside the repo by construction), never logged.
- Read-only blast radius: a box compromise leaks *financial visibility*, never transfer capability (no money movement) and no card PANs beyond what a statement shows.
- Optional hardening (boring, recommend if we want it): `systemd` `LoadCredentialEncrypted=` so the creds decrypt only into the unit's runtime rather than sitting plaintext like the other `/etc/family-inc` secrets. Default if we skip it = mode-600 plaintext, consistent with the existing secret posture.

## 2. Architecture — confirm **D-031**, with 2026 deltas

D-031 still holds end-to-end. Runtime = the VPS, a `systemd` timer; `israeli-bank-scrapers` (Puppeteer/headless-Linux); **no second runtime** (D-018), **no Drive** (D-016 — `lib/sheet` is the sole writer). The flow:

```
systemd timer ~06:00
  └─ node automation/finance/scrape.js          # the only new Node besides the bridge
        reads /etc/family-inc/bank_creds.json    # mode 600
        logs into Mizrahi / Max / Cal (read-only)
        writes /var/lib/family-inc/finance/<provider>_<YYYY-MM-DD>.csv
  └─ python automation/finance_ingest.py         # CSV → normalize → dedup
        writes via lib/sheet  →  Finance-Accts (balances) + Finance-Transactions (raw)
```

Node scrapes, **Python owns every Sheet write** — keeps D-016 intact and mirrors the existing split. The CSV on local disk is the only staging (no Drive-as-queue).

**Deltas vs the D-031-era assumptions (and the stale attic plan):**

- **Library is healthy in 2026** — `israeli-bank-scrapers` latest **6.7.3**, published ~11 days ago, "Healthy". Bump the D-031 pin from "6.7.x" to a specific current tag. Requires **Node ≥ 22.12** — the bridge already runs Node 22 (D-029), confirm the installed minor at build.
- **Anti-bot: clean path for this mix.** The 2026 Cloudflare Bot-Management wall hits **Isracard/Amex** — which we're **not** ingesting. Mizrahi/Max/Cal scrape without it. If a wall ever appears, the escape hatch is already proven on the property lane: the maintained anti-detect fork (`@sergienko4/israeli-bank-scrapers`, Camoufox) first (free, on-box), then a managed-proxy pivot (the D-040 Apify precedent). No proxy needed today.
- **Browser dep is already provisioned.** M5 put headless Chromium + Xvfb on the box (`provision.sh` §4b, D-037/D-039) — exactly the shared dep SPEC §12.1 anticipated finance reusing. Build note: point Puppeteer at the provisioned Chromium (`PUPPETEER_EXECUTABLE_PATH`) or let it manage its own; reuse the `xvfb-run` unit wrapper either way.
- **Render + the `Finance_CSVs` Drive folder stay dropped** (D-031). The `attic/bank-scraper/` README is the *old* Render/Drive plan — port off it, don't follow it.

**2FA / OTP** (D-031, unchanged): first run **interactive** (Adar enters the OTP once per challenging provider; session persisted under `/var/lib/family-inc/finance/<provider>_session/`). Later re-challenges **fail loud** → fail-flag → next digest ("⚠ Max צריך אימות מחדש"), never silent. Mizrahi is typically password-only; Max/Cal challenge new devices.

**Cadence:** confirm D-031's **~06:00 daily** (before the 07:25 engine read, so fresh balances feed the briefing and the >35d staleness is accurate). Transactions fetched as "since last success, with a few-days overlap" + dedup. If Max/Cal OTP challenges prove noisy, **cadence is the first knob** — drop the cards to 2–3×/week, keep the bank daily.

## 3. Data model — reconcile the drift, add transactions

**SPEC-vs-code disagreement to surface (not silently fix — repo guardrail).** SPEC §6 lists the tab as `Finance-Budget`; the code reads as-built **`Finance-Bdgt`** (`weekly_briefing.section_money`) and **`Finance-Accts`** (the >35d stale-import check), with an in-code comment already flagging this since 2026-06-12 and deferring to a PO rename. The build session resolves it one of two ways:

- **Recommend — standardize now** while we're in the lane: `Finance-Accounts`, `Finance-Transactions`, `Finance-Budget`; update the 2 consumer reads + SPEC §6. Kills the drift permanently. Low risk (tabs are placeholder — no ingestion has run).
- Alternative — keep the short as-built names and fix SPEC §6 to match. Zero code churn.

Tabs (schema **additive-only** — old rows must keep parsing):

| Tab | Role | Columns (raw — no category, D-033) |
|---|---|---|
| `Finance-Accts` *(exists)* | One row per account/card; balances + freshness. Feeds the briefing KPI + dashboard Money drawer + the >35d stale-import warning. | `Account` · `Type` (bank/card) · `Balance` (ILS) · `As-Of` (last good scrape) · `Last Imported` (datetime) |
| `Finance-Transactions` *(new)* | One row per transaction, append-only. Feeds month-to-date spend + the monthly review. | `Date` · `Amount` (ILS, signed) · `Description` (raw Hebrew merchant) · `Account` · `Txn-ID` (dedup key) · `Imported-At` |
| `Finance-Bdgt` *(exists, manual)* | Shanee's budget targets. **Separate track** — see §4. Not written by ingestion. | (as-built) |

**Dedup / retention:** `Txn-ID` = provider id if given, else a stable hash of `date+amount+description+account`; same-day reruns overwrite that day's CSV and dedup on ingest, so reruns are idempotent (mirror M5's "gate the advance on a successful Sheet write", D-037). Keep **all** transactions (low volume, the monthly review and trend KPIs want history); revisit a `Finance-Transactions-Archive` rolloff only if it ever grows.

## 4. Build plan (milestone **M6**)

Even with creds permitted for all three, build incrementally — same discipline as M5.

- **M6.1 — Repo port + schema (hermetic, no appliance).** Un-attic the scraper into `automation/finance/scrape.js`, stripped of Render/Drive; `automation/finance_ingest.py` (CSV → `lib/sheet`); add `Finance-Transactions`; `family-finance.{service,timer}` (~06:00, `TimeoutStartSec`/`MemoryMax`, `OnFailure` → fail-flag); `provision.sh` finance section. Tests: mock CSV → ingest → mock Sheet; dedup/idempotency; fail-loud on missing creds; stale-import warning. No live bank contact.
- **M6.2 — Appliance deploy + first interactive auth (the "VPS hour").** Place `bank_creds.json` (mode 600). Mizrahi first (simplest, password-only) → verify CSV→Sheet roundtrip live → Max + Cal (interactive OTP once each, session persisted). Enable the timer. Expect the same deploy-time hermeticity checks M5 hit (D-038/D-041 — tests must not reach the live Sheet/creds).
- **M6.3 — Consumer wiring + close.** Confirm the briefing Money section renders live balances + MTD spend, the stale warning fires, the dashboard Money drawer reads live. **Acceptance of the lane = the first monthly review actually happening** (~30 days in) — that's the unfreeze condition made real. External milestone review folds in per the D-035 precedent.
- **Parallel — Shanee's budget migration** (her domain, separate session): her existing manual budget → `Finance-Bdgt`. This is what makes actuals-vs-target meaningful; the kickoff already flagged it as a pending Shanee follow-up. Ingestion delivers raw actuals regardless; budget gives them a denominator.

## 5. Failure modes & delivery

Delivery is **silent, like property** — finance lands in the Sheet and surfaces in the weekly briefing + dashboard, **never an alert** (briefings > notifications, §3). The only finance *message* is fail-loud.

| Failure | Detection | Behavior |
|---|---|---|
| OTP re-challenge (Max/Cal) | scraper auth error | fail-flag → next digest "⚠ <provider> צריך אימות מחדש"; Adar re-runs interactive; tune cadence if frequent |
| Scraper breaks (bank site change / lib regression) | scrape throws → CSV not written | fail-flag → digest; weekly escalates via the >35d stale-import line; mitigation = pinned version + the maintained fork as fallback |
| Cloudflare wall appears on Mizrahi/Max/Cal | challenge page | M5 playbook: anti-detect fork (free) → managed-proxy pivot (D-040) if needed |
| Box compromise | — | read-only visibility only; **no transfer capability** (no money movement); creds mode-600 + optional encrypted-credentials |
| Sheet write fails | `lib/sheet` error | ingest fails loud; CSVs retained on disk (no data loss); retry next run |
| Double-ingest | — | `Txn-ID` dedup → idempotent |

**Watch item — the kickoff "ouch > ₪500 single charge" threshold.** Transactions now flowing makes this *possible* to surface, but it's an **alert path** (2/day budget) and brushes the killed anomaly lane (D-033). **Recommend deferring** to a deliberate Shanee call — keep ingestion raw/silent first; don't bolt an alert onto the thaw.

## 6. Open items before/at build

1. **Shanee co-sign** on the thaw + the credential-non-goal amendment (§1). Major joint call — not live until logged.
2. **Tab-rename call** (§3): standardize now (recommended) vs keep as-built + fix SPEC.
3. **Budget migration** scheduling (Shanee session) — independent of M6.1.
4. **Confirm at build:** Node minor ≥ 22.12 on the box; Puppeteer→Chromium path; the encrypted-credentials hardening yes/no.
5. **Canon edits the build session will make** (not now): SPEC §4/§1 non-goal narrowed + new §12.2 finance ingestion contract; `BACKLOG.md` finance row → M6; `DECISIONS.md` D-049.

## 7. Handoff (run on Adar's machine — git ops never in the sandbox)

```
# 1. [done 2026-06-17] Shanee co-signed the §1 thaw + credential amendment.
# 2. [done 2026-06-17] D-049 added to DECISIONS.md; SPEC §12.2 inserted; §4/§1 non-goal narrowed.
# 3. [done 2026-06-17] BACKLOG.md: frozen Finance row removed, M6 section added, status note added.
# 4. Regenerate the next entry point:  python3 automation/session_kickoff.py
# 5. Stage + commit + push:
git add FINANCE_PLAN.md DECISIONS.md BACKLOG.md NEXT_SESSION_PROMPT.md
git commit -m "plan: finance ingestion thaw (M6) — draft D-049 pending co-sign"
git push
# The build session opens by reading FINANCE_PLAN.md (this doc) once D-049 is ratified.
```

---

## Appendix A — draft SPEC §12.2 (lift verbatim into `SPEC.md` after §12.1, when D-049 lands)

### 12.2 Finance — Mizrahi / Max / Cal (unfrozen 2026-06-17, D-049)

A committed monthly finance review is the standing consumer. Build = **M6**; **raw transactions only** (D-033 — no categorization/anomaly). Reuses the M5 browser dependency; investments/brokerage out of scope.

| Facet | Spec |
|---|---|
| **Source** | The online portals of Mizrahi-Tefahot (bank) + Max + Cal (cards), read via `israeli-bank-scrapers` (Puppeteer/headless-Linux, pinned 6.7.3, Node ≥ 22.12). No public API; the library drives each portal's web session. **Read-only by nature** — it fetches balances + transactions but cannot move money (the §4 "money movement" non-goal stays absolute). |
| **Mechanism** | A `systemd` timer runs `automation/finance/scrape.js`: logs into each provider with creds from `/etc/family-inc/bank_creds.json`, fetches balances + the transaction window (since last success, with a few-days overlap), writes one CSV per provider to `/var/lib/family-inc/finance/<provider>_<YYYY-MM-DD>.csv`. `automation/finance_ingest.py` then normalizes, dedups on `Txn-ID`, and writes via `lib/sheet` (sole Sheet writer, D-016). Node scrapes; **Python owns every Sheet write**. The local CSV is the only staging — no Drive (D-031). Same-day reruns overwrite the day's CSV and dedup on ingest → idempotent; the import advance gates on a successful Sheet write (mirrors §12.1 / D-037). |
| **Runtime** | One `systemd` timer (`family-finance.timer`), Asia/Jerusalem, **~06:00 daily** — before the 07:25 engine read, so fresh balances feed the 07:30 digest + the weekly briefing and the >35d staleness stays accurate. `TimeoutStartSec` + `MemoryMax` bound a stuck browser; reuses the M5 `xvfb-run` wrapper + provisioned Chromium (`provision.sh`). No second runtime (D-018). Cadence is the first tuning knob — if Max/Cal OTP challenges prove noisy, drop the cards to 2–3×/week and keep the bank daily. |
| **Auth model** | **The D-049 amendment.** Read-only portal logins for the three institutions live at `/etc/family-inc/bank_creds.json` (mode 600, family-inc-owned, never in the repo, never logged; optional `systemd LoadCredentialEncrypted` hardening). This **narrows** the §4/§1 "no credential storage" non-goal to permit *appliance-local, read-only financial portal logins* — distinct from the service keys already stored (D-040) — while "no money movement" stays absolute (the scrapers cannot transfer). **2FA** (Max/Cal challenge new devices): first run is interactive (operator enters the OTP once; session persisted under `/var/lib/family-inc/finance/<provider>_session/`); later re-challenges **fail loud** (§10.2), never silent. Sheet writes use the existing `Family_OS` service account (§8.6). |
| **Sheet landing zone** | Two tabs, written via `lib/sheet`, **raw — no category column** (D-033). **`Finance-Accts`** — one row per account/card: `Account` · `Type` (bank/card) · `Balance` (ILS) · `As-Of` · `Last Imported` (drives the briefing's >35d stale-import warning). **`Finance-Transactions`** (new) — one row per transaction, append-only: `Date` · `Amount` (ILS, signed) · `Description` (raw Hebrew merchant) · `Account` · `Txn-ID` (dedup key: provider id, else a stable hash of date+amount+description+account) · `Imported-At`. Retention: keep all (low volume; the monthly review + trend KPIs want history). Money values ILS only (§6). *(Name reconciliation: the as-built `Finance-Bdgt`/`Finance-Accts` vs this §6 `Finance-Budget` drift — flagged in code since 2026-06-12 — is resolved at the M6 build; schema changes additive-only.)* |
| **Delivery** | Finance lands **silently**: balances + spend surface in the weekly briefing **Money** section, the dashboard **Money** drawer, and the >35d stale-import hygiene line — **never an alert, never a budget bypass** (briefings > notifications, §3 principle 4). The only finance *message* is fail-loud (below). The kickoff "ouch > ₪500 single charge" threshold is **not** wired in this lane (an alert path + a product call that brushes the killed anomaly lane, D-033 — deferred to a deliberate PO decision). |
| **Failure handling** | An OTP re-challenge, a scraper/site-change error, or a Sheet-write failure sets the fail-flag (`OnFailure` → `logs/fail.flag`); the next delivered digest reports it ("⚠ <provider> צריך אימות מחדש" / "finance scrape failed") and the weekly briefing surfaces persistent failures + the >35d stale line — fail loud, never silent (§9, §10.2). CSVs are retained on disk on a Sheet-write failure (no data loss; retry next run). Anti-bot: clean for this mix (the 2026 Cloudflare wall is on Isracard/Amex, not ingested); if a wall ever appears the escape hatch is the maintained anti-detect fork (Camoufox) on-box, then a managed-proxy pivot (the D-040 precedent). A box compromise leaks read-only financial visibility only — no transfer capability. |
| **Unfreeze ordering** | Unfrozen D-049 on a committed monthly-review habit; acceptance of the lane = the first real monthly review. The one-time Chromium provisioning cost was already paid by M5 (§12.1) — finance reuses it. Shanee's budget migration (manual budget → `Finance-Bdgt`) is a parallel track that gives the raw actuals a target to read against. |

---

## Appendix B — paste-ready `DECISIONS.md` row (D-049)

*Drop at the top of the table (newest-first, directly above the D-048 row):*

```
| D-049 | 2026-06-17 | **Finance-ingestion lane UNFROZEN (joint — Adar + Shanee co-signed); the "no credential storage" non-goal AMENDED to permit read-only bank/card portal logins on the appliance.** Executes D-031's pre-resolved architecture (VPS systemd timer ~06:00, `israeli-bank-scrapers` Puppeteer/headless-Linux bumped 6.7.x→**6.7.3**/Node≥22.12, scrape→local CSV `/var/lib/family-inc/finance/`→`automation/finance_ingest.py`→`lib/sheet` sole writer, no Drive). Scope = Mizrahi (bank) + Max + Cal (cards), **raw uncategorized** transactions only (D-033 holds); investments/brokerage out of scope. Creds `/etc/family-inc/bank_creds.json` mode 600 (optional `systemd LoadCredentialEncrypted` hardening); **"no money movement" unchanged** — scrapers are read-only, so only "no credential storage" is narrowed (appliance-local read-only financial logins, distinct from the service keys already stored, D-040). 2FA first run interactive, re-challenges fail loud (§10.2). Browser dep reused from M5 (provision §4b); anti-bot clean for this mix (the 2026 Cloudflare wall is Isracard/Amex, not ingested) — escape hatch = anti-detect fork → managed-proxy pivot (D-040). New `Finance-Transactions` tab; the `Finance-Bdgt`/`Finance-Accts` vs §6.4 `Finance-Budget` drift resolved at build. Delivery silent (briefing Money + dashboard drawer + >35d stale-import line; never an alert). Build = **M6**; acceptance = first real monthly review. Shanee budget migration = parallel track; "ouch >₪500" alert deferred. Plan: `FINANCE_PLAN.md`. | The data finally has a committed monthly-review consumer; the amendment is narrow + defensible — a read-only login keeps "no money movement" fully intact, and service keys were always stored | `Finance ingestion` frozen-lane row (`BACKLOG.md`); D-033(a) "stays frozen"; SPEC §4 Non-goals + §1 "never stores bank credentials" (narrowed, not deleted); D-031's "lane stays frozen" + 6.7.x pin |
```
