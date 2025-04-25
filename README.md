# Australian Government Transparency Project - Disclosure Data Pipeline

This repository contains a modular, maintainable pipeline for processing, standardizing, and analyzing Australian parliamentary financial disclosure data. The project is focused on extracting structured data from PDFs, cleaning and standardizing it, and enabling robust analysis of MPs' financial interests.

## Key Features
- **End-to-end pipeline** for PDF scraping, parsing, cleaning, and output
- **Strongly-typed, functional Python code** (see `/src`)
- **Canonical database schema** for disclosures, MPs, and entities
- **Modular structure** for easy extension and testing
- **LLM (Gemini) integration** for entity extraction and validation

## What's in this Repo
- `/src/preparation`: Data preparation, schema generation, and scraping helpers
- `/src/parsing`: PDF parsing and entity extraction (Gemini, OCR, etc.)
- `/src/cleaning`: Data cleaning, standardization, recategorization, and deduplication
- `/src/output`: Output/export logic (to be expanded)
- `/src/common`: Shared utilities (rate limiter, helpers)
- `disclosures.db`: Main SQLite database (see schema below)
- `docs/`: Project documentation (pipeline, schema, workflows)
- `outputs/`, `pdfs/`: Data and results (not tracked in version control)

## What's Not (anymore)
- No backend API or frontend code (moved to a separate repository)
- No legacy scripts or monolithic processing logic
- No direct API endpoints or web server in this repo

## Pipeline Workflow

1. **Preparation** (`/src/preparation`)
    - Generate canonical database schema (`generate_schema.py`)
    - Scrape PDFs from parliament websites (`scrape_parliament.py`)
    - Get MP party affiliations (`get_mp_party_affiliations.py`)
2. **Parsing** (`/src/parsing`)
    - Extract text and entities from PDFs using Gemini or OCR
    - Parse and structure disclosure data
