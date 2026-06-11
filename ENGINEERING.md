# Family Inc. — Engineering Handbook

*How this system is built, tested, deployed, and operated. v1.0 · 2026-06-11.*
*Contracts live in `SPEC.md`; this document is the "how". If they disagree, `SPEC.md` wins and the disagreement is a bug.*

---

## 1. Repo layout (target — reached at end of M1)

```
family-inc/
├── CLAUDE.md            # session context for Claude (thin; points here)
├── SPEC.md  ENGINEERING.md  DESIGN.md  DECISIONS.md  BACKLOG.md
├── automation/
│   ├── lib/
│   │   ├── config.py    # env + TOML loading; ALL constants live here
│   │   ├── sheet.py     # the only gspread client (retry, tab accessors)
│   │   ├── outbox.py    # the only path to a human (budget ledger, dedup, kinds)
│   │   ├── llm.py       # the only Anthropic wrapper (model registry, cost log)
│   │   ├── dates.py     # to_date / to_datetime / fmt_date — one implementation
│   │   └── money.py     # ILS formatting — one implementation
│   ├── reminders_engine.py
│   ├── weekly_briefing.py        # renamed from sunday_briefing (it runs Saturday)
│   ├── daily_digest.py           # assembles ONE morning message (engine fires + WA digest + hebcal)
│   ├── whatsapp_summarizer.py
│   ├── hebcal_client.py
│   ├── review.py                 # milestone review tool
│   └── bridge/                   # Baileys listener + sender (Node)
│       ├── baileys_listener.js  package.json
│       └── state/               # gitignored: auth_state/, inbox/, outbox/, ledgers
├── dashboard/            # vanilla PWA (GitHub Pages serves this directory)
│   ├── index.html  app.js  styles.css  sw.js  manifest.json
│   ├── config.example.js         # committed; real config.js is gitignored
│   └── mock_data.json
├── deploy/
│   ├── systemd/          # *.service + *.timer units (source of truth for schedules)
│   ├── provision.sh      # idempotent VPS setup
│   └── deploy.sh         # pull + test + restart (the only way code reaches the box)
├── tests/                # pytest; fixtures/ holds golden files
├── seeds/                # CSV seeds (reminders, group config, goals) — values may be personal → gitignored where so
├── Setup/                # live runbooks only (VPS, bridge pairing, OAuth, ICS)
├── Archive/              # superseded docs — read-only history
├── attic/                # frozen scripts — unmaintained, excluded from tests
└── logs/ Briefings/      # runtime output (gitignored except .gitkeep)
```

Rules: scripts never define utilities that belong in `lib/` (CI greps for redefinitions of `to_date`/`fmt_money`). Nothing outside `bridge/` touches WhatsApp. Nothing outside `lib/sheet.py` constructs a gspread client. Nothing outside `lib/llm.py` imports `anthropic`.

## 2. Toolchain

| Layer | Choice | Notes |
|---|---|---|
| Python | 3.12 + **uv** | `uv sync` on the box; lockfile committed |
| Key deps | gspread, google-auth, anthropic, pytest, requests | additions need a one-line justification in the PR/commit body |
| Node | LTS, plain npm | bridge only; `npm ci` |
| Scheduling | **systemd timers** (not crontab) | journald logs, `OnFailure=` hooks, `Persistent=true` catches missed runs after reboots |
| Hosting (dashboard) | GitHub Pages from `main:/dashboard` | static, zero backend |
| Secrets | `/etc/family-inc/` mode 600 | `service-account.json`, `env` (ANTHROPIC_API_KEY, SMTP app password, review-provider keys), `recipients.json` |

## 3. Configuration

- `automation/lib/config.py` loads `/etc/family-inc/env` then `config.toml` (committed, non-secret): schedule constants, budget cap, tombstone window, model ids, group digest order.
- **No constant may be defined in a script.** The 2026-06-11 audit found `ALERT_BUDGET_PER_DAY` defined twice with independent ledgers — the class of bug this rule exists to prevent.
- Dashboard config: `config.example.js` committed with placeholders; real `config.js` (Sheet ID, OAuth client id) gitignored. Sheet ID is not secret-secret, but keeping it out of the public repo is free.

## 4. Coding standards

