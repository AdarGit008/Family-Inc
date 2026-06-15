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

**Live since 2026-06-13; v1 accepted 2026-06-15 — tagged `v1-live`.** v1 = keystone (reminders → WhatsApp + weekly briefing + dashboard write-back) + group summarizer, running on the appliance. The SPEC §11 acceptance window (2026-06-13→15, clock from the D-029 Baileys-7 re-pair) passed: the morning WhatsApp digest reached both phones three consecutive days. M1 (restructure) + M2 (one source of truth) closed 2026-06-12; M3 (go-live) closed 2026-06-15 (D-035) — `BACKLOG.md` holds the full M1–M3 record, `DECISIONS.md` D-019→D-035 the why. Foundations still hold: `lib/sheet.py` is the only workbook access (live gspread when `FAMILY_INC_SHEET_ID` is set, seed xlsx otherwise, schema-drift guard); budget enforced only in the outbox ledger; bridge on Baileys 7.0.0-rc13/ESM (D-029); repo public, Pages-served dashboard, secrets in `/etc/family-inc/`. **Next:** M5 (property tracker — build now, D-034), then M4 (summarizer hardening — waits ≥1 week live); LLM stays keyless until M4 wires DeepSeek (D-032).

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
