# Family Inc. — Session Context

*Auto-loaded at the top of every session opened in this folder. Remade 2026-06-11 ("the remake"). Keep under 100 lines.*

## What this is

Household operating system for Adar + Shanee (+ 2 young kids, adult-mediated). Master DB = `Family_OS` Google Sheet. Two product surfaces: WhatsApp messages (self-hosted Baileys bridge) and a PWA dashboard pinned to both iPhones. All automation runs on **one VPS** ("the appliance"). Israeli context throughout: Hebrew/RTL, ILS, Asia/Jerusalem, Maccabi, Hebcal.

## Canon — five documents, one job each

| Doc | Owns | If you need |
|---|---|---|
| `SPEC.md` | What the system is: scope, architecture, data model, contracts, policies, acceptance | any contract or "how should X behave" |
| `ENGINEERING.md` | How it's built/run: repo layout, toolchain, VPS, deploy, tests, migration M1–M4 | any "how do we do X" |
| `DESIGN.md` | Both surfaces: dashboard UI + WhatsApp message design, i18n, states | any pixel or copy question |
| `DECISIONS.md` | Why: dated decision log — the only decision record | history or "didn't we decide…" |
| `BACKLOG.md` | When: v1 milestones M1–M4, v1.1 candidates, frozen lanes — the only status record | what's next / what's frozen |

`Archive/` = superseded docs (read-only history). `attic/` = frozen code, unmaintained (created in M1). Status lives **only** in `BACKLOG.md`; decisions **only** in `DECISIONS.md`. Don't re-create per-doc status flags or review appendices.

## Roles & authority

| Role | Person |
|---|---|
| CTO + co-PO | **Adar** — engineering direction, ships code |
| Chief Design + co-PO | **Shanee** — product direction, UX feel |
| Lead Architect | **Claude** — design, code, tradeoffs; defers to POs on product, to Adar on engineering detail |
| Reviewer | External model via `automation/review.py` (Gemini default) — milestone reviews only |

Either PO can lead a session and take routine calls solo; major directional calls (new feature, principle change, removing shipped behavior) are joint and land in `DECISIONS.md`. Session leader = whoever opened the session; Claude treats them as "the PO" unless they defer.

## Non-negotiable principles (full versions: SPEC §3)

One source of truth per domain · boring tech · alert budget 2/day enforced at the outbox (criticals bypass, briefings exempt) · briefings > notifications · partner-symmetric, no scoring · fail loud, degrade quiet · never promise an affordance that doesn't exist · no money movement, no credential storage, no messages beyond the two adults, no kid-facing UI.

## Current state (live)

