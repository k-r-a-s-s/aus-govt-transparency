# Scraper (`python -m disclosures scrape`)

```sh
python -m disclosures scrape --chamber house --parliament 48           # download new/changed statements
python -m disclosures scrape --chamber house --parliament 48 --verify  # re-download everything, compare sha256
python -m disclosures scrape --limit 5                                 # first 5 listing rows only (testing)
```

Only the current House parliament (48th) is scraped. The 43rd to 47th archives are already
tracked in git and are back-filled into the manifest by `python -m disclosures.manifest --backfill`.

## What it does

1. Fetches the live register listing (`disclosures/sources.py`, browser User-Agent, retries).
   151 member rows on 2026-10-03: 147 link the register API
   (`interests-register-api-public.aph.gov.au/api/members/{id}/statement/48`) and 4 link a
   static PDF (`static.aph.gov.au/.../48p/{AB..SZ}/{Surname}_48P.pdf?rev=…`).
2. Downloads each statement and writes it to `pdfs/48/{surname}{first-initial}_48p.pdf`
   (lower-case ASCII, punctuation dropped, e.g. `odowdk_48p.pdf`). On a name collision it uses the full
   given name (`smithjohn_48p.pdf`), then a numeric suffix (`smithjohn_48p_2.pdf`). A
   statement keeps its file name for good. Its manifest row is found by the link without its
   query string, or else by surname plus electorate.
3. Upserts one row per statement in `pdfs/manifest.csv` (ADR-8 columns) after every file,
   so a killed run loses nothing. `member_name` is "Given Surname" from the listing, and
   `electorate_or_state` is the electorate. Member identity (`member_id`, `pdf_members.csv`) is
   handled separately (T3.3b).
4. Refuses (never writes) bodies over 95 MB and bodies that aren't a PDF, and reports both.
   Exit code 1 if anything was refused or failed.

The last log line is
`scrape house 48: N listed, N new, N changed, N unchanged, N refused, N failed`.

## Change detection

On 2026-10-02/03, repeated downloads of the same API statement (`316915-48.pdf`, 11 pages,
Aspose-generated) and the same static PDF gave identical bytes. A `--verify` run over all 151,
a few minutes after the first download, found 0 changed. So the bytes are stable, and sha256
is the change signal:

- A listing row whose link (including `?rev=`) and "Last updated" date both match its manifest
  row, and whose file exists, is **unchanged** and isn't downloaded. A second run therefore
  requests only the listing page and logs `0 new, 0 changed` (AC-4.4).
- Otherwise the statement is downloaded. If it has no manifest row, it's **new**. If its sha256
  differs, it's **changed**: the file is overwritten in place, so git history versions it
  (ADR-8). If the sha256 is the same, it's **unchanged**, and the row's link and date are
  refreshed.
- `--verify` downloads everything regardless of the listing. Use it if APH ever re-uploads a
  statement without changing its date.

## Senate 48th

`python -m disclosures scrape --chamber senate --parliament 48` reads the senators' interests
API (`disclosures/senate.py`, `sources.SENATE_API_BASE`; send `Origin: https://www.aph.gov.au`).
It saves each `getSenatorStatement` payload, pretty-printed with sorted keys, to
`pdfs/senate/48/{surname}{first-initial}_48s.json` and the listing to
`pdfs/senate/48/_query_statements.json`, and upserts a manifest row (chamber `senate`,
`listed_date` = `lastDateUpdated` as a Sydney date, `page_count` 1). Every statement is fetched
each run (76 small requests); a changed sha256 is **changed**. Two fetches gave identical bytes
(2026-10-02). Then `python -m disclosures extract --source senate-json pdfs/senate/48/*.json`
writes `extractions/senate-json/senate/48/`.

## Refresh

`python -m disclosures refresh --dry-run` downloads every House 48th statement and every Senate
payload (`scrape --verify` semantics, ~2 min) and lists each one whose sha256 differs from
`pdfs/manifest.csv` (`changed`) or that has no row (`new`). It writes nothing. A download
failure exits 1 rather than print a partial list.

`python -m disclosures refresh` (gemini source) saves those files and their manifest rows,
extracts only the new/changed House PDFs with the G2 config (`refresh.G2_EXTRACT`, batches of
20), runs the Senate adapter on the changed senators, then runs
`load --source gemini-api --source senate-json` and `entities` (online, so uncached long-tail
blocks are paid). It stops at the first sub-command that fails; every step is idempotent, so
re-run it. `--source workflow` saves the files and runs the Senate adapter, then prints the
`extract-disclosures` Workflow args (`pdfs`, `page_counts`, `extracted_at`) and the load and
entities commands to run after the Workflow.

## Committing

Commit the PDFs and `pdfs/manifest.csv` in the same commit. `tests/test_manifest.py` (AC-4.3)
asserts that every tracked PDF has a manifest row and that every sha256 matches its file.
