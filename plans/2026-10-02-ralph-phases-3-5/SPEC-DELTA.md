# SPEC delta — attachment fix, Phases 3–5 (2026-10-02)

`plans/2026-10-01-disclosures-v2/SPEC.md` is still the spec: its ADRs and acceptance criteria
(AC-0, AC-3, AC-4, AC-5) are the bar, and this plan never weakens them. This file only adds
what the SPEC doesn't settle: (1) a prompt fix found in review, (2) design choices the SPEC
leaves open, (3) external facts re-verified on 2026-10-02, (4) budget, branch and gate rules for
an unattended loop. Section numbers (D1, D2, …) are cited from `IMPLEMENTATION_PLAN.md`.

---

## D1. Attachments are not itemised (review finding, 2026-10-02)

**Finding.** In the gemini-api backfill, some statements say "see attached" in a section cell and
the attachment is bound into the PDF, but the model recorded no item for the attachment's
holdings. Clearest case: `pdfs/45/odowdk45p.pdf` (Kevin O'Dowd, 45th). Its notes say "Page 9
contains Attachment 'A' listing SMSF holdings referenced in Section 7", but there are 0 items on
page 9. v1 has 22 named holdings from that list (BT Wrap, Magellan Global, Amcor, BHP, CSL,
Westpac, …) and v2 has none of them. Other files handle attachments correctly
(`southcotta_44p`: 51 holdings after "see attached list"; `wilsonr_45p`: 27). The prompt
(`disclosures/prompts/extract.md`, v0) has no rule for attachments, so the behaviour is
inconsistent.

**Scale (estimate).** Distinct v1 named entities with no v2 counterpart:
342 of 20,414 (1.7%), and most of those are v1 OCR noise. Files where a v2 item points at an
attachment ("see attachment", "as per attached", "Attachment A") and few or no items follow it
in that section and owner: `odowdk45p`, `fletcher_44p` (s12/s13 "See Attachment 1/2"),
`coultonm_43p`, `coultonm_44p`, `coultonm_45p`, `broadbentr_43p`, `broadbentr_44p`,
`broadbentr_45p`, `smitht_45p` (spouse), `clarej_43p`, `freelanderm_45p`, `huntg_44p`. That list
is a starting point, not the answer: T1.1 rebuilds it with a script and T1.2 confirms each file
by looking at the pages.

**Gold precedent.** `eval/gold/plibersekt_43p.json` notes: "Section 13 self says 'see attached
list' -> p8 typed attachment, recorded as initial items on p8". The "see attached" line itself
is not an item there. Rule C12 follows that convention.

**Rule C12 (add to `disclosures/prompts/extract.md`; bump the header to v1).** Use this wording
unless the gold check (T1.4) forces a change:

> - **C12 Attachments.** When a section's cell says "see attached", "see Attachment A", "as per
>   attached list/schedule", or similar, and the attachment is bound into this PDF (a typed
>   list, a schedule, a broker or portfolio statement, a share-registry printout): record ONE
>   item per holding/account/entity listed on the attachment. Each item takes the
>   referencing section, subsection and owner, `page` = the attachment page where that line
>   appears, and the dates and change type of the page that references it (an initial
>   statement → `initial`; an alteration notice → that notice's change type and date). The
>   "see attached" line itself produces no item, unless it also names an interest of its own
>   (e.g. "XYZ Self-Managed Super Fund – see attached" → keep the fund as an item as well).
>   If the attachment is not in this PDF, keep the referencing line as one item (description
>   as printed, `confidence="medium"`) and say so in `extraction_notes`.

Add a checklist line too: "7. Every 'see attached' reference whose attachment is in the PDF has
been itemised from the attachment."

**Re-extraction scope.** Only the files T1.2 confirms. The other ≈ 750 files stay on prompt v0;
C12 only changes attachment handling. Record which files were re-extracted, and why, in
`eval/attachment_gaps.md` and `eval/extraction_failures.md`. Re-extracting the whole corpus
(≈ US$38) is out of scope.

**Not changed (deliberately).** The Sandakan-trek case in `morrisons_43p` / `oakeshottr_43p`
is a judgment call, not an extraction failure. v2 read the trek's sponsor list (BHP Billiton,
Interlink Roads, …) as part of a covering letter (C2: the member paid their own way), and v1
logged the sponsors as travel gifts. Leave it as is and list it as an open question for Kevin
in HANDOFF.md.

---

## D2. Phase 3 (entities): choices the SPEC leaves open

