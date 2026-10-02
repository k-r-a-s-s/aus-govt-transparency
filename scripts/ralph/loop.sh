#!/usr/bin/env bash
# Local fresh-context Ralph loop: one `claude -p` run per task, until status.py says STOP.
#
#   scripts/ralph/loop.sh [max_iterations]      # default 60
#
# Every iteration starts with an empty context and re-reads PROMPT.md from disk; state lives in
# IMPLEMENTATION_PLAN.md, PROGRESS.md and git. Logs: .ralph/logs/ (gitignored). Ctrl+C stops it;
# re-running picks up where it left off. See plans/2026-10-02-ralph-phases-3-5/RUNNING.md.
#
# Stops on: status.py STOP; 2 iterations in a row that change neither HEAD nor the plan file
# (no progress); a malformed plan that one iteration couldn't repair; claude exiting non-zero.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

PLAN_DIR=plans/2026-10-02-ralph-phases-3-5
MAX=${1:-60}
PERMISSION_MODE=${RALPH_PERMISSION_MODE:-auto}
ITER_TIMEOUT=${RALPH_ITER_TIMEOUT:-7200}   # seconds per iteration
TIMEOUT_BIN=$(command -v timeout || command -v gtimeout || true)
mkdir -p .ralph/logs

fingerprint() { echo "$(git rev-parse HEAD) $(cksum <"$PLAN_DIR/IMPLEMENTATION_PLAN.md")"; }
stalls=0
plan_errors=0

for ((i = 1; i <= MAX; i++)); do
  python3 scripts/ralph/status.py
  s=$?
  if [ $s -eq 3 ]; then echo "loop: STOP after $((i - 1)) iteration(s). See plans/2026-10-01-disclosures-v2/HANDOFF.md"; exit 0; fi
  if [ $s -eq 2 ]; then
    plan_errors=$((plan_errors + 1))
    if [ $plan_errors -ge 2 ]; then echo "loop: plan still malformed after a repair iteration; fix it by hand"; exit 2; fi
    echo "loop: plan malformed; giving the agent one iteration to repair it"
  elif [ $s -ne 0 ]; then
    echo "loop: status.py exited $s; stopping"; exit $s
  else
    plan_errors=0
  fi

  before=$(fingerprint)
  log=".ralph/logs/$(date +%Y%m%dT%H%M%S)-iter$i.jsonl"
  echo "loop: iteration $i/$MAX, log $log"
  ${TIMEOUT_BIN:+$TIMEOUT_BIN "$ITER_TIMEOUT"} claude -p "$(cat "$PLAN_DIR/PROMPT.md")" \
    --permission-mode "$PERMISSION_MODE" --permission-prompts none \
    --output-format stream-json --verbose >"$log" 2>&1
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "loop: claude exited $rc (usage limit, auth, timeout or crash?); see $log. Re-run this script to resume."
    exit $rc
  fi
  tail -n 1 "$log" | python3 -c 'import json,sys
try: r=json.loads(sys.stdin.read())
except Exception: sys.exit(0)
print("loop: result:", str(r.get("result",""))[-400:].replace("\n"," "))' || true

  if [ "$(fingerprint)" = "$before" ]; then
    stalls=$((stalls + 1))
    echo "loop: iteration $i changed neither HEAD nor the plan (stall $stalls/2)"
    if [ $stalls -ge 2 ]; then echo "loop: no progress in 2 iterations; stopping. Check $log and git status."; exit 1; fi
  else
    stalls=0
  fi
done
echo "loop: reached max iterations ($MAX). Re-run to continue."
