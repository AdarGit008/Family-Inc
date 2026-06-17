# Session changes — 2026-06-17, debrief + D-046 (classifier JSON-parse hardening)

Review trigger: PO call (Adar, "run review") on a debrief session. D-046 itself is a gate-free hardening edit — no contract/budget/privacy/delivery change, so it does **not** by itself trip the §11/ENGINEERING-§11 review triggers. **Scope of this review: the session's code/design changes + one spec-vs-code divergence the debrief surfaced (below). This is NOT the gated M4 accuracy + external milestone review** — those still need ≥1-week-live data and stay at ~2026-06-20 (D-044/D-035). Lane: `milestone` (full canon attached for context).

## Debrief verification outcomes (context — no code change)
- **DeepSeek confirmed genuinely live on the appliance**, not just asserted: production `whatsapp_summarizer` classifications logged at **~180–300 input tokens** (full prompt: instructions + group meta + ≤3 context + JSON schema), versus the 11-token manual smoke-test ping that first appeared in `llm_costs.csv`. The "empty-prompt" worry is cleared.
- **D-045 both-adults briefing confirmed in the real run**: `delivery_log.csv` shows `2026-06-17,baileys,adar|shanee` — today's 07:30 briefed both adults over WhatsApp (not the email fallback).
- Minor: the `delivery_log` row carries a trailing `\` (`adar|shanee\`). Harmless to delivery; that log feeds the weekly degraded-day surfacing, so worth a glance for a stray char in the recipients write.

## D-046 — the fix (landed, deployed `f46143b`, verified live on-box)
- **Bug, found live:** `deepseek-chat` sometimes returns the JSON object **plus trailing prose**; `llm_classify`'s plain `json.loads` (after a code-fence strip) raised `Extra data` → silent drop to the keyword `deterministic_classify`. Degrade-quiet (no outage) but an accuracy leak — the cruder path ran on ~1/8 messages the LLM should have judged.
- **`whatsapp_summarizer._first_json_obj`** — parses the first JSON object via `json.JSONDecoder().raw_decode`, tolerant of leading text, trailing prose, and ```json fences```. Provider-agnostic (also covers the Anthropic fallback, which has no JSON mode).
- **`lib/llm.complete(json_mode=…)`** — sets DeepSeek `response_format={"type":"json_object"}`, passed **only** from the classify call (non-JSON tasks like briefing prose stay unconstrained). Root-cause fix; the tolerant parse is the safety net.
- Stale `"Haiku"`/"only Anthropic wrapper" log+docstring labels → provider-neutral.
- **Tests 288 → 291** (+3: `json_mode` body present-only-when-asked; trailing-prose end-to-end through the LLM-fake; `_first_json_obj` fence/leading/trailing/no-object matrix). The live `Extra data` payload reproduced and shown to parse.
- Verified live: an on-box `--dry-run` classified **30 live inbox messages** clean through DeepSeek with **zero parse-fallback warnings**.

## OPEN QUESTION for the reviewer — §7.2 briefing-prose divergence
SPEC §7.2 / §4 say the weekly briefing is **LLM-written** (a 5-scene narrative, template fallback). But `automation/weekly_briefing.py` **never imports `lib/llm`** and runs **template-only** — its own comment: *"deterministic template as its fallback is still an open lane — what follows IS the fallback path."* So DeepSeek's only production consumer today is the summarizer; the briefing prose path is dormant. Two candidate resolutions — **which, and what are the risks?**
- **(a) Wire the briefing prose to `deepseek-chat`** now the key is live. **Privacy tension:** the briefing reads *all tabs* (reminders, finance, kids' health, goals), so LLM prose would send **whole-Sheet context** to DeepSeek — far beyond §8.6's deliberate "one message + ≤3 context" classification bound. Does §8.6 sanction this, or does it need an explicit amendment + Shanee's joint call? Cost against the §11 ≤₪120/mo ceiling (weekly, whole-Sheet prompts).
- **(b) Correct §7.2/§4 to call the briefing deterministic-by-design** and drop the LLM-written language. Cheaper, privacy-tighter, but loses the "Strava-year-in-review meets Morning Brew" voice DESIGN §6 describes.

Ask: is the current template-only briefing a latent gap to fill (a) or a spec overstatement to correct (b)? Weigh privacy (§8.6 surface), cost (§11), and the calm-tech/quality goals.

## Canon updated this session
- `DECISIONS.md` — **D-046** row (deployed `f46143b` + verified live).
- `BACKLOG.md` — M4 gains the D-046 ✅ item; the "Now:" clause records deployed/verified.
- (No SPEC/DESIGN change in D-046 — internal robustness only. The §7.2 divergence is the open question above, deliberately left for this review + the PO/Shanee.)