Base: SPEC ADR-6, ADR-7, AC-3.1–3.6.

- **Run order.** `load` builds the DB with empty entity tables, then `entities` runs on that
  DB. `entities` reads items from `disclosures_v2.db` and writes `entities`, `entity_aliases`
  and `items.entity_id`. Always run them in that order: `load`, then `entities` (`refresh` does
  both). Document this in `docs/v2/entities.md`.
- **Committed inputs** make it reproducible with no network and no LLM:
  `data/entities/generic_terms.csv`, `data/entities/aliases.csv`,
  `data/reference/asx_listed_companies_<YYYY-MM-DD>.csv` (newest by date wins) and
  `data/entities/llm_decisions.jsonl` (the long-tail cache).
  `python -m disclosures entities --offline` uses only these and exits 1, listing the blocks,
  if any long-tail block is uncached. The default (online) mode calls the LLM only for
  uncached blocks and appends to the cache.
- **Ids.** `entity_id` = slug of `canonical_name`, made the same way as `member_id`
  (`load.member_slug`). `entity_aliases.alias_normalised` = `normalise_entity(entity_name_raw)`
  (`disclosures/normalise.py`). Running `entities` twice gives identical tables (test it, like
  AC-2.8).
- **Precedence** curated > asx > llm > singleton (ADR-6). `generic` aliases get
  `entity_id = NULL`. Items whose `entity_name_raw` is NULL get no entity (ADR-6 step 1).
- **ASX scope.** An alias is eligible for ASX matching if it occurs on at least one section-1
  item. Once matched, every item with that alias gets the entity, whatever its section.
- **Long tail.** Unresolved aliases with ≥ 2 items are blocked by first token, then rapidfuzz
  `token_set_ratio` ≥ 85 forms the candidates. Each block goes to
  `google/gemini-3.8-flash` via OpenRouter (flex, strict `json_schema`; the model id goes
  through `resolve_gemini_model()`, ADR-5). The LLM returns groups: canonical name,
  `entity_type` (ADR-6 enum), `confidence`. The cache key is sha1 of the sorted block members
  plus the prompt version. Tests mock the HTTP layer (`httpx.MockTransport`, as in
  `tests/test_openrouter.py`). Add a small text-mode method to `disclosures/openrouter.py`
  rather than a second transport.
- **Singletons** (unresolved, 1 item) become their own entity with `method='singleton'` and
  `entity_type = NULL` ("untyped"). Typing ~10k singletons through the LLM isn't worth the
  credit. Document this as a known limitation; it's for Kevin to revisit, not a blocker.
- **Curated table.** `data/entities/aliases.csv` columns: `alias, canonical_name, entity_type,
  asx_code` (SPEC), plus optional `review_flag` and `note`. Every row has an `entity_type`
  (AC-3.2). Use `review_flag` for any row where the agent isn't sure: the merge, the type or
  the ASX code. The agent drafts this table from its own knowledge plus the ASX snapshot.
  There's no API call; it's curation work over T2.3's candidate list.
- **G3 review pack.** `eval/entities_g3_review.csv` holds the top 50 aliases by item count plus
  every flagged row, with columns `rank, alias, item_count, canonical_name, entity_type,
  asx_code, method, review_flag, note, kevin_ok, kevin_fix`. Kevin fills in `kevin_ok` (y) or
  `kevin_fix` (the corrected canonical name / type / code) and marks G3 done (see D6).

## D3. Phase 4 (scraper, 48th, Senate, refresh): facts verified 2026-10-02 and choices

Base: SPEC ADR-8, ADR-9, AC-4.1–4.7. Facts re-checked live on 2026-10-02 with a browser
User-Agent; re-check anything that fails.

**House 48th register** `https://www.aph.gov.au/senators_and_members/members/register`:
HTTP 200, 151 member rows, every row has a statement link. Most link
`https://interests-register-api-public.aph.gov.au/api/members/{id}/statement/48`. That
returns `application/pdf` (`content-disposition: attachment; filename={id}-48.pdf`). The
sample was 11 pages, typed, with a text layer: cheaper than the scanned 43rd–45th and less
likely to hit RECITATION. A handful still link `static.aph.gov.au/.../48P/...pdf`. The page
also links the 43rd–47th archive pages (SPEC §0 URLs; the 47th slug is
`47th_Parliament_Register_of_Members_interests`).
- **API PDFs may be generated on the fly.** Download the same statement twice and compare
  sha256 before you design change detection. If the bytes differ between requests, use the
  listing's "Last updated" date plus page count as the change signal, keep the first
  download, and say so in `docs/v2/scrape.md`. Otherwise AC-4.4 ("0 new, 0 changed" on the
  second run) can never pass.
