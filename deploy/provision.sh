#!/usr/bin/env bash
# Family inc. — idempotent VPS provisioning (ENGINEERING §5). Run as root, once
# (reruns are safe). Debian/Ubuntu assumed. Secrets are NEVER touched here —
# step 4 of deploy/README.md places them by hand.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/AdarGit008/Family-Inc.git}"  # override: REPO_URL=… ./provision.sh
APP_DIR=/opt/family-inc
APP_USER=familyinc
NODE_MAJOR=22  # LTS

[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

echo "== 1. user + timezone"
id "$APP_USER" &>/dev/null || useradd -m -s /bin/bash "$APP_USER"
timedatectl set-timezone Asia/Jerusalem

echo "== 2. packages (git, curl, rclone, node ${NODE_MAJOR}.x, uv)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl ca-certificates rclone
if ! command -v node &>/dev/null || [ "$(node -v | cut -dv -f2 | cut -d. -f1)" -lt "$NODE_MAJOR" ]; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y -qq nodejs
fi
command -v uv &>/dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

echo "== 3. repo → ${APP_DIR}"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
sudo -u "$APP_USER" mkdir -p "$APP_DIR/logs" "$APP_DIR/Briefings" \
  "$APP_DIR/automation/bridge/state/inbox" "$APP_DIR/automation/bridge/state/outbox"

echo "== 4. dependencies"
(cd "$APP_DIR" && sudo -u "$APP_USER" uv sync --frozen)
(cd "$APP_DIR/automation/bridge" && sudo -u "$APP_USER" npm ci --omit=dev)

echo "== 4b. headed browser + Xvfb for the property scraper (M5/D-039, SPEC §12.1)"
# Kept OUT of the core lockfile (boring core; one runtime, D-018): the
# family-property unit runs via `uv run --with playwright`. OS libs need root;
# the browser binary is installed under the app user (where the unit looks).
# Idempotent — playwright skips an already-installed browser. Non-fatal: a
# failure here only disables the property lane, which then fails loud (§10.2).
# Xvfb + xauth give the HEADED Chromium a virtual display (D-039 anti-bot).
apt-get install -y -qq xvfb xauth \
  || echo "  [warn] xvfb/xauth install failed — headed scraping (D-039) disabled until fixed"
(cd "$APP_DIR" && uv run --with playwright python -m playwright install-deps chromium) \
  || echo "  [warn] playwright OS-deps install failed — property lane disabled until fixed"
(cd "$APP_DIR" && sudo -u "$APP_USER" uv run --with playwright python -m playwright install chromium) \
  || echo "  [warn] playwright chromium install failed — property lane disabled until fixed"

echo "== 5. secrets directory (files placed BY HAND — deploy/README.md step 3)"
install -d -m 700 -o "$APP_USER" -g "$APP_USER" /etc/family-inc
cat <<'EOF'
   /etc/family-inc/ expects (mode 600, owner familyinc):
     env                    ANTHROPIC_API_KEY, FAMILY_INC_SHEET_ID, SMTP_* (SPEC §10.2), review keys
     service-account.json   Google service account (Sheet editor)
     recipients.json        the two adult JIDs (bridge send scope)
     property_searches.json saved-search URLs (M5, §12.1; optional — see
                            deploy/property_searches.example.json)
EOF

echo "== 6. sudoers — the ONE whitelisted line (ENGINEERING §6)"
echo "$APP_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart family-bridge" > /etc/sudoers.d/familyinc
chmod 440 /etc/sudoers.d/familyinc
visudo -c -q

echo "== 7. systemd units (schedules are code — change via PR, not on the box)"
cp "$APP_DIR"/deploy/systemd/* /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now family-bridge.service \
  family-reminders.timer family-digest.timer family-summarizer.timer \
  family-weekly.timer family-backup.timer family-property.timer

echo "== done. Next: place secrets, pair Baileys (deploy/README.md steps 3–4)."
echo "   Until recipients.json + pairing exist, the bridge loops printing a QR — expected."
