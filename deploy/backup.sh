#!/usr/bin/env bash
# Family inc. — weekly backup (Sun 03:00 timer): tar bridge/state (incl. the
# Baileys auth_state that avoids re-pairing after a rebuild) + logs/ → Drive
# via rclone. Remote name comes from /etc/family-inc/env (RCLONE_REMOTE);
# `rclone config` is a one-time interactive step — deploy/README.md step 7.
set -euo pipefail
cd /opt/family-inc

REMOTE="${RCLONE_REMOTE:-gdrive:family-inc-backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-90}"
STAMP="$(date +%F)"
TARBALL="/tmp/family-inc-${STAMP}.tar.gz"

tar czf "$TARBALL" automation/bridge/state logs
rclone copy "$TARBALL" "$REMOTE" --quiet
rm -f "$TARBALL"
rclone delete "$REMOTE" --min-age "${KEEP_DAYS}d" --quiet || true  # prune; never fail the backup over it
echo "backup ${STAMP} → ${REMOTE} (pruned >${KEEP_DAYS}d)"
