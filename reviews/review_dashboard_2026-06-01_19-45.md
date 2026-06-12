# Gemini-style Review — dashboard lane

- **When:** 2026-06-01T19:45:29
- **Provider:** gemini (`gemini-2.5-pro`)
- **Elapsed:** 0.0s
- **Attached files (7):**
  - `CLAUDE.md` (13,191 chars)
  - `06_Lift_Recommendations_2026-05-30.md` (19,112 chars)
  - `05_Dashboard_Design.md` (28,114 chars)
  - `Dashboard/DESIGN_LOG.md` (1,784 chars)
  - `Dashboard/index.html` (10,429 chars)
  - `Dashboard/app.js` (55,550 chars)
  - `Dashboard/styles.css` (10,522 chars)

---

## Response

### Concerns
(MOCK MODE — no API key set; this is a placeholder so the audit-trail file
still gets written. Set the provider's API key env var and re-run.)

### Missed alternatives
- None evaluated.

### Affirmations
- None evaluated.

### Concrete suggestions
- Set the provider API key (e.g. `export GEMINI_API_KEY=...`) and re-run.

### One question for the team
- Which provider do you want as the canonical reviewer going forward?


---

<details>
<summary>Full prompt sent (click to expand)</summary>

```
You are reviewing engineering decisions made in a working session on the "Family Inc"
household-automation project. You are the explicit adversarial-but-fair reviewer. The
team owners (Adar = CTO, Shanee = Chief Design + PO) value pushback over agreement.

## Project one-paragraph context
Adar's household-automation system. Master DB = Google Sheets. PWA dashboard pinned
to iPhone, write-back to the Sheet. Briefings via WhatsApp (Twilio). Israeli context
(ILS, Hebrew, Maccabi healthcare). Family = 2 adults + 2 kids (kid-1 3yr, kid-2 3mo).
Operating principles: briefings > notifications, alert budget 2/day, no kid-facing UI,
boring tech, one source of truth per domain.

## What this session changed
- Introduced a STRINGS.he / STRINGS.en table in `Dashboard/app.js` as the single source of truth for every chrome string. A `t(key, vars)` helper does {var} interpolation; an `applyChromeStrings()` walker handles `data-i18n` (textContent), `data-i18n-html` (innerHTML, used for the sign-in screen's embedded demo anchor), and `data-i18n-placeholder` (input placeholders).
- Translated every visible chrome surface: tabbar, Today-screen sections, six drawer names (contracts = "מנויים וחוזים"), banner, status pill, row action buttons, empty states across every list/drawer, Sunday view headings + inline copy, Settings (incl. sign-in / stale-badge / OAuth-not-configured / toast), and write-back action toasts.
- Rewrote `duePhrase()` to be language-aware with proper Hebrew singular / dual ("יומיים") / plural grammar.
- Added a "שפה / Language" segmented control in Settings that writes `localStorage.familyinc.lang` and reloads (pre-paint script on the next boot applies `lang`/`dir`).
- Snooze pills kept as `+1d`/`+3d`/`+7d`/`+14d`/`+30d` per PO call — Latin units, universal numerals.
- Date range on the Sunday header switched from `week of YYYY-MM-DD → YYYY-MM-DD` to a compact `D.M — D.M` (e.g. "7.6 — 14.6").
- Appended one line to `Dashboard/DESIGN_LOG.md`.

## What I want you to review
1. Architectural soundness of the changes above.
2. Missed alternatives or simpler paths we didn't consider.
3. Tradeoffs we made implicitly without writing them down.
4. Risks / failure modes not covered.
5. Internal consistency across the changed files.

## What I do NOT want you to review
- Style, tone, formatting, copyediting.
- Adherence to design "best practices" in the abstract — only call those out if
  ignoring them creates a concrete risk for THIS project.
- The roles or session ritual itself (out of scope; that's our process).
- Files I did not list in "What this session changed" — assume those are settled.

## Required output (use these headings, in this order)
### Concerns
Things that should change. Be specific (file + section). Rank by severity.

### Missed alternatives
Paths we likely didn't explore. One-sentence each. Don't develop them — just name them.

### Affirmations
Decisions you think are correct, especially non-obvious ones. Brief.

### Concrete suggestions
Edits we could make right now. Phrase as "replace X with Y because Z."

### One question for the team
The single most useful question you'd ask Adar+Shanee+Claude if you had one.

Be terse. We're going to act on this directly.

---

## Attached context files

The following files are attached for you to read. Each is delimited by a header line.
Reference them by relative path in your review.

=== File: CLAUDE.md ===
# Family inc. — Project Context

*Auto-loaded at the top of every session opened in this folder. Keep tight; long-form thinking lives in the numbered docs.*

## What this is

Adar's household-automation system. Source of truth = Google Sheets `Family_OS` (tabs per domain) + Drive folder structure. Briefings via WhatsApp (Twilio). PWA dashboard pinned to iPhone, write-back to the Sheet. Audience = Adar + Shanee. Kids' data is structured but adult-mediated. Israeli context throughout (ILS, Hebrew, Maccabi, etc.).

## Roles

| Role | Person | Owns |
|---|---|---|
| CTO + co-PO | **Adar** | Engineering direction, stack calls, ships code; joint product authority with Shanee |
| Chief Design + co-PO | **Shanee** | Product direction, UX feel; joint product authority with Adar |
| Lead Architect | **Claude** | System design, code/specs, tradeoff proposals — defers to either PO on product calls; defaults to Adar's preference on engineering details |
| Reviewer (adversarial but fair) | **Gemini** | Independent second opinion at session end — not a co-author, explicitly outside our context |

**Decision authority.** Adar and Shanee are joint POs. Either can start a session and take decisions on their own; the other does not need to be in the loop. Routine calls (copy, ordering, what's in a drawer, which color, what to ship next) land with whoever is leading the session. Major directional calls (new feature, principle change, removing something already shipped) are made jointly and recorded in the affected doc. Disagreements are surfaced, not papered over.

**Session leadership.** Whoever pastes the session-start prompt leads that session. Claude treats the leader as "the PO" for the duration and doesn't ask the other partner to weigh in unless the leader explicitly defers.

## Stack & file map

```
Family Inc/
├── CLAUDE.md                              ← this file (auto-loads)
├── 00_Architecture_and_Roadmap.md         ← north star + phase status
├── 01_Family_Kickoff_Guide.md             ← kickoff script
├── 02_Kickoff_Output_2026-05-30.md        ← real kickoff output (goals + owners)
├── 02_Reminders_Engine_Spec.md            ← reminders engine spec
├── 03_Partner_Signoff.md                  ← partner signoff doc
├── 04_Dashboard_Design_Prompt.md          ← dashboard design brief
├── 05_Dashboard_Design.md                 ← dashboard design (rev 2026-05-30: arc + ticker + skeleton + offline lock)
├── 06_Lift_Recommendations_2026-05-30.md  ← LIVE BACKLOG with ✅/🟢/🟡/❌ status
├── 07_WhatsApp_Group_Summarizer_Spec.md   ← WhatsApp groups feature spec
├── Dashboard/                             ← vanilla HTML/JS PWA prototype
│   ├── index.html, app.js, styles.css
│   ├── config.js, mock_data.json
│   └── README_SETUP.md                    ← OAuth setup
├── Automation/                            ← Python automation scripts
│   ├── README.md                          ← script index + cron suggestions
│   ├── hebcal_client.py                   ← Shabbat + chagim
│   ├── friday_briefing.py                 ← Claude-reads-whole-sheet briefing
│   ├── anomaly_detector.py                ← subscription/duplicate/drift
│   ├── pediatric_milestones.py            ← Tipat Halav schedule
│   ├── goal_coaching.py                   ← weekly retro one-liners
│   ├── hebrew_categorizer.py              ← merchant → category
│   ├── pdf_to_event.py                    ← Ohai-style multimodal
│   └── dira_tracker.py                    ← Dira BeHanacha scraper
├── Setup/                                 ← runbook for cred-dependent items
│   ├── 00_Runbook.md                      ← TOC
│   ├── 01_Israeli_Bank_Scrapers.md
│   ├── 02_Yad2_Madlan_Watchers.md
│   ├── 03_Gmail_MCP_Bill_Parser.md
│   ├── 04_Mindee_Receipt_OCR.md
│   ├── 05_iCloud_GCal_Sync.md
│   ├── 06_Voice_Receipt_Shortcuts.md
│   ├── 07_Maccabi_Passport_Forwarders.md
│   ├── 08_Israeli_Reminders_Seed.csv
│   ├── 09_Vaccine_Schedule_Seed.csv
│   ├── 10_Dashboard_Goals_Seed.csv
│   ├── 11_Kol_Zchut_Reference_Links.md
│   └── code/                              ← drop-in scripts (.js, .gs)
├── Briefings/                             ← generated briefing outputs
├── Family_OS.xlsx                         ← master sheet template
├── reminders_engine.py                    ← legacy script (kept until ported)
└── sunday_briefing.py                     ← legacy script (kept until ported)
```

## Operating principles (non-negotiable)

- **One source of truth per domain.** No data lives in two places. If it does, one of them is a view.
- **Boring tech.** Google Sheets > custom DB. CSV drops > brittle scrapers. PWA > native.
- **Alerts are a budget, not a firehose.** Hard cap = 2/day. WhatsApp is the only alert channel (PWA push declined 2026-05-30).
- **Chrome language: Hebrew default, English fallback toggle.** `<html lang="he" dir="rtl">` ships as default; `localStorage.familyinc.lang = "en"` flips to English. Data values (merchant strings, Kol-Zchut links) stay Hebrew regardless.
- **Offline write-back: queue + per-row tombstone, not lock.** Dashboard taps queue locally when offline; reconnect flushes them with `WriteQueue_Tombstone = now()`. Reminders engine reads tombstones on startup and skips rows tombstoned within 6h.
- **Briefings > notifications.** Daily 1-liner, Friday briefing, weekly Sunday review (Sat 21:00).
- **Partner-readable, kid-aware.** Both adults see everything. No kid-facing surface.
- **No money movement on Adar's behalf. No credential storage. No messages outside Adar+Shanee.**

## Where to look for what

| You need to know | Read |
|---|---|
| What we're trying to build | `00_Architecture_and_Roadmap.md` |
| What's done / pending / declined | `06_Lift_Recommendations_2026-05-30.md` (status legend at top) |
| Live backlog ordered by week | `06_Lift_Recommendations_2026-05-30.md` §"Ship order" |
| Dashboard contract | `05_Dashboard_Design.md` |
| Reminders engine contract | `02_Reminders_Engine_Spec.md` |
| Goals + owners + kids info | `02_Kickoff_Output_2026-05-30.md` |
| How to ship a cred-dependent item | `Setup/00_Runbook.md` → pick a section |
| What a Python automation does | `Automation/README.md` |

## DevOps — running and shipping the prototype

The interactive prototype at `Dashboard/` is the canonical design surface. To keep design sessions self-serve (either PO can run one without the other being available), the prototype is hosted as a live URL that both phones can hit at any time.

**Hosting:** GitHub Pages from the `main` branch, `/Dashboard/` subdirectory.

**Live URL:** `[TODO: Adar to set up GH Pages repo and paste URL here]`

**Working folder sync:** the `Family Inc/` folder lives on `[TODO: confirm — iCloud Drive recommended]` so both Adar and Shanee see the same files from their own machines.

**Session loop (whoever leads runs this):**

1. Open Cowork → load the `Family Inc/` folder.
2. Paste the session-start prompt (e.g. `08_Design_Session_Prompt.md` for a design session).
3. Claude reads `Dashboard/DESIGN_LOG.md` to see the prior session's state.
4. Decisions land as direct edits to `Dashboard/{index.html, app.js, styles.css, mock_data.json}`.
5. Cowork commits + pushes to `main` *(method: `[TODO: Adar — choose: auto-commit per save, manual `git push` at end of session, or session-end script]`).*
6. GitHub Pages redeploys; the live URL is fresh in ~30 seconds.
7. Leader refreshes their pinned PWA on phone or laptop → sees the change.
8. Loop until end-of-session.

**No live-machine dependency.** The live URL is always up; neither laptop needs to be on for the other PO to start a session.

**One-time setup checklist (Adar's responsibility, blocking Shanee's first solo session):**

- [ ] Create GH repo containing `Dashboard/` (root or `/docs/`)
- [ ] Enable GH Pages from `main`
- [ ] Decide and document the commit-on-save flow
- [ ] Pin the live URL as a PWA on both phones
- [ ] Paste the live URL into this file under "Live URL" above
- [ ] Confirm Family Inc folder sync method (iCloud Drive vs Google Drive vs Dropbox)

Until this checklist is complete, design sessions can still run locally — Claude edits files, leader opens `Dashboard/index.html` in a desktop browser. The phone-preview workflow waits on the GH Pages step.

## Phase status snapshot (2026-05-30)

- ✅ Phase 0 — schema, Drive structure
- 🟡 Phase 1 — Sunday briefing built; Calendar-Events tab live; Google Calendar connector not wired
- 🟡 Phase 2 — Reminders engine built (dry-run); Twilio not provisioned
- 🟢 Phase 3 — finance ingestion plan ready (`Setup/01_Israeli_Bank_Scrapers.md`)
- 🟢 Phase 4 — health/education seeds ready (`Setup/09_Vaccine_Schedule_Seed.csv`, etc.)
- 🟢 Phase 5 — goals seeded incl. Shanee's wellness goal
- ✅ Phase 6 — Dashboard PWA prototype shipped; design refresh applied 2026-05-30
- 🟢 Phase 6.1 — `LastDoneBy` + `DoneAt` + `WriteQueue_Tombstone` schema bump; rolling-7-day arc + domain-grouped ticker + skeleton + queue+tombstone offline model spec'd; engine addendum spec'd

---

# Session-end ritual — Gemini review

Every working session ends here. Don't close until this is done.

## Step 1 — Claude generates the Gemini prompt

At session end, Claude produces a copy-paste block in this exact shape:

```
You are reviewing engineering decisions made in a working session on the "Family Inc"
household-automation project. You are the explicit adversarial-but-fair reviewer. The
team owners (Adar = CTO, Shanee = Chief Design + PO) value pushback over agreement.

## Project one-paragraph context
Adar's household-automation system. Master DB = Google Sheets. PWA dashboard pinned
to iPhone, write-back to the Sheet. Briefings via WhatsApp (Twilio). Israeli context
(ILS, Hebrew, Maccabi healthcare). Family = 2 adults + 2 kids (kid-1 3yr, kid-2 3mo).
Operating principles: briefings > notifications, alert budget 2/day, no kid-facing UI,
boring tech, one source of truth per domain.

## What this session changed
[Claude fills in: a tight bullet list of decisions, files changed, specs landed.
One line per item. No defending — just what shifted.]

## What I want you to review
1. Architectural soundness of the changes above.
2. Missed alternatives or simpler paths we didn't consider.
3. Tradeoffs we made implicitly without writing them down.
4. Risks / failure modes not covered.
5. Internal consistency across the changed files.

## What I do NOT want you to review
- Style, tone, formatting, copyediting.
- Adherence to design "best practices" in the abstract — only call those out if
  ignoring them creates a concrete risk for THIS project.
- The roles or session ritual itself (out of scope; that's our process).
- Files I did not list in "What this session changed" — assume those are settled.

## Required output (use these headings, in this order)
### Concerns
Things that should change. Be specific (file + section). Rank by severity.

### Missed alternatives
Paths we likely didn't explore. One-sentence each. Don't develop them — just name them.

### Affirmations
Decisions you think are correct, especially non-obvious ones. Brief.

### Concrete suggestions
Edits we could make right now. Phrase as "replace X with Y because Z."

### One question for the team
The single most useful question you'd ask Adar+Shanee+Claude if you had one.

Be terse. We're going to act on this directly.
```

Claude fills in the "What this session changed" section with real specifics.

## Step 2 — Claude lists the context files to attach

Same message as Step 1, Claude appends:

> **Attach these to your Gemini chat:**
> - `00_Architecture_and_Roadmap.md` *(always)*
> - `06_Lift_Recommendations_2026-05-30.md` *(always — for backlog status)*
> - `CLAUDE.md` *(always — for principles + roles)*
> - *[lane-specific files that changed this session]*

Lane-specific defaults:

| Session worked on | Also attach |
|---|---|
| Dashboard UI/UX | `05_Dashboard_Design.md`, the three `Dashboard/*` files touched |
| Automation script | `02_Reminders_Engine_Spec.md` + the specific `Automation/*.py` files |
| Setup runbook | The specific `Setup/*.md` section |
| WhatsApp groups | `07_WhatsApp_Group_Summarizer_Spec.md` |
| New spec / new feature | Just the new doc + any docs it references |

## Step 3 — Adar runs the review externally

Adar pastes the prompt + files into a fresh Gemini chat, runs it, brings the output back to Claude in the next message.

## Step 4 — Resolve

Claude walks through Gemini's response and produces:

1. **Apply** — changes Claude agrees with, made directly to the affected files.
2. **Defend (with reason)** — places Claude disagrees, with a written justification appended to the relevant doc as a tradeoff note.
3. **Open** — items neither side can resolve without Adar/Shanee input — surfaced as a question.

The session closes with a one-paragraph summary appended to whatever spec/doc was the main artifact, in this shape:

> *Reviewed by Gemini 2026-MM-DD. Applied: [list]. Defended: [list with reasons]. Open: [list]. Tradeoffs accepted: [list].*

## When to skip the ritual

Tiny edits (typo fixes, single-line config changes, status-flag updates) don't need a review. Anything that changes a spec, ships code, or sets a direction does.

=== End: CLAUDE.md ===

=== File: 06_Lift_Recommendations_2026-05-30.md ===
# Family inc. — Lift Recommendations

*Research synthesis · 2026-05-30 · 4 parallel passes (Israel, plugins/MCPs, UX/design, AI)*
*Status updated 2026-05-30 — Adar approved with exclusions; new items added (§5 and §6).*

This doc lists every concrete change worth shipping. Each item: **what it is → what it unlocks → effort → source**. The top of each section is the highest-leverage move. The "Ship Order" at the bottom is the recommended sequencing.

## Status legend

- ✅ **APPLIED** — code/spec landed in this session, runbook in `Setup/` or scripts in `Automation/`
- 🟢 **APPROVED** — Adar approved, awaits live creds or scheduling
- 🟡 **PENDING** — needs Adar's decision (see notes)
- ❌ **DEFERRED** — explicitly skipped

**Session 2026-05-30 decisions:** §1 all approved except 1.12 ❌ and 1.13 ❌. §2 all approved except 2.7 ❌ (Adar declined — WhatsApp stays the only alert channel). §3 all approved. §4 all approved. Two new sections added: §5 WhatsApp group summarizer and §6 Shanee's grooming goal.

---

## 1. Israel-specific

### 1.1 ✅ `israeli-bank-scrapers` (Node cron) → replaces monthly CSV drop
Headless screen-scraper covering Hapoalim, Leumi, Discount, Isracard, Max, Cal. No Open-Banking license needed (uses your credentials). Schedule daily on a tiny VPS, append to **Finance — Transactions**. Biggest single ROI item in the whole list — kills the manual pain point.
Effort: **med (4 hrs)**. https://github.com/eshaham/israeli-bank-scrapers

### 1.2 ✅ Hebcal API → Shabbat times + chagim in every briefing
Free JSON/ICS for candle-lighting, parasha, all holidays, fast days. Use Kiryat Tivon coords for ⟨town⟩ area. Briefing line: *"Friday candle-lighting 19:21 · Shabbat ends 20:32."* Also drives "is tomorrow a chag?" so daycare/work plans don't surprise you.
Effort: **low (30 min)**. https://www.hebcal.com/home/195/jewish-calendar-rest-api

### 1.3 ✅ Yad2 + Madlan watchers — the "house goal" gets a heartbeat
Apify actors `swerve/yad2-scraper` and `swerve/madlan-analytics`. Filter ⟨town⟩, room count, price ceiling. Post matches to WhatsApp. Track median ₪/sqm trend on the dashboard so the house goal moves visibly each week.
Effort: **low (1 hr)**. https://apify.com/swerve/yad2-scraper · https://apify.com/swerve/madlan-analytics

### 1.4 ✅ Dira BeHanacha lottery tracker
Mechir LaMishtaken's successor. Up to 20% discount + ₪40-60K periphery grants. Lotteries open in waves. Scrape `dira.moch.gov.il` weekly for Northern district tenders. Direct line into the house goal.
Effort: **low (2 hrs)**. https://www.dira.moch.gov.il

### 1.5 ✅ Tipat Halav + National Immunization Registry (kid-2)
Vaccination registry is online since March 2025. For kid-2 (3 mo): 4-month vaccines next (DTaP-IPV-Hib-HepB + Rotavirus + PCV), then 6-month. No API — but a once-a-month manual sync into the Health tab + Reminders auto-fires.
Effort: **low (manual)**. https://me.health.gov.il/en/parenting/raising-children/immunization-schedule/babies-immunization-schedule/

### 1.6 ✅ Tofes 101 + reservist credits (annual, January)
2026 added temporary miluim nekudot zikui. Build a one-shot January reminder + auto-fill template from People tab (teudot zehut, ages, Shanee maternity status). Catches tax-refund opportunities the family would otherwise miss.
Effort: **low (1 hr)**. https://www.cwsisrael.com/israeli-tax-changes-2026-complete-guide/

### 1.7 ✅ Misrad HaRishui + TesTime — car-test SMS forward
Annual test SMS arrives ~6 weeks ahead with a TesTime booking link. Forward to a dedicated email, parse into Reminders. Same trick for license-renewal email.
Effort: **low (30 min)**. https://www.gov.il/en/service/car_licence_renewal

### 1.8 ✅ Maccabi → email/SMS forward + parse (no API)
Maccabi has no public API. The practical play: forward Maccabi confirmation emails/SMS to a Google Workspace label, parse with Apps Script into Health tab + Reminders. Covers kid-1's pediatrician slots, kid-2's DDH ultrasound, blood-test bookings.
Effort: **med (3 hrs)**. https://www.maccabi4u.co.il

### 1.9 ✅ Misrad HaPnim — passport tracker
Online status check for kid-2's Israeli passport; recurring reminders for adults' renewal expiries. Polish citizenship status via Urząd Stanu Cywilnego — manual, but auto-remind every 30 days.
Effort: **low (1 hr)**. https://www.gov.il/en/departments/population_and_immigration_authority

### 1.10 ✅ Hebrew/RTL chrome (default) with English fallback toggle
`lang="he" dir="rtl"` on root (default) · logical CSS (`padding-inline-start`) · week starts Sunday · `DD/MM/YYYY` · `Intl.NumberFormat('he-IL', {style:'currency', currency:'ILS'})` for "₪1,250" · wrap LTR runs in `<bdi>`. Heebo font (see §3.2). **Settings has a `עברית / English` toggle; `localStorage.lang = "en"` flips `lang`/`dir` and selects the English chrome strings.** Decision 2026-05-30 (post-Gemini-review): Hebrew chrome default, English fallback available; data values (merchant strings, Kol-Zchut links) stay in Hebrew regardless.
Effort: **lang/dir flip done; Hebrew chrome string translation pending (low — 2 hrs)**.

### 1.11 ✅ Kol-Zchut + Chaim V'Chessed deep-links per reminder
Add a `guide_url` column to Reminders. When a reminder fires, the "how to do this" guide is one tap away. Saves Shanee hunting through bureaucracy.
Effort: **low (ongoing)**. https://www.kolzchut.org.il

### 1.12 ❌ Inforu / Cellact as Israeli SMS fallback — DEFERRED by Adar 2026-05-30
If WhatsApp/Twilio stays unprovisioned, drop to InforuMobile SMS (Hebrew-supporting, ILS billing, ~$0.01-0.02/segment). Hot-swappable behind the existing alert function.
Effort: **med (2 hrs)**. https://apidoc.inforu.co.il

### 1.13 ❌ Finanda (Open Banking IL) — DEFERRED by Adar 2026-05-30
ISA-licensed Open-Banking data aggregator under Israel's 2021 Financial Information Service Law. Pulls bank + card data programmatically. Riseup shut down Dec 2025, so this is the leading replacement.
Effort: **med — but consumer eligibility unclear**. Use `israeli-bank-scrapers` today; revisit Finanda Q4 2026. https://www.finanda.com/en/

---

## 2. Plugins / MCPs / automation

### 2.1 ✅ Gmail MCP via Apps Script → bills auto-flow to Contracts/Transactions
Kanshi Tanaike's working Apps Script MCP server (protocol 2025-03-26) is drop-in for Cowork. Pair with a Claude extraction step that pulls amount/due-date/vendor from arnona/electric/internet/insurance emails. Populates Contracts + Reminders without touching Veryfi/Klippa-class spend.
Effort: **med (4 hrs)**. https://medium.com/google-cloud/gmail-processing-using-mcp-network-powered-by-google-apps-script-5ede2a25c94e

### 2.2 ✅ Mindee receipt OCR via Drive→Zapier→Sheets
Free tier, 96% accuracy, documented Zapier recipe: Drive upload → Mindee parse → Sheets row append. Klippa is the budget alternative if multilingual/Hebrew bites. Veryfi is overkill at $500/mo floor.
Effort: **low (2 hrs)**. https://zapier.com/shared/receipt-scan/54f6726fa0ce50ffc70ffd2de68d02684fb45a6e

### 2.3 ✅ iCloud → Google Calendar via public ICS share (free, one-way)
Shanee shares her iCloud calendar as a public URL → subscribe in Adar's Google Calendar → briefing sees both. Refresh ~10 min. Beats CalendarBridge ($5/mo) for the read-only briefing use case.
Effort: **low (15 min)**. https://www.onecal.io/blog/how-to-sync-apple-icloud-calendar-to-google-calendar

### 2.4 🟢 LlamaParse on insurance/contract PDFs
Drive watcher → LlamaParse → Claude extracts renewal date / premium / provider → Contracts tab. Reducto only if audit-grade matters; for a household's 20 PDFs LlamaParse is right.
Effort: **med (3 hrs)**. https://www.llamaindex.ai/llamaparse

### 2.5 🟢 WhatsApp delivery — stay on Twilio, plan migration
Meta's July 2025 pricing reshuffle plus Twilio's ~$0.005/msg markup makes the difference <$5/mo at family volume. Migrate to Meta Cloud API direct only when you want the cleaner template approval flow. Don't let the migration block §2.1-§2.4.
Effort: **migration = 4-6 hrs**. https://www.twilio.com/en-us/whatsapp/pricing

### 2.6 ✅ Voice capture: Hey Siri → Sheets row
`bcongdon/google-sheets-shortcut` (Apps Script webapp) is battle-tested. "Hey Siri, log expense" → dictation → Claude parses → row append. Wife-friendly. Pair with Whisper Memos if Hebrew dictation needs more accuracy.
Effort: **low (1 hr)**. https://github.com/bcongdon/google-sheets-shortcut

### 2.7 ❌ PWA web-push — DEFERRED by Adar 2026-05-30 (WhatsApp stays the only alert channel)
iOS 16.4+ supports Safari web-push for home-screen-installed PWAs. iOS 26 (2026) defaults home-screen sites to web-app mode. Use PWA push for "today" surfaces; keep WhatsApp for the Sunday briefing and true alerts.
Effort: **med (6 hrs)**. https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide

### 2.8 ✅ Steal Ohai.ai's "PDF/photo → calendar event" pipeline
Ohai's killer feature: snap a daycare flyer, get a calendar event + reminder. Replicable with Gemini multimodal + your Drive watcher in ~5 hrs. Probably the single feature most likely to win Shanee's daily use.
Effort: **med (5 hrs)**. https://www.ohai.ai/

---

## 3. Design / UX lift

### ✅ 3.1 Palette swap: warm-paper neutrals + indigo accent
The current green (#2d5f3f) reads "earnest startup." 2026 calm-tech is on warm-paper neutrals with one distinctive accent:

- Surface light: `#FAF8F5` · dark: `#15161A`
- Ink: `#1A1A1F` / `#E8E6E1`
- Muted: zinc `#71717A` `#A1A1AA` `#D4D4D8`
- Accent: **Linear-indigo `#5E6AD2`** (replaces green)
- Semantic: success `#3F8F5F` sage · warning `#C58B3A` amber · alert `#C44545` terracotta

### ✅ 3.2 Type stack: Inter + Heebo + Geist Mono
Inter for Latin UI (tabular figures = decimals align automatically). Heebo for Hebrew (9 weights, same metric feel as Inter — feels like one system). Geist Mono for amounts only ("₪4,280.00") so money rows are visually distinct without changing weight.

### ✅ 3.3 Card pattern: "Big number + sparkline" (Notion 3.4 / 2026)
Each domain drawer's closed state = one oversized KPI + a sparkline underneath. Tap → details. Money, Goals, Health all become legible in one glance. Add Robinhood's open-source `spark` library for drag-to-scrub on the sparkline — the cheapest single trick that makes a chart feel real. https://github.com/robinhood/spark

### ✅ 3.4 Beeminder-style "bright line" for long goals
Progress bars are dead for 3-5 year goals — they never visibly move. Draw a target line + actual line + colored safety band ("ahead / on pace / behind"). Apply to House fund, Career, Passive income. https://www.beeminder.com/strava

### ✅ 3.5 Sunday briefing = Strava year-in-sport meets Morning Brew
Vertical scroll of 5-6 "scenes": *This week's spend · Kids' biggest moment · Next week's three things · One goal nudge · One contract heads-up.* Plain typography, one accent color, one-line items. Text *is* the design.

### ✅ 3.6 Lean dense, but progressively disclose
2026 consensus: Notion/Linear/Stripe density wins on dashboards; Things-style whitespace loses. Family inc.'s move = dense Today (every domain visible) + drawers (every detail hidden until tap). You already have this — keep going.

### ✅ 3.7 "All caught up" empty state
When Today has nothing: sage-tinted card with the date + warm one-liner ("Nothing on fire. Tea? ☕"). Zero CTAs. The absence is the reward.

### ✅ 3.8 Liquid Glass icon (cheap iOS-native feel)
Apple auto-applies the iOS 26 glass shimmer to your `apple-touch-icon` — pay-once configure-once trick to make the home-screen icon look native without faking translucency inside the app.
https://branclon.com/blog/liquid-glass-pwa-icons/

### ✅ 3.9 Sticky status pill in lieu of Dynamic Island
PWAs can't claim the island. Use a sticky top one-liner instead: *"Sunday briefing ready · 2 alerts."*

---

## 4. AI / agentic lift

### ✅ 4.1 Friday family briefing (Claude reads the whole Sheet)
Scheduled Cowork task Friday 17:00 → pull last 7 days from all tabs (~30k tokens) → Claude Sonnet 4.6 writes a 5-sentence briefing → WhatsApp. Cost: ~$0.10/week. Replaces today's templated Sunday script with something context-aware. Honors "briefings > notifications" rule.
Effort: **1 day**.

### ✅ 4.2 Hebrew merchant categorizer (cache + LLM)
Claude leads Hebrew classification (~93% on 11-cat financial task). Architecture: regex/exact-match cache first ("שופרסל"→Groceries), LLM fallback for unknowns, write back to cache. Skips Plaid entirely.
Effort: **1-2 days**.

### ✅ 4.3 Receipt photo → Sheet via Shortcut
Share-sheet Shortcut: photo → Claude vision "extract vendor, total, date, category" → webhook → Sheets append. Same trick as §2.6 but for receipts. 30-second capture, wife-friendly.
Effort: **half day**.

### ✅ 4.4 Subscription creep + duplicate detector
Python diff on Transactions: flag (a) new strings appearing ≥2 months in a row, (b) same vendor + same amount within 48h, (c) amount drift (Netflix +12%). Rule-based, no LLM, no spam. Surface in Sunday briefing.
Effort: **1 day**.

### ✅ 4.5 Goal-coaching agent — weekly retro pattern
Avoid daily nudges (2.5hr/wk lost, per research). Weekly Sunday: one line per Goal — *"House fund: +4,200 ILS, on track for 2028"* or *"Career: no movement in 3 weeks — add a task?"* One question max. Respects the calm budget.
Effort: **1 day**.

### ✅ 4.6 Pediatric milestone monitor (passive, non-scary)
Monthly task: given kid age (3yr / 3mo), Claude checks CDC milestones + Israeli Tipat Halav schedule, flags only what's due this month. Design rule: never list red flags unsolicited; surface "vaccine X due by [date]," not "watch for autism signs."
Effort: **1-2 days**.

### ✅ 4.7 Tasklet-style actionable briefing replies
Shortwave's Tasklet (Jan 2026) pattern: WhatsApp briefing arrives with inline action buttons. Reply "1" to add reminder, "2" to schedule, "3" to dismiss. Twilio webhook routes back to Claude → Sheet write. Briefings → still calm, but actionable.
Effort: **2 days**.

### ✅ 4.8 Anomaly detection beyond the 500-ILS threshold
Rolling 90-day mean+stddev per category. Flag >2σ ("Groceries this week: 1,400 vs 850 avg"). Merchant-string drift collapse ("שופרסל דיל" + "שופרסל אקספרס" → one).
Effort: **1 day**.

---

---

## 5. WhatsApp group summarization (new — Adar request 2026-05-30)

### 5.1 🟢 Read groups + classify ALERT / DIGEST / ROUTINE
Full spec lives in `07_WhatsApp_Group_Summarizer_Spec.md`. Reads daycare, building, family, neighborhood groups via a WhatsApp Web bridge (Whapi.cloud recommended); classifies each message with Claude Haiku; fires WhatsApp alert only for messages tagged ALERT (shares the existing 2/day budget); rolls everything else into a morning digest section.

Why it matters: daycare parent chats at 22:00 ("tomorrow bring snack") + building/vaad messages get missed. This closes that hole without adding screen time.

Effort: **~15h split across 2 evenings**. Cost: **~$48/mo all-in** (Whapi $39 + Claude classification ~$9). Provider decision pending — see spec doc §"Provider choice."

---

## 6. Shanee's grooming + wellness goal (new — Adar request 2026-05-30)

### 6.1 ✅ Added as Goal 4 in the Goals tab
Fitness, weight, diet, skin, nails, hair — one integrated personal-habit goal owned by Shanee. Seeded in `Setup/10_Dashboard_Goals_Seed.csv` and `02_Kickoff_Output_2026-05-30.md`. Metric: weeks-at-cadence (target 52 by end of 2026). 90-day milestone: 3x/week routine sustained 8 consecutive weeks.

Tracked weekly in Friday/Sunday briefing through `Automation/goal_coaching.py` — surfaces "Wellness: 4 weeks at cadence, on pace" or "Wellness: missed last week — want a small reset?" One-line, never preachy.

Why it matters: until now, Goals tab was all Adar's career/passive-income work. Adding Shanee's personal goal makes the dashboard a shared system, not Adar's project Shanee tolerates.

---

## Ship order (recommended)

**Week 1 — kill the biggest pain points**

1. `israeli-bank-scrapers` cron (1.1) — replaces the manual CSV drop
2. Hebcal in Sunday briefing (1.2) — 30 minutes, immediate "wow"
3. iCloud → GCal public ICS (2.3) — 15 minutes, makes briefing real
4. Voice + receipt Shortcuts (2.6 + 4.3) — wife-facing wins

**Week 2 — close the loops**

5. Gmail MCP bill parser (2.1) — Contracts tab fills itself
6. Hebrew merchant categorizer (4.2) — Finance tab quality
7. Friday briefing via Claude reads-whole-sheet (4.1) — replaces templated script

**Week 3 — house goal gets a heartbeat**

8. Yad2 + Madlan watchers (1.3) + Dira BeHanacha tracker (1.4)
9. Beeminder bright-line goal viz (3.4)

**Week 4 — design refresh**

10. Palette swap to warm-paper + indigo (3.1)
11. Inter + Heebo + Geist Mono (3.2)
12. RTL guardrails (1.10)
13. Big-number + sparkline cards (3.3)

**Later — when the system is humming**

- LlamaParse on insurance PDFs (2.4)
- Tasklet-style reply-to-act (4.7)
- WhatsApp Cloud API direct migration (2.5)
- Pediatric milestone monitor (4.6)
- Tofes 101 January reminder (1.6)

---

## What to skip

- **Superhuman / Shortwave subscriptions** ($30/mo each) — rebuildable with Claude + Gmail MCP for ~$0.
- **Plaid-style enrichment** — LLM categorizer is cheaper, handles Hebrew better.
- **Daily-nudge apps** (Stoic-class) — violates *briefings > notifications*.
- **Faking Dynamic Island / Live Activities** in a PWA — Apple-only, gives a worse UX than a sticky status pill.
- **Finanda right now** — eligibility unclear for a household user. Revisit Q4 2026 when BOI expands open-banking to insurance/gemel.

---

*Source agents: 4 parallel research passes 2026-05-30. URLs inline. Full per-agent reports preserved in session memory.*
*Updated 2026-05-30: status marks applied; WhatsApp groups (§5) and Shanee's wellness goal (§6) added.*

---

## Reviewed by Gemini 2026-05-30 — Resolved

**Applied at this doc's level:**
- §1.10 Hebrew/RTL chrome confirmed as **default** with English fallback toggle (Adar's call: O1 = a). Updated to reflect the explicit toggle pattern.
- §5.1 WhatsApp summarizer: bridge recommendation switched from Whapi.cloud to self-hosted Baileys-on-dedicated-Android for privacy. See full revision in `07_WhatsApp_Group_Summarizer_Spec.md`.

**Resolved at the design-doc level (see `05_Dashboard_Design.md`):**
- Progress arc language scrubbed of streak/pace nag → rolling 7-day count.
- Appreciation ticker regrouped by **domain** primary, partner name inline (Adar's call: O2 = c).
- Explicit offline lock replaced with **queue + per-row tombstone**, the middle path Gemini proposed (Adar's call: D1 = accept). New `WriteQueue_Tombstone` column on Reminders; engine reads it on startup and skips rows tombstoned within 6h. Engine-side spec updated in `02_Reminders_Engine_Spec.md` §"Phase 6.1 addendum."

**Defended:** None.

**Open:** None.

**Tradeoffs accepted (logged 2026-05-30):**
- Hebrew chrome strings need translation work (~2h follow-up); the lang/dir flip ships now, the string set fills in incrementally.
- 6h tombstone window leaves a residual race: phone offline >6h with a queued completion → one extra alert before flush. Window is tunable.
- Domain-grouped ticker still surfaces names; we are betting domain primacy + partnership absorb the residual scoring risk.

=== End: 06_Lift_Recommendations_2026-05-30.md ===

=== File: 05_Dashboard_Design.md ===
# Family inc. — Dashboard Design (compressed)

*Phase 6. Written 2026-05-28. Revised 2026-05-30 to integrate four UX moves: rolling-7-day progress arc, domain-grouped appreciation ticker, skeleton loading, and offline queue + tombstone (replaces the explicit lock per 2026-05-30 review). Companion to `04_Dashboard_Design_Prompt.md`.*

**Chrome language:** Hebrew default with `<html lang="he" dir="rtl">`. English fallback selectable in Settings (`localStorage.lang = "en"` flips `lang`/`dir` and the chrome string set). The ASCII wireframes below show English labels for readability — the production surface renders Hebrew.

This is the abbreviated version because we're going straight to a working prototype. The four design directions are sketched briefly; the recommended direction is specified in enough detail that the prototype in `/Dashboard/` is its faithful implementation.

---

## Section 1 — Four design directions

**A. Today-first.** *One screen. "What needs me right now?" — overdue, fire-today, then the next two days. Money/Health/Goals collapsed at the bottom.* Optimized for: the 8 AM glance on a phone. Tradeoff: hides Phase 1 weekly context behind a tap, which makes the dashboard feel "thin" on quiet days. Failure mode: a quiet week and the screen looks empty, so the dashboard stops earning a tap.

**B. Domain tiles.** *Home is a 2×3 grid: Money, Health, Calendar, Goals, Car, Contracts. Each tile shows a number + a verb.* Optimized for: pulling a specific domain on demand. Tradeoff: forces a second tap before you see what's urgent — slower than "Today-first" for the morning glance. Failure mode: every domain looks equally important, so urgency gets lost.

**C. Stream.** *Chronological scroll of items from now → 60 days out. Cards mix reminders, calendar events, bill-dues, milestones.* Optimized for: forward planning, Sunday-briefing mood. Tradeoff: lousy at "what is overdue" because overdue items live above the fold and get scrolled past. Failure mode: long days the stream is a wall of text.

**D. Briefing-first.** *Home is the most recent Sunday briefing rendered as a page. "Today" is a small bar at top.* Optimized for: the Sunday 5-minute read with coffee. Tradeoff: weekday usage is awkward — most of the page is stale by Wednesday. Failure mode: nobody opens it Tue–Sat.

---

## Section 2 — Recommended direction: **Today-first with domain drawers**

Direction A, with Direction B's tiles demoted to a collapsible drawer below the fold, and a Sunday view available as a second tab. This matches the existing operating principle "briefings, not notifications" (the morning page is the briefing) and the existing Phase 1/Phase 2 engines (which already produce a daily glance and a Sunday briefing — the dashboard renders both, doesn't duplicate logic).

**Four UX refinements (added 2026-05-30):**

1. **Rolling 7-day progress arc** at top of Today — fixes the "thin on quiet days" failure mode by always showing positive forward motion, even when there's nothing urgent. Rolling total, not a streak — a sick week doesn't reset a counter to zero. *(Calm-tech: no streak, no pace nag.)*
2. **Passive appreciation ticker** at bottom of Today — surfaces who's been doing the work so the dashboard is a shared system, not a chore list.
3. **Skeleton loading state** on initial fetch — the UI shell renders in <50ms with the right shape, gapi fills it in.
4. **Explicit offline lock** on write-back — no silent queue. If the device is offline, the buttons are disabled and visibly say so. The 07:30 engine and the dashboard can never race because the dashboard only writes when it knows it can.

### Information architecture

```
Home (Today)
├── Header: 🏠 Family inc. · 2026-05-28 · "Adar"   (rendered RTL Hebrew)
├── Connection pill: 🟢 live  /  ⛔ offline — taps queue; flush on reconnect
├── Progress arc strip:
│     ╭─────╮  5 completed · last 7 days
│     │ ◐ 71│  Mon ✓ Tue ✓ Wed ✓ Thu ✓ Fri · Sat · Sun ·
│     ╰─────╯  (no streak counter, no pace text — calm-tech, see Gemini review)
├── Banner: red if any OVERDUE, orange if any FIRE TODAY, otherwise green "all clear"
├── Section: Today's actions    (reminders where Auto-flag ∈ {OVERDUE, FIRE TODAY})
├── Section: Today's calendar   (Calendar-Events rows where Date == today)
├── Section: Next 7 days        (reminders WEEK OUT + calendar events Mon–Sun)
├── Drawer (collapsed by default):
│   ├── Money     (budget % of month, top 3 categories over)
│   ├── Health    (next due appointments for any person)
│   ├── Goals     (each goal: %, next milestone, bright-line viz)
│   ├── Car       (test/insurance/license countdown)
│   └── Contracts (renewals within 60 days)
└── Appreciation ticker (Recently completed) — grouped by domain:
    Health    ✓ Pediatrician kid-2  (Shanee, 2h)
    Money     ✓ Arnona payment       (Adar, yest.)
    Education ✓ Daycare snack day    (Shanee, yest.)
    Car       ✓ Insurance renewal    (Adar, 2d)
    Domain is the primary axis; the partner's name appears inline as attribution.
    Reduces leaderboard / scoring read; keeps the transparency benefit intact.

Sunday tab
└── The latest Sunday briefing rendered (most recent /Briefings/*sunday_briefing.md)

Settings tab
├── Sign in / out (Google)
├── Sheet ID
└── Show: kid-mode mask (hide health for child rows), demo data toggle
```

The progress arc is fixed-height (~56px) so the Today section above the fold doesn't shift when it loads. The appreciation ticker sits below the domain drawers — last thing on the page, but visible without much scrolling.

### Wireframes

**Quiet weekday (8 AM) — the new "thin day" problem solved by the arc + ticker:**

```
┌─────────────────────────────────────────┐
│ 🏠 Family inc.            Thu May 28    │
│ 🟢 live                                  │
│ ─────────────────────────────────────── │
│  ╭─────╮  5 completed · last 7 days     │
│  │ ◐ 71│  M ✓  T ✓  W ✓  T ✓  F · S · S│
│  ╰─────╯                                │
│                                         │
│ ✅ all clear today                       │
│                                         │
│ TODAY                                   │
│   (nothing urgent)                      │
│                                         │
│ CALENDAR                                │
│   — no events —                         │
│                                         │
│ NEXT 7 DAYS                             │
│   🟡 Dentist kid-1    Tue Jun 2 (5d)  │
│   📆 Date night         Fri May 29 19:00│
│                                         │
│ ▸ Money · Health · Goals · Car · ...    │
│                                         │
│ RECENTLY COMPLETED                      │
│   Health    ✓ Pediatrician kid-2       │
│              (Shanee, 2h)               │
│   Money     ✓ Arnona payment            │
│              (Adar, yesterday)          │
│   Education ✓ Daycare snack day         │
│              (Shanee, yesterday)        │
│   Car       ✓ Insurance renewal         │
│              (Adar, 2d)                 │
│                                         │
│ ─────────────────────────────────────── │
│   Today  |  Sunday  |  Settings         │
└─────────────────────────────────────────┘
```

The screen never feels empty: the arc has yesterday's tick, the ticker shows the last few wins grouped by domain (not by person), the empty Today section is the reward, not a void.

**Heavy day with overdue:**

```
┌─────────────────────────────────────────┐
│ 🏠 Family inc.            Thu May 28    │
│ 🟢 live                                  │
│ ─────────────────────────────────────── │
│  ╭─────╮  2 completed · last 7 days     │
│  │ ◔ 25│  M ✓  T ·  W ✓  T ·  F · S · S│
│  ╰─────╯                                │
│                                         │
│ 🔴 1 overdue · 🟠 2 today                │
│                                         │
│ TODAY                                   │
│   🔴 Car annual test    overdue 3d      │
│      [✓ done]  [+7d]  [mute 30d]        │
│   🟠 Mortgage payment   due today       │
│      [✓ done]  [+7d]  [add note]        │
│   🟠 Dentist kid-1     due today       │
│      [✓ done]  [+7d]  [add note]        │
│                                         │
│ CALENDAR                                │
│   19:00 Date night · Cafe Levinsky      │
│                                         │
│ NEXT 7 DAYS                             │
│   🟡 Home insurance    Wed Jun 3 (6d)   │
│                                         │
│ ▸ Money (3 cats over) · Health · Goals  │
│                                         │
│ RECENTLY COMPLETED                      │
│   Money  ✓ Annual tax form              │
│           (Adar, this AM)               │
│   Health ✓ Pediatrician kid-2          │
│           (Shanee, yesterday)           │
│   … 4 more                              │
└─────────────────────────────────────────┘
```

No "behind — 6 to go" nudge; the arc only ever reports what was done, not what you missed. The ticker shows real motion grouped by domain — names attribute but don't lead.

**Offline (queue + tombstone — taps still work, sync when reconnected):**

```
┌─────────────────────────────────────────┐
│ 🏠 Family inc.            Thu May 28    │
│ ⛔ Offline — 2 taps queued · flush on    │
│    reconnect                            │
│ ─────────────────────────────────────── │
│  ╭─────╮  5 completed · last 7 days     │
│  │ ◐ 71│  M ✓  T ✓  W ✓  T ✓  F · S · S│
│  ╰─────╯  (cached)                       │
│                                         │
│ 🔴 1 overdue · 🟠 2 today  (cached)     │
│                                         │
│ TODAY                                   │
│   🔴 Car annual test    overdue 3d      │
│      [✓ done]  [+7d]  [mute 30d]        │
│   🟢 Mortgage payment   ⏳ queued —      │
│      will sync on reconnect             │
│   🟢 Dentist kid-1     ⏳ queued —      │
│      will sync on reconnect             │
│                                         │
│ NEXT 7 DAYS                             │
│   🟡 Home insurance    Wed Jun 3 (6d)   │
│                                         │
│ ▸ Money · Health · Goals · Car · ...    │
│                                         │
│ RECENTLY COMPLETED                      │
│   (will refresh after sync)             │
└─────────────────────────────────────────┘
```

Buttons stay enabled offline. A tap updates the UI optimistically and queues the write to `localStorage.pendingWrites[]`. The connection pill shows the queue length. On reconnect, the queue flushes — each write sets the target row's `WriteQueue_Tombstone = now()` in the same `batchUpdate` as the intended `Status`/`DoneAt`/`LastDoneBy` change. The 07:30 engine reads the tombstone column on startup and skips any row whose tombstone is within the last 6 hours, so a queued completion is never re-alerted. This is the middle path: no cognitive load on the user, no race with the engine.

**Initial load — skeleton shell (≤300ms typical):**

```
┌─────────────────────────────────────────┐
│ 🏠 Family inc.            Thu May 28    │
│ 🟢 live                                  │
│ ─────────────────────────────────────── │
│  ╭─────╮  ▒▒▒▒▒▒▒▒  ▒▒▒▒  ▒  ▒▒▒▒▒▒▒    │
│  │  ▒  │  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒           │
│  ╰─────╯                                │
│                                         │
│ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                      │
│                                         │
│ TODAY                                   │
│   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒              │
│   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒              │
│   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                    │
│                                         │
│ CALENDAR                                │
│   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                  │
│                                         │
│ NEXT 7 DAYS                             │
│   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                  │
│   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                  │
│                                         │
│ ▸ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                   │
│                                         │
│ RECENTLY COMPLETED                      │
│   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                  │
│   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                  │
└─────────────────────────────────────────┘
```

The shell is rendered from cached `localStorage` shape if any (so the previous values flash for ~80ms before getting replaced) or from neutral skeleton rows on cold start. No "Loading…" string. The header + connection pill + tab bar are real from t=0 because they don't depend on Sheet data. The Recently-Completed section also rebuilds its domain grouping from cache, so the ticker structure doesn't pop in.

**Sunday view (unchanged):**

```
┌─────────────────────────────────────────┐
│ Sunday Briefing · May 31 → Jun 7        │
│ ─────────────────────────────────────── │
│ Week ahead                              │
│   Wed Jun 3  Sunday review              │
│   Sat Jun 6  Cousin birthday 20:00      │
│                                         │
│ Reminders firing this week              │
│   (none)                                │
│                                         │
│ Money — ₪7,512 / ₪28,700 (26%)         │
│   No categories over budget.            │
│                                         │
│ Goals                                   │
│   Buy home · 5% · next: open savings    │
│   Wellness (Shanee) · 4 weeks ·  on pace│
│                                         │
│ Data hygiene                            │
│   4 People rows using placeholder names │
│                                         │
│   Today  |  Sunday  |  Settings         │
└─────────────────────────────────────────┘
```

### Data binding

| UI element | Sheet tab | Column(s) |
|---|---|---|
| Connection pill (live/offline) | (client) | `navigator.onLine` + 30s health-ping; not from Sheet |
| Progress arc — rolling 7-day completion | Reminders | count of `Status=Done` with `DoneAt` in last 7 days |
| Progress arc — weekday ticks | Reminders | per-day Done count over last 7 days, rendered as ✓ / · |
| Banner overdue/today counts | Reminders | L (Auto-flag) |
| Today's actions list | Reminders | A,B,C,D,G,J + computed K,L |
| Today's calendar | Calendar-Events | A=today |
| Next 7 days reminders | Reminders | K (1..7) |
| Next 7 days calendar | Calendar-Events | A in [today, today+7] |
| Money drawer total | Finance-Bdgt | B (target), C (actual) |
| Money over-budget tiles | Finance-Bdgt | E > 1.0 |
| Health drawer | Health | A, E (next due in next 60d) |
| Goals drawer | Goals | A, F, E, H |
| Goals bright-line viz | Goals | `target_at_start`, `target_at_deadline`, `pct_complete`, `target_date` |
| Car drawer | Car | D, E, G (countdown to each) |
| Contracts drawer | Contracts | E (renewal within 60d) |
| **Appreciation ticker** | **Reminders** | **`Status`=Done · `DoneAt` desc · limit 7 · render grouped by `Domain` (col B), inline: ✓ `Title` (`LastDoneBy`, relative time)** |
| **Tombstone (engine race guard)** | **Reminders** | **`WriteQueue_Tombstone` = ISO datetime set on every dashboard write; engine skips row if tombstone ∈ last 6h** |
| Sunday tab | (file) | latest `/Briefings/*sunday_briefing.md` rendered |

**New Reminders columns required for the four refinements** (Phase 6.1 schema bump):

| Column | Type | Set by | Purpose |
|---|---|---|---|
| `LastDoneBy` | text (name) | dashboard write-back | Appreciation ticker line · partner attribution |
| `DoneAt` | datetime ISO | dashboard write-back | Ticker ordering · rolling 7-day arc count |
| `WriteQueue_Tombstone` | datetime ISO | dashboard write-back (every write, online or queued) | Engine race guard — engine skips row if tombstone is within last 6h |

Existing `Last Sent` is preserved and continues to track when an alert fired — separate concern from when an action was completed.

### Interaction model

- Tap a reminder row → reveals three buttons: ✓ done, +Nd snooze, add note. Buttons stay enabled offline; offline taps queue locally (see Refresh / loading model).
- ✓ done: writes `Status = Done` + `DoneAt = now` + `LastDoneBy = currentUserName` + `WriteQueue_Tombstone = now` to the Reminders row, in one `batchUpdate`. If `Recurrence != One-off`, also bumps `Due Date`. Triggers an optimistic UI update + appreciation-ticker prepend (under the row's domain section).
- +Nd: user picks 1/3/7/14/30 from a quick row of pills → writes new Due Date + `Status = Snoozed` + `WriteQueue_Tombstone = now`. Does not write `DoneAt` (snooze isn't completion — keeps the 7-day count honest).
- Add note: appends to column J with a `[2026-05-28 Adar]` prefix + writes `WriteQueue_Tombstone = now`.
- Drawers tap to expand.
- Progress arc tap → expands to per-domain 7-day breakdown (Money/Health/etc. each get a small inline arc).
- Appreciation ticker is non-interactive — passive surface only. Tapping a row does nothing; it's read-only by design (the system shouldn't reward gaming the ticker). Domain headings are sticky as you scroll the ticker.
- Pull-to-refresh re-fetches all tabs.
- Settings: language toggle (`עברית` / `English`) — persists in `localStorage.lang`, flips `<html lang>` + `dir` + the chrome string set on next render.

### Tech stack

- **Vanilla HTML/JS PWA.** No build step. One `index.html`, one `app.js`, one `styles.css`. Hosted on GitHub Pages or any static host. "Boring tech" wins.
- **Google Identity Services (GIS)** for OAuth (token client, implicit flow). Works in iOS Safari with no native app.
- **gapi client** for Sheets v4. Reads use `spreadsheets.values.batchGet`. Writes use `spreadsheets.values.update`.
- **Manifest + service worker** for iPhone home-screen install + offline shell. Service worker caches the app shell; data always tries live first then falls back to last-cached JSON in `localStorage`.
- **No backend.** Auth happens client-side. Both Adar and Partner sign in with their own Google account (each must be shared as editor on the Sheet). The OAuth client_id is the same for both.

### Refresh / loading model

The state machine the client moves through on every cold open:

```
        t=0
         │  render shell + skeletons (no Sheet data yet)
         │  read cached snapshot from localStorage, replace skeletons if present
         │  ↓
t=~50ms  │  GIS bootstrap (silent token if available)
         │  ↓
t=~80ms  │  gapi load
         │  ↓
t=~200ms │  batchGet for all sheet ranges
         │  ↓
         │  if 2xx → render real cards (cross-fade over skeletons, 120ms)
         │            + flush localStorage.pendingWrites[] if any
         │  if offline / network error / 5xx → keep cached snapshot + stale badge
         │                                   + set state.online = false
         │                                   + leave write-back buttons enabled (queue mode)
         └→ idle
```

**Skeleton specifics:**

- One skeleton row per expected card. Counts come from the cached snapshot if available, otherwise: 3 Today rows, 2 Calendar, 3 Next-7-Days, 4 Recently-Completed.
- CSS: `.skeleton` class, a `linear-gradient(90deg, transparent, rgba(0,0,0,0.04), transparent)` shimmer at 1.6s `infinite`.
- The progress arc renders its own skeleton (gray ring + 4 gray weekday ticks) and is replaced with real values from the same batchGet response.
- Header + connection pill + tab bar are not skeleton-eligible — they have no Sheet dependency and must be live from t=0.
- Skeletons never animate while `state.online === false` — a static gray block is more honest than a "we're still trying" shimmer when we know we're not.

**Connection detection + queue flush:**

- Initial state: `state.online = navigator.onLine`.
- Listen to `online` / `offline` events on `window`.
- Belt-and-braces: a 30-second polled `HEAD` against the Sheets `userinfo` endpoint catches the "navigator-says-online-but-it's-actually-a-captive-portal" case.
- Any failed `gapi` write flips `state.online = false` immediately, regardless of `navigator.onLine`.
- When `state.online` transitions true → false: re-render with `<body>` getting the `is-offline` class. Connection pill updates to "⛔ offline — N taps queued." Buttons stay enabled. Ticker shows "will refresh after sync" placeholder.
- When `state.online` transitions false → true: **flush `localStorage.pendingWrites[]` first** (in tap order, one `batchUpdate` per row, each write includes the `WriteQueue_Tombstone = now()` column), then refetch via `batchGet`, then dismiss the pill notice. Failed flushes stay in the queue and retry on the next online event.
- **Queue shape:** `{ rowIndex, intent: "done"|"snooze"|"note", payload: {...}, queuedAt: ISO }`. Idempotent on retry (the tombstone makes double-flush safe).

### Edge cases

1. **Offline (subway).** Service worker serves cached shell + last `localStorage` snapshot. Connection pill shows "⛔ offline — N taps queued." Write-back buttons stay enabled; taps queue to `localStorage.pendingWrites[]` and the row gets a `⏳ queued — will sync on reconnect` indicator. On reconnect the queue flushes, each write also writing the row's `WriteQueue_Tombstone = now()`. The 07:30 engine reads tombstones on startup and skips any row tombstoned within the last 6h — so a queued completion is never re-alerted, even if the engine fires while the phone is still offline.
2. **Engine fires for a row the user already queued offline.** Engine sees `Status=Pending` (the queued write hasn't flushed yet) BUT `WriteQueue_Tombstone` is within 6h → engine skips the row and logs `skipped_due_to_tombstone` to `/Briefings/reminders_log.csv`. Worst-case scenario: a tombstone is more than 6h old (phone offline >6h with a queued completion) — engine sends one extra alert; queue still flushes correctly when phone reconnects. This is the accepted residual race; the 6h window is tunable in `reminders_engine.py` config.
3. **Online but Sheet write fails (rate limit, token expiry).** Optimistic UI rolls back; row goes back to its pre-tap state; small inline error "Couldn't save — retry?" replaces the action row briefly. Token expiry triggers a one-time silent refresh; if that fails, banner asks Adar to re-sign-in. Queued writes follow the same path.
4. **Back from a week off, 30 overdue.** Today section shows top 10 overdue by Due Date asc, with a "+20 more" footer that expands the list. Banner says "🔴 30 overdue — bulk done?" with a single tap that opens a multi-select. Arc shows the realistic low 7-day count — no streak to reset.
5. **Two people mark the same reminder done simultaneously.** Last-writer-wins at the Sheet level; ticker shows whoever's write succeeded second. Acceptable for a 2-person household.
6. **DoneAt skew (phone clock drift).** Use `Date.now()` on the client but the engine recomputes the 7-day count from `DoneAt` server-side once a day; minor skew (< 24h) is tolerated.
7. **Empty ticker (week 1).** Ticker section renders a quiet placeholder: "Marks of work done will show up here." No CTA, no shame. Domain headings appear as the first writes land.
8. **Queue grows large (no connectivity for days).** Cap at 50 pending writes; oldest start dropping with a one-shot warning toast "Queue full — N writes will be lost if not synced." Practically unreachable for household use; documented for safety.

---

## Section 3 — Feature gap analysis

### Missing in the data layer (ranked by leverage)

1. **`Reminders.Priority` column.** Right now everything sorts by date alone. "Bulk done" on a week-off needs urgency-aware ordering. Low cost, high leverage.
2. **`Calendar-Events` populated for real.** The dashboard's Calendar section is empty until the Google Calendar MCP is wired. This is already in Phase 1 backlog.
3. **~~`Reminders.LastDoneBy`.~~ NOW IN SCHEMA (Phase 6.1).** Plus the new `Reminders.DoneAt` column. Both feed the appreciation ticker and the rolling 7-day arc. Closed by this revision.
4. **`Settings` tab.** Today the dashboard infers user identity from the Google login email. A `Settings.UserMap` (email → Adar/Partner) is needed so the appreciation ticker shows the display name ("Shanee") instead of the email. Now blocking — was nice-to-have before. Also stores `lang` preference (Hebrew default, English fallback).
5. **`Reminders.WriteQueue_Tombstone` — NEW (Phase 6.1).** Per-row datetime set on every dashboard write (including queued writes when they flush). Engine reads on startup and skips rows tombstoned within 6h. Replaces the older "WriteQueue tab" idea — column-on-row is simpler and stays inside the Reminders schema.

### Exists but the dashboard probably won't surface

- **Finance-Txns line items.** 85+ rows is the wrong UI on a phone. Money drawer aggregates only.
- **Contacts tab.** No reason to surface in the daily view; lives in the Sheet.
- **Lists tab (controlled vocabs).** Pure schema infra, never surfaced.
- **Briefings folder, raw markdown other than Sunday.** Daily briefings are duplicated by the Today section; no need to render them.

### How each phase shows up on the dashboard

- **Phase 0 (schema).** Implicit — every dashboard row is read from the schema.
- **Phase 1 (calendar + Sunday briefing).** Today's calendar list; Sunday tab.
- **Phase 2 (reminders).** Today section + Next-7-days section + write-back buttons.
- **Phase 3 (finance).** Money drawer (target/actual/variance).
- **Phase 4 (health/education).** Health drawer; Education shown inside Health drawer under "Kids" sub-list.
- **Phase 5 (goals).** Goals drawer with bright-line viz (see `06_Lift_Recommendations_2026-05-30.md` §3.4).
- **Phase 6 (this dashboard).** Is the dashboard.
- **Phase 6.1 (this revision).** `LastDoneBy` + `DoneAt` + `WriteQueue_Tombstone` schema bump (3 new columns on Reminders); rolling 7-day progress arc + domain-grouped appreciation ticker UI; skeleton states; offline queue + per-row tombstone (engine race guarded). Hebrew default chrome with English fallback toggle. No new tabs; backwards compatible — old rows without `DoneAt`/tombstone are treated as never-tombstoned and excluded from arc math gracefully. Engine change required: read `WriteQueue_Tombstone` and skip rows within 6h — see `02_Reminders_Engine_Spec.md`.

---

*Prototype implementation lives in `/Dashboard/`. See `Dashboard/README_SETUP.md` for the 5-minute Google Cloud OAuth setup needed to wire it to your real Sheet. The four 2026-05-30 refinements are additive — none of them changes the existing read-path or write-path contracts, so they ship independently.*

---

## Reviewed by Gemini 2026-05-30 — Resolved

**Applied:**
- Progress arc language — removed "streak" and "behind pace" copy; replaced with neutral rolling-7-day count. Arc no longer resets on a bad week.
- Appreciation ticker — regrouped by **domain** primary, partner name appears inline as attribution. Reduces leaderboard read while preserving transparency (Gemini's "passive-aggressive scoring" question, Adar's call: option c).
- **Offline behavior — queue + per-row tombstone replaces the explicit lock** (Gemini Concern 3 / Suggestion 2, Adar's call to accept the middle path). New `WriteQueue_Tombstone` column on Reminders; engine reads tombstones on startup and skips rows tombstoned within 6h. Buttons stay enabled offline; taps queue locally and flush on reconnect. Engine spec updated separately — see `02_Reminders_Engine_Spec.md`.
- **Hebrew default chrome, English fallback toggle in Settings** (Adar's call: option a). `<html lang="he" dir="rtl">` ships as default; `localStorage.lang` selects English fallback. Chrome string translation is a follow-up task tracked in `06_Lift_Recommendations_2026-05-30.md` §1.10.

**Defended:** None — all Gemini concerns either applied or already aligned.

**Open:** None.

**Tradeoffs accepted:**
- The appreciation ticker still surfaces names — relying on domain-grouping + the partnership to absorb any residual scoring risk.
- The 6h tombstone window leaves a small residual race: if a phone is offline for >6h with a queued completion, the engine may send one extra alert before the queue flushes. Window is tunable in `reminders_engine.py` config; defensible at household scale.
- Hebrew chrome strings need translation; English ASCII wireframes remain in this doc for readability.

=== End: 05_Dashboard_Design.md ===

=== File: Dashboard/DESIGN_LOG.md ===
# Dashboard — Design Log

*One line per design session. Newest at top. The running prototype in this folder is the source of truth; this file is the audit trail of who changed what, when, and why.*

**Format:** `YYYY-MM-DD — Person — change summary (one sentence).`

---

## Log

- **2026-06-01 — Adar** — Hebrew chrome strings wired end-to-end: STRINGS.he/en table + `t()` helper + `data-i18n`/`-html`/`-placeholder` attribute walker; tabbar, sections, six drawers (contracts → "מנויים וחוזים"), banner, status pill, row buttons (✓ בוצע / + דחה / + הערה), all empty states, Sunday view ("סיכום ראשון" + literal subheads + "7.6 — 14.6" date range), Settings + sign-in + stale-badge + toasts; `duePhrase` now grammar-aware (יום/יומיים/ימים); "שפה / Language" segmented toggle added to Settings (persists to localStorage, reloads).
- **2026-05-30 — Claude (apply Gemini-review resolutions)** — Hebrew chrome default with English toggle (lang/dir flip + pre-paint script); the three new schema columns are referenced from the spec but UI surfacing is the next-session work for Shanee.
- **2026-05-30 — Claude (design refresh from lift recommendations)** — Palette swapped to warm-paper + Linear indigo; Inter+Heebo+Geist Mono added; sticky status pill, big-number+sparkline drawer states, Beeminder bright-line goal viz, "Nothing on fire ☕" empty state, Liquid Glass apple-touch-icon hint.
- **2026-05-28 — Claude (Phase 6 initial build)** — First working PWA: Today/Sunday/Settings tabs, domain drawers, write-back with snooze pills + notes, demo mode + live Sheets-API mode, OAuth setup documented.

---

*Next session: open. Likely candidates — schema-bump UI wiring (LastDoneBy / DoneAt / WriteQueue_Tombstone) or Shanee's pass on the Hebrew copy now that strings are in one place.*

=== End: Dashboard/DESIGN_LOG.md ===

=== File: Dashboard/index.html ===
<!doctype html>
<!--
  Chrome language: Hebrew default with English fallback toggle in Settings.
  Boot script reads localStorage.lang ("he" | "en") and rewrites lang + dir
  before first paint. Default is "he" / "rtl"; ASCII source below stays in
  English for legibility — the chrome string set lives in app.js.
-->
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>Family inc.</title>
  <meta name="description" content="Family inc. — household dashboard" />
  <meta name="theme-color" content="#5E6AD2" />

  <!-- iOS PWA -->
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-status-bar-style" content="default" />
  <meta name="apple-mobile-web-app-title" content="Family inc." />
  <!-- iOS 26 auto-applies the Liquid Glass treatment to this icon. -->
  <link rel="apple-touch-icon" href="icon-180.png" />

  <link rel="manifest" href="manifest.webmanifest" />
  <link rel="icon" type="image/svg+xml" href="icon.svg" />

  <!-- Google Fonts: Inter (UI), Heebo (Hebrew fallback), Geist Mono (numerals) -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Heebo:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap" />

  <link rel="stylesheet" href="styles.css" />
  <!-- Pre-paint lang/dir application from user preference (default: he/rtl) -->
  <script>
    (function () {
      try {
        var saved = localStorage.getItem('familyinc.lang');
        if (saved === 'en') {
          document.documentElement.setAttribute('lang', 'en');
          document.documentElement.setAttribute('dir', 'ltr');
        }
      } catch (_) { /* localStorage blocked — keep he/rtl default */ }
    })();
  </script>
