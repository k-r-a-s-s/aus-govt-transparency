# Double Disclosure Analysis

## Overview

This document summarizes the findings of the double disclosure analysis conducted on the Australian Government Transparency Project database. The analysis aimed to identify and quantify the issue of "double disclosures" - instances where multiple entities are mentioned in a single entity field, such as "Shell and Optus" or "CBA, ANZ".

## Key Findings

- **Prevalence**: Out of 30,469 total disclosures in the database, 1,988 (6.52%) are potential double disclosures based on the presence of common separators.

- **Separator Patterns**: The most common separators indicating multiple entities are:
  - Comma (,): 1,047 occurrences
  - "and": 721 occurrences 
  - Forward slash (/): 332 occurrences
  - Ampersand (&): 26 occurrences
  - Plus (+): 22 occurrences

- **Common Examples**: The most frequent double disclosures include:
  - "Andrews and Andrews Consulting Pty Ltd" (15 occurrences)
  - "Taipei Economic and Cultural Office" (15 occurrences)
  - "Qantas, Virgin" (13 occurrences)
  - "Australian Subscription Television and Radio Association" (12 occurrences)
  - "Australian and New Zealand Banking Group Limited" (10 occurrences)

- **Banking Institutions**: Financial institutions are frequently represented in combined forms:
  - "CBA, ANZ"
  - "Bendigo and Adelaide Bank" 
  - "Bendigo/Adelaide Bank"
  - "Wizard, GE Money, Commonwealth Bank"

- **False Positives**: Some entities containing separators are single organizations with compound names, not true double disclosures. Examples include:
  - "Andrews and Andrews Consulting Pty Ltd" (likely a single law firm)
  - "Australian and New Zealand Banking Group Limited" (formal name of ANZ)
  - "Community and Public Sector Union" (single organization)

## Impact on Entity Deduplication

The presence of double disclosures creates challenges for the entity deduplication process:

1. **Duplicate Creation**: When entity A and entity B appear together as "A and B", they create a third unique entity in the database.

2. **Canonical Entity Matching**: Our existing canonical entity mapping may not correctly handle split entities.

3. **Statistical Accuracy**: Double disclosures skew statistics about entity frequency and influence.

4. **Search Functionality**: Users searching for a single entity (e.g., "Shell") may not find records where it appears in combined form (e.g., "Shell and Optus").

## Recommendations

Based on the analysis, we recommend the following approach:

### Short-term Actions

1. **Manual Review of Top Cases**: Review the top 100 most frequent double disclosures to distinguish:
   - True double disclosures (separate entities combined in one field)
   - False positives (compound names that should remain as single entities)

2. **Database Schema Enhancement**: Add an `original_entity` column to preserve the original combined entity text.

3. **Split High-impact Doubles**: Create a script to split the most common true double disclosures (e.g., "Qantas, Virgin") into separate disclosure records.

### Medium-term Strategy

1. **Automated Splitting Framework**: Develop a consistent approach for automatically identifying and handling double disclosures during data processing.

2. **API Enhancement**: Update the API to support queries that can recognize both individual and combined entity forms.

3. **Frontend Updates**: Modify the Entity Explorer to handle and display split entities appropriately.

### Long-term Improvements

1. **Data Collection Guidelines**: Establish standards for data entry that discourage double disclosures in future data collection.

2. **Machine Learning Classification**: Implement ML models to distinguish between true double disclosures and compound entity names.

3. **Entity Relationship Tracking**: Create a system to track when entities frequently appear together in disclosures.

## Implementation Plan

The recommended implementation approach consists of these steps:

1. **Database Schema Update**:
   ```sql
   ALTER TABLE disclosures ADD COLUMN original_entity TEXT;
   UPDATE disclosures SET original_entity = entity;
   ```

2. **Split Entity Processing**:
   - Create a script that:
     - Identifies double disclosures using regex patterns
     - Splits the entity field
     - Creates new disclosure records for each entity
     - Sets the canonical_entity field appropriately
     - Preserves the original entity in the original_entity field

3. **Update Frontend**:
   - Modify Entity Explorer to show both individual entities and their original combined form
   - Update entity search to include results from original_entity matches

## Next Steps

1. Conduct a manual review of the top double disclosures to confirm which should be split
2. Create a prioritized list of true double disclosures for implementation
3. Implement database schema updates
4. Develop and test the entity splitting script
5. Apply the changes to the production database
6. Update documentation and user interfaces

## Appendix: Sample Double Disclosures

The full dataset of potential double disclosures is available in:
- `scripts/double_disclosure_results/potential_double_disclosures.csv`
- `scripts/double_disclosure_results/double_disclosure_analysis.json`
- `scripts/double_disclosure_results/double_disclosure_report.md` 