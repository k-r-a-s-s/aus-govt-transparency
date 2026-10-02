# Senate source: the APH senators' interests API (ADR-9, D3)

The Senate register is not a set of PDFs. The register page
(`https://www.aph.gov.au/Parliamentary_Business/Committees/Senate/Senators_Interests/Senators_Interests_Register`;
the `/Senators_and_Members/Senators/...` form of the URL 404s)
is a React app that reads a JSON API. v2 saves that JSON and maps it to ADR-2 with code, not an
LLM (`source_id = senate-json`, `disclosures/senate.py`).

```sh
.venv/bin/python -m disclosures scrape --chamber senate --parliament 48          # ~30 s, all 76
.venv/bin/python -m disclosures extract --source senate-json pdfs/senate/48/*.json   # free, no key
.venv/bin/python -m disclosures.members --chamber senate --parliament 48         # pdf_members rows
.venv/bin/python -m disclosures.members --chamber senate --parliament 48 --party-terms
.venv/bin/python -m disclosures load --source gemini-api --source senate-json
```

The two `disclosures.members` steps only add rows for source documents that have none, so after a
re-scrape they only matter when a new senator appears.

## Coverage

| Parliament | Senate data in `disclosures_v2.db` |
|---|---|
| 48th (2025–) | Yes: 76 senators, 76 statements, 1,980 items (1,328 interests, 652 alterations), statements lodged 2025-07-10 to 2026-09-25 (scraped 2026-10-02) |
| 43rd–47th | No. See [Archives](#archives) |

Check: `select count(distinct member_id) from items where chamber='senate' and parliament=48`
must be between 70 and 80 (AC-4.6). It is 76.

## Endpoints

Base: `https://pbs-apim-aqcdgxhvaug7f8em.z01.azurefd.net/api` (`sources.SENATE_API_BASE`). It
comes from the app's config, `/js/apps/senators-interests-register/build/env.js`
(`SENATORS_API_BASE_URL`). If the host stops answering, re-read `env.js`. Send a browser
`User-Agent` and `Origin: https://www.aph.gov.au`.

| Endpoint | Returns |
|---|---|
| `GET {base}/queryStatements?currentPage=1&pageSize=100&sortBy=senator&sortDirection=ascending` | The listing: `{statementOfRegisterableInterests: [...], rowCount: 76, pageCount: 1, currentPage, pageSize, wasSuccessful, errors}`. Saved as `pdfs/senate/48/_query_statements.json` |
| `GET {base}/getSenatorStatement?cdapid={cdapId}` | One senator's statement (below). Saved as `pdfs/senate/48/{surname}{first-initial}_48s.json` |
| `GET {base}/GetParties` | The party list (not used) |

**reCAPTCHA.** The page loads Google reCAPTCHA, but on 2026-10-02 the API answered plain GETs
with no token. If it starts demanding one, the scrape will fail with HTTP 4xx. Re-check the
app bundle (`main.js`) for how the token is sent before trying anything else.

## Payload shape

A listing row:

```json
{"cdapId": "298839", "id": "c4ded6d5-ca7b-f011-b4cb-000d3ad253b4",
 "lastDateUpdated": "2026-05-13T09:06:50", "lodgmentDate": "2025-08-14T13:31:50Z",
 "name": "Allman-Payne, Penny", "postNominal": "", "publishNotes": false,
 "senatorParty": "Australian Greens", "state": "Queensland", "statementNotes": "",
 "title": "Senator"}
```

A statement has `senatorInterestStatement`, `wasSuccessful` and `errors`, plus one object per
section, each `{"interests": [...], "alterations": [...]}`. Abridged sample
(`pdfs/senate/48/cashm_48s.json` and, for the alteration, `allmanpaynep_48s.json`):

```json
{
  "senatorInterestStatement": {
    "electorateState": "Western Australia", "id": "7927492b-8872-f011-b4cc-002248929e07",
    "lastDateUpdated": "8/6/2025 2:35:19 PM", "lodgementDate": "8/5/2025 2:00:00 PM",
    "publishNotes": false, "senatorName": "Cash, Michaelia",
    "senatorParty": "Liberal Party of Australia", "senatorPostNominal": "",
    "senatorTitle": "Senator the Hon.", "statementNotes": ""},
  "liabilities": {"interests": [{"creditor": "Bankwest", "id": "4cb8efd1-…",
                                 "natureOfLiability": "Mortgage on Primary Residence"}],
                  "alterations": []},
  "realEstate": {"interests": [{"id": "1928492b-…", "location": "Floreat",
                                "purposeForWhichOwned": "Primary Residence"}],
                 "alterations": []},
  "gifts": {"interests": [{"detailOfGifts": "Foxtel EO Subscription", "id": "20291768-…"}],
            "alterations": [{"alterationType": "Addition", "createdOn": "2026-05-13T09:00:00Z",
                             "details": "Shirt from Football Australia offered to all MPs and Senators …",
                             "id": "45a9f190-…"}]},
  "wasSuccessful": true, "errors": []
}
```

Timestamps come in two formats: `M/D/YYYY h:mm:ss AM` in the statement header and ISO in the
listing and alterations. Both are UTC. v2 uses the Australia/Sydney calendar date
(DECISIONS.md 2026-10-03). Across all 76 payloads the alteration types are `Addition` (597) and
`Deletion` (55).

## Section mapping

| API key | Section | Fields → ADR-2 |
|---|---|---|
| `shareHoldings` | 1 | `nameOfCompany` → entity_name |
| `trusts` | 2 | `nameOfCompany` → entity_name; `nature`, `interest` → description; `type` beneficiary/trustee → subsection 2(i)/2(ii) |
| `realEstate` | 3 | `location` → location; `purposeForWhichOwned` → purpose |
| `registeredDirectorshipsOfCompanies` | 4 | `nameOfCompany` → entity_name; `activitiesOfCompany` → description |
| `partnerships` | 5 | `nameOfPartnership` → entity_name; `natureOfInterest`, `activitiesOfPartnership` → description |
| `liabilities` | 6 | `creditor` → entity_name; `natureOfLiability` → description |
| `investments` | 7 | `bodyOfWhichInvestmentIsHeld` → entity_name; `typeOfInvestment` → description |
| `savingsOrInvestmentAccounts` | 8 | `nameOfBankInstitution` → entity_name; `natureOfAccount` → description |
| `otherAssets` | 9 | `nameOfOtherAsset` → description |
| `otherIncome` | 10 | `nameOfIncome` → description |
| `gifts` | 11 | `detailOfGifts` → description |
| `sponsoredTravelOrHospitality` | 12 | `detailOfTravelHospitality` → description |
| `officeHolderDonating` | 13 | `nameOfOrganisation` → entity_name |
| `otherInterest` | 14 | `natureOfInterest` → description |

Each item's description holds all of its non-empty fields joined by `; `. An unmapped section key,
or an unknown field inside a section, raises an error instead of being dropped. A nil row
(`NIL`, `-`, `none`, empty) is not an item.

- Interests: `is_alteration=false`, `change_type=initial`, `lodged_date` = the statement's
  `lodgementDate` date.
- Alterations: `is_alteration=true`, `change_type` from `alterationType` (Addition → added,
  Deletion → removed, Variation/Change → varied, else unknown), `lodged_date` = the `createdOn`
  date, description = `details`.
- `owner` is always `self`: the spouse and children's part (Form B) is confidential.
- `page=1`, `confidence=high`, `extraction_notes = "structured source: APH senators' interests API"`.
- The saved JSON is the source document: `pdf_path` points at it, `pdf_sha256` is its sha256 and
  `page_count = 1`. `validate` checks the sha256 and `page_count == 1`, and skips PyMuPDF.

## Members and parties

- `data/overrides/pdf_members.csv` has a row for every Senate source document
  (`source=aph_senate_48`), written by `python -m disclosures.members --chamber senate`. It
  resolves the listing name through `member_aliases.csv` (name with state, then name alone). A
  senator who was an MP keeps their House `member_id` and is printed as `CROSS-CHAMBER`. In the
  48th there are four: Michelle Ananda-Rajah (House 47th), Sarah Henderson (44th–45th), Deborah
  O'Neill (43rd) and Dave Sharma (46th). The other 72 are new: `member_id` = slug of the
  listing's "Given Surname" (`Matthew Canavan` → `matthew_canavan`), plus a
  `member_aliases.csv` row.
- `party_terms.csv` senate/48 rows (`source=aph_senate_api`) take the payload's `senatorParty`
  through `party_mapping.csv`. A Queensland Liberal or National is `Liberal National Party`, as
  for the House. **This is the party when the statement was scraped, not at the start of the
  term**, so a senator who changed party since July 2025 shows the new party.
- `members.chamber` is the chamber of the member's most recent term, so all four ex-MPs are
  `senate`. `member_terms` keeps one row per chamber and parliament (`dave_sharma` has
  house/46 and senate/48).

## Archives

Senate statements for the 43rd–47th Parliaments are **not loaded**, and the API can't supply
them. They exist only as PDFs, in two formats. Extracting them is a follow-up (ADR-9 accepts
stopping here). Checked live on 2026-10-03 (T3.9).

### The API serves current senators only

- The app's only listing call is `searchInterestsStatements`, which sends
  `currentPage, pageSize, sortBy, sortDirection` plus, from the filter form, `keyword`, `state`
  and `party` (`main.js`, `handleFilterSearchResults`). There is no parliament or archive
  parameter, and the app has no archive view (routes `/` and `/:senatorId` only).
- The API silently ignores unknown parameters. With `parliament=45`, `parliamentNumber=45`,
  `parliamentId=45`, `parl=45`, `term=45`, `parliament=44th`, `year=2019`,
  `includeArchived=true`, `archived=true`, `status=all` or `historical=true` it returns the same
  76 senators (identical `cdapId` set). `keyword=Cash` returns 5 rows, so parameters do reach it.
- Former senators are not in it: `keyword=Abetz`, `Kitching` and `Birmingham` return nothing,
  while sitting senators (`Lambie`) are found. `pageSize=500` still gives 76 and page 2 is empty.

### Format 1: per-senator PDFs, 44th and 45th only

| Page | Links | Format |
|---|---|---|
| `…/Senators_Interests/Register44thparl` | 62 PDFs, `static.aph.gov.au/-/media/Committees/Senate/committee/interests_ctte/statements2014/{Surname}{I}_Astat_{yymmdd}.pdf` | Scanned, no text layer |
| `…/Senators_Interests/Register45thparl` | 75 PDFs, `…/Statements_2016_45th_Parl/{Surname}{I}_Astat_{yymmdd}.pdf` | Scanned, no text layer |
| `…/Register43rdparl`, `…/Register46thparl`, `…/Register47thparl` | HTTP 404: no such page | |

Six sampled files had 7–22 pages (mean ≈ 11.5), all images. One PDF per senator, so they would
fit the House pipeline (`pdf_members.csv` row per file, G2 extraction), but they only cover two
parliaments, and 62 files for the 44th is fewer than its 76 seats plus replacements.

### Format 2: tabled volumes, every parliament

`…/Senators_Interests/Tabled_volumes` links 89 consolidated PDFs, one or two per half-year,
from "lodged by 2 June 1994" to "1 January 2026 – 30 June 2026". Each bundles every Form A
statement and alteration notification lodged in the period, in senator-name order: one form per
page or several pages, headed `Surname: … Other names: … State/Territory: … Date: …`. Links use
`/-/media/{32 hex}.ashx` (2022 on) or `/~/media/{32 hex}.ashx` (older; the bare `/media/...`
form 404s). One link ("24 November 2009 and 21 June 2010 (PDF 70.2Mb)") is a duplicate of the
3.9 MB file.

All 40 volumes covering the 43rd–47th were downloaded and counted (bucketed by Senate term,
1 July to 30 June; "text pages" have > 200 characters of text):

| Parliament | Volumes | Pages | Text pages | Notes |
|---|---|---|---|---|
| 43rd (2010–13) | 9 | 1,255 | 6 | Scans; incl. "statements only" vols 1–2 (Aug 2011) |
| 44th (2013–16) | 8 | 1,254 | 151 | Scans except Dec 2013 – Jul 2014 |
| 45th (2016–19) | 8 | 1,560 | 18 | Scans |
| 46th (2019–22) | 7 | 1,061 | 908 | Mostly typed |
| 47th (2022–25) | 8 | 1,326 | 1,036 | Mostly typed; Jul–Dec 2024 (234 pp) is a scan |
| **Total** | **40** | **6,456** | **2,119** | 505 MB |

### Follow-up estimate

Extracting the tabled volumes needs one new step and then the existing extractor:

1. **Split** each volume into per-senator page ranges (a form starts at a page whose header has
   `Surname:`). Text pages split by regex; the ≈ 4,300 scanned pages need a cheap OCR or LLM
   page-header pass. Each range becomes a source document with a `pdf_members.csv` row and a
   manifest row. This is the one additional adapter; ADR-9 caps the archive work below that.
2. **Extract** with the G2 config. House 48th cost US$4.03 for 2,684 typed pages
   (≈ US$0.0015/page). Scanned pages cost more: RECITATION fallbacks hit 20–25% of scans (AGENTS.md),
   so ≈ US$0.0035/page. Estimate: 2,100 typed × 0.0015 + 4,350 scanned × 0.0035 ≈ **US$18**,
   budget **US$25** with retries.
3. **Statements vs alterations.** The volume at the start of each term holds the Form A
   statements; the rest are alterations (Form A – Alteration, Addition/Deletion), which map to
   `is_alteration=true` like the API's alterations.

The 44th/45th per-senator PDFs (137 files, ≈ 1,600 scanned pages, ≈ US$6–9) would fit the
current pipeline without a splitter, but they leave the 43rd, 46th and 47th empty and overlap
the tabled volumes, so the volumes are the better follow-up.
