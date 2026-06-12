#!/usr/bin/env bash
# D-030 publication rewrite — strip personal paths + redact strings from ALL
# history, verify, force-push. Runs on the PO's Mac, never the VPS, and only
# while the repo is still PRIVATE. Full sequence: deploy/README.md §6.
#
# Needs: git-filter-repo (brew install git-filter-repo) and seeds/redact.txt
# (gitignored — lives only on PO machines + backups; it carries the strings it
# removes, so it can never be committed).
set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)
PATHS_FILE="$REPO_ROOT/deploy/publish_paths.txt"
REDACT_FILE="$REPO_ROOT/seeds/redact.txt"
ORIGIN_URL=$(git -C "$REPO_ROOT" remote get-url origin)

command -v git-filter-repo >/dev/null || { echo "missing git-filter-repo — brew install git-filter-repo"; exit 1; }
[ -f "$PATHS_FILE" ]  || { echo "missing $PATHS_FILE"; exit 1; }
[ -f "$REDACT_FILE" ] || { echo "missing seeds/redact.txt — it lives only on PO machines; restore from backup"; exit 1; }

WORK=$(mktemp -d /tmp/family-inc-publish.XXXXXX)
cp "$PATHS_FILE" "$WORK/paths.txt"
cp "$REDACT_FILE" "$WORK/redact.txt"

echo "==> fresh mirror clone of $ORIGIN_URL"
# --no-local: keeps the clone "fresh" in filter-repo's eyes even for a
# local-path origin (no-op for the real https origin)
git clone --quiet --no-local --mirror "$ORIGIN_URL" "$WORK/repo.git"
cd "$WORK/repo.git"

echo "==> rewriting history (filter-repo)"
git filter-repo --invert-paths --paths-from-file "$WORK/paths.txt" --replace-text "$WORK/redact.txt"

echo "==> gauntlet 1/2: every stripped path absent from every ref"
fail=0
while IFS= read -r p; do
  case "$p" in \#*|"") continue;; esac
  if git log --all --oneline -- "$p" | grep -q .; then echo "FAIL path still in history: $p"; fail=1; fi
done < "$WORK/paths.txt"

echo "==> gauntlet 2/2: every redaction LHS absent from every blob of every ref"
ALL_REVS=$(git rev-list --all)
while IFS= read -r line; do
  case "$line" in \#*|""|regex:*) continue;; esac
  needle="${line%%==>*}"
  if git grep -q -F -- "$needle" $ALL_REVS 2>/dev/null; then echo "FAIL string still present: $needle"; fail=1; fi
done < "$WORK/redact.txt"

if [ "$fail" != 0 ]; then
  echo "VERIFY FAILED — nothing pushed. Rewritten repo left for inspection at $WORK/repo.git"
  exit 1
fi

echo "==> verify clean ($(git rev-list --count HEAD) commits kept)."
read -r -p "Force-push rewritten history to $ORIGIN_URL? [y/N] " a
if [ "${a:-n}" != "y" ]; then
  echo "aborted — rewritten repo left at $WORK/repo.git, origin untouched"
  exit 1
fi
# filter-repo strips the origin remote (its accidental-push guard) — restore it
git remote add origin "$ORIGIN_URL" 2>/dev/null || git remote set-url origin "$ORIGIN_URL"
git push --quiet --force origin 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'
cd / && rm -rf "$WORK"
echo "==> pushed. Every existing clone is now orphaned — continue with deploy/README.md §6 steps 2–5 (re-point VPS, fresh-clone the Mac, flip public, Pages)."
