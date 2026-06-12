# Milestone review · deepseek-chat · 2026-06-11 21:35

*Prompt: `Briefings/gemini_remake_review_prompt_2026-06-11.md` · chunked × 2 · 1414 output tokens*

---

### Concerns

1. **Data plane split remains a latent divergence risk (SPEC §5 vs §6.1).** The dashboard writes via user OAuth while Python reads via service account. If the dashboard writes a column the engine doesn't expect (or vice versa), there's no shared schema validation layer. **Severity: High.** File: `SPEC.md` §5 architecture diagram and §6.1 table — neither mentions a readback contract or schema reconciliation step after writes.

2. **Backlog references pre-restructure file paths that don't exist yet (BACKLOG.md M1 items).** M1 tasks reference deleting `reminders_engine.py` and `sunday_briefing.py` from root, but current state shows those files don't exist in the attached files — only `automation/` paths. If the repo _currently_ has root-level scripts, this is fine; if not, the backlog is stale before execution starts. **Severity: Medium.** File: `BACKLOG.md` M1 item 2.

3. **Tombstone 6h window is tuned against a guess, not observed behavior (SPEC §8.3).** A 6h skip window means an offline phone reconnecting 5.5h after a tap will still be processed, but one at 6.5h risks a spurious duplicate alert. No guidance on what to do if the observation shows the 6h window is either too tight (duplicates observed) or too loose (real taps missed). **Severity: Medium.** File: `SPEC.md` §8.3 — "Widen to 12h if observed" is a plan, but there's no monitoring to detect _which_ failure occurred.

4. **Review script (`review.py`) is listed as a tool but no contract exists for its output format.** The `Automation/review.py` script is referenced in `ENGINEERING.md` §11 and `CLAUDE.md`, but there's no spec for what it builds, what attachments it gathers, or how it formats the review prompt. If the script breaks or generates a malformed prompt, the review pipeline silently degrades. **Severity: Low.** File: `ENGINEERING.md` §11 references it; `ENGINEERING.md` §1 lists it in `automation/lib/` — but neither file defines its contract.

5. **Fallback chain (§10) has conditional dependency on infrastructure not provisioned.** Twilio and Inforu are listed as fallbacks but explicitly "not in code" and "revisit only on 2+ failures." If the bridge fails mid-week, setting up email fallback requires manual intervention. The EMAIL fallback is described as automatic after 24h silence, but there's no description of _how_ it's automatic — does a systemd timer watch for bridge heartbeat and trigger a send? **Severity: Medium.** File: `SPEC.md` §10 — the email fallback mechanism is unspecified beyond "automatic."

### Missed alternatives

- A single JSON file on disk as the master DB instead of Google Sheets (eliminates API quota concerns and network dependency for all operations, trading multi-device concurrency for simpler failure modes).
- Having the dashboard write directly to the same outbox JSONL that the bridge polls, removing the dashboard→Sheet→engine readback cycle entirely (write-once, deliver-once without tombstone).
- Running the hourly summarizer as an event-driven trigger on new inbox entries rather than a cron-poll (eliminates the 1h latency window for critical messages without changing the 2/day budget).
- A single shared configuration file (JSON/YAML) for the bridge/Node side rather than duplicating `recipients.json`, group config, and routing rules between Python config and Node state.
- Replacing the tombstone/race-guard pattern with a write-ahead log approach (dashboard writes intent to a separate Sheet tab, engine consumes after a delay, no 6h window tuning needed).

### Affirmations

- **Single outbox chokepoint** (`lib/outbox.py`) is the right structure — removing per-script budget counters was the most important change in this session.
- **Hard scope guard on the bridge** (only recipients in `recipients.json`) correctly limits blast radius if the bridge is compromised.
- **Tombstone + offline queue** without disabling buttons is the correct offline model for a household tool where "two people may tap the same row."
- **Single morning message** (daily digest) rather than multiple sends respects the 2/day budget and the "briefings > notifications" principle.
- **One machine, one failure domain** is correct at this scale — the simplicity of "everything or nothing" beats the complexity of partial-failure scenarios for a household system.

