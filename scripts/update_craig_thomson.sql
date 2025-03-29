-- Add Craig Thomson to the database with Labor affiliation

-- Check if Craig Thomson already exists
INSERT INTO disclosures (id, mp_name, party, electorate, political_bloc, category, declaration_date)
SELECT 
    'CT' || strftime('%s', 'now'), 
    'Craig Thomson', 
    'Australian Labor Party', 
    'Dobell', 
    'Labor', 
    'Unknown', 
    date('now')
WHERE NOT EXISTS (
    SELECT 1 FROM disclosures WHERE mp_name = 'Craig Thomson'
);

-- If he already exists, update his party and political bloc
UPDATE disclosures 
SET party = 'Australian Labor Party', political_bloc = 'Labor'
WHERE mp_name = 'Craig Robert Thomson'; 