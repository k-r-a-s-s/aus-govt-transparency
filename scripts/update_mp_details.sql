-- Update MP details with correct party names and electorates

-- Add missing MPs
INSERT INTO disclosures (id, mp_name, party, electorate, political_bloc, category, declaration_date)
VALUES ('LMF' || strftime('%s', 'now'), 'Louise Miller-Frost', 'Australian Labor Party', 'Boothby', 'Labor', 'Unknown', date('now'));

INSERT INTO disclosures (id, mp_name, party, electorate, political_bloc, category, declaration_date)
VALUES ('AS' || strftime('%s', 'now'), 'Alexander Somlyay', 'Liberal Party of Australia', 'Fairfax', 'Coalition', 'Unknown', date('now'));

-- Jenny Ware - Liberal Party - Hughes
UPDATE disclosures 
SET party = 'Liberal Party of Australia', electorate = 'Hughes', political_bloc = 'Coalition'
WHERE mp_name = 'Jenny Ware';

-- Louise Miller-Frost - Australian Labor Party - Boothby
UPDATE disclosures 
SET party = 'Australian Labor Party', electorate = 'Boothby', political_bloc = 'Labor'
WHERE mp_name = 'Louise Miller-Frost';

-- Robert Charles Baldwin - Liberal Party - Paterson
UPDATE disclosures 
SET party = 'Liberal Party of Australia', electorate = 'Paterson', political_bloc = 'Coalition'
WHERE mp_name = 'Robert Charles Baldwin';

-- Sam Rae - Australian Labor Party - Hawke
UPDATE disclosures 
SET party = 'Australian Labor Party', electorate = 'Hawke', political_bloc = 'Labor'
WHERE mp_name = 'Sam Rae';

-- Alexander Somlyay - Liberal Party - Fairfax
UPDATE disclosures 
SET party = 'Liberal Party of Australia', electorate = 'Fairfax', political_bloc = 'Coalition'
WHERE mp_name = 'Alexander Somlyay';

-- Sophie Scamps - Independent - Mackellar
UPDATE disclosures 
SET party = 'Independent', electorate = 'Mackellar', political_bloc = 'Independent'
WHERE mp_name = 'Sophie Scamps';

-- Stephen Bates - Australian Greens - Brisbane
UPDATE disclosures 
SET party = 'Australian Greens', electorate = 'Brisbane', political_bloc = 'Greens'
WHERE mp_name = 'Stephen Bates';

-- Timothy Jerome Hammond - Australian Labor Party - Perth
UPDATE disclosures 
SET party = 'Australian Labor Party', electorate = 'Perth', political_bloc = 'Labor'
WHERE mp_name = 'Timothy Jerome Hammond'; 