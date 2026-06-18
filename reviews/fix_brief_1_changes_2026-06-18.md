# Session changes — Brief 1 fix lane (blocker + 7 majors)

Source: `reviews/fix_brief_1_blocker_major_2026-06-18.md` (from the 2026-06-18 audit).
Test baseline 341 → **355 green**. Three PO decisions were taken up front (B1/B3/B4).

## What this session changed

- **B1 (blocker, SPEC §7.4):** the Baileys bridge no longer acks 1:1 chats. Inbound 1:1s from known senders are **logged** to `replies.jsonl` (raw material for the parked v1.1 reply feature); the bridge never acts on them and never acks (honest-affordance §3.7). `reply_handler.py` stays unwired; `ackText`/`parseReply` kept as documented v1.1 stubs. SPEC §7.4 + the file docstrings updated to match. *PO call: "just log for now."*
- **B3 (major, budget, SPEC §7.3):** muted groups — a **critical/safety keyword still pierces mute** (budget-exempt ALERT); every non-critical hard rule (alert-keyword/teacher-evening/vaad) is now suppressed in a muted group, closing the budget-bypass leak. `hard_rule_alert` gained a mute short-circuit after the critical check. SPEC §7.3 + comments updated. *PO call: criticals pierce mute.*
- **B4 (major, privacy, SPEC §8.6/§8.7):** reconciled the "DeepSeek only" vs Anthropic-fallback contradiction **provider-agnostically** — the guarantee is the minimal payload (one msg + ≤3 context; finance = description+amount), identical for whichever single provider is configured. **No code change** to `lib/llm.py` (already provider-symmetric). §12.2 phrasing aligned. *PO call: every provider treated like DeepSeek (divergence from the brief's "gate" recommendation, approved).*
- **B5 (major, M6):** finance gap-fill now **chunk-loops** over `GAPFILL_MAX_BATCH`, so a >80-txn first import (45-day backlog) is fully categorized before the write — previously the overflow was written blank with real Txn-IDs and excluded from dedup forever (permanent loss). The per-chunk reply budget is **sized to the chunk** (`len(batch)*24`), not a fixed 600 that truncated a full chunk's JSON to nothing (caught in adversarial verification).
- **B7 (major, M6):** `deploy.sh` now runs `npm ci --omit=dev` in `automation/finance` (was bridge-only) and restored `--frozen` on the pytest line — unblocks M6.2.
- **B2 (major):** the candle-lighting digest line fires on **erev-chag** (yom-tov eve), not only Fridays — new `hebcal_client.chag_candles()` reads the calendar endpoint's candles/havdalah items; `_hebcal_line` picks Shabbat ("צאת שבת") vs chag ("צאת החג"). Degrade-quiet preserved.
- **B6 (major, ENGINEERING §8 / SPEC §8.3):** the weekly briefing now carries the **system self-report line** (`N/N runs green · M classified · K tombstone skips (max age Xh) · ₪Y LLM spend`), with `_system_flags` warnings replacing it. Added the additive `tombstone_max_age_h` column to `reminders_log.csv` (makes §8.3 "max age seen" real) and indicative LLM ₪ pricing constants in config. New `## System` section; all four metrics share the trailing-7-day window.
- **B8 (major, SPEC §7.6 / DESIGN §6):** dashboard offline queue **caps at 50** with a one-shot loss warning (he+en), re-armed after a flush.

## Canon touched
SPEC §7.3, §7.4, §8.6, §8.7, §12.2; ENGINEERING §8 (already matched); DESIGN §9 smoke checklist; BACKLOG (fix-lane status + reply-parsing entry).

## Ride-along (pre-existing uncommitted WIP, PO-approved for this commit)
SPEC §12.2 M6.3 wording; `config.example.js` finance-tab rename; two id-less-collision tests in `test_finance.py`; new `deploy/FINANCE.md` runbook.