- Python: type hints on public functions; dataclasses for Sheet rows; no bare `except:` — catch narrowly, log with context, and **decide**: degrade (LLM paths) or surface (data paths). Silent swallowing is the bug class that hid the mock/real boundary for two weeks.
- Every script is also a library: `main()` guarded, pure logic importable for tests.
- Logging: stdlib `logging` to stderr (journald captures); one structured CSV per domain in `logs/` for the self-reporting briefing lines.
- JS (dashboard): keep the single-file vanilla discipline; state lives in the one `state` object; every Sheet write goes through `applyWrites()` and conforms to the SPEC §6.1 write contract.
- Hebrew in code: string literals fine, identifiers English. Message copy lives in template constants, not inline f-strings, so DESIGN.md can review it.

## 5. The appliance (VPS)

Provisioning is `deploy/provision.sh`, idempotent, run as root once:

1. Create user `familyinc` (no sudo); `timedatectl set-timezone Asia/Jerusalem`.
2. Install uv + Node LTS; clone repo to `/opt/family-inc`; `uv sync`; `npm ci` in `bridge/`.
3. Copy `deploy/systemd/*` → `/etc/systemd/system/`; `systemctl enable --now` the bridge service + all timers.
4. Place secrets in `/etc/family-inc/` by hand (never scripted, never copied off the box).
5. Pair Baileys: `systemctl stop family-bridge && node bridge/baileys_listener.js` interactively once, scan QR, restart service. `bridge/state/auth_state/` is covered by the weekly backup — **after a VPS rebuild, restore it before considering a re-pair**; a fresh QR scan is the fallback, not the default.

Units (schedules are code — change them via PR, not on the box):

