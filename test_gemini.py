#!/usr/bin/env python3
import os
import argparse
import logging
import json
from typing import Dict, Any
from dotenv import load_dotenv
import google.generativeai as genai
import fitz  # PyMuPDF

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file.
        
    Returns:
        A string containing the extracted text.
    """
    logger.info(f"Extracting text from PDF: {pdf_path}")
    
    try:
        pdf_document = fitz.open(pdf_path)
        text = ""
        
        for page_num, page in enumerate(pdf_document):
            page_text = page.get_text()
            text += f"--- PAGE {page_num + 1} ---\n{page_text}\n\n"
        
        pdf_document.close()
        return text
    
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise

def test_gemini_api(api_key: str = None, pdf_path: str = None, sample_text: str = None):
    """
    Test the Gemini API with a sample text or PDF.
    
    Args:
        api_key: Google API key for Gemini. If None, will use the GOOGLE_API_KEY environment variable.
        pdf_path: Path to a PDF file to process. If provided, will extract text from the PDF.
        sample_text: Sample text to process. If None and pdf_path is None, will use a default sample.
    """
    # Use provided API key or get from environment
    api_key = api_key or os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable or provide it directly.")
    
    # Configure the Gemini API
    genai.configure(api_key=api_key)
    
    # Get the Gemini 2.0 Flash model
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    # Extract text from PDF if provided
    if pdf_path:
        sample_text = extract_text_from_pdf(pdf_path)
        filename = os.path.basename(pdf_path)
        mp_id = filename.split('_')[0]
        parliament = filename.split('_')[1].replace('p.pdf', '')
    else:
        # Use provided sample text or default sample
        if not sample_text:
            sample_text = """
--- PAGE 1 ---
STATEMENT OF REGISTRABLE INTERESTS

Member: Mark Dreyfus QC MP
Electorate: Isaacs
Date: 19 July 2010

I, Mark Alfred Dreyfus, give the following statement of interests.

1. SHAREHOLDINGS IN PUBLIC AND PRIVATE COMPANIES
Self:
BHP Billiton Ltd
Telstra Corporation Ltd
Spouse:
Westpac Banking Corporation
Commonwealth Bank of Australia

2. FAMILY AND BUSINESS TRUSTS AND NOMINEE COMPANIES
Self:
Beneficiary of the Dreyfus Family Trust
Spouse:
Beneficiary of the Dreyfus Family Trust

--- PAGE 2 ---
3. REAL ESTATE
Self:
Residential property in Malvern, VIC (investment)
Holiday house in Rye, VIC
Spouse:
Residential property in Malvern, VIC (investment)
Holiday house in Rye, VIC

4. DIRECTORSHIPS
Self:
Director, Dreyfus Nominees Pty Ltd (non-remunerated)
Spouse:
None

5. PARTNERSHIPS
Self:
None
Spouse:
None

6. LIABILITIES
Self:
Mortgage on investment property, Westpac Banking Corporation
Spouse:
Mortgage on investment property, Westpac Banking Corporation

--- PAGE 3 ---
7. BONDS, DEBENTURES AND LIKE INVESTMENTS
Self:
None
Spouse:
None

8. SAVINGS OR INVESTMENT ACCOUNTS
Self:
Savings account, Commonwealth Bank of Australia
Term deposit, Westpac Banking Corporation
Spouse:
Savings account, Commonwealth Bank of Australia
Term deposit, Westpac Banking Corporation

9. GIFTS
Self:
Two tickets to AFL Grand Final, value approx. $400, from Monash Foundation
Spouse:
None

10. SPONSORED TRAVEL
Self:
None
Spouse:
None

--- PAGE 4 ---
11. MEMBERSHIPS OF ASSOCIATIONS
Self:
Australian Labor Party
Law Institute of Victoria
Victorian Bar Association
Spouse:
Australian Labor Party

12. ANY OTHER INTERESTS
Self:
None
Spouse:
None

Signature: [Signature]
Date: 19 July 2010
            """
        filename = "dreyfus_43p.pdf"
        mp_id = "dreyfusm"
        parliament = "43"
    
    # Create prompt for Gemini
    prompt = f"""
You are an expert in analyzing and structuring political disclosure documents. 
I have a parliamentary disclosure document for an MP that I need you to analyze and convert to structured JSON format.

Here's information about the document:
- Filename: {filename}
- MP ID: {mp_id}
- Parliament: {parliament}

Below is the OCR-extracted text from the document. Please analyze it and extract the following information:
1. MP's full name
2. Party affiliation
3. Electorate
4. All declarations of registrable interests, categorized by type (Shares, Real Estate, Gifts, etc.)

IMPORTANT: The document may contain multiple disclosure dates or addendums. Each declaration should be linked to its specific declaration date.

For each declaration, include:
- Declaration date (when the declaration was made)
- Category (e.g., Shares, Real Estate, Gifts, Directorships, etc.)
- Entity (company, organization, or person involved)
- Value (if disclosed)
- Status (Active, Sold, Removed, etc.)
- Any other relevant details

Format your response as a valid JSON object with the following structure:
{{
  "mp_name": "Full Name",
  "party": "Party Name",
  "electorate": "Electorate Name",
  "disclosures": [
    {{
      "declaration_date": "YYYY-MM-DD",
      "category": "Category Name",
      "entity": "Entity Name",
      "value": "Value or Undisclosed",
      "status": "Status",
      "details": "Additional details about this declaration"
    }},
    ...
  ],
  "relationships": [
    {{
      "entity": "Entity Name",
      "relationship_type": "Owns Shares, Received Gift, etc.",
      "value": "Financial value if disclosed",
      "date_logged": "YYYY-MM-DD"
    }},
    ...
  ]
}}

If you cannot determine a value with certainty, use "Unknown" or "Undisclosed" as appropriate.
If the document structure is unclear or information is missing, make your best judgment based on the available text.

Here is the OCR text:
{sample_text}

Respond ONLY with the JSON object, nothing else.
"""
    
    try:
        # Call Gemini API
        logger.info("Calling Gemini API...")
        response = model.generate_content(prompt)
        
        # Extract JSON from response
        response_text = response.text
        
        # Try to find JSON in the response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            structured_data = json.loads(json_str)
        else:
            # If no JSON found, try to parse the whole response
            structured_data = json.loads(response_text)
        
        # Print the structured data
        logger.info("Structured data extracted successfully:")
        print(json.dumps(structured_data, indent=2))
        
        # Save the structured data to a file
        output_filename = f"gemini_test_output_{os.path.splitext(filename)[0]}.json"
        with open(output_filename, "w") as f:
            json.dump(structured_data, f, indent=2)
        
        logger.info(f"Structured data saved to {output_filename}")
        
    except Exception as e:
        logger.error(f"Error calling Gemini API: {str(e)}")
        logger.error(f"Response text: {response_text if 'response_text' in locals() else 'No response'}")

def main():
    """
    Main function to test the Gemini API.
    """
    parser = argparse.ArgumentParser(description="Test the Gemini API")
    parser.add_argument("--api-key", help="Google API key for Gemini")
    parser.add_argument("--pdf", help="Path to a PDF file to process")
    parser.add_argument("--sample-file", help="Path to a file containing sample text to process")
    
    args = parser.parse_args()
    
    # Load sample text from file if provided
    sample_text = None
    if args.sample_file:
        with open(args.sample_file, "r") as f:
            sample_text = f.read()
    
    # Test the Gemini API
    test_gemini_api(api_key=args.api_key, pdf_path=args.pdf, sample_text=sample_text)

if __name__ == "__main__":
    main() 