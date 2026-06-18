# Fix Brief 2 — Systemic gaps + Minor + Disputed

## Session opener — read first (this brief is self-contained)

*Open a fresh Claude Code session in this repo and point it at this file. It carries all the context the fix needs — no prior conversation required.*

**You are opening a Family Inc fix session as Lead Architect.** `CLAUDE.md` auto-loads (roles, principles, guardrails) — read it. **The PO has authorized this fix lane as the session focus.** It sits outside the standing M6 focus in `BACKLOG.md`, but **Lane A** items below *are* M6 work; the rest is PO-sanctioned by this brief.

**Where this came from.** A full-project audit on 2026-06-18 (a 123-agent verified workflow) produced three artifacts in `reviews/`:
- `review_audit_2026-06-18_13-48.md` — the **evidence base**: every finding's claim · evidence · suggested fix · the two verifier verdicts, plus hand-verification notes on the high-stakes items. **Open it for the full detail behind any item here.**
- `fix_brief_1_blocker_major_2026-06-18.md` — the 1 blocker + 7 majors (do that brief first; some of its items are M6-critical).
- `fix_brief_2_gaps_minor_disputed_2026-06-18.md` — **this file** (10 systemic gaps + 29 minors + 6 disputed + nits).

**Current state (2026-06-18).** v1 is live & accepted (`v1-live`); M6 finance ingestion is building (repo half done, appliance step next); the M6.4 reconciliation is gated to ~2026-06-20 — **Lane A is the time-sensitive one.** **Test baseline: 341 passed, 0 failed — keep it green.**

**Read order:** `CLAUDE.md` (auto) → `BACKLOG.md` → this brief → for each item you take, the matching section of the audit report + the `SPEC`/`ENGINEERING`/`DESIGN` clause it cites.

**Run the tests** from the repo root (hermetic — an autouse fixture blanks live env, so it never touches the real Sheet / model / SMTP):
`uv run --frozen pytest -q`  (or `.venv/bin/python -m pytest -q`).

**Session protocol (CLAUDE.md):** `git pull --ff-only` before any work · constants → `automation/lib/config.py` (never in a script), utilities → `automation/lib/`, message copy → `automation/templates.py` · a directional call **folds into the canon** — edit the relevant doc to its new present-tense state + a short inline *why*; the dated rationale goes in the commit message (there is no separate decision log) · git index ops run on the **PO's machine**, never in the sandbox · end with ONE handoff terminal block.

**Review gate:** only **Lane B** (delivery seams) and **Lane S** (publish/privacy) trip the gate → run `automation/review.py` when either closes. **Lanes A/C/D/E** are below the review bar (small edits / doc cleanup) — no gate needed. See ENGINEERING §10. *(Lane A is M6 work; its close is judged at the M6.3 live verification, not a separate review.)*

---

*Work plan derived from `reviews/review_audit_2026-06-18_13-48.md`. Scope: 10 systemic gaps + 29 minors + 6 disputed (+ the 7 nits, folded into their natural lanes so nothing is orphaned). Full evidence per item is in the audit report. This is larger than one sitting — organized into 6 lanes; suggest **2–3 sessions**, Lane A first.*

> **Review-trigger note:** Lane B (delivery seams) and Lane S (publish/privacy) touch delivery/privacy guarantees → run the `review.py` gate when either closes. Lanes C/D/E are below the review bar (tiny edits / doc cleanup) — no gate needed, per ENGINEERING §10.

## Pre-flight (every session)
- `git pull --ff-only`; read `BACKLOG.md`; don't open lanes outside this brief.