| Unit | Schedule | Runs |
|---|---|---|
| `family-bridge.service` | always-on, `Restart=on-failure` | Baileys listener + outbox sender |
| `family-reminders.timer` | 07:25 daily | reminders engine (writes fires, doesn't send) |
| `family-digest.timer` | 07:30 daily | daily digest assembly → outbox |
| `family-summarizer.timer` | hourly, 24h | classifier — runs at night so **criticals** can fire any hour; ordinary alerts are still held 22:00–07:00 by the outbox |
| `family-weekly.timer` | Sat 21:00 | weekly briefing |
| `family-backup.timer` | Sun 03:00 | tar `bridge/state` + `logs/` → Drive via rclone |

All timers: `Persistent=true`, `OnFailure=family-fail-flag.service` (writes a flag file that the next digest reports — fail loud, §SPEC 3.6).

## 6. Deployment

`deploy/deploy.sh` on the box (or via `ssh familyinc@appliance deploy`):

```
git pull --ff-only
uv sync && (cd automation/bridge && npm ci)
uv run pytest -q                 # red tests abort the deploy; running code is untouched
sudo /usr/bin/systemctl restart family-bridge   # the one whitelisted sudoers line
```

Timers pick up new code automatically on next fire (they exec scripts from the repo); only the long-running bridge needs a restart. The `familyinc` user has exactly one sudo capability — restarting `family-bridge` — so a compromised script can't escalate.

Dashboard deploys are just `git push` (Pages rebuilds in ~30s). The PWA on both phones picks up on next open; `sw.js` cache-busts on version bump in `config.example.js` → mirrored manually into `config.js`.

## 7. Testing policy

Base: the 2026-06-12 integrated suite (`tests/` — 55 tests over engine + briefing, green) is the starting point; M1 renames it to the target layout and extends it. Minimum bar — these exist and stay green from M1 onward:

| Suite | Covers |
|---|---|
| `test_engine.py` | fire-reason matrix (overdue/lead/due-today), tombstone skip window incl. future-skew, recurrence bumps incl. Feb-29, Last-Sent idempotency |
| `test_outbox.py` | budget ledger: 2-cap, critical bypass, briefing exemption, shared-ledger across two sender sources, (id,target) dedup, quiet-hours hold |
| `test_summarizer.py` | the 5 hard rules, per-group routing incl. `none`→NEEDS-A-LOOK, keyword fallback without API key |
| `test_render_golden.py` | weekly briefing + daily digest rendered against `tests/fixtures/*.md` golden files (byte-exact; update goldens deliberately) |
| `test_sheet.py` | row parsing tolerance: missing columns, bad dates → skipped + reported, never raised |

LLM calls are never made in tests — `lib/llm.py` has a fake injected via env. The dashboard gets a manual smoke checklist in `DESIGN.md` §9 (no JS test harness — boring tech; revisit if app.js exceeds ~2,000 lines).

## 8. Observability

- journald per unit (`journalctl -u family-reminders`).
- `logs/reminders_log.csv`, `logs/wa_classifier.csv`, `logs/llm_costs.csv`, `logs/outbox_ledger/`.
- Self-reporting: the weekly briefing includes one system line — "7/7 runs green · 41 messages classified · 2 tombstone skips (max age 1.4h) · ₪6.10 LLM spend"; any fail-flag, schema-drift, or stale heartbeat replaces it with a warning. The humans never check logs unless the briefing tells them to.
- External uptime ping (healthchecks.io free tier) — optional, listed v1.1.

**"No digest by 08:00" runbook** (the most likely 24h failure is a logged-out WhatsApp session on a healthy VPS):

1. Check email — if the digest arrived there, the bridge is down but the system is fine: SSH in, re-pair the QR (restore `auth_state/` first if post-rebuild).
2. No email either → the VPS itself is down: reboot from the provider console; `Persistent=true` timers fire the missed runs on boot.
3. Repeated same-week bridge logouts → treat as ban signal; invoke the fallback chain decision (SPEC §10).

## 9. Migration plan (current tree → this handbook)

Executed as sessions M1–M4; the per-item checklists live in `BACKLOG.md`. Session boundaries are hard: each ends with tests green and a one-line entry in `DECISIONS.md` if anything was decided.

- **M1 — Restructure.** Create `lib/` by extracting the *best* duplicate of each utility (the audit mapped them); move frozen scripts to `attic/`; delete root-level legacy scripts; purge Twilio; rename `sunday_briefing` → `weekly_briefing`; carve `daily_digest.py` out of the engine's send path; pytest scaffold green.
- **M2 — One source of truth.** gspread port behind `lib/sheet.py`; dashboard write contract (DoneAt/LastDoneBy/Tombstone); `Settings.UserMap`; outbox chokepoint + shared ledger; strip reply footers; golden tests.
- **M3 — Go-live.** Provision VPS; pair bridge; secrets; timers on; seed ≥20 real reminders; GitHub Pages + PWA pinned; run SPEC §11 acceptance.
- **M4 — Harden.** Role roster; Phase-F accuracy review; family-criticals PO call; milestone review.

Rollback at any point = `git revert` + redeploy; the Sheet schema only ever gains columns (additive, backwards-compatible — old rows without M/N/O are treated as never-tombstoned).

## 10. Git & repo conventions

- `main` is deployable; small focused commits; imperative subjects; body explains *why* when non-obvious.
- Working sessions commit at session end minimum (the leader pushes; Pages + deploy.sh consume `main`).
- No long-lived branches — this is a two-committer repo (Adar + Claude-in-session).
- Tags: `v1-live` at M3 acceptance, then `vX.Y` per milestone.

## 11. Review ritual (revised 2026-06-11)

Reviews fire on **milestones**, not every session: new spec, architecture change, anything touching delivery/budget/privacy guarantees, and each M-milestone close. Mechanism: `automation/review.py` builds the prompt + attachment list; reviewer = best available external model (Gemini default; substitutions logged). Output is resolved in-session as Apply / Defend (reason appended to the affected doc §History) / Open (PO question), and the resolution lands in `DECISIONS.md` if directional. Tiny edits never trigger review.

**review.py contract:** inputs = `--lane` (drives default attachments), `--changes` (markdown bullet list of what the session changed), optional `--extra-files`; output = the assembled prompt (`--dry-run`) or the model's review, always saved under `Briefings/review_*.md` as the audit trail. Failure behavior: a failed or truncated review never blocks a milestone — log the failure, proceed, and note it in `BACKLOG.md`. `run_review_deepseek.py` is the interim DeepSeek sender (plain + chunked modes, key from `DEEPSEEK_API_KEY` env only); it folds into review.py as a provider in M1.

## 12. Definition of done (any work item)

Code merged with tests for its logic · constants in config · errors either degrade or surface (no silent paths) · contracts updated in SPEC/DESIGN if changed · BACKLOG status flipped · deployed and observed green once on the appliance.
