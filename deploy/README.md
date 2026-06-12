# deploy/ — the go-live hour (M3)

*Runbook = ordered commands. The "why" lives in `ENGINEERING.md` §5–§6; if they disagree, ENGINEERING wins and the disagreement is a bug.*

Layout: `systemd/` units (source of truth for schedules — change via PR, never on the box) · `provision.sh` (idempotent, root, once) · `deploy.sh` (the only way code reaches the box) · `backup.sh` (Sun 03:00 timer).

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

## 4. Verify (~5 min)

```bash
systemctl list-timers 'family-*'            # 5 timers, next fires sane
sudo -u familyinc -i sh -c 'cd /opt/family-inc && uv run --no-sync python automation/daily_digest.py --dry-run'
journalctl -u family-bridge -n 20           # "connected", no QR loop
```

## 5. Seed the Sheet (~10 min)

Import `seeds/08_Israeli_Reminders_Seed.csv` (≥20 rows across Car/Health/Education/Contracts) into the Reminders tab — column mapping in `seeds/README.md`. Copy real `seeds/` + `dashboard/config.js` to any machine that needs them (both gitignored, D-024).

## 6. Dashboard on Pages + PWA (~10 min)

1. GitHub repo → Settings → Pages → Source: **GitHub Actions**.
2. Repo → Settings → Secrets and variables → Actions: add `DASHBOARD_CLIENT_ID`, `DASHBOARD_SHEET_ID` (the workflow writes them into `config.js` at deploy — never into git).
3. Google Cloud Console → the OAuth client → add the Pages origin (`https://<user>.github.io`) to Authorized JavaScript origins.
4. Push to `main` (or run the `pages` workflow manually) → site live in ~1 min.
5. Both phones: open the Pages URL → Share → Add to Home Screen. Sign in once.

## 7. Backups (~5 min, one-time)

```bash
sudo -u familyinc -i rclone config        # interactive: Google Drive remote named per RCLONE_REMOTE
sudo -u familyinc /opt/family-inc/deploy/backup.sh   # prove one green run
```

## 8. Acceptance watch (3 days — SPEC §11)

Both phones get the 07:30 digest 3 consecutive days; one done→recur cycle visible in `logs/reminders_log.csv`; then flip `BACKLOG.md` M3 and tag `v1-live`.

**Day-to-day:** code changes reach the box only via `deploy.sh`. No digest by 08:00 → runbook in `ENGINEERING.md` §8.
