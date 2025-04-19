import os
import json
import logging
import pathlib
import copy
import re
import time
import datetime
import random
from typing import Dict, Any, List, Optional, Union, Deque
from collections import deque
from dotenv import load_dotenv
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
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

class RateLimiter:
    """
    A class to handle rate limiting for API requests.
    Implements a sliding window mechanism to track requests per minute.
    """
    
    def __init__(self, requests_per_minute: int = 15, requests_per_day: int = 1500):
        """
        Initialize the rate limiter.
        
        Args:
            requests_per_minute: Maximum number of requests allowed per minute
            requests_per_day: Maximum number of requests allowed per day
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        
        # Track request timestamps using deques
        self.minute_window: Deque[float] = deque()
        self.day_window: Deque[float] = deque()
        
        # Track successful requests and failures
        self.total_successful_requests = 0
        self.total_rate_limit_errors = 0
        
        logger.info(f"Rate limiter initialized with {requests_per_minute} RPM and {requests_per_day} RPD")
    
    def _cleanup_windows(self):
        """Clean up expired timestamps from the windows"""
        current_time = time.time()
        
        # Clean up minute window
        while self.minute_window and (current_time - self.minute_window[0]) > 60:
            self.minute_window.popleft()
        
        # Clean up day window
        while self.day_window and (current_time - self.day_window[0]) > 86400:
            self.day_window.popleft()
    
    def check_rate_limits(self) -> bool:
        """
        Check if the current request would exceed any rate limits.
        
        Returns:
            True if limits are not exceeded, False otherwise
        """
        self._cleanup_windows()
        
        # Check minute limit
        if len(self.minute_window) >= self.requests_per_minute:
            return False
        
        # Check day limit
        if len(self.day_window) >= self.requests_per_day:
            return False
        
        return True
    
    def record_request(self):
        """Record a successful request"""
        current_time = time.time()
        self.minute_window.append(current_time)
        self.day_window.append(current_time)
        self.total_successful_requests += 1
    
    def record_rate_limit_error(self):
        """Record a rate limit error"""
        self.total_rate_limit_errors += 1
    
    def get_current_usage(self) -> Dict[str, int]:
        """
        Get the current usage statistics.
        
        Returns:
            Dictionary with current usage statistics
        """
        self._cleanup_windows()
        return {
            "requests_in_last_minute": len(self.minute_window),
            "requests_in_last_day": len(self.day_window),
            "total_successful_requests": self.total_successful_requests,
            "total_rate_limit_errors": self.total_rate_limit_errors
        }
    
    def wait_if_needed(self):
        """Wait if necessary to avoid exceeding rate limits"""
        while not self.check_rate_limits():
            # Check which limit is causing the wait
            current_rpm = len(self.minute_window)
            current_rpd = len(self.day_window)
            
            if current_rpm >= self.requests_per_minute:
                # Calculate time until oldest request expires from minute window
                sleep_time = 60 - (time.time() - self.minute_window[0]) + 0.1  # Add a small buffer
                logger.warning(f"Rate limit approaching: {current_rpm}/{self.requests_per_minute} RPM. Waiting {sleep_time:.2f}s")
                time.sleep(max(1, min(sleep_time, 30)))  # Cap waiting time between 1-30 seconds
            elif current_rpd >= self.requests_per_day:
                # Daily limit reached, calculate time until oldest request expires
                sleep_time = 86400 - (time.time() - self.day_window[0]) + 0.1
                logger.warning(f"Daily rate limit reached: {current_rpd}/{self.requests_per_day} RPD. Long wait required: {sleep_time/60:.1f} minutes")
                # For daily limits, we might want to terminate rather than wait a very long time
                raise Exception(f"Daily rate limit of {self.requests_per_day} requests reached. Try again tomorrow.")
            else:
                # Add a small delay as a fallback
                logger.info("Rate limits approaching, adding small delay")
                time.sleep(2)
            
            # Recheck the windows after waiting
            self._cleanup_windows()
            
        # Add a small random delay to avoid multiple processes hitting limits simultaneously
        jitter = random.uniform(0.1, 0.5)
        time.sleep(jitter)

class RateLimitError(Exception):
    """Exception raised when a rate limit is hit"""
    pass

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
        
        # Initialize rate limiter (using default values for Gemini 2.0 Flash free tier)
        self.rate_limiter = RateLimiter(requests_per_minute=15, requests_per_day=1500)
        
    def is_rate_limit_error(self, error: Exception) -> bool:
        """
        Check if an exception is related to rate limiting.
        
        Args:
            error: The exception to check
            
        Returns:
            True if the error is related to rate limiting
        """
        error_str = str(error).lower()
        return (
            "rate limit" in error_str or 
            "quota exceeded" in error_str or 
            "resource exhausted" in error_str or
            "429" in error_str or
            "too many requests" in error_str
        )
        
    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(5), 
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
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
        
        # Check and wait for rate limits if needed
        self.rate_limiter.wait_if_needed()
        
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
            
            # Record successful request
            self.rate_limiter.record_request()
            
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
            error_message = str(e)
            logger.error(f"Error processing PDF with Gemini API: {error_message}")
            
            # Check if this is a rate limit error
            if self.is_rate_limit_error(e):
                self.rate_limiter.record_rate_limit_error()
                logger.warning("Rate limit exceeded. Retrying with exponential backoff...")
                # Add current timestamp to track when the error occurred
                raise RateLimitError(f"Rate limit exceeded at {datetime.datetime.now().isoformat()}: {error_message}")
            else:
                # For other errors, re-raise
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
        total_pdfs = len(pdf_files)
        successful = 0
        failed = 0
        rate_limited = 0
        
        # Create a progress bar
        with tqdm(total=total_pdfs, desc="Processing PDFs") as pbar:
            for i, pdf_path in enumerate(pdf_files):
                try:
                    # Display current rate limits
                    usage = self.rate_limiter.get_current_usage()
                    rpm_usage = f"{usage['requests_in_last_minute']}/{self.rate_limiter.requests_per_minute} RPM"
                    rpd_usage = f"{usage['requests_in_last_day']}/{self.rate_limiter.requests_per_day} RPD"
                    logger.info(f"Rate limit status: {rpm_usage}, {rpd_usage}")
                    
                    # Update progress bar description
                    pbar.set_description(f"Processing PDFs [{i+1}/{total_pdfs}] (S:{successful} F:{failed} R:{rate_limited})")
                    
                    # Process the PDF
                    structured_data = self.process_pdf(pdf_path, use_file_api=use_file_api)
                    
                    # Add the PDF path to the result
                    structured_data["pdf_path"] = pdf_path
                    
                    # Add to results
                    results.append(structured_data)
                    
                    # Log success
                    logger.info(f"Successfully processed: {pdf_path}")
                    successful += 1
                    
                except RateLimitError as e:
                    logger.warning(f"Rate limit error processing {pdf_path}: {str(e)}")
                    results.append({
                        "error": f"Rate limit error: {str(e)}",
                        "pdf_path": pdf_path
                    })
                    rate_limited += 1
                    
                    # Wait longer when we hit rate limits
                    wait_time = random.uniform(30, 60)
                    logger.info(f"Waiting {wait_time:.1f}s after rate limit error")
                    time.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"Error processing {pdf_path}: {str(e)}")
                    results.append({
                        "error": str(e),
                        "pdf_path": pdf_path
                    })
                    failed += 1
                
                # Update progress bar
                pbar.update(1)
        
        # Log final statistics
        logger.info(f"Batch processing complete. Total: {total_pdfs}, Success: {successful}, Failed: {failed}, Rate Limited: {rate_limited}")
        return results 