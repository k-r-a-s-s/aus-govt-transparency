# AI-Powered Political Disclosure Tracking System

This project automates the extraction, structuring, and analysis of parliamentary financial disclosures using Google Gemini 2.0 AI.

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
- **Query & Analysis**: Python scripts for data analysis and export

## Gemini API Usage

This project uses the Google Gemini API, which is available with a generous free tier:

- **Gemini 2.0 Flash**: 15 requests per minute (RPM), 1,000,000 tokens per minute (TPM), 1,500 requests per day (RPD)

The project includes robust rate limiting to ensure you stay within these free tier limits when processing large numbers of documents. You can adjust the rate limits using command line arguments:

```bash
# Process with more conservative rate limits
python process_parliament_disclosures.py --rpm 10 --rpd 1400
```

For processing all parliaments, we recommend using slightly conservative rate limits (10-12 RPM instead of 15) to provide a safety margin.

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

## Project Structure

- `scrape_parliament.py`: Script to download PDFs from parliamentary websites
- `parliament_urls.py`: Configuration file with URLs for different parliaments
- `gemini_pdf_processor.py`: Module for direct PDF processing with Google Gemini 2.0 API
- `db_handler.py`: Module for handling database operations
- `process_parliament_disclosures.py`: Main script that orchestrates the complete batch processing pipeline
- `test_gemini_pdf.py`: Script to test direct PDF processing with Gemini API
- `requirements.txt`: List of dependencies

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up environment variables in `.env.local`:
   ```
   GOOGLE_API_KEY=your_google_api_key
   ```

## Environment Variables and Security

This project uses environment variables to manage sensitive information like API keys. To protect your credentials:

1. **Never commit API keys or sensitive information to Git**
   - The project includes a comprehensive `.gitignore` file that prevents accidentally committing sensitive files
   - All files with patterns like `.env`, `.env.local`, `*.env` are ignored

2. **Use example environment files**
   - Copy the provided example files (`.env.example`, `api/.env.example`, etc.) to create your own configuration
   - Example: `cp .env.example .env.local` then edit with your actual credentials

3. **Available environment files**
   - Root directory: `.env.local` for main project configuration (Google API keys)
   - API directory: `api/.env` for Flask API configuration
   - Frontend directory: `aus-govt-transparency-viz/frontend/.env` for frontend configuration
   - Backend directory: `aus-govt-transparency-viz/backend/.env` for backend configuration

4. **Environment variables reference**
   - `GOOGLE_API_KEY`: Your Google Gemini API key (required for PDF processing)
   - `DB_PATH`: Path to SQLite database (used by API)
   - `PORT`: Port for running the API server
   - `DEBUG`: Enable debug mode for Flask API
   - `VITE_API_URL`: API URL for frontend requests

Always inspect your Git commits with `git diff --staged` before committing to ensure no sensitive information is included.

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

```