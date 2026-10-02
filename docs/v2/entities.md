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
python -m disclosures entities --offline --report         # also refresh eval/entities_report.md
```

`entities` rewrites the three outputs in place, in one transaction, so re-running it is safe.
It reads only committed files, so two runs give identical tables (tested). It prints, per
method, how many aliases and items resolved that way. It also prints the AC-3.3 count: named,
non-generic items that have no entity. That count must be 0, and the command exits 1 if it
isn't. It also prints the AC-3.2 coverage: the share of the items of the top 200 non-generic
names that have an `aliases.csv` row (must be ≥ 95%; printed, and asserted by the tests). Exit 2 means a missing DB or bad input. The command refuses to touch v1's
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
| `data/entities/llm_decisions.jsonl` | Long-tail LLM cache (T2.6): one JSON object per block, `key, prompt_version, model, members, groups` (each group `members, canonical_name, entity_type, confidence`), sorted by key. It holds the LLM's answer as given; the AC-3.4 rule below is applied when it's read. |

## Method

1. **Normalise.** `alias_normalised = normalise_entity(entity_name_raw)` (`disclosures/normalise.py`,
   the same function `score` uses). Items with a NULL `entity_name_raw` get no entity.
2. **Generic.** An alias in `generic_terms.csv` gets an `entity_aliases` row with
   `entity_id = NULL` and `method = 'generic'`.
3. **Stages, in precedence order** `curated > asx > llm > singleton`. Each stage gets the
   still-unresolved aliases and returns the ones it can name. The first stage to claim an
   alias wins. `entity_aliases.method` records which stage it was.
   - `curated`: exact match of the normalised `aliases.csv` alias. Heads 1–100 (T2.4): 330
     aliases → 72 entities, 12,597 items. Heads 101–200 (T2.5) bring it to 522 aliases and
     14,641 items, and 100% of the top 200's items. A trust and its trustee company stay
     separate (Kimlie Trust and Kimlie Pty Ltd); a renamed organisation takes its current name
     (Football Australia, Rugby Australia); delisted companies (Newcrest, Atlas Iron) are typed
     `other` and flagged. Curation rules (DECISIONS 2026-10-02, T2.4): one
     entity per brand as disclosed (St.George, Bankwest, BankSA, ME Bank stay apart from their
     parents); lounges, clubs and frequent-flyer programmes resolve to the airline; party and
     union state branches stay separate; combined names (`qantas and virgin`) aren't curated.
     Types: banks and insurers `bank_or_financial`, airlines `airline`, media
     `media_or_entertainment`, other listed companies `listed_company` (always with
     `asx_code`). Rows with `review_flag=1` carry a `note` for G3.
   - `asx`: only aliases that occur on at least one section-1 item are eligible. The match is
     the exact normalised company name (normalised the same way), or failing that the exact
     ticker (`bhp`, `cba`). Then every item with that alias gets the entity, whatever its
     section. `entity_type = 'listed_company'`, `asx_code` set. A name two listed companies
     share matches nothing. All aliases of one code share a canonical name: the commonest raw
     spelling among the name-matched aliases, else the ASX name in capwords; a code that
     `aliases.csv` already uses takes that row's canonical name and type instead, so it stays
     one entity. 2026-10-02 snapshot: 309 aliases / 4,370 items before curation; 279 / 1,067
     after T2.4 claimed the big names.
   - `llm`: long-tail grouping (ADR-6 step 5) for every alias still unresolved with ≥ 2
     items. **Blocks:** aliases are grouped by first token. Within a group, names joined by a
     chain of rapidfuzz `token_set_ratio` ≥ 85 form one block. A name with no such neighbour is
     a 1-name block, which the LLM only names and types. **Cache:** the key is sha1 of the
     sorted block members plus the prompt version (`entities-llm-v1`, prompt in
     `disclosures/prompts/entities_llm.md`). Online mode (no `--offline`) sends only uncached
     blocks to `google/gemini-3.8-flash` via OpenRouter (`google-ai-studio/flex`, azure
     ignored, strict `json_schema`, model id through `resolve_gemini_model`). It packs about 40
     names per request (a block is never split) and appends each reply to the cache as it
     arrives. A reply whose groups don't exactly partition its block is retried alone once,
     then left uncached. `--offline` reads the cache only. In either mode, any uncached block
     makes the command exit 1 and list the blocks, with the DB left unchanged; online, re-run
     to continue. `--llm-dry-run` prints blocks, uncached count and requests, then stops.
     `--llm-limit N` caps requests per run (to chunk a long run). **AC-3.4 rule:** a group the
     LLM types `listed_company` takes the ASX code that its canonical name, or failing that one
     of its members, matches exactly in the snapshot (names two companies share and
     `asx_exclusions.csv` don't count). With no match it's typed `other` (foreign-listed or
     delisted). **One entity per ASX code:** a later stage's alias with a code an entity
     already has joins that entity. 2026-10-02 run: 4,090 aliases / 14,128 items in 3,322
     blocks (417 with > 1 name), 104 requests, US$1.16. The result is 3,822 groups (232
     merges), 3,567 of them `high` confidence.
   - `singleton`: everything left, i.e. the aliases with 1 item, becomes its own entity. It's
     named after the alias's commonest raw spelling (ties go to the alphabetically first), with
     `entity_type = NULL`.
4. **Ids.** `entity_id` is the `member_slug` of `canonical_name` (the same slug rule as
   `member_id`). A name with no ASCII letters or digits falls back to `entity_` plus a sha1
   prefix. When two aliases map to the same id, they're treated as one organisation: the alias
   joins the existing entity and the first definition stands. Precedence order decides which
   comes first, then alias order. Example: `loreal australia` / `loréal australia`. On the
   real data, the singleton stage alone made 16 merges like this, all correct.
5. **Join by name** (after all stages). An entity made only by the `llm` stage whose
   canonical name normalises to an alias a non-singleton entity owns joins that owner (`qf`
   was named "Qantas", and `qantas` is curated to Qantas Airways). A singleton alias equal to
   another entity's normalised canonical name joins it (`agest super` -> AGEST Super). Curated
   and asx entities never move, so Tower Limited (asx) stays apart from Tower Australia (llm).
   Aliases keep their own method. 2026-10-02: 34 merges, 10,219 -> 10,185 entities.

## Report (`--report`)

`entities --report [MD]` (after resolving) rewrites the generated block of
`eval/entities_report.md`: method and type counts, AC-3.3 and AC-3.4 results, and the top 20
next to v1's top 20 (AC-3.6, v1 read-only). Text outside the BEGIN/END markers is kept.

## Known limitations

- Singletons are untyped (`entity_type` NULL). Typing about 6k one-item names through the LLM
  isn't worth the credit (SPEC-DELTA D2). Kevin can revisit this.
- The `listed_company` ASX lookup for LLM groups is exact-name only, so a listed company the
  snapshot names differently (`Abacus Property Group` vs `ABACUS GROUP`) is typed `other`.
  On the 2026-10-02 run, 45 of the 348 groups the LLM typed `listed_company` got a code (49
  aliases); the other 303 groups (324 aliases) became `other`. Curating the big ones into `aliases.csv` fixes them.
- Changing the prompt means bumping `LLM_PROMPT_VERSION`, which invalidates every cached block
  (about US$1.20 to redo).
