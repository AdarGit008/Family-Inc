# What this session changed (2026-06-11 remake)

- Full doc remake: 11 numbered docs superseded → `Archive/`; new canon = `SPEC.md` (system spec v2.0), `ENGINEERING.md` (handbook v1.0), `DESIGN.md` (design spec v2.0), `DECISIONS.md` (single decision log), `BACKLOG.md` (single status/backlog). `CLAUDE.md` rewritten thin; old copy archived.
- Runtime decided: one VPS ("the appliance") runs Baileys bridge + systemd timers + all Python. Datacenter-IP WhatsApp-ban risk accepted, documented, with fallback chain (email → Twilio → Inforu SMS).
- v1 scope locked: keystone (reminders → WhatsApp, weekly briefing, dashboard write-back) + group summarizer. Six lanes frozen with explicit unfreeze conditions.
- Data plane unified (prescribed for M2): all Python on gspread + service account; local `Family_OS.xlsx` demoted to seed template. Dashboard stays on gapi user OAuth. (Audit found Python read a local xlsx while the dashboard wrote Google Sheets — two diverging sources of truth.)
- Alert budget moved to a single outbox chokepoint (`lib/outbox.py`): shared daily ledger across all senders, kinds = alert / critical (bypass) / briefing (exempt), quiet hours enforced there. Previously the engine and summarizer each kept independent 2/day counters (combined 4+/day possible).
- Morning flow split: 07:25 engine computes fires; 07:30 daily digest assembles ONE message (fires + WhatsApp digest + Hebcal) per recipient. Summarizer runs hourly 24/7 so criticals can fire at night while ordinary alerts hold to 07:00.
- Dashboard write contract made explicit: every write-back stamps `DoneAt`/`LastDoneBy`/`WriteQueue_Tombstone`. (Audit: tombstone was read by the engine but never written by the dashboard — the race guard, arc, and ticker were dead on arrival. `05_Dashboard_Design.md` also still contained the contradictory "explicit offline lock" text.)
- New principle: honest affordances — reply-command footers removed from message templates until reply parsing ships (v1.1).
- Review ritual revised: milestone-only (new spec / architecture shift / budget-privacy-delivery changes / each milestone close), via `review.py`, best available external model, Gemini default.
- Migration plan M1–M4 with hard session boundaries; v1 acceptance criteria (SPEC §11); pytest minimum bar + golden-file briefing tests; systemd timers (not cron); uv; ILS-only; weekly briefing standardized Sat 21:00.
- Docs are portfolio-grade: English, self-contained, public-repo-safe by construction (personal data only in Sheet / `/etc/family-inc/` / gitignored seeds).
