# Ralph loop: Disclosures v2, attachment fix → Phases 3–5. One task per iteration.

You are one iteration of a loop. Treat this iteration as if you have no memory of earlier
ones, even if this conversation shows them: the files on disk and git history are the only
trustworthy state. Re-read the files below every time. Do exactly ONE task, prove it, commit
it, report, then end your turn.

Plan folder: `plans/2026-10-02-ralph-phases-3-5/` (written as `$P/` below).

## 0. Orient (every iteration, in this order)
0a. Run `bash scripts/ralph/bootstrap.sh`. If it exits non-zero, fix that first (it's then the task).
0b. Study `$P/AGENTS.md` (how to run things, files you never touch).
0c. Run `python3 scripts/ralph/status.py`. If its last line starts `RALPH-STATUS: STOP`, go to step 6.
    If it prints `PLAN-ERROR`, repair `$P/IMPLEMENTATION_PLAN.md`'s format; that's your task.
0d. Study the task it names (`next=<ID>`): its whole block in `$P/IMPLEMENTATION_PLAN.md`, the
    `$P/SPEC-DELTA.md` sections it cites, and only the parts of
    `plans/2026-10-01-disclosures-v2/SPEC.md` (ADRs, ACs) it cites. Read `tail -n 20 $P/PROGRESS.md`.
0e. If `git status` shows uncommitted changes, they're probably an earlier iteration's
    unfinished work on this task. Inspect them. Keep and finish them if they're sound. Discard
    only code or data paths that clearly belong to that failed attempt. Never discard or revert
    anything under `plans/`, `scripts/ralph/`, `tests/` or `data/`: if it isn't yours,
    commit it as-is (`ralph <ID>: commit pre-existing changes`) before starting.

## 1. Claim the task
Increment its `- attempts:` line. If attempts is now 4 or more, don't try again. Set
`- status: blocked (agent): <what keeps failing, what you tried, what would unblock it>`,
log it (step 5), commit, and go to step 6.

## 2. Search before you build
Don't assume it's not implemented. Search the codebase first (grep, or a read-only subagent for
wide sweeps) for existing code, tests, CLI flags, data files and partial work from earlier
attempts. Reuse what exists (`disclosures/normalise.py`, `load.member_slug`,
`openrouter.py`, `validate.py`, test fixtures) rather than writing a second version.

## 3. Do the task, completely
- Implement it fully. Placeholders and stubs waste effort and time redoing the same work.
- Stay inside the task. If you find an unrelated bug, add a task or a `notes:` line in the plan.
  Fix it now only if it blocks this task.
- Paid calls (OpenRouter) only when the task's `budget:` allows them. Run
  `python3 scripts/ralph/credit.py --min 3` before each paid command, and follow SPEC-DELTA D4
  (caps, blocking on low credit). Never change the G2 models.
- Long commands: every Bash call must finish within 10 minutes (`timeout: 600000`). Use the
  batch sizes in AGENTS.md; the extractor is idempotent, so re-run it rather than waiting.
- Network failure on a host the task needs: retry once, then block the task `(network)` with the
  exact command Kevin should run locally. Don't loop on it.
- Need human judgment the plan doesn't give you? Write the question into the task, set it
  `blocked (kevin): <question>`, and move on (step 5). Never mark an `owner: kevin` task done
  yourself, unless Kevin's own message in this conversation explicitly approves it. In that
  case, quote his words in the task's notes.
- Capture the why: when you make a design choice SPEC-DELTA doesn't settle, add a dated entry to
  `plans/2026-10-01-disclosures-v2/DECISIONS.md`.

## 4. Prove it (backpressure)
Run every command in the task's `done when:` and the always-checks at the top of the plan
(full test suite green, v1 sha unchanged, no secrets, plan still parses). If anything fails,
fix it and re-run. Never commit a red test suite. If you can't get to green this iteration,
write what's wrong under the task's `notes:`, leave its status `todo`, revert code you can't
finish, and commit only the plan note.

## 5. Record and commit
- In the task block, set `- status: done <YYYY-MM-DD>`, update `spent:` for paid tasks, and add
  key numbers to `notes:` (keep it short, and prune old notes).
- Append ONE line to `$P/PROGRESS.md`:
  `<UTC timestamp> | <ID> | done/blocked/partial | spent US$x.xx | <one-line result or blocker>`
- Learned how to run something, or hit a gotcha? Add at most 2 lines to `$P/AGENTS.md`.
  Never progress notes there.
- `git status`, then `git add` the specific paths, then `git commit -m "ralph <ID>: <summary>"`.
  Never add `.env*`, `*.db` (except `site/disclosures_v2.db` from T5.2), `.venv/` or `.ralph/`.
- Push only if the current branch starts with `claude/` (a cloud session's branch; bootstrap
  prints the push rule): `git push -u origin HEAD`. On any other branch, don't push. If a push
  is refused (e.g. a token without `workflow` scope for `.github/workflows/`), keep the commit
  and block the task `(kevin): push from a local clone`.

## 6. Report and end the turn
Run `python3 scripts/ralph/status.py` and print its last line verbatim. That is the last thing
you do.
- `CONTINUE`: end your turn now. Don't start the next task: the loop starts a fresh iteration.
- `STOP`: update `plans/2026-10-01-disclosures-v2/HANDOFF.md`: what's done, what's waiting on
  Kevin with the exact steps he must take, open questions, and credit remaining. Commit (and
  push if on `claude/*`). On a `claude/*` branch, open a PR against `v2-upgrade` if this branch
  has none (if you can't, say so in HANDOFF). Then print `RALPH-STATUS: STOP …` again, followed
  by `<promise>RALPH_STOP</promise>`. That tag is only for the optional `ralph-wiggum` plugin;
  `loop.sh` and `/goal` go by status.py. Output it only when status.py printed STOP in this
  iteration. Never output it to escape a hard task; that would be lying.

## Never
Write `disclosures.db` (v1); edit `eval/gold/*.json`; print or commit secrets; push to
`v2-upgrade`/`main`, force-push or rewrite history; enable Pages, upload to Kaggle, post
anywhere or open issues; weaken a SPEC acceptance criterion to make a check pass; work more
than one task per iteration.