- **Naming** (ADR-8): `{surname}{first-initial}_48p.pdf`, lower-case ASCII. On a collision, use
  the full given name, then a numeric suffix. The manifest is the source of truth for member
  and parliament, not the filename.
- **New members.** Returning MPs resolve through `member_aliases.csv` (normalised name plus
  electorate). New MPs get `member_id` = slug of "Given Surname" (prefer the Wikipedia form, as
  v1 did) and a `member_aliases.csv` row with `source=aph_48`. Every 48th PDF gets a
  `pdf_members.csv` row.
- **48th parties.** Use the party at the start of the term from Wikipedia "Members of the
  Australian House of Representatives, 2025–2028", mapped through `party_mapping.csv`, with
  the bloc from `political_blocs.csv`. Rows are written with `source=wikipedia_48`. Misses go
  in `unknown_party.csv`; AC-2.9 allows ≤ 5 across all terms.

**Senate 48th: structured JSON, open, no key.** The register page
(`.../Senators_Interests/Senators_Interests_Register`) is a React app. Its config
`/js/apps/senators-interests-register/build/env.js` sets
`SENATORS_API_BASE_URL = https://pbs-apim-aqcdgxhvaug7f8em.z01.azurefd.net/api`. If that host
stops answering, re-read `env.js`. Endpoints (from the app bundle, `main.js`):
- `GET {base}/queryStatements?currentPage=1&pageSize=100&sortBy=senator&sortDirection=ascending`
  returns `{statementOfRegisterableInterests: [...], rowCount: 76, pageCount: 1, wasSuccessful,
  errors}`. Row keys: `cdapId, state, name ("Surname, Given"), lastDateUpdated, lodgmentDate,
  title, postNominal, senatorParty, publishNotes, statementNotes, id`.
- `GET {base}/getSenatorStatement?cdapid={cdapId}` returns `senatorInterestStatement`
  (`lodgementDate`, `lastDateUpdated`, `senatorName`, `senatorParty`, `electorateState`, …)
  plus one object per section, each `{interests: [...], alterations: [...]}`. Alterations
  carry `alterationType` ('Addition' / 'Deletion' / …), `details` and `createdOn`.
- `GET {base}/GetParties`.
- The page loads reCAPTCHA, but on 2026-10-02 the API answered plain GETs (Origin
  `https://www.aph.gov.au`) with no token.
- **Section keys → official numbers** (check against the labels in the bundle):
  `shareHoldings` 1, `trusts` 2, `realEstate` 3 (`location`, `purposeForWhichOwned`),
  `registeredDirectorshipsOfCompanies` 4, `partnerships` 5, `liabilities` 6
  (`natureOfLiability`, `creditor` → `entity_name`), `investments` 7,
  `savingsOrInvestmentAccounts` 8 (`nameOfBankInstitution` → `entity_name`), `otherAssets` 9,
  `otherIncome` 10, `gifts` 11, `sponsoredTravelOrHospitality` 12, `officeHolderDonating` 13,
  `otherInterest` 14. List every key seen across all 76 payloads; an unmapped key is an error,
  not a silent drop.
- **Adapter, no LLM** (ADR-9), `source_id = senate-json`. Save each raw payload, pretty-printed
  with sorted keys, at `pdfs/senate/48/{surname}{first-initial}_48s.json`. That file is the
  "source document": `pdf_path` points at it and `pdf_sha256` is its sha256. Use
  `page_count = 1` and `pages_covered = [1]`. Interests become `is_alteration=false`,
  `change_type="initial"` and `lodged_date` = the `lodgementDate` date. Alterations become
  `is_alteration=true`, change type from `alterationType` (Addition → added, Deletion →
  removed, Variation/Change → varied, else unknown) and `lodged_date` = the `createdOn` date.
  `owner` is always `self` (Form B is confidential). Set `page=1`, `confidence="high"` and
  `extraction_notes = "structured source: APH senators' interests API"`.
- **Validator change (needs a DECISIONS.md entry).** `validate` must accept a `.json` source
  document. Check its sha256 and require `page_count == 1`; skip PyMuPDF. The ADR-2 schema
  itself is unchanged.
