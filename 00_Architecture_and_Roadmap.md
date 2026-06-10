# Family inc. — Architecture & Roadmap

*Living design doc. Edit freely; Cowork will update as decisions evolve.*

Last updated: 2026-05-27

## North-Star goals

1. Help the family set and achieve long-term (3–5 year) goals.
2. Use AI to enhance Health, Finance, Education, and other life areas.
3. Maximum automation — minimum daily babysitting of the system.
4. Provide a simple "today / this week" dashboard accessible on iPhone (web first, native later if it earns it).

## Operating principles

- **One source of truth per domain.** No data lives in two places. If it does, one of them is a view.
- **Boring tech where possible.** Google Sheets > custom database. CSV drops > brittle scrapers. PWA > native app — until proven otherwise.
- **Alerts are a budget, not a firehose.** Better one well-timed WhatsApp at 8 AM than ten throughout the day. Hard cap to be enforced.
- **Briefings, not notifications.** Daily 1-line digest, weekly multi-domain briefing, monthly deep dive. Real-time alerts reserved for true urgency (overdue car test, doctor cancellation, etc.).
- **Partner-readable, kid-aware.** Both adults can read everything; kids' data is structured but adult-mediated.

## Foundational decisions (2026-05-25)

| Decision | Choice | Reason |
|---|---|---|
| Alert channel | WhatsApp via Twilio | Reliable, real API, family already on WhatsApp |
| Finance ingestion | Manual monthly CSV drop into Drive | Israeli banks lack APIs; scrapers are fragile and credential-risky |
| Storage | Google Drive + Google Sheets | Easiest automation surface; both adults already have Google accounts |
| Audience | Adar + partner | Shared access; no kid-facing UI yet |
| Dashboard | Web (PWA) first; native iOS later if needed | 10x faster to build; pin to home screen feels native enough |

## System architecture

```
+--------------------------------------------------------------+
|  HUMAN INPUTS                                                |
|  - Google Calendar + iCloud Calendar (life events)           |
|  - Bank/card CSVs dropped into Drive (monthly)               |
|  - Manual entries in the master Sheet (goals, contacts, etc.)|
|  - Gmail (incoming bills, school newsletters)                |
+----------------------+---------------------------------------+
                       |
                       v
+--------------------------------------------------------------+
|  SOURCE OF TRUTH                                             |
|  Google Drive folder: Family inc./                           |
|   |-- Family_OS.gsheet  <- master DB (tabs per domain)       |
|   |-- /Finance_CSVs/    <- monthly bank/card exports         |
|   |-- /Documents/       <- contracts, insurance, school docs |
|   +-- /Briefings/       <- generated reports                 |
+----------------------+---------------------------------------+
                       |
                       v
+--------------------------------------------------------------+
|  AUTOMATION LAYER (Cowork scheduled tasks)                   |
|  - Daily 07:30: today's-events check, urgent reminders fire  |
|  - Weekly Sun 18:00: full family briefing generated          |
|  - Monthly 1st: finance digest + anomaly report              |
|  - On CSV upload: parse, categorize, write back to Sheet     |
+----------------------+---------------------------------------+
                       |
        +--------------+--------------+
        v                             v
+------------------+         +----------------------+
|  ALERTS          |         |  DASHBOARD (PWA)     |
|  WhatsApp via    |         |  Pinned to iPhone    |
|  Twilio          |         |  Read-only view      |
|  (Adar + partner)|         |  of the Sheet        |
+------------------+         +----------------------+
```

## Master Sheet schema (draft)

Tabs in `Family_OS.gsheet`:

1. **People** — name, role, DOB, ID number (Teudat Zehut), Kupat Holim, blood type, allergies.
2. **Calendars** — registered calendar sources, sync status, color coding.
3. **Reminders** — universal table: title, domain, owner, due date, lead times (60/30/7/1), status, last sent, channel.
4. **Finance — Accounts** — bank/card accounts, last imported date, balance snapshot.
5. **Finance — Transactions** — append-only ledger from CSV imports; columns: date, account, description, amount, category, tags, notes.
6. **Finance — Budget** — monthly category targets vs actuals.
7. **Goals** — long-term goal, owner, target date, 90-day milestone, % complete, last update.
8. **Education** — child, school/preschool, year, key dates (registry windows, parent-teacher), contacts.
9. **Health** — person, provider, last visit, next due, notes; sub-tab for vaccine schedule.
10. **Car** — vehicle, plate, test date, insurance renewal, license expiry, mechanic.
11. **Contacts** — doctors, teachers, mechanic, plumber, lawyer, accountant — tagged by domain.
12. **Contracts** — insurance, mortgage, utilities — renewal dates, premiums, providers.

The **Reminders** tab is the keystone. Every domain writes to it, and one daily automation reads it.

## Phased rollout

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Master Sheet created with all tab schemas; Drive folder structure; this doc | **done (2026-05-27)** |
| 1 | Calendar merge + Sunday-evening briefing piped to WhatsApp | **in progress** — `sunday_briefing.py` built, `Calendar-Events` tab added, scheduled Sunday 18:00 with email fallback; Google Calendar connector suggested but not yet connected |
| 2 | Reminders engine: daily check, escalation tiers, WhatsApp delivery | **in progress** — spec done (`02_Reminders_Engine_Spec.md`), dry-run engine built, Twilio not yet wired |
| 3 | Finance ingestion + monthly digest | not started |
| 4 | Education + Health trackers wired into Reminders | not started |
| 5 | Long-term goals tracking + Friday progress report | not started |
| 6 | Dashboard PWA pinned to iPhone | not started |

## Assumptions in force (2026-05-27)

- **Partner sign-off assumed.** `03_Partner_Signoff.md` exists; treating it as agreed pending real conversation.
- **Kickoff conversation deferred.** Seeded reminders + goals are placeholders; will be replaced after the 90-min session in `01_Family_Kickoff_Guide.md`.
- **Until Twilio is provisioned**, the Reminders engine writes briefings to `/Briefings/` and drafts a Gmail to Adar as the alert channel. Switch to WhatsApp is a single function swap.

## Open questions / blockers

- Twilio account: not provisioned. Email fallback in place until then.
- Google Calendar connector: suggested, not yet connected. Briefing falls back to manual `Calendar-Events` rows until then.
- iCloud Calendar (partner): no native MCP yet. Manual entry into Calendar-Events with Source="iCloud" works as interim.
- Kids' info: ages, schools, Kupat Holim — current Sheet values are placeholders.
- Long-term goals: 2 placeholder goals seeded; replace after kickoff.

## What Cowork is NOT doing (out of scope, for now)

- Trading or moving money on Adar's behalf.
- Storing bank credentials anywhere.
- Sending messages to anyone outside Adar + partner.
- Making medical decisions; only surfacing reminders.
