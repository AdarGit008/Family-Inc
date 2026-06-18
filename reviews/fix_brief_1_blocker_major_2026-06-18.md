# Fix Brief 1 — Blocker + Major

## Session opener — read first (this brief is self-contained)

*Open a fresh Claude Code session in this repo and point it at this file. It carries all the context the fix needs — no prior conversation required.*

**You are opening a Family Inc fix session as Lead Architect.** `CLAUDE.md` auto-loads (roles, principles, guardrails) — read it. **The PO has authorized this fix lane as the session focus.** It sits outside the standing M6 focus in `BACKLOG.md`, but the items marked **(M6)** below *are* M6 work; the rest is PO-sanctioned by this brief.

**Where this came from.** A full-project audit on 2026-06-18 (a 123-agent verified workflow) produced three artifacts in `reviews/`:
- `review_audit_2026-06-18_13-48.md` — the **evidence base**: every finding's claim · evidence · suggested fix · the two verifier verdicts, plus hand-verification notes on the high-stakes items. **Open it for the full detail behind any item here.**
- `fix_brief_1_blocker_major_2026-06-18.md` — **this file** (1 blocker + 7 majors).
- `fix_brief_2_gaps_minor_disputed_2026-06-18.md` — the remainder (10 systemic gaps + 29 minors + 6 disputed + nits).

**Current state (2026-06-18).** v1 is live & accepted (`v1-live`); M6 finance ingestion is building (repo half done, appliance step next); the M6.4 reconciliation is gated to ~2026-06-20. **Test baseline: 341 passed, 0 failed — keep it green.**

**Read order:** `CLAUDE.md` (auto) → `BACKLOG.md` → this brief → for each item you take, the matching section of the audit report + the `SPEC`/`ENGINEERING`/`DESIGN` clause it cites.

**Run the tests** from the repo root (hermetic — an autouse fixture blanks live env, so it never touches the real Sheet / model / SMTP):
`uv run --frozen pytest -q`  (or `.venv/bin/python -m pytest -q`).

**Session protocol (CLAUDE.md):** `git pull --ff-only` before any work · constants → `automation/lib/config.py` (never in a script), utilities → `automation/lib/`, message copy → `automation/templates.py` · a directional call **folds into the canon** — edit the relevant doc to its new present-tense state + a short inline *why*; the dated rationale goes in the commit message (there is no separate decision log) · git index ops run on the **PO's machine**, never in the sandbox · end with ONE handoff terminal block.

**Review gate:** this brief touches **privacy (LLM), delivery (bridge + digest), and budget (mute→critical)** guarantees → run `automation/review.py` at close, blocking inside the handoff chain (resolve a MAJOR as Apply / Defend / Open). See ENGINEERING §10.

---

*Work plan derived from `reviews/review_audit_2026-06-18_13-48.md`. Scope: the 1 confirmed blocker + 7 confirmed majors. Full evidence per item is in the audit report; this brief is the sequenced action plan. Est: ~1 focused session.*

> **This session touches privacy (LLM), delivery (bridge + digest), and budget (mute→critical) guarantees.** Per ENGINEERING §10 that makes it **review-triggering** — run the `automation/review.py` gate at close (blocking inside the handoff chain). Two items (B7, B5) are M6-critical and also block the M6.2 appliance step.

## Pre-flight
- `git pull --ff-only` (origin is the cross-agent sync point — CLAUDE.md §0).
- Confirm the appliance is at origin HEAD before trusting any "deployed" claim (committed ≠ deployed). **Specifically check whether the box is running the `baileys_listener.js` that contains the 1:1 reply path — that decides how urgent B1 is.**
- Read `BACKLOG.md` first; this session does not open new lanes.

