# Decision Log

*One line per decision: date · decision · why · what it superseded. Newest first.*
*This is the only place decisions live. Specs describe the current state; this file explains how we got here.*

| Date | Decision | Why | Supersedes |
|---|---|---|---|
| 2026-06-12 | **Hermes parallel sprint integrated.** A second AI session ("Hermes") had pushed 15 commits to origin from another clone; 10 code commits cherry-picked onto the remake (tests ×55, `config.py`, reply parsing, quiet-hours/batch-window impl, fixes), 5 doc/status commits superseded by the remake. "Hermes" naming **not adopted**. Originals preserved on `remote-backup` branch | Real work must not be lost; remade docs supersede its doc edits | Hermes doc commits A1–A4, Progress-page status |
| 2026-06-12 | **Sessions must `git pull --ff-only` before any work; origin is the sync point between agents** (added as session protocol step 0) | Two sessions diverged silently for a week — local audit was stale against pushed work | Implicit "local folder is current" assumption |
| 2026-06-12 | Remake milestone review run (DeepSeek; Gemini unavailable this session) and resolved: 6 applies (schema-drift guard, data-driven tombstone tuning, specified email fallback, review.py contract, auth-state restore note, no-digest runbook), 5 defends, 0 open — no direction changes. Audit: `Briefings/review_remake_2026-06-12.md` | Milestone-only ritual: a new spec qualifies | — |
| 2026-06-11 | **Full remake.** Canon docs = `SPEC.md` + `ENGINEERING.md` + `DESIGN.md` + `DECISIONS.md` + `BACKLOG.md`; superseded docs → `Archive/` | 4 competing sources of truth for status; doc sprawl outpaced shipping | All numbered docs |
| 2026-06-11 | Runtime = **one VPS** ("the appliance"): Baileys bridge + systemd timers + all Python | Bridge needs always-on anyway; no home hardware; one failure domain | Cowork scheduled tasks, Render cron, "always-on home machine" |
| 2026-06-11 | v1 scope = **keystone + group summarizer**; six lanes frozen (see `BACKLOG.md`) | Ship the loop that justifies the system; breadth-first is how nothing went live | "All lanes active" |
| 2026-06-11 | Python Sheets access = **gspread + service account**; local `Family_OS.xlsx` demoted to seed template | openpyxl-vs-gapi split = two diverging sources of truth, violating principle #1 | openpyxl reads of local xlsx |
| 2026-06-11 | **Alert budget enforced at the outbox** (single daily ledger, all senders), not per-script | Engine + summarizer each kept their own 2/day counter → combined 4+/day possible | Per-script budget counters |
| 2026-06-11 | WhatsApp messages **must not advertise reply commands** until reply parsing ships (v1.1) | Current templates promise `✅ done` replies that go nowhere — dishonest UI | Reply footers in message templates |
| 2026-06-11 | Docs are **portfolio-grade**: English, self-contained, public-repo-ready; personal data lives only in gitignored config/seeds | Doubles as a showcase artifact for Adar's job search (Goal 2) | Internal-only doc tone |
| 2026-06-11 | Review ritual = **milestone-only** (new spec, architecture shift, go-live), via `review.py`, best available external model, Gemini default | Per-session reviews drifted (DeepSeek/Ollama substitutions); codify reality | Per-session mandatory Gemini review |
| 2026-06-11 | Currency = **ILS everywhere**; weekly briefing = **Sat 21:00** | Kickoff mixed USD/ILS; docs disagreed Sat 21:00 vs Sun 18:00 | Mixed currencies; Sun 18:00 |
| 2026-06-04 | WhatsApp delivery = **self-hosted Baileys outbox**; Twilio dropped to documented fallback | ₪0 marginal, no WABA verification, no template approval, free-form Hebrew | "WhatsApp via Twilio" (2026-05-25) |
| 2026-06-02 | Bridge = **self-hosted Baileys** (not Whapi/Green API); all 5 groups in, incl. family | Free + plaintext never leaves the box we control | Whapi.cloud fast path |
| 2026-06-02 | **Per-group alert routing** (daycare/building → both; student → Adar; family/neighborhood → digest-only) + **critical-keyword bypass** of the daily cap | Relevance is per-group; emergencies must never queue behind mundane alerts | Global routing; flat 2/day cap |
| 2026-05-30 | Offline model = **optimistic queue + per-row tombstone** (`WriteQueue_Tombstone`, 6h skip window) | No cognitive load offline, no engine race | Explicit offline lock (disabled buttons) |
| 2026-05-30 | **No PWA push.** WhatsApp is the only alert channel | One channel, one budget | PWA web-push proposal |
| 2026-05-30 | Dashboard chrome **Hebrew default, RTL**, English fallback toggle; data values stay Hebrew | Household reads Hebrew; toggle costs little | English-default chrome |
| 2026-05-30 | Appreciation ticker grouped by **domain**, names inline | Avoid leaderboard/scoring read between partners | Person-grouped ticker |
| 2026-05-30 | Palette = warm-paper + indigo `#5E6AD2`; type = Inter + Heebo + Geist Mono | Calm-tech; Hebrew/Latin metric parity; money legibility | Green `#2d5f3f` palette |
| 2026-05-30 | Kickoff agreements: alert budget **2/day hard cap**, both adults get everything, weekly review Sat 21:00, nothing off-limits to track | Joint PO session output | — |
| 2026-05-25 | Storage = Google Sheets + Drive; dashboard = vanilla PWA; finance = CSV drops (now frozen) | Boring tech; both adults already on Google | — |

## How to add a decision

Append a row at the top. If it changes a contract, update `SPEC.md`/`DESIGN.md` in the same commit. If it's a major directional call, both POs decide (see `CLAUDE.md` → Decision authority).