</head>
<body>
  <!-- Sign-in screen (shown when not authenticated and not in demo mode) -->
  <div id="signin-screen" class="signin" hidden>
    <div style="font-size: 48px">🏠</div>
    <h2>Family inc.</h2>
    <p data-i18n-html="signin.prompt">Sign in with the Google account that has access to your <code>Family_OS</code> sheet.</p>
    <button class="signin-btn" id="signin-btn" data-i18n="signin.button">Sign in with Google</button>
    <p style="margin-top:24px;font-size:12px" data-i18n-html="signin.demoLine">
      Or <a href="#" id="demo-link">try with demo data</a>.
    </p>
  </div>

  <!-- App shell -->
  <div id="app" hidden>
    <header class="app-header">
      <h1>🏠 Family inc.</h1>
      <div class="date" id="header-date"></div>
    </header>

    <div id="stale-badge" class="stale-badge" hidden></div>

    <!-- TODAY view -->
    <section class="view active" id="view-today">
      <div id="status-pill" class="status-pill" hidden><span id="status-pill-text"></span></div>
      <div id="banner" class="banner clear" data-i18n="state.loading">Loading…</div>

      <div class="section">
        <h2 data-i18n="section.todayList">Today</h2>
        <div id="today-list"></div>
      </div>

      <div class="section">
        <h2 data-i18n="section.todayCalendar">Today's calendar</h2>
        <div id="today-cal"></div>
      </div>

      <div class="section">
        <h2 data-i18n="section.next7">Next 7 days</h2>
        <div id="next7-list"></div>
      </div>

      <div class="section">
        <h2 data-i18n="section.domains">Domains</h2>
        <div class="drawer" data-drawer="money">
          <div class="drawer-toggle">
            <span class="drawer-label"><span class="drawer-name" data-i18n="drawer.money">Money</span><span id="money-summary" class="row-meta"></span></span>
            <span class="kpi" id="money-kpi"></span>
            <svg class="sparkline" id="money-spark" viewBox="0 0 80 24"></svg>
          </div>
          <div class="drawer-body" id="money-body"></div>
        </div>
        <div class="drawer" data-drawer="health">
          <div class="drawer-toggle">
            <span class="drawer-label"><span class="drawer-name" data-i18n="drawer.health">Health</span><span id="health-summary" class="row-meta"></span></span>
            <span class="kpi" id="health-kpi"></span>
            <svg class="sparkline" id="health-spark" viewBox="0 0 80 24"></svg>
          </div>
          <div class="drawer-body" id="health-body"></div>
        </div>
        <div class="drawer" data-drawer="goals">
          <div class="drawer-toggle">
            <span class="drawer-label"><span class="drawer-name" data-i18n="drawer.goals">Goals</span><span id="goals-summary" class="row-meta"></span></span>
            <span class="kpi" id="goals-kpi"></span>
            <svg class="sparkline" id="goals-spark" viewBox="0 0 80 24"></svg>
          </div>
          <div class="drawer-body" id="goals-body"></div>
        </div>
        <div class="drawer" data-drawer="car">
          <div class="drawer-toggle">
            <span class="drawer-label"><span class="drawer-name" data-i18n="drawer.car">Car</span><span id="car-summary" class="row-meta"></span></span>
            <span class="kpi" id="car-kpi"></span>
            <svg class="sparkline" id="car-spark" viewBox="0 0 80 24"></svg>
          </div>
          <div class="drawer-body" id="car-body"></div>
        </div>
        <div class="drawer" data-drawer="contracts">
          <div class="drawer-toggle">
            <span class="drawer-label"><span class="drawer-name" data-i18n="drawer.contracts">Contracts</span><span id="contracts-summary" class="row-meta"></span></span>
            <span class="kpi" id="contracts-kpi"></span>
            <svg class="sparkline" id="contracts-spark" viewBox="0 0 80 24"></svg>
          </div>
          <div class="drawer-body" id="contracts-body"></div>
        </div>
        <div class="drawer" data-drawer="education">
          <div class="drawer-toggle">
            <span class="drawer-label"><span class="drawer-name" data-i18n="drawer.education">Education</span><span id="education-summary" class="row-meta"></span></span>
            <span class="kpi" id="education-kpi"></span>
            <svg class="sparkline" id="education-spark" viewBox="0 0 80 24"></svg>
          </div>
          <div class="drawer-body" id="education-body"></div>
        </div>
      </div>
    </section>

    <!-- SUNDAY view -->
    <section class="view sunday" id="view-sunday">
      <h2 class="briefing-title" data-i18n="sunday.title">Sunday Briefing</h2>
      <div class="week" id="sunday-week"></div>

      <div class="sub" data-i18n="sunday.weekAhead">Week ahead</div>
      <div id="sunday-week-ahead"></div>

      <div class="sub" data-i18n="sunday.remindersThisWeek">Reminders firing this week</div>
      <div id="sunday-reminders"></div>

      <div class="sub" data-i18n="sunday.overdue">Overdue</div>
      <div id="sunday-overdue"></div>

      <div class="sub" data-i18n="sunday.money">Money</div>
      <div id="sunday-money"></div>

      <div class="sub" data-i18n="sunday.goals">Goals</div>
      <div id="sunday-goals"></div>

      <div class="sub" data-i18n="sunday.hygiene">Data hygiene</div>
      <div id="sunday-hygiene"></div>
    </section>

    <!-- SETTINGS view -->
    <section class="view settings" id="view-settings">
      <div class="section">
        <h2 data-i18n="settings.account">Account</h2>
        <div class="row">
          <div id="settings-account" data-i18n="state.loading">Loading…</div>
          <div class="actions" style="display:flex">
            <button class="action-btn" id="signout-btn" data-i18n="settings.signOut">Sign out</button>
            <button class="action-btn" id="refresh-btn" data-i18n="settings.forceRefresh">Force refresh</button>
          </div>
        </div>
      </div>
      <div class="section">
        <h2 data-i18n="settings.language">Language</h2>
        <div class="row">
          <div class="actions" style="display:flex">
            <button class="action-btn" data-lang="he" data-i18n="settings.langHebrew">עברית</button>
            <button class="action-btn" data-lang="en" data-i18n="settings.langEnglish">English</button>
          </div>
        </div>
      </div>
      <div class="section">
        <h2 data-i18n="settings.sheet">Sheet</h2>
        <div class="row">
          <label><span data-i18n="settings.sheetIdLabel">Sheet ID</span>
            <input id="settings-sheetid" placeholder="from Google Sheet URL" data-i18n-placeholder="settings.sheetIdPlaceholder" />
          </label>
          <label><span data-i18n="settings.demoModeLabel">Demo mode</span>
            <select id="settings-demo">
              <option value="true" data-i18n="settings.demoOn">On (use mock data)</option>
              <option value="false" data-i18n="settings.demoOff">Off (live Google Sheet)</option>
            </select>
          </label>
          <div class="actions" style="display:flex; margin-top: 12px">
            <button class="action-btn primary" id="settings-save" data-i18n="settings.saveReload">Save & reload</button>
          </div>
        </div>
      </div>
      <div class="section">
        <h2 data-i18n="settings.pendingWrites">Pending writes</h2>
        <div class="row" id="settings-queue" data-i18n="empty.noQueuedWrites">No queued writes.</div>
      </div>
      <div class="section">
        <h2 data-i18n="settings.about">About</h2>
        <div class="row">
          <span data-i18n="settings.aboutBody">Family inc. dashboard · v0.1 · Phase 6 prototype</span>
          <div class="row-note" data-i18n="settings.aboutNote">Data lives in your Google Sheet. This page is a local view.</div>
        </div>
      </div>
    </section>

    <nav class="tabbar">
      <button data-tab="today" class="active" data-i18n="tabbar.today">Today</button>
      <button data-tab="sunday" data-i18n="tabbar.sunday">Sunday</button>
      <button data-tab="settings" data-i18n="tabbar.settings">Settings</button>
    </nav>
  </div>

  <div id="toast" class="toast"></div>

  <script src="config.js"></script>
  <script src="app.js"></script>
  <script>
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('sw.js').catch(() => {/* offline only — fine to fail */});
      });
    }
  </script>
