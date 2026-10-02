# Disclosures v2

v2 is built alongside v1 (`src/`, `disclosures.db`), which is frozen until Phase 5.
Spec: `plans/2026-10-01-disclosures-v2/SPEC.md`.

## Layout

| Path | What |
|---|---|
| `disclosures/` | v2 package; CLI `python -m disclosures <command>` (`cli.py`) |
| `disclosures/schema.py` | Pydantic v2 extraction contract (ADR-2) |
| `schema/extraction.schema.json` | JSON Schema generated from `schema.py` (committed; a test keeps it in sync) |
| `disclosures/validate.py` | contract + completeness validation |
| `disclosures/normalise.py` | entity-name normalisation (ADR-6 step 1) |
| `disclosures/score.py` | scoring harness (ADR-4) |
| `disclosures/gold.py` | PDF stats, gold selection, review sheet |
| `disclosures/extract_gemini.py` | Extractor B `gemini-api`: chunked, schema-constrained extraction (ADR-5); `GenaiBackend` transport |
| `disclosures/openrouter.py` | OpenRouter transport for extractor B (native PDF + strict json_schema; any vendor's model for the bake-off) |
| `disclosures/gemini_model.py` | `resolve_gemini_model()`: the one Gemini model-id resolver (bans 0.x-2.x ids) |
| `disclosures/load.py` | loader: validated extractions -> `disclosures_v2.db` (ADR-7); see `docs/v2/loading.md` |
| `disclosures/sources.py` | House register URLs (43rd–48th), browser-UA HTTP with retries, listing parser (fixtures in `tests/fixtures/aph/`) |
| `disclosures/manifest.py` | `pdfs/manifest.csv` (ADR-8): one row per tracked PDF; `python -m disclosures.manifest --backfill [--html-dir DIR]` rebuilds it, matching source_url/listed_date from the 43rd–47th archive listings |
| `disclosures/entities.py` | entity standardisation (ADR-6); see `docs/v2/entities.md` |
| `data/entities/` | committed entity inputs: generic terms, curated aliases, ASX exclusions, LLM cache |
| `data/reference/` | ASX listed-companies snapshots (`entities --fetch-asx`) |
| `data/overrides/` | member identity + party-per-term CSVs carried forward from v1 (see its `README.md`) |
| `scripts/seed_v2_overrides.py` | one-off: regenerate / `--check` `data/overrides/` from v1 assets (read-only) |
| `.claude/workflows/extract-disclosures.js` | Extractor A `workflow-claude`: Claude Code Workflow script (ADR-5) |
| `docs/v2/extraction.md` | how to run both extractors |
| `docs/v2/loading.md` | what `load` does: member resolution, item ids, AC-2.7 queries |
| `disclosures/prompts/extract.md` | shared extraction instructions (gold drafters and extractors) |
| `eval/` | gold set, PDF stats, baselines (see `eval/README.md`) |
| `plans/2026-10-01-disclosures-v2/` | `SPEC.md` (plan), `DECISIONS.md` (decision log), `HANDOFF.md` (current state, next action) |
| `tests/` | pytest suite (no network, no API calls) |

## Setup and tests

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

## Commands implemented so far (Phases 1, 2a and 2c)

```sh
python -m disclosures --help
python -m disclosures validate <file-or-dir> [...]          # exit 1 if any file invalid
python -m disclosures extract --source gemini [--provider auto|gemini|openrouter] [--model ID] \
    [--provider-order google-ai-studio/flex] [--ignore-providers azure] [--fallback-model ID] [--workers 4] [--out-root extractions/<source-id>] \
    [--chunk-pages 20] [--max-retries 4] [--force] <pdfs...>   # see docs/v2/extraction.md
python -m disclosures score --pred <dir> --gold eval/gold [--json out.json]
python -m disclosures score --v1 disclosures.db --gold eval/gold [--json eval/v1_baseline.json]
python -m disclosures load --source workflow-claude [--db disclosures_v2.db] \
    [--extractions extractions] [--overrides data/overrides]   # see docs/v2/loading.md
python -m disclosures entities [--offline] [--db disclosures_v2.db] [--data data/entities]   # after load; docs/v2/entities.md
python -m disclosures entities --fetch-asx    # new ASX snapshot into data/reference/, then stop
python -m disclosures entities --draft-candidates [CSV] [--top 200]   # curation worksheet, then stop
python -m disclosures entities --offline --report [MD]   # also refresh eval/entities_report.md (AC-3.3/3.4/3.6)
python -m disclosures entities --g3-review [CSV]   # G3 review pack -> eval/entities_g3_review.csv, then stop
python -m disclosures entities --llm-dry-run   # long-tail blocks / uncached / requests, then stop
python -m disclosures entities [--llm-limit N] [--workers 8]   # online: LLM for uncached blocks (paid, OpenRouter)
python -m disclosures.schema --write | --check              # regenerate / check the JSON Schema
python -m disclosures.gold stats [--force]                  # eval/pdf_stats.csv
python -m disclosures.gold select --seed 20261001 --n 12    # eval/gold/selection.json
python -m disclosures.gold review-sheet                     # eval/gold/review.csv
python -m disclosures.gold apply-review                     # mark fully-ticked gold files reviewed
```

`scrape, export, refresh` are registered stubs (exit 2) until their phase.
The workflow arm (`extract-disclosures`) runs through the Claude Code Workflow tool, not the CLI; see `docs/v2/extraction.md`.

Extraction files live at `extractions/<source_id>/<chamber>/<parliament>/<pdf_stem>.json`.
