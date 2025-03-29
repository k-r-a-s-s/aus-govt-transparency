# AI-Powered Political Disclosure Tracking System

This project automates the extraction, structuring, and analysis of parliamentary financial disclosures using Google Gemini 2.0 Flash AI.

## Motivation & Goal

Government financial disclosures, particularly registrable interests of MPs, are often published in PDF format, making them difficult to track, analyze, and compare over time. This project aims to automate the extraction, structuring, and analysis of these disclosures.

By doing so, we can:
- Monitor financial changes over time (e.g., assets appearing/disappearing)
- Detect patterns (e.g., MPs acquiring/selling stocks before policy changes)
- Expose relationships between MPs, companies, and gifts
- Enable citizen journalism by making structured data easily accessible

## Tech Stack

- **PDF Collection**: Python script to download PDFs from parliamentary websites
- **AI-Powered Data Structuring**: Google Gemini 2.0 Flash for direct PDF processing and data extraction
- **Database Storage**: SQLite for local storage and analysis
- **API Server**: Flask-based REST API for accessing the data
- **Frontend**: React-based web application for visualization and analysis

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- [Documentation Index](docs/index.md)
- [System Architecture](docs/architecture/overview.md)
- [Backend Documentation](docs/backend/database.md)
- [API Documentation](docs/api/endpoints.md)
- [Frontend Documentation](docs/frontend/components.md)
- [Setup Guide](docs/workflows/setup.md)
- [LLM Guidance](docs/backend/llm_guidance.md)

## Gemini API Usage

This project exclusively uses the Google Gemini 2.0 Flash model, which is available with a generous free tier:

- **Gemini 2.0 Flash**: 15 requests per minute (RPM), 1,000,000 tokens per minute (TPM), 1,500 requests per day (RPD)

The project includes robust rate limiting to ensure you stay within these free tier limits when processing large numbers of documents. You can adjust the rate limits using command line arguments:

```bash
# Process with more conservative rate limits
python process_parliament_disclosures.py --rpm 10 --rpd 1400
```

For processing all parliaments, we recommend using slightly conservative rate limits (10-12 RPM instead of 15) to provide a safety margin.

For detailed guidance on using Gemini 2.0 Flash effectively in this project, see the [LLM Guidance](docs/backend/llm_guidance.md) document.

## Quick Start

For detailed setup instructions, see the [Setup Guide](docs/workflows/setup.md).

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables in `.env.local`:
   ```
   GOOGLE_API_KEY=your_google_api_key
   ```
4. Run the API server:
   ```bash
   cd api
   python app.py
   ```
5. Run the frontend:
   ```bash
   cd aus-govt-transparency-viz/frontend
   npm install
   npm run dev
   ```

## Environment Variables and Security

This project uses environment variables to manage sensitive information like API keys. To protect your credentials:

1. **Never commit API keys or sensitive information to Git**
   - The project includes a comprehensive `.gitignore` file that prevents accidentally committing sensitive files
   - All files with patterns like `.env`, `.env.local`, `*.env` are ignored

2. **Use example environment files**
   - Copy the provided example files (`.env.example`, `api/.env.example`, etc.) to create your own configuration
   - Example: `cp .env.example .env.local` then edit with your actual credentials

## Key Features

- **PDF Scraping**: Automatically download PDFs from parliamentary websites
- **AI Extraction**: Use Google Gemini 2.0 to extract structured data from PDFs
- **Data Standardization**: Clean and standardize MP names, electorates, and categories
- **Entity Analysis**: Identify and track entities mentioned in disclosures
- **Visualizations**: Interactive visualizations of disclosure data
- **Search & Filter**: Search and filter disclosures by MP, category, entity, etc.
- **Entity Standardization**: Standardizes entity names for consistent analysis
- **Double Disclosure Processing**: Intelligently splits combined entity names (e.g., "Qantas and Virgin") into separate entities while preserving the original combined name
- **Data Quality Checks**: Validates data integrity and completeness
- **Statistical Analysis**: Generates insights and trends from the data

## Contributing

Contributions are welcome! Please see the [Development Workflow](docs/workflows/development.md) guide before contributing.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

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
- `scripts/apply_double_disclosure_entity_results.py`: Processes and splits combined entity names (e.g., "Qantas and Virgin") into separate entities while preserving the original combined name
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

### Database Schema for Entity Processing

The system uses the following columns for entity processing:

- `original_entity`: Contains the original entity name as extracted from documents
- `entity`: The current standardized entity name
- `split_entity`: Contains individual entities extracted from multi-entity strings (e.g., "Qantas" from "Qantas and Virgin")
- `regex_standardized`: Used during standardization processing
- `canonical_entity`: Used for the final standardized version

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
   - `scripts/apply_double_disclosure_entity_results.py`: Processes and splits combined entity names
   - `scripts/reset_original_entities.py`: Resets entity values for reprocessing

3. **Double Disclosure Processing**:
   - `scripts/double_disclosure_analysis.py`: Identifies potential double disclosures
   - `scripts/prepare_gemini_entity_analysis.py`: Prepares data for Gemini AI analysis
   - `scripts/analyze_double_disclosures_with_gemini.py`: Uses Gemini AI to analyze entities
   - `scripts/summarize_gemini_entity_analysis.py`: Generates analysis reports
   - `scripts/apply_double_disclosure_entity_results.py`: Applies split results to database

4. **Data Analysis**:
   - `scripts/analyze_disclosures.py`: Performs statistical analysis
   - `scripts/generate_reports.py`: Creates summary reports
   - `scripts/export_data.py`: Exports data in various formats

### Data Quality Checks