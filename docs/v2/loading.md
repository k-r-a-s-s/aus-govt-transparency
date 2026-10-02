# Loading: `python -m disclosures load`

```sh
.venv/bin/python -m disclosures load --source workflow-claude \
    [--db disclosures_v2.db] [--extractions extractions] [--overrides data/overrides]
```

Run it from the repo root, because `pdf_path` in the extraction files is relative to the repo.

## What it does

1. Takes every `*.json` under `extractions/<source>/` and runs `validate_file` on it (the
   same check as `python -m disclosures validate`). Invalid files are skipped. Each one is
   printed as `SKIPPED <file>: <error>`, and the number skipped is printed too. If two files
   have the same `pdf_sha256`, the second is skipped as a duplicate.
2. Builds a new SQLite DB from scratch with the ADR-7 tables (`documents`, `members`,
   `member_terms`, `items`, `entities`, `entity_aliases`) plus `meta` (`schema_version`,
   `source_id`, `loaded_at`, `n_files`). It writes the DB to `<db>.tmp-<pid>` and then
   renames that over `<db>`. A load that fails leaves the previous DB as it was.
   `entities` and `entity_aliases` start empty; Phase 3 (`entities`) fills them.
   `documents.source_url` and `fetched_at` are NULL for now; `pdfs/manifest.csv` (T3.2) holds
   them, and the loader doesn't read it yet.
3. Prints a summary and runs the AC-2.7 sanity queries. The summary gives files loaded and
   skipped; counts of members, member_terms and items; how each member was resolved; any
   member that had to be slugged; and any term with no party that isn't listed in
   `unknown_party.csv`. Exit codes: 0 when every hard query is 0, 1 when a hard query isn't
   0, 2 for a bad source, extractions or overrides path.

It refuses to write a file named `disclosures.db`, so v1 is never touched.

## Member identity (`member_id`)

`member_id` = slug of the canonical full name: lower case, ASCII-folded, each run of
non-alphanumerics becomes `_`, no leading or trailing `_` (`Clare O'Neil` -> `clare_o_neil`).
The loader tries these in order and uses the first that matches:

1. **`data/overrides/pdf_members.csv`** by `pdf_path`. It covers all 774 tracked PDFs. A row
   with an empty `member_id` is a non-member document: `documents.member_id` is NULL and no
   member or term row is made.
2. **`data/overrides/member_aliases.csv`** by the normalised `member_name_as_printed`. The
   normalisation reorders "Surname, Given", ASCII-folds, lower-cases, drops brackets and
   honorifics, deletes apostrophes, turns other punctuation into spaces and collapses
   whitespace. It looks for a match together with the normalised electorate first, then for
   the name alone. Either lookup counts only if it gives exactly one member.
3. **Slug of `member_name_as_printed`**, with a `WARNING` line. Add the PDF to
   `pdf_members.csv` when you see one.

`member_terms` gets one row per (member, chamber, parliament) that has a document.
`electorate_or_state` comes from the extraction as printed. If that is empty, it comes from
the PDF's `pdf_members.csv` row. `party` and `political_bloc` come from `party_terms.csv`, and
are NULL when no row exists. See `data/overrides/README.md` for how that table was derived.

## Item ids

`item_id = sha1(json([pdf_sha256, page, section, owner, normalise_entity(entity_name or
description), ordinal]))`. `ordinal` is the 0-based count of earlier items in the same file
with the same five-part key, in file order. The id therefore depends only on the extraction
file, and loading twice gives identical `items` (AC-2.8).
`category` is derived from `section` using the ADR-7 table (1 Shareholding ... 14 Other
interest). `entity_name_raw` is the extraction's `entity_name`. `entity_id` stays NULL until
Phase 3.

## AC-2.7 queries (printed on every load)

```sql
-- must be 0
select count(*) from items where section not between 1 and 14
  or owner not in ('self','spouse','dependent_child','unknown') or page < 1;
select count(*) from items i join documents d using(pdf_sha256) where i.page > d.page_count;
select count(*) from items where lodged_date is not null and (lodged_date < '1990-01-01'
  or lodged_date > date('now') or lodged_date not glob '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]');
-- informational (list in eval/bakeoff.md; early-dated interests can be genuine)
select count(*) from items where lodged_date < '2010-01-01' and confidence != 'low';
```

## Inspecting

```sh
sqlite3 disclosures_v2.db ".tables"
sqlite3 -header -column disclosures_v2.db "select * from meta"
sqlite3 -header -column disclosures_v2.db \
  "select m.full_name, t.parliament, t.party, count(*) n from items i
   join members m using(member_id) join member_terms t using(member_id, chamber, parliament)
   group by 1, 2 order by n desc limit 20"
sqlite3 disclosures_v2.db "select item_id from items order by 1" | shasum   # AC-2.8
sqlite3 disclosures_v2.db "select member_id, parliament from member_terms where party is null"  # AC-2.9
```

`disclosures_v2.db` is gitignored (`*.db`). Rebuild it with `load` and don't commit it.