## PO decisions needed (resolve before coding the affected items)
1. **OTP affordance (Lane A).** SPEC §12.2 + BACKLOG M6.2 promise an *interactive* OTP re-run that the headless-only `scrape.js` can't do. Implement an interactive path, or **scrub the promise to truth** (operator re-runs the unit/script; recommended — "interactive" overstates today).
2. **Finance scrape window (Lane A).** `scrape.js` uses a fixed 45-day lookback. Accept that (and fix SPEC §12.2 "since last success" to match), or implement since-last-success with overlap. Recommend accept + doc-fix (45d + Txn-ID dedup is simpler and correct).
3. **"Budget is biting" line (Lane E).** SPEC §8.1's auto-escalation line is unbuilt. Implement now, or defer to v1.1 and mark it so in SPEC/BACKLOG.
4. **`reply_handler.py` cluster (Lane E / Brief 1).** Its defects (openpyxl Sheet write, hardcoded `Adar`, `apply_mute` ignores `days`) are latent only while unwired. Decide: leave as a flagged v1.1 stub, or fix as prerequisites. Tied to Brief 1 / B1.

---

## Lane A — Finance hardening (M6-CRITICAL — do before the ~2026-06-20 reconciliation)
- **GAP-1 [high] Category vocab mismatch.** `seeds/14_Finance_Category_Rules.csv` emits `{Dining, Fees, Shopping, Income, …}`; `Finance-Budget` rows are `{Dining out, Subscriptions, Savings, Other, …}`. Exact-match `SUMIFS` ⇒ `Dining`→₪0, `Fees/Shopping/Income` invisible. **Fix:** align the two vocabularies (rename rule `Dining`→`Dining out`; add rows/rules for the rest) **and** add a test asserting `rules.vocabulary() ⊆ budget.categories`. Coordinate with Shanee's budget migration (the vocabulary authority). **This is the single highest-value fix in the audit.**
- **`finance-ingest#3` (minor).** `txns_seen` + run summary mislabel within-batch id-less collisions as "already on the tab" (`finance_ingest.py:189,262,276`). **Fix:** distinct counter/label for in-batch phantom-dup drops vs already-seen.
- **OTP cluster (minor ×4)** — `finance-ingest#2`, `finance-scrape-js#2` (`scrape.js:114`), `docs-canon#1` (`SPEC.md:299`), `docs-canon#2` (`BACKLOG.md:26`). One decision (#1 above), one fix: either build the path or scrub the four promises to truth.
- **`finance-scrape-js#3` (minor).** Fixed 45-day window vs SPEC "since last success" (`scrape.js:40`). Per decision #2 — fix doc or code.
- **GAP-6 [medium] Seed-backend formula reads.** `lib/sheet` seed backend uses `data_only=True` → formula cells (Reminders K/L, Finance-Budget actuals) read `None` offline, so a class of formula behavior is untestable and tests can pass against zeros. Relates to disputed `tests-quality#3`. **Fix:** document the limitation in `lib/sheet`; where a test needs computed values, compute them in-test deliberately (the current SUMIFS re-impl) **with a comment** explaining why, not as an accident.
- **`finance-ingest#4` (nit).** `seeds/README.md` omits the committed (gitignore-excepted) `14_Finance_Category_Rules.csv` and contradicts its own gitignore claim (`seeds/README.md:1-19`). **Fix:** document the committed rules CSV.
- *(Cross-ref: Brief 1 B5 gap-fill overflow + B7 deploy npm ci are also M6-critical.)*

## Lane S — Publish / privacy safety (HIGH — repo is meant public-safe by construction)
- **GAP-5 [high] `Family_OS.xlsx` binary blind spot.** Tracked, **not** in `deploy/publish_paths.txt`, and as a binary zip the `git filter-repo --replace-text` gauntlet can't scrub strings inside it. People is placeholder-scrubbed but Contacts (26)/Health (22)/Finance-Accounts rows are unverified; Settings still carries `Adar`/`Shanee` plaintext. **Fix:** audit all 18 tabs of the committed seed for real PII (phones/JIDs/health/financial values); scrub to placeholders; add the seed to the publish redaction path or a dedicated check. CLAUDE.md's "public-safe by construction" guarantee depends on it.
- **`deploy-systemd#4` (minor).** `publish.sh` redaction skips `regex:` rules (`deploy/publish.sh:42-46`) — regex-based PII redaction is never verified before the public push. **Fix:** include `regex:` rules in the gauntlet (or assert none are silently skipped).

## Lane B — Robustness seams (delivery / outbox / state) — review-triggering
- **GAP-2 [high] Stamp-after-queue, not after-deliver.** `daily_digest` stamps `Last Sent`/`Status` + clears the fail-flag right after `outbox.queue()` returns (append to JSONL), not after the bridge confirms send (`daily_digest` ~349-367). A refused/undelivered row reads "Sent" on the Sheet and the Last-Sent guard blocks re-firing → silent lost reminder. **Fix:** reconcile `whatsapp_sent.jsonl` outcome back to the Sheet stamp (stamp on delivery confirmation, or a reconcile pass), so "Sent" means delivered.
- **`outbox-budget#1` (minor).** Budget ledger is a single full-rewrite JSON with fail-open read — a torn write silently resets the day's hard cap to 0 (`outbox.py:56-73`). **Fix:** atomic write (tmp+rename) and/or durable JSONL per SPEC §7.5; fail-closed on a corrupt ledger (treat as cap-reached, log loud).
- **`outbox-budget#2` (minor).** Ledger read-modify-write has no locking — concurrent senders can each pass the 2/day check (`outbox.py:182-199`) — the exact bug the single-ledger rule exists to prevent. **Fix:** file lock around check+increment (e.g. `fcntl.flock`).
- **`outbox-budget#3` (minor).** `pop_deferred` deletes budget-deferred alerts before the digest is queued/sent (`daily_digest.py:313-355`) — a failure after the pop loses them. **Fix:** pop only after the digest send is confirmed (or re-append on failure).
- **GAP-3 [medium] Unbounded JSONL + O(n) per-poll rescan.** `whatsapp_outbox.jsonl`/`whatsapp_sent.jsonl` never rotate; the bridge re-reads the whole file every 15s and Python rebuilds the dedup index over all history per `queue()`. **Fix:** rotate/compact the sent ledger; bound the rescan window.
- **GAP-8 [medium] Multi-timer Sheet races.** finance(06:00)/reminders(07:25)/digest(07:30)/property all hit one Sheet, `gspread` batch updates aren't transactional. **Fix:** at minimum document as an accepted race; consider an ordering guard or read-after-write tolerance in the 07:30 digest.
- **GAP-10 [low] Bridge batch all-or-nothing.** One throwing `sendMessage` abandons the rest of the poll and can head-of-line-block (`baileys processOutbox`). **Fix:** per-row try/catch; record per-row failure; continue the batch.
- **`bridge-node#2` (disputed → make real).** No tests for the bridge scope guard or per-(id,target) dedup. **Fix:** add a minimal Node test (or a documented harness) proving a non-`recipients.json` target is refused and a duplicate (id,target) is dropped — this guards the §7.4 hard scope boundary.

## Lane C — Dashboard parity + the engine↔dashboard write contract
- **GAP-4 [medium] Recurrence duplication** (`lib/dates.bump_due` vs `app.js bumpDate()`) — "must not diverge" with no shared source/cross-check. **Tackle with the two disputed siblings below as one cluster:**
  - **`reminders-engine#2` (disputed).** Dashboard may write the bumped Due Date as `YYYY-MM-DD`, violating col-D `DD/MM/YYYY` (`app.js:1234`). **Verify + fix** the format.
  - **`dashboard-pwa#2` (disputed).** Dashboard writes by hard-coded column letters without validating the loaded header — the §7.1 "never written by position" guard may be absent on the write surface (`app.js:1224-1236`). **Verify**; if real, add a header check before `batchUpdate`.
  - **Fix for GAP-4 itself:** add a behavioral cross-check (a shared test vector of Done→next-due cases the Python and JS implementations must both satisfy, incl. Feb-29 clamp).
- **`dashboard-pwa#5` (minor).** The progress-arc strip (DESIGN §2/§3) is absent from the shipped Today screen (`index.html:75-93`). **Fix:** implement it, or amend DESIGN if intentionally dropped.
- **`dashboard-pwa#3` (minor).** No persistent connection/sync pill — queued writes signalled only by a transient toast (`index.html:77`). **Fix:** add the 🟢/⛔ pill (DESIGN §2).
- **`dashboard-pwa#4` (minor).** Write-failure path keeps optimistic state — no rollback, no token-expiry refresh (`app.js:1317-1323`), contrary to DESIGN §4. **Fix:** rollback on failure + silent token refresh once, then re-sign-in banner.
- **GAP-9 [low].** Dashboard finance reads depend on Sheet-computed SUMIFS columns being recomputed before the read (`app.js:679-684`) — can show stale actuals right after a write/06:00 append; compounds GAP-1. **Fix:** note the dependency; consider a recompute-tolerant read.
- **`dashboard-pwa#6` (nit).** Manifest `theme_color`/`background_color`/`description` contradict the running brand (`manifest.webmanifest:4-8`). **Fix:** align to DESIGN §2 tokens.

## Lane D — Hebcal (prerequisite for Brief 1 B2)
- **GAP-7 [medium] `hebcal_client` unexamined.** The erev-chag candle data may not be reachable through the current API surface; the 24h cache returns a `{_stub:true}` on fetch failure that callers may render as "no chag" (fail-quiet suppressing a real holiday). **Fix:** confirm the holiday/candles endpoint supplies erev-chag times; make the stub distinguishable from a genuine no-chag; add a test. **Do this before/with Brief 1 B2.**

## Lane E — Docs/canon cleanup + small correctness + test gaps (low-risk, batchable)
**Canon hygiene**
- **`docs-canon#5` (minor).** `FINANCE_PLAN.md` is superseded by SPEC §12.2 and self-contradictory (`FINANCE_PLAN.md:5-15`) → move to `Archive/`.
- **`docs-canon#6` (minor) + finance seed header.** Leftover `D-NN` refs survive the log retirement — `deploy/FINANCE.md:49` and the `seeds/14_…csv` header (`M6.4; D-050`). **Finish the sweep** across live canon + committed files.
- **`docs-canon#4` (nit).** `deploy/FINANCE.md` is orphaned — referenced by no canon doc. **Fix:** link it from ENGINEERING/BACKLOG or move under `Setup/`.
- **`principles-boundaries#1` (minor).** ENGINEERING §1 claims "CI greps enforce the first" boundary rule — no such CI exists (`ENGINEERING.md:57`). **Fix:** add a real `tests/test_boundaries.py` (AST/grep over `automation/`) **or** soften the wording to "convention, reviewer-checked." (Adding the test is the higher-value option — it makes the other four boundary rules real too.)
- **`principles-boundaries#2` (minor).** "Only `bridge/` and `finance/` touch a third-party site" is contradicted by `property_scrape.py`, `lib/apify.py`, `hebcal_client.py` (`ENGINEERING.md:57`). **Fix:** restate the real invariant ("each third-party touch is the sole, named function in its module").
- **`deploy-systemd#3` (minor).** `deploy/README.md:52` says "5 timers"; provision enables 7. **Fix:** correct to 7.
- **`deploy-systemd#2` (minor).** `family-finance.timer` comment + SPEC §12.2 claim 06:00 feeds the digest/engine, but no code consumes finance there yet (it's M6.3). **Fix:** soften the comment to "feeds M6.3 consumers (pending)."
- **`digest-briefing#5` (nit).** BACKLOG says the weekly briefing carries "Hebcal lines" — the code has none (`BACKLOG.md:13`). **Fix:** correct BACKLOG (or add the line if intended).
- **`summarizer#3` (nit).** Module docstring names "Haiku" as the active model instead of DeepSeek (`whatsapp_summarizer.py:12`). **Fix:** one-word doc edit.
- **`reminders-engine#1` (minor).** SPEC §8.4 documents an outbox id `rem-{row}-{date}` the code never emits (`SPEC.md:227`). **Fix:** decide direction — emit the documented id, or correct SPEC to the real id format.

**Small correctness**
- **`digest-briefing#3` (minor).** Lead-time fires >30 days (the SPEC's 60/30 chain) render a bare `•` instead of a semantic flag emoji (`daily_digest.py:81`). **Fix:** add a 🟢/appropriate flag tier for >30d, or define the >30d emoji in DESIGN §6.
- **`summarizer#4` (minor).** `derive_rule` can mislabel a critical-keyword ALERT as a raw reason string instead of `RULE_CRITICAL` (`accuracy_review.py:128-138`). **Fix:** map critical matches to the canonical rule label so the accuracy tally is correct.
- **`property-apify#1` (minor).** SPEC §12.1 claims cards carry `posted-at`, but the scraper never extracts it (`property_scrape.py:94-104`). **Fix:** extract it, or drop it from SPEC §12.1.
- **`property-apify#2` (minor).** `detect_block` uses over-broad substrings (`_px`, `captcha`) that can false-positive on a legit results page and discard it (`property_scrape.py:71-79`). **Fix:** tighten to anchored/structural anti-bot signals.
- **`digest-briefing#4` / `tests-quality#2` (minor).** SPEC §8.1 "budget is biting" line — unimplemented + untested (`weekly_briefing.py:297-326`). Per decision #3 — implement+test, or defer to v1.1 and mark it.
- **`principles-boundaries#4` / `#5` (minor).** `reply_handler.apply_done` hardcodes `Adar` as `LastDoneBy` (breaks partner-symmetry + name-constant-in-script); `apply_mute` ignores its `days` argument (`reply_handler.py:137,163-167`). Per decision #4 — fix or flag as v1.1 stub.

**Test gaps**
- **`tests-quality#1` (minor).** `apply_budget` can drop an OVERDUE fire when must-keep overflows — SPEC §8.1 "OVERDUE always survive" is untested in the overflow case (`reminders_engine.py:144-155`). **Fix:** add the overflow test (and fix the code if it really drops OVERDUE).
- **`reminders-engine#3` (nit).** Overdue cooldown `≥3d` has no test at exactly 3 days (`test_engine.py:54-71`). **Fix:** add the boundary case.

**Disputed — quick adjudication**
- **`finance-scrape-js#1`.** `israeli-bank-scrapers@6.7.3` may need Node ≥22.13 vs the ≥22.12 pin (`package.json:11`). **Verify against the lib's `engines`; bump the pin + SPEC §12.2 if real** (cheap, do in Lane A).
- **`principles-boundaries#3`.** `reply_handler.py` writes the Sheet via `openpyxl`, bypassing `lib/sheet` (`:49,210,290`). Latent while unwired → fix as a v1.1 prerequisite (decision #4); flag now.
- **`tests-quality#3`.** The budget-reconciliation test re-implements the SUMIFS in Python (`test_finance.py:389-406`) — acceptable given GAP-6 (offline formulas read `None`), but **add a comment** saying so, and rely on the M6.3 live verification for the real formula.

---

## Suggested sequencing
1. **Lane A + Lane S** first — M6 correctness and public-repo safety, both time-sensitive.
2. **Lane B** next (review-triggering; the stamp-ordering gap is a real silent-loss path).
3. **Lane D** with Brief 1 B2 (hebcal).
4. **Lane C** and **Lane E** as a final polish session (mostly below the review bar; batch the canon edits + nits together).

## Definition of done (ENGINEERING §11)
Per item: tests for its logic green · constants in `config.py` (not scripts) · errors degrade or surface · canon (`SPEC`/`ENGINEERING`/`DESIGN`/`BACKLOG`) updated where a contract moved · `BACKLOG.md` status flipped · `review.py` gate run when Lane B or S closes.
