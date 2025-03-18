#!/usr/bin/env python3
import os
import argparse
import logging
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from gemini_pdf_processor import GeminiPDFProcessor
from db_handler import DatabaseHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')

def test_gemini_pdf_processing(
    pdf_path: str, 
    output_dir: Optional[str] = None,
    use_file_api: bool = False,
    store_in_db: bool = False,
    db_path: str = "disclosures.db",
    skip_post_processing: bool = False
):
    """
    Test the Gemini PDF processing with a sample PDF.
    
    Args:
        pdf_path: Path to a PDF file to process.
        output_dir: Directory to save the structured data as JSON. If None, will not save.
        use_file_api: Whether to use the File API for uploading.
        store_in_db: Whether to store the structured data in the database.
        db_path: Path to the SQLite database file.
        skip_post_processing: Whether to skip post-processing of the extracted data.
    """
    logger.info(f"Testing Gemini PDF processing with file: {pdf_path}")
    
    # Initialize the Gemini PDF processor
    gemini_processor = GeminiPDFProcessor(apply_post_processing=not skip_post_processing)
    
    # Initialize database handler if needed
    db_handler = None
    if store_in_db:
        db_handler = DatabaseHandler(db_path=db_path)
    
    try:
        # Process the PDF with Gemini
        structured_data = gemini_processor.process_pdf(pdf_path, use_file_api=use_file_api)
        
        # Print the structured data
        logger.info("Structured data extracted successfully:")
        print(json.dumps(structured_data, indent=2))
        
        # Store in database if requested
        if db_handler:
            disclosure_ids = db_handler.store_structured_data(structured_data)
            logger.info(f"Stored structured data in database with IDs: {disclosure_ids}")
        
        # Save the structured data to a file if output directory provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            filename = os.path.basename(pdf_path)
            output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_gemini.json")
            
            with open(output_path, "w") as f:
                json.dump(structured_data, f, indent=2)
            
            logger.info(f"Saved structured data to: {output_path}")
        
        return structured_data
        
    except Exception as e:
        logger.error(f"Error processing PDF with Gemini: {str(e)}")
        return {
            "error": str(e),
            "pdf_path": pdf_path
        }

def batch_process_pdfs(
    pdf_dir: str,
    output_dir: Optional[str] = None,
    use_file_api: bool = False,
    store_in_db: bool = False,
    db_path: str = "disclosures.db",
    limit: Optional[int] = None,
    skip_post_processing: bool = False
):
    """
    Process multiple PDF files with Gemini.
    
    Args:
        pdf_dir: Directory containing PDF files.
        output_dir: Directory to save the structured data as JSON. If None, will not save.
        use_file_api: Whether to use the File API for uploading.
        store_in_db: Whether to store the structured data in the database.
        db_path: Path to the SQLite database file.
        limit: Maximum number of PDFs to process. If None, process all PDFs.
        skip_post_processing: Whether to skip post-processing of the extracted data.
    """
    logger.info(f"Batch processing PDFs from directory: {pdf_dir}")
    
    # Initialize the Gemini PDF processor
    gemini_processor = GeminiPDFProcessor(apply_post_processing=not skip_post_processing)
    
    # Initialize database handler if needed
    db_handler = None
    if store_in_db:
        db_handler = DatabaseHandler(db_path=db_path)
    
    # Process PDFs
    results = gemini_processor.batch_process_pdfs(pdf_dir, use_file_api=use_file_api, limit=limit)
    
    # Store in database if requested
    if db_handler:
        for result in results:
            if "error" not in result:
                try:
                    disclosure_ids = db_handler.store_structured_data(result)
                    logger.info(f"Stored structured data in database with IDs: {disclosure_ids}")
                except Exception as e:
                    logger.error(f"Error storing structured data in database: {str(e)}")
    
    # Save the structured data to files if output directory provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
        for i, result in enumerate(results):
            try:
                if "error" not in result:
                    # Use MP name and party for filename if available
                    mp_name = result.get("mp_name", f"unknown_{i}")
                    mp_name = mp_name.lower().replace(" ", "_")
                    party = result.get("party", "").lower().replace(" ", "_")
                    
                    output_path = os.path.join(output_dir, f"{mp_name}_{party}_gemini.json")
                    
                    with open(output_path, "w") as f:
                        json.dump(result, f, indent=2)
                    
                    logger.info(f"Saved structured data to: {output_path}")
            except Exception as e:
                logger.error(f"Error saving structured data to file: {str(e)}")
    
    return results

def main():
    """
    Main function to test the Gemini PDF processing.
    """
    parser = argparse.ArgumentParser(description="Test Gemini PDF processing")
    parser.add_argument("--pdf", help="Path to a PDF file to process")
    parser.add_argument("--pdf-dir", help="Directory containing PDF files to process")
    parser.add_argument("--output-dir", help="Directory to save structured data as JSON")
    parser.add_argument("--use-file-api", action="store_true", help="Force using the File API for uploading")
    parser.add_argument("--store-in-db", action="store_true", help="Store structured data in the database")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to SQLite database file")
    parser.add_argument("--limit", type=int, help="Maximum number of PDFs to process")
    parser.add_argument("--skip-post-processing", action="store_true", help="Skip post-processing of extracted data")
    
    args = parser.parse_args()
    
    # Process single PDF
    if args.pdf:
        test_gemini_pdf_processing(
            pdf_path=args.pdf,
            output_dir=args.output_dir,
            use_file_api=args.use_file_api,
            store_in_db=args.store_in_db,
            db_path=args.db_path,
            skip_post_processing=args.skip_post_processing
        )
    
    # Process batch PDFs
    elif args.pdf_dir:
        batch_process_pdfs(
            pdf_dir=args.pdf_dir,
            output_dir=args.output_dir,
            use_file_api=args.use_file_api,
            store_in_db=args.store_in_db,
            db_path=args.db_path,
            limit=args.limit,
            skip_post_processing=args.skip_post_processing
        )
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 