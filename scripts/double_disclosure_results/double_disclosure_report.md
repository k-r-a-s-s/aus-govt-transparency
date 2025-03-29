# Double Disclosure Analysis Report

## Summary

- Total disclosures: 30469
- Potential double disclosures: 1988 (6.52%)

## Separator Analysis

Common separators found in entity names:

- ",": 1047 occurrences
- "and": 721 occurrences
- "/": 332 occurrences
- "&": 26 occurrences
- "+": 22 occurrences

## Top Double Entities

Most frequent potential double entities:

1. "Andrews and Andrews Consulting Pty Ltd" (15 occurrences) - Possible split: Andrews | Andrews Consulting Pty Ltd
2. "Taipei Economic and Cultural Office" (15 occurrences) - Possible split: Taipei Economic | Cultural Office
3. "Qantas, Virgin" (13 occurrences) - Possible split: Qantas | Virgin
4. "Australian Subscription Television and Radio Association" (12 occurrences) - Possible split: Australian Subscription Television | Radio Association
5. "Taipei Economic and Cultural Office in Australia" (11 occurrences) - Possible split: Taipei Economic | Cultural Office in Australia
6. "Australian and New Zealand Banking Group Limited (ANZ)" (10 occurrences) - Possible split: Australian | New Zealand Banking Group Limited (ANZ)
7. "Australian and New Zealand Banking Group Limited" (10 occurrences) - Possible split: Australian | New Zealand Banking Group Limited
8. "Australian Subscription Television and Radio Association (ASTRA)" (10 occurrences) - Possible split: Australian Subscription Television | Radio Association (ASTRA)
9. "Qantas and Virgin" (10 occurrences) - Possible split: Qantas | Virgin
10. "Community and Public Sector Union" (9 occurrences) - Possible split: Community | Public Sector Union
11. "Pericles Unit Trust/Elysium Pty Ltd" (9 occurrences) - Possible split: Pericles Unit Trust | Elysium Pty Ltd
12. "PK Super (Qld) P/L" (9 occurrences) - Possible split: PK Super (Qld) P | L
13. "CBA, ANZ" (8 occurrences) - Possible split: CBA | ANZ
14. "Liberal Party of Australia, NSW Division" (8 occurrences) - Possible split: Liberal Party of Australia | NSW Division
15. "Pebema P/L" (8 occurrences) - Possible split: Pebema P | L
16. "Tura Beach, NSW" (8 occurrences) - Possible split: Tura Beach | NSW
17. "Royal Motor Yacht Club, Woolooware" (7 occurrences) - Possible split: Royal Motor Yacht Club | Woolooware
18. "Bendigo and Adelaide Bank" (7 occurrences) - Possible split: Bendigo | Adelaide Bank
19. "Qantas and Virgin Australia" (7 occurrences) - Possible split: Qantas | Virgin Australia
20. "Bendigo/Adelaide Bank" (6 occurrences) - Possible split: Bendigo | Adelaide Bank

## Matched Canonical Entities

Double entities with matches to existing canonical entities:

1. "ADELAIDE BANK AND RISMARK (THROUGH PERMANENT CUSTODIANS)" - Matched with: National Mortgage Market - Adelaide Bank, A
2. "MR MAX LIONDOS, LIONDOS TAILORS, SYDNEY" - Matched with: MR MAX LIONDOS, LIONDOS TAILORS, SYDNEY, MR MAX LIONDOS, LIONDOS TAILORS, SYDNEY, Sydney Adventist Hospital Zipper and Stent Club
3. "Melbourne Cricket Club (MCC) and Cricket Australia" - Matched with: Melbourne Cricket Club, Cricket Australia
4. "CBA, ANZ" - Matched with: CBA, ANZ
5. "Dulwich High School of Visual Arts and Design" - Matched with: A, S
6. "Vladimir Yakunin, President of Russian Railways" - Matched with: A, A
7. "Ipswich Motorway Construction Company, Origin Alliance" - Matched with: Ipswich Motorway Construction Company, Origin Alliance, Ipswich Motorway Construction Company, Origin Alliance
8. "Emirates and Lion" - Matched with: Emirates, Lion
9. "Ministry of Economy, United Arab Emirates" - Matched with: Ministry of Economy, United Arab Emirates, United Arab Emirates
10. "Minister for the Indonesian Search and Rescue Agency" - Matched with: Indonesia, A
11. "Channel 9 and Qantas" - Matched with: Channel 9 and Qantas, Qantas
12. "Chen Yuming, Chinese Embassy in Australia" - Matched with: Chen Yuming, Chinese Embassy in Australia, Chen Yuming, Chinese Embassy in Australia
13. "Qantas and Emirates" - Matched with: Qantas, Emirates
14. "Westpac and Rhymney Pty Ltd" - Matched with: Westpac, R
15. "Santos and Orica Green Edge" - Matched with: Santos, Orica Green Edge
16. "Shell and Optus" - Matched with: Seashells Resort Broome, Optus
17. "Andrews and Andrews Consulting Pty Ltd" - Matched with: Andrews, A
18. "Australian and New Zealand Banking Group Limited (ANZ)" - Matched with: Australian Access Capital Comapny Pty Ltd, A
19. "artwork / vehicle" - Matched with: A, Vehicle Amoarok
20. "Australian and New Zealand Banking Group Limited" - Matched with: Australian Access Capital Comapny Pty Ltd, A

## Recommendations

Based on the analysis, we recommend:

1. Split double disclosures into individual disclosure records
2. Use existing canonical entities where possible
3. Update the data ingestion pipeline to automatically handle double disclosures
4. Consider normalizing banking institutions and other common entity groups

## Implementation Approach

To handle double disclosures, we can:

1. Create a script to identify and split double disclosures
2. For each double disclosure, create multiple new disclosure records
3. Maintain the original disclosure data in a new 'original_entity' field
4. Update all related database indexes and views
