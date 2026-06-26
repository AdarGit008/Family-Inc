# Family Inc. — Roadmap & forward lane contracts

*Spec **ahead** of build. This is the one place the next things are sequenced and contracted before they are written — the deliberate counterweight to a build that runs ahead of its spec. v1.0 · 2026-06-20.*

*Companions: `SPEC.md` (what the system **is**, present tense) · `BACKLOG.md` (status: shipped / in-flight / gated / frozen) · `ENGINEERING.md` · `DESIGN.md`. **Status lives only in `BACKLOG.md`** — this doc holds the **plan** (the sequence) and the **forward contracts** (what each lane must do before it is built). When a lane ships, its contract graduates into `SPEC.md` and its status into `BACKLOG.md`; the entry here is then struck.*

*Generated from the 2026-06-20 audit + roadmap pass (50 verified drift findings → reconciliation; a value/risk/dependency judge panel → this sequence; per-lane spec-ahead drafts → the contracts below). The four PO calls of 2026-06-20 are baked in: GAP-7 → **fix (fail loud)** · reviewer default → **code flipped to DeepSeek** · the three phantom DESIGN components → **removed** · spec-ahead → **this doc**.*

---

## 1. The next lane (recommended)

> ✅ **Shipped 2026-06-23** — `.github/workflows/tests.yml` (pytest gate + `lib/pii.py` repo-wide leak guard + `config.js` smoke), **421 green**, merged to `main` (`9bf50cb`). The first Actions run was red — `astral-sh/setup-uv@v8` is unresolvable (no floating major past v7) — pinned `@v7` (`5168c6d`); see `BACKLOG.md`. **Two deviations from the sketch below, by design:** the leak guard is a **pytest, not a grep step** (single-sources its patterns with `test_seed_safety.py` + rides `deploy.sh`), and the job runs on the **whole tree with no path filter** (a path-filtered run would let a PII paste in docs/config bypass the guard). **The now-next lane is GAP-7** (§2 rank 2). The original rationale is kept below for the record.

**A pre-merge CI gate — and bundle two cheaper, higher-irreversibility wins into the same job.**

The hermetic 390-test suite (~2.6s) runs today **only** inside `deploy/deploy.sh` on the appliance. Nothing runs it on push/PR, so a red commit can sit on `main` and silently keep the box from reaching HEAD during the mandated 30-day boring hold. The gate is the meta-protection that makes every later fix in §3 safe to land — and it needs no live data, has zero guardrail surface, and fits the light 06-20→06-26 window.

