# Final acceptance sweep: SPEC §3, AC-0 to AC-5 (T5.6, 2026-10-03)

Branch `claude/ralph-proxmox` at 85eace2 + this commit. Rebuilt from committed inputs first:

```sh
.venv/bin/python -m disclosures load --source gemini-api --source senate-json   # 995 files, 50,936 items, exit 0
.venv/bin/python -m disclosures entities --offline                              # 11,542 entities, exit 0
.venv/bin/python -m disclosures export --site site                              # 50,936 rows, exit 0
```

`site/disclosures_v2.db` is byte-identical to the rebuilt `disclosures_v2.db` (`cmp`). The rebuild
changed only the entity count (11,544 → 11,542, V2's curated ticker fixes) and the load timestamp
in `site/index.html` and `exports/kaggle/README.md`. AC-2.8 item-id hash (sha1, AGENTS.md method):
`88fb48c0…` before and after the reload.

Every row passes. The only "Kevin" item is G4 itself (publishing), which AC-5.6 says the build
must leave alone.

| AC | Check run | Result | Status |
|---|---|---|---|
| AC-0.1 | `pytest -q`; tests per module | 322 passed, 1 skipped (`test_cli.py` empty param set). Tests cover schema, validate, score, extract-gemini (mocked), load, entities, scrape (recorded HTML), export, plus sources, manifest, members, senate, refresh, openrouter | pass |
| AC-0.2 | `sha256sum disclosures.db` | `5e6a18cc…5079` (unchanged) | pass |
| AC-0.3 | `python -m disclosures --help` | `scrape, extract, validate, score, load, entities, export, refresh` | pass |
| AC-0.4 | `git ls-files pdfs \| wc -l` | 1,003 (925 House PDFs + manifest + 77 Senate JSON) ≥ 774 | pass |
| AC-0.5 | `git grep -I -nE 'AIza…\|sk-or-v1-…' -- ':!pdfs' ':!*.db'` | no match (exit 1) | pass |
| AC-1.1 | `tests/test_schema.py::test_committed_schema_matches_models_byte_for_byte` | passes | pass |
| AC-1.2 | `eval/gold/selection.json`; `tests/test_gold_selection.py` (3 strata tests) | 12 PDFs with seed and strata; tests pass | pass |
| AC-1.3 | `validate eval/gold`; `reviewed_by`; `review.csv` | 12 valid, 0 invalid; all `reviewed_by == "kevin"`; `review.csv` present | pass |
| AC-1.4 | `score --pred eval/gold --gold eval/gold` | P = R = F1 = 1.000; owner, change_type, is_alteration, page, lodged_date all 1.000 | pass |
| AC-1.5 | `tests/test_score.py` (`test_hand_built_exact_prf`, `test_single_error_cases`, `test_wrong_owner_…`) | pass | pass |
| AC-1.6 | `score --v1 disclosures.db --gold eval/gold --json <scratch>` | runs; section-ignored P 0.856 / R 0.625 (committed `eval/v1_baseline.json` same shape) | pass |
| AC-1.7 | `tests/test_validate.py` (`pages_covered` gap, `pdf_sha256 mismatch`) | pass; message names file and reason | pass |
| AC-2.1 | `.claude/workflows/extract-disclosures.js`; `docs/v2/extraction.md` | starts with literal `export const meta = {`; doc gives args shape, per-parliament waves, `/config` step | pass |
| AC-2.2 | gold files in `extractions/gemini-api`; mocked tests | all 12 gold stems present and valid; tests for chunk offsets → absolute page, max-tokens re-split, 1-page failure → no file + non-zero exit | pass |
| AC-2.2a | `resolve_gemini_model` tests; `git grep -nE 'gemini-(1\|2)\.[0-9]' -- disclosures/` | ban test passes; 0 matches in `disclosures/` (banned ids appear only in negative tests under `tests/`); DECISIONS records `gemini-3.8-flash` | pass |
| AC-2.3 | `validate extractions/workflow-claude/house` | 23 valid, 0 invalid; all 12 gold stems present | pass |
| AC-2.4 | `eval/bakeoff.md`; DECISIONS | per-arm + v1 metrics, cost lines, bar pass/fail, chosen arm gemini-api by the ADR-5 rule; DECISIONS has the model id and G2 | pass |
| AC-2.5 | `score --pred extractions/gemini-api --gold eval/gold` | P 0.986, R 0.987, F1 0.987; owner 1.000, page 1.000 (clears ADR-4 bar) | pass |
| AC-2.6 | `validate extractions/gemini-api/house`; `eval/extraction_failures.md` | 919 valid, 0 invalid = 768 (43–47) + 6 non-statements = 774, + 151 (48th); 0 failures | pass |
| AC-2.7 | `load` sanity queries | documents 995 = 919 + 76 valid files; bad section/owner/page 0; page > page_count 0; bad lodged_date 0; pre-2010 non-low 4 (all `grayg_43p`, listed in `eval/bakeoff.md`) | pass |
| AC-2.8 | item-id hash before/after `load` | `88fb48c0…` both times | pass |
| AC-2.9 | `select count(*) from member_terms where party is null` | 0; `unknown_party.csv` has 0 rows (header only) | pass |
| AC-2.10 | `tests/test_load.py` duplicate-MP table (Bowen et al.) | pass | pass |
| AC-3.1 | `tests/test_entities.py` (AC-3.1 on the DB); direct query | every group occurs and resolves to 1 entity: CBA 1,618 items, NAB 1,115, ANZ 687, Qantas 1,592, Virgin 452, Westpac 970, Telstra 240 (raw-name matches) | pass |
| AC-3.2 | `entities` coverage line; `tests/test_entities.py` AC-3.2 | every row typed; top-200 coverage 15,502/15,865 = 97.7% | pass |
| AC-3.3 | `entities --offline` | non-generic named items without an entity: 0 | pass |
| AC-3.4 | `entity_aliases` by method; listed codes vs snapshot | curated 531, asx 293, generic 7 (plus llm 4,732, singleton 7,129); 266 `listed_company` entities, all with a code in `data/reference/asx_listed_companies_2026-10-02.csv` | pass |
| AC-3.5 | DECISIONS.md | "G3 — entity spot-check: approved (2026-10-03)", 114 rows, 0 fixes | pass |
| AC-3.6 | `eval/entities_report.md` top-20 vs live DB | report's v2 top 20 equals the live query row for row; no two rows are the same organisation (by inspection) | pass |
| AC-4.1 | `disclosures/sources.py`; `tests/test_sources.py::test_ac_4_1_48th_rows` | 43–47 archive URLs (47th slug present), 48th current URL, browser UA on every request; test passes | pass |
| AC-4.2 | manifest rows for house/48 | 151 | pass |
| AC-4.3 | `tests/test_manifest.py::test_ac_4_3_…` | every tracked PDF has a row with a matching sha256; 1,001 rows, 997 with `source_url` | pass |
| AC-4.4 | `tests/test_scrape.py`, `tests/test_senate.py` ("0 new, 0 changed"); live run in T3.3a | second run logged `0 new, 0 changed` (T3.3a, re-checked by V3); no live re-run here (task is network: none) | pass |
| AC-4.5 | `tests/test_refresh.py` (one differing sha → that file; workflow source prints args) | pass | pass |
| AC-4.6 | `docs/v2/senate_source.md`; senate 48th distinct members | doc has endpoints, payload, sample, coverage; 76 | pass |
| AC-4.7 | house 48th distinct members | 151 | pass |
| AC-5.1 | `export`; row counts; dictionary | `exports/disclosures_v2.csv` 50,936 rows = items; `exports/kaggle/{csv,README.md,dataset-metadata.json}`; all 33 columns in the README dictionary | pass |
| AC-5.2 | `site/` files; `yaml.safe_load(pages.yml)`; `http.server` + curl | both files exist; YAML valid; served index contains the `lite.datasette.io` link, DB served 200 | pass |
| AC-5.3 | `grep -oE 'python -m disclosures [a-z]+' README.md \| sort -u` | 8 commands, all in the AC-0.3 list | pass |
| AC-5.4 | `src/`, `examples/`, `test_output.json`, `setup_pipeline.sh`; `git grep "from src\."` | all gone; overrides in `data/overrides/`; grep empty | pass |
| AC-5.5 | fresh venv install + pytest (T5.5, 2026-10-03) | install and `pip check` clean, freeze == pins, suite passes; requirements unchanged since | pass |
| AC-5.6 | `git log origin/{main,v2-upgrade} --grep '^ralph'`; Pages API; Kaggle | 0 ralph commits on either; `origin/main` still `dae1630` (2025-04-26); Pages API 404 (not enabled); Kaggle id is still the placeholder, nothing uploaded; work lives on `claude/ralph-proxmox` (PR #2 → `v2-upgrade`, open) | pass (G4: Kevin) |

Notes
- `git log origin/main..v2-upgrade` is non-empty (37 commits), as the AC expects; `git status` is
  clean after this commit.
- Open questions that don't affect any AC (Sandakan sponsors, untyped singletons) are in `HANDOFF.md`.