### Concrete suggestions

1. **Replace** SPEC §6.1's implicit write contract with an explicit "after every dashboard write, the engine shall read back the affected rows and log any schema mismatch" step in §7.1 — because without readback validation, the dual-OAuth/service-account data plane _will_ diverge silently when someone adds a new column to the dashboard write that the engine's row parsing doesn't handle.

2. **Replace** the vague "automatic email fall### Concrete suggestions (continued)

3. **Replace** "widen to 12h if observed" in SPEC §8.3 with a specific monitoring line in `logs/outbox_ledger/` — log `tombstone_skip_vs_alert` events and add a weekly briefing line that reports "N tombstone skips / N alerts sent" so the tuning decision is data-driven, not anecdotal.

4. **Replace** the implicit contract for `review.py` by adding a one-paragraph spec block to ENGINEERING.md §11 defining: input paths it gathers, output format (markdown?), and failure behavior ("if review fails, continue milestone without it and log the failure to DECISIONS.md"). Currently the tool is mentioned as if it exists, but nothing says what it does.

5. **Replace** the manual-lookup pattern for the bridge's `recipients.json` (pairing is described as interactive QR scan) with a documented `Setup/` runbook step that writes the file from a seed template at provisioning time — because a lost bridge session after VPS rebuild requires both paired phones to re-scan, and there's no backup of the auth state.

### One question for the team

**What is the single most likely reason both phones will miss a morning digest for 24+ hours, and what specific non-code action (e.g., "check Sheet API quota page" or "reboot the VPS via provider console") will the adults follow before the system self-recovers?**

---

## Resolution — 2026-06-12 (Claude, session leader: Adar)

*Note: suggestion 2 was truncated at a chunk seam; its substance equals Concern 5 and is resolved there.*

**Applied:**
- Concern 1 [HIGH], modified — reviewer's "engine reads back after every dashboard write" is impossible (the engine isn't running when the dashboard writes). Root worry is schema drift across the two write paths; applied as **engine header validation every run**: abort before firing on column-map mismatch, log `schema_drift`, surface in next briefing. → `SPEC.md` §7.1 + §9 row.
- Concern 3 [MED] — tombstone tuning made data-driven: skips logged with age; weekly briefing reports "N skips · max age"; widen window on age distribution, not anecdote. → `SPEC.md` §8.3, `ENGINEERING.md` §8.
- Concern 5 [MED] (+ truncated suggestion 2) — email fallback mechanism specified: the daily-digest task itself checks heartbeat and degrades to SMTP; no watcher process. → `SPEC.md` §10.
- Concern 4 [LOW] — `review.py` contract paragraph added (inputs, output location, never-blocks-milestone failure behavior); `run_review_deepseek.py` documented as interim provider. → `ENGINEERING.md` §11.
- Suggestion 5 — `auth_state/` restore-before-re-pair note added to provisioning; it was already inside the weekly backup scope. → `ENGINEERING.md` §5.
- One question — answered as the "No digest by 08:00" runbook (most likely failure: logged-out WA session on a healthy VPS; actions: check email fallback → re-pair; no email → provider-console reboot; repeats → fallback-chain decision). → `ENGINEERING.md` §8.

**Defended:**
- Concern 2 [MED] — the root-level legacy scripts DO exist in the repo (the reviewer saw only attached docs, not the tree); `BACKLOG.md` M1 is accurate.
- Alt: JSON-file master DB — rejected: the Sheet *is* the partner-facing editing surface; "boring tech" includes humans editing a spreadsheet.
- Alt: dashboard writes to outbox directly — category error: the dashboard writes data state, not messages; the engine needs Sheet state regardless.
- Alt: shared bridge/Python config — `recipients.json` is bridge-local *by design* (privacy: JIDs never leave the box); group config already has one home (the Sheet seed).
- Alt: WAL tab instead of tombstone — heavier mechanism, same residual race window; tombstone is shipped thinking with a now-monitored tuning loop.

**Accepted into backlog:** event-driven classifier trigger (inotify on inbox append) → v1.1 candidate.

**Open:** none.
