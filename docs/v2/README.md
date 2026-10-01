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
| `disclosures/extract_gemini.py` | Extractor B `gemini-api`: chunked, schema-constrained Gemini extraction (ADR-5) |
| `disclosures/gemini_model.py` | `resolve_gemini_model()`: the one Gemini model-id resolver (bans 0.x-2.x ids) |
| `.claude/workflows/extract-disclosures.js` | Extractor A `workflow-claude`: Claude Code Workflow script (ADR-5) |
| `docs/v2/extraction.md` | how to run both extractors |
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

## Commands implemented so far (Phases 1 and 2a)

```sh
python -m disclosures --help
python -m disclosures validate <file-or-dir> [...]          # exit 1 if any file invalid
python -m disclosures extract --source gemini [--model ID] [--out-root extractions/gemini-api] \
    [--chunk-pages 20] [--max-retries 4] [--force] <pdfs...>   # see docs/v2/extraction.md
python -m disclosures score --pred <dir> --gold eval/gold [--json out.json]
python -m disclosures score --v1 disclosures.db --gold eval/gold [--json eval/v1_baseline.json]
python -m disclosures.schema --write | --check              # regenerate / check the JSON Schema
python -m disclosures.gold stats [--force]                  # eval/pdf_stats.csv
python -m disclosures.gold select --seed 20261001 --n 12    # eval/gold/selection.json
python -m disclosures.gold review-sheet                     # eval/gold/review.csv
python -m disclosures.gold apply-review                     # mark fully-ticked gold files reviewed
```

`scrape, load, entities, export, refresh` are registered stubs (exit 2) until their phase.
The workflow arm (`extract-disclosures`) runs through the Claude Code Workflow tool, not the CLI; see `docs/v2/extraction.md`.

Extraction files live at `extractions/<source_id>/<chamber>/<parliament>/<pdf_stem>.json`.
