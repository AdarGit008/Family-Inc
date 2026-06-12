# Gemini-style Review — whatsapp lane

- **When:** 2026-06-04T20:50:57
- **Provider:** OpenCode Zen (`gemini-3.1-pro`)
- **Elapsed:** 1.0s
- **Attached files (7):**
  - `CLAUDE.md` (14,107 chars)
  - `06_Lift_Recommendations_2026-05-30.md` (20,547 chars)
  - `07_WhatsApp_Group_Summarizer_Spec.md` (17,708 chars)
  - `Automation/wa_outbox.py` (3,869 chars)
  - `Automation/whatsapp_bridge/baileys_listener.js` (9,685 chars)
  - `Automation/whatsapp_bridge/README.md` (2,656 chars)
  - `02_Reminders_Engine_Spec.md` (12,771 chars)

---

## Response

### Provider call failed

```
HTTP 401 Unauthorized: {"type":"error","error":{"type":"AuthError","message":"Missing API key."}}
```

Audit file written so the request payload is preserved. Re-run with a known-good model or report this shape to the script maintainer.


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
- DECISION (Adar, session lead, 2026-06-04): WhatsApp delivery = Baileys-first; Twilio NOT provisioned, demoted to fallback-if-flaky. Inforu SMS stays deep fallback. Supersedes 06-doc 2.5 "stay on Twilio."
- `whatsapp_bridge/baileys_listener.js`: bridge now also SENDS — polls `Automation/outbox/whatsapp_outbox.jsonl` every 15s, delivers 1:1, dedups per (id, target) against `whatsapp_sent.jsonl` (survives mid-"both" crash); hard scope guard: recipients limited to adar/shanee JIDs in uncommitted `recipients.json`, anything else refused + logged; outbox timer stops on disconnect.
- NEW `Automation/wa_outbox.py`: shared send helper — `queue_message(to, body, source)` (validates recipient, durable JSONL append), `bridge_alive()` (heartbeat staleness ≤45 min), `delivery_status(id)`. 2/day budget stays with callers; briefings exempt by principle.
- `whatsapp_summarizer.py` `dispatch_alert()`: mock body → queues to outbox (dry-run unchanged); warns when heartbeat stale.
- Smoke-tested: queue → simulated bridge send → per-target dedup (second pass 0 resends) → delivery_status; Hebrew body intact.
- Spec/docs updated for the decision: CLAUDE.md (stack line, phase 2, file map, Gemini context), 06-doc 2.5 (full decision record + tradeoffs) and §5, 02_Reminders spec (send step, templates note: free-form Hebrew, replies via bridge — requires lifting groups-only read guard for the two recipient JIDs, NOT BUILT; failure table: bridge-down row replaces Twilio-down; definition of done), 07 spec (scope note: groups stay read-only; 1:1 send to the two POs only), both READMEs, reminders_engine.py port comments.
- .gitignore fix: parent-relative patterns don't work in git; added `Automation/.gitignore` (inbox/, outbox/, data/), bridge ignores recipients.json.
- Accepted tradeoffs written down: unofficial-API ban risk (low volume, 1:1 pattern, sending slightly raises risk vs read-only); delivery depends on bridge machine uptime (durable queue + heartbeat surfacing, Sunday-briefing escalation if stale >24h).

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

