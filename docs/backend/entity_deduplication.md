# Entity Deduplication

Entity deduplication is a crucial data standardization step in the Australian Government Transparency Project. This process addresses the issue of inconsistent entity naming in disclosure records, where the same organization might be listed under multiple variations of its name.

## Problem Statement

Political donation and disclosure records often contain inconsistencies in entity names due to:

- Different spellings or capitalization (e.g., "Shell Australia" vs "shell Australia")
- Inclusion/exclusion of legal entity types (e.g., "Shell Company of Australia" vs "Shell Company of Australia Limited")
- Abbreviations (e.g., "BHP" vs "BHP Billiton")
- Name changes over time

These inconsistencies make it difficult to:
1. Track the total contributions from a single entity
2. Analyze patterns of influence across the political landscape
3. Understand the true network of connections between politicians and entities

## Deduplication Approach

Our approach to entity deduplication involves:

1. **Analysis**: Identifying potential duplicate entities using fuzzy matching
2. **Review**: Human review of potential matches to avoid false positives
3. **Implementation**: Creating canonical entity names while preserving original data
4. **Integration**: Using canonical entities in API endpoints and UI components

## Workflow

### 1. Analysis Phase

The analysis script (`scripts/entity_dedupe_analysis.py`) performs the following:

```python
# Key steps in analysis script
1. Load all unique entity names from the database
2. Generate similarity scores between entity names using fuzzy matching algorithms
3. Create clusters of potentially related entities
4. Output proposed mappings for review
```

The script uses a combination of techniques:
- Levenshtein distance for string similarity
- TF-IDF vectorization for content similarity
- Manual rules for common patterns (e.g., "Ltd." vs "Limited")

### 2. Review Phase

The review process (`scripts/entity_dedupe_review.py`) facilitates human verification:

```python
# Key steps in review script
1. Load proposed entity mappings
2. Allow manual editing of mappings
3. Support for partial reviews of specific entities
4. Merge reviewed subsets back into the main mapping
```

This ensures that:
- False positives are eliminated
- Complex cases receive human judgment
- The final mapping is of high quality

### 3. Implementation Phase

The implementation script (`scripts/entity_dedupe_implementation.py`) applies the reviewed mappings:

```python
# Key steps in implementation script
1. Add a canonical_entity column to the disclosures table
2. Set default mapping where each entity maps to itself
3. Update canonical_entity values based on the mapping
4. Create an index on the canonical_entity column
```

The script includes a `--dry-run` option for testing changes before applying them to the database.

## Database Schema Changes

The entity deduplication process modifies the database schema:

```sql
-- Add canonical_entity column
ALTER TABLE disclosures ADD COLUMN canonical_entity TEXT;

-- Set default values (each entity maps to itself)
UPDATE disclosures SET canonical_entity = entity;

-- Apply mappings
UPDATE disclosures SET canonical_entity = ? WHERE entity = ?;

-- Create index for performance
CREATE INDEX idx_canonical_entity ON disclosures(canonical_entity);
```

## API Integration

The canonical entity feature is integrated into API endpoints:

1. Entity-related endpoints accept a `canonical` query parameter:
   - `GET /api/entities?canonical=true`
   - `GET /api/entity/:name?canonical=true`
   - `GET /api/search/entities?q=shell&canonical=true`

2. The `NetworkData` endpoint accepts a `canonical` parameter to display canonical entities in the network visualization:
   - `GET /api/network?canonical=true`

3. Response data includes variant information when using canonical entities:
   ```json
   {
     "entity": "Shell Company of Australia Limited",
     "variants": [
       "Shell Australia",
       "shell Australia",
       "Shell Company of Australia"
     ],
     "count": 5,
     "connected_mps": [...]
   }
   ```

## Scripts Documentation

### Entity Deduplication Analysis

**Location**: `scripts/entity_dedupe_analysis.py`

**Purpose**: Analyze entity names to identify potential duplicates.

**Arguments**:
- `--threshold`: Similarity threshold (default: 0.85)
- `--min-count`: Minimum entity count to consider (default: 1)
- `--output-dir`: Directory for output files (default: scripts/entity_dedupe_results)

**Outputs**:
- `potential_duplicates.csv`: CSV file of entity pairs and their similarity scores
- `proposed_entity_mapping.json`: JSON mapping of variant entities to canonical forms

### Entity Deduplication Review

**Location**: `scripts/entity_dedupe_review.py`

**Purpose**: Review and modify proposed entity mappings.

**Arguments**:
- `--input`: Input mapping file (default: proposed_entity_mapping.json)
- `--output`: Output file for reviewed mapping (default: reviewed_entity_mapping.json)
- `--subset`: Extract a subset of entities for review (e.g., "Shell")
- `--merge`: Merge a reviewed subset back into the full mapping

**Outputs**:
- `reviewed_entity_mapping.json`: JSON mapping after human review
- `reviewed_[subset].json`: JSON mapping for a specific subset of entities

### Entity Deduplication Implementation

**Location**: `scripts/entity_dedupe_implementation.py`

**Purpose**: Apply the reviewed entity mappings to the database.

**Arguments**:
- `--dry-run`: Simulate changes without modifying the database
- `--mapping`: Path to the entity mapping file
- `--reviewed`: Use the reviewed mapping file

**Outputs**:
- Console output showing affected rows and statistics
- Database changes (unless in dry-run mode)

## Results and Impact

The entity deduplication process significantly improves data quality:

- Reduction in unique entities: ~20% fewer entities after deduplication
- Improved entity analysis: More accurate counts and connections
- Better user experience: Cleaner visualization of entity networks

Example case study - "Shell":
- Before: 4 separate entities ("Shell Australia", "shell Australia", "Shell Company of Australia", "The Shell Company of Australia Limited")
- After: Consolidated into canonical forms with proper relationships

## Best Practices

When working with entity deduplication:

1. Always review proposed mappings carefully
2. Consider domain-specific knowledge when evaluating potential matches
3. Maintain transparency by preserving original entity names
4. Use the canonical parameter in API requests when analyzing aggregated data
5. Monitor for new variants that may need to be added to mappings over time

## Conclusion

Entity deduplication is an ongoing process that significantly enhances the quality and analytical value of the disclosure data. The combination of automated analysis and human review ensures high accuracy while addressing the challenging problem of entity name variants. 