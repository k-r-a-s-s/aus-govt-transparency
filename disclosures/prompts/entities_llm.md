You are standardising the names of organisations, funds and people that Australian federal
members of parliament disclosed on their Register of Members' Interests. The 14 register
sections are: 1 shareholdings, 2 trusts and nominee companies, 3 real estate, 4 directorships,
5 partnerships, 6 liabilities (creditor), 7 bonds and debentures, 8 savings and investment
accounts (bank), 9 other assets, 10 other income, 11 gifts, 12 sponsored travel or hospitality,
13 memberships, 14 other interests.

Below are BLOCKS of normalised names (lower case, punctuation and legal suffixes such as
"pty ltd" removed). Each name shows how many register items use it, the sections it appears
in, and its commonest spellings as printed. Names in one block share a first word and look
alike; a block may also hold a single name.

For each block, split its names into GROUPS. Names belong in one group only if they clearly
refer to the same organisation, fund or person (spelling variants, typos, with or without
"group", "australia", "pty ltd" and the like). When unsure, keep names apart. Rules:
- A trust and its trustee company are different entities ("Smith Family Trust" vs
  "Smith Holdings Pty Ltd"), and so are different funds of one manager ("Vanguard
  Australian Shares Index Fund" vs "Vanguard Diversified Growth"). Different clubs, councils,
  branches, chapters or state branches stay separate ("Rotary Club of Ballarat" vs "Rotary
  Club of Bendigo"; "Labor NSW" vs "Labor Victoria").
- Keep each brand as disclosed (a subsidiary bank or brand is not merged into its parent).
- Lounges, clubs and frequent-flyer programmes belong with the airline that runs them.
- A name joining two organisations ("qantas and virgin") is its own group.

Every name in a block must appear in exactly one of that block's groups, spelled exactly as
given. For each group give:
- `canonical_name`: the organisation's proper display name, in its usual capitalisation
  (e.g. "Commonwealth Bank of Australia", "Rotary Club of Ballarat", "Smith Family Trust").
  Drop "Pty Ltd"/"Limited" for well-known companies, keep it where the name would otherwise be
  just a surname or a generic phrase.
- `entity_type`, one of:
  `listed_company` (listed on a stock exchange), `private_company`, `bank_or_financial`
  (banks, credit unions, insurers, super funds, fund managers and their funds),
  `airline`, `sporting_body` (clubs, leagues, codes), `media_or_entertainment`,
  `government_body` (departments, councils, agencies, state-owned bodies), `union`, `political_party`, `association_or_ngo` (associations, charities,
  service clubs, think tanks, chambers), `education` (schools, universities, colleges),
  `person`, `trust_or_fund` (family or private trusts, private super funds),
  `other` (anything else, or not identifiable).
- `confidence`: `high` (you are sure of the grouping and the type), `medium`, or `low`.

Return JSON only, with one entry per block, using the block ids given.
