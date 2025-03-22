# Backend Architecture

The backend system is responsible for scraping, processing, and storing parliamentary disclosure data. It's composed of several Python modules that handle different aspects of the data pipeline.

## Core Components

### PDF Collection

The PDF collection component is responsible for downloading disclosure PDFs from parliamentary websites.

**Key Files:**
- `scrape_parliament.py`: Main scraping script
- `parliament_urls.py`: Configuration file with URLs for different parliaments

**Key Functions:**
- `scrape_parliament.py::scrape_parliament()`: Downloads PDFs for a specific parliament
- `scrape_parliament.py::scrape_all_parliaments()`: Downloads PDFs for all configured parliaments

### PDF Processing

The PDF processing component uses Google's Gemini 2.0 AI to extract structured data from disclosure PDFs.

**Key Files:**
- `gemini_pdf_processor.py`: Module for direct PDF processing with Google Gemini 2.0 API
- `test_gemini_pdf.py`: Script to test direct PDF processing with Gemini API
- `process_parliament_disclosures.py`: Main orchestration script

**Key Classes:**
- `GeminiPDFProcessor`: Handles interaction with the Gemini API for PDF processing
- `RateLimiter`: Ensures API rate limits are respected

**Key Functions:**
- `GeminiPDFProcessor::process_pdf()`: Processes a single PDF file
- `GeminiPDFProcessor::process_directory()`: Processes all PDFs in a directory
- `GeminiPDFProcessor::post_process_data()`: Cleans and standardizes extracted data

### Database Management

The database management component handles the storage and retrieval of structured disclosure data.

**Key Files:**
- `db_handler.py`: Main database handling module
- `reset_db.py`: Script for resetting the database to a clean state

**Key Classes:**
- `Categories`: Defines standard categories for disclosures
- `Subcategories`: Defines subcategories for each main category
- `TemporalTypes`: Defines temporal types for disclosures (one-time, recurring, ongoing)
- `DatabaseHandler`: Main class for database operations

**Key Functions:**
- `DatabaseHandler::create_tables()`: Creates the database schema
- `DatabaseHandler::insert_disclosure()`: Inserts a disclosure into the database
- `DatabaseHandler::update_disclosure()`: Updates an existing disclosure
- `DatabaseHandler::get_disclosures()`: Retrieves disclosures with filtering options
- `DatabaseHandler::filter_nil_entries()`: Filters out "nil" or "n/a" entries

### Data Standardization

The data standardization component ensures consistency in MP names, electorates, and categories.

**Key Files:**
- `standardize_data.py`: Main script for the complete standardization pipeline
- `standardize_mp_names.py`: Script for standardizing MP names
- `standardize_electorates.py`: Script for standardizing electorate names
- `recategorize_unknowns.py`: Script for recategorizing entries with regex patterns
- `recategorize_unknowns_llm.py`: Script for recategorizing entries using LLM

**Key Functions:**
- `standardize_mp_names.py::standardize_mp_names()`: Standardizes MP names in the database
- `standardize_electorates.py::standardize_electorates()`: Standardizes electorate names
- `recategorize_unknowns.py::recategorize()`: Uses regex patterns to recategorize unknown entries

## Data Flow

1. **PDF Collection**:
   ```
   scrape_parliament.py --parliament 47th
   ```
   Downloads PDFs from the 47th parliament website to the `pdfs/47th/` directory.

2. **PDF Processing**:
   ```
   process_parliament_disclosures.py --parliament 47th --store-in-db
   ```
   Processes all PDFs in the `pdfs/47th/` directory, extracting structured data and storing it in the database.

3. **Data Standardization**:
   ```
   standardize_data.py
   ```
   Standardizes MP names, electorates, and categories in the database.

4. **Recategorization**:
   ```
   recategorize_all.py
   ```
   Recategorizes unknown entries in the database using pattern matching and LLM.

## Database Schema

The main database (`disclosures.db`) contains the following tables:

### Disclosures Table

Stores individual disclosure entries extracted from PDFs.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key (UUID) |
| mp_name | TEXT | MP's name |
| party | TEXT | Political party |
| electorate | TEXT | Electoral district |
| category | TEXT | Disclosure category (Asset, Liability, etc.) |
| sub_category | TEXT | Subcategory (Real Estate, Shares, etc.) |
| item | TEXT | Disclosed item |
| entity | TEXT | Associated entity |
| entity_id | TEXT | Reference to entities table |
| declaration_date | TEXT | Date of declaration |
| details | TEXT | Additional details |
| temporal_type | TEXT | one-time, recurring, or ongoing |
| start_date | TEXT | Start date for recurring/ongoing items |
| end_date | TEXT | End date for recurring/ongoing items |
| pdf_url | TEXT | URL to the source PDF |
| pdf_page | INTEGER | Page number in the PDF |
| confidence | REAL | AI confidence score (0-1) |
| last_updated | TEXT | Timestamp of last update |

### Entities Table

Stores unique entities mentioned in disclosures.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key (UUID) |
| name | TEXT | Entity name |
| entity_type | TEXT | Type of entity (Company, Organization, etc.) |
| category | TEXT | Primary category of interest |
| abn | TEXT | Australian Business Number |
| description | TEXT | Entity description |
| first_appearance | TEXT | Date of first appearance |
| last_appearance | TEXT | Date of last appearance |
| appearances_count | INTEGER | Number of times entity appears |

## Configuration

The backend system is configured through environment variables:

- `GOOGLE_API_KEY`: Google Gemini API key for PDF processing
- `DB_PATH`: Path to SQLite database file

These can be set in a `.env.local` file in the project root directory.

## Next Steps

- [Database Schema and Operations](../backend/database.md)
- [PDF Processing Pipeline](../backend/pdf_processing.md)
- [Data Standardization](../backend/data_standardization.md) 