## PO decisions needed up front (don't code these until called)
1. **Bridge 1:1 reply path (B1).** Disable until v1.1, or formally unpark reply-parsing now? Recommendation: **disable** — the v1.1 prerequisites aren't met (LID-addressing drops replies, `reply_handler.py` is unwired + writes the Sheet via `openpyxl` + hardcodes `Adar`). Removing shipped-but-unspecced behavior is a directional call.
2. **§8.6 vs §8.7 reconciliation (B4).** §8.6 says "DeepSeek only, no others"; §8.7 sanctions an Anthropic fallback. Either (a) gate Anthropic off the message/`classify` task and keep it for non-message tasks only, or (b) carve the fallback into §8.6 explicitly. Privacy call → joint (Shanee).
3. **Mute vs critical (B3).** Does a `critical_keyword` match override a `mute` group? Today the code lets it (and bypasses budget). Either enforce mute as the hard rule SPEC §7.3 says, or amend §7.3 + the line-353 comment to state criticals pierce mute.

---

## Work items

### B1 — 🔴 BLOCKER: bridge reads 1:1 chats and sends acks (reply-parsing is parked to v1.1)
- **Where:** `automation/bridge/baileys_listener.js:388-423`
- **Contract:** SPEC §7.4 ("never reads 1:1 chats until reply parsing, v1.1"); honest-affordance principle (SPEC §3.7 / DESIGN §1.5).
- **Fix (if decision = disable):** `return`/`continue` out of the `if (!isGroup(jid))` branch before any read/parse/ack, leaving only the existing drop. Remove the ack send. Keep the code behind a clearly-commented v1.1 stub.
- **Test:** bridge has no JS harness today — at minimum add a note to the DESIGN §9 smoke checklist ("a 1:1 to the bridge gets no reply/ack"). (A bridge scope-guard test is tracked in Brief 2 / disputed `bridge-node#2`.)
- **Canon:** none if disabling (restores SPEC §7.4 truth). If unparking, this is a major BACKLOG move + SPEC §7.4 rewrite — out of scope for this brief.
- **Effort:** S (disable) / L (unpark).

### B4 — 🟠 Anthropic fallback can send WhatsApp plaintext to a processor §8.6 forbids
- **Where:** `automation/lib/llm.py:75-76,126-151`
- **Fix (if decision = gate):** in `complete()`, when the task is a message task (`classify`) and `provider == "anthropic"`, return `None` → deterministic keyword fallback. Leave Anthropic available for any non-message task.
- **Test:** `test_llm.py` — with only `ANTHROPIC_API_KEY` set, a `classify` call returns `None` (deterministic path), never reaches `_complete_anthropic`.
- **Canon:** reconcile **SPEC §8.6 ↔ §8.7** to the chosen reading (the disagreement itself is the bug, per SPEC line 4).
- **Effort:** S.

### B3 — 🟠 Muted group is not a hard rule (keyword/critical ALERTs fire despite mute)
- **Where:** `automation/whatsapp_summarizer.py:223-246, 340-351, 353`
- **Fix (if decision = enforce mute):** add a mute short-circuit at the **top** of `hard_rule_alert()` — `return (None, False)` when `group_cfg(...)["importance_default"] == "mute"` — so the documented ordering holds and the line-353 comment becomes true.
- **Test:** `test_summarizer.py` — a muted group **with** a configured `critical_keyword` classifies ROUTINE, `critical=False`, no outbox dispatch (the budget-bypass path is closed).
- **Canon:** if instead criticals pierce mute, amend SPEC §7.3 + the inline comment.
- **Effort:** S.

### B5 — 🟠 (M6) Gap-fill overflow is permanently uncategorized, not retried next run
- **Where:** `automation/lib/categorize.py:34-37` (`GAPFILL_MAX_BATCH = 80`); flow at `finance_ingest.py:256-265`.
- **Why:** once written with a blank `Category` + real `Txn-ID`, dedup excludes those rows from `new_txns` forever — the LLM never gets a second pass. First live import (45-day backlog) can easily exceed 80.
- **Fix:** chunk-loop the gap-fill in `_gapfill` so all rules-misses are categorized before the write (preferred), **or** add a re-categorize pass over already-written blank-`Category` rows. Correct the comment either way.
- **Test:** `test_finance.py` — ingest >80 rules-miss txns (fake LLM), assert **none** land with a blank `Category`.
- **Canon:** none (comment + code only).
- **Effort:** M.

