# Session changes — 2026-06-12, M3 session 3 (publication rewrite kit, D-030)

*Input for the privacy-triggered review gate (CLAUDE.md protocol 5: budget-privacy-delivery changes). No personal values appear below or in any committed artifact — categories only.*

## What changed

- **`deploy/publish.sh`** (new): one-time D-030 publication rewrite. Fresh `--mirror` clone of origin → `git filter-repo --invert-paths --paths-from-file deploy/publish_paths.txt --replace-text seeds/redact.txt` → two-stage verify gauntlet (every stripped path via `git log --all`; every redaction LHS via `git grep -F` across `git rev-list --all`) → interactive confirm → force-push heads+tags. Any gauntlet hit aborts before push; abort leaves origin untouched and the rewritten mirror in `/tmp` for inspection.
- **`deploy/publish_paths.txt`** (new): 24 paths stripped from all history — the 8 personal Archive docs at both their current and pre-M1 locations, `Briefings/`, `Progress/`, `Dashboard/config.js`, four Setup seed CSVs, `Setup/code/`, `Automation/vaccines_due.csv`. Scan-derived: every line matched a personal-data token in at least one historical blob.
- **`seeds/redact.txt`** (new, gitignored, NOT in this commit): replace-text rules for blobs of kept files — kid names (incl. one Hebrew form), pediatrician name, two DOB date literals, a personal email, the house-build town (Latin + two Hebrew spellings), three kickoff health/money phrasing fragments. Lives only on PO machines + backups; `publish.sh` refuses to run without it.
- **`.gitignore`**: `seeds/redact.txt` added with rationale comment.
- **`seeds/README.md`**: import-provenance paragraph genericized (D-030b) — old wording let family size and an infant's condition be inferred; old blobs covered by the rewrite's redact rules.
- **`deploy/README.md`**: new §6 "Publish the repo" (rewrite → re-point VPS clone → fresh-clone Macs carrying gitignored personals → flip public → credless VPS remote + provision-PAT revocation → GitHub-side unreachable-object caveat with delete+recreate as paranoia option); Pages/Backups/Acceptance renumbered §7/§8/§9.
- **`DECISIONS.md`**: D-030. **`BACKLOG.md`**: publication item ⬜→🔵, Now-line updated.

## PO calls taken in-session (Adar, routine)

1. House-build town = personal → stripped everywhere, including 12 HEAD residuals (`attic/` ×4, `reviews/` ×7, `Archive/02_Yad2`) that survived D-024's manual pass.
2. seeds/README health-backlog phrasing → genericized.

## Verification already performed (sandbox rehearsal on a clone)

- Gauntlet: all stripped paths absent, all redaction LHS absent, across every blob of every ref.
- Independent sweep with case-insensitive Latin + Hebrew regexes (broader than the rule list): zero hits.
- 24/24 commits preserved; **204 tests green on the rewritten tree**.

## Review focus questions

1. Is the strip-vs-redact split right — whole-path removal for wholly-personal files, replace-text for kept files' old blobs — or should any kept file's history be dropped entirely?
2. Does the operational ordering in README §6 (rewrite → re-point clones → flip public → revoke PAT) leave any window where personal blobs are publicly reachable?
3. Is the gauntlet sufficient as a push-blocking acceptance check, given the redaction list itself can't be committed for review?
