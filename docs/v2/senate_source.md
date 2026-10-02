# Senate source: the APH senators' interests API (ADR-9, D3)

The Senate register is not a set of PDFs. The register page
(`https://www.aph.gov.au/Senators_and_Members/Senators/Senators_Interests/Senators_Interests_Register`)
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

Senate statements for the 43rd–47th Parliaments are not loaded. Task T3.9 checks whether
`queryStatements` filters by parliament and what the archive pages (`…/Register44thparl` etc.)
link to, and records the findings here.
