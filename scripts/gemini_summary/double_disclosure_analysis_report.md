# Double Disclosure Entity Analysis Report

## Summary

- Total entities analyzed: 1478
- Single entities: 535 (36.2%)
- Multiple entities: 943 (63.8%)
- High confidence classifications: 1353 (91.54%)
- High confidence multiple entities: 868 (58.73%)

## Entities by Separator

| Separator | Count |
|-----------|-------|
| and | 501 |
| ampersand | 58 |
| comma | 719 |
| slash | 174 |
| plus | 12 |
| other | 14 |

## Next Steps

1. Review the [CSV file](double_disclosure_entity_analysis.csv) to validate the analysis results
2. Focus on high confidence multiple entities for database updates
3. Manually review medium and low confidence classifications
4. Update the database schema with a new column for original_entity
5. Apply the validated mappings to split entities in the database