Bundle (the audit critic's additions — same S-effort window, both currently un-automated):
1. **pytest job** — GitHub Actions, `uv run --frozen pytest -q` on push + PR to `main`, path-filtered to `automation/**` + `tests/**`. Mirror `.github/workflows/pages.yml`'s shape.
2. **Secret/PII-leak guard** — the "public-portfolio-safe by construction" guardrail (`CLAUDE.md`) has **zero** automation today; one slip is irreversible in git history. A grep step that fails on phone patterns, `@s.whatsapp.net` JIDs, or ILS-amount-shaped values in tracked files. Pairs with the existing `tests/test_seed_safety.py`.
3. **Dashboard `config.js` smoke** — `pages.yml` generates `config.js` from Actions secrets and is the real deploy path for the most-frequently-shipped artifact, yet has no pre-merge validation. A JS syntax/lint + "`config.example.js` still applies" check in the same job.

**First steps:** branch `ci/test-gate` → add `.github/workflows/tests.yml` (pytest + leak-grep + config-smoke) → confirm green locally (390/390) → PR → watch Actions go green. No `deploy.sh` change, no box contact. Then take **GAP-7** immediately after (rank 2), in the same window.

---

## 2. The sequence

Ranked by *fits-the-window-and-clears-blockers*, then value-per-effort. The window **now → ~06-26** is light (finance acceptance is gated on ≥1 week of live data + Shanee's budget-vocab migration), so it is a reconciliation/hardening slot, not a build-features slot. v1 holds boring/stable until ~07-13 (30 days from `v1-live`).

| # | Lane | Value | Effort | Risk | Window |
|---|---|---|---|---|---|
| 1 | **CI gate + PII-leak guard + config smoke** — ✅ shipped 06-23 (merged) | high | S | low | ✅ done |
| 2 | **GAP-7 Hebcal fail-loud** (decided: fix) | high | S | low | now → 06-26 |
| 3 | **Reviewer/provider canon** (done this session; verify) | med | S | low | now → 06-26 |
| 4 | **DESIGN reconcile** (done this session: 3 components removed) | high | S | low | now → 06-26 |
| 5 | **Lane C dashboard write-contract** (col-D format + header guard) — ✅ shipped 06-26 | high | M | med | ✅ done |
| 6 | **uptime-ping** (healthchecks.io dead-man) | high | S | low | now → 06-26 |
| 7 | **Box-side verification** of the live claims — ✅ done 06-23 (VPS hour) | high | S | low | ✅ done |
| 8 | **stale-digest → briefing system-health line** | med | S | low | now → 06-26 |
| 9 | **Lane B: JSONL rotation** (GAP-3) | med | M | low | now → 06-26 |
| 10 | **Lane E correctness remainders** (batch under the new gate) | med | M | low | now → 06-26 |
| 11 | **M6.3/M6.4 acceptance** (classifier-accuracy run + vocab migration + external review) | high | M | low | after 06-26 |
| 12 | **classifier-fp-metric** (human-mark channel) | med | M | low | after 06-26 |
| 13 | **Bridge scope-guard harness** (bridge-node#2) — *hard prereq to reply-parsing* | med | M | low | after 06-26 |
| 14 | **reply-parsing** (done/snooze via WhatsApp) | high | L | med | later v1.1 (post-hold) |
| 15 | **inbox-trigger** (inotify, sub-hour critical latency) | med | M | med | later v1.1 (post-hold) |
| 16 | **apify-cap** (≤₪120/mo result-counter) | low | M | low | later v1.1 |
| 17 | **calendar-connectors** (decomposed; Hebrew-string pass pullable early) | high | XL | high | later v1.1 (majors) |
| 18 | **v3-today-redesign** (decided 06-25; §3.8) — Today-surface UI rebuild | high | L | med | v1.1 — window is a PO call (now vs post-hold) |
| — | **big-charge-alert** (>₪500) | med | S | med | **frozen** — joint PO call |
| — | **ai-briefing** (LLM five-scene) | med | L | high | **frozen** — joint Shanee privacy call |
| — | **GCal/iCloud auto-ingest** | high | XL | high | **frozen** — credential-storage amendment |

**Where the lenses disagreed (resolved):** value-first opened on GAP-7 (cheapest family-felt fix); risk + dependency opened on the CI gate. Resolved **gate-first, GAP-7 immediately after** — same window, and GAP-7 ships *with* a regression test the new gate then enforces. Reply-parsing: value-first ranked it higher; risk/dependency pushed it past the bridge harness because it mutates two guardrail-sensitive seams (the budget chokepoint + the Sheet write path) — risk/dependency won.

---

## 3. Forward lane contracts

*Near-future tense. Each lane states its scope, behaviour contract, data touchpoints (additive-only), policy interactions, acceptance bar, dependencies, and the PO calls it still owes. Guardrails that must hold for every lane: no money movement · the outbox (`lib/outbox.py`) is the sole alert path · alert budget 2/day (criticals bypass, briefings exempt) · additive-only schema · no PII in committed files · two-adults-only · partner-symmetric, no scoring · no kid UI · boring tech.*

### 3.0 v1-hardening (lanes 1–10) — the pre-v1.1 stabilization bundle

The now→06-26 work. Each item is small, low-risk, needs no new live data, and either protects the dev loop or fixes a live correctness/honesty gap.

- **CI gate + leak guard + config smoke (lane 1)** — ✅ **built 2026-06-22** (status in `BACKLOG.md`; lands on push). `.github/workflows/tests.yml` runs the hermetic suite on push/PR to `main`. Acceptance met locally (421 green): a red commit can't merge; the PII guard (`tests/test_repo_pii_guard.py` + `lib/pii.py`) fails on a planted phone/JID/amount; the `config.js` smoke fails on a drifted template. **Two deviations from the §1 sketch, by design:** the leak guard is a **pytest, not a grep step** (single-sources its patterns with the seed guard + rides `deploy.sh` on the box), and the job runs on the **whole tree with no path filter** (a path-filtered run would let a PII paste outside `automation/**` bypass the guard). *PO call resolved: gate added.* **Shipped 2026-06-23** — first Actions run red (`setup-uv@v8` unresolvable → pinned `@v7`, `5168c6d`), then merged (`9bf50cb`); contract closed.
- **GAP-7 Hebcal fail-loud (lane 2)** — **decided fix.** `hebcal_client` returns `{_stub:true}` on fetch failure; today `daily_digest._hebcal_line` (and the Shabbat `shabbat_times` path — the higher-stakes weekly one) render that as **silence**, indistinguishable from a genuine no-chag day. Contract: on `_stub`, surface a short Hebrew "candle times unavailable" line (copy = Shanee) instead of silence, per the §3.6 clarification landed this session (time-critical data fails loud). Ships with a regression test. Policy: rides the budget-exempt `kind=briefing` digest, no new alert path. *Open: exact Hebrew string (Shanee); confirm both the Friday Shabbat and the erev-chag paths get the line.*
- **Reviewer/provider canon (lane 3)** — **done this session:** `review.py --provider` default flipped to `deepseek` so code matches the "DeepSeek default" canon; ollama stays the keyless local fallback via `--provider ollama`. Consequence: a bare `review.py` now needs `DEEPSEEK_API_KEY` (always present when the operator runs a gate). The runtime classifier + summarizer already run on DeepSeek — the canon is now consistent across all three. Verify before the 06-26 milestone gate fires.
- **DESIGN reconcile (lane 4)** — **done this session:** the progress arc, connection pill, and skeleton/shimmer loading — documented but never built — are **removed** from `DESIGN.md` (components, IA, states, acceptance, smoke checklist). The real stale-data badge + the single-signal Today status pill are now documented as-built. No code change; the dashboard never had these.
- **Lane C dashboard write-contract (lane 5)** — ✅ **shipped 2026-06-26 → graduated to SPEC §6.1/§7.6/§8.5.** PO call (2026-06-26): keep col D a real Sheets **date** cell (human-friendly DD/MM entry + the col-K/L Days-Until formulas keep working) and make the **read** robust rather than forcing ISO-text storage — the 06-25 "ISO everywhere" headline was re-confirmed once tracing showed `USER_ENTERED` coerces an ISO write back into the locale render anyway. Delivered: (a) both write surfaces now emit the **ISO literal** (the engine's `encode_value` joined the dashboard — Sheets parses ISO locale-unambiguously, where DD/MM would misparse under any other locale); (b) the dashboard's `parseDate` reads ISO + the he-IL DD/MM·DD.MM render (the machine M/N/O ISO-T *stamps* untouched — only col D was the bug); (c) the JS write surface resolves columns by **header name** and **pauses writes on header drift**, mirroring the engine's §7.1 guard. Acceptance: the parseDate round-trip cases + airplane-mode reverify (DESIGN §9 item 4 / new item 15). **Unblocks V3.3** (absolute snooze now round-trips: a future col-D clears OVERDUE).
- **uptime-ping (lane 6)** — see §3.5.
- **Box-side verification (lane 7)** — a one-time PO read confirming the asserted-live-but-unverifiable-from-repo facts before the 06-26 gate treats them as settled: `git` SHA of the box vs origin HEAD; `journalctl -u family-finance.service` for the 98-row ingest + dedup counters; the live `Finance-Budget` tab (J1 header, SUMIFS machine cells, non-zero actuals); `gh run list --workflow=pages.yml` green. **Output is a confirmation, not a commit.** Pairs with a standing follow-on: have the box log its git SHA into a line the weekly briefing surfaces, so "committed ≠ deployed" becomes invisibly checkable. **✅ Done 2026-06-23 (the VPS hour):** a 36-check read-only sweep found the system healthy and caught + fixed a 3-day-stale box (deployed to HEAD `9bf50cb`), a down finance scrape (lib bumped 6.7.3→6.7.8), and a ~77%-blank categorization gap (→ M6.4); findings in `BACKLOG.md`. The "box logs its git SHA into the weekly briefing" follow-on remains open.
- **stale-digest → briefing line (lane 8)** — see §3.4.
- **Lane B JSONL rotation (lane 9)** — append-only logs (`inbox/replies/whatsapp_sent/digest_pending.jsonl`) grow unbounded; reconcile + the classifier scan them every run. Contract: size/age rotation that **preserves the <48h reconcile horizon** (§7.5). Additive, hermetic. *Open: retain how many rotated files; rotate on size or age (Adar ops call).*
- **Lane E correctness remainders (lane 10)** — bounded batch under the new gate so the new tests are load-bearing: digest >30d flag, `derive_rule`, the OVERDUE cooldown boundary test (exactly 3 days — Brief 2 reminders-engine#3, currently untested), `reply_handler` stub flags, the property-apify test. Also fold in **Brief 2 reminders-engine#1** (now closed by the SPEC §8.4 reconciliation — no `rem-` id is emitted).

### 3.1 reply-parsing — done/snooze via WhatsApp

- **Scope.** Adult 1:1 WhatsApp replies (`done` / `+Nd` / `mute` / `?`) act on the `Reminders` tab. *Not:* free-text NLU, group replies, or any sender beyond the two adult JIDs.
- **Contract.** The bridge already logs 1:1 replies (no ack — B1) to `replies.jsonl`. Consume them: port `reply_handler.py`'s writes from `openpyxl` to the header-validated `lib/sheet` (never the parked openpyxl path); fix LID-addressing (`msg.key.remoteJidAlt`) so adult replies aren't dropped; reinstate the single reply-footer line; act only on rows present in the most recent digest snapshot for that recipient (anything else → "reply ? for the current list").
- **Data.** `Reminders` writes obey the §6.1 tombstone write contract, sender-attributed.
- **Policy — the central design point.** A solicited ack must **not** consume the unsolicited 2/day budget. The parked code defaults acks to `kind="alert"`, which the outbox **suppresses** under the cap — so a user's own confirmed action could silently vanish on a busy day. **Required:** a new outbox `kind="ack"` — budget-exempt and quiet-hours-exempt (the user just messaged; an immediate confirmation isn't an interruption). This is a §7.5 contract change → milestone review.
- **Acceptance.** A `done` reply marks the row done + recurrence-bumps; an ack returns within seconds, off-budget, only to the replier; an unknown JID is still dropped; the bridge scope-guard harness (lane 13) is green first.
- **Dependencies.** Hard-blocked behind lane 13 (bridge scope-guard harness) — reply-parsing expands the inbound 1:1 surface. Post the 30-day hold.
- **Open PO calls.** `kind="ack"` confirmed? · ack visible to both adults or only the replier (lean: replier; shared completion shows in dashboard/briefing)? · does `mute` truly suppress firing for N days (needs an engine mechanism) or is it just a label?

### 3.2 ai-briefing — LLM five-scene narrative (FROZEN until a privacy call)

- **Scope.** An LLM-written five-scene opener (the week's spend · a kids' moment · next week's three things · a goal line · a contract heads-up) layered over the existing deterministic 8-section template, which stays the **verbatim fallback**.
- **Contract.** Openers-only (recommended); the deterministic template renders first and is always the fallback if the LLM is down or the privacy gate is unmet.
- **Policy — the gate.** This is the **single largest guardrail surface in the pool**: it sends whole-Sheet context (incl. finance, kids' health) to the configured provider — strictly broader than today's §8.6 "description+amount only" finance gap-fill. Requires a **joint Shanee privacy call** *and* a content-review gate (which fields are redacted before send). Provider canon (lane 3) is a hard prerequisite — sending finance to an ambiguous provider is the failure mode. Stays `kind=briefing`; no new alert path.
- **Acceptance.** A real week reviewed before go-live; the deterministic fallback proven; privacy + content-review signed off.
- **Open PO calls.** Facts-only bounded summary acceptable to Shanee? · kids'-moment source (kid-keyword rows vs an additive kid-tag column)? · voice/personality? · re-run determinism (accept wording drift vs pin a seed)?

### 3.3 inbox-trigger — inotify sub-hour critical latency

- **Scope.** An inotify watcher on `inbox.jsonl` invokes the existing summarizer within seconds of a new group message, so critical-safety keywords fire sub-hour — **without** touching the hourly digest cadence or adding a second classifier path.
- **Contract.** `--critical-only` mode: classify the new line; on `kind=critical`, dispatch via the existing `dispatch_alert → queue()` path; write **zero** Sheet rows (the hourly run stays the single writer of record). Debounce ~10–15s to coalesce bursts.
- **Policy.** The outbox stays the sole alert path; only `kind=critical` travels this path and criticals already bypass the budget by spec — no `alert` slot spent, no new bypass.
- **Acceptance.** A planted critical fires within the debounce+poll window; a non-critical does nothing until the hourly run; no duplicate Sheet rows.
- **Dependencies.** A new always-on watcher = a new silent-failure surface → pair with the dead-man ping (§3.5) + JSONL rotation. Defer past the 30-day hold.
- **Open PO calls.** Debounce window? · critical-only scope (recommend yes) vs also the digest-only "⚠ NEEDS A LOOK" block?

### 3.4 classifier-fp-metric + stale-digest line — measured quality & visible degradation

- **classifier-fp-metric.** One **additive** `Review` column on `WhatsApp_Inbox`, marked from the dashboard, turning the weekly accuracy pass from a by-eye read into a measured ALERT-tier FP rate against the <1/week bar. No alert path (the only consumer is the budget-exempt weekly briefing). Best **after** the first 06-26 accuracy run gives a baseline. *Open: FP-only mark vs full reviewed-coverage; where the mark lives (inline vs a weekly review screen); does the number ever auto-narrow patterns (recommend: stays a human edit, §7.3).*
- **stale-digest → briefing line (lane 8).** GAP-2 already drops a digest unconfirmed past 48h and re-fires its reminders (safe), but the drop is only a log line — a persistently-failing bridge is invisible to the adults. Extend the weekly briefing's existing system-health/self-report section with the stale-drop count (budget-exempt, additive, no new alert path). The rejected "stamp-anyway" tier stays rejected (it would reintroduce silent loss). *Open: copy/tone (Shanee); threshold ≥1 vs ≥2; confirm `stale-dropped` replaces the reconcile `queued-stale` line to avoid double-counting.*

### 3.5 uptime-ping — external dead-man

- **Scope.** A healthchecks.io dead-man's switch that pages the **operator** out-of-band when the whole VPS goes dark — closing the one failure §9 still calls silent (a dead box pages no one, because the email fallback assumes the box is alive, and the design deliberately makes silence read as a calm day).
- **Contract.** The 07:30 digest run pings a healthchecks.io URL on success; a missed ping past a grace window pages the operator. Optionally a finer ~30–60min bridge-liveness ping as an additive follow-on.
- **Policy — the one named tension.** The "outbox is the sole alert path" guardrail governs **household** alerts to the two adults; this is an **operator** page emitted off-box by healthchecks.io. It does not route a family message outside the outbox — the guardrail's intent holds.
- **Acceptance.** Killing the box's networking pages the operator within grace; a normal day never pages.
- **Open PO calls.** Which checks ship in v1.1 (digest-daily first)? · grace window? · should a *recovered* briefing also carry an in-band "system was down N hours" line (a separate small lane)?

### 3.6 apify-cap — monthly cost backstop

- **Scope.** A durable monthly result-counter that hard-stops the Apify property secondary before billed results cross the §11 ≤₪120/mo ceiling — converting today's structurally-implied bound (per-search/per-day + item caps) into an enforced one, with the month's burn in the weekly briefing.
- **Contract.** Persist `{month, count}` (or projected-₪ at a conservative per-result rate); at the cap, hard-stop to primary-only for the rest of the month (degrade-quiet) + a budget-exempt briefing line. No alert.
- **Policy.** No new credentialed surface (an integer + a config rate, not an invoice read); outbox untouched.
- **Open PO calls.** Per-result ₪ rate to encode? · enforce on projected-₪ or raw count? · accept that a capped month may miss blocked-portal listings until rollover?

### 3.7 finance-cards-unfreeze — Cal **shipped 2026-06-23**; remaining cards follow the same path

**✅ Graduated into SPEC §12.2 / BACKLOG M6.5.** Cal (Visa) is live — the `--auth` device-trust path (built-but-dormant since 06-19) was exercised: a one-time headed login under xvfb + x11vnc over an SSH tunnel, then daily **headless** (first import 103 txns, ~90% categorized). The "config-only activation" held — a `bank_creds.json` `cal` block + the `--auth cal` login, no code change — **except** one addition the spec-ahead missed: a **`Card Settlement`** exclusion rule, because Cal is *immediate-debit* (its spend also lands merchant-less on the Mizrahi statement, so the mirror must be excluded or the spend double-counts). **Remaining cards** follow this now-proven path, but the `--auth` step is **only for a card on a new portal**: a card on an already-connected login rides the existing scrape, mirror-token-only. **Shanee's debit card (worked 2026-06-23) is the no-auth case** — a Cal-cleared immediate-debit card on the connected Cal login, so its only change was the `רכישה בכרטיס דביט` `Card Settlement` mirror token + flipping the morning's over-match guard (which had assumed it needed its own auth). The other Visa-debit lines (`ויזה-דביט`) still need each source confirmed before a mirror.

- **Open PO calls (carried to M6.5).** Per-card `Owner` default? · daily vs 2–3×/week cadence (re-challenge noise)? · does a card change the >35d stale-import expectation (a card may legitimately have no charges for a month)?

### 3.8 v3-today-redesign — rebuild the dashboard Today surface

**Decided 2026-06-25.** A visual + interaction evolution of the **Today** surface, from a hi-fi prototype handoff put through an 8-dimension adversarial design review; 8 calls co-signed (Adar + Shanee). Full decision record + design tokens in `V3_RECONCILE.md`; the **file-level build plan + 4 hard blockers + open PO calls in `V3_BUILD_PLAN.md`** (synthesized from a 13-agent planning pass, 2026-06-25); full pixel spec in the handoff (`~/Downloads/Family Inc Repo Redesign.zip`, **currently missing from the box** — V3.4–V3.6 geometry builds to the written contract until it's restored). Same data philosophy (calm tech, Today-first, Hebrew/RTL); new layout + two net-new components.

- **Scope.** The Today home surface only. A **system-wide cool retone** (tokens live on `:root`, so Sunday/Settings inherit colors but keep their layouts) + IBM Plex Mono for all numerals. New/changed components: a 3-tier status pill (red/amber/sage **+ count**), a parent-to-parent **love-note**, a 3-day scroll-snap **calendar**, a select-to-act **desk**, a **coming-up** strip (WEEK-OUT/MONTH-OUT), a cross-domain **timeline** (exponential 1wk→5yr zoom + category filter), and one data-driven **bottom-sheet** drawer replacing the inline accordions. *Not:* the WhatsApp surface; Sunday's or Settings' layouts.
- **Contract — the 8 calls (D1–D8).** D1 a coming-up strip homes the WEEK-OUT tier (replaces v1 "Next 7 days"). D2 love-notes (Data). D3 account-switch = real Google re-auth, never a label flip. D4 snooze writes an **absolute** Due date. D5 the pill keeps a **red** OVERDUE tier + count. D6 the Car drawer stays. D7 drop the prototype's notif-toggles / bank-connect / export from Settings. D8 goal **tile** = progress bar, **drawer** keeps the bright-line viz; retone system-wide; mono widened to all numerals.
- **Data touchpoints (additive-only).** (a) **Love-notes — appliance-local, not the Sheet:** one ephemeral note per direction (text|voice), 24h-or-on-replace expiry, over a small authenticated dashboard→appliance endpoint — the **first dashboard datum that is neither the Sheet nor the outbox**. The voice memo is the **bounded unfreeze** of the §4 voice-capture frozen lane (≤24h, appliance-local, the one stored-media exception). (b) **Snooze → col D as an absolute date** — settle the col-D format in Lane C (§2 rank 5) first so the engine round-trips it; an absolute future date clears OVERDUE cleanly (which +N could not on an already-overdue row). (c) **Timeline** needs a milestone-inclusion rule + a Domain→{finance,health,car,edu} map; no new tab.
- **Policy.** Love-notes have **no push** → no alert-budget spend, no new channel to phones (the note shows on the recipient's next open); the outbox stays the sole alert path. Two-adults-only, parents-only (no kid UI), partner-symmetric (each sends/receives). Switch-account keeps `LastDoneBy` truthful via the live OAuth session (both adults are editors on the one sheet + UserMap entries).
- **Acceptance.** Each slice ships tests-green and its DESIGN/SPEC sections **graduate to present-tense** as it lands. The DESIGN §9 smoke passes on the rebuilt Today; AA holds on both surfaces (the prototype's amber pill + muted text failed → the darkened `--amber #8A5E12` / `--muted #5F6878` are the fixes); RTL + EN-fallback intact (every new chrome string in `STRINGS` he+en); love-note round-trips with the 24h sweep; an overdue row snoozed to a future date leaves OVERDUE.
- **Build sequence.** V3.1 token retone (`styles.css` + font link; reconcile names with the existing `--border`/`--font-mono`) → V3.2 scaffold + 3-tier pill → V3.3 desk + coming-up + absolute snooze (via `applyWrites`/tombstone) → V3.4 calendar → V3.5 portfolios + bottom-sheet (Money hero, Health avatars w/ **non-color** urgency, Goals bar+bright-line, Car, Contracts) → V3.6 timeline → V3.7 love-notes (appliance endpoint + UI; **text first, voice second**) → V3.8 i18n + a11y + Settings (add switch-account; drop the 3 cut controls) → V3.9 milestone review (`review.py`) + close.
- **Dependencies.** Lane C (§2 rank 5) first (settles col-D). The love-note endpoint is the one appliance-side (server) piece. A full UI rebuild is **L–XL** — see the window call below.
- **PO calls — the 4 build blockers RESOLVED 2026-06-25** (detail + consequences in `V3_BUILD_PLAN.md` §0): **window → build the whole lane now** (V3.3+ still waits on Lane C as a real dependency, not a window choice); **col-D format → ISO `YYYY-MM-DD`** everywhere (`parseDate` stays as-is; both write surfaces stay ISO via Lane C's helper); **days 3–7 calendar gap → the coming-up strip carries calendar events** (3–7d, 📆-tagged); **love-note exposure → Cloudflare Tunnel** (+ a 4th `pages.yml` sed / `DASHBOARD_LOVENOTE_URL` secret / 4th config-smoke anchor). **Resolved since (folded into SPEC):** Timeline milestone-inclusion rule + Domain→category map + **Education's only Today home = Timeline** (V3.6, SPEC §7.6); **love-note on-box storage → flat JSON per direction**, **auth → access_token→Google-tokeninfo** (opt-in audience check), **`LOVENOTE_URL` sed-substituted** (4th `pages.yml` sed + smoke anchor) — V3.7 **text** phase landed 2026-06-25 (SPEC §7.7). **Still open (per-slice):** `--blue` token fate · JS-test-harness now vs deferred · **love-note voice phase** (the SPEC §4/§7.7 stored-media carve-out — not built) · does account-switch need UI beyond reusing the sign-in flow (V3.8).

---

## 4. Decisions & open questions carried forward

**Landed this session (2026-06-20):**
- GAP-7 → **fix, fail loud** (§3.6 clarified: time-critical data surfaces an "unavailable" line, never silence). Implementation is lane 2.
- Reviewer/provider canon → **code flipped to DeepSeek default** (`review.py`); ollama is the keyless fallback.
- The three phantom DESIGN components → **removed from the project**.
- Spec-ahead lives here in **ROADMAP.md** (5th canon doc).
- ~30 doc-vs-code drift reconciliations across SPEC/ENGINEERING/DESIGN/README + code one-liners (see git history / `BACKLOG.md`).

**Landed 2026-06-25:**
- **v3 Today redesign decided** — 8 design calls co-signed (Adar + Shanee) after an 8-dimension adversarial review of a hi-fi prototype handoff. Captured as forward lane §3.8 + `V3_RECONCILE.md` (decision record + design tokens). Build not started; **window is an open PO call** (now vs after the boring-hold ~07-13). The first canon fold was mistakenly written against a stale base and discarded (the redesign reviewed while origin raced ahead with M6.5); this is the clean placement.

**Open PO calls before / at the 06-26 gate:**
- **Define the classifier-accuracy PASS THRESHOLD** (e.g. ALERT-tier FP < 1/week = accept; ≥ that = narrow patterns and re-run) *before* 06-26, so the milestone close isn't a judgment call on ambiguous ground.
- **Box-side verification** (lane 7) run before the gate treats the live claims as settled.
- Add the CI gate, or document a deliberate no-CI choice.

**Standing principle reaffirmed:** anomaly/subscription detection stays **killed**; `big-charge-alert` is its only bounded re-entry and needs a **joint** PO call + a recurring-payee exclusion (which itself depends on Shanee's budget-vocab migration) + the live finance baseline — it does **not** auto-ride card activation.
