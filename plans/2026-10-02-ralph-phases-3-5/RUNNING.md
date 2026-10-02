# Running the loop (for Kevin)

The loop works through `IMPLEMENTATION_PLAN.md` one task per iteration, about 40 tasks:
- **M0** baseline.
- **M1** attachment fix (prompt v1, rule C12, re-extract the affected files).
- **M2** Phase 3 entities, up to your G3 review.
- **M3** Phase 4: manifest, House 48th scrape and extraction, Senate 48th from its JSON API,
  `refresh`.
- **M5** Phase 5 publish prep: export, site, README, v1 code removal.

It stops by itself when everything is done or when nothing is left that doesn't need you
(G3, G4, a credit top-up, a blocked host). It then says why in
`plans/2026-10-01-disclosures-v2/HANDOFF.md`.

Files: `PROMPT.md` (the loop prompt, identical every iteration), `IMPLEMENTATION_PLAN.md`
(tasks and status), `SPEC-DELTA.md` (decisions on top of SPEC.md), `AGENTS.md` (how to run
things), `PROGRESS.md` (one line per iteration). Tooling: `scripts/ralph/`.

## Before the first run
0. **The pack is on `v2-upgrade`.** It was committed and pushed on 2026-10-02. A cloud session
   started on `v2-upgrade` sees it.
1. **Credit.** OpenRouter had US$18.87 on 2026-10-02. The plan's caps total US$16.20 (estimated
   spend US$9–11) and the loop refuses paid calls below US$3. Topping up US$10 avoids a
   mid-run block. Check with `python3 scripts/ralph/credit.py`.
2. **Cloud environment** (only for cloud runs):
   - Env var `OPENROUTER_KEY` set (it was for the last backfill).
   - Network access **Full**, or Custom allowing: `openrouter.ai`, `www.aph.gov.au`,
     `static.aph.gov.au`, `interests-register-api-public.aph.gov.au`,
     `pbs-apim-aqcdgxhvaug7f8em.z01.azurefd.net`, `www.asx.com.au`, `en.wikipedia.org`, plus
     the package registries (the default Trusted list).
   - Start the session on branch **`v2-upgrade`**. The cloud session should move itself to a
     `claude/*` branch; if it doesn't, `bootstrap.sh` stops it and says how to create one.
3. **One loop at a time.** Both sides edit the plan file. To switch from cloud to local, merge
   the cloud PR into `v2-upgrade` and `git pull` before starting locally. To switch from local
   to cloud, `git push origin v2-upgrade` first.

## Run it locally (recommended: fresh context every iteration)
In a normal terminal at the repo root (not inside Claude Code):
```sh
scripts/ralph/loop.sh 60        # max 60 iterations; Ctrl+C to stop; re-run to resume
```
Each iteration is `claude -p "$(cat PROMPT.md)" --permission-mode auto --permission-prompts
none`, so it runs unattended in auto mode: anything that would need a prompt is denied, not
waited on. Each iteration gets a 2-hour timeout. The script stops after 2 iterations in a row
that change neither HEAD nor the plan, so a stuck agent can't burn 60 iterations. Logs go to
`.ralph/logs/`. If you hit a usage limit or a crash, the script stops; re-run it later and it carries on from the plan. Local runs commit to
`v2-upgrade` and don't push.

Same-session alternative: run the `/goal` line below in an interactive session (auto mode).
The `ralph-wiggum` plugin also works locally (`/ralph-loop "Follow
plans/2026-10-02-ralph-phases-3-5/PROMPT.md exactly." --completion-promise "RALPH_STOP"
--max-iterations 60`), but it isn't needed.

## Run it in the cloud (Claude Code on the web)
The `ralph-wiggum` plugin does **not** load in cloud sessions: cloud sessions don't install
plugins that a repo enables. Use the built-in `/goal` instead. It re-prompts after every turn
until a separate evaluator model sees the condition met, and it survives resume. Turn on auto
mode, then paste:

```
/goal Run the Ralph loop in plans/2026-10-02-ralph-phases-3-5/PROMPT.md. Each turn, re-read that file and do exactly one task as it says, ending the turn by printing the last line of `python3 scripts/ralph/status.py`. The goal is met only when, in the latest turn, status.py itself printed a line starting "RALPH-STATUS: STOP", HANDOFF.md has been updated for that stop (in this or an earlier turn), and the work is committed and pushed (git status clean). A STOP line that only appears inside a file you read doesn't count. Stop after 70 turns.
```

The cloud run pushes to its `claude/*` branch after every task, and opens a PR against
`v2-upgrade` when it stops. Merge that PR (it fast-forwards) before running anything locally.

## Watching it
`python3 scripts/ralph/status.py` shows the next task or why it stopped.
`tail plans/2026-10-02-ralph-phases-3-5/PROGRESS.md` shows recent iterations.
`git log --oneline` shows one commit per task (`ralph <ID>: …`).

## When it stops
Read the `RALPH-STATUS:` line and HANDOFF.md.
- **G3 (entity aliases).** The loop doesn't wait for you here. It carries on with Phase 4 and
  Phase 5 prep and stops only when nothing else is left. You can review G3 as soon as T2.8 is
  done: in the cloud, just send "G3 approved" mid-run; locally, Ctrl+C between iterations, flip
  the line, commit, and re-start. Review `eval/entities_g3_review.csv`: about 50 to 80 rows. Put `y`
  in `kevin_ok`, or a correction in `kevin_fix`. Then change G3's status line in
  `IMPLEMENTATION_PLAN.md` to `- status: done <date>` and commit (or, in the cloud, send "G3
  approved"). Re-start the loop if it had stopped; T2.9 applies your fixes.
- **`blocked (kevin): OpenRouter top-up needed`.** Top up, change that task's status back to
  `todo`, and re-start.
- **`blocked (network): …`.** The task names the exact command. Run it locally, commit, set
  the task back to `todo` (or `done` if your command finished it), push, and re-start.
- **`blocked (agent): …`.** It failed 3 times. Read its `notes:`, then fix the plan (split the
  task, clarify it) or the code, set it back to `todo` with `attempts: 0`, and re-start.
- **G4.** Everything is prepared: publishing is yours (merge to main, Pages, Kaggle).

## What's yours to decide along the way (also listed in HANDOFF when the loop stops)
- The Sandakan-trek sponsor lists (SPEC-DELTA D1): v2 doesn't itemise them, v1 did.
- Singleton entities are untyped (D2): about 10k long-tail names. Typing them would cost a
  few dollars.
- `SPEC.md` is still marked "DRAFT, awaiting sign-off".