</body>
</html>

=== End: Dashboard/index.html ===

=== File: Dashboard/app.js ===
// Family inc. dashboard — single-file SPA.
// Boring tech: vanilla JS, no build step, no framework.

(() => {
  'use strict';

  const cfg = window.FAMILY_INC_CONFIG;
  const SCOPES = 'https://www.googleapis.com/auth/spreadsheets';
  const DISCOVERY = 'https://sheets.googleapis.com/$discovery/rest?version=v4';
  const CACHE_KEY = 'family_inc_cache_v1';
  const QUEUE_KEY = 'family_inc_writequeue_v1';
  const TOKEN_KEY = 'family_inc_token_v1';

  // ---------------- i18n ----------------
  // Single source of truth for chrome strings. Hebrew is canonical; English
  // mirrors meaning, not literal legacy text. To add a key: drop it here and
  // tag the element with data-i18n="<key>" OR call t('<key>', {vars}) in JS.
  const STRINGS = {
    he: {
      // Tabbar
      'tabbar.today': 'היום',
      'tabbar.sunday': 'ראשון',
      'tabbar.settings': 'הגדרות',
      // Today screen sections
      'section.todayList': 'להיום',
      'section.todayCalendar': 'יומן היום',
      'section.next7': 'השבוע הקרוב',
      'section.domains': 'תחומים',
      // Drawers
      'drawer.money': 'כספים',
      'drawer.health': 'בריאות',
      'drawer.goals': 'יעדים',
      'drawer.car': 'רכב',
      'drawer.contracts': 'מנויים וחוזים',
      'drawer.education': 'חינוך',
      // Banner
      'banner.allClear': '✅ אין דברים דחופים',
      'banner.overdueAndToday': '🔴 {overdue} באיחור · 🟠 {today} להיום',
      'banner.overdueOnly': '🔴 {overdue} באיחור',
      'banner.todayOnly': '🟠 {today} להיום',
      // Status pill
      'pill.overdue': '{n} באיחור',
      'pill.dueToday': '{n} להיום',
      'pill.sundayReady': 'סיכום ראשון מוכן',
      // Row actions
      'row.done': '✓ בוצע',
      'row.snooze': '+ דחה',
      'row.note': '+ הערה',
      'prompt.addNote': 'הוסף הערה (תתווסף לעמודת הערות):',
      // Empty states
      'empty.nothingOnFire': 'שום דבר לא בוער. ☕',
      'empty.nothingThisWeek': 'אין אירועים השבוע.',
      'empty.noEventsToday': 'אין אירועים היום.',
      'empty.noQueuedWrites': 'אין כתיבות בתור.',
      'empty.next60Days': 'אין אירועים בחודשיים הקרובים.',
      'empty.noBudget': 'אין תקציב.',
      'empty.noGoals': 'אין יעדים.',
      'empty.noVehicle': 'אין רכב.',
      'empty.noRenewals': 'אין חידושים בחודשיים הקרובים.',
      'empty.noUpcoming': 'אין פריטים קרובים.',
      'empty.noOverdue': 'אין פריטים באיחור.',
      'empty.allClean': 'הכל נקי.',
      'state.allGood': 'הכל בסדר',
      'state.loading': 'טוען…',
      // Calendar
      'cal.allDay': 'כל היום',
      // Car field labels
      'car.annualTest': 'טסט שנתי',
      'car.insurance': 'ביטוח',
      'car.license': 'רישיון',
      // Generic chrome
      'label.next': 'הבא:',
      // Drawer summary templates
      'summary.upcoming': '{n} בקרוב',
      'summary.active': '{n} פעילים',
      'summary.over': '{n} חורגות',
      'summary.within60': '{n} בחודשיים הקרובים',
      // Sunday view
      'sunday.title': 'סיכום ראשון',
      'sunday.weekAhead': 'השבוע הקרוב',
      'sunday.remindersThisWeek': 'תזכורות לשבוע',
      'sunday.overdue': 'באיחור',
      'sunday.money': 'כספים',
      'sunday.goals': 'יעדים',
      'sunday.hygiene': 'תחזוקת נתונים',
      'sunday.monthToDate': 'מתחילת החודש',
      'sunday.noOverBudget': 'אף קטגוריה לא חרגה.',
      'sunday.hygienePeople': '{n} שורות באנשים עם שמות לדוגמה',
      'sunday.hygieneGoals': '{n} יעדים עם טקסט לדוגמה',
      // Settings
      'settings.account': 'חשבון',
      'settings.sheet': 'גיליון',
      'settings.language': 'שפה',
      'settings.pendingWrites': 'כתיבות בתור',
      'settings.about': 'אודות',
      'settings.sheetIdLabel': 'מזהה הגיליון',
      'settings.sheetIdPlaceholder': 'מתוך כתובת ה-Google Sheet',
      'settings.demoModeLabel': 'מצב הדגמה',
      'settings.demoOn': 'דלוק (נתוני הדגמה)',
      'settings.demoOff': 'כבוי (גיליון אמיתי)',
      'settings.signOut': 'התנתק',
      'settings.forceRefresh': 'רענן עכשיו',
      'settings.saveReload': 'שמור וטען מחדש',
      'settings.aboutBody': 'Family inc. dashboard · v0.1 · אב-טיפוס שלב 6',
      'settings.aboutNote': 'המידע יושב בגיליון Google שלך. הדף הזה הוא תצוגה מקומית.',
      'settings.demoModeStatus': 'מצב הדגמה',
      'settings.demoNoAccount': 'לא מחובר חשבון Google.',
      'settings.signedInAs': 'מחובר כ-{name}',
      'settings.notSignedIn': 'לא מחובר.',
      'settings.langHebrew': 'עברית',
      'settings.langEnglish': 'English',
      // Stale / offline
      'stale.offline': 'לא מקוון — נתונים מ-{when}',
      // Sign-in screen
      'signin.prompt': 'התחבר עם חשבון Google שיש לו גישה לגיליון <code>Family_OS</code> שלך.',
      'signin.button': 'התחבר עם Google',
      'signin.notConfigured': 'OAuth לא מוגדר',
      'signin.demoLine': 'או <a href="#" id="demo-link">נסה עם נתוני הדגמה</a>.',
      // Error toasts
      'toast.signinFailed': 'ההתחברות נכשלה: {err}',
      'toast.oauthNotConfigured': 'OAuth לא מוגדר — ראה README_SETUP.md',
      'toast.loadFailed': 'לא הצלחתי לטעון נתונים ואין מטמון זמין.',
      'toast.demoPrefix': '(הדגמה) {label}',
      'toast.queuedOffline': 'נשמר בתור לא מקוון: {label}',
      'toast.queued': 'נשמר בתור: {label}',
      'toast.flushed': 'הוזרמו {n} פעולות מהתור',
      // Action labels (used in toasts after write-back)
      'action.markedDone': 'בוצע: {title}',
      'action.snoozed': 'נדחה ב-+{days}d: {title}',
      'action.noteAdded': 'הערה נוספה',
    },
    en: {
      'tabbar.today': 'Today',
      'tabbar.sunday': 'Sunday',
      'tabbar.settings': 'Settings',
      'section.todayList': 'For today',
      'section.todayCalendar': "Today's calendar",
      'section.next7': 'This coming week',
      'section.domains': 'Domains',
      'drawer.money': 'Money',
      'drawer.health': 'Health',
      'drawer.goals': 'Goals',
      'drawer.car': 'Car',
      'drawer.contracts': 'Subscriptions & contracts',
      'drawer.education': 'Education',
      'banner.allClear': '✅ Nothing urgent',
      'banner.overdueAndToday': '🔴 {overdue} overdue · 🟠 {today} due today',
      'banner.overdueOnly': '🔴 {overdue} overdue',
      'banner.todayOnly': '🟠 {today} due today',
      'pill.overdue': '{n} overdue',
      'pill.dueToday': '{n} due today',
      'pill.sundayReady': 'Sunday briefing ready',
      'row.done': '✓ done',
      'row.snooze': '+ snooze',
      'row.note': '+ note',
      'prompt.addNote': 'Add a note (will be appended to the Notes column):',
      'empty.nothingOnFire': 'Nothing on fire. ☕',
      'empty.nothingThisWeek': 'Nothing scheduled this week.',
      'empty.noEventsToday': 'No events today.',
      'empty.noQueuedWrites': 'No queued writes.',
      'empty.next60Days': 'Nothing in the next two months.',
      'empty.noBudget': 'No budget yet.',
      'empty.noGoals': 'No goals yet.',
      'empty.noVehicle': 'No vehicle.',
      'empty.noRenewals': 'No renewals in the next two months.',
      'empty.noUpcoming': 'No upcoming items.',
      'empty.noOverdue': 'No overdue items.',
      'empty.allClean': 'All clean.',
      'state.allGood': 'All good',
      'state.loading': 'Loading…',
      'cal.allDay': 'all day',
      'car.annualTest': 'Annual test',
      'car.insurance': 'Insurance',
      'car.license': 'License',
      'label.next': 'next:',
      'summary.upcoming': '{n} upcoming',
      'summary.active': '{n} active',
      'summary.over': '{n} over',
      'summary.within60': '{n} in next two months',
      'sunday.title': 'Sunday Briefing',
      'sunday.weekAhead': 'Week ahead',
      'sunday.remindersThisWeek': 'Reminders this week',
      'sunday.overdue': 'Overdue',
      'sunday.money': 'Money',
      'sunday.goals': 'Goals',
      'sunday.hygiene': 'Data hygiene',
      'sunday.monthToDate': 'Month-to-date',
      'sunday.noOverBudget': 'No categories over budget.',
      'sunday.hygienePeople': '{n} People row(s) using placeholder names',
      'sunday.hygieneGoals': '{n} Goal(s) using placeholder text',
      'settings.account': 'Account',
      'settings.sheet': 'Sheet',
      'settings.language': 'Language',
      'settings.pendingWrites': 'Pending writes',
      'settings.about': 'About',
      'settings.sheetIdLabel': 'Sheet ID',
      'settings.sheetIdPlaceholder': 'from Google Sheet URL',
      'settings.demoModeLabel': 'Demo mode',
      'settings.demoOn': 'On (use mock data)',
      'settings.demoOff': 'Off (live Google Sheet)',
      'settings.signOut': 'Sign out',
      'settings.forceRefresh': 'Force refresh',
      'settings.saveReload': 'Save & reload',
      'settings.aboutBody': 'Family inc. dashboard · v0.1 · Phase 6 prototype',
      'settings.aboutNote': 'Data lives in your Google Sheet. This page is a local view.',
      'settings.demoModeStatus': 'Demo mode',
      'settings.demoNoAccount': 'No Google account is connected.',
      'settings.signedInAs': 'Signed in as {name}',
      'settings.notSignedIn': 'Not signed in.',
      'settings.langHebrew': 'עברית',
      'settings.langEnglish': 'English',
      'stale.offline': 'Offline — data from {when}',
      'signin.prompt': 'Sign in with the Google account that has access to your <code>Family_OS</code> sheet.',
      'signin.button': 'Sign in with Google',
      'signin.notConfigured': 'OAuth not configured',
      'signin.demoLine': 'Or <a href="#" id="demo-link">try with demo data</a>.',
      'toast.signinFailed': 'Sign-in failed: {err}',
      'toast.oauthNotConfigured': 'OAuth not configured — see README_SETUP.md',
      'toast.loadFailed': 'Could not load data and no cache available.',
      'toast.demoPrefix': '(demo) {label}',
      'toast.queuedOffline': 'Queued offline: {label}',
      'toast.queued': 'Queued: {label}',
      'toast.flushed': 'Flushed {n} queued action(s)',
      'action.markedDone': '{title} → done',
      'action.snoozed': '{title} → +{days}d',
      'action.noteAdded': 'Note added',
    },
  };
  function currentLang() {
    return document.documentElement.lang === 'en' ? 'en' : 'he';
  }
  function t(key, vars) {
    const dict = STRINGS[currentLang()] || STRINGS.he;
    let s = dict[key];
    if (s == null) s = key; // fail visibly if a key is missing
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        s = s.split(`{${k}}`).join(String(v));
      }
    }
    return s;
  }
  // Walks the DOM once at boot and replaces text content of any element tagged
  // with data-i18n="<key>". The English text in index.html is a fallback that
  // shows if JS fails to run. data-i18n-html does innerHTML — use only for keys
  // we control (e.g. signin.demoLine which embeds a known anchor).
  function applyChromeStrings() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const v = t(key);
      if (v != null && v !== key) el.textContent = v;
    });
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const key = el.dataset.i18nHtml;
      const v = t(key);
      if (v != null && v !== key) el.innerHTML = v;
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.dataset.i18nPlaceholder;
      const v = t(key);
      if (v != null && v !== key) el.setAttribute('placeholder', v);
    });
  }

  // ---------------- State ----------------
  const state = {
    user: null,           // {email, name}
    token: null,
    data: null,           // parsed sheet data
    cachedAt: null,
    tab: 'today',
    pendingWrites: [],
    today: stripTime(new Date()),
    tokenClient: null,
    gapiReady: false,
    gisReady: false,
  };

  // ---------------- Utilities ----------------
  function stripTime(d) {
    const x = new Date(d);
    x.setHours(0, 0, 0, 0);
    return x;
  }
  function daysBetween(a, b) {
    return Math.round((stripTime(a) - stripTime(b)) / (1000 * 60 * 60 * 24));
  }
  // Intl-based formatters (Hebrew locale). Defined as helpers so RTL copy "just works".
  const _ilsFmt = new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });
  const _dateHEFmt = new Intl.DateTimeFormat('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const _dateHEShortFmt = new Intl.DateTimeFormat('he-IL', { day: '2-digit', month: '2-digit' });

  function formatILS(n) {
    if (n == null || isNaN(n)) return '';
    return _ilsFmt.format(Math.round(n));
  }
  function formatDateHE(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return _dateHEFmt.format(d);
  }
  // Back-compat wrappers — old call sites still work, now wired to Hebrew formatting.
  function fmtDate(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return _dateHEShortFmt.format(d);
  }
  // Sub-shorthand: just "D.M" (e.g. "7.6") for the Sunday header date range.
  // Intl emits a trailing dot in he-IL for this style; we hand-format to skip it.
  function fmtDateShort(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    return `${d.getDate()}.${d.getMonth() + 1}`;
  }
  function fmtILS(n) { return formatILS(n); }
  // Wraps an amount string in an isolated bidi span so ₪ + Hebrew text don't reorder.
  function amountHtml(n) {
    const s = formatILS(n);
    if (!s) return '';
    return `<span class="amount bidi-amount">${escapeHtml(s)}</span>`;
  }
  function fmtISO(d) {
    if (!(d instanceof Date) || isNaN(d)) return '';
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
  function parseDate(v) {
    if (!v) return null;
    if (v instanceof Date) return isNaN(v) ? null : v;
    if (typeof v === 'number') {
      // Excel serial — used if we ever roundtrip from xlsx, but Sheets API
      // returns formatted strings, so this branch is rare.
      return new Date(Math.round((v - 25569) * 86400 * 1000));
    }
    const d = new Date(v);
    return isNaN(d) ? null : d;
  }
  function flagFor(daysUntil, status) {
    if (status === 'Done' || status === 'Skipped') return '';
    if (daysUntil == null || isNaN(daysUntil)) return '';
    if (daysUntil < 0) return 'OVERDUE';
    if (daysUntil <= 1) return 'FIRE TODAY';
    if (daysUntil <= 7) return 'WEEK OUT';
    if (daysUntil <= 30) return 'MONTH OUT';
    return '';
  }
  function flagEmoji(f) {
    return { 'OVERDUE': '🔴', 'FIRE TODAY': '🟠', 'WEEK OUT': '🟡', 'MONTH OUT': '🟢' }[f] || '·';
  }
  function flagClass(f) {
    return { 'OVERDUE': 'flag-OVERDUE', 'FIRE TODAY': 'flag-FIRE', 'WEEK OUT': 'flag-WEEK', 'MONTH OUT': 'flag-MONTH' }[f] || '';
  }
  function duePhrase(daysUntil) {
    if (daysUntil == null) return '';
    if (currentLang() === 'he') {
      // Hebrew grammar: singular (יום), dual (יומיים), plural (ימים).
      if (daysUntil < 0) {
        const abs = -daysUntil;
        if (abs === 1) return 'באיחור של יום';
        if (abs === 2) return 'באיחור של יומיים';
        return `באיחור של ${abs} ימים`;
      }
      if (daysUntil === 0) return 'להיום';
      if (daysUntil === 1) return 'מחר';
      if (daysUntil === 2) return 'בעוד יומיים';
      return `בעוד ${daysUntil} ימים`;
    }
    if (daysUntil < 0) return `overdue by ${-daysUntil}d`;
    if (daysUntil === 0) return 'due today';
    if (daysUntil === 1) return 'due tomorrow';
    return `in ${daysUntil}d`;
  }
  function toast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2200);
  }
  function colLetter(n) {
    // 1 → A, 27 → AA
    let s = '';
    while (n > 0) {
      const r = (n - 1) % 26;
      s = String.fromCharCode(65 + r) + s;
      n = Math.floor((n - 1) / 26);
    }
    return s;
  }

  // ---------------- Auth ----------------
  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src; s.async = true; s.defer = true;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Failed to load ' + src));
      document.head.appendChild(s);
    });
  }

  async function initAuth() {
    if (cfg.DEMO_MODE) return;
    if (!cfg.CLIENT_ID || cfg.CLIENT_ID.startsWith('PASTE_')) return;

    await loadScript('https://apis.google.com/js/api.js');
    await new Promise((resolve) => gapi.load('client', resolve));
    await gapi.client.init({ discoveryDocs: [DISCOVERY] });
    state.gapiReady = true;

    await loadScript('https://accounts.google.com/gsi/client');
    state.tokenClient = google.accounts.oauth2.initTokenClient({
      client_id: cfg.CLIENT_ID,
      scope: SCOPES,
      callback: (resp) => {
        if (resp.error) { toast(t('toast.signinFailed', { err: resp.error })); return; }
        state.token = resp;
        sessionStorage.setItem(TOKEN_KEY, JSON.stringify({ access_token: resp.access_token, expires_at: Date.now() + (resp.expires_in * 1000) }));
        afterSignIn();
      },
    });
    state.gisReady = true;

    // Restore session token if still valid (avoids forcing sign-in every reload).
    const saved = sessionStorage.getItem(TOKEN_KEY);
    if (saved) {
      try {
        const t = JSON.parse(saved);
        if (t.expires_at > Date.now() + 60000) {
          gapi.client.setToken({ access_token: t.access_token });
          state.token = t;
          afterSignIn();
        }
      } catch {}
    }
  }

  function requestSignIn() {
    if (!state.tokenClient) {
      toast(t('toast.oauthNotConfigured'));
      return;
    }
    state.tokenClient.requestAccessToken({ prompt: 'consent' });
  }

  function signOut() {
    sessionStorage.removeItem(TOKEN_KEY);
    state.token = null;
    state.user = null;
    if (window.google?.accounts?.oauth2) {
      google.accounts.oauth2.revoke(gapi.client.getToken()?.access_token, () => {});
    }
    showSignIn();
  }

  async function afterSignIn() {
    // Identify the user via Sheets API meta — cheap & uses the same scope.
    try {
      const meta = await gapi.client.sheets.spreadsheets.get({
        spreadsheetId: cfg.SHEET_ID,
        fields: 'properties.title',
      });
      // We don't get the email from Sheets directly — use the token's id_token
      // approach would require an extra scope. Instead, we just default to the
      // first email in cfg.USERS for attribution. User can override in Settings.
      const emails = Object.keys(cfg.USERS);
      state.user = { email: emails[0] || 'unknown', name: cfg.USERS[emails[0]] || 'You' };
    } catch (e) {
      console.warn('Could not load Sheet meta', e);
    }
    showApp();
    await loadAll();
  }

  // ---------------- Data load ----------------
  async function loadAll() {
    if (cfg.DEMO_MODE) {
      const resp = await fetch('mock_data.json');
      const json = await resp.json();
      state.data = parseAll(json);
      state.cachedAt = new Date();
      renderAll();
      return;
    }
    try {
      const tabs = cfg.TABS;
      const ranges = [
        `${tabs.reminders}!A:L`,
        `${tabs.calendarEvents}!A:H`,
        `${tabs.people}!A:I`,
        `${tabs.finance_bdgt}!A:I`,
        `${tabs.finance_txns}!A:I`,
        `${tabs.goals}!A:I`,
        `${tabs.health}!A:I`,
        `${tabs.education}!A:I`,
        `${tabs.car}!A:I`,
        `${tabs.contracts}!A:I`,
      ];
      const resp = await gapi.client.sheets.spreadsheets.values.batchGet({
        spreadsheetId: cfg.SHEET_ID,
        ranges,
        valueRenderOption: 'UNFORMATTED_VALUE',
        dateTimeRenderOption: 'FORMATTED_STRING',
      });
      const byRange = {};
      resp.result.valueRanges.forEach((vr, i) => {
        byRange[Object.keys(tabs)[['reminders','calendarEvents','people','finance_bdgt','finance_txns','goals','health','education','car','contracts'][i]]] = vr.values || [];
      });
      // Re-key by canonical names used by parseAll:
      const named = {
        reminders: resp.result.valueRanges[0].values || [],
        calendarEvents: resp.result.valueRanges[1].values || [],
        people: resp.result.valueRanges[2].values || [],
        finance_bdgt: resp.result.valueRanges[3].values || [],
        finance_txns: resp.result.valueRanges[4].values || [],
        goals: resp.result.valueRanges[5].values || [],
        health: resp.result.valueRanges[6].values || [],
        education: resp.result.valueRanges[7].values || [],
        car: resp.result.valueRanges[8].values || [],
        contracts: resp.result.valueRanges[9].values || [],
      };
      state.data = parseAll(named);
      state.cachedAt = new Date();
      localStorage.setItem(CACHE_KEY, JSON.stringify({ raw: named, at: state.cachedAt.toISOString() }));
      renderAll();
      await flushQueue();
    } catch (e) {
      console.error('Live load failed', e);
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const { raw, at } = JSON.parse(cached);
        state.data = parseAll(raw);
        state.cachedAt = new Date(at);
        document.getElementById('stale-badge').hidden = false;
        document.getElementById('stale-badge').textContent = t('stale.offline', { when: state.cachedAt.toLocaleString() });
        renderAll();
      } else {
        toast(t('toast.loadFailed'));
      }
    }
  }

  // ---------------- Parsers ----------------
  // Sheet tab → header row (row 1) + data rows (row 2+).
  // Each parsed row carries its 1-based sheet row number as `_row` so writes
  // can target the right cell.
  function rowsToObjects(rows) {
    if (!rows || rows.length < 2) return [];
    const headers = rows[0];
    return rows.slice(1).map((r, i) => {
      const o = { _row: i + 2 };
      headers.forEach((h, j) => { o[h] = r[j] ?? null; });
      return o;
    });
  }

  function parseAll(named) {
    const reminders = rowsToObjects(named.reminders).map(r => {
      const due = parseDate(r['Due Date']);
      const daysUntil = due ? daysBetween(due, state.today) : null;
      const status = r['Status'] || 'Pending';
      return {
        _row: r._row,
        title: r['Title'] || '',
        domain: r['Domain'] || '',
        owner: r['Owner'] || '',
        due,
        leads: (r['Lead Times (days)'] || '').toString().split(',').map(x => parseInt(x, 10)).filter(x => !isNaN(x)),
        recurrence: r['Recurrence'] || 'One-off',
        status,
        lastSent: parseDate(r['Last Sent']),
        channel: r['Channel'] || '',
        notes: r['Notes'] || '',
        daysUntil,
        flag: flagFor(daysUntil, status),
      };
    });
    const calendarEvents = rowsToObjects(named.calendarEvents).map(r => ({
      _row: r._row,
      date: parseDate(r['Date']),
      start: r['Start'] || '',
      end: r['End'] || '',
      title: r['Title'] || '',
      owner: r['Owner'] || '',
      source: r['Source'] || '',
      location: r['Location'] || '',
      notes: r['Notes'] || '',
    }));
    const people = rowsToObjects(named.people);
    const budget = rowsToObjects(named.finance_bdgt).map(r => ({
      category: r['Category'],
      target: parseFloat(r['Monthly Target (ILS)']) || 0,
      actual: parseFloat(r['Actual (current month)']) || 0,
      pct: parseFloat(r['% of Target']) || 0,
    })).filter(b => b.category && b.category !== 'Category');
    const txns = rowsToObjects(named.finance_txns).map(r => ({
      date: parseDate(r['Date']),
      account: r['Account'],
      desc: r['Description'],
      amount: parseFloat(r['Amount (ILS)']) || 0,
      category: r['Category'],
    }));
    const goals = rowsToObjects(named.goals).map(r => ({
      _row: r._row,
      goal: r['Goal'],
      owner: r['Owner'],
      horizon: r['Horizon'],
      targetDate: parseDate(r['Target Date']),
      milestone: r['90-Day Milestone'],
      pct: parseFloat(r['% Complete']) || 0,
      status: r['Status'],
    })).filter(g => g.goal);
    const health = rowsToObjects(named.health).map(r => ({
      person: r['Person'],
      provider: r['Provider'],
      specialty: r['Specialty'],
      nextDue: parseDate(r['Next Due']),
      action: r['Action Needed'],
    })).filter(h => h.person);
    const education = rowsToObjects(named.education).map(r => ({
      child: r['Child'],
      institution: r['Institution'],
      nextDate: parseDate(r['Next Key Date']),
      type: r['Type'],
      action: r['Action Needed'],
    })).filter(e => e.child);
    const car = rowsToObjects(named.car).map(r => ({
      vehicle: r['Vehicle'],
      plate: r['Plate'],
      test: parseDate(r['Annual Test (Rishui)']),
      insurance: parseDate(r['Insurance Renewal']),
      license: parseDate(r['License Expiry']),
    })).filter(c => c.vehicle);
    const contracts = rowsToObjects(named.contracts).map(r => ({
      contract: r['Contract'],
      provider: r['Provider'],
      type: r['Type'],
      renewal: parseDate(r['Renewal Date']),
      monthly: parseFloat(r['Monthly Cost (ILS)']) || 0,
    })).filter(c => c.contract);

    return { reminders, calendarEvents, people, budget, txns, goals, health, education, car, contracts };
  }

  // ---------------- Render ----------------
  function renderAll() {
    document.getElementById('header-date').textContent = state.today.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
    renderBanner();
    renderStatusPill();
    renderToday();
    renderTodayCalendar();
    renderNext7();
    renderDrawers();
    renderSunday();
    renderSettings();
  }

  // ---------------- Status pill ----------------
  function setStatusPill(text) {
    const pill = document.getElementById('status-pill');
    const txt = document.getElementById('status-pill-text');
    if (!pill || !txt) return;
    if (!text) {
      pill.hidden = true;
      txt.textContent = '';
      return;
    }
    txt.textContent = text;
    pill.hidden = false;
  }
  function renderStatusPill() {
    const r = state.data.reminders;
    const overdue = r.filter(x => x.flag === 'OVERDUE').length;
    const todayCount = r.filter(x => x.flag === 'FIRE TODAY').length;
    const dow = state.today.getDay(); // 0 = Sunday
    let msg = '';
    if (overdue > 0) {
      msg = t('pill.overdue', { n: overdue });
    } else if (todayCount > 0) {
      msg = t('pill.dueToday', { n: todayCount });
    } else if (dow === 0) {
      msg = t('pill.sundayReady');
    }
    setStatusPill(msg);
  }

  // ---------------- Sparkline + KPI ----------------
  function renderSparkline(svgEl, points) {
    if (!svgEl) return;
    if (!points || points.length < 2) { svgEl.innerHTML = ''; return; }
    const w = 80, h = 24, pad = 2;
    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = max - min || 1;
    const step = (w - pad * 2) / (points.length - 1);
    const coords = points.map((p, i) => {
      const x = pad + i * step;
      const y = h - pad - ((p - min) / range) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    svgEl.innerHTML = `<polyline points="${coords}" />`;
  }
  function renderKpi(drawerName, value, trend) {
    const kpiEl = document.getElementById(`${drawerName}-kpi`);
    if (!kpiEl) return;
    if (value == null || value === '') {
      kpiEl.textContent = '';
      kpiEl.classList.remove('kpi-pos', 'kpi-neg');
      return;
    }
    kpiEl.textContent = value;
    kpiEl.classList.toggle('kpi-pos', trend === 'pos');
    kpiEl.classList.toggle('kpi-neg', trend === 'neg');
  }

  // ---------------- Goal bright-line viz ----------------
  // Renders a small Beeminder-style chart:
  //   - target band (straight line from targetStart at t=0 → targetEnd at t=100%)
  //   - actual line (from 0 at start to `current` at pctTimeElapsed)
  //   - safety bands tinted around the target line
  function renderGoalLine(svgEl, { targetStart = 0, targetEnd = 100, current = 0, pctTimeElapsed = 0 } = {}) {
    if (!svgEl) return;
    const w = 100, h = 40, pad = 2;
    const yFor = (v) => {
      const clamped = Math.max(0, Math.min(100, v));
      return h - pad - (clamped / 100) * (h - pad * 2);
    };
    const xNow = Math.max(0, Math.min(100, pctTimeElapsed));
    const yT0 = yFor(targetStart);
    const yT1 = yFor(targetEnd);
    const yA0 = yFor(targetStart);
    const yA1 = yFor(current);
    // Safety bands (±5% of target line). Build as polygons spanning full width.
    const targetTopBand = `M 0,${yFor(Math.min(100, targetStart + 5))} L 100,${yFor(Math.min(100, targetEnd + 5))} L 100,0 L 0,0 Z`;
    const okBand        = `M 0,${yFor(Math.min(100, targetStart + 5))} L 100,${yFor(Math.min(100, targetEnd + 5))} L 100,${yFor(Math.max(0, targetEnd - 5))} L 0,${yFor(Math.max(0, targetStart - 5))} Z`;
    const badBand       = `M 0,${yFor(Math.max(0, targetStart - 5))} L 100,${yFor(Math.max(0, targetEnd - 5))} L 100,${h} L 0,${h} Z`;
    svgEl.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svgEl.setAttribute('preserveAspectRatio', 'none');
    svgEl.innerHTML = `
      <path class="band-ok"   d="${targetTopBand}" />
      <path class="band-warn" d="${okBand}" />
      <path class="band-bad"  d="${badBand}" />
      <polyline class="target-line" points="0,${yT0} 100,${yT1}" />
      <polyline class="actual-line" points="0,${yA0} ${xNow},${yA1}" />
      <circle class="now-dot" cx="${xNow}" cy="${yA1}" r="2" />
    `;
  }

  function renderBanner() {
    const r = state.data.reminders;
    const overdue = r.filter(x => x.flag === 'OVERDUE').length;
    const today = r.filter(x => x.flag === 'FIRE TODAY').length;
    const banner = document.getElementById('banner');
    if (overdue > 0 && today > 0) {
      banner.className = 'banner alert';
      banner.textContent = t('banner.overdueAndToday', { overdue, today });
    } else if (overdue > 0) {
      banner.className = 'banner alert';
      banner.textContent = t('banner.overdueOnly', { overdue });
    } else if (today > 0) {
      banner.className = 'banner warn';
      banner.textContent = t('banner.todayOnly', { today });
    } else {
      banner.className = 'banner clear';
      banner.textContent = t('banner.allClear');
    }
  }

  function renderToday() {
    const list = state.data.reminders
      .filter(r => r.flag === 'OVERDUE' || r.flag === 'FIRE TODAY')
      .sort((a, b) => (a.daysUntil ?? 9e9) - (b.daysUntil ?? 9e9));
    const el = document.getElementById('today-list');
    if (!list.length) {
      el.innerHTML = `<div class="empty-caught-up">${escapeHtml(t('empty.nothingOnFire'))} <span class="empty-date">${escapeHtml(formatDateHE(state.today))}</span></div>`;
      return;
    }
    el.innerHTML = list.map(renderReminderRow).join('');
    attachRowHandlers(el);
  }

  function renderNext7() {
    const list = state.data.reminders
      .filter(r => r.flag === 'WEEK OUT')
      .sort((a, b) => (a.daysUntil ?? 9e9) - (b.daysUntil ?? 9e9));
    const events = state.data.calendarEvents
      .filter(e => e.date && daysBetween(e.date, state.today) >= 1 && daysBetween(e.date, state.today) <= 7)
      .sort((a, b) => a.date - b.date);
    const el = document.getElementById('next7-list');
    let html = '';
    list.forEach(r => { html += renderReminderRow(r); });
    events.forEach(e => {
      const d = daysBetween(e.date, state.today);
      html += `<div class="row cal-event">
        <div class="row-top">
          <span class="row-title">📆 ${escapeHtml(e.title)}</span>
          <span class="row-meta">${fmtDate(e.date)} ${e.start || ''}</span>
        </div>
        ${e.location ? `<div class="row-note">${escapeHtml(e.location)}${e.owner ? ' · ' + escapeHtml(e.owner) : ''}</div>` : ''}
      </div>`;
    });
    el.innerHTML = html || `<div class="empty">${escapeHtml(t('empty.nothingThisWeek'))}</div>`;
    attachRowHandlers(el);
  }

  function renderTodayCalendar() {
    const todays = state.data.calendarEvents.filter(e => e.date && daysBetween(e.date, state.today) === 0);
    const el = document.getElementById('today-cal');
    if (!todays.length) {
      el.innerHTML = `<div class="empty">${escapeHtml(t('empty.noEventsToday'))}</div>`;
      return;
    }
    el.innerHTML = todays.map(e => `
      <div class="row cal-event">
        <div class="row-top">
          <span class="row-title">${escapeHtml(e.title)}</span>
          <span class="row-meta cal-time">${e.start || escapeHtml(t('cal.allDay'))}${e.end ? '–' + e.end : ''}</span>
        </div>
        ${e.location ? `<div class="row-note">${escapeHtml(e.location)}${e.owner ? ' · ' + escapeHtml(e.owner) : ''}</div>` : ''}
      </div>
    `).join('');
  }

  function renderReminderRow(r) {
    const emoji = flagEmoji(r.flag);
    const cls = flagClass(r.flag);
    return `<div class="row" data-row="${r._row}" data-id="${r._row}">
      <div class="row-top">
        <span class="row-title"><span class="flag ${cls}">${emoji}</span> ${escapeHtml(r.title)}</span>
        <span class="row-meta">${duePhrase(r.daysUntil)}</span>
      </div>
      ${r.notes ? `<div class="row-note">${escapeHtml(r.notes)}</div>` : ''}
      <div class="actions">
        <button class="action-btn primary" data-act="done">${escapeHtml(t('row.done'))}</button>
        <button class="action-btn" data-act="snooze">${escapeHtml(t('row.snooze'))}</button>
        <button class="action-btn" data-act="note">${escapeHtml(t('row.note'))}</button>
      </div>
      <div class="snooze-pills">
        ${[1,3,7,14,30].map(n => `<button class="snooze-pill" data-snooze="${n}">+${n}d</button>`).join('')}
      </div>
    </div>`;
  }

  function attachRowHandlers(container) {
    container.querySelectorAll('.row[data-row]').forEach(rowEl => {
      rowEl.addEventListener('click', (ev) => {
        const actBtn = ev.target.closest('[data-act]');
        const snoozeBtn = ev.target.closest('[data-snooze]');
        if (snoozeBtn) {
          ev.stopPropagation();
          const days = parseInt(snoozeBtn.dataset.snooze, 10);
          handleSnooze(rowEl.dataset.row, days);
          return;
        }
        if (actBtn) {
          ev.stopPropagation();
          const act = actBtn.dataset.act;
          if (act === 'done') handleDone(rowEl.dataset.row);
          else if (act === 'snooze') rowEl.classList.toggle('snoozing');
          else if (act === 'note') handleAddNote(rowEl.dataset.row);
          return;
        }
        rowEl.classList.toggle('expanded');
        rowEl.classList.remove('snoozing');
      });
    });
  }

  // ---------------- Drawers ----------------
  function renderDrawers() {
    // Money
    const totalTarget = state.data.budget.reduce((s, b) => s + b.target, 0);
    const totalActual = state.data.budget.reduce((s, b) => s + b.actual, 0);
    const overBudget = state.data.budget.filter(b => b.pct > 1.0);
    document.getElementById('money-summary').textContent = `${formatILS(totalActual)} / ${formatILS(totalTarget)}${overBudget.length ? ` · ${t('summary.over', { n: overBudget.length })}` : ''}`;
    document.getElementById('money-body').innerHTML = state.data.budget.map(b => `
      <div class="kv"><span>${escapeHtml(b.category)}</span><span class="v">${amountHtml(b.actual)} / ${amountHtml(b.target)} (${Math.round(b.pct * 100)}%)</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noBudget'))}</div>`;

    // Money KPI: % of monthly target. Sparkline: last 7 days of txn totals.
    const moneyPct = totalTarget ? Math.round(100 * totalActual / totalTarget) : null;
    renderKpi('money', moneyPct == null ? '' : `${moneyPct}%`, moneyPct != null && moneyPct > 100 ? 'neg' : 'pos');
    renderSparkline(document.getElementById('money-spark'), txnTrend7d());

    // Health (next 60d)
    const upcomingHealth = state.data.health
      .filter(h => h.nextDue && daysBetween(h.nextDue, state.today) <= 60 && daysBetween(h.nextDue, state.today) >= -30)
      .sort((a, b) => a.nextDue - b.nextDue);
    document.getElementById('health-summary').textContent = upcomingHealth.length ? t('summary.upcoming', { n: upcomingHealth.length }) : t('state.allGood');
    document.getElementById('health-body').innerHTML = upcomingHealth.map(h => `
      <div class="kv"><span>${escapeHtml(h.person)} · ${escapeHtml(h.specialty || h.provider || '')}</span><span class="v">${escapeHtml(formatDateHE(h.nextDue))}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.next60Days'))}</div>`;
    renderKpi('health', upcomingHealth.length ? String(upcomingHealth.length) : '', upcomingHealth.length ? 'neg' : 'pos');
    // No numeric trend for health — leave sparkline empty.
    renderSparkline(document.getElementById('health-spark'), null);

    // Goals
    document.getElementById('goals-summary').textContent = t('summary.active', { n: state.data.goals.length });
    document.getElementById('goals-body').innerHTML = state.data.goals.map((g, i) => {
      const pctTimeElapsed = goalPctTimeElapsed(g);
      return `
      <div class="kv goal-kv" data-goal-idx="${i}"><span>${escapeHtml(g.goal)} <span class="row-meta">· ${escapeHtml(g.owner || '')}</span></span><span class="v">${g.pct}%</span></div>
      <svg class="goal-line" id="goal-line-${i}" viewBox="0 0 100 40" preserveAspectRatio="none"></svg>
      ${g.milestone ? `<div class="row-note" style="margin: -2px 0 6px">${escapeHtml(t('label.next'))} ${escapeHtml(g.milestone)}</div>` : ''}
    `;
    }).join('') || `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;
    // After insertion, draw each goal-line.
    state.data.goals.forEach((g, i) => {
      const svg = document.getElementById(`goal-line-${i}`);
      if (svg) renderGoalLine(svg, {
        targetStart: 0,
        targetEnd: 100,
        current: g.pct,
        pctTimeElapsed: goalPctTimeElapsed(g),
      });
    });
    const avgPct = state.data.goals.length ? Math.round(state.data.goals.reduce((s, g) => s + (g.pct || 0), 0) / state.data.goals.length) : null;
    renderKpi('goals', avgPct == null ? '' : `${avgPct}%`, 'pos');
    renderSparkline(document.getElementById('goals-spark'), state.data.goals.length ? state.data.goals.map(g => g.pct || 0) : null);

    // Car
    const car = state.data.car[0];
    if (car) {
      const items = [
        [t('car.annualTest'), car.test],
        [t('car.insurance'), car.insurance],
        [t('car.license'), car.license],
      ].filter(([, d]) => d).map(([k, d]) => `<div class="kv"><span>${escapeHtml(k)}</span><span class="v">${escapeHtml(formatDateHE(d))} (${duePhrase(daysBetween(d, state.today))})</span></div>`);
      const nextDate = [car.test, car.insurance, car.license].filter(Boolean).sort((a, b) => a - b)[0];
      const next = nextDate ? `${t('label.next')} ${formatDateHE(nextDate)}` : '—';
      document.getElementById('car-summary').textContent = next;
      document.getElementById('car-body').innerHTML = items.join('');
      // KPI: days to next test (or any next milestone).
      if (nextDate) {
        const days = daysBetween(nextDate, state.today);
        renderKpi('car', `${days}d`, days < 14 ? 'neg' : 'pos');
      } else {
        renderKpi('car', '', null);
      }
    } else {
      document.getElementById('car-summary').textContent = '—';
      document.getElementById('car-body').innerHTML = `<div class="empty">${escapeHtml(t('empty.noVehicle'))}</div>`;
      renderKpi('car', '', null);
    }
    renderSparkline(document.getElementById('car-spark'), null);

    // Contracts (renewals within 60d)
    const renewals = state.data.contracts
      .filter(c => c.renewal && daysBetween(c.renewal, state.today) <= 60 && daysBetween(c.renewal, state.today) >= -30)
      .sort((a, b) => a.renewal - b.renewal);
    document.getElementById('contracts-summary').textContent = renewals.length ? t('summary.within60', { n: renewals.length }) : t('state.allGood');
    document.getElementById('contracts-body').innerHTML = renewals.map(c => `
      <div class="kv"><span>${escapeHtml(c.contract)} · ${escapeHtml(c.provider || '')}</span><span class="v">${escapeHtml(formatDateHE(c.renewal))}</span></div>
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noRenewals'))}</div>`;
    renderKpi('contracts', renewals.length ? String(renewals.length) : '', renewals.length ? 'neg' : 'pos');
    renderSparkline(document.getElementById('contracts-spark'), null);

    // Education
    const eduUp = state.data.education
      .filter(e => e.nextDate && daysBetween(e.nextDate, state.today) <= 60 && daysBetween(e.nextDate, state.today) >= -7)
      .sort((a, b) => a.nextDate - b.nextDate);
    document.getElementById('education-summary').textContent = eduUp.length ? t('summary.upcoming', { n: eduUp.length }) : t('state.allGood');
    document.getElementById('education-body').innerHTML = eduUp.map(e => `
      <div class="kv"><span>${escapeHtml(e.child)} · ${escapeHtml(e.type || '')}</span><span class="v">${escapeHtml(formatDateHE(e.nextDate))}</span></div>
      ${e.action ? `<div class="row-note" style="margin:-2px 0 6px">${escapeHtml(e.action)}</div>` : ''}
    `).join('') || `<div class="empty">${escapeHtml(t('empty.next60Days'))}</div>`;
    renderKpi('education', eduUp.length ? String(eduUp.length) : '', eduUp.length ? 'neg' : 'pos');
    renderSparkline(document.getElementById('education-spark'), null);

    // Attach drawer toggle handlers
    document.querySelectorAll('.drawer').forEach(d => {
      const toggle = d.querySelector('.drawer-toggle');
      toggle.addEventListener('click', () => d.classList.toggle('open'));
    });
  }

  // Build a last-7-day spending series from transactions (signed-amount sum per day).
  // Falls back to null if no transactions are available.
  function txnTrend7d() {
    const txns = state.data.txns || [];
    if (!txns.length) return null;
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(state.today);
      d.setDate(d.getDate() - i);
      const sum = txns
        .filter(t => t.date && daysBetween(t.date, d) === 0)
        .reduce((s, t) => s + Math.abs(t.amount || 0), 0);
      days.push(sum);
    }
    if (days.every(v => v === 0)) return null;
    return days;
  }

  // Estimate % of the goal's time window that has elapsed (0..100).
  function goalPctTimeElapsed(g) {
    if (!g.targetDate) return 0;
    const total = Math.max(1, daysBetween(g.targetDate, new Date(g.targetDate.getFullYear(), g.targetDate.getMonth() - 3, g.targetDate.getDate())));
    const elapsed = total - Math.max(0, daysBetween(g.targetDate, state.today));
    return Math.max(0, Math.min(100, Math.round((elapsed / total) * 100)));
  }

  // ---------------- Sunday view ----------------
  function renderSunday() {
    const start = new Date(state.today);
    const dow = start.getDay();
    // Sunday = 0; Israeli week starts Sunday.
    const daysToSunday = dow === 0 ? 0 : 7 - dow;
    const sundayStart = new Date(start);
    sundayStart.setDate(start.getDate() + daysToSunday);
    const weekEnd = new Date(sundayStart);
    weekEnd.setDate(sundayStart.getDate() + 7);

    document.getElementById('sunday-week').textContent = `${fmtDateShort(sundayStart)} — ${fmtDateShort(weekEnd)}`;

    // Week ahead
    const events = state.data.calendarEvents
      .filter(e => e.date && e.date >= sundayStart && e.date < weekEnd)
      .sort((a, b) => a.date - b.date);
    document.getElementById('sunday-week-ahead').innerHTML = events.length
      ? events.map(e => `<div class="kv"><span>${fmtDate(e.date)} ${e.start ? '· ' + e.start : ''} — ${escapeHtml(e.title)}</span><span class="v">${escapeHtml(e.owner || '')}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.nothingThisWeek'))}</div>`;

    // Reminders firing this week
    const weekRem = state.data.reminders
      .filter(r => r.daysUntil != null && r.daysUntil >= 0 && r.daysUntil <= 7 && r.status !== 'Done')
      .sort((a, b) => a.daysUntil - b.daysUntil);
    document.getElementById('sunday-reminders').innerHTML = weekRem.length
      ? weekRem.map(r => `<div class="kv"><span>${flagEmoji(r.flag)} ${escapeHtml(r.title)}</span><span class="v">${fmtDate(r.due)}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.noUpcoming'))}</div>`;

    // Overdue
    const overdue = state.data.reminders.filter(r => r.flag === 'OVERDUE').sort((a, b) => a.daysUntil - b.daysUntil);
    document.getElementById('sunday-overdue').innerHTML = overdue.length
      ? overdue.map(r => `<div class="kv"><span>🔴 ${escapeHtml(r.title)}</span><span class="v">${duePhrase(r.daysUntil)}</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.noOverdue'))}</div>`;

    // Money
    const totalT = state.data.budget.reduce((s, b) => s + b.target, 0);
    const totalA = state.data.budget.reduce((s, b) => s + b.actual, 0);
    const over = state.data.budget.filter(b => b.pct > 1.0);
    document.getElementById('sunday-money').innerHTML = `
      <div class="kv"><span>${escapeHtml(t('sunday.monthToDate'))}</span><span class="v">${amountHtml(totalA)} / ${amountHtml(totalT)} (${totalT ? Math.round(100 * totalA / totalT) : 0}%)</span></div>
      ${over.length ? over.map(b => `<div class="kv"><span>⚠ ${escapeHtml(b.category)}</span><span class="v">${Math.round(b.pct * 100)}%</span></div>`).join('') : `<div class="row-note" style="padding:6px 0">${escapeHtml(t('sunday.noOverBudget'))}</div>`}
    `;

    // Goals
    document.getElementById('sunday-goals').innerHTML = state.data.goals.map(g => `
      <div class="kv"><span>${escapeHtml(g.goal)} <span class="pill">${escapeHtml(g.owner || '')}</span><span class="pill">${escapeHtml(g.status || '')}</span></span><span class="v">${g.pct}%</span></div>
      ${g.milestone ? `<div class="row-note" style="padding: 0 0 6px">${escapeHtml(t('label.next'))} ${escapeHtml(g.milestone)}</div>` : ''}
    `).join('') || `<div class="empty">${escapeHtml(t('empty.noGoals'))}</div>`;

    // Data hygiene
    const placeholderPeople = state.data.people.filter(p => (p['Name'] || '').startsWith('['));
    const placeholderGoals = state.data.goals.filter(g => g.goal.startsWith('['));
    const hygiene = [];
    if (placeholderPeople.length) hygiene.push(t('sunday.hygienePeople', { n: placeholderPeople.length }));
    if (placeholderGoals.length) hygiene.push(t('sunday.hygieneGoals', { n: placeholderGoals.length }));
    document.getElementById('sunday-hygiene').innerHTML = hygiene.length
      ? hygiene.map(h => `<div class="kv"><span>${escapeHtml(h)}</span><span class="v">—</span></div>`).join('')
      : `<div class="empty">${escapeHtml(t('empty.allClean'))}</div>`;
  }

  // ---------------- Settings ----------------
  function renderSettings() {
    const acc = document.getElementById('settings-account');
    if (cfg.DEMO_MODE) {
      acc.innerHTML = `${escapeHtml(t('settings.demoModeStatus'))}<div class="row-note">${escapeHtml(t('settings.demoNoAccount'))}</div>`;
    } else if (state.user) {
      acc.innerHTML = `${escapeHtml(t('settings.signedInAs', { name: state.user.name }))}<div class="row-note">${escapeHtml(state.user.email)}</div>`;
    } else {
      acc.innerHTML = escapeHtml(t('settings.notSignedIn'));
    }
    document.getElementById('settings-sheetid').value = cfg.SHEET_ID;
    document.getElementById('settings-demo').value = String(cfg.DEMO_MODE);
    // Language toggle active state.
    const lang = currentLang();
    document.querySelectorAll('[data-lang]').forEach(b => {
      b.classList.toggle('primary', b.dataset.lang === lang);
    });
    renderQueue();
  }

  function renderQueue() {
    const q = document.getElementById('settings-queue');
    if (!state.pendingWrites.length) { q.textContent = t('empty.noQueuedWrites'); return; }
    q.innerHTML = state.pendingWrites.map(w => `<div class="kv"><span>${w.kind} · row ${w.row}</span><span class="v">${w.queuedAt}</span></div>`).join('');
  }

  // ---------------- Write-back ----------------
  function findReminder(rowNum) {
    return state.data.reminders.find(r => String(r._row) === String(rowNum));
  }

  async function handleDone(rowNum) {
    const r = findReminder(rowNum);
    if (!r) return;
    r.status = 'Done';
    r.flag = '';
    const writes = [
      { range: `${cfg.TABS.reminders}!G${rowNum}`, value: 'Done' },
      { range: `${cfg.TABS.reminders}!H${rowNum}`, value: fmtISO(new Date()) },
    ];
    // Bump recurring
    if (r.recurrence && r.recurrence !== 'One-off' && r.due) {
      const bumped = bumpDate(r.due, r.recurrence);
      if (bumped) {
        writes.push({ range: `${cfg.TABS.reminders}!D${rowNum}`, value: fmtISO(bumped) });
        writes.push({ range: `${cfg.TABS.reminders}!G${rowNum}`, value: 'Pending' });
        r.due = bumped; r.status = 'Pending';
        r.daysUntil = daysBetween(bumped, state.today);
        r.flag = flagFor(r.daysUntil, r.status);
      }
    }
    await applyWrites(writes, t('action.markedDone', { title: r.title }));
    renderAll();
  }

  async function handleSnooze(rowNum, days) {
    const r = findReminder(rowNum);
    if (!r || !r.due) return;
    const newDate = new Date(r.due);
    newDate.setDate(newDate.getDate() + days);
    r.due = newDate;
    r.status = 'Snoozed';
    r.daysUntil = daysBetween(newDate, state.today);
    r.flag = flagFor(r.daysUntil, r.status);
    await applyWrites([
      { range: `${cfg.TABS.reminders}!D${rowNum}`, value: fmtISO(newDate) },
      { range: `${cfg.TABS.reminders}!G${rowNum}`, value: 'Snoozed' },
    ], t('action.snoozed', { title: r.title, days }));
    renderAll();
  }

  async function handleAddNote(rowNum) {
    const r = findReminder(rowNum);
    if (!r) return;
    const text = window.prompt(t('prompt.addNote'));
    if (!text) return;
    const stamp = `[${fmtISO(new Date())} ${state.user?.name || 'You'}]`;
    const newNotes = (r.notes ? r.notes + ' \n' : '') + `${stamp} ${text}`;
    r.notes = newNotes;
    await applyWrites([{ range: `${cfg.TABS.reminders}!J${rowNum}`, value: newNotes }], t('action.noteAdded'));
    renderAll();
  }

  function bumpDate(d, recurrence) {
    const x = new Date(d);
    switch (recurrence) {
      case 'Daily': x.setDate(x.getDate() + 1); return x;
      case 'Weekly': x.setDate(x.getDate() + 7); return x;
      case 'Monthly': x.setMonth(x.getMonth() + 1); return x;
      case 'Quarterly': x.setMonth(x.getMonth() + 3); return x;
      case 'Yearly': x.setFullYear(x.getFullYear() + 1); return x;
      default: return null;
    }
  }

  async function applyWrites(writes, label) {
    if (cfg.DEMO_MODE) {
      toast(t('toast.demoPrefix', { label }));
      return;
    }
    if (!navigator.onLine || !state.gapiReady) {
      writes.forEach(w => state.pendingWrites.push({ kind: 'update', row: extractRow(w.range), range: w.range, value: w.value, queuedAt: new Date().toISOString() }));
      localStorage.setItem(QUEUE_KEY, JSON.stringify(state.pendingWrites));
      toast(t('toast.queuedOffline', { label }));
      renderQueue();
      return;
    }
    try {
      const data = writes.map(w => ({ range: w.range, values: [[w.value]] }));
      await gapi.client.sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: cfg.SHEET_ID,
        resource: { valueInputOption: 'USER_ENTERED', data },
      });
      toast(label);
    } catch (e) {
      console.error('Write failed', e);
      writes.forEach(w => state.pendingWrites.push({ kind: 'update', row: extractRow(w.range), range: w.range, value: w.value, queuedAt: new Date().toISOString() }));
      localStorage.setItem(QUEUE_KEY, JSON.stringify(state.pendingWrites));
      toast(t('toast.queued', { label }));
      renderQueue();
    }
  }
  function extractRow(range) { return (range.match(/(\d+)$/) || [])[1] || ''; }

  async function flushQueue() {
    if (!state.pendingWrites.length || cfg.DEMO_MODE) return;
    const queue = state.pendingWrites.slice();
    try {
      await gapi.client.sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: cfg.SHEET_ID,
        resource: {
          valueInputOption: 'USER_ENTERED',
          data: queue.map(w => ({ range: w.range, values: [[w.value]] })),
        },
      });
      state.pendingWrites = [];
      localStorage.setItem(QUEUE_KEY, JSON.stringify([]));
      toast(t('toast.flushed', { n: queue.length }));
      renderQueue();
    } catch (e) {
      console.warn('Queue flush failed', e);
    }
  }

  // ---------------- HTML helpers ----------------
  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ---------------- Tabs & UI shell ----------------
  function switchTab(name) {
    state.tab = name;
    document.querySelectorAll('nav.tabbar button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
  }
  function showApp() {
    document.getElementById('signin-screen').hidden = true;
    document.getElementById('app').hidden = false;
  }
  function showSignIn() {
    document.getElementById('signin-screen').hidden = false;
    document.getElementById('app').hidden = true;
  }

  // ---------------- Boot ----------------
  async function boot() {
    // Apply chrome strings to static markup BEFORE first paint of the shell.
    applyChromeStrings();

    // Restore queue
    try { state.pendingWrites = JSON.parse(localStorage.getItem(QUEUE_KEY)) || []; } catch {}

    // Tab clicks
    document.querySelectorAll('nav.tabbar button').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));

    // Sign-in screen buttons
    document.getElementById('signin-btn').addEventListener('click', requestSignIn);
    document.getElementById('demo-link').addEventListener('click', (e) => {
      e.preventDefault();
      cfg.DEMO_MODE = true;
      showApp();
      loadAll();
    });

    // Settings buttons
    document.getElementById('signout-btn').addEventListener('click', signOut);
    document.getElementById('refresh-btn').addEventListener('click', loadAll);
    document.getElementById('settings-save').addEventListener('click', () => {
      cfg.SHEET_ID = document.getElementById('settings-sheetid').value;
      cfg.DEMO_MODE = document.getElementById('settings-demo').value === 'true';
      localStorage.setItem('family_inc_config_override', JSON.stringify({ SHEET_ID: cfg.SHEET_ID, DEMO_MODE: cfg.DEMO_MODE }));
      location.reload();
    });

    // Restore config overrides (Sheet ID / demo flag) from a previous Settings save
    try {
      const o = JSON.parse(localStorage.getItem('family_inc_config_override'));
      if (o) Object.assign(cfg, o);
    } catch {}

    // Language toggle clicks (Settings → Language section).
    // Persist preference to localStorage then reload so the pre-paint script
    // applies the correct lang/dir on next boot.
    document.querySelectorAll('[data-lang]').forEach(b => {
      b.addEventListener('click', () => {
        const newLang = b.dataset.lang;
        try { localStorage.setItem('familyinc.lang', newLang); } catch {}
        location.reload();
      });
    });

    // Online → flush queue
    window.addEventListener('online', () => flushQueue());

    if (cfg.DEMO_MODE) {
      showApp();
      await loadAll();
      return;
    }
    if (!cfg.CLIENT_ID || cfg.CLIENT_ID.startsWith('PASTE_')) {
      showSignIn();
      document.getElementById('signin-btn').textContent = t('signin.notConfigured');
      document.getElementById('signin-btn').disabled = true;
      return;
    }
    await initAuth();
    if (!state.token) showSignIn();
  }

  document.addEventListener('DOMContentLoaded', boot);
})();

