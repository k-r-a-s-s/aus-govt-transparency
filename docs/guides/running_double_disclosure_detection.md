# Guide: Running the Double Disclosure Detection Workflow

This guide walks through the complete process of detecting and processing double disclosures using the Gemini-powered workflow.

## Prerequisites

- Python 3.8 or higher
- SQLite database with disclosure data
- Google API key with access to Gemini API
- Required Python packages:
  - google-generativeai
  - pandas
  - sqlite3
  - tqdm

## Step 1: Prepare Input Data

First, you need to identify potential double disclosures in your database:

```bash
# Generate the CSV of potential double disclosures
python scripts/double_disclosure_analysis.py \
  --db-path disclosures.db \
  --output-dir scripts/double_disclosure_results
```

This will generate a CSV file with potential double disclosures at `scripts/double_disclosure_results/potential_double_disclosures.csv`.

## Step 2: Prepare Data for Gemini Analysis

Next, prepare the data in batches for the Gemini API:

```bash
# Create batch files for Gemini analysis
python scripts/prepare_gemini_entity_analysis.py \
  --input-file scripts/double_disclosure_results/potential_double_disclosures.csv \
  --output-dir scripts/gemini_batches \
  --batch-size 50
```

This will create batch files in the `scripts/gemini_batches` directory, with each file containing up to 50 entities for analysis.

## Step 3: Run Gemini Analysis

Now, use the Gemini API to analyze the batches:

```bash
# Create a file with your API key
echo "YOUR_API_KEY" > .gemini_api_key

# Run the analysis
python scripts/gemini_entity_analyzer.py \
  --input-dir scripts/gemini_batches \
  --output-dir scripts/gemini_results \
  --api-key-file .gemini_api_key \
  --model gemini-1.5-flash-latest
```

This will analyze each batch and save the results in the `scripts/gemini_results` directory, along with a compiled results file.

> **Note**: For large datasets, this may take some time and incur API usage costs. Consider running a small batch first as a test.

## Step 4: Review Results (Optional)

Before applying changes to your database, you might want to review the results:

```bash
# Extract a summary of results
python scripts/summarize_gemini_results.py \
  --input-file scripts/gemini_results/compiled_results.json \
  --output-file scripts/gemini_results/summary.csv
```

This will create a CSV summary that you can open in a spreadsheet program to review the classifications and proposed splits.

## Step 5: Run a Dry Run

It's recommended to first run the application script in dry-run mode to see what changes would be made:

```bash
# Perform a dry run
python scripts/apply_gemini_entity_results.py \
  --input-file scripts/gemini_results/compiled_results.json \
  --db-path disclosures.db \
  --dry-run
```

Review the output to ensure the proposed changes look correct.

## Step 6: Apply Changes to Database

When you're ready to apply the changes to your database:

```bash
# Apply changes to the database (only HIGH confidence)
python scripts/apply_gemini_entity_results.py \
  --input-file scripts/gemini_results/compiled_results.json \
  --db-path disclosures.db
```

By default, this will only apply HIGH confidence MULTIPLE entity splits. If you want to apply other confidence levels:

```bash
# Apply MEDIUM and HIGH confidence splits
python scripts/apply_gemini_entity_results.py \
  --input-file scripts/gemini_results/compiled_results.json \
  --db-path disclosures.db \
  --confidence MEDIUM
```

## Step 7: Verify Results

After applying changes, verify that the database was updated correctly:

```bash
# Check some example entities
sqlite3 disclosures.db "SELECT entity, original_entity, COUNT(*) as count FROM disclosures WHERE original_entity IS NOT NULL GROUP BY entity, original_entity LIMIT 10"
```

You should see the original entity names and their splits in the results.

## Troubleshooting

### API Rate Limits

If you encounter rate limit errors with the Gemini API:

1. Increase the delay between API calls using the `--api-delay` parameter
2. Process smaller batches at a time with `--batch-size`

### Error Handling

If the process is interrupted, you can continue from where you left off:

```bash
# Continue processing from a specific batch
python scripts/gemini_entity_analyzer.py \
  --input-dir scripts/gemini_batches \
  --output-dir scripts/gemini_results \
  --api-key-file .gemini_api_key \
  --batch-id batch_5.json
```

### Database Backup

Always make a backup of your database before applying changes:

```bash
# Backup the database
cp disclosures.db disclosures_backup_$(date +%Y%m%d).db
```

## Extending the Workflow

### Adding New Separators

If you want to detect additional separators:

1. Modify the `SEPARATOR_PATTERNS` in `double_disclosure_analysis.py`
2. Re-run the analysis pipeline

### Adjusting Confidence Thresholds

You can adjust how conservative the system is by modifying the confidence thresholds:

```bash
# Apply only the highest confidence splits
python scripts/apply_gemini_entity_results.py \
  --input-file scripts/gemini_results/compiled_results.json \
  --db-path disclosures.db \
  --confidence HIGH

# Apply all confidence levels for multiple entities
python scripts/apply_gemini_entity_results.py \
  --input-file scripts/gemini_results/compiled_results.json \
  --db-path disclosures.db \
  --all-confidences
```

## Next Steps

After running the workflow, consider:

1. Updating your API endpoints to use the new canonical entities
2. Adjusting your frontend to display both original and split entities
3. Running regular analysis on new data to identify new double disclosures 