3. **Cleaning** (`/src/cleaning`)
    - Standardize MP names, electorates, and categories, link across tables
    - **MP Party & Canonicalization:**
        - Update and patch MP party affiliations using `python src/cleaning/get_mp_party_affiliations.py --db-path disclosures.db` (includes robust scraping, fuzzy matching, and manual party fixes for stubborn or missing cases).
        - Canonicalize and merge duplicate MPs using `python src/cleaning/merge_duplicate_mps.py --db-path disclosures.db` (handles normalization, case/whitespace, and explicit manual merge overrides for edge cases).
        - Result: The `mps` table is now deduplicated, all MPs have correct party affiliations, and all disclosures point to the canonical `mp_id`.
    - **Entities:**
        1. Link entities across the tables (ensure each disclosure's `raw_entity` is linked to a canonical entity in the `entities` table via `entity_id`).
        2. Run vector-based entity matching (`vector_match.py`) with LLM supervision to merge similar entities to canonical names.
        3. Update and merge entity IDs to ensure consistency for database queries and analysis.
    - **Disclosures:**
        1. Perform a final check for duplicate disclosures (e.g., same MP, date, entity, and description).
        2. Run final quality checks to ensure data integrity and completeness.

4. **Output** (`/src/output`)
    - Export cleaned data for analysis or external use (to be expanded)

## Iterative LLM-Supervised Entity Grouping and Canonicalization

The pipeline includes an iterative, LLM-supervised process for grouping, merging, and canonicalizing entities:
- After initial entity extraction, entities are grouped using vector embeddings and community detection.
- For each group of similar entities (community):
    - If the group has more than one member, the list is sent to Gemini LLM for supervision.
    - The LLM selects a single canonical entity name, identifies which entities should be merged, and which should be rejected.
- Rejected entities are returned to the pool for future iterations, allowing them to be grouped with other entities in subsequent passes.
- Canonical entities (already merged groups) can also be returned to the pool if new merges are possible, supporting dynamic, evidence-driven grouping.
- If a canonical entity is merged again and the LLM selects a new canonical name for the expanded group, a warning is logged, but the merge and name change are allowed to proceed.
- The process is repeated for a fixed number of iterations (e.g., 4). Singletons are finalized after 4 iterations.
- After all iterations, a mapping of `{old_entity_id, new_entity_id, canonical_name, status}` is exported for migration to the main database.

This approach allows for robust, evidence-driven merging of entities, supports correction of earlier grouping errors, and provides a clear audit trail for all canonicalization decisions. See `refactor_plan.rmd` and `development_diary.rmd` for implementation details and user instructions.

## Setup

1. **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```
2. **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4. **Set up environment variables:**
    - Copy `.env.example` to `.env.local` and fill in required values (e.g., `GOOGLE_API_KEY` for Gemini)
5. **Prepare the database:**
    - Run the schema generator:
    ```bash
    python src/preparation/generate_schema.py
    ```

## Running the Pipeline

- **Orchestrate the full pipeline:**
    ```bash
    python src/main.py --parliament 47th --store-in-db --standardize
    ```
    - See `python src/main.py --help` for all options (batch processing, skipping steps, etc.)

- **Run individual steps:**
    - Scrape PDFs: `python src/preparation/scrape_parliament.py`
    - Parse PDFs: `python src/parsing/parse_disclosures.py --pdf-dir pdfs/47th --db-path disclosures.db`
    - Clean/standardize: `python src/cleaning/standardize_mp_names.py --db-path disclosures.db`
    - Recategorize: `python src/cleaning/recategorize_all.py --db-path disclosures.db`
    - Merge entities: `python src/cleaning/merge_entities.py --db-path disclosures.db`

## Database Schema (Canonical)

See `refactor_plan.rmd` and `/docs/backend/database.md` for full details. Key tables:

```sql
CREATE TABLE mps (
    mp_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    electorate TEXT,
    party TEXT,
    wikidata_id TEXT
);

CREATE TABLE disclosures (
    disclosure_id TEXT PRIMARY KEY,
    mp_id TEXT NOT NULL,
    pdf_filename TEXT NOT NULL,
    date TEXT NOT NULL,
    raw_description TEXT NOT NULL,
    raw_entity TEXT,
    category TEXT,
    interest_type TEXT,
    entity_id TEXT,
    FOREIGN KEY (mp_id) REFERENCES mps(mp_id),
    FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
);

CREATE TABLE entities (
    entity_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    iteration INTEGER,
    status TEXT,
    notes TEXT
);
```

## Contributing
- Please see `development_diary.rmd` for workflow and change tracking
- All code should be modular, strongly typed, and functional
- Document all changes and update docs as you go

## License
(Add license information if applicable)

## System Workflow

The system workflow is straightforward:

### Direct PDF Processing Workflow
1. **PDF Collection**: PDFs are downloaded from parliamentary websites using the `scrape_parliament.py` script.
2. **Direct PDF Processing**: Google Gemini 2.0 Flash directly processes PDFs and extracts structured data.
3. **Database Storage**: AI-generated JSON is inserted into SQLite database.
4. **Query & Analysis**: Structured data enables trend detection and analysis.

### Complete Batch Processing Pipeline
1. **PDF Collection**: PDFs from multiple parliaments are downloaded and organized by parliament.
2. **Direct PDF Processing**: All PDFs are processed with Gemini 2.0 Flash with post-processing for enhanced data quality.
3. **Database Storage**: Structured data is stored in SQLite database.
4. **Output Organization**: JSON outputs are organized by parliament for easy access.

### 3. Entity Processing
- `scripts/process_entities.py`: Processes and standardizes entity names
- `scripts/apply_entity_results.py`: Applies entity standardization results to the database
- `scripts/apply_double_disclosure_entity_results.py`: Processes and splits combined entity names (e.g., "Qantas and Virgin") identified by prior analysis (like `analyze_double_disclosures_with_gemini.py`). It updates the original row for the first split entity and creates *new* rows for subsequent splits. **Crucially, when creating new rows, it copies all data from the original row, preserving fields (including NULLs) and only changing the `id`, `entity`, `original_entity`, and `split_entity` columns.** This ensures data integrity across the split entries.
- `scripts/reset_original_entities.py`: Resets entity values to match original_entity values, useful for reprocessing double disclosures
- `scripts/standardize_entities.py`: Standardizes entity names using a multi-stage process:
  1. Checks for populated `split_entity` column (requires running `apply_double_disclosure_entity_results.py` first)
  2. Applies acronym standardization
  3. Applies regex-based standardization
  4. Applies fuzzy matching for similar entities
  5. Applies case standardization

### 4. Data Analysis
- `scripts/double_disclosure_analysis.py`: Analyzes potential double disclosures in the database
- `scripts/prepare_gemini_entity_analysis.py`: Prepares data for Gemini analysis
- `scripts/analyze_double_disclosures_with_gemini.py`: Analyzes entities with Gemini AI to distinguish between true multiple entities and single entities with compound names
- `scripts/summarize_gemini_entity_analysis.py`: Summarizes and generates reports from Gemini analysis results

### 5. Iterative Entity Grouping and LLM Validation
- `scripts/vector_entity_grouping.py`: This is the core script for identifying and validating groups of similar entity names.
    - **Purpose:** To iteratively cluster normalized entity names based on semantic similarity (vector embeddings) and then use an LLM (Gemini) to perform granular validation of the members within each proposed cluster.
    - **Workflow:**
        1.  Calculates sentence embeddings for entities not yet confirmed.
        2.  Builds a graph based on cosine similarity above a threshold.
        3.  Detects communities using the Louvain algorithm.
        4.  Sends multi-member communities to Gemini for member-by-member confirmation/rejection (unless `--no-llm-review` is used).
        5.  Treats single-member communities (isolated entities) as confirmed.
        6.  Saves all processed groups and member statuses (`confirmed`, `rejected`, `pending_review`) to a dedicated `entity_grouping.db` SQLite database, using a unique `community_ID` (e.g., "iteration-group_index").
        7.  Outputs an intermediate JSON file (`iteration_<N>_reviewed_communities.json`) for debugging each iteration.
    - **Iteration:** Designed to be run multiple times with increasing `--iteration` numbers. Each run excludes previously confirmed entities, allowing focus on the remaining ungrouped/rejected ones.
    - **Setup & Usage:** See the detailed docstring within the script itself for environment setup (requires specific libraries like `python-louvain`, `google-generativeai`), API key configuration (`.env.local`), and command-line arguments (`--iteration`, `--threshold`, `--limit`, `--no-llm-review`).

### Entity Processing Workflow

1. **Double Disclosure Processing**:
   ```bash
   # First, analyze and split combined entity names
   python scripts/apply_double_disclosure_entity_results.py --db disclosures.db --input-file scripts/gemini_results/compiled_results.json
   ```

2. **Entity Standardization**:
   ```bash
   # Then standardize the split entities
   python scripts/standardize_entities.py --db disclosures.db
   
   # Optional flags:
   --no-fuzzy           # Skip fuzzy matching
   --skip-regex         # Skip regex standardization
   --skip-acronyms      # Skip acronym standardization
   --auto              # Run without confirmation prompts
   ```

3. **Verification and Reset**:
   ```bash
   # If needed, reset entities to original values
   python scripts/reset_original_entities.py
   ```

This workflow ensures that:
1. Multi-entity strings are properly split before standardization
2. The relationship between original and split entities is preserved
3. Standardization is applied to individual entities rather than combined strings
4. The process is clear and enforced through checks

## Project Structure

- `scrape_parliament.py`: Script to download PDFs from parliamentary websites
- `parliament_urls.py`: Configuration file with URLs for different parliaments
- `gemini_pdf_processor.py`: Module for direct PDF processing with Google Gemini 2.0 API
- `db_handler.py`: Module for handling database operations
- `process_parliament_disclosures.py`: Main script that orchestrates the complete batch processing pipeline
- `test_gemini_pdf.py`: Script to test direct PDF processing with Gemini API
- `requirements.txt`: List of dependencies

## Usage

### Downloading PDFs

```bash
# Download PDFs from the latest parliament (47th)
python scrape_parliament.py

# Download PDFs from a specific parliament
python scrape_parliament.py --parliament 46th

# Download PDFs from all parliaments
python scrape_parliament.py --all
```

### Testing Direct PDF Processing with Gemini

```bash
python test_gemini_pdf.py --pdf path/to/pdf
```

### Processing a Single PDF (Direct PDF Processing)

```bash
python test_gemini_pdf.py --pdf path/to/pdf --output-dir gemini_output
```

### Processing Multiple PDFs (Direct PDF Processing)

```bash
python test_gemini_pdf.py --pdf-dir pdfs --output-dir gemini_output --limit 5
```

### Complete Batch Processing Pipeline

```bash
# Process the latest parliament (47th)
python process_parliament_disclosures.py

# Process a specific parliament
python process_parliament_disclosures.py --parliament 46th

# Process all parliaments
python process_parliament_disclosures.py --all

# Skip the scraping step (if PDFs are already downloaded)
python process_parliament_disclosures.py --skip-scraping

# Store results in database
python process_parliament_disclosures.py --store-in-db

# Skip post-processing
python process_parliament_disclosures.py --skip-post-processing

# Limit the number of PDFs processed per parliament
python process_parliament_disclosures.py --limit 10

# Process all parliaments with rate limiting and store in database
python process_parliament_disclosures.py --all --store-in-db --rpm 10 --continue-on-error
```

### Complete Batch Processing Pipeline with Data Standardization

```bash
# Process all parliaments with standardization (ensures consistent MP names and electorates)
python process_parliament_disclosures.py --all --store-in-db --rpm 10 --continue-on-error --standardize

# Skip scraping if PDFs are already downloaded
python process_parliament_disclosures.py --all --store-in-db --skip-scraping --rpm 10 --continue-on-error --standardize
```

The `--standardize` flag ensures:
1. MP names are standardized (removing middle names and handling inconsistencies)
2. Electorate names are standardized (fixing case issues and updating renamed electorates)
3. Category validation and statistics are generated

This ensures data consistency and improves analysis quality by correctly tracking MPs across parliaments, even when their names appear with different formats.

### Running Standardization Separately

If you need to run standardization separately after processing:

```bash
# Run the complete standardization pipeline
python standardize_data.py

# Run just MP name standardization
python standardize_mp_names.py

# Run just electorate standardization
python standardize_electorates.py
```

### Processing Large PDFs (>20MB)

For large PDFs, the system automatically uses the Gemini File API:

```bash
python test_gemini_pdf.py --pdf path/to/large.pdf
```

Or force using the File API even for small PDFs:

```bash
python test_gemini_pdf.py --pdf path/to/pdf --use-file-api
```

### Exporting Database to JSON

```bash
python process_disclosures.py --export-json export.json
```

### Running Recategorization

The system includes a comprehensive recategorization pipeline to improve entry categorization:

```bash
# Regular regex-based recategorization (fastest, no external API calls)
python recategorize_unknowns.py --db-path=disclosures.db

# LLM-based recategorization for remaining unknowns
# Requires Google API key set as GOOGLE_API_KEY environment variable
python recategorize_unknowns_llm.py --db-path=disclosures.db --max-entries=100

# Run the complete pipeline
python recategorize_all.py --db-path=disclosures.db
```

## Rate Limiting and Error Handling

The system includes sophisticated rate limiting to ensure you don't exceed Gemini API limits:

- **Adaptive Waiting**: Automatically waits when approaching rate limits
- **Retry Logic**: Implements exponential backoff for rate limit errors
- **Progress Tracking**: Shows real-time statistics on successful/failed/rate-limited requests
- **Resumable Processing**: Can continue from where it left off if interrupted

When processing all parliaments, use the `--continue-on-error` flag to ensure processing continues even if individual PDFs fail:

```bash
python process_parliament_disclosures.py --all --store-in-db --rpm 10 --continue-on-error
```

## Data Structure

The AI extracts structured data from PDFs into the following JSON format:

## Entity Deduplication and Double Disclosure Detection

The system includes specialized tools for identifying and handling "double disclosure" scenarios where a single disclosure entry contains multiple entities that should be treated separately:

### Double Disclosure Detection Workflow

```bash
# Step 1: Analyze potential double disclosures in the database
python scripts/double_disclosure_analysis.py

# Step 2: Prepare data for Gemini analysis
python scripts/prepare_gemini_entity_analysis.py

# Step 3: Analyze entities with Gemini AI to distinguish between true multiple entities and single entities with compound names
python scripts/analyze_double_disclosures_with_gemini.py --api-key-file .gemini_api_key

# Step 4: Summarize and generate reports from Gemini analysis results
python scripts/summarize_gemini_entity_analysis.py --input-file scripts/gemini_results/compiled_results.json --output-dir scripts/gemini_summary

# Step 5: Apply high-confidence results to update the database (dry run)
python scripts/apply_double_disclosure_entity_results.py --db disclosures.db --input-file scripts/gemini_results/compiled_results.json

# Step 6: Apply changes to the database (after reviewing dry run)
python scripts/apply_double_disclosure_entity_results.py --db disclosures.db --input-file scripts/gemini_results/compiled_results.json --no-dry-run
```

### Double Disclosure Documentation

For a comprehensive understanding of the double disclosure detection workflow, see:

- [Double Disclosure Analysis Guide](docs/workflows/double_disclosure_detection.md)
- [Gemini API Setup](docs/guides/gemini_api_setup.md)

This feature significantly improves data accuracy by properly handling cases where multiple entities are incorrectly grouped together in a single disclosure entry.

### Data Processing Pipeline

1. **PDF Processing**:
   - `scripts/process_pdfs.py`: Extracts text from PDFs
   - `scripts/parse_disclosures.py`: Parses disclosure text into structured data
   - `scripts/apply_parsing_results.py`: Applies parsing results to database

2. **Entity Processing**:
   - `scripts/process_entities.py`: Processes and standardizes entity names
   - `scripts/apply_entity_results.py`: Applies entity standardization results to database
   - `scripts/apply_double_disclosure_entity_results.py`: Processes and splits combined entity names (copies all original data for new rows).
   - `scripts/reset_original_entities.py`: Resets entity values for reprocessing

3. **Double Disclosure Processing**:
   - `scripts/double_disclosure_analysis.py`: Identifies potential double disclosures
   - `scripts/prepare_gemini_entity_analysis.py`: Prepares data for Gemini AI analysis
   - `scripts/analyze_double_disclosures_with_gemini.py`: Uses Gemini AI to analyze entities
   - `scripts/summarize_gemini_entity_analysis.py`: Generates analysis reports
   - `scripts/apply_double_disclosure_entity_results.py`: Applies split results to database by updating the first split entity row and creating new rows (copying original data) for subsequent splits.

4. **Data Analysis**:
   - `scripts/analyze_disclosures.py`: Performs statistical analysis
   - `scripts/generate_reports.py`: Creates summary reports
   - `scripts/export_data.py`: Exports data in various formats

### Data Quality Checks