#!/usr/bin/env python3
"""
Example script demonstrating how to use the Gemini PDF processor to directly process a PDF file.
"""
import os
import sys
import logging
import json
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
    Main function to demonstrate Gemini PDF processing.
    """
    # Check if PDF path is provided
    if len(sys.argv) < 2:
        print("Usage: python process_pdf_example.py <path_to_pdf>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # Check if PDF exists
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)
    
    print(f"Processing PDF: {pdf_path}")
    
    try:
        # Initialize the Gemini PDF processor
        gemini_processor = GeminiPDFProcessor()
        
        # Process the PDF
        structured_data = gemini_processor.process_pdf(pdf_path)
        
        # Print the structured data
        print("\nExtracted structured data:")
        print(json.dumps(structured_data, indent=2))
        
        # Save the structured data to a file
        output_path = f"{os.path.splitext(pdf_path)[0]}_gemini_output.json"
        with open(output_path, "w") as f:
            json.dump(structured_data, f, indent=2)
        
        print(f"\nSaved structured data to: {output_path}")
        
        # Print summary
        print("\nSummary:")
        print(f"MP Name: {structured_data.get('mp_name', 'Unknown')}")
        print(f"Party: {structured_data.get('party', 'Unknown')}")
        print(f"Electorate: {structured_data.get('electorate', 'Unknown')}")
        print(f"Disclosures: {len(structured_data.get('disclosures', []))}")
        print(f"Relationships: {len(structured_data.get('relationships', []))}")
        
        # Optional: Store in database
        store_in_db = input("\nStore in database? (y/n): ").lower() == 'y'
        if store_in_db:
            db_handler = DatabaseHandler()
            disclosure_ids = db_handler.store_structured_data(structured_data)
            print(f"Stored {len(disclosure_ids)} disclosures in database")
    
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 