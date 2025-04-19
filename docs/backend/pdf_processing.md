# PDF Processing Pipeline

The PDF processing pipeline is a core component of the Australian Government Transparency Project. It extracts structured data from parliamentary disclosure PDFs using Google's Gemini 2.0 AI and organizes it for downstream cleaning and analysis.

## Overview

The pipeline consists of several modular steps:

1. **PDF Collection**: Download PDFs from parliamentary websites using `src/preparation/scrape_parliament.py`.
2. **PDF Processing**: Extract structured data from PDFs using Gemini AI via `src/parsing/gemini_pdf_processor.py` and orchestrated by `src/main.py`.
3. **Post-Processing**: Clean and standardize extracted data (see [Data Standardization](./data_standardization.md)).
4. **Database Storage**: Store structured data in the canonical SQLite database (`disclosures.db`).

## Key Components

### PDF Collection
- `src/preparation/scrape_parliament.py`: Downloads PDFs and organizes them by parliament.
- `src/preparation/parliament_urls.py`: Configuration for parliament URLs.

### PDF Processing
- `src/parsing/gemini_pdf_processor.py`: Main module for extracting structured data from PDFs using Gemini 2.0 Flash.
- `src/parsing/parse_disclosures.py`: Batch processing and orchestration of PDF parsing.
- `src/main.py`: Orchestrates the full pipeline (scraping, parsing, cleaning, output).

### Post-Processing & Storage
- Post-processing and cleaning are handled by modules in `/src/cleaning`.
- Structured data is stored in `disclosures.db` using the canonical schema (see [Database Schema](./database.md)).

## Usage Examples

### Orchestrate the Full Pipeline
```bash
python src/main.py --parliament 47th --store-in-db --standardize
```
- See `python src/main.py --help` for all options (batch processing, skipping steps, etc.)

### Run Individual Steps
- **Scrape PDFs:**
    ```bash
    python src/preparation/scrape_parliament.py
    ```
- **Parse PDFs:**
    ```bash
    python src/parsing/parse_disclosures.py --pdf-dir pdfs/47th --db-path disclosures.db
    ```
- **Test Gemini PDF Processing:**
    ```bash
    python src/parsing/gemini_pdf_processor.py --pdf path/to/pdf
    ```

## Data Extraction Process

1. **PDF Loading**: Load PDF file into memory
2. **Content Extraction**: Use Gemini AI to extract structured data
3. **Prompting**: Guide the AI with a prompt for disclosure extraction
4. **JSON Parsing**: Parse the AI's response into a JSON structure
5. **Post-Processing**: Clean and standardize the extracted data
6. **Database Storage**: Store results in `disclosures.db`

## Rate Limiting and Error Handling

- The system includes adaptive rate limiting (see `src/common/rate_limiter.py`) to stay within Gemini API limits.
- Implements retry logic and progress tracking for robust batch processing.

## Notes
- All pipeline steps are modularized in `/src` for maintainability and testing.
- For full pipeline details, see the [README](../../README.md) and [docs/index.md](../index.md).

## Pipeline Module Structure: Orchestrator vs. Processor

- `parse_disclosures.py`: This is the main entry point and CLI orchestrator for batch or single PDF processing. Users should run this script to process PDFs, save results, and (optionally) insert into the database. It handles CLI arguments, file I/O, and database integration.
- `pdf_gemini_pipeline.py`: This is the core Gemini PDF processor module. It provides the `GeminiPDFProcessor` class, which handles all Gemini API calls, prompt loading, rate limiting, and post-processing. This module is not meant to be run directly; it is imported and used by `parse_disclosures.py` (and potentially other scripts) to perform the actual extraction.

**Summary:**
- Use `parse_disclosures.py` to run the pipeline.
- `pdf_gemini_pipeline.py` is the engine/library for Gemini PDF extraction. 