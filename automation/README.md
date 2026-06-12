# automation/ — the appliance's Python + the bridge

What runs on the VPS (ENGINEERING.md §5 timers). Everything runs in
**dry/mock mode** out-of-the-box — until M3 go-live, nothing messages anyone.

| Script | Timer | Does |
| --- | --- | --- |
| `reminders_engine.py` | 07:25 | computes fires from the Reminders tab; logs heartbeat; **does not send** |
| `daily_digest.py` | 07:30 | assembles ONE morning message per recipient (fires + WA digest + Hebcal) → `lib/outbox.py` with `--send` |
| `whatsapp_summarizer.py` | hourly | classifies group messages (hard rules → Haiku → deterministic), routes alerts under budget, builds the WA digest |
| `weekly_briefing.py` | Sat 21:00 | cross-domain weekly briefing |
| `hebcal_client.py` | (library) | Shabbat times + chagim, cached 24h |
| `reply_handler.py` | — | PARKED until v1.1 (reply parsing) |
| `review.py` | manual | milestone review tool (ENGINEERING.md §11) |
| `session_kickoff.py` | session end | regenerates `NEXT_SESSION_PROMPT.md` |
| `bridge/` | always-on | Baileys listener + outbox sender (see `bridge/README.md`) |

`lib/` holds the single implementations (config, sheet, outbox, llm, dates,
money) — scripts import from lib and define no constants of their own
(ENGINEERING.md §1/§3).

Setup: `uv sync` at repo root (ENGINEERING.md §2). Env vars: `ANTHROPIC_API_KEY`
(optional — deterministic fallbacks without it); review.py providers use
`OLLAMA_API_KEY`/`OLLAMA_HOST` or `DEEPSEEK_API_KEY`. Secrets live in
`/etc/family-inc/env` on the appliance, never in the repo.

Canon: `SPEC.md` (contracts) · `ENGINEERING.md` (how) · `DESIGN.md` (copy) ·
`DECISIONS.md` (why) · `BACKLOG.md` (when).
