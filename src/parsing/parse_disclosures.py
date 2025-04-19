#!/usr/bin/env python3
"""
Main entry point for parsing Australian parliamentary disclosure PDFs using direct Gemini PDF processing (no OCR step).

This script orchestrates batch and single PDF processing, extracting structured data from PDFs using Gemini, and saving results to a database or JSON files. It is designed to work with the new modular pipeline and database schema (see refactor_plan.rmd and README.md).

Typical usage:
    python parse_disclosures.py --pdf-dir path/to/pdfs --db-path disclosures.db

Dependencies:
    - pdf_gemini_pipeline.py: Handles Gemini API calls for structured extraction
    - src/preparation/db_handler.py: Handles database operations
"""
import os
import argparse
import logging
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from pdf_gemini_pipeline import GeminiPDFProcessor
from src.preparation.db_handler import DatabaseHandler

# Configure logging with both file and console handlers
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("process_disclosures.log", mode='w'),  # 'w' mode to start fresh
        logging.StreamHandler()  # This will output to console
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')
api_key = os.getenv('GOOGLE_API_KEY')
logger.info(f"API Key present: {bool(api_key)}")

def process_single_pdf(
    pdf_path: str,
    gemini_processor: GeminiPDFProcessor,
    db_handler: Optional[DatabaseHandler] = None,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a single PDF file and extract structured data using Gemini.
    Args:
        pdf_path: Path to the PDF file.
        gemini_processor: GeminiPDFProcessor instance.
        db_handler: Database handler instance. If provided, will store the structured data.
        output_dir: Directory to save the structured data as JSON. If None, will not save.
    Returns:
        A dictionary containing the structured data extracted from the PDF.
    """
    logger.info(f"Processing PDF: {pdf_path}")
    try:
        # Step 1: Process PDF with Gemini
        logger.debug("Starting Gemini processing...")
        structured_data = gemini_processor.process_pdf(pdf_path)
        logger.debug(f"Gemini processing complete. Data received: {bool(structured_data)}")
        if structured_data:
            logger.debug(f"Data structure: {json.dumps(structured_data, indent=2)}")

        # Step 2: Store structured data in database if handler provided
        if db_handler and structured_data:
            logger.debug("Storing data in database...")
            disclosure_ids = db_handler.store_structured_data(structured_data)
            structured_data["disclosure_ids"] = disclosure_ids
            logger.debug(f"Stored {len(disclosure_ids)} disclosures in database")

        # Step 3: Save structured data as JSON if output directory provided
        if output_dir and structured_data:
            logger.debug(f"Saving to output directory: {output_dir}")
            os.makedirs(output_dir, exist_ok=True)
            filename = os.path.basename(pdf_path)
            output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.json")
            with open(output_path, "w") as f:
                json.dump(structured_data, f, indent=2)
            logger.info(f"Saved structured data to: {output_path}")

        return structured_data
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {str(e)}", exc_info=True)  # Added exc_info for stack trace
        return {
            "error": str(e),
            "pdf_path": pdf_path
        }

def process_batch_pdfs(
    pdf_dir: str,
    gemini_processor: GeminiPDFProcessor,
    db_handler: Optional[DatabaseHandler] = None,
    output_dir: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Process multiple PDF files in a directory using Gemini.
    Args:
        pdf_dir: Directory containing PDF files.
        gemini_processor: GeminiPDFProcessor instance.
        db_handler: Database handler instance. If provided, will store the structured data.
        output_dir: Directory to save the structured data as JSON. If None, will not save.
        limit: Maximum number of PDFs to process. If None, process all PDFs.
    Returns:
        A list of dictionaries containing the structured data extracted from each PDF.
    """
    logger.info(f"Batch processing PDFs from directory: {pdf_dir}")
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    pdf_files.sort()
    if limit:
        pdf_files = pdf_files[:limit]
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    results = []
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        try:
            result = process_single_pdf(
                pdf_path=pdf_path,
                gemini_processor=gemini_processor,
                db_handler=db_handler,
                output_dir=output_dir
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            results.append({
                "error": str(e),
                "pdf_path": pdf_path
            })
    return results

def main():
    """
    Main function to process parliamentary disclosure PDFs using Gemini direct PDF processing.
    """
    parser = argparse.ArgumentParser(description="Process parliamentary disclosure PDFs with Gemini")
    parser.add_argument("--pdf", help="Path to a single PDF file to process")
    parser.add_argument("--pdf-dir", help="Directory containing PDF files to process")
    parser.add_argument("--output-dir", help="Directory to save structured data as JSON")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to SQLite database file")
    parser.add_argument("--limit", type=int, help="Maximum number of PDFs to process")
    parser.add_argument("--skip-db", action="store_true", help="Skip storing data in database")
    parser.add_argument("--export-json", help="Export all database data to a JSON file")
    args = parser.parse_args()

    gemini_processor = GeminiPDFProcessor()
    db_handler = None if args.skip_db else DatabaseHandler(db_path=args.db_path)

    # Export database to JSON if requested
    if args.export_json and db_handler:
        db_handler.export_to_json(args.export_json)
        return

    # Process single PDF
    if args.pdf:
        process_single_pdf(
            pdf_path=args.pdf,
            gemini_processor=gemini_processor,
            db_handler=db_handler,
            output_dir=args.output_dir
        )
    # Process batch PDFs
    elif args.pdf_dir:
        process_batch_pdfs(
            pdf_dir=args.pdf_dir,
            gemini_processor=gemini_processor,
            db_handler=db_handler,
            output_dir=args.output_dir,
            limit=args.limit
        )
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 