Adar's household-automation system. Source of truth = Google Sheets `Family_OS` (tabs per domain) + Drive folder structure. Briefings via WhatsApp through the self-hosted Baileys bridge (decision 2026-06-04; Twilio not provisioned, kept as fallback). PWA dashboard pinned to iPhone, write-back to the Sheet. Audience = Adar + Shanee. Kids' data is structured but adult-mediated. Israeli context throughout (ILS, Hebrew, Maccabi, etc.).

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
├── 07_WhatsApp_Group_Summarizer_Spec.md   ← WhatsApp groups feature spec (built 2026-06-02, mock mode)
├── 08_Design_Session_Prompt.md            ← design session kickoff prompt
├── 09_Progress_Review_Session_Prompt.md   ← progress review kickoff (deck + architecture + Progress/ prototype)
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
│   ├── dira_tracker.py                    ← Dira BeHanacha scraper
│   ├── review.py                          ← session-end Gemini review (USE THIS, not hand-assembled prompts)
│   ├── whatsapp_summarizer.py             ← group msg classifier + tiered alerts + digest
│   ├── wa_outbox.py                       ← WhatsApp send helper (queue → bridge delivers)
│   └── whatsapp_bridge/                   ← self-hosted Baileys listener + outbox sender (Node, free)
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
│   ├── 12_WhatsApp_Group_Config_Seed.csv  ← group routing + alert/critical keywords
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
- 🟡 Phase 2 — Reminders engine built (dry-run); delivery = Baileys outbox (2026-06-04, Twilio dropped); awaits QR pairing + `recipients.json` + engine port to `wa_outbox.py`
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
to iPhone, write-back to the Sheet. Briefings via WhatsApp (self-hosted Baileys bridge). Israeli context
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
**Update 2026-06-03:** built for **Mizrahi + Max + Cal** on **Render cron** (Adar's call; supersedes Hapoalim/launchd default). Script + blueprint + setup checklist in `Automation/bank-scraper/`. Awaiting Adar's Render/Drive setup (~30 min) to go live.
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

### 2.5 ✅ WhatsApp delivery — Baileys-first, Twilio NOT provisioned — DECIDED by Adar 2026-06-04
**Supersedes "stay on Twilio."** The self-hosted Baileys bridge (§5) now also SENDS: Python automations append to `Automation/outbox/whatsapp_outbox.jsonl` via `Automation/wa_outbox.py`; the bridge polls every 15s and delivers 1:1 to Adar/Shanee only (scope guard via `recipients.json` on the bridge machine; refused otherwise). Per-(id,target) dedup against a sent ledger; per-target dedup survives a mid-"both" crash. Rationale: ₪0 marginal cost, no WABA business verification, no template approval fighting free-form Hebrew briefings, reply parsing free (bridge already reads). Accepted tradeoffs: unofficial API ban risk (mitigated: low volume, person-to-person pattern, dedicated paired device) and delivery depends on the bridge machine being up (mitigated: durable on-disk queue + existing heartbeat surfaced by callers via `bridge_alive()`). Twilio remains the documented fallback if the bridge proves flaky; Inforu SMS (1.12) stays the deep fallback.
Effort: **done (sender shipped 2026-06-04; awaits QR pairing + recipients.json)**.

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

### 5.1 ✅ Read groups + classify ALERT / DIGEST / ROUTINE — BUILT 2026-06-02 (mock mode)
Full spec lives in `07_WhatsApp_Group_Summarizer_Spec.md`. Phases A–E built: self-hosted **Baileys** bridge (`Automation/whatsapp_bridge/`) → inbox JSONL → `Automation/whatsapp_summarizer.py` classifies with Claude Haiku (deterministic fallback), applies 5 hard rules, routes ALERTs **per group** under the 2/day budget, and builds the daily digest. Mock-tested against the spec's verify checklist (all pass).

Why it matters: daycare parent chats at 22:00 ("tomorrow bring snack") + building/vaad messages get missed. This closes that hole without adding screen time.

Bridge decision: **self-hosted Baileys (free)**, not Whapi — Adar chose free + privacy-first. Cost now ~**$9/mo** (Claude classification only; bridge is free software on an always-on machine). Groups onboarded: daycare, building, neighborhood, family, student. **Update 2026-06-04:** `dispatch_alert()` now queues to the Baileys outbox (no Twilio — see 2.5); **remaining to go live:** pair the Baileys QR once + drop `recipients.json` on the bridge machine. Phase F (weekly accuracy tuning) not built.

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

=== File: 07_WhatsApp_Group_Summarizer_Spec.md ===
# Family inc. — WhatsApp Group Summarizer Spec

*Drafted: 2026-05-30 · Build session 2026-06-02 (Adar leading): Phases A–E built in mock mode. Bridge = self-hosted Baileys (free). Per-group alert routing added. · Update 2026-06-04 (Adar): alert dispatch = Baileys outbox — bridge now also sends; Twilio dropped (see 06-doc 2.5). Awaits: pair the bridge once + `recipients.json`.*

## Goal

Turn the firehose of WhatsApp groups Adar + Shanee are in (daycare, building, family, neighborhood) into:

1. **One daily "what happened in groups" digest** (delivered with the morning briefing).
2. **Real-time alerts for truly important messages** (under the existing 2/day alert budget).

This is squarely in scope of the "briefings > notifications" principle.

## Use cases (from real life)

- Daycare parent group at 22:00: "Tomorrow brings snack." Easy to miss. → Important.
- Building group: maintenance worker coming Thursday 09:00. → Important if Adar/Shanee are home.
- Family group: birthday photos, memes. → Digest only.
- Kid's pediatrician sends an SMS-style notice via a wide list. → Important.
- "Anyone has a babysitter recommendation?" → Digest if posted by stranger; important if posted by close friend.

## Architecture

```
WhatsApp groups (Adar's phone)
        │
        ▼
WhatsApp Web bridge (provider — see §"Provider choice")
        │   webhook on every incoming message
        ▼
Apps Script /webhook endpoint OR small FastAPI service
        │   appends raw message to "WhatsApp_Inbox" tab in Family_OS
        ▼
Hourly Cowork scheduled task: classify each new message
   ├── ROUTINE → mark digested=false, group_summary=null
   ├── DIGEST  → write a one-line summary
   └── ALERT   → queue to the Baileys outbox; bridge delivers 1:1 (decision 2026-06-04)
        │
        ▼
Daily 07:30 task: build digest from previous 24h of DIGEST + ROUTINE-with-1-liner items,
prepend to the morning briefing.
```

## Provider choice — read this before building

Twilio's official WhatsApp API **does not give you read access to groups you didn't initiate**. To read incoming group messages, you need an unofficial WhatsApp Web bridge. Options, ranked:

| Option | Pricing | Pros | Cons |
|---|---|---|---|
| **Baileys on dedicated Android (self-hosted)** ⭐ recommended | ₪400 one-time (cheap second Android) + free software + ~₪0 power | **Plaintext group messages never leave your home Wi-Fi.** Total control. Maintenance is "phone stays plugged in." | One evening to set up; breaks occasionally on WA protocol updates |
| **Whapi.cloud** | $39/mo | Fastest to ship; Hebrew docs; group support out of the box | **Every group message in plaintext goes to a third-party cloud.** Acceptable for daycare/building groups; risky for the family group |
| **Green API** | $20/mo | Cheapest hosted option, popular in Israel | Russian-owned; same plaintext-to-third-party concern as Whapi |
| **Wasender** | $25/mo | Hebrew support team | Same third-party concern; less mature than Whapi |

**Recommended path — privacy-first:** stand up **Baileys on a cheap dedicated Android phone** sitting on your home Wi-Fi. The phone runs nothing else, stays plugged in, has its own WhatsApp account paired as a "WhatsApp Web" companion to Adar's main number. All group messages stay in your house; only the LLM classification request leaves (to Claude, with one message at a time, no thread context shared beyond 3 messages). This is the right answer for household-grade privacy.

**Fallback path — speed-first:** if the dedicated-phone route feels like too much hardware management, **Whapi.cloud** ships the same feature in one afternoon with the explicit trade that plaintext family-group messages transit a commercial third party. Acceptable if you scope the connector to *only* the daycare and building groups and exclude the family group entirely.

⚠ All these solutions work by pairing a phone — same QR-code flow as WhatsApp Web. They're widely used but technically against WhatsApp's ToS for high-volume commercial use. For household use, the risk profile is the same as running WhatsApp Web on a laptop.

## Data model — new Family_OS tab

**`WhatsApp_Inbox`** (append-only, one row per incoming group message):

| column | type | notes |
|---|---|---|
| msg_id | string | provider-supplied unique ID |
| group_name | string | e.g. "גן עידן הורים תשפ\"ז" |
| group_type | enum | `daycare`, `building`, `family`, `neighborhood`, `other` |
| sender_name | string | as shown in WA |
| sender_role | string | `teacher`, `vaad_bayit`, `parent_close`, `parent_distant`, `family`, `unknown` |
| received_at | datetime IL | |
| text | string | message body (Hebrew + English) |
| has_media | bool | |
| classification | enum | `ROUTINE`, `DIGEST`, `ALERT` |
| one_liner | string | LLM-generated summary (≤120 chars) |
| action_required | bool | |
| action_owner | enum | `adar`, `shanee`, `both`, `none` |
| digested_at | datetime | when included in a digest |

Plus **`WhatsApp_Group_Config`** (manual seed):

| column | type |
|---|---|
| group_name | string |
| group_type | enum (`daycare`, `building`, `family`, `neighborhood`, `student`, `other`) |
| importance_default | enum (`alert_eligible`, `digest_only`, `mute`) |
| alert_recipients | enum (`both`, `adar`, `shanee`, `none`) — **who an ALERT from this group is sent to** (added 2026-06-02; see "Per-group alert routing") |
| close_contacts | list — messages from these always upgrade by one tier. `;`-separated in the CSV |
| alert_keywords | list of regex, `;`-separated in the CSV (e.g. `מחר.*גן`, `מתחילים ב[\\d:]+`) — budget-bound alerts |
| critical_keywords | list of regex — safety/emergency matches (e.g. `חירום`, `הגן סגור`, `מים סגורים`, `אשפוז`) that **bypass the 2/day budget** (added post-Gemini-review 2026-06-02) |

Seed lives at `Setup/12_WhatsApp_Group_Config_Seed.csv`.

### Per-group alert routing (decision 2026-06-02, Adar)

Alert routing is **per group**, not global — relevance depends on the group:

| group | importance_default | alert_recipients |
|---|---|---|
| daycare (`גן עידן`) | alert_eligible | **both** |
| building (`ועד הבית`) | alert_eligible | **both** |
| student (`סטודנטים`) | digest_only | **adar** |
| neighborhood | digest_only | **none** (digest only) |
| family | digest_only | **none** (digest only) |

A group with `alert_recipients = none` never sends a real-time WhatsApp alert. If a
hard rule still classifies one of its messages as ALERT (e.g. an emergency keyword in
the family group), the engine does **not** silently swallow it — it floats to a
`⚠ NEEDS A LOOK` block at the top of the daily digest instead of pinging anyone.

## Classification policy

Each incoming message → Claude Haiku 4.5 (cheap) given:
- The group's `group_type` and `importance_default`
- Whether sender is in `close_contacts`
- The message text
- Last 3 messages in the same group (thread context)

Prompt outputs JSON: `{classification, one_liner, action_required, action_owner, reason}`.

**Hard rules that override the LLM:**

1. If message matches any `alert_keywords` regex → upgrade to ALERT minimum.
2. If sender_role = `teacher` AND group_type = `daycare` AND it's between 18:00–08:00 → ALERT (typically "tomorrow bring X").
3. If sender_role = `vaad_bayit` AND text contains "מים" / "חשמל" / "תיקון" / "מעלית" → ALERT.
4. If the message is a media-only message (photo/video) with no caption → ROUTINE (no LLM call).
5. If group is in `mute` state → never alert, only digest.

**Budget (tiered — revised post-Gemini-review 2026-06-02):** standard alerts from
WhatsApp groups share the existing 2/day cap; if the cap is hit, downgrade to DIGEST
and log "alert suppressed by budget." **`critical_keywords` matches bypass the cap**
(unlimited safety tier) — a daycare emergency at 16:00 must never be trapped in
tomorrow's digest because two mundane alerts fired in the morning. Critical alerts
don't consume the standard budget. The calm principle holds because critical
patterns are narrow (emergencies, closures, water/power cuts), not "important."

## Archive policy (revised 2026-05-30)

Two tabs, two retention policies:

**`WhatsApp_Inbox`** — operational hot table.
- Columns include `classification`, `action_required`, `action_owner`, `digested_at` (the noisy metadata).
- Rolls off after 90 days.

**`WhatsApp_Archive`** — long-term searchable record.
- Columns: `msg_id`, `group_name`, `sender_name`, `received_at`, `text` (raw), `one_liner` (LLM-generated).
- **Never rolls off.** Lets you query "when did vaad announce the elevator maintenance?" 6 months later.
- Append-only; written by the same hourly classifier task that updates `WhatsApp_Inbox`.

The long-term archive is text-only (no media references, no classification metadata) so it stays small — at 200 msg/day, the archive grows ~5MB/year. Trivial.

## Cost ceiling

At ~200 messages/day across all groups, Haiku at $1/M input + $5/M output, average ~200 input tokens + 80 output tokens per classification → **~$0.30/day, ~$9/month**. Acceptable.

Plus bridge:
- **Baileys on dedicated Android** (recommended) → ~₪400 one-time, ~₪0/month ongoing → **~$9/month** all-in
- **Whapi.cloud** (fallback) → $39/mo → **~$48/month** all-in

Both pay off if the feature kills the "I missed it on the parent chat" problem even once a month.

## Daily digest format (delivered with morning briefing)

```
WhatsApp groups (last 24h)
─────────────────────────
DAYCARE
  • Tomorrow: snack day — bring fruit (teacher, 22:14)
  • Friday party 16:00, parents invited (teacher, 14:02)

BUILDING
  • Elevator maintenance Thu 09:00–12:00 (vaad, 11:30)

FAMILY
  • Mom shared kid-1's swimming photos (digest only)
  • Cousin's bar mitzvah save-the-date — June 14 (Liora, 19:45)

NEIGHBORHOOD
  • 1 babysitter recommendation (Idan, 20:11)

3 alerts fired today · 7 messages digested
```

## Build phases

| Phase | Deliverable | Status |
|---|---|---|
| **A** | Bridge appends to inbox. **Built as self-hosted Baileys** (`whatsapp_bridge/baileys_listener.js`) → `inbox/whatsapp_inbox.jsonl`, not a cloud webhook. Awaits one-time QR pairing on an always-on machine. | ✅ built (mock-tested; needs pairing) |
| **B** | Manual seed of `WhatsApp_Group_Config` | ✅ `Setup/12_WhatsApp_Group_Config_Seed.csv` (5 groups, per-group routing) |
| **C** | Classifier (Claude Haiku) writes `classification` + `one_liner` | ✅ `whatsapp_summarizer.py` (deterministic fallback when no API key) |
| **D** | Hard-rule overrides + budget-aware alert dispatch | ✅ all 5 hard rules + 2/day budget + per-group routing |
| **E** | Daily digest | ✅ `Briefings/whatsapp_digest_YYYY-MM-DD.md` |
| **F** | Weekly review surface — accuracy tuning, false-positive purge | ⬜ not built |

**Built 2026-06-02 in mock mode; send path closed 2026-06-04.** `dispatch_alert()` now
queues to `Automation/outbox/whatsapp_outbox.jsonl` via `wa_outbox.py`; the bridge polls
every 15s and delivers, deduping per (id, target) against a sent ledger. Two things stand
between this and live: (1) pair the Baileys listener once on an always-on machine;
(2) drop `recipients.json` (adar/shanee JIDs) next to `auth_state/`. No Twilio anywhere.

## What's out of scope

- **No replying into groups.** The system never posts to any group. (Scope narrowed 2026-06-04: the bridge does send 1:1 alerts/briefings to Adar and Shanee only — hard scope guard in `recipients.json` + code-side refusal of any other target. Groups stay read-only forever.)
- **No 1:1 chat reading.** Groups only.
- **Inbox metadata caps at 90 days; raw text + summary archive forever.** See "Archive policy" below — the 90-day rolloff was the original design but lost real value (vaad maintenance history, daycare announcements). Revised after 2026-05-30 Gemini review.
- **No kid-facing surface.** Standing principle.
- **No sharing with third parties.** Classification runs Claude → output only goes to the family Sheet.

## Privacy

- **Bridge choice is a privacy decision.** Baileys-on-Android keeps plaintext in your house; Whapi.cloud routes everything through a commercial third party. Pick before turning on.
- Family-group messages contain personal context — keep the LLM prompts short (no system-wide context leak); only the message + 3 prior messages of the same group go to Claude per classification call.
- `WhatsApp_Inbox` metadata rolls off at 90 days; `WhatsApp_Archive` retains raw text + summary indefinitely.
- Never store media (photos/videos) — only the fact that media existed.
- Tell Shanee explicitly before turning on, regardless of bridge choice.

## Open decisions for Adar — RESOLVED 2026-06-02

1. ~~**Bridge:**~~ → **Self-hosted Baileys** (free). "Anything that is free." Runs on an always-on laptop / Pi / old phone on home Wi-Fi; plaintext stays in the house.
2. ~~**Which groups?**~~ → **daycare, building, neighborhood, family, student** all seeded. Family group is in (safe on the self-hosted bridge — would have stayed OUT only on Whapi).
3. ~~**Alert routing:**~~ → **Per group** (see "Per-group alert routing"): daycare + building → both; student → Adar; neighborhood + family → digest only.

### Still open (surfaced during the build)

- ~~**Budget priority.**~~ → RESOLVED 2026-06-02 by the tiered budget: `critical_keywords` bypass the 2/day cap, so emergencies can't be crowded out by mundane alerts. Mid-tier ranking (elevator vs. student deadline within the standard budget) remains first-come-first-served; acceptable for v1.
- **Role detection.** `sender_role` (teacher / vaad_bayit) is provided in mock data but in production needs a sender→role roster to make hard rules 2–3 fire reliably. Until seeded, those two rules only trigger when role is known; the keyword rules carry the load.
- **Family-group criticals (PO call needed).** Family is `alert_recipients = none`, so even a critical match (אשפוז, חירום) only floats to the digest's "⚠ NEEDS A LOOK" block — it never pings. Should true emergencies in the family group override the digest-only routing? Adar + Shanee to decide jointly (changes a shipped routing decision).

## Verify it worked (after phase D)

- [ ] A message in daycare group with "מחר" + a time triggers an ALERT within 10 min.
- [ ] A meme in the family group results in no notification.
- [ ] Daily digest at 07:30 contains a "WhatsApp groups" section.
- [ ] Sunday review shows >80% of classifications were correct (manual spot-check on 20 messages).
- [ ] False-positive rate on ALERT tier is <1 per week.

Related: [[06_Lift_Recommendations_2026-05-30]] · [[02_Reminders_Engine_Spec]] · [[00_Architecture_and_Roadmap]]

---

## Reviewed by Gemini 2026-05-30

**Applied:** (a) Self-hosted Baileys on a dedicated cheap Android phone promoted to **recommended** path; Whapi.cloud demoted to fast-path fallback with explicit "family group OUT if on Whapi" guidance. (b) Archive policy split: `WhatsApp_Inbox` metadata rolls off at 90d as before; new `WhatsApp_Archive` tab retains raw text + LLM summary indefinitely so historical queries (vaad maintenance, daycare announcements) work. (c) Open decisions list trimmed and reordered around the bridge call.

**Defended:** None.

**Open:** Bridge choice (Baileys vs Whapi) — moved to top of Open decisions for Adar.

**Tradeoffs accepted:** ongoing Android-phone maintenance vs $39/mo Whapi convenience; ~5MB/year archive growth vs perfect data hygiene.

---

## Reviewed by Gemini 2026-06-02 — Resolved (build session)

**Applied:**
- **Tiered alert budget** — new `critical_keywords` config column; safety/emergency matches bypass the 2/day cap (Gemini concern 3 / suggestion 2). Verified in mock: a 15:00 "הגן סגור" critical fires after the budget is exhausted.
- **Bridge health surfacing** (Gemini's one question) — listener writes `inbox/heartbeat.txt` on connect + every message + 15-min idle timer (timer stops on disconnect so a dead bridge looks dead); `whatsapp_summarizer.py` prepends a "⚠ BRIDGE SILENT Nh" warning to the digest when the heartbeat is >12h stale.

**Defended (with reason):**
- **Baileys over a managed API** (concern 1 / alternative 1): managed WhatsApp APIs (Twilio, Cloud API) cannot read groups you didn't initiate — that limitation is the entire reason this spec needs a bridge (§Provider choice). Whapi was explicitly declined by Adar ("anything that is free") and routes family-group plaintext through a third party. Fragility is real; it's mitigated by the heartbeat + digest warning, and the failure mode is now loud, not silent.
- **Local CSV staging** (concern 2 / alternative 2): Family_OS (Sheets) remains the master DB. The CSVs are an interim pre-credentials buffer — the same posture as `reminders_engine.py`'s email fallback before Twilio. Nothing else reads them, so no second source of truth exists in practice. TODO(gspread) marked in code; direct Sheets writes land when `FAMILY_INC_SHEET` creds are wired.
- **JSONL over SQLite** (concern 4 / alternative 4): single writer (atomic line appends) + single reader that rereads the whole file each run and dedups by `msg_id` makes torn writes self-healing — a corrupt tail line is skipped this run and picked up complete next run. SQLite adds a dependency without removing a failure mode at ~200 msg/day.

**Open:** Family-group criticals — should an emergency keyword in the digest-only family group override `alert_recipients = none` and actually ping? Joint PO call (changes shipped routing); logged under "Still open."

**Tradeoffs accepted:** critical keywords are regex, so a sloppy pattern could leak mundane messages past the budget — patterns kept narrow (emergencies/closures/utilities) and reviewed in Phase F; 12h staleness threshold may false-positive on a genuinely silent day (Yom Kippur) — tunable constant.

=== End: 07_WhatsApp_Group_Summarizer_Spec.md ===

=== File: Automation/wa_outbox.py ===
"""
Family inc. — WhatsApp outbox writer (Baileys-first delivery).

Decision 2026-06-04 (Adar): alerts + briefings go out through the self-hosted
Baileys bridge, NOT Twilio. Every automation that wants to send a WhatsApp
message calls queue_message() here; the bridge (whatsapp_bridge/
baileys_listener.js) polls the outbox and delivers within ~15s.

Contract
--------
Outbox file:  Automation/outbox/whatsapp_outbox.jsonl
Row:          {"id": uuid, "to": "adar"|"shanee"|"both", "body": str,
               "source": str, "queued_at": iso8601}
Sent ledger:  Automation/outbox/whatsapp_sent.jsonl (bridge-written; one row
              per (id, target): status sent | refused_unknown_recipient)

Delivery guarantee is at-least-once from this side's perspective: the queue is
durable on disk, the bridge dedups per (id, target) against the sent ledger.
If the bridge machine is down, rows wait. Callers that care should check
bridge_alive() and surface a warning instead of assuming delivery.

The 2/day alert BUDGET is NOT enforced here — it stays with the callers
(reminders engine, whatsapp_summarizer), same as in the Twilio design.
Briefings are exempt from the budget by principle ("briefings > notifications").
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTBOX_DIR = ROOT / "outbox"
OUTBOX_FILE = OUTBOX_DIR / "whatsapp_outbox.jsonl"
SENT_FILE = OUTBOX_DIR / "whatsapp_sent.jsonl"
HEARTBEAT_FILE = ROOT / "inbox" / "heartbeat.txt"

VALID_RECIPIENTS = {"adar", "shanee", "both"}
STALE_AFTER = timedelta(minutes=45)  # heartbeat is written at least every 15m


def queue_message(to: str, body: str, source: str = "unknown") -> str:
    """Append one message to the outbox. Returns the message id.

    `to` must be adar/shanee/both — anything else raises here, and the bridge
    refuses it again on its side (defense in depth).
    """
    if to not in VALID_RECIPIENTS:
        raise ValueError(f"recipient must be one of {VALID_RECIPIENTS}, got {to!r}")
    if not body or not body.strip():
        raise ValueError("empty message body")
    OUTBOX_DIR.mkdir(exist_ok=True)
    msg_id = str(uuid.uuid4())
    row = {
        "id": msg_id,
        "to": to,
        "body": body.strip(),
        "source": source,
        "queued_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with OUTBOX_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return msg_id


def bridge_alive(now: datetime | None = None) -> bool:
    """True if the bridge heartbeat is fresh. Callers surface a warning when
    False — queued messages will still go out when the bridge returns."""
    try:
        ts = datetime.fromisoformat(HEARTBEAT_FILE.read_text().strip().replace("Z", "+00:00"))
    except (OSError, ValueError):
        return False
    now = now or datetime.now(ts.tzinfo)
    return (now - ts) <= STALE_AFTER


def delivery_status(msg_id: str) -> list[dict]:
    """Sent-ledger rows for one message id (one per target). Empty = pending."""
    if not SENT_FILE.exists():
        return []
    rows = []
    for line in SENT_FILE.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("id") == msg_id:
            rows.append(row)
    return rows


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] in VALID_RECIPIENTS:
        mid = queue_message(sys.argv[1], " ".join(sys.argv[2:]), source="cli")
        alive = bridge_alive()
        print(f"queued {mid} → {sys.argv[1]} (bridge {'alive' if alive else 'DOWN — will send on reconnect'})")
    else:
        print("usage: python wa_outbox.py adar|shanee|both <message text>")

=== End: Automation/wa_outbox.py ===

=== File: Automation/whatsapp_bridge/baileys_listener.js ===
/**
 * Family inc. — WhatsApp group listener (self-hosted, free bridge)
 *
 * Pairs as a WhatsApp Web "companion" to Adar's main number using Baileys
 * (the same QR-code flow as web.whatsapp.com). Two jobs:
 *
 * 1. LISTEN — group messages ONLY, normalized into the WhatsApp_Inbox schema,
 *    appended as JSON lines to ../inbox/whatsapp_inbox.jsonl.
 * 2. SEND — polls ../outbox/whatsapp_outbox.jsonl (written by the Python
 *    automations: reminders engine, briefings, whatsapp_summarizer alerts)
 *    and delivers each queued message to Adar/Shanee 1:1. Decision
 *    2026-06-04 (Adar): Baileys-first delivery, Twilio not provisioned.
 *
 * SEND SCOPE GUARD: outbound goes ONLY to the recipients named in
 * ./recipients.json ({"adar": "9725...@s.whatsapp.net", "shanee": ...}).
 * That file lives next to auth_state/ on the bridge machine and is never
 * committed. Any outbox row addressed to anyone else is refused and logged.
 *
 * Nothing leaves the machine. The Python classifier (whatsapp_summarizer.py)
 * reads the JSONL file on its hourly run. This is the privacy-first path from
 * 07_WhatsApp_Group_Summarizer_Spec.md — plaintext stays in the house.
 *
 * COST: free software. Runs on any old Android-via-Termux, a Raspberry Pi,
 * an always-on laptop, or a cheap second phone. ~₪0/month.
 *
 * --- Setup ---
 *   cd Automation/whatsapp_bridge
 *   npm install
 *   node baileys_listener.js            # scan the QR with Adar's phone once
 *   # auth persists in ./auth_state/ ; restart resumes without re-scanning
 *
 * --- Scope guard ---
 * Reads GROUPS ONLY (jid ends in @g.us). 1:1 chats (@s.whatsapp.net) are
 * dropped before any processing — matches the spec's "No 1:1 chat reading."
 * Media bodies are never stored; only has_media=true is recorded.
 */

const fs = require('fs');
const path = require('path');
const P = require('pino');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');

const ROOT = __dirname;
const AUTH_DIR = path.join(ROOT, 'auth_state');
const INBOX_DIR = path.join(ROOT, '..', 'inbox');
const INBOX_FILE = path.join(INBOX_DIR, 'whatsapp_inbox.jsonl');
const HEARTBEAT_FILE = path.join(INBOX_DIR, 'heartbeat.txt');
const OUTBOX_DIR = path.join(ROOT, '..', 'outbox');
const OUTBOX_FILE = path.join(OUTBOX_DIR, 'whatsapp_outbox.jsonl');
const SENT_FILE = path.join(OUTBOX_DIR, 'whatsapp_sent.jsonl');
const RECIPIENTS_FILE = path.join(ROOT, 'recipients.json'); // never committed
const OUTBOX_POLL_MS = 15 * 1000;

fs.mkdirSync(INBOX_DIR, { recursive: true });
fs.mkdirSync(OUTBOX_DIR, { recursive: true });

// Heartbeat: whatsapp_summarizer.py checks this file's timestamp and surfaces a
// "bridge may be down" warning in the daily digest when it goes stale.
// Written on connect + every message + every 15 min while connected.
function beat() {
  try { fs.writeFileSync(HEARTBEAT_FILE, new Date().toISOString(), 'utf-8'); } catch (e) { /* noop */ }
}

const logger = P({ level: 'warn' });

// In-memory cache of group subject lookups so we don't spam metadata calls.
const groupNameCache = new Map();

function isGroup(jid) {
  return typeof jid === 'string' && jid.endsWith('@g.us');
}

// Pull the human-readable body out of the many WA message shapes.
function extractText(msg) {
  const m = msg.message || {};
  return (
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.imageMessage?.caption ||
    m.videoMessage?.caption ||
    m.documentMessage?.caption ||
    ''
  ).trim();
}

function hasMedia(msg) {
  const m = msg.message || {};
  return Boolean(
    m.imageMessage || m.videoMessage || m.audioMessage ||
    m.stickerMessage || m.documentMessage,
  );
}

function appendInbox(row) {
  fs.appendFileSync(INBOX_FILE, JSON.stringify(row) + '\n', 'utf-8');
}

// --- Outbound (Baileys-first delivery, decision 2026-06-04) ----------------

function loadRecipients() {
  try {
    const r = JSON.parse(fs.readFileSync(RECIPIENTS_FILE, 'utf-8'));
    // hard scope guard: exactly these two logical names, 1:1 JIDs only
    const out = {};
    for (const name of ['adar', 'shanee']) {
      if (typeof r[name] === 'string' && r[name].endsWith('@s.whatsapp.net')) {
        out[name] = r[name];
      }
    }
    return out;
  } catch (e) {
    return null; // missing/invalid -> sending disabled, listening unaffected
  }
}

function readJsonl(file) {
  if (!fs.existsSync(file)) return [];
  return fs.readFileSync(file, 'utf-8')
    .split('\n')
    .filter(Boolean)
    .map((l) => { try { return JSON.parse(l); } catch (e) { return null; } })
    .filter(Boolean);
}

let outboxBusy = false;
async function processOutbox(sock) {
  if (outboxBusy) return; // don't overlap polls
  outboxBusy = true;
  try {
    const recipients = loadRecipients();
    const pending = readJsonl(OUTBOX_FILE);
    if (!pending.length) return;
    if (!recipients || !Object.keys(recipients).length) {
      console.log('[outbox] recipients.json missing/invalid — sending disabled');
      return;
    }
    // dedup per (id, target) so a crash mid-"both" still delivers the second leg
    const done = new Set(readJsonl(SENT_FILE).map((r) => `${r.id}:${r.to}`));
    for (const row of pending) {
      if (!row.id) continue;
      const targets = row.to === 'both' ? ['adar', 'shanee'] : [row.to];
      for (const name of targets) {
        if (done.has(`${row.id}:${name}`)) continue;
        const jid = recipients[name];
        if (!jid) { // scope guard: refuse anything not adar/shanee
          fs.appendFileSync(SENT_FILE, JSON.stringify({
            id: row.id, to: name, status: 'refused_unknown_recipient',
            at: new Date().toISOString(),
          }) + '\n', 'utf-8');
          console.log(`[outbox] REFUSED ${row.id} → "${name}" (not a configured recipient)`);
          continue;
        }
        await sock.sendMessage(jid, { text: String(row.body || '').slice(0, 4096) });
        fs.appendFileSync(SENT_FILE, JSON.stringify({
          id: row.id, to: name, status: 'sent', at: new Date().toISOString(),
        }) + '\n', 'utf-8');
        console.log(`[outbox] sent ${row.id} → ${name}`);
        done.add(`${row.id}:${name}`);
      }
    }
  } catch (e) {
    console.log('[outbox] error (will retry next poll):', e.message || e);
  } finally {
    outboxBusy = false;
  }
}

async function resolveGroupName(sock, jid) {
  if (groupNameCache.has(jid)) return groupNameCache.get(jid);
  try {
    const meta = await sock.groupMetadata(jid);
    groupNameCache.set(jid, meta.subject || jid);
    return meta.subject || jid;
  } catch (e) {
    return jid;
  }
}

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
    logger,
    printQRInTerminal: true, // scan once with Adar's phone -> Linked devices
    markOnlineOnConnect: false, // stay invisible except when delivering outbox
    syncFullHistory: false,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (u) => {
    const { connection, lastDisconnect } = u;
    if (connection === 'open') {
      console.log('[baileys] connected — listening to GROUP messages; outbox sender armed');
      beat();
      processOutbox(sock); // flush anything queued while we were down
      if (!global._beatTimer) {
        global._beatTimer = setInterval(beat, 15 * 60 * 1000); // idle heartbeat
      }
      if (!global._outboxTimer) {
        global._outboxTimer = setInterval(() => processOutbox(sock), OUTBOX_POLL_MS);
      }
    } else if (connection === 'close') {
      // stop the timers so a dead bridge actually LOOKS dead (and can't "send")
      if (global._beatTimer) { clearInterval(global._beatTimer); global._beatTimer = null; }
      if (global._outboxTimer) { clearInterval(global._outboxTimer); global._outboxTimer = null; }
      const code = lastDisconnect?.error?.output?.statusCode;
      const loggedOut = code === DisconnectReason.loggedOut;
      console.log(`[baileys] connection closed (code ${code}); ${loggedOut ? 'logged out — delete auth_state and re-pair' : 'reconnecting…'}`);
      if (!loggedOut) start();
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    beat();
    if (type !== 'notify') return; // ignore history backfill
    for (const msg of messages) {
      try {
        const jid = msg.key?.remoteJid;
        if (!isGroup(jid)) continue;       // GROUPS ONLY
        if (msg.key?.fromMe) continue;     // ignore our own sends

        const text = extractText(msg);
        const media = hasMedia(msg);
        if (!text && !media) continue;     // nothing to record

        const groupName = await resolveGroupName(sock, jid);
        const senderJid = msg.key?.participant || jid;
        const senderName = msg.pushName || senderJid.split('@')[0];
        const tsSec = Number(msg.messageTimestamp) || Math.floor(Date.now() / 1000);

        appendInbox({
          msg_id: msg.key?.id,
          group_jid: jid,
          group_name: groupName,
          sender_jid: senderJid,
          sender_name: senderName,
          received_at: new Date(tsSec * 1000).toISOString(),
          text: media && !text ? '' : text, // never store media body
          has_media: media,
        });
        console.log(`[inbox] ${groupName} | ${senderName}: ${(text || '[media]').slice(0, 60)}`);
      } catch (e) {
        logger.warn({ e }, 'failed to process message');
      }
    }
  });
}

start().catch((e) => {
  console.error('[baileys] fatal', e);
  process.exit(1);
});

=== End: Automation/whatsapp_bridge/baileys_listener.js ===

=== File: Automation/whatsapp_bridge/README.md ===
# WhatsApp bridge — self-hosted, free

The privacy-first bridge from `07_WhatsApp_Group_Summarizer_Spec.md`. Plaintext
group messages never leave the machine; only the Python classifier's per-message
LLM call leaves the house.

## What it does

Pairs as a WhatsApp Web **companion** to Adar's main number (same QR flow as
web.whatsapp.com → Linked devices). Two jobs:

1. **Listen** — group messages only; drops 1:1 chats and media bodies, appends
   each message as one JSON line to `../inbox/whatsapp_inbox.jsonl`.
   `whatsapp_summarizer.py` reads that file.
2. **Send** (added 2026-06-04, Baileys-first decision — Twilio dropped) — polls
   `../outbox/whatsapp_outbox.jsonl` every 15s and delivers each queued row 1:1
   to Adar/Shanee. Python side queues via `Automation/wa_outbox.py`. Delivery is
   recorded per (id, target) in `../outbox/whatsapp_sent.jsonl` (dedup ledger).

## recipients.json (required for sending)

Create next to `auth_state/` on the bridge machine — **never commit**:

```json
{
  "adar":   "9725XXXXXXXX@s.whatsapp.net",
  "shanee": "9725XXXXXXXX@s.whatsapp.net"
}
```

Sending is disabled (listening unaffected) if the file is missing. Any outbox
row addressed to anyone other than these two is refused and logged — that is
the "no messages outside Adar+Shanee" principle enforced in code.

## Run it (one-time pair, then leave running)

```bash
cd Automation/whatsapp_bridge
npm install
node baileys_listener.js     # scan the QR with Adar's phone (Linked devices)
```

Auth persists in `./auth_state/` — restart resumes without re-scanning.

## Where to host (all free)

- An always-on laptop or a Raspberry Pi on home Wi-Fi.
- A cheap second Android via Termux (`pkg install nodejs`).
- Any old phone kept plugged in running nothing else.

Keep it on the home network and the messages stay in the house.

## Notes / caveats

- **Groups are read-only forever** — the bridge never posts to a group. Outbound
  is 1:1 to the two configured recipients only.
- Unofficial WhatsApp Web automation is technically against WhatsApp ToS for
  high-volume commercial use; household volume (a few messages/day, person-to-
  person pattern) keeps the risk profile close to WhatsApp Web on a laptop.
  Sending raises it slightly vs read-only — accepted tradeoff (06-doc 2.5).
- If the bridge machine is down, outbox rows wait on disk and flush on
  reconnect; callers can check staleness via `wa_outbox.bridge_alive()`.
- If it logs out (code 401), delete `auth_state/` and re-pair.
- `auth_state/`, `inbox/`, `outbox/`, `recipients.json`, and `node_modules/`
  are git-ignored — never commit session credentials, numbers, or content.

=== End: Automation/whatsapp_bridge/README.md ===

=== File: 02_Reminders_Engine_Spec.md ===
# Family inc. — Reminders Engine (Phase 2 spec)

*Companion to `00_Architecture_and_Roadmap.md`. Living document.*

Last updated: 2026-05-27

---

## Purpose

One automation owns the entire "did we drop the ball?" surface of Family inc. It reads the **Reminders** tab of the master Sheet, decides what needs to fire today, and sends at most a few WhatsApp messages. Every domain (Car, Health, Education, Contracts, …) writes into the Reminders tab — nothing fires from anywhere else.

This is the keystone. Get this right and the rest of the system is plumbing.

---

## Inputs

### From the master Sheet — `Reminders` tab

Authoritative columns the engine reads:

| Col | Field | Notes |
|---|---|---|
| A | Title | Short, human-readable. Used verbatim in WhatsApp. |
| B | Domain | Validated dropdown (Calendar / Finance / … ) |
| C | Owner | Adar / Partner / Both / Child / System |
| D | Due Date | Real date. Anchors all lead-time math. |
| E | Lead Times (days) | Comma-separated, e.g. `60,30,7,1`. Each integer = one fire opportunity. |
| F | Recurrence | One-off / Yearly / Monthly / … — after Due Date passes, the engine bumps it. |
| G | Status | Pending / Snoozed / Sent / Done / Skipped / Overdue |
| H | Last Sent | Last datetime the engine sent a message for this row. |
| I | Channel | WhatsApp / Email / None |
| J | Notes | Free text. Appended to the WhatsApp message if short. |

Engine-derived helper columns (already added in the hardened sheet):

| Col | Field | Formula |
|---|---|---|
| K | Days until | `=D−TODAY()` |
| L | Auto-flag | `OVERDUE` / `FIRE TODAY` / `WEEK OUT` / `MONTH OUT` / blank |

Phase 6.1 columns (added 2026-05-30 for the dashboard's offline-queue race guard):

| Col | Field | Notes |
|---|---|---|
| M | LastDoneBy | Name of whoever marked Done. Set by dashboard write-back. |
| N | DoneAt | ISO datetime the dashboard recorded the completion. Engine uses it for the rolling 7-day count surfaced in the dashboard arc. |
| O | WriteQueue_Tombstone | ISO datetime stamped on every dashboard write (including the flush of a queued offline tap). **Engine reads this on startup and skips any row whose tombstone is within the last 6 hours.** Prevents the "engine fires before the queued completion flushes" race. |

### From config (constants in code, not the Sheet)

- `DAILY_RUN_TIME` = 07:30 local (Asia/Jerusalem)
- `ALERT_BUDGET_PER_DAY` = 2 messages per recipient (hard cap)
- `QUIET_HOURS` = 22:00–07:00 — no messages sent inside this window even if budget allows
- `BATCH_WINDOW_MINUTES` = 5 — multiple fires within this window are merged into one message
- `OVERDUE_REPEAT_DAYS` = 3 — an overdue item re-fires at most every 3 days
- `TOMBSTONE_SKIP_HOURS` = 6 — skip any row whose `WriteQueue_Tombstone` is within this window (the offline-queue race guard; tunable)

---

## The daily run

Triggered by a Cowork scheduled task at 07:30 local.

```
1. Refresh Reminders tab (read from Google Sheets API)
2. For each row where Status ∈ {Pending, Snoozed, Overdue}:
     a. TOMBSTONE GUARD (Phase 6.1):
        if WriteQueue_Tombstone is not blank AND
           (now − WriteQueue_Tombstone) < TOMBSTONE_SKIP_HOURS:
          → SKIP this row this run
          → log entry "skipped_due_to_tombstone" with row id + tombstone age
          → continue to next row
        (Rationale: the dashboard wrote — or is about to flush a queued write —
        within the last 6h. The row state we're reading may already be stale.
        Better to wait one cycle than re-alert something already closed.)
     b. compute days_until = Due Date − today
     c. determine fire reason:
          - OVERDUE                if days_until < 0 and (today − Last Sent) >= OVERDUE_REPEAT_DAYS
          - LEAD-TIME HIT          if days_until ∈ Lead Times (e.g. exactly 30, 7, or 1)
          - DUE TODAY              if days_until == 0
          - otherwise skip
3. Group fires by recipient (per Owner → WhatsApp number map)
4. For each recipient:
     a. Apply alert budget (see "Alert budget" below)
     b. Render the digest message (see "Message templates")
     c. Send via the Baileys outbox (`Automation/wa_outbox.queue_message()` — decision 2026-06-04, Twilio dropped)
     d. On success: stamp Last Sent = now, Status = Sent (or Overdue if still past due)
5. Update Goals.LastUpdate "system_reminders_run" to now (heartbeat)
6. Write a one-line entry to /Briefings/reminders_log.csv (date, fires, sent, skipped_due_to_budget, skipped_due_to_tombstone)
```

**Residual race the tombstone guard doesn't cover:** if a phone is offline for more than 6 hours with a queued completion, the tombstone hasn't been written yet (it's set on flush, not on tap). Engine may then send one extra alert before the queue flushes. Acceptable trade for household scale; window is tunable via `TOMBSTONE_SKIP_HOURS`. Worth widening to 12h if the dashboard's queue-flush time turns out to vary widely with morning connectivity.

### Escalation tiers

Lead Times in column E are the only place tiers are defined — per row. Suggested defaults:

| Domain | Default lead times | Why |
|---|---|---|
| Car (annual test, insurance) | `60, 30, 7, 1` | Catastrophic if missed, but bookable months ahead |
| Contracts (renewals) | `45, 14, 1` | Enough runway to shop alternatives |
| Health (annual checkups, vaccines) | `30, 7, 1` | Provider lead time is usually 1–2 weeks |
| Education (registry, parent-teacher) | `30, 14, 7, 1` | Hard deadlines, often immovable |
| Finance (bill due, CSV import) | `7, 1` | Short cycle, monthly cadence |
| Goals (90-day milestone check) | `14, 1` | Soft deadlines; nudge, don't nag |
| One-off / Other | `7, 1` | Safe default |

Owners can override per row in column E.

### Recurrence handling

When `Status` flips to `Done`, the engine looks at `Recurrence`:

| Recurrence | Action on completion |
|---|---|
| One-off | Status stays Done; row is archived to a `Reminders-Archive` tab on the 1st of next month |
| Yearly / Monthly / Quarterly / Weekly / Daily | `Due Date += period`, `Status → Pending`, `Last Sent → blank` |
| Custom | Engine flags row for human review (sends a message: "this one needs your re-scheduling") |

---

## Alert budget

The hard cap is 2 WhatsApp messages per recipient per day. Enforced in this order:

1. **Coalesce first.** All fires for one recipient in one daily run produce **one** digest message, not N messages. This is the main reason the budget rarely bites.
2. **Within-day re-fires.** If a non-scheduled fire happens later (e.g. an emergency on-demand reminder added manually), it counts as message #2. Anything beyond #2 is queued for tomorrow.
3. **Priority order** when trimming:
   - Always include: OVERDUE, FIRE TODAY, Domain = Health for kids
   - Bumpable: WEEK OUT, MONTH OUT
   - Dropped first: notes-only reminders, Domain = Goals (these get the Friday report instead)
4. **Quiet hours win.** If the daily run is delayed past 22:00 (rare), the digest is held until 07:00.
5. **Audit trail.** Every coalesced/dropped fire is written to `/Briefings/reminders_log.csv` with reason — so we can tell if the budget is too tight.

If the log shows >10% of fires dropped over a rolling 14-day window, the system surfaces "alert budget is being hit — consider raising cap or splitting recipients" in the Sunday briefing.

---

## Message templates

WhatsApp via the self-hosted Baileys bridge (decision 2026-06-04). Sender is the bridge's paired number; recipient resolution = logical `adar`/`shanee`/`both` in the outbox row, mapped to numbers only on the bridge machine (`recipients.json`). Free-form text — no Meta template approval applies, so Hebrew copy is unconstrained.

### Single-fire digest (most common — 1 item)

```
🏠 Family inc. — {date}
{flag emoji} {title}  ·  {due_phrase}
{notes if short}

Reply:
  ✅ done    📆 +N days    🤐 mute 30d
```

`{flag emoji}` map:
- OVERDUE → 🔴
- FIRE TODAY → 🟠
- WEEK OUT → 🟡
- MONTH OUT → 🟢

`{due_phrase}` examples: "due today", "due in 7 days (2026-06-03)", "overdue by 4 days".

### Multi-fire digest (2–5 items)

```
🏠 Family inc. — {date}
You have {N} reminders today:

🔴 Car annual test — overdue by 3 days
🟠 Dentist for Child 1 — due today
🟡 Mortgage payment — due in 7 days

Reply 1/2/3 ✅ to mark done, or 1/2/3 +N to snooze.
```

If N > 5, the engine sends the top 5 by priority and notes "+{N−5} more in the dashboard".

### Reply parsing

Inbound replies arrive through the same bridge (1:1 messages from Adar/Shanee to the paired number; requires lifting the bridge's groups-only read guard for exactly those two JIDs — not built yet). The parser understands:

- `done`, `1 done`, `1 ✅` → set Status = Done on the indexed row
- `+7`, `1 +7`, `snooze 7d` → push Due Date by N days, Status = Snoozed, decrement remaining lead times that have already passed
- `mute 30d`, `1 mute` → Status = Snoozed for 30d; doesn't change Due Date
- `list`, `today`, `?` → bot replies with the current digest re-rendered

Anything else → bot replies: "Didn't catch that. Send `?` to see today's list."

---

## Failure modes & guardrails

| Failure | Detection | Fallback |
|---|---|---|
| Bridge down (machine off / WA protocol break / logged out) | `wa_outbox.bridge_alive()` False — heartbeat stale | Message stays durable in the outbox; bridge flushes on reconnect. Engine logs a warning; if stale >24h, surface in Sunday briefing + fall back to email digest. Inforu SMS is the deep fallback (06-doc 1.12). |
| Sheet not reachable | API 5xx | Engine skips the run; alerts Adar at next successful run with "missed yesterday" line |
| Row has invalid date | Parse fails | Skip row, write to log; surfaced in weekly briefing under "data hygiene" |
| Two recipients, same item | Owner = "Both" | One message per recipient; replies are independent (each can mark done) |
| Budget exhausted | Queue overflow | Held items roll to next day; if held >2 days the engine escalates them to priority |
| Recurrence math wrong (Feb 29 etc.) | Sanity check after bump | Falls back to last day of target month; flags for human review |
| Phone offline >6h with queued write | Tombstone not yet set | Engine fires one extra alert; queue flushes correctly on reconnect (idempotent). Widen `TOMBSTONE_SKIP_HOURS` if this surfaces in real use. |
| Tombstone in the future (clock skew) | `tombstone > now()` | Treat as valid for the full skip window; log anomaly to weekly briefing data-hygiene section. |

---

## Out of scope (for Phase 2)

- Two-way Sheet writes from WhatsApp replies → planned, but Phase 2 ships with read-only sends. Replies parsed and logged but not yet written back to Status. Phase 2.5.
- Per-kid recipient routing (e.g., only Partner gets kids' health reminders) → schema supports it via Owner column, but routing rules live in Phase 3.
- Anomaly detection (transaction over ouch threshold) → Phase 3, separate engine.
- Calendar-derived reminders (Phase 1's briefing already covers these) → not duplicated here.

---

## Definition of done (Phase 2)

- [ ] Baileys bridge paired (one QR scan) on an always-on machine; `recipients.json` placed next to `auth_state/` (numbers never in the Sheet or the repo).
- [ ] Cowork scheduled task running daily at 07:30 Asia/Jerusalem.
- [ ] At least 20 seed reminders in the Sheet across Car, Health, Education, Contracts.
- [ ] First real digest received on a real phone by both Adar and Partner.
- [ ] `/Briefings/reminders_log.csv` accumulating entries for ≥7 days.
- [ ] One full overdue-snooze-done cycle completed end-to-end and visible in the log.

When all six boxes are ticked, Phase 2 closes and Phase 3 (Finance) starts.

---

## Phase 6.1 addendum — Tombstone race guard (added 2026-05-30)

The dashboard's offline behavior changed from "lock buttons" to "queue + per-row tombstone" in the 2026-05-30 review resolution. To support that, the engine must:

- Read the new column `O` (`WriteQueue_Tombstone`) on each `Pending`/`Snoozed`/`Overdue` row.
- Skip any row whose tombstone is within `TOMBSTONE_SKIP_HOURS` (default 6h).
- Log skipped rows separately in `/Briefings/reminders_log.csv` as `skipped_due_to_tombstone` with the tombstone age — so the column "is it firing too aggressively or too cautiously?" can be answered from the log.

Implementation: ~30 lines in `reminders_engine.py`. Definition of done for the addendum:

- [ ] Column `O` (`WriteQueue_Tombstone`) added to the Reminders tab.
- [ ] Engine reads + skips rows with tombstones < 6h old.
- [ ] `reminders_log.csv` includes `skipped_due_to_tombstone` count column.
- [ ] One end-to-end test: dashboard taps `✓ done` offline → reconnects → engine runs → row not re-alerted; tombstone visible in log.

See `05_Dashboard_Design.md` §"Refresh / loading model" and §"Edge cases" for the dashboard-side contract.

=== End: 02_Reminders_Engine_Spec.md ===


```

</details>
