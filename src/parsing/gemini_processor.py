import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
from dotenv import load_dotenv
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')

class GeminiProcessor:
    """
    A class to interact with Google Gemini 2.0 API for processing OCR text and extracting structured data.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini processor.
        
        Args:
            api_key: Google API key for Gemini. If None, will use the GOOGLE_API_KEY environment variable.
        """
        # Use provided API key or get from environment
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable or provide it directly.")
        
        # Configure the Gemini API
        genai.configure(api_key=self.api_key)
        
        # Get the Gemini 2.0 Flash model
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def extract_structured_data(self, ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured data from OCR text using Gemini 2.0.
        
        Args:
            ocr_data: Dictionary containing OCR data with metadata and page text.
            
        Returns:
            A dictionary containing the structured data extracted from the OCR text.
        """
        metadata = ocr_data.get("metadata", {})
        pages = ocr_data.get("pages", [])
        
        # Combine all page text
        all_text = "\n\n".join([f"--- PAGE {page['page_number']} ---\n{page['text']}" for page in pages])
        
        # Create prompt for Gemini
        prompt = self._create_extraction_prompt(metadata, all_text)
        
        try:
            # Call Gemini API
            response = self.model.generate_content(prompt)
            
            # Extract JSON from response
            structured_data = self._extract_json_from_response(response.text)
            
            # Add metadata
            pdf_url = metadata.get("filename", "")
            page_numbers = [page["page_number"] for page in pages]
            
            # Add PDF reference and page numbers to each disclosure
            for disclosure in structured_data.get("disclosures", []):
                disclosure["pdf_url"] = pdf_url
                disclosure["page_numbers"] = ",".join(map(str, page_numbers))
            
            return structured_data
            
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}")
            raise
    
    def _create_extraction_prompt(self, metadata: Dict[str, Any], text: str) -> str:
        """
        Create a prompt for Gemini to extract structured data from OCR text.
        
        Args:
            metadata: Dictionary containing PDF metadata.
            text: OCR text from the PDF.
            
        Returns:
            A string containing the prompt for Gemini.
        """
        return f"""
You are an expert in analyzing and structuring political disclosure documents. 
I have a parliamentary disclosure document for an MP that I need you to analyze and convert to structured JSON format.

Here's information about the document:
- Filename: {metadata.get('filename', 'Unknown')}
- MP ID: {metadata.get('mp_id', 'Unknown')}
- Parliament: {metadata.get('parliament', 'Unknown')}

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
{text}

Respond ONLY with the JSON object, nothing else.
"""
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """
        Extract JSON from Gemini response text.
        
        Args:
            response_text: Text response from Gemini.
            
        Returns:
            A dictionary containing the extracted JSON.
        """
        # Clean up response to extract only the JSON part
        try:
            # Try to find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            else:
                # If no JSON found, try to parse the whole response
                return json.loads(response_text)
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from Gemini response: {str(e)}")
            logger.error(f"Response text: {response_text}")
            
            # Return a basic structure with error information
            return {
                "error": "Failed to parse JSON from Gemini response",
                "raw_response": response_text
            }
    
    def batch_process_ocr_results(self, ocr_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple OCR results with Gemini.
        
        Args:
            ocr_results: List of dictionaries containing OCR results.
            
        Returns:
            A list of dictionaries containing the structured data extracted from each OCR result.
        """
        logger.info(f"Batch processing {len(ocr_results)} OCR results with Gemini")
        
        structured_data_list = []
        
        for ocr_result in ocr_results:
            try:
                filename = ocr_result.get("metadata", {}).get("filename", "Unknown")
                logger.info(f"Processing OCR result for {filename} with Gemini")
                
                structured_data = self.extract_structured_data(ocr_result)
                structured_data_list.append(structured_data)
                
            except Exception as e:
                logger.error(f"Error processing OCR result with Gemini: {str(e)}")
                structured_data_list.append({
                    "error": str(e),
                    "filename": ocr_result.get("metadata", {}).get("filename", "Unknown")
                })
        
        return structured_data_list 