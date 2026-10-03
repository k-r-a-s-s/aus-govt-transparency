# Australian Parliament Registers of Members' and Senators' Interests (v2)

Every interest Australian federal MPs and senators disclosed in the Registers of Interests,
transcribed item by item from the official statements and joined with the member's party and
a standardised entity (company, organisation, trust) for each item.

`disclosures_v2.csv`: 50,936 rows, one per disclosed item (a shareholding, a gift, a trip, a
directorship, …), 33 columns. Built from `disclosures_v2.db` (schema
2.0, loaded 2026-10-02T22:42:31+00:00).

## Coverage

| chamber | parliament | members | statements | items |
|---|---|---|---|---|
| house | 43 | 150 | 150 | 7,784 |
| house | 44 | 152 | 152 | 8,511 |
| house | 45 | 153 | 158 | 9,426 |
| house | 46 | 153 | 153 | 7,461 |
| house | 47 | 155 | 155 | 9,070 |
| house | 48 | 151 | 151 | 6,704 |
| senate | 48 | 76 | 76 | 1,980 |

House: the 43rd-47th parliaments (2010-2025) from the archived registers, and the current 48th
register as scraped. Senate: the 48th parliament only (the senators' interests API serves
current senators only).

## Field dictionary

| column | type | description |
|---|---|---|
| `item_id` | string | Stable id of the disclosed item (sha1 of the document hash and the item's content; see docs/v2/loading.md). |
| `chamber` | string | `house` (House of Representatives) or `senate`. |
| `parliament` | integer | Parliament number (43 = 2010-2013 … 48 = 2025-). |
| `member_id` | string | Stable member id (slug of the member's name, e.g. `tony_abbott`); the same person keeps one id across parliaments and chambers. |
| `member_name` | string | Member's full name. |
| `party` | string | Member's party for this parliament (start of term). |
| `political_bloc` | string | `Labor`, `Coalition` or `Crossbench`, derived from party. |
| `electorate_or_state` | string | House: electorate. Senate: state or territory. |
| `statement_date` | string | Date of the member's initial statement (YYYY-MM-DD), where printed. |
| `section` | integer | Register section number (1-14, the House form's numbering; Senate categories are mapped onto it). |
| `subsection` | string | Sub-part of the section where the form has one (`2(i)` family trusts, `2(ii)` other trusts), else empty. |
| `category` | string | Section name: Shareholding, Trust, Real estate, Directorship, Partnership, Liability, Bond/debenture, Account, Other asset, Income, Gift, Sponsored travel/hospitality, Membership, Other interest. |
| `owner` | string | Whose interest it is: `self`, `spouse`, `dependent_child` or `unknown`. |
| `entity_name_as_printed` | string | The company, organisation, trust or person the item names, as printed. Empty when the item names no entity (e.g. a house address). |
| `entity_id` | string | Standardised entity id; items naming the same organisation in different spellings share it. Empty for no entity or a generic term (e.g. `family trust`). |
| `entity_name` | string | Canonical name of the standardised entity. |
| `entity_type` | string | Entity type (listed_company, private_company, bank_or_financial, trust_or_fund, association_or_ngo, sporting_body, government_body, political_party, union, airline, media_or_entertainment, education, person, other). Empty for most one-off (singleton) entities. |
| `entity_asx_code` | string | ASX ticker when the entity matched an ASX-listed company (banks, airlines and media groups included, e.g. `CBA`, `QAN`), else empty. |
| `entity_match_method` | string | How the name was standardised: `curated` (hand table), `asx` (ASX listed-companies snapshot), `llm` (LLM grouping of variants), `singleton` (one-off name, its own entity) or `generic` (generic term, no entity). |
| `description` | string | The item as printed on the form (the full cell text). |
| `location` | string | Location, where the form gives one (real estate, travel). |
| `purpose` | string | Purpose, where the form gives one (real estate, liabilities). |
| `is_alteration` | integer | 1 if the item comes from a later Notification of Alteration, 0 if from the initial statement. |
| `change_type` | string | `initial`, `added`, `removed`, `varied` or `unknown`. |
| `lodged_date` | string | Date the statement or alteration was lodged (YYYY-MM-DD; see date_precision). |
| `date_precision` | string | `day`, `month` (day set to 01) or `unknown` (no date printed; lodged_date empty). |
| `page` | integer | Page of the source PDF the item is on (1-based). Senate items: 1. |
| `extraction_confidence` | string | Extractor's confidence in the item: `high`, `medium` or `low` (low/medium = hard-to-read scan or ambiguous layout). |
| `source_file` | string | Source document path in the repository (House PDF, or the Senate API JSON payload). |
| `source_sha256` | string | sha256 of the source document. |
| `source_url` | string | Where the source document was downloaded from (APH). |
| `extraction_source` | string | `gemini-api` (LLM transcription of the PDF) or `senate-json` (Senate interests API, no LLM). |
| `extraction_model` | string | Model(s) that transcribed the PDF; `a+b` means model b handled pages model a refused. |

Empty cells are nulls.

## Method

1. **Collect.** House statements are the PDFs on aph.gov.au (archived registers for the
   43rd-47th parliaments, the live register for the 48th); `source_url` points at each one.
   Senate statements come from the Parliament's senators' interests API (JSON).
2. **Transcribe.** Each House PDF (initial statement plus every alteration bound into it) was
   transcribed by `google/gemini-3.8-flash` into a strict JSON schema, one item per disclosed
   interest, with `anthropic/claude-sonnet-5.5` taking any pages Gemini refused. On a 12-PDF
   hand-checked gold set (790 items) this scored precision 0.986, recall 0.987 (F1 0.987),
   with 100% owner and page accuracy. Senate items are mapped from the API's fields; no
   model is involved.
3. **Validate and load.** Every transcription passes a schema and completeness check
   (every page covered, every item on a real page) before loading. Members are matched across
   parliaments and chambers to one `member_id`; party and bloc come from a per-term table.
4. **Standardise entities.** Entity names are normalised, then resolved in order: a curated
   alias table (the most common names), the ASX listed-companies list, an LLM grouping of
   spelling variants, and finally one entity per remaining one-off name. 11,542 entities.

## Known limitations

- **Senate before the 48th parliament is missing.** Earlier Senate registers exist only as
  tabled volumes and are not in this release.
- **Two prompt versions.** Most House statements for the 43rd-47th parliaments were
  transcribed with prompt v0. Prompt v1 adds one rule (C12): itemise lists bound in as
  attachments ("see attached"). Only the 7 statements found to have un-itemised attachments
  were re-run on v1 (`coultonm_43p`, `nevillep_43p`, `coultonm_44p`, `huntg_44p`, `pynec_44p`,
  `coultonm_45p`, `odowdk45p`); the whole 48th House register used v1. A few other v0
  statements may still describe an attachment in one item instead of itemising it.
- **One-off entities are untyped.** 7,037 of the 11,542 entities are names that
  appear once; each is its own entity with an empty `entity_type`.
- **ASX matching is name-based.** A listed company whose snapshot name differs from the name
  the LLM chose may be typed `other` with no `entity_asx_code`.
- **Transcription is not perfect.** Expect roughly 1-2% of items to be missed or misread,
  more on poor scans (43rd-45th parliaments); `extraction_confidence` flags the doubtful ones.
  Check anything important against the source PDF (`source_url`, `page`).
- **Dates.** `lodged_date` is empty when no date is printed (`date_precision = unknown`).
- **Party** is the party at the start of each term; mid-term defections are not tracked.

## Source and licence

Parliament of Australia, Register of Members' Interests and Register of Senators' Interests
(aph.gov.au). Code and documentation: https://github.com/k-r-a-s-s/aus-govt-transparency. Browse and query the data online
(Datasette Lite): https://k-r-a-s-s.github.io/aus-govt-transparency/.

Licence: [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). You may share and
adapt this dataset for non-commercial purposes if you credit it and the source. The
NonCommercial term follows the source: material on aph.gov.au is published under
[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) and is credited as
"Parliament of Australia website". Each row's `source_url` links the original statement.
