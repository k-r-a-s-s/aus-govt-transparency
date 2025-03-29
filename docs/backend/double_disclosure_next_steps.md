# Double Disclosure: Next Steps

This document outlines the next steps for implementing double disclosure handling in the Australian Government Transparency Project.

## Summary of Analysis

We have completed an initial analysis of double disclosures in our database:

- **Detection**: We identified 1,988 potential double disclosures (6.52% of all disclosures) containing common separators like commas, "and", and slashes.

- **Patterns**: The most frequent patterns involve banking institutions, government agencies, and pairs of companies (e.g., "Qantas, Virgin").

- **False Positives**: Some entities containing separators are single organizations with compound names, such as "Andrews and Andrews Consulting Pty Ltd" and "Australian and New Zealand Banking Group Limited".

## Implementation Plan

### Phase 1: Manual Review (Current)

1. **Review Template Created**: We've generated a proposed mapping file (`proposed_entity_mapping.json`) containing the top 100 potential double disclosures.

2. **Specific Entity Subsets**: We can extract specific entity patterns (e.g., Shell-related) for targeted review using the `--extract` option.

3. **Manual Editing**: The reviewing team should edit these JSON files to:
   - Remove entries that are false positives
   - Correct split suggestions that are incorrect
   - Add missing split possibilities

### Phase 2: Database Schema Update

1. **Add Original Entity Column**:
   ```sql
   ALTER TABLE disclosures ADD COLUMN original_entity TEXT;
   UPDATE disclosures SET original_entity = entity;
   ```

2. **Index New Column**:
   ```sql
   CREATE INDEX idx_original_entity ON disclosures(original_entity);
   ```

### Phase 3: Implementation

1. **Execute Implementation Script**: Run the double disclosure implementation script with the reviewed mapping:
   ```
   python scripts/double_disclosure_implementation.py --reviewed-file scripts/double_disclosure_results/reviewed_entity_mapping.json
   ```

2. **Verify Results**: Check the database for correct splitting and original entity preservation.

3. **Update API**: Modify the API to support querying both `entity` and `original_entity`.

### Phase 4: Frontend Integration

1. **Entity Explorer Updates**:
   - Modify the Entity Explorer to show a note when an entity was part of a split
   - Add ability to view all splits of the same original entity
   - Update entity search to include matches in original_entity

2. **Visualization Updates**: Update entity relationship diagrams to handle split entities appropriately.

## Benefits

Implementing this approach will:

1. **Improve Data Accuracy**: Each entity will be properly counted and tracked.

2. **Enhance Search**: Users will find all disclosures related to an entity, regardless of how it was originally recorded.

3. **Maintain Data Integrity**: Original data is preserved via the original_entity field.

4. **Better Analytics**: More accurate statistics on entity frequency and relationships.

## Risks and Mitigations

1. **Risk**: False positives could be incorrectly split.
   **Mitigation**: Thorough manual review by domain experts before implementation.

2. **Risk**: Database schema changes could impact existing functionality.
   **Mitigation**: Run in dry-run mode first and thoroughly test all changes.

3. **Risk**: Processing time for large numbers of splits.
   **Mitigation**: Batch processing and progress reporting.

## Timeline

| Phase | Task | Estimated Time | Dependencies |
|-------|------|----------------|--------------|
| 1 | Manual Review of Proposed Mappings | 2-3 days | None |
| 2 | Database Schema Update | 1 day | Completed Review |
| 3 | Implementation Script Execution | 1 day | Schema Update |
| 4 | API and Frontend Updates | 2-3 days | Implementation |
| - | Testing and Verification | 1-2 days | All Above |

## Getting Started

To begin the manual review process:

1. Review the full list of potential double disclosures in:
   `scripts/double_disclosure_results/potential_double_disclosures.csv`

2. Edit the proposed mapping template:
   `scripts/double_disclosure_results/proposed_entity_mapping.json`

3. For specific entities, create targeted review files:
   ```
   python scripts/double_disclosure_review.py --extract PATTERN
   ```

4. Merge reviewed subsets back into the full mapping:
   ```
   python scripts/double_disclosure_review.py --merge scripts/double_disclosure_results/reviewed_PATTERN.json
   ``` 