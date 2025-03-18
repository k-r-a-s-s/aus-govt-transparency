#!/usr/bin/env python3
import os
import argparse
import logging
import json
import uuid
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from ocr_processor import OCRProcessor
from gemini_processor import GeminiProcessor
from db_handler import DatabaseHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("process_disclosures.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')

def process_single_pdf(
    pdf_path: str,
    ocr_processor: OCRProcessor,
    gemini_processor: GeminiProcessor,
    db_handler: Optional[DatabaseHandler] = None,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a single PDF file and extract structured data.
    
    Args:
        pdf_path: Path to the PDF file.
        ocr_processor: OCR processor instance.
        gemini_processor: Gemini processor instance.
        db_handler: Database handler instance. If provided, will store the structured data.
        output_dir: Directory to save the structured data as JSON. If None, will not save.
        
    Returns:
        A dictionary containing the structured data extracted from the PDF.
    """
    logger.info(f"Processing PDF: {pdf_path}")
    
    try:
        # Step 1: Process PDF with OCR
        ocr_data = ocr_processor.process_local_pdf(pdf_path)
        
        # Step 2: Extract structured data with Gemini
        structured_data = gemini_processor.extract_structured_data(ocr_data)
        
        # Step 3: Store structured data in database if handler provided
        if db_handler:
            disclosure_ids = db_handler.store_structured_data(structured_data)
            structured_data["disclosure_ids"] = disclosure_ids
        
        # Step 4: Save structured data as JSON if output directory provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            filename = os.path.basename(pdf_path)
            output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.json")
            
            with open(output_path, "w") as f:
                json.dump(structured_data, f, indent=2)
            
            logger.info(f"Saved structured data to: {output_path}")
        
        return structured_data
        
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
        return {
            "error": str(e),
            "pdf_path": pdf_path
        }

def process_batch_pdfs(
    pdf_dir: str,
    ocr_processor: OCRProcessor,
    gemini_processor: GeminiProcessor,
    db_handler: Optional[DatabaseHandler] = None,
    output_dir: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Process multiple PDF files in a directory.
    
    Args:
        pdf_dir: Directory containing PDF files.
        ocr_processor: OCR processor instance.
        gemini_processor: Gemini processor instance.
        db_handler: Database handler instance. If provided, will store the structured data.
        output_dir: Directory to save the structured data as JSON. If None, will not save.
        limit: Maximum number of PDFs to process. If None, process all PDFs.
        
    Returns:
        A list of dictionaries containing the structured data extracted from each PDF.
    """
    logger.info(f"Batch processing PDFs from directory: {pdf_dir}")
    
    # Get list of PDF files
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    
    if limit:
        pdf_files = pdf_files[:limit]
        
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    # Process each PDF
    results = []
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_dir, pdf_file)
        try:
            result = process_single_pdf(
                pdf_path=pdf_path,
                ocr_processor=ocr_processor,
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
    Main function to process parliamentary disclosure PDFs.
    """
    parser = argparse.ArgumentParser(description="Process parliamentary disclosure PDFs")
    parser.add_argument("--pdf", help="Path to a single PDF file to process")
    parser.add_argument("--pdf-dir", help="Directory containing PDF files to process")
    parser.add_argument("--output-dir", help="Directory to save structured data as JSON")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to SQLite database file")
    parser.add_argument("--limit", type=int, help="Maximum number of PDFs to process")
    parser.add_argument("--skip-db", action="store_true", help="Skip storing data in database")
    parser.add_argument("--export-json", help="Export all database data to a JSON file")
    parser.add_argument("--credentials", help="Path to Google Cloud credentials JSON file")
    parser.add_argument("--skip-ocr", action="store_true", help="Skip OCR and use PyMuPDF for text extraction")
    
    args = parser.parse_args()
    
    # Initialize processors
    ocr_processor = OCRProcessor(credentials_path=args.credentials)
    gemini_processor = GeminiProcessor()
    
    # Initialize database handler if not skipped
    db_handler = None if args.skip_db else DatabaseHandler(db_path=args.db_path)
    
    # Export database to JSON if requested
    if args.export_json and db_handler:
        db_handler.export_to_json(args.export_json)
        return
    
    # Process single PDF
    if args.pdf:
        process_single_pdf(
            pdf_path=args.pdf,
            ocr_processor=ocr_processor,
            gemini_processor=gemini_processor,
            db_handler=db_handler,
            output_dir=args.output_dir
        )
    
    # Process batch PDFs
    elif args.pdf_dir:
        process_batch_pdfs(
            pdf_dir=args.pdf_dir,
            ocr_processor=ocr_processor,
            gemini_processor=gemini_processor,
            db_handler=db_handler,
            output_dir=args.output_dir,
            limit=args.limit
        )
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 