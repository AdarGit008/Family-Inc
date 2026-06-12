# Gemini PRO prompt — Progress Review Deck (2026-06-03)

*Copy the fenced block into a fresh Gemini PRO chat and run. Gemini has all project files.*

```
Read first: 06_Lift_Recommendations_2026-05-30.md, 00_Architecture_and_Roadmap.md,
CLAUDE.md, 07_WhatsApp_Group_Summarizer_Spec.md, Automation/README.md. Ignore all
other files.

Generate a progress-review slide deck for "Family Inc" — a household-automation
system (Google Sheets master DB, PWA dashboard, WhatsApp briefings, Israeli
context). Audience: the two product owners (Adar = CTO, Shanee = Chief Design).
Tone: honest, calm, zero hype.

## Verified status (2026-06-03) — trust this over stale doc snapshots
- NOTHING IS LIVE. ~10 scripts built but all run mock/dry; dashboard is demo-mode.
- Use 3 states everywhere: DONE / BUILT-DARK (code works, awaits cred) / SPEC-ONLY.
- Corrections: Hebrew chrome is DONE (2026-06-01); item 4.7 is approved-NOT-built
  (its ✅ in the 06 doc is wrong); Phase 6.1 UI + engine tombstone guard = spec-only.
- Twilio is the dominant blocker: one credential unlocks 5 lanes (reminders, Sunday
  + Friday briefing delivery, WhatsApp alerts, reply-to-act). Other blockers:
  Baileys QR pairing, GCal connector, Gmail Apps Script, OAuth, GH Pages, bank
  creds+VPS, ANTHROPIC_API_KEY, Apify.
- Costs: ₪0/mo today → ~₪70/mo full operation (classifier ₪33, Twilio ₪18, VPS
  ~₪18, briefing LLM ₪1.5) + ₪400 one-time bridge phone.
- 3 PO decisions: (1) provision Twilio now? (2) schedule the one-time devops day
  (GH Pages + sync + OAuth — blocks Shanee's solo sessions)? (3) family-group
  emergency keywords: override digest-only routing and ping?

## Exactly 6 slides — visual-first, max 15 words of prose per slide
1. What we set out to build — L0 sketch: inputs → Sheet → automation → WhatsApp/PWA
2. What exists today — status grid, phases 0–6.1, 3-state colors
3. Built-but-dark — dependency graph: credentials → unlocks; Twilio dominant
4. Ship order ahead — week 1–4 + Later timeline (from the 06 doc)
5. Costs — bars: ₪0 today vs ~₪70 full, itemized; ₪400 one-time marked
6. Three decisions — one card each with the tradeoff in one line

## Don't
Invent numbers; soften "nothing is live"; call built-dark "done"; use hype or
emojis; add slides. Output: per slide — title, one-line message, rendered visual,
≤3-sentence presenter notes.
```
