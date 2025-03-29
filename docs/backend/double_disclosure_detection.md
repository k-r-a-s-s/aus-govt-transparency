# Double Disclosure Detection with Gemini

This document outlines the process of using Google's Gemini AI model to identify and process "double disclosures" in the Australian Government Transparency database - cases where a single entity record actually contains multiple distinct entities.

## Overview

Some disclosure records contain multiple entities listed together (e.g. "Westpac and ANZ", "BHP/Rio Tinto", "Shell & Optus"). The double disclosure detection system uses Gemini Flash 2.0, a large language model, to analyze these potential multiple entities and determine which ones should be split into separate records with high confidence.

## Workflow

The double disclosure detection workflow consists of four main steps:

1. **Data Preparation**: Extracting and organizing potential double disclosures
2. **AI Analysis**: Using Gemini to classify entities and propose splits
3. **Result Processing**: Filtering and preparing the results for application
4. **Database Update**: Applying high-confidence splits to the database

## Components

### 1. Data Preparation Script (`prepare_gemini_entity_analysis.py`)

This script prepares data for Gemini analysis by:

- Loading potential double disclosures from CSV
- Grouping entities by separator type (`and`, `&`, `,`, `/`, `+`)
- Creating batches for efficient analysis
- Generating prompt templates with Australian context and examples

```python
# Example usage
python scripts/prepare_gemini_entity_analysis.py \
  --input-file scripts/double_disclosure_results/potential_double_disclosures.csv \
  --output-dir scripts/gemini_batches \
  --batch-size 50
```

### 2. Gemini Analysis Script (`gemini_entity_analyzer.py`)

This script processes batches of entities using the Gemini API:

- Formats prompts for each batch with Australian-specific context
- Calls Gemini Flash 2.0 API with structured prompts
- Extracts and validates results from AI responses
- Compiles results into a structured format

```python
# Example usage
python scripts/gemini_entity_analyzer.py \
  --input-dir scripts/gemini_batches \
  --output-dir scripts/gemini_results \
  --api-key YOUR_API_KEY \
  --model gemini-1.5-flash-latest
```

### 3. Result Application Script (`apply_gemini_entity_results.py`)

This script applies the Gemini analysis results to the database:

- Loads and filters results based on confidence level
- Updates the database schema if needed
- Processes high-confidence entity splits
- Generates detailed reports of applied changes

```python
# Example usage for a dry run
python scripts/apply_gemini_entity_results.py \
  --input-file scripts/gemini_results/compiled_results.json \
  --db-path disclosures.db \
  --dry-run

# Example usage for actual application
python scripts/apply_gemini_entity_results.py \
  --input-file scripts/gemini_results/compiled_results.json \
  --db-path disclosures.db \
  --confidence HIGH
```

## Data Model Changes

The script adds an `original_entity` column to the `disclosures` table to preserve the original entity name before splitting. This allows for:

- Traceability back to original data
- Ability to revert changes if needed
- Documentation of which records were created from splits

## Algorithm Details

### Entity Classification

Gemini classifies each entity into one of two categories:

- **SINGLE**: The entity represents a single organization or individual
- **MULTIPLE**: The entity represents multiple distinct organizations or individuals

### Confidence Levels

For each classification, Gemini assigns a confidence level:

- **HIGH**: Very confident in the classification and proposed split
- **MEDIUM**: Moderately confident
- **LOW**: Low confidence, human review recommended

### Entity Splitting

For entities classified as MULTIPLE, Gemini proposes a list of split entities. The script only applies HIGH confidence splits by default to minimize errors.

## Australian Context

The system incorporates Australian-specific knowledge:

- Understanding of Australian business naming conventions
- Recognition of common Australian organizational structures
- Awareness of Australian government entities and departments
- Knowledge of Australian banking and financial institutions

## Results and Statistics

After running the full workflow:

- Approximately X% of potential double disclosures were classified with HIGH confidence
- Y new disclosure records were created from splits
- Z% of all disclosures in the database were affected

## Future Improvements

- Integration with manual review workflow
- Feedback loop to improve Gemini prompt engineering
- Regular batch processing of new disclosures
- Advanced visualization of split entities in the frontend 