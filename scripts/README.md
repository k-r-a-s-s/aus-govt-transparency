# Scripts

This directory contains scripts for data processing, analysis, and database management for the Australian Government Transparency Project.

## Entity Deduplication

- **entity_dedupe_analysis.py**: Analyzes the database to identify potential duplicate entities using fuzzy matching.
- **entity_dedupe_review.py**: Helps review proposed entity mappings and merge reviewed subsets back into the full mapping.
- **entity_dedupe_implementation.py**: Applies the reviewed entity mappings to the database, updating entity names to their canonical forms.

## Double Disclosure Detection with Gemini

The following scripts implement a workflow for identifying and processing "double disclosures" (records where a single entity field contains multiple entities) using Google's Gemini AI:

- **double_disclosure_analysis.py**: Analyzes the database to identify potential double disclosures based on separator patterns.
- **prepare_gemini_entity_analysis.py**: Prepares data for Gemini analysis by creating batches of entities.
- **gemini_entity_analyzer.py**: Uses the Gemini API to analyze and classify entities, determining which ones should be split.
- **summarize_gemini_results.py**: Creates a CSV summary of Gemini analysis results for easier review.
- **apply_gemini_entity_results.py**: Applies the Gemini analysis results to the database, splitting entities identified as containing multiple entities.

## Entity Normalization

- **standardize_entities.py**: Reads the `split_entity` column, expands known abbreviations using a provided JSON mapping file (`--mapping`), applies basic normalization (lowercase, removes special characters except '&', collapses whitespace), and writes the result to the `normalized_entity` column. This prepares names for further processing like deduplication.
  ```bash
  python standardize_entities.py --db <database_path> --mapping <path_to_expanded_entities.json>
  ```

## Database Management

- **init_db.py**: Initializes the database schema and indexes.
- **import_data.py**: Imports data from CSV files into the database.
- **update_data.py**: Updates existing data in the database.

## Usage

For detailed usage instructions, please refer to the documentation in the `docs/` directory:

- Basic usage: `docs/guides/basic_usage.md`
- Entity deduplication: `docs/backend/entity_deduplication.md`
- Double disclosure detection: `docs/backend/double_disclosure_detection.md`
- Running the double disclosure workflow: `docs/guides/running_double_disclosure_detection.md` 