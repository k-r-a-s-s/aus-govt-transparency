import os
import json
import logging
import pathlib
import copy
import re
from typing import Dict, Any, List, Optional, Union
from dotenv import load_dotenv
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
import time
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')

class GeminiPDFProcessor:
    """
    A class to interact with Google Gemini API for direct PDF processing and extracting structured data.
    """
    
    def __init__(self, api_key: Optional[str] = None, apply_post_processing: bool = True):
        """
        Initialize the Gemini PDF processor.
        
        Args:
            api_key: Google API key for Gemini. If None, will use the GOOGLE_API_KEY environment variable.
            apply_post_processing: Whether to apply post-processing to the extracted data.
        """
        # Use provided API key or get from environment
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable or provide it directly.")
        
        # Configure the Gemini API
        genai.configure(api_key=self.api_key)
        
        # Get the Gemini model
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Post-processing flag
        self.apply_post_processing = apply_post_processing
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def process_pdf(self, pdf_path: str, use_file_api: bool = False) -> Dict[str, Any]:
        """
        Process a PDF file directly with Gemini API and extract structured data.
        
        Args:
            pdf_path: Path to the PDF file.
            use_file_api: Whether to use the File API for uploading. 
                          If True, always uses File API. 
                          If False, uses File API only for files > 20MB.
            
        Returns:
            A dictionary containing the structured data extracted from the PDF.
        """
        logger.info(f"Processing PDF directly with Gemini API: {pdf_path}")
        
        # Get file size
        file_size = os.path.getsize(pdf_path)
        file_size_mb = file_size / (1024 * 1024)
        logger.info(f"PDF file size: {file_size_mb:.2f} MB")
        
        # Extract filename for metadata
        filename = os.path.basename(pdf_path)
        name_parts = os.path.splitext(filename)[0].split('_')
        mp_id = name_parts[0] if len(name_parts) > 0 else "Unknown"
        parliament = name_parts[1].replace('p', '') if len(name_parts) > 1 else "Unknown"
        
        # Create prompt for Gemini
        prompt = self._create_extraction_prompt(filename, mp_id, parliament)
        
        try:
            # Read file as bytes
            pdf_bytes = pathlib.Path(pdf_path).read_bytes()
            
            # For large PDFs, we might need to handle them differently
            # but for now, we'll use the standard approach
            if file_size_mb > 20:
                logger.warning(f"PDF file is large ({file_size_mb:.2f} MB). This might exceed API limits.")
            
            # Create multipart content with PDF and prompt
            response = self.model.generate_content([
                {
                    "mime_type": "application/pdf",
                    "data": pdf_bytes
                },
                prompt
            ])
            
            # Extract JSON from response
            structured_data = self._extract_json_from_response(response.text)
            
            # Add PDF reference to each disclosure
            for disclosure in structured_data.get("disclosures", []):
                disclosure["pdf_url"] = filename
            
            # Ensure the structure includes an empty relationships array for backward compatibility
            if "relationships" not in structured_data:
                structured_data["relationships"] = []
            
            # Apply post-processing if enabled
            if self.apply_post_processing:
                structured_data = self.post_process_disclosures(structured_data)
            
            return structured_data
            
        except Exception as e:
            logger.error(f"Error processing PDF with Gemini API: {str(e)}")
            raise
    
    def post_process_disclosures(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post-process the structured data to:
        1. Split grouped share entries into individual entries
        2. Add sub-categories to gift entries
        
        Args:
            structured_data: The structured data extracted from the PDF
            
        Returns:
            The post-processed structured data
        """
        logger.info("Applying post-processing to extracted data")
        
        # Make a copy to avoid modifying the original
        processed_data = copy.deepcopy(structured_data)
        
        # Get all disclosures
        disclosures = processed_data.get("disclosures", [])
        
        # Process shares (splitting)
        new_disclosures = []
        for disclosure in disclosures:
            if disclosure.get("category") == "Shares":
                # Process shares...
                split_disclosures = self._split_share_entry(disclosure)
                new_disclosures.extend(split_disclosures)
            else:
                new_disclosures.append(disclosure)
        
        # Process gifts (sub-categorization)
        for disclosure in new_disclosures:
            if disclosure.get("category") == "Gifts":
                # Add sub-category
                disclosure["sub_category"] = self._classify_gift(disclosure)
        
        # Update the disclosures
        processed_data["disclosures"] = new_disclosures
        
        logger.info(f"Post-processing complete. Original disclosures: {len(disclosures)}, New disclosures: {len(new_disclosures)}")
        
        return processed_data
    
    def _split_share_entry(self, disclosure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split a share entry with multiple entities into individual entries.
        
        Args:
            disclosure: A disclosure entry with category "Shares"
            
        Returns:
            A list of individual share entries
        """
        entity = disclosure.get("entity", "")
        
        # If entity is N/A or doesn't contain list indicators, return as is
        if entity == "N/A" or not re.search(r'[,;&]|\band\b', entity):
            return [disclosure]
        
        # Split the entity string by common separators
        entities = re.split(r'\s*,\s*|\s+and\s+|\s*;\s*|\s*&\s*', entity)
        entities = [e.strip() for e in entities if e.strip()]
        
        # Create a new disclosure for each entity
        result = []
        for single_entity in entities:
            new_disclosure = copy.deepcopy(disclosure)
            new_disclosure["entity"] = single_entity
            
            # Update details to be more specific
            if "details" in new_disclosure:
                # If details is generic, make it more specific
                if "shareholdings" in new_disclosure["details"].lower():
                    new_disclosure["details"] = f"Shareholding in {single_entity}"
            
            result.append(new_disclosure)
        
        return result
    
    def _classify_gift(self, disclosure: Dict[str, Any]) -> str:
        """
        Classify a gift disclosure into a sub-category.
        
        Args:
            disclosure: A disclosure entry with category "Gifts"
            
        Returns:
            The sub-category of the gift
        """
        details = disclosure.get("details", "").lower()
        entity = disclosure.get("entity", "").lower()
        combined_text = f"{details} {entity}"
        
        # Define classification rules
        classifications = [
            ("Sports Tickets", r'ticket|game|match|final|stadium|afl|nrl|cricket|tennis|football|rugby|soccer|basketball'),
            ("Alcohol", r'wine|champagne|spirits|beer|bottle|alcohol'),
            ("Food", r'hamper|chocolates|food|meal|dinner|lunch|breakfast|catering'),
            ("Clothing", r'shirt|tie|scarf|jersey|clothing|apparel|t-shirt|cap|hat'),
            ("Electronics", r'ipad|device|electronic|gadget|phone|tablet|computer|laptop|digital'),
            ("Travel", r'upgrade|flight|lounge|accommodation|chairman\'s lounge|velocity|qantas|virgin|emirates|hotel'),
            ("Books/Media", r'book|publication|media|dvd|cd|magazine|journal'),
            ("Decorative", r'artwork|ornament|statue|plaque|trophy|medal|award|commemorative'),
            ("Office Items", r'pen|stationery|business card|desk|notepad|calendar|coaster')
        ]
        
        # Check each classification
        for sub_category, pattern in classifications:
            if re.search(pattern, combined_text):
                return sub_category
        
        # Default
        return "Other Gifts"
    
    def _create_extraction_prompt(self, filename: str, mp_id: str, parliament: str) -> str:
        """
        Create a prompt for Gemini to extract structured data from a PDF.
        
        Args:
            filename: Name of the PDF file.
            mp_id: MP ID extracted from the filename.
            parliament: Parliament number extracted from the filename.
            
        Returns:
            A string containing the prompt for Gemini.
        """
        return f"""
You are an expert in analyzing and structuring political disclosure documents. 
I have a parliamentary disclosure document for an MP that I need you to analyze and convert to structured JSON format.

Here's information about the document:
- Filename: {filename}
- MP ID: {mp_id}
- Parliament: {parliament}

Please analyze the PDF document and extract the following information:
1. MP's full name
2. Party affiliation (only if explicitly mentioned in the document)
3. Electorate
4. All declarations of registrable interests, categorized by type

IMPORTANT: The document may contain multiple disclosure dates or addendums. Each declaration should be linked to its specific declaration date.

For each declaration, include:
- Declaration date (when the declaration was made)
- Category (use one of the standard categories listed below)
- Entity (company, organization, or person involved; use "N/A" if not applicable)
- Details (additional details about this declaration)

Standard Categories to use:
- Shares
- Real Estate
- Trusts
- Directorships
- Partnerships
- Liabilities
- Savings/Investments
- Income Sources
- Gifts
- Travel
- Hospitality
- Memberships
- Other Assets
- Other Interests

Format your response as a valid JSON object with the following structure:
{{
  "mp_name": "Full Name",
  "party": "Party Name",
  "electorate": "Electorate Name",
  "disclosures": [
    {{
      "declaration_date": "YYYY-MM-DD",
      "category": "Category Name",
      "entity": "Entity Name or N/A",
      "details": "Additional details about this declaration"
    }},
    ...
  ]
}}

If you cannot determine a value with certainty, use "Unknown" or "N/A" as appropriate.
If the document structure is unclear or information is missing, make your best judgment based on the available information.

Respond ONLY with the JSON object, nothing else.
"""
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """
        Extract JSON from the Gemini API response text.
        
        Args:
            response_text: The text response from Gemini API
            
        Returns:
            A dictionary containing the structured data
        """
        try:
            # Find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            else:
                logger.error("No JSON found in the response")
                return {}
        except Exception as e:
            logger.error(f"Error extracting JSON from response: {str(e)}")
            return {}
    
    def batch_process_pdfs(self, pdf_dir: str, use_file_api: bool = False, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Process multiple PDF files from a directory.
        
        Args:
            pdf_dir: Directory containing PDF files to process
            use_file_api: Whether to use the File API for uploading
            limit: Maximum number of PDFs to process. If None, process all PDFs.
            
        Returns:
            A list of dictionaries containing the structured data extracted from each PDF
        """
        logger.info(f"Batch processing PDFs from directory: {pdf_dir}")
        
        # Get list of PDF files
        pdf_files = []
        for root, _, files in os.walk(pdf_dir):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        # Sort files alphabetically
        pdf_files.sort()
        
        # Apply limit if specified
        if limit is not None and limit > 0:
            pdf_files = pdf_files[:limit]
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        
        # Process each PDF
        results = []
        for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
            try:
                # Process the PDF
                structured_data = self.process_pdf(pdf_path, use_file_api=use_file_api)
                
                # Add the PDF path to the result
                structured_data["pdf_path"] = pdf_path
                
                # Add to results
                results.append(structured_data)
                
                # Log success
                logger.info(f"Successfully processed: {pdf_path}")
                
                # Add a small delay to avoid rate limiting
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing {pdf_path}: {str(e)}")
                results.append({
                    "error": str(e),
                    "pdf_path": pdf_path
                })
        
        logger.info(f"Batch processing complete. Processed {len(results)} PDFs.")
        return results 