=== End: Dashboard/app.js ===

=== File: Dashboard/styles.css ===
/* Family inc. dashboard — single sheet of styles. Boring on purpose. */

:root {
  --bg: #FAF8F5;            /* warm paper */
  --card: #ffffff;
  --ink: #1A1A1F;
  --ink-dim: #71717A;       /* zinc-500 */
  --border: #D4D4D8;        /* zinc-300 */
  --muted: #A1A1AA;         /* zinc-400 */
  --accent: #5E6AD2;        /* Linear indigo */
  --red: #C44545;           /* terracotta — alert */
  --orange: #C58B3A;        /* amber — warning */
  --yellow: #C58B3A;        /* alias to amber for legacy flag classes */
  --green: #3F8F5F;         /* sage — success */
  --blue: #4A6FA5;          /* slate-blue — info */
  --shadow: 0 1px 2px rgba(0,0,0,0.04), 0 2px 8px rgba(0,0,0,0.04);
  --radius: 12px;
  --font: 'Inter', 'Heebo', -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
  --font-mono: 'Geist Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, "Courier New", monospace;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15161A;
    --card: #1E2127;
    --ink: #E8E6E1;
    --ink-dim: #A1A1AA;
    --border: #2A2A2E;
    --muted: #71717A;
    --accent: #7D8AEF;       /* Linear indigo (dark) */
    --shadow: 0 1px 2px rgba(0,0,0,0.2), 0 2px 8px rgba(0,0,0,0.2);
  }
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font);
  font-size: 16px;
  line-height: 1.4;
  -webkit-font-smoothing: antialiased;
  overscroll-behavior-y: contain;
}

