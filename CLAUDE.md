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
(ILS, Hebrew, Maccabi healthcare). Family = 2 adults + 2 kids (⟨child-1⟩ 3yr, ⟨child-2⟩ 3mo).
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
