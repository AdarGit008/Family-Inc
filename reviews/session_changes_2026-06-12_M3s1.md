# Session changes — 2026-06-12, M3 session 1 (go-live repo side)

Review trigger: touches delivery, budget, and privacy guarantees (ENGINEERING §11) — not an M-close.

- `deploy/` created: idempotent `provision.sh` (ENGINEERING §5 steps 1–4 + units), `deploy.sh` (§6 verbatim + frozen sync), `backup.sh` (tar bridge/state+logs → rclone remote from env, 90-day prune), `deploy/README.md` = the PO's go-live-hour runbook
- 13 systemd units in `deploy/systemd/`: always-on bridge (Restart=on-failure), 5 timer+service pairs (engine 07:25, digest 07:30, summarizer hourly, weekly Sat 21:00, backup Sun 03:00; all Persistent=true), templated `family-fail-flag@.service` on every unit's OnFailure=
- **Budget**: daily digest now queues kind=briefing, was kind=alert — it consumed 1 of 2 daily alert slots and was deferrable by the ledger into the next digest (circular, since over-budget alerts defer INTO the digest). PO call, D-027a, SPEC §7.2 clarified
- **Delivery**: SPEC §10.2 email fallback implemented — `lib/mailer.py` (the only smtplib import), `outbox.heartbeat_age_hours()`; digest --send degrades to SMTP when heartbeat stale >24h (identical content, "delivered by email — bridge down Nh" note, stamps normally); SMTP-also-down → queue + shout, fail flag retained. Framed as transport substitution, not an outbox bypass (D-027b)
- **Delivery**: fail-flag loop closed — `logs/fail.flag` (config.FAIL_FLAG) appended by OnFailure hook, reported (Hebrew prepend line, templates.py) + cleared by the next *delivered* digest, surfaced by the weekly briefing if stale (D-027e)
- **Privacy**: GitHub Pages serves `dashboard/` via `.github/workflows/pages.yml`; gitignored `config.js` generated at deploy from Actions secrets DASHBOARD_CLIENT_ID/DASHBOARD_SHEET_ID — ids never enter git history (D-027d, D-024 lineage)
- `recipients.json` read from `/etc/family-inc/` first, bridge-dir fallback for dev (D-027c) — code now matches ENGINEERING §2
- `Dashboard/` → `dashboard/` case rename (two-step git mv in the handoff block) + all content refs updated (review.py, READMEs, .gitignore)
- `seeds/Reminders_Import_M3.csv` drafted (31 rows from the 08 seed + kickoff health backlog, §6.1 layout, gitignored) + import instructions in seeds/README.md
- Tests 172 → 191 (new `tests/test_mailer.py`: heartbeat age, SMTP fake, degrade paths, kind=briefing, fail-flag report/clear/keep semantics); goldens untouched
- **Privacy** (D-027f, completes D-024): kid names/health details scrubbed from 10 tracked Setup/+reviews/ files the M1 purge missed; 8 personal Archive/ docs (kickoff output, money baseline, design docs with names) untracked + gitignored — files stay on PO machines, git history rewrite deliberately deferred
- Canon updates: SPEC §7.2 (digest kind), ENGINEERING §1/§2/§5 (layout current, Pages-via-Actions, fail-flag semantics), CLAUDE.md current-state, BACKLOG M3 statuses, DECISIONS D-027