body {
  max-width: 640px;
  margin: 0 auto;
  padding-block-start: env(safe-area-inset-top, 0);
  padding-block-end: calc(80px + env(safe-area-inset-bottom, 0));
  padding-inline: 12px;
  min-height: 100vh;
  font-feature-settings: "tnum", "cv11";
}

/* Header */
header.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-block: 12px 8px;
  padding-inline: 4px;
}
header.app-header h1 {
  font-size: 18px;
  margin: 0;
  font-weight: 600;
}
header.app-header .date {
  font-size: 14px;
  color: var(--ink-dim);
}

/* Sticky status pill */
.status-pill {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-block: 4px 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg) 78%, transparent);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  border: 1px solid var(--border);
  color: var(--accent);
  font-size: 13px;
  font-weight: 500;
  width: max-content;
  max-width: 100%;
}

/* Status banner */
.banner {
  padding: 14px 16px;
  border-radius: var(--radius);
  margin-block: 8px 16px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}
.banner.clear { background: rgba(63, 143, 95, 0.12); color: var(--green); }
.banner.warn  { background: rgba(197, 139, 58, 0.14); color: var(--orange); }
.banner.alert { background: rgba(196, 69, 69, 0.14); color: var(--red); }

/* Sections */
.section {
  margin-bottom: 18px;
}
.section h2 {
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--ink-dim);
  margin: 0 4px 8px;
  font-weight: 600;
}

