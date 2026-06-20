# automation/ — the appliance's Python + the bridge

What runs on the VPS (ENGINEERING.md §5 timers). **dry/mock by default** for a
creds-less checkout; **live on the appliance since `v1-live` (2026-06-13)**.
Status lives only in `BACKLOG.md` — look there for what's shipped vs gated.

| Script | Timer | Does |
| --- | --- | --- |
| `reminders_engine.py` | 07:25 | computes fires from the Reminders tab; logs heartbeat; **does not send** |
| `daily_digest.py` | 07:30 | assembles ONE morning message per recipient (fires + WA digest + Hebcal) → `lib/outbox.py` with `--send` |
| `whatsapp_summarizer.py` | hourly | classifies group messages (hard rules → DeepSeek → deterministic), routes alerts under budget, builds the WA digest |
| `weekly_briefing.py` | Sat 21:00 | cross-domain weekly briefing |
| `property_scrape.py` | `family-property.timer` 07:10 + 19:10 | Yad2/Madlan scrape → digest section + `Property-Listings` |
| `finance/scrape.js` + `finance_ingest.py` | `family-finance.timer` 06:00 | Node read-only Mizrahi scrape → CSV, then Python is the only Sheet writer |
| `accuracy_review.py` | Sat 21:00 | classifier-accuracy fold-in to the weekly briefing + on-demand operator surface |
| `finance_budget_formulas.py` | on-demand | idempotent budget-SUMIFS installer |
| `import_reminders.py` | one-shot | M3 Reminders seeder |
| `hebcal_client.py` | (library) | Shabbat times + chagim, cached 24h |
| `reply_handler.py` | — | PARKED until v1.1 (reply parsing) |
| `review.py` | manual | milestone review tool (ENGINEERING.md §11) |
| `session_kickoff.py` | session end | regenerates `NEXT_SESSION_PROMPT.md` |
| `bridge/` | always-on | Baileys listener + outbox sender (see `bridge/README.md`) |

`lib/` holds the single implementations (config, sheet, outbox, llm, dates,
money) — scripts import from lib and define no constants of their own
(ENGINEERING.md §1/§3).

Setup: `uv sync` at repo root (ENGINEERING.md §2). Runtime LLM key:
`FAMILY_INC_DEEPSEEK_API_KEY` is the primary (DeepSeek; deterministic
fallbacks without it); `ANTHROPIC_API_KEY` is the fallback provider. `review.py`
reads its own keyspace (`DEEPSEEK_API_KEY` / `OLLAMA_API_KEY` / `OLLAMA_HOST`).
Secrets live in `/etc/family-inc/env` on the appliance, never in the repo.

Canon: `SPEC.md` (contracts) · `ENGINEERING.md` (how it's built/run) ·
`DESIGN.md` (surfaces/copy) · `BACKLOG.md` (status) · `ROADMAP.md` (the forward
v1.1 plan + lane contracts).
