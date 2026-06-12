# Next session — Family Inc

*Generated 2026-06-12 by `automation/session_kickoff.py`. Regenerated at every session end — do not edit by hand.*

**Before pasting (on your machine):** `git pull --ff-only`

Paste everything below this line to open the session:

---

You are opening a Family Inc working session as Lead Architect. Read `CLAUDE.md`
(roles, principles, guardrails), then work the current milestone only.

**Current milestone: M3 — Appliance live = go-live (repo side ✅ 2026-06-12 session 1; remaining = PO's ~1h at the VPS, runbook: `deploy/README.md`)**

Open items:

- ⬜ The VPS hour: provision (private-repo clone via read-only fine-grained PAT — repo turned out to be private at go-live) → secrets in `/etc/family-inc/` (`FAMILY_INC_SHEET_ID` = the live-backend flip, + SMTP creds for §10.2; **no LLM key — keyless go-live, provider call in M4**) → pair Baileys → verify timers → import seeds → one green `backup.sh` run · *prerequisite step-zero done 2026-06-12: live `Family_OS` Sheet created from the seed xlsx, Settings.UserMap fixed, GCP project + service account + OAuth client created*
- ⬜ **Publication** (gates Pages + PWA): history rewrite first — `git filter-repo` strips the 8 Archive personal docs + pre-D-024 blobs (kid names, kickoff health/money) from ALL history — then flip repo public (free-plan Pages requires public), enable Pages (Source=GitHub Actions + the two secrets + OAuth origin), pin PWA on both phones, rotate the provision PAT. **Repo stays private until the rewrite — D-027f's deferral is only safe unpublished.** Dashboard-dependent acceptance items (#2, #5) wait for this; digest acceptance (#1) ticks from tonight
- ⬜ **Acceptance: both phones receive the morning digest 3 consecutive days; one full done→recur cycle visible in the log** → then flip CLAUDE.md "Current state", tag `v1-live`, M4 after ≥1 week

Recent decisions (full log in `DECISIONS.md`):

- D-028 (2026-06-12): M3 session-1 review run (DeepSeek, post-push — the in-chain gate ran MOCK twice: Ollama cloud 403'd the 671b model mid-day, then a placehold…
- D-027 (2026-06-12): M3 session-1 contract resolutions (delivery infrastructure). (a) Daily digest queues kind=briefing — it was kind=alert, consuming 1 of the 2…
- D-026 (2026-06-12): M2 milestone review run (DeepSeek) and resolved: 2 wording applies (SPEC §8.3 one-clock tombstone semantics; §7.1 validate-before-write clau…
- D-025 (2026-06-12): M2 contract resolutions (one source of truth port). (a) SPEC §7.1 errata: engine reads Status ∉ {Done, Skipped} — the spec'd ∈ {Pending, Sno…
- D-024 (2026-06-12): Personal-data purge of the tracked tree (M1). Seed CSVs (reminders/vaccines/goals/group-config) → gitignored `seeds/`; `Dashboard/config.js`…

Session contract: don't open lanes outside this milestone without a PO call
logged in `DECISIONS.md` · constants → config, utilities → `automation/lib/`,
message copy → templates · session end: tests green if code moved, `BACKLOG.md`
flipped, directional calls logged with the next D-number, regenerate this file
(`python3 automation/session_kickoff.py`), and hand the PO ONE terminal block
(stage → review gate if milestone-closing → commit → push). Git index operations
run on the PO's machine, never in the sandbox.
