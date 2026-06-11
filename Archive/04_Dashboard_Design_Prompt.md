# Family inc. — Dashboard PWA Design Brief (prompt)

*Paste the section under "PROMPT — start here" into a fresh Claude session. Everything above the line is just notes for me (Adar) about why this prompt exists and what to do with the output.*

## Why this exists

The dashboard is Phase 6 of the Family inc. rollout — the part the rest of the family will actually look at. Every other phase produces structured data; the dashboard is where two adults glance at it on an iPhone home screen and decide whether the system is earning its keep.

I want a design pass done by Claude before I commit to any tech choices, because the wrong layout will get ignored and the system will quietly die. Three things I need out of the design session:

1. **A few distinct design directions** — not one polished idea, but three or four credible options to compare.
2. **One complete design**, picked from the options, fleshed out enough that I could hand it to an engineer (or build it myself) without re-deciding things.
3. **A feature gap analysis** — what the dashboard surfaces that the rest of Family inc. can't yet provide, and what features I should add to the master Sheet or the engines to make the dashboard useful.

When done, drop the output as `05_Dashboard_Design.md` in the same folder.

---

## PROMPT — start here

You are designing the user-facing dashboard for **Family inc.**, a personal household-operations system I (Adar) am building. The dashboard is Phase 6 of a phased rollout. Most of the underlying data and automation is already built — you are designing the surface that a busy parent looks at on an iPhone for 30 seconds in the morning and 5 minutes on Sunday evening.

### Before you start

Read these files in the working folder so you have the full picture (in this order):

1. `00_Architecture_and_Roadmap.md` — north-star goals, operating principles, schema, phase status
2. `02_Reminders_Engine_Spec.md` — what the daily-7:30 engine does and produces
3. `03_Partner_Signoff.md` — what's in scope, what's explicitly off-limits
4. `Family_OS.xlsx` — the master data store; open it via `openpyxl` or `extract-text` to see the tabs and current seed data
5. `Briefings/` — sample daily and Sunday briefings already produced; this is what the dashboard will visualize
6. `reminders_engine.py` and `sunday_briefing.py` — the engines whose output the dashboard renders

If anything in those files is ambiguous or contradictory for your design work, **ask me up to three clarifying questions before you start designing**. Don't ask cosmetic questions; ask ones that would change the shape of the design (e.g. "is the partner expected to interact with the dashboard or only read it", "is the dashboard meant to be edit-capable or strictly read-only").

### What to produce

Deliver one markdown document, `05_Dashboard_Design.md`, with the sections below. Aim for thorough but not bloated — about 6–10 pages of markdown equivalent.

**Section 1 — Three to four design directions (one paragraph each).**

For each direction, give:
- A short name (e.g. "Today-first", "Domain tiles", "Stream").
- One-sentence concept.
- Who it's optimised for (which family member, which moment of the day).
- The key tradeoff vs the other directions.
- One concrete failure mode — when would this design fall apart?

Cover a meaningful spread of metaphors. Avoid four variations of the same idea. Examples of metaphors worth considering: a single "today" screen with no navigation, a domain-tile home (Money / Health / Calendar / Goals), a chronological stream of upcoming items, an "alerts only" minimal screen, a Sunday-briefing-first design that hides daily detail.

**Section 2 — Recommended direction + complete design.**

Pick one of the directions and fully specify it:

- **Information architecture.** Every screen, every section, in order of importance. Use a tree or hierarchical list.
- **Wireframes.** ASCII or markdown-block wireframes for: (a) the main screen as seen at 8 AM on a quiet weekday, (b) the same screen on a heavy day with several reminders and an overdue item, (c) the Sunday-briefing view. Show roughly where text, lists, buttons, and color blocks go.
- **Data binding.** For every UI element, name the Sheet tab and column that feeds it. If an element has no current data source, mark it as a feature gap (see Section 3).
- **Interaction model.** What can you tap? What expands? Can the dashboard write back to the Sheet (mark a reminder done, snooze, etc.) or is it strictly read-only? If write-back, where does that happen architecturally.
- **Tech stack recommendation.** Justify: vanilla HTML + JS, a small React app, a Next.js PWA, or something else. Argue based on the operating principle "boring tech where possible" — don't recommend React just because it's familiar. Include how authentication to Google Sheets works on iPhone Safari, given the partner also needs access.
- **Refresh model.** When the user opens the dashboard, what happens? Pull from Sheet on every load? Cache + background sync? Push notifications?
- **Edge cases.** Two minimum: (i) the Sheet is unreachable (offline subway), (ii) the user has been on vacation for a week and there are 30 overdue items.

**Section 3 — Feature gap analysis.**

Walk through what the dashboard needs to be useful, and contrast that with what the Family inc. system currently provides (per the roadmap + the engine code). Produce two ranked lists:

- **Missing features in the data layer** (master Sheet schema, engines): what should be added to make the dashboard meaningfully better. Rank by leverage. For each, give a one-line rationale.
- **Features that exist but the dashboard probably won't surface** (and why that's OK or a problem). This forces honesty about whether some current capabilities earn their keep.

End the section with **one sentence per phase** (Phases 0–5) on how that phase's data shows up in your recommended dashboard. If a phase's data has no place on the dashboard, say so plainly.

### Format and constraints

- **Markdown only.** No HTML, no images, no diagrams beyond ASCII.
- **No emoji decoration** unless it's actually part of the dashboard UI mockup (e.g. flag icons in a wireframe).
- **No code samples longer than ~15 lines.** This is a design doc, not a prototype.
- **Stay within the partner-readable, kid-aware, alert-budget operating principles** from the roadmap. If a design idea breaks one of those principles, call that out and either drop the idea or argue for the principle change.
- **Don't recommend tech you can't justify.** "Boring tech where possible" is binding.
- **Write for one reader: me, Adar.** Skip generic UX preamble.

When the document is written, save it as `05_Dashboard_Design.md` and tell me one line about which design direction you recommended and why, so I can decide whether to read it now or later.
