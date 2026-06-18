# deploy/ — the go-live hour (M3)

*Runbook = ordered commands. The "why" lives in `ENGINEERING.md` §5–§6; if they disagree, ENGINEERING wins and the disagreement is a bug.*

Layout: `systemd/` units (source of truth for schedules — change via PR, never on the box) · `provision.sh` (idempotent, root, once) · `deploy.sh` (the only way code reaches the box) · `backup.sh` (Sun 03:00 timer) · `publish.sh` + `publish_paths.txt` (one-time D-030 history rewrite, §6).

## 1. Provision (~10 min)

```bash
ssh root@<vps>
curl -fsSL https://raw.githubusercontent.com/AdarGit008/Family-Inc/main/deploy/provision.sh | bash
# or: git clone … /opt/family-inc && /opt/family-inc/deploy/provision.sh
```

Creates `familyinc` (no sudo, one whitelisted systemctl line), TZ=Asia/Jerusalem, Node 22 + uv, repo at `/opt/family-inc`, deps, units enabled. Reruns are safe.

## 2. Secrets (~10 min, by hand — never scripted, never copied off the box)

```bash
# /etc/family-inc/env  (mode 600, owner familyinc)
ANTHROPIC_API_KEY=sk-ant-…
FAMILY_INC_SHEET_ID=…        # ← THE go-live flip: lib/sheet.py live backend on
SMTP_HOST=smtp.gmail.com     # email fallback, SPEC §10.2
SMTP_PORT=587
SMTP_USER=…@gmail.com
SMTP_PASS=…                  # Gmail app password
FAMILY_INC_EMAIL_TO=adar@…,shanee@…   # fallback recipients (else Settings.UserMap)
RCLONE_REMOTE=gdrive:family-inc-backups
BACKUP_KEEP_DAYS=90          # optional — backup.sh prune window (default 90)
```

Also: `service-account.json` (Sheet shared with its client_email as Editor) and `recipients.json` (the two adult JIDs — see `automation/bridge/README.md`). `chmod 600 /etc/family-inc/*`.

Without `FAMILY_INC_SHEET_ID` everything keeps running dry against the seed xlsx and nothing messages anyone — that's the designed creds-less mode, not a bug.

## 3. Pair Baileys (~5 min)

```bash
systemctl stop family-bridge
cd /opt/family-inc/automation/bridge && sudo -u familyinc node baileys_listener.js
# scan QR with Adar's phone (WhatsApp → Linked devices), Ctrl-C after "connected"
systemctl start family-bridge
```

`state/auth_state/` persists the pairing and rides the weekly backup. **After a VPS rebuild, restore it before considering a re-pair** — a fresh QR is the fallback, not the default.

**Exception — Baileys major upgrades (D-029):** auth_state written by an older Baileys line is not forward-compatible (v7 added lid-mapping/device-list/tctoken key types). When `package.json` crosses such a boundary: `npm ci`, **wipe** `state/auth_state/`, re-pair fresh. Never restore a pre-boundary backup over it.

## 4. Verify (~5 min)

```bash
systemctl list-timers 'family-*'            # 7 timers, next fires sane
sudo -u familyinc -i sh -c 'cd /opt/family-inc && uv run --no-sync python automation/daily_digest.py --dry-run'
journalctl -u family-bridge -n 20           # "connected", no QR loop
```

## 5. Seed the Sheet (~10 min)

Import `seeds/08_Israeli_Reminders_Seed.csv` (≥20 rows across Car/Health/Education/Contracts) into the Reminders tab — column mapping in `seeds/README.md`. Copy real `seeds/` + `dashboard/config.js` to any machine that needs them (both gitignored, D-024).

## 6. Publish the repo (one-time, before Pages — D-030)

Git history still holds pre-D-024 personal blobs (the 8 Archive docs at their
old paths, seed CSVs, `Briefings/`, `Dashboard/config.js`, …). Rewrite BEFORE
the repo ever goes public — D-027f deferred this as safe only while private.

On the PO's Mac (never the VPS), repo still private:

```bash
brew install git-filter-repo     # once
deploy/publish.sh                # mirror-clone → filter-repo → verify → confirmed force-push
```

The script consumes `deploy/publish_paths.txt` (paths stripped from all
history) + `seeds/redact.txt` (string redactions; gitignored — PO machines and
backups only) and refuses to push unless every stripped path and every
redaction string greps clean across every blob of every ref. Aborting leaves
origin untouched.

Then, in order:

1. **Re-point the VPS** — every pre-rewrite clone is orphaned:
   ```bash
   ssh root@<vps>
   cd /opt/family-inc && sudo -u familyinc git fetch origin \
     && sudo -u familyinc git reset --hard origin/main && deploy/deploy.sh
   ```
2. **Fresh-clone the Mac working copy.** Keep the old clone renamed
   `Family Inc pre-rewrite/` until done; carry over the gitignored personals:
   the 8 `Archive/` docs + `Archive/Progress/`, `seeds/*.csv` +
   `seeds/redact.txt`, `dashboard/config.js`. Any parallel-agent clone
   re-clones the same way.
3. **Flip public:** GitHub → Settings → General → Danger Zone → Change
   visibility → Public. Only after publish.sh verified clean.
4. **Drop the PAT:** a public repo needs no credentials —
   `sudo -u familyinc git -C /opt/family-inc remote set-url origin https://github.com/AdarGit008/Family-Inc.git`,
   then revoke the provision PAT (GitHub → Settings → Developer settings →
   Fine-grained tokens). Do this *after* step 1 (the old URL still carries the
   token the fetch needs).
5. *Paranoia option:* GitHub keeps unreachable objects server-side until its
   own gc, and the rewrite can't reach those. The repo was never public, so
   nothing was ever exposed; for absolute certainty, delete + recreate the
   repo under the same name instead of force-pushing (re-add the two Actions
   secrets afterwards).

## 7. Dashboard on Pages + PWA (~10 min)

1. GitHub repo → Settings → Pages → Source: **GitHub Actions**.
2. Repo → Settings → Secrets and variables → Actions: add `DASHBOARD_CLIENT_ID`, `DASHBOARD_SHEET_ID` (the workflow writes them into `config.js` at deploy — never into git).
3. Google Cloud Console → the OAuth client → add the Pages origin (`https://<user>.github.io`) to Authorized JavaScript origins.
4. Push to `main` (or run the `pages` workflow manually) → site live in ~1 min.
5. Both phones: open the Pages URL → Share → Add to Home Screen. Sign in once.

## 8. Backups (~5 min, one-time)

```bash
sudo -u familyinc -i rclone config        # interactive: Google Drive remote named per RCLONE_REMOTE
sudo -u familyinc /opt/family-inc/deploy/backup.sh   # prove one green run
```

## 9. Acceptance watch (3 days — SPEC §11)

Both phones get the 07:30 digest 3 consecutive days; one done→recur cycle visible in `logs/reminders_log.csv`; then flip `BACKLOG.md` M3 and tag `v1-live`.

**Day-to-day:** code changes reach the box only via `deploy.sh`. No digest by 08:00 → runbook in `ENGINEERING.md` §8.
