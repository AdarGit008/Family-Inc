# Family inc. — Automation pack

Companion scripts to `sunday_briefing.py` and `reminders_engine.py`.
Every script runs in **mock mode** out-of-the-box (no creds required)
and prints a `RUNNING IN MOCK MODE` notice when it does.

Python 3.11+. Install deps:

```bash
pip install requests beautifulsoup4 python-dateutil openpyxl anthropic
```

`anthropic` is optional — scripts that use it fall back to deterministic
templates when `ANTHROPIC_API_KEY` is missing.

---

## Scripts

| File | Purpose | Inputs | Outputs |
| --- | --- | --- | --- |
| `hebcal_client.py` | Shabbat times + chag windows (Haifa proxy for ⟨town⟩) | — | `cache/hebcal_cache.json` |
| `friday_briefing.py` | 5-section Friday recap, embeds Shabbat times + goal retro | `Family_OS.xlsx` (optional) | `Briefings/friday_YYYY-MM-DD.md` |
| `anomaly_detector.py` | Subscription creep, duplicates, drift, spikes, merchant suffix drift | transactions CSV | `Briefings/anomalies_YYYY-MM-DD.json` |
| `pediatric_milestones.py` | Tipat Halav vaccines + visits + "things to celebrate" for under-3s | People CSV (optional) | `vaccines_due.csv` |
| `goal_coaching.py` | Weekly one-liner per goal (celebrate / nudge / steady) | Goals CSV (optional) | `Briefings/goal_retro_YYYY-MM-DD.md` |
| `hebrew_categorizer.py` | Cache → regex → LLM categorization of Israeli vendors | vendor strings | `cache/merchant_cache.json` |
| `pdf_to_event.py` | Multimodal PDF/image → calendar events | files in `test_inputs/` | `events_extracted.csv` |
| `dira_tracker.py` | Scrape dira.moch.gov.il for Northern District lotteries | — | `dira_matches.csv` or `dira_stub.txt` |
| `whatsapp_summarizer.py` | Classify WhatsApp group messages (ROUTINE/DIGEST/ALERT), hard-rule + per-group alert routing under the 2/day budget, build daily digest | `whatsapp_bridge/inbox/whatsapp_inbox.jsonl` + `Setup/12_WhatsApp_Group_Config_Seed.csv` | `data/WhatsApp_Inbox.csv`, `data/WhatsApp_Archive.csv`, `Briefings/whatsapp_digest_YYYY-MM-DD.md` |
| `whatsapp_bridge/baileys_listener.js` | Self-hosted, free WhatsApp Web companion — appends group messages to the inbox JSONL **and delivers outbox messages 1:1 to Adar/Shanee** (Baileys-first decision 2026-06-04; Twilio dropped) | paired WA account + `whatsapp_bridge/recipients.json` | `inbox/whatsapp_inbox.jsonl`, `outbox/whatsapp_sent.jsonl` |
| `wa_outbox.py` | WhatsApp send helper — every automation queues outbound messages here (`queue_message(to, body)`); bridge delivers within ~15s; `bridge_alive()` exposes heartbeat staleness | called as a library (CLI: `python wa_outbox.py both "text"`) | `outbox/whatsapp_outbox.jsonl` |
| `review.py` | Session-end Gemini review — assembles the canonical prompt + lane-specific attachments, sends to a chosen provider, writes audit trail | `--lane`, `--changes` (markdown file or stdin) | `Briefings/review_<lane>_<ts>.md` |

---

## Env vars

| Var | Used by | Required? |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | `friday_briefing.py`, `hebrew_categorizer.py`, `pdf_to_event.py`, `whatsapp_summarizer.py` | optional (fallback to template / "Other" / deterministic classifier) |
| `OLLAMA_API_KEY` | `review.py` — Ollama Cloud key (switched from OpenCode Zen 2026-06-04). Get one at https://ollama.com → API keys | optional (mock mode without it; not needed for local) |
| `OLLAMA_HOST` | `review.py` — set `http://localhost:11434` to use a local Ollama instead of cloud | optional (default: https://ollama.com) |
| `FAMILY_INC_SHEET` | (reserved for future gspread wiring) | unused today |

Cost ceiling: each LLM-touching script targets ≤ $0.10/run. We default
to `claude-haiku-4-5` for routing and `claude-sonnet-4-5` only for the
multimodal PDF extractor.

---

## Suggested cron / launchd schedule

```
# Daily 07:00 — Reminders digest (existing)
0  7  *  *  *   python /path/to/Family\ Inc/reminders_engine.py

# Sun 18:00 — Sunday briefing (existing)
0 18  *  *  0   python /path/to/Family\ Inc/sunday_briefing.py

# Fri 11:00 — Friday briefing
0 11  *  *  5   python /path/to/Family\ Inc/Automation/friday_briefing.py

# Daily 05:30 — Anomaly scan over last 90 days
30 5  *  *  *   python /path/to/Family\ Inc/Automation/anomaly_detector.py

# Mon 08:00 — Refresh pediatric reminders 60-day window
0  8  *  *  1   python /path/to/Family\ Inc/Automation/pediatric_milestones.py --window-days 60

# Thu 19:00 — Goal retro draft (so Friday brief can pull it)
0 19  *  *  4   python /path/to/Family\ Inc/Automation/goal_coaching.py

# Wed 09:00 — Dira tracker
0  9  *  *  3   python /path/to/Family\ Inc/Automation/dira_tracker.py

# Hourly — classify new WhatsApp group messages + refresh digest
0  *  *  *  *   python /path/to/Family\ Inc/Automation/whatsapp_summarizer.py
```

The WhatsApp bridge (`whatsapp_bridge/baileys_listener.js`) is a long-running
process, not a cron job — start it once with `node baileys_listener.js` (pair
the QR) and keep it running on an always-on machine. See
`whatsapp_bridge/README.md`. The hourly `whatsapp_summarizer.py` reads whatever
the listener has appended since the last run (dedups by `msg_id`).

`hebcal_client.py` and `hebrew_categorizer.py` are libraries — call
them from the briefing scripts, no separate schedule needed.
`pdf_to_event.py` is run on-demand (drop a file in `test_inputs/`).

---

## Conventions matched from `sunday_briefing.py`

- Module-level docstring describes run modes + file outputs
- `from __future__ import annotations` + `pathlib.Path` everywhere
- `ROOT = Path(__file__).parent`
- `--as-of YYYY-MM-DD` and `--dry-run` flags where applicable
- `logging` for warnings; `print()` for user-visible run output
- Mock fallbacks announced with `RUNNING IN MOCK MODE` notices
- Israeli context: ILS amounts, Hebrew strings preserved
