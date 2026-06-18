#!/usr/bin/env bash
# Family inc. — the only way code reaches the box (ENGINEERING §6).
# Run as familyinc: ssh familyinc@appliance /opt/family-inc/deploy/deploy.sh
# Red tests abort the deploy; running code is untouched.
set -euo pipefail
cd /opt/family-inc

git pull --ff-only
uv sync --frozen
(cd automation/bridge && npm ci --omit=dev)
(cd automation/finance && npm ci --omit=dev)   # bank scrapers (ENGINEERING §6) — was missing; M6.2 needs it
FAMILY_INC_SHEET_ID= uv run --frozen pytest -q   # empty, NOT -u: load_env "existing env wins" keeps the suite off the live Sheet (D-038); --frozen matches the documented appliance path
sudo /usr/bin/systemctl restart family-bridge   # the one whitelisted sudoers line
echo "deployed $(git rev-parse --short HEAD); timers pick up new code on next fire"
