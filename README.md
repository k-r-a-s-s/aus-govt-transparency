# AI-Powered Political Disclosure Tracking System

This project automates the extraction, structuring, and analysis of parliamentary financial disclosures using Google Cloud Vision OCR and Google Gemini 2.0 AI.

## Motivation & Goal

Government financial disclosures, particularly registrable interests of MPs, are often published in PDF format, making them difficult to track, analyze, and compare over time. This project aims to automate the extraction, structuring, and analysis of these disclosures.

By doing so, we can:
- Monitor financial changes over time (e.g., assets appearing/disappearing)
- Detect patterns (e.g., MPs acquiring/selling stocks before policy changes)
- Expose relationships between MPs, companies, and gifts
- Enable citizen journalism by making structured data easily accessible

## Tech Stack

- **PDF Collection**: Python script to download PDFs from parliamentary websites
- **OCR Processing**: Google Cloud Vision API for text extraction
- **AI-Powered Data Structuring**: Google Gemini 2.0 Flash for structuring extracted text
- **Database Storage**: SQLite for local storage and analysis
- **Query & Analysis**: Python scripts for data analysis and export

## System Workflow

The system supports two processing workflows:

### Traditional OCR-based Workflow
1. **PDF Collection**: PDFs are downloaded from parliamentary websites using the `scrape_parliament.py` script.
2. **OCR Processing**: Google Cloud Vision API extracts text from PDFs.
3. **AI-Powered Data Structuring**: Google Gemini 2.0 Flash categorizes text into structured JSON.
4. **Database Storage**: AI-generated JSON is inserted into SQLite database.
5. **Query & Analysis**: Structured data enables trend detection and analysis.

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
- `ocr_processor.py`: Module for handling PDF processing with Google Cloud Vision OCR
- `gemini_processor.py`: Module for interacting with Google Gemini 2.0 API (OCR-based workflow)
- `gemini_pdf_processor.py`: Module for direct PDF processing with Google Gemini 2.0 API
- `db_handler.py`: Module for handling database operations
- `process_disclosures.py`: Script that orchestrates the OCR-based workflow
- `process_parliament_disclosures.py`: Main script that orchestrates the complete batch processing pipeline
- `test_gemini.py`: Simple script to test the Gemini API with OCR text
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
4. Set up Google Cloud credentials (for Vision API):
   ```
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
   ```

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

### Testing Gemini API with OCR Text

```bash
python test_gemini.py
```

### Testing with a specific PDF (OCR-based)

```bash
python test_gemini.py --pdf path/to/pdf
```

### Testing Direct PDF Processing with Gemini

```bash
python test_gemini_pdf.py --pdf path/to/pdf
```

### Processing a Single PDF (OCR-based)

```bash
python process_disclosures.py --pdf path/to/pdf --output-dir structured_data
```

### Processing a Single PDF (Direct PDF Processing)

```bash
python test_gemini_pdf.py --pdf path/to/pdf --output-dir gemini_output
```

### Processing Multiple PDFs (OCR-based)