/* Row card */
.row {
  background: var(--card);
  border-radius: var(--radius);
  padding: 12px 14px;
  margin-bottom: 8px;
  box-shadow: var(--shadow);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: transform 0.08s ease;
}
.row:active { transform: scale(0.99); }
.row.expanded { background: var(--card); }
.row-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
}
.row-title {
  font-weight: 500;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row-meta {
  font-size: 13px;
  color: var(--ink-dim);
  white-space: nowrap;
}
.row-note {
  font-size: 13px;
  color: var(--ink-dim);
  margin-top: 4px;
}
.flag { font-size: 13px; }
.flag-OVERDUE { color: var(--red); }
.flag-FIRE { color: var(--orange); }
.flag-WEEK { color: var(--yellow); }
.flag-MONTH { color: var(--green); }

/* Amounts — tabular mono, bidi-safe for Hebrew + ₪ */
.amount {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
.bidi-amount {
  unicode-bidi: isolate;
}

/* Actions revealed on expand */
.actions {
  display: none;
  margin-top: 10px;
  flex-wrap: wrap;
  gap: 6px;
}
.row.expanded .actions { display: flex; }
.action-btn {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--ink);
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
}
.action-btn:hover { background: var(--bg); }
.action-btn.primary {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
.action-btn.danger { color: var(--red); }
.snooze-pills {
  display: none;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 6px;
}
.row.snoozing .snooze-pills { display: flex; }
.snooze-pill {
  border: 1px solid var(--border);
  background: var(--bg);
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  color: var(--ink);
}

/* Empty state */
.empty {
  color: var(--ink-dim);
  font-size: 14px;
  padding: 8px 4px;
  font-style: italic;
}
.empty-caught-up {
  background: rgba(63, 143, 95, 0.10);
  color: var(--green);
  border-radius: var(--radius);
  padding: 24px 16px;
  text-align: center;
  font-size: 15px;
  font-weight: 500;
  margin-bottom: 8px;
}
.empty-caught-up .empty-date {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  font-weight: 400;
  color: var(--ink-dim);
  font-family: var(--font-mono);
}

/* Calendar events */
.cal-event { padding: 10px 14px; }
.cal-time { font-variant-numeric: tabular-nums; color: var(--blue); font-size: 13px; }

/* Drawer */
.drawer {
  background: var(--card);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  margin-top: 6px;
  overflow: hidden;
}
.drawer-toggle {
  padding: 12px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  user-select: none;
  gap: 10px;
}
.drawer-toggle .drawer-label {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 8px;
  overflow: hidden;
}
.drawer-toggle .drawer-name {
  font-weight: 500;
}
.drawer-toggle .kpi {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 20px;
  font-weight: 500;
  color: var(--accent);
  margin-inline-start: auto;
  white-space: nowrap;
}
.drawer-toggle .kpi.kpi-neg { color: var(--red); }
.drawer-toggle .kpi.kpi-pos { color: var(--accent); }
.drawer-toggle .kpi:empty { display: none; }
.drawer-toggle .sparkline {
  flex-shrink: 0;
  width: 80px;
  height: 24px;
  color: var(--accent);
  stroke: currentColor;
  fill: none;
  stroke-width: 1.5;
}
.drawer-toggle .sparkline:empty { display: none; }
.drawer-toggle::after {
  content: '\25B8';
  color: var(--ink-dim);
  transition: transform 0.15s ease;
  flex-shrink: 0;
}
.drawer.open .drawer-toggle::after { transform: rotate(90deg); }
.drawer-body {
  display: none;
  padding: 4px 14px 14px;
  border-top: 1px solid var(--border);
}
.drawer.open .drawer-body { display: block; }
.kv {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 14px;
  border-bottom: 1px solid var(--border);
  gap: 12px;
}
.kv:last-child { border-bottom: none; }
.kv .v {
  color: var(--ink-dim);
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono);
  white-space: nowrap;
}

/* Goal bright-line viz */
.goal-line {
  width: 100%;
  height: 40px;
  display: block;
  margin: 6px 0 4px;
}
.goal-line .band-ok { fill: rgba(63, 143, 95, 0.12); }
.goal-line .band-warn { fill: rgba(197, 139, 58, 0.14); }
.goal-line .band-bad { fill: rgba(196, 69, 69, 0.12); }
.goal-line .target-line { stroke: var(--ink-dim); stroke-width: 1; stroke-dasharray: 3 3; fill: none; }
.goal-line .actual-line { stroke: var(--accent); stroke-width: 2; fill: none; }
.goal-line .now-dot { fill: var(--accent); }

/* Tab bar */
nav.tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--card);
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-around;
  padding: 8px 0 calc(8px + env(safe-area-inset-bottom, 0));
  max-width: 640px;
  margin: 0 auto;
}
nav.tabbar button {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--ink-dim);
  font-size: 13px;
  cursor: pointer;
  padding: 6px 0;
  font-family: inherit;
}
nav.tabbar button.active { color: var(--accent); font-weight: 600; }