**Live since 2026-06-13; v1 accepted 2026-06-15 — tagged `v1-live`.** v1 = keystone (reminders → WhatsApp + weekly briefing + dashboard write-back) + group summarizer, running on the appliance. The SPEC §11 acceptance window (2026-06-13→15, clock from the D-029 Baileys-7 re-pair) passed: the morning WhatsApp digest reached both phones three consecutive days. M1 (restructure) + M2 (one source of truth) closed 2026-06-12; M3 (go-live) closed 2026-06-15 (D-035) — `BACKLOG.md` holds the full M1–M3 record, `DECISIONS.md` D-019→D-043 the why. Foundations still hold: `lib/sheet.py` is the only workbook access (live gspread when `FAMILY_INC_SHEET_ID` is set, seed xlsx otherwise, schema-drift guard); budget enforced only in the outbox ledger; bridge on Baileys 7.0.0-rc13/ESM (D-029); repo public, Pages-served dashboard, secrets in `/etc/family-inc/`. **M5 (property tracker) CLOSED 2026-06-16 (D-043) — live on the appliance:** the on-box headed-Chromium primary clears **Yad2**, **Madlan comes via the Apify secondary (D-040)**, and new listings land in the `Property-Listings` tab + the silent `🏠 דירות חדשות` morning-digest section. The deploy also fixed two appliance-only bugs the credless suite couldn't see: test hermeticity vs `/etc/family-inc/env` SMTP creds (**D-041**) and over-strict per-item Apify errors (**D-042** — skip junk rows, fail loud only on zero-usable). **M4 build items landed 2026-06-16 (D-044):** DeepSeek wired (`lib/llm` OpenAI-compatible urllib backend; provider by key-presence — **DeepSeek key placed 2026-06-17 — the live system now runs `deepseek-chat` as the active provider; real-model output accrues from this date for the M4 accuracy review**), WhatsApp_Inbox 30-day rolloff, quiet-day digest partner-symmetric, sender→role roster — 286 tests green; SPEC §8.6/§8.7 now name DeepSeek. **Next:** M4's remaining two items — the Phase-F accuracy review + the external milestone review (which folds in M5's, D-035 precedent) — are **gated to ≥1-week-live (~2026-06-20)**. **Asymmetric-day briefing closed (D-045, 2026-06-17):** the daily briefing now goes to **both adults every day** — the empty-handed adult gets the quiet-day line + shared sections, kind=briefing so budget-exempt; 288 tests green. **Phase-F surface front-loaded (D-048, 2026-06-17):** `automation/accuracy_review.py` (weekly classifier accuracy review — re-derives each ALERT's rule via `hard_rule_alert`, no Inbox schema change) + a compact "Classifier accuracy" section in the weekly briefing (reuses `family-weekly.timer`, no new unit); 312 tests green. (No open M4 PO questions remain. **Still gated to ~2026-06-20:** the *first real* accuracy-review run + false-positive purge on a full week of live data, and the external milestone review.) **Finance (M6) thawed 2026-06-17 (D-049/050/051: read-only bank/card logins permitted, categorized+trends, DeepSeek gap-fill approved). M6.1 — the hermetic repo half — BUILT same day (D-052):** ported Node scraper (`automation/finance/scrape.js`, Render/Drive stripped) → local CSV → `finance_ingest.py` → `lib/sheet` (append `Finance-Transactions` + upsert `Finance-Accounts`); finance tabs standardized to `Finance-Budget`/`Finance-Accounts`/`Finance-Transactions` (D-052 — config, the 2 `weekly_briefing` reads, seed + budget `SUMIFS` refs, SPEC §6.4/§12.2; briefing tolerates a not-yet-renamed live tab); `family-finance.{service,timer}` (06:00, headless Puppeteer) + provision wiring; **329 tests green (+17)**, no appliance touch (incl. same-day independent-review fixes — `.gitignore` creds-ignore Blocker, SPEC §12.2 auth-model honesty, +tests). **Next: M6.2** (VPS hour — place `bank_creds.json`, rename the 3 live-Sheet tabs, first interactive OTP) — plus the still-gated M4/M5 external review (~06-20).

## Session protocol

0. `git pull --ff-only` before touching anything — other agents push to origin; the local folder is not assumed current (lesson of 2026-06-12, see `DECISIONS.md`).
1. Read `BACKLOG.md` first — it says where we are.
2. Work the current milestone; don't open new lanes without a PO call logged in `DECISIONS.md`.
3. Constants go in config, utilities in `automation/lib/`, message copy in templates (reviewable against `DESIGN.md` §6).
4. Session end: tests green if code moved, `BACKLOG.md` statuses flipped, `python3 automation/session_kickoff.py` regenerated `NEXT_SESSION_PROMPT.md`, and the PO gets ONE terminal block (stage → review gate if milestone-closing → commit → push) to run on their machine. Next session opens by pasting `NEXT_SESSION_PROMPT.md`.
5. **Milestone reviews only** (new spec / architecture shift / budget-privacy-delivery changes / each M-close): run `automation/review.py`, resolve as Apply / Defend / Open, log directional outcomes in `DECISIONS.md`. Tiny edits never trigger review.

## Guardrails for Claude in this repo

- Never put names, phone numbers, JIDs, or real finance values in committed files — they belong in the Sheet, `/etc/family-inc/`, or gitignored seeds (repo is public-portfolio-safe by construction).
- Never add an alert path that bypasses the outbox chokepoint (`automation/lib/outbox.py`).
- Schema changes are additive-only on the Sheet (old rows must keep parsing).
- If SPEC and code disagree, say so before "fixing" either.