- **Loader.** `--source` becomes repeatable (`load --source gemini-api --source senate-json`).
  Senate members resolve through `pdf_members.csv` rows keyed by the JSON source path, and
  `member_aliases.csv` handles people who moved chambers. `members.chamber` is the chamber of
  the member's most recent term; `member_terms` keeps one row per chamber and parliament.
  48th Senate party comes from the API's `senatorParty` (`source=aph_senate_api`). Note that
  this is the current party, not the start-of-term party.
- **Senate archives (43rd–47th): discovery only.** Check whether `queryStatements` takes a
  parliament parameter, and what the archive pages (`.../Register44thparl` etc.) link to.
  Document the findings in `docs/v2/senate_source.md`. If they are PDFs, record the count and
  estimated cost as a follow-up: extracting them is out of scope (credit), which ADR-9 accepts.

## D4. Budget (OpenRouter credit)

Credit on 2026-10-02: **US$18.87** remaining of 70. Estimated spend for this plan:
| Task | Cap (US$) | Estimate |
|---|---|---|
| T1.4 gold regression (12 PDFs, prompt v1; one revision allowed) | 1.20 | ≈ 0.50 |
| T1.5 re-extract confirmed attachment files (≤ 15) | 3.00 | ≈ 1.50 |
| T2.6 entities long tail | 3.00 | ≈ 1–2 |
| T3.5 House 48th (≈ 151 typed PDFs) | 8.00 | ≈ 5–6 |
| T3.10 entities on the new names | 1.00 | ≈ 0.50 |
| **Total** | **16.20** | **≈ 9–11** |

Rules: check `python3 scripts/ralph/credit.py --min 3` before every paid command. Never start
a paid command when it exits non-zero, or when the task's running `spent:` plus the next batch's
estimate would pass its cap. Instead set `status: blocked (kevin): OpenRouter top-up needed
(remaining US$x, task needs ≈ US$y)`. Record the actual spend from the extractor's summary in
the task's `spent:` line and in PROGRESS.md. The G2 configuration is fixed (SPEC/DECISIONS
G2): Gemini 3.8 Flash on `google-ai-studio/flex`, Sonnet 5.5 fallback, `--ignore-providers
azure`. Don't change models to save money.

## D5. Branches, pushing, outward actions

- **Local run:** work on `v2-upgrade`; commit after every task; **don't push** (Kevin pushes,
  SPEC non-goals).
- **Cloud run:** work on the session's own `claude/*` branch. The push rule is keyed on the
  branch name, not an environment variable: push (`git push -u origin HEAD`) after every task
  only when the branch starts with `claude/`, because the container can be reclaimed.
  `bootstrap.sh` refuses to run a cloud session on a non-`claude/*` branch, and prints the
  push rule every iteration. At STOP, open one PR against `v2-upgrade` if this branch has none
  (if you can't, say so in HANDOFF). Never push to `v2-upgrade` or `main`; never force-push.
- **Deviation from SPEC Non-goals** ("Kevin performs all outward-facing actions: `git push`"):
  cloud runs push their own `claude/*` branch and open a PR, which is the only way work leaves
  the container (as the Phase 2 backfill did). Merging and every push to `v2-upgrade`/`main`
  stay Kevin's. Recorded in DECISIONS.md, 2026-10-02.
- Never enable GitHub Pages, upload to Kaggle, post anywhere, or open issues (G4 is Kevin's).
- Before switching between local and cloud runs, Kevin merges the other side first (RUNNING.md).
  Don't run two loops at once: they share the plan file.

## D6. Gates and blocks

- **G3** (`owner: kevin` in the plan). The agent prepares the review pack (T2.8), then stops
  when nothing else is ready. Kevin marks it done in one of two ways: edit the G3 block to
  `- status: done <date>` and commit, or, in a cloud session, say so in his own message
  ("G3 approved"). In the second case the agent quotes his message in the G3 block's notes and
  flips it. Fixes go in `eval/entities_g3_review.csv` (`kevin_fix`); T2.9 applies them.
- **G4** (`owner: kevin`): publication, which is always Kevin's.
- **Ad-hoc blocks** use `status: blocked (kevin): …` or `blocked (network): …` with the exact
  command Kevin must run. Typical ones: OpenRouter top-up; a host blocked by the cloud network
  policy (Kevin runs that step locally and pushes); the prompt v1 gold regression failing
  twice (T1.4).
- An agent never marks an `owner: kevin` item done on its own judgment.

## D7. Out of scope for this plan

Extracting Senate archives; extending the gold set with a 48th PDF (ADR-3 says "not
blocking"); re-extracting the corpus on prompt v1; changing the G2 models; typing singleton
entities; anything in SPEC Non-goals.