/* Sign-in screen */
.signin {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 70vh;
  text-align: center;
  padding: 24px;
}
.signin h2 { margin: 8px 0; font-weight: 600; }
.signin p { color: var(--ink-dim); max-width: 320px; }
.signin-btn {
  margin-top: 18px;
  background: var(--accent);
  color: white;
  border: none;
  padding: 12px 22px;
  border-radius: 999px;
  font-size: 16px;
  cursor: pointer;
  font-family: inherit;
}

/* Stale-cache badge */
.stale-badge {
  font-size: 12px;
  color: var(--orange);
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(197, 139, 58, 0.10);
  margin-bottom: 8px;
}

/* Hide views */
.view { display: none; }
.view.active { display: block; }

/* Sunday view */
.sunday h2.briefing-title { font-size: 22px; font-weight: 600; margin: 12px 4px 4px; }
.sunday .week { color: var(--ink-dim); margin: 0 4px 16px; font-size: 14px; }
.sunday .sub { color: var(--ink-dim); margin-top: 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; }
.sunday .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: var(--bg); margin-inline-end: 4px; font-size: 12px; color: var(--ink-dim); }

/* Settings */
.settings .row { cursor: default; }
.settings label { font-size: 13px; color: var(--ink-dim); display: block; margin-top: 8px; }
.settings input, .settings select {
  width: 100%;
  padding: 8px;
  margin-top: 4px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--ink);
  border-radius: 8px;
  font-family: inherit;
  font-size: 14px;
}

/* Toast */
.toast {
  position: fixed;
  bottom: 90px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--ink);
  color: var(--bg);
  padding: 10px 16px;
  border-radius: 999px;
  font-size: 14px;
  z-index: 100;
  opacity: 0;
  transition: opacity 0.2s ease;
  pointer-events: none;
}
.toast.show { opacity: 1; }

=== End: Dashboard/styles.css ===


```

</details>