```bash
python process_disclosures.py --pdf-dir pdfs --output-dir structured_data --limit 5
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

## Data Structure

The AI extracts structured data from PDFs into the following JSON format:

```json
{
  "mp_name": "Mark Dreyfus",
  "party": "Labor",
  "electorate": "Isaacs",
  "disclosures": [
    {
      "declaration_date": "2010-07-19",
      "category": "Asset",
      "sub_category": "Shares",
      "item": "BHP Billiton Ltd",
      "temporal_type": "ongoing",
      "start_date": "2010-07-19",
      "end_date": "",
      "details": "Additional details about this declaration"
    },
    {
      "declaration_date": "2010-07-19",
      "category": "Asset",
      "sub_category": "Real Estate",
      "item": "Residential property in Melbourne, VIC",
      "temporal_type": "ongoing",
      "start_date": "2010-07-19",
      "end_date": "",
      "details": "Investment property"
    },
    {
      "declaration_date": "2010-10-02",
      "category": "Gift",
      "sub_category": "Entertainment",
      "item": "Two tickets to AFL Grand Final",
      "temporal_type": "one-time",
      "start_date": "2010-10-02",
      "end_date": "2010-10-02",
      "details": "Received from Monash Foundation, valued at approx. $400"
    }
  ],
  "relationships": [
    {
      "entity": "BHP Billiton Ltd",
      "relationship_type": "Owns Shares",
      "value": "Undisclosed",
      "date_logged": "2010-07-19"
    },
    {
      "entity": "Monash Foundation",
      "relationship_type": "Received Gift",
      "value": "Approx. $400",
      "date_logged": "2010-10-02"
    }
  ]
}
```

## Post-Processing Features

The system includes post-processing capabilities to enhance the quality of extracted data:

1. **Share Splitting**: Automatically splits grouped share entries into individual entries
   - Before: `"entity": "BHP, QAN, ANZ, Dutton Holdings (QLD) Pty Ltd"`
   - After: Four separate entries for BHP, QAN, ANZ, and Dutton Holdings

2. **Gift Sub-Categorization**: Adds sub-categories to gift entries
   - Sports Tickets: Tickets to sporting events
   - Alcohol: Wine, spirits, etc.
   - Food: Hampers, meals, etc.
   - Clothing: Apparel items
   - Electronics: Devices, gadgets
   - Travel: Flights, accommodation, lounge access
   - Books/Media: Publications, media
   - Decorative: Artwork, ornaments
   - Office Items: Stationery, business items

## Database Schema

The database schema consists of the following tables:

### Disclosures Table

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Unique ID (UUID) |
| mp_name | TEXT | MP's full name |
| party | TEXT | Political party |
| electorate | TEXT | MP's electorate/state |
| declaration_date | TEXT | When the declaration was made |
| category | TEXT | Asset, Liability, Income, Membership, Gift, Travel |
| sub_category | TEXT | More specific classification (e.g., Shares, Real Estate) |
| item | TEXT | What's being disclosed |
| temporal_type | TEXT | one-time, recurring, ongoing |
| start_date | TEXT | When the item began (for ongoing items) |
| end_date | TEXT | When the item ended (if applicable) |
| details | TEXT | Additional details about the declaration |
| pdf_url | TEXT | Link to source document |
| entity_id | TEXT | Reference to the related entity |
| entity | TEXT | Company or organization linked to the declaration |

### Entities Table

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Unique ID (UUID) |
| entity_type | TEXT | Type of entity (company, organization, etc.) |
| canonical_name | TEXT | Normalized name for the entity |
| first_appearance_date | TEXT | Date first mentioned in disclosures |
| last_appearance_date | TEXT | Date last mentioned in disclosures |
| is_active | BOOLEAN | Whether the entity is still active |
| confidence_score | FLOAT | Confidence in entity matching |
| mp_id | TEXT | Associated MP's name |
| notes | TEXT | Additional notes about the entity |

### Relationships Table

| Column | Type | Description |
|--------|------|-------------|
| relationship_id | TEXT | Unique ID (UUID) |
| mp_name | TEXT | MP involved |
| entity | TEXT | Company, donor, or organization |
| relationship_type | TEXT | Owns Shares, Received Gift, etc. |
| value | TEXT | Financial value if disclosed |
| date_logged | TEXT | When the relationship was recorded |

## Improved Category System

The system uses an improved categorization system based on accounting principles, providing better insight into the nature of disclosed items:

### Main Categories

- **Asset**: Owned items that have value (shares, property)
- **Liability**: Obligations or debts (loans, mortgages)
- **Income**: Earnings received (dividends, salary)
- **Membership**: Ongoing services or benefits (club memberships, professional associations)
- **Gift**: Items received without payment (tickets, hospitality)
- **Travel**: Travel-related benefits (flights, accommodation)

### Temporal Classification

Items are classified based on their temporal nature:

- **one-time**: A single occurrence (e.g., a gift)
- **recurring**: Repeats periodically (e.g., dividend payments)
- **ongoing**: Continues indefinitely (e.g., share ownership)

### Item Persistence Tracking

The system tracks how items persist over time:

- **Long-term items**: Present for 3+ years
- **Medium-term items**: Present for 2 years
- **Short-term items**: Present for 1 year

### Command to Update Categories

To apply the improved category system to existing disclosures:

```bash
python update_categories.py

# To see changes without applying them
python update_categories.py --dry-run
```

## Comparison of Processing Methods

| Feature | OCR-based Workflow | Direct PDF Processing |
|---------|-------------------|----------------------|
| Processing Speed | Slower (two-step process) | Faster (single-step process) |
| PDF Size Limit | Limited by OCR API | Up to 3,600 pages or 2GB |
| Page-specific References | Yes (can reference specific pages) | Limited (references entire document) |
| Visual Element Understanding | Limited | Better (understands tables, charts, etc.) |
| Implementation Complexity | Higher | Lower |
| Cost | Higher (OCR + Gemini API) | Lower (Gemini API only) |

## Parliament Coverage

The system is configured to process disclosures from the following parliaments:

- 47th Parliament (Current)
- 46th Parliament
- 45th Parliament
- 44th Parliament
- 43rd Parliament

## License

This project is licensed under the MIT License - see the LICENSE file for details. 