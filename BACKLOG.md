# Backlog

*The only live status record. What's shipped, what's in flight, what's parked, what's frozen.*
*Legend: ✅ done · 🔵 in progress · ⬜ todo · 🧊 frozen. Scope and acceptance live in `SPEC.md`. The dated history of how each item landed lives in `Archive/`.*

## Now

**v1 is live and accepted** (since 2026-06-13, tagged `v1-live`): the morning WhatsApp digest, the weekly briefing, the dashboard write-back loop, and the group summarizer all run unattended on the appliance. The **property tracker** is live (Yad2 on-box + Madlan via Apify). The summarizer runs on **DeepSeek**. **Finance ingestion (M6)** is the current build — the repo half is done; the appliance step is next. Two summarizer-review items are **gated** until ~2026-06-20 (they need a week of live classifier output to judge).

## Shipped

- **Keystone loop** — reminders engine (07:25) → daily digest (07:30) → WhatsApp, with dashboard write-back, the outbox budget chokepoint, quiet hours, and the offline-write tombstone guard.
- **Weekly briefing** (Sat 21:00) — deterministic template, Hebcal lines, the system self-report, and a classifier-accuracy section.
- **WhatsApp summarizer** — 5 hard rules + DeepSeek (with keyless keyword fallback), per-group routing, critical-keyword bypass.
- **Daily digest is partner-symmetric** — both adults briefed every day; the empty-handed adult gets the quiet-day line + shared sections, budget-free.
- **Property tracker** — saved-search scrape (headed Chromium under Xvfb) + Apify secondary (backup + gap-fill, primary always wins), silent `Property-Listings` landing + morning digest section.
- **Delivery hardening** — email (SMTP) fallback when the bridge is silent >24h, fail-flag → next-digest reporting, transport logging; email days count as degraded, not green.
- **Go-live + publication** — VPS provisioned, Baileys paired (7.x/ESM), GitHub Pages + PWA pinned to both phones, repo history rewritten clean and made public.
- **Classifier-accuracy surface** — `accuracy_review.py` re-derives each ALERT's rule from persisted Inbox fields (no schema change); a compact pulse folds into the weekly briefing.

## In progress — M6 finance ingestion

Banks + cards, categorized + trends, delivered silently. Read-only logins permitted on the appliance; "no money movement" unchanged. Full contract: `SPEC.md` §12.2.

- ✅ **M6.1 — repo port + schema (hermetic, no appliance).** `automation/finance/scrape.js` (read-only login → CSV) + `finance_ingest.py` (CSV → normalize → Txn-ID dedup → `lib/sheet`: append `Finance-Transactions`, upsert `Finance-Accounts`). Finance tabs standardized to `Finance-Budget`/`Finance-Accounts`/`Finance-Transactions`; `Category`/`Cat-Source` ship present-but-blank (the budget `SUMIFS` keys on the Category column position). `family-finance.{service,timer}` + provision wiring. Tests green; no live bank contact.
- ⬜ **M6.2 — appliance deploy + first interactive auth (the "VPS hour").** Place `bank_creds.json` (mode 600); rename the 3 live-Sheet tabs to the full names; Mizrahi first → verify CSV→Sheet roundtrip live → Max + Cal (interactive OTP once each); enable the timer.
- ⬜ **M6.3 — consumer wiring + close.** Briefing Money section + dashboard Money drawer read live; the >35d stale-import warning fires. Acceptance = the first real monthly review (~30 days in).
- 🔵 **M6.4 — analysis layer.** *Repo half built + tested (2026-06-18).* The on-box rules engine (`automation/lib/categorize.py` + committed `seeds/14_Finance_Category_Rules.csv`) populates `Category`/`Cat-Source` at ingest; DeepSeek gap-fills the rules-miss remainder (description + amount only, §8.6). The briefing Money section gained per-category spend + month-over-month (the dashboard drawer reads the same tab — M6.3). **Reconciliation (the build-note landmine, resolved):** budget actuals now `SUMIFS` with a **text-prefix wildcard** on the ISO-text Date (`<yyyy-mm>&"*"`), not a serial `DATE()` window that read ₪0 — chosen over `USER_ENTERED` (which would coerce `Txn-ID`/`Account` and break dedup); the append stays RAW. Seed formulas updated + a regression test pins the form. **Gated to M6.3 (live):** apply the same formulas to the live `Finance-Budget` tab and verify actuals go non-zero on the first real month. **PROVISIONAL** category vocab until Shanee's budget migration firms it up. Silent delivery; no anomaly detection.
- ⬜ **Parallel (Shanee).** Budget migration — her manual budget → `Finance-Budget`; gives the actuals a target and defines the category vocab the rules engine maps to.

## Gated — summarizer review (opens ~2026-06-20, needs ≥1 week live)

- ⬜ **First real classifier-accuracy run + false-positive cleanup** — run `accuracy_review.py` over a full week of live DeepSeek output; narrow any over-firing keyword patterns.
- ⬜ **External milestone review on the live system** — folds in the property lane's review too.

## v1.1 candidates (unordered — pick after v1 is boring)

- **Reply parsing** (done/snooze via WhatsApp) — code exists (`reply_handler.py`, already on `queue()` with `wa-{msg_id}` ids); remaining: lift the bridge's 1:1 read guard for exactly the two adult JIDs, port its Sheet writes to `lib/sheet`, reinstate the reply footer, and a PO call on kinds (solicited acks would otherwise consume the unsolicited budget).
- **AI-written weekly briefing** — the briefing is template-only by design; wiring LLM prose needs a privacy call (whole-Sheet context → DeepSeek) with Shanee. Pair it with a content review of the template.
- **Inbox-append trigger** for the classifier (inotify on `inbox.jsonl`) — sub-hour critical latency without changing the hourly digest cadence.
- **Machine-measured classifier FP rate** — a human-mark channel (an Inbox `review` column or a dashboard control) to replace the by-eye accuracy read.
- **Apify monthly result-counter cap** — a programmatic ≤₪120/mo backstop for the property secondary source (today bounded only by per-search/per-day calls + item caps).
- **">₪500 single charge" finance alert** — an explicit PO call; it's an alert path that brushes the killed anomaly lane, so deferred deliberately.
- **External uptime ping** (healthchecks.io dead-man) — closes the silent hard-VPS-down gap.
- Google Calendar connector → `Calendar-Events`; iCloud → GCal ICS subscribe; a Reminders `Priority` column + bulk-done; a Hebrew chrome-string completion pass.

## Frozen lanes 🧊

*Frozen = the script lives in `attic/`, unmaintained. Unfreeze = the stated condition holds AND v1 has been stable for 30 days.*

| Lane | Unfreeze condition |
|---|---|
| Pediatric milestones | the Health tab is actively maintained |
| Goal coaching | the Goals tab is updated weekly for a month (proves the habit) |
| PDF→event, receipt OCR, voice capture, Gmail bill parser, Maccabi forwarders | per-item PO request, one at a time |

**Killed** (not frozen — gone from the board): anomaly / subscription detection. A keyword categorizer, also once killed, returns only in bounded form as the on-box finance rules engine (M6.4).
