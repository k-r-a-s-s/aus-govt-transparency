#!/usr/bin/env bash
# Idempotent environment check, run at the start of every Ralph iteration (local and cloud).
# Creates .venv if missing, reinstalls when the requirements change, and checks that v1's
# disclosures.db is untouched (AC-0.2). Exit 1 means stop and fix before doing anything else.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

sha256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }
V1_SHA=5e6a18cc80a7123276e8aa3d229a370733cd9aeec5f983706e77b85199ae5079

if [ ! -x .venv/bin/python ]; then
  echo "bootstrap: creating .venv"
  python3 -m venv .venv
fi
stamp=.venv/.ralph-requirements-sha
want=$(cat requirements.txt requirements-dev.txt | sha256 | cut -d' ' -f1)
if [ "$(cat "$stamp" 2>/dev/null || true)" != "$want" ]; then
  echo "bootstrap: installing requirements-dev.txt"
  .venv/bin/pip install -q --upgrade pip >/dev/null
  .venv/bin/pip install -q -r requirements-dev.txt
  echo "$want" > "$stamp"
fi

branch=$(git rev-parse --abbrev-ref HEAD)
echo "bootstrap: branch $branch at $(git log --oneline -1)"
echo "bootstrap: uncommitted paths: $(git status --porcelain | wc -l | tr -d ' ')"
echo "bootstrap: cloud session: ${CLAUDE_CODE_REMOTE:-false}"
if [ "$branch" = main ] || [ "$branch" = HEAD ]; then
  echo "bootstrap: on '$branch'. Work on v2-upgrade (local) or a claude/* branch (cloud), never main or a detached HEAD."
  exit 1
fi
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && [[ "$branch" != claude/* ]]; then
  echo "bootstrap: cloud session on '$branch'. Create your own branch first: git switch -c claude/ralph-$(date +%Y%m%d)"
  exit 1
fi
if [[ "$branch" == claude/* ]]; then
  echo "bootstrap: push rule: push this claude/* branch after every commit (git push -u origin HEAD)"
else
  echo "bootstrap: push rule: do NOT push (branch $branch; Kevin pushes)"
fi
if [ "$(sha256 disclosures.db | cut -d' ' -f1)" = "$V1_SHA" ]; then
  echo "bootstrap: v1 disclosures.db unchanged (AC-0.2)"
else
  echo "bootstrap: v1 disclosures.db CHANGED. Restore it with 'git checkout -- disclosures.db' and find out what wrote it."
  exit 1
fi
if [ -f disclosures_v2.db ]; then
  echo "bootstrap: disclosures_v2.db present"
else
  echo "bootstrap: disclosures_v2.db missing (gitignored). Rebuild it as AGENTS.md 'Rebuild the DB' says before any task that reads it."
fi
