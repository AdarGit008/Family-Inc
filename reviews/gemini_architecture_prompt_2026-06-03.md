# Gemini PRO prompt — Architecture Overview + Deep Dive (2026-06-03)

*Copy the fenced block into a fresh Gemini PRO chat and run. Gemini has all project files.*

```
Read first: 00_Architecture_and_Roadmap.md, CLAUDE.md, 02_Reminders_Engine_Spec.md,
05_Dashboard_Design.md, 07_WhatsApp_Group_Summarizer_Spec.md, Automation/README.md.
Ignore all other files. Every component, schedule, and column name must come from
them — invent nothing.

Write the canonical architecture document for "Family Inc" — a household-automation
system (Google Sheets master DB Family_OS, vanilla-JS PWA dashboard with Sheet
write-back, Python automation + Node WhatsApp bridge, WhatsApp via Twilio,
Israeli context). Readers: the two product owners. Tone: precise, dry.

## Honesty requirement (critical)
As of 2026-06-03 NOTHING IS LIVE — all scripts run mock/dry; Twilio, GCal
connector, OAuth, GH Pages, Baileys pairing all pending. Every Mermaid diagram
must distinguish 3 states with a legend: SOLID (exercised today, mock output),
DASHED (built-but-dark, awaits credential), DOTTED "spec only" (tombstone engine
guard, 6.1 dashboard UI, bank scrapers, Gmail bill parser, reply-to-act).
A diagram showing the system as if running is a failure.

## Structure (use these headings; Mermaid + legend at every level)
- L0 — one-screen overview: human inputs → Family_OS Sheet → automation layer
  (07:30 reminders, hourly WhatsApp classify, Fri/Sun briefings) → WhatsApp + PWA.
- L1 — five lane dives, one diagram each: (1) briefings, (2) reminders (lead-time
  tiers, 2/day budget, recurrence, spec-only tombstone guard), (3) finance
  ingestion (manual CSV today; planned scrapers/parsers marked honestly),
  (4) WhatsApp summarizer (Baileys JSONL + heartbeat → Haiku + 5 hard rules →
  per-group routing → tiered budget with critical_keywords bypass → digest),
  (5) dashboard write-back (OAuth → batchGet → optimistic UI → offline queue →
  tombstone flush; UI spec-only).
- L2 — data contracts: Reminders cols A–O, WhatsApp tabs, tombstone semantics
  (write-on-flush, 6h skip window, >6h residual race, clock-skew rule), alert
  budget tiers, mock-mode contract (single Twilio swap point).
- A Day in the Life — Wednesday walkthrough 05:30 → Sat 21:00; at each step pair
  what happens TODAY (mock file output) vs at FULL OPERATION (WhatsApp arrives).
- What Is NOT Built — explicit list, one line each: item + what unblocks it.

## Don't
No invented components, no future-vision sections beyond the not-built list, no
UX commentary, no collapsing the 3 states into done/not-done. Be terse — the
diagrams carry the weight.
```
