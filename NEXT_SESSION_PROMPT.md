# Next session — Family Inc

*Generated 2026-06-15 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current milestone only.

> **⚠ Build order (overrides the auto-pick below): the next build is M5 — Property tracker (build now per D-034/D-035), independent of finance — see the M5 section in `BACKLOG.md`. The generator names M4 because it lists first with open items, but M4 (summarizer hardening) is gated "≥1 week live" (earliest ~2026-06-22), so it is NOT this session. The M4 items are retained below for when that gate opens.**

**Current milestone: M4 — Summarizer hardening (1 session, after ≥1 week live)**

Open items:

- ⬜ Sender→role roster seeded (makes hard rules 2–3 reliable)
- ⬜ Phase F weekly accuracy review surface (false-positive purge)
- ⬜ PO call (joint): do family-group criticals override digest-only routing?
- ⬜ PO call (joint): quiet-day digest goes to Adar only (pre-M1 heartbeat behavior preserved) — Shanee gets nothing on days without her fires, incl. the WhatsApp-groups section. Partner-symmetric? (noticed at go-live 2026-06-12)
- ⬜ LLM provider — **direction set to DeepSeek (D-032, 2026-06-13, Adar in-session); remaining = Shanee's confirm of the joint call + wiring** (`lib/llm.py` OpenAI-compatible backend, ~30 lines + tests; §8.6/§8.7 update to name DeepSeek at wiring). v1 stays **keyless** (keyword classification + template briefing) until then; the PRC data-handling tradeoff for group plaintext + Sheet data is accepted by that call
- ⬜ WhatsApp_Inbox hot-tab rolloff against the live Sheet (SPEC §6.2; deferred from M2 — nothing to roll off before ~3 months of live rows; also resolve the 90-day-spec vs 30-day-config disagreement, D-025)
- ⬜ Milestone review (external model) on the live system

Recent decisions (full log in `DECISIONS.md`):

- D-035 (2026-06-15): M3 (go-live) CLOSED — v1 accepted, tagged `v1-live`. The SPEC §11 acceptance window (2026-06-13→15, clock from the D-029 Baileys-7 re-pair) …
- D-034 (2026-06-13): Property tracker (Yad2/Madlan) UNFROZEN — active house search (data-fetching planning session). The only lane unfrozen this session. Build s…
- D-033 (2026-06-13): Frozen-lane dispositions (data-fetching planning session). (a) Finance ingestion (L1) stays frozen — no commitment yet to the ~20–30 min/mon…
- D-032 (2026-06-13): LLM provider direction = DeepSeek (joint M4 call made early; Adar in-session, Shanee to confirm). The open M4 provider call (Anthropic §8.7 …
- D-031 (2026-06-13): Finance-ingestion build architecture pre-resolved while the lane stays frozen (data-fetching planning session). Runtime = the VPS, not Rende…

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
