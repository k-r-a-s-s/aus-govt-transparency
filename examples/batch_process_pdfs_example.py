#!/usr/bin/env python3
"""
Example script demonstrating how to batch process multiple PDF files with the Gemini PDF processor.
"""
import os
import sys
import logging
import json
import argparse
from dotenv import load_dotenv

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

def main():
    """
    Main function to demonstrate batch processing of PDFs with Gemini.
    """
    parser = argparse.ArgumentParser(description="Batch process PDFs with Gemini")
    parser.add_argument("pdf_dir", help="Directory containing PDF files to process")
    parser.add_argument("--output-dir", default="gemini_output", help="Directory to save structured data as JSON")
    parser.add_argument("--limit", type=int, help="Maximum number of PDFs to process")
    parser.add_argument("--use-file-api", action="store_true", help="Force using the File API for uploading")
    parser.add_argument("--store-in-db", action="store_true", help="Store structured data in the database")
    
    args = parser.parse_args()
    
    # Check if PDF directory exists
    if not os.path.isdir(args.pdf_dir):
        print(f"Error: PDF directory not found at {args.pdf_dir}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Processing PDFs from directory: {args.pdf_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Limit: {args.limit if args.limit else 'No limit'}")
    print(f"Using File API: {args.use_file_api}")
    print(f"Storing in database: {args.store_in_db}")
    
    try:
        # Initialize the Gemini PDF processor
        gemini_processor = GeminiPDFProcessor()
        
        # Initialize database handler if needed
        db_handler = None
        if args.store_in_db:
            db_handler = DatabaseHandler()
        
        # Get list of PDF files
        pdf_files = [f for f in os.listdir(args.pdf_dir) if f.lower().endswith('.pdf')]
        
        if args.limit:
            pdf_files = pdf_files[:args.limit]
            
        print(f"\nFound {len(pdf_files)} PDF files to process")
        
        # Process each PDF
        results = []
        for i, pdf_file in enumerate(pdf_files):
            pdf_path = os.path.join(args.pdf_dir, pdf_file)
            print(f"\nProcessing PDF {i+1}/{len(pdf_files)}: {pdf_file}")
            
            try:
                # Process the PDF
                structured_data = gemini_processor.process_pdf(pdf_path, use_file_api=args.use_file_api)
                
                # Store in database if requested
                if db_handler:
                    disclosure_ids = db_handler.store_structured_data(structured_data)
                    print(f"Stored {len(disclosure_ids)} disclosures in database")
                
                # Save to JSON file
                mp_name = structured_data.get("mp_name", "unknown").replace(" ", "_").lower()
                party = structured_data.get("party", "").replace(" ", "_").lower()
                output_path = os.path.join(args.output_dir, f"{mp_name}_{party}_gemini.json")
                
                with open(output_path, "w") as f:
                    json.dump(structured_data, f, indent=2)
                
                print(f"Saved structured data to: {output_path}")
                
                # Add to results
                results.append({
                    "pdf_file": pdf_file,
                    "mp_name": structured_data.get("mp_name", "Unknown"),
                    "party": structured_data.get("party", "Unknown"),
                    "disclosures": len(structured_data.get("disclosures", [])),
                    "relationships": len(structured_data.get("relationships", [])),
                    "output_path": output_path
                })
                
            except Exception as e:
                print(f"Error processing PDF {pdf_path}: {str(e)}")
                results.append({
                    "pdf_file": pdf_file,
                    "error": str(e)
                })
        
        # Print summary
        print("\nBatch Processing Summary:")
        print(f"Total PDFs processed: {len(results)}")
        print(f"Successful: {len([r for r in results if 'error' not in r])}")
        print(f"Failed: {len([r for r in results if 'error' in r])}")
        
        # Save summary to file
        summary_path = os.path.join(args.output_dir, "batch_processing_summary.json")
        with open(summary_path, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\nSaved batch processing summary to: {summary_path}")
    
    except Exception as e:
        print(f"Error in batch processing: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 