### B7 — 🟠 (M6) `deploy.sh` never installs the finance Node deps
- **Where:** `deploy/deploy.sh:10` (only `automation/bridge` gets `npm ci`).
- **Fix:** add `(cd automation/finance && npm ci --omit=dev)` between the bridge `npm ci` and the pytest line, matching ENGINEERING §6. While here, restore `--frozen` on the pytest line (`uv run --frozen pytest` — nit `deploy-systemd#5`) to match the documented appliance path.
- **Test:** none (shell); covered by the M6.2 live roundtrip.
- **Canon:** none (deploy.sh now matches ENGINEERING §6).
- **Effort:** S. **Do this before M6.2.**

### B2 — 🟠 Erev-chag candle-lighting line never fires (Fridays only)
- **Where:** `automation/daily_digest.py:155` (`if today.weekday() != 4 ...`).
- **Note:** also examine `automation/hebcal_client.py` — the erev-chag candle data may not be reachable through the current API surface (Brief 2 gap #7). Confirm the data source before wiring the render, else this fix renders nothing.
- **Fix:** extend `_hebcal_line` to emit the 🕯 line on erev-chag (holiday eve), not just `weekday()==4`, sourcing candle times from the holiday endpoint. Degrade-quiet preserved.
- **Test:** `test_render_golden.py` — a fixture dated erev-chag renders the candle line; a Friday still renders; a plain weekday renders nothing.
- **Canon:** none (code matches SPEC §4/§7.2 once fixed); update the `daily_digest.py:153` docstring ("Fridays") to include chagim.
- **Effort:** M (depends on hebcal_client capability).

### B6 — 🟠 Weekly briefing missing the contracted system self-report line
- **Where:** `automation/weekly_briefing.py:351-379`.
- **Fix:** add `section_self_report(today)` reading `reminders_log.csv` (runs-green ratio, tombstone-skip count + max age), the summarizer's classified count, and `logs/llm_costs.csv` (week spend; month-to-date on the month's first briefing), rendered as the ENGINEERING §8 line ("7/7 runs green · N classified · M tombstone skips (max age) · ₪ spend"). Existing warning lines replace it when any flag is set.
- **Test:** `test_render_golden.py` — the line is present and byte-shaped; a flag set replaces it with the warning.
- **Canon:** none (implements the existing ENGINEERING §8 / SPEC §7.2 contract).
- **Effort:** M.

### B8 — 🟠 Dashboard offline queue: no cap-50, no loss warning
- **Where:** `dashboard/app.js:1303-1309` (and the catch branch ~1319-1321).
- **Fix:** before pushing in `applyWrites()`, guard `if (state.pendingWrites.length >= 50) { one-shot toast warning; return; }`; add the warning string to `STRINGS.he`/`STRINGS.en`; reset the one-shot flag after a successful flush. (Cap 50 is a constant — keep it a named const at the top of `app.js`, mirroring config discipline.)
- **Test:** dashboard has no JS harness; add to the DESIGN §9 smoke checklist (queue 50 offline writes → warning shows, further taps don't grow the queue).
- **Canon:** none (implements SPEC §7.6 / DESIGN §5).
- **Effort:** S.

---

## Suggested order
1. **B7** (one line, unblocks M6.2) → **B5** (M6 correctness) — clear the finance-deploy path first.
2. **B1** (the blocker) once the deploy-status check + PO call land.
3. **B4, B3** (privacy + budget — the review-sensitive pair) after their PO calls.
4. **B6, B8** (pure implementation, no decisions).
5. **B2** last — gated on confirming hebcal_client can supply erev-chag data.

## Definition of done (ENGINEERING §11, per item)
Tests for its logic green · constants in `config.py`/named consts (not scripts) · errors degrade or surface · `SPEC.md`/`DESIGN.md` updated where a contract moved · `BACKLOG.md` status flipped · **review gate run at close** (privacy/delivery/budget touched) · M6 items observed green on the appliance before declaring live.

## Handoff (session end → PO runs on their machine)
One terminal block: `pytest -q` → `review.py` gate (resolve MAJOR as Apply/Defend/Open) → `git commit` → `git push`. A MAJOR review finding stops the commit until resolved or PO-overridden.
