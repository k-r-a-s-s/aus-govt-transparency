# Entities (ADR-6, Phase 3)

`python -m disclosures entities` groups the names on items (`items.entity_name_raw`) into
organisations. It writes `entities`, `entity_aliases` and `items.entity_id` in
`disclosures_v2.db`.

## Run order

Always run `load` first, then `entities`, on the same DB (`refresh` does both):

```sh
python -m disclosures load --source gemini-api            # rebuilds the DB, entity tables empty
python -m disclosures entities --offline                  # [--db disclosures_v2.db] [--data data/entities] [--reference data/reference]
python -m disclosures entities --fetch-asx                # download a new ASX snapshot, then stop
python -m disclosures entities --draft-candidates          # curation worksheet (below), then stop
```

`entities` rewrites the three outputs in place, in one transaction, so re-running it is safe.
It reads only committed files, so two runs give identical tables (tested). It prints, per
method, how many aliases and items resolved that way. It also prints the AC-3.3 count: named,
non-generic items that have no entity. That count must be 0, and the command exits 1 if it
isn't. Exit 2 means a missing DB or bad input. The command refuses to touch v1's
`disclosures.db`.

## Curation worksheet (`--draft-candidates`)

`entities --draft-candidates [CSV] [--top 200]` reads the DB (read-only) and writes
`data/entities/alias_candidates.csv` (or `CSV`), the starting point for `aliases.csv` (ADR-6
step 3). It has one row per head: the top 200 normalised names by item count, generic terms
removed, ties broken alphabetically. Columns: `rank, alias, item_count, sections` (the
sections the alias occurs in), `sample_spellings` (the 3 commonest raw spellings with counts),
`asx_code, asx_name` (what the ASX stage would give the head), `variant_count` and `variants`.
`variants` lists every other non-generic normalised name with rapidfuzz `token_set_ratio` >= 90
to the head, as `name (items)` sorted by item count, plus `[CODE]` if that variant would
ASX-match. Token-set ratio scores a subset as 100, so `qantas` pulls in `qantas club` and
`qantas and virgin`: variants are candidates to judge, not merges. Short tickers such as `cba`
won't fuzzy-match their full names; those pairs come from curation. Output is deterministic.

## Inputs (all committed)

| File | What |
|---|---|
| `data/entities/generic_terms.csv` | `term, note`. Descriptors that name no organisation (`family trust`, `smsf`, `n/a`, `various`, ...). Terms are normalised like aliases before matching. |
| `data/entities/aliases.csv` | Curated aliases (T2.4/T2.5): `alias, canonical_name, entity_type, asx_code, review_flag, note`. |
| `data/entities/asx_exclusions.csv` | `alias, note`. Aliases that never ASX-match because a ticker is also another organisation's usual name (`ing`: Inghams versus ING Bank). |
| `data/reference/asx_listed_companies_<date>.csv` | ASX snapshot from `--fetch-asx` (title line, blank line, then `Company name,ASX code,GICS industry group`). The newest by date wins. The reference dir defaults to `<data>/../reference`. |
| `data/entities/llm_decisions.jsonl` | Long-tail LLM cache (later task). |

## Method

1. **Normalise.** `alias_normalised = normalise_entity(entity_name_raw)` (`disclosures/normalise.py`,
   the same function `score` uses). Items with a NULL `entity_name_raw` get no entity.
2. **Generic.** An alias in `generic_terms.csv` gets an `entity_aliases` row with
   `entity_id = NULL` and `method = 'generic'`.
3. **Stages, in precedence order** `curated > asx > llm > singleton`. Each stage gets the
   still-unresolved aliases and returns the ones it can name. The first stage to claim an
   alias wins. `entity_aliases.method` records which stage it was.
   - `curated`: exact match of the normalised `aliases.csv` alias.
   - `asx`: only aliases that occur on at least one section-1 item are eligible. The match is
     the exact normalised company name (normalised the same way), or failing that the exact
     ticker (`bhp`, `cba`). Then every item with that alias gets the entity, whatever its
     section. `entity_type = 'listed_company'`, `asx_code` set. A name two listed companies
     share matches nothing. All aliases of one code share a canonical name: the commonest raw
     spelling among the name-matched aliases, else the ASX name in capwords. 2026-10-02
     snapshot: 309 aliases / 4,370 items (117 of them ticker matches).
   - `llm`: long-tail grouping for aliases with ≥ 2 items (later task, not yet active).
   - `singleton`: everything left becomes its own entity. It's named after the alias's
     commonest raw spelling (ties go to the alphabetically first), with `entity_type = NULL`.
     Until the LLM stage lands, this also catches aliases with ≥ 2 items.
4. **Ids.** `entity_id` is the `member_slug` of `canonical_name` (the same slug rule as
   `member_id`). A name with no ASCII letters or digits falls back to `entity_` plus a sha1
   prefix. When two aliases map to the same id, they're treated as one organisation: the alias
   joins the existing entity and the first definition stands. Precedence order decides which
   comes first, then alias order. Example: `loreal australia` / `loréal australia`. On the
   real data, the singleton stage alone made 16 merges like this, all correct.

## Known limitations

- Singletons are untyped (`entity_type` NULL). Typing about 10k one-item names through the LLM
  isn't worth the credit (SPEC-DELTA D2). Kevin can revisit this.
