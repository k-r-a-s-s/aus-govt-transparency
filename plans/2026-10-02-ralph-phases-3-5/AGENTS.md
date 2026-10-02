# AGENTS.md — how to run things (operational only; progress goes in IMPLEMENTATION_PLAN.md / PROGRESS.md)

Repo root is the working directory. Python is `.venv/bin/python` (`bash scripts/ralph/bootstrap.sh` makes it).

## Every iteration
- `bash scripts/ralph/bootstrap.sh`: venv, requirements, v1 sha check (AC-0.2). It exits 1 if v1 changed.
- `python3 scripts/ralph/status.py`: the next task, or STOP. `python3 scripts/ralph/credit.py --min 3` before any paid call.
- Tests: `.venv/bin/python -m pytest -q` (no network, no API calls in tests, ever; use recorded fixtures).

## Rebuild the DB (gitignored; rebuild whenever it's missing or extractions changed)
- `.venv/bin/python -m disclosures load --source gemini-api` (once the Senate lands: `--source gemini-api --source senate-json`), then `.venv/bin/python -m disclosures entities --offline` once that exists.
- AC-2.8 id hash, same method as the baseline: `.venv/bin/python -c "import sqlite3,hashlib;print(hashlib.sha1('\n'.join(r[0] for r in sqlite3.connect('disclosures_v2.db').execute('select item_id from items order by 1')).encode()).hexdigest())"`; baseline `f69d40da…`.
- AC-2.7/2.9 queries: `docs/v2/loading.md`. `validate`: `.venv/bin/python -m disclosures validate extractions/gemini-api/house`.

## G2 extract command (the only allowed extraction config; paid)
```sh
.venv/bin/python -m disclosures extract --source gemini --provider openrouter \
  --model google/gemini-3.8-flash --provider-order google-ai-studio/flex \
  --fallback-model anthropic/claude-sonnet-5.5 --ignore-providers azure --workers 8 \
  <≤ 20 pdf paths> 2>&1 | tee -a .ralph/extract.log
```
- It skips files that are already valid (idempotent); `--force` redoes them. It writes each file atomically, so a killed batch loses only in-flight PDFs.
- Each Bash call must finish in < 10 min: pass `timeout: 600000` and keep batches ≤ 20 PDFs (≤ 10 for the scanned 43rd–45th).
- Cost guide: typed PDF ≈ US$0.03; one with a Sonnet fallback chunk (Gemini RECITATION) ≈ US$0.16. RECITATION hits 20–25% of the scanned 43rd–45th, ≈ 2% of the typed ones. The summary line prints US$ per file and per run.
- zsh doesn't word-split `$VAR`: inline the paths or use `${=VAR}`. Bash is fine.

## Network
- APH (`www.aph.gov.au`, `static.aph.gov.au`, `interests-register-api-public.aph.gov.au`) and ASX block requests with no User-Agent (WAF 403). Always send:
  `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36`
- Senate API: `https://pbs-apim-aqcdgxhvaug7f8em.z01.azurefd.net/api` (from `/js/apps/senators-interests-register/build/env.js`); send `Origin: https://www.aph.gov.au`.
- If a host fails in a cloud session (proxy/allowlist), don't loop on it. Block the task `(network)` with the exact command for Kevin to run locally.

## Secrets and files never to touch
- Never print, cat or commit `.env.local` or any key. `credit.py` reads the key without printing it.
- Never write `disclosures.db` (v1), `eval/gold/*.json`, or `pdfs/{43..47}/*.pdf`. `src/` stays until T5.4.
- Read v1 read-only: `sqlite3.connect('file:disclosures.db?mode=ro', uri=True)`.
- Secrets check without choking on PDFs: `git grep -I -nE 'AIza[0-9A-Za-z_-]{30,}|sk-or-v1-[0-9a-f]{20,}' -- ':!pdfs' ':!*.db'`.
- `.gitignore` ignores `*.db`, `*.log`, and names containing token/secret/credential/apikey. Don't name files that way.
- Scratch output: `.ralph/scratch/` (gitignored). Logs: `.ralph/`.

## Git
- One commit per task: `git add` the specific paths (check `git status` first), then `git commit -m "ralph <ID>: <summary>"`.
- Push only when the branch starts with `claude/` (cloud sessions; bootstrap prints the rule): `git push -u origin HEAD` after each commit. Any other branch: don't push.
- Never push to `v2-upgrade`/`main`, force-push, rewrite history, or `git reset --hard` over uncommitted work you didn't make.

## Known quirks
- No poppler, so the Read tool can't render PDF pages. Render with PyMuPDF instead: `pymupdf.open(pdf)[n-1].get_pixmap(dpi=90).save(".ralph/scratch/x.png")`, then Read the PNG.
- `tests/test_load.py::test_unwritable_target_exits_2` fails as root (cloud) until T0.1 skips it.
- `load` exits 1 (but still installs the DB) if a hard AC-2.7 query isn't 0. Treat exit 1 as a failure.
- Docs to keep current when behaviour changes: `docs/v2/README.md` (commands), `docs/v2/<topic>.md`, `data/overrides/README.md`.
