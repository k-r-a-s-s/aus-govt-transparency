#!/usr/bin/env python3
"""
Extract meaningful item values from disclosure details using Google Gemini API.

This script:
1. Reads disclosures from the database
2. Uses Gemini to extract meaningful item values from the details
3. Updates the database with the extracted item values
"""

import os
import json
import sqlite3
import logging
import time
from typing import List, Dict, Any, Optional
import argparse
from dotenv import load_dotenv
import google.generativeai as genai
from tqdm import tqdm
import copy
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from multiple possible locations
for env_file in ['.env', '.env.local']:
    if os.path.exists(env_file):
        load_dotenv(env_file)
        logger.info(f"Loaded environment from {env_file}")

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
        
        # Track request timestamps using lists with timestamps
        self.minute_window = []
        self.day_window = []
        
        # Track successful requests and failures
        self.total_successful_requests = 0
        self.total_rate_limit_errors = 0
        
        logger.info(f"Rate limiter initialized with {requests_per_minute} RPM and {requests_per_day} RPD")
    
    def _cleanup_windows(self):
        """Clean up expired timestamps from the windows"""
        current_time = time.time()
        
        # Clean up minute window
        self.minute_window = [t for t in self.minute_window if (current_time - t) <= 60]
        
        # Clean up day window
        self.day_window = [t for t in self.day_window if (current_time - t) <= 86400]
    
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
    
    def wait_if_needed(self):
        """Wait if necessary to avoid exceeding rate limits"""
        while not self.check_rate_limits():
            # Check which limit is causing the wait
            current_rpm = len(self.minute_window)
            current_rpd = len(self.day_window)
            
            if current_rpm >= self.requests_per_minute:
                # Calculate time until oldest request expires from minute window
                sleep_time = 60 - (time.time() - min(self.minute_window)) + 0.1  # Add a small buffer
                logger.warning(f"Rate limit approaching: {current_rpm}/{self.requests_per_minute} RPM. Waiting {sleep_time:.2f}s")
                time.sleep(max(1, min(sleep_time, 30)))  # Cap waiting time between 1-30 seconds
            elif current_rpd >= self.requests_per_day:
                # Daily limit reached, calculate time until oldest request expires
                sleep_time = 86400 - (time.time() - min(self.day_window)) + 0.1
                logger.warning(f"Daily rate limit reached: {current_rpd}/{self.requests_per_day} RPD. Long wait required: {sleep_time/60:.1f} minutes")
                # For daily limits, we might want to terminate rather than wait a very long time
                raise Exception(f"Daily rate limit of {self.requests_per_day} requests reached. Try again tomorrow.")
            else:
                # Add a small delay as a fallback
                logger.info("Rate limits approaching, adding small delay")
                time.sleep(2)
            
            # Recheck the windows after waiting
            self._cleanup_windows()

class ItemExtractor:
    """
    A class to extract meaningful item values from disclosure details using Gemini API.
    """
    
    def __init__(self, db_path: str, batch_size: int = 200, dry_run: bool = False):
        """
        Initialize the item extractor.
        
        Args:
            db_path: Path to the SQLite database
            batch_size: Number of disclosures to process in a batch
            dry_run: If True, don't actually update the database
        """
        self.db_path = db_path
        self.batch_size = batch_size
        self.dry_run = dry_run
        
        # Get API key from environment
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable in .env or .env.local file.")
        
        # Configure Gemini API
        genai.configure(api_key=self.api_key)
        
        # Get Gemini model
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(requests_per_minute=15, requests_per_day=1500)
        
        # Create database connection
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        logger.info(f"Item extractor initialized with batch size {batch_size} and dry_run={dry_run}")
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
    
    def get_total_disclosures(self) -> int:
        """
        Get the total number of disclosures in the database.
        
        Returns:
            Total number of disclosures
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM disclosures")
        result = cursor.fetchone()[0]
        cursor.close()
        return result
    
    def get_disclosures_batch(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        """
        Get a batch of disclosures from the database.
        
        Args:
            offset: Offset to start from
            limit: Maximum number of rows to return
            
        Returns:
            List of disclosures as dictionaries
        """
        cursor = self.conn.cursor()
        query = """
        SELECT id, mp_name, category, entity, details
        FROM disclosures
        LIMIT ? OFFSET ?
        """
        cursor.execute(query, (limit, offset))
        
        # Convert rows to dictionaries
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "mp_name": row["mp_name"],
                "category": row["category"],
                "entity": row["entity"],
                "details": row["details"]
            })
        
        cursor.close()
        return results
    
    def get_disclosures_by_category(self, category: str, limit: int, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get a batch of disclosures by category.
        
        Args:
            category: Category to filter by
            limit: Maximum number of rows to return
            offset: Offset to start from
            
        Returns:
            List of disclosures as dictionaries
        """
        cursor = self.conn.cursor()
        query = """
        SELECT id, mp_name, category, entity, details
        FROM disclosures
        WHERE category = ?
        LIMIT ? OFFSET ?
        """
        cursor.execute(query, (category, limit, offset))
        
        # Convert rows to dictionaries
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "mp_name": row["mp_name"],
                "category": row["category"],
                "entity": row["entity"],
                "details": row["details"]
            })
        
        cursor.close()
        return results
    
    def update_items(self, item_updates: List[Dict[str, Any]]):
        """
        Update the item field for multiple disclosures.
        
        Args:
            item_updates: List of dictionaries with id and item fields
        """
        if self.dry_run:
            logger.info(f"DRY RUN: Would update {len(item_updates)} items")
            return
        
        cursor = self.conn.cursor()
        
        # Use a transaction for better performance
        cursor.execute("BEGIN TRANSACTION")
        
        try:
            for update in item_updates:
                cursor.execute(
                    "UPDATE disclosures SET item = ? WHERE id = ?",
                    (update["item"], update["id"])
                )
            
            # Commit the transaction
            cursor.execute("COMMIT")
            logger.info(f"Updated {len(item_updates)} items in the database")
        
        except Exception as e:
            # Rollback in case of error
            cursor.execute("ROLLBACK")
            logger.error(f"Error updating items: {str(e)}")
            raise
        
        finally:
            cursor.close()
    
    def extract_items(self, disclosures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract meaningful item values from disclosure details using Gemini.
        
        Args:
            disclosures: List of disclosures
            
        Returns:
            List of dictionaries with id and extracted item
        """
        # Wait for rate limiting if needed
        self.rate_limiter.wait_if_needed()
        
        # Create prompt for Gemini
        prompt = self._create_extraction_prompt(disclosures)
        
        try:
            # Call Gemini API
            response = self.model.generate_content(prompt)
            
            # Record successful request
            self.rate_limiter.record_request()
            
            # Get text response directly
            response_text = response.text
            
            # Print a sample of the response for debugging
            logger.debug(f"Response text sample: {response_text[:200]}...")
            
            # Parse the response to extract the JSON
            extracted_items = self._parse_response(response_text)
            
            # Log info on what we got
            logger.info(f"Extracted {len(extracted_items)} item values from {len(disclosures)} disclosures")
            
            return extracted_items
            
        except Exception as e:
            logger.error(f"Error extracting items: {str(e)}")
            
            # If rate limited, wait and return empty list
            if "rate limit" in str(e).lower() or "quota" in str(e).lower():
                self.rate_limiter.record_rate_limit_error()
                logger.warning("Rate limit exceeded. Waiting before retrying...")
                time.sleep(60)  # Wait a minute before retrying
            
            return []
    
    def _create_extraction_prompt(self, disclosures: List[Dict[str, Any]]) -> str:
        """
        Create a prompt for Gemini to extract item values.
        
        Args:
            disclosures: List of disclosures
            
        Returns:
            Prompt string
        """
        # Create JSON string of disclosures for the prompt
        disclosures_json = json.dumps(disclosures, indent=2)
        
        return f"""
Extract meaningful and specific item descriptions from parliamentary disclosures.

For each disclosure, extract an item value that is distinct from the entity and provides useful information about what the disclosure represents.

Follow these guidelines for different categories:

1. GIFT entries:
   - Extract the specific gift item (e.g., "Silver tea set", "Ceremonial sword", "Signed book")
   - Include brief distinguishing features when available

2. ASSET-PROPERTY entries:
   - Use specific property types: "Residential House", "Investment Apartment", "Vacation Home", "Rural Land", "Farm", "Commercial Property"
   - Include location context if available (e.g., "Sydney Apartment")

3. ASSET-SHARES entries:
   - Use "Shares" as the base item
   - Add company type if available (e.g., "Mining Shares", "Bank Shares")

4. ASSET-OTHER entries:
   - Be as specific as possible (e.g., "Vintage Car", "Art Collection", "Jewelry")

5. INCOME entries:
   - Specify type: "Salary", "Consulting Fee", "Pension", "Rental Income", "Dividends"

6. LIABILITY entries:
   - Specify type: "Mortgage", "Personal Loan", "Credit Card", "Investment Loan"

FORMAT YOUR RESPONSE AS A JSON ARRAY WITH OBJECTS CONTAINING id AND item FIELDS ONLY.

EXAMPLE INPUT:
[
  {{
    "id": 123,
    "category": "Gift",
    "entity": "President of Indonesia",
    "details": "Silver tea set from the President of Indonesia. I have surrendered this gift to the Department of Prime Minister and Cabinet."
  }},
  {{
    "id": 124,
    "category": "Asset",
    "entity": "N/A",
    "details": "Residential property in Sydney, NSW owned jointly with spouse."
  }},
  {{
    "id": 125,
    "category": "Asset",
    "entity": "Commonwealth Bank of Australia",
    "details": "Shareholding in Commonwealth Bank of Australia (CBA)"
  }},
  {{
    "id": 126,
    "category": "Income",
    "entity": "University of Sydney",
    "details": "Part-time lecturing position at the University of Sydney, Faculty of Law"
  }},
  {{
    "id": 127,
    "category": "Liability",
    "entity": "Westpac",
    "details": "Mortgage on investment property in Brisbane, QLD with Westpac Banking Corporation"
  }}
]

EXAMPLE OUTPUT:
[
  {{
    "id": 123,
    "item": "Silver tea set"
  }},
  {{
    "id": 124,
    "item": "Residential House in Sydney"
  }},
  {{
    "id": 125,
    "item": "Bank Shares"
  }},
  {{
    "id": 126,
    "item": "Lecturing Position"
  }},
  {{
    "id": 127,
    "item": "Investment Property Mortgage"
  }}
]

Now, extract items for the following disclosures:
{disclosures_json}
"""
    
    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse the response from Gemini to extract the JSON.
        
        Args:
            response_text: Response from Gemini
            
        Returns:
            List of dictionaries with id and item fields
        """
        try:
            # First try to parse the entire response as JSON
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                pass
                
            # Try to find JSON in code blocks
            json_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', response_text)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
                
            # Try to find any JSON array
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Found JSON-like structure but couldn't parse it: {str(e)}")
                    logger.error(f"JSON string sample: {json_str[:200]}...")
            
            # If we still don't have valid JSON, log the response and return empty list
            logger.error("No valid JSON found in the response")
            logger.error(f"Response text sample: {response_text[:500]}...")
            return []
        except Exception as e:
            logger.error(f"Error parsing response: {str(e)}")
            return []
    
    def get_all_categories(self) -> List[str]:
        """
        Get all unique categories from the database.
        
        Returns:
            List of category strings
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM disclosures")
        categories = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return categories
    
    def count_by_category(self) -> Dict[str, int]:
        """
        Count disclosures by category.
        
        Returns:
            Dictionary mapping category to count
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT category, COUNT(*) FROM disclosures GROUP BY category")
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.close()
        return counts
    
    def process_all(self, limit: Optional[int] = None):
        """
        Process all disclosures in the database by category.
        
        Args:
            limit: Maximum number of entries to process per category
        """
        # Get all categories
        categories = self.get_all_categories()
        category_counts = self.count_by_category()
        
        logger.info(f"Found {len(categories)} categories")
        for category in categories:
            logger.info(f"Category: {category}, Count: {category_counts.get(category, 0)}")
        
        # Process each category in batches
        for category in categories:
            self.process_category(category, limit=limit)
    
    def process_category(self, category: str, limit: Optional[int] = None):
        """
        Process all disclosures in a specific category.
        
        Args:
            category: Category to process
            limit: Maximum number of entries to process
        """
        # Get total count for this category
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM disclosures WHERE category = ?", (category,))
        total_count = cursor.fetchone()[0]
        cursor.close()
        
        # Apply limit if specified
        if limit is not None and limit > 0:
            total_count = min(total_count, limit)
        
        logger.info(f"Processing category '{category}' with {total_count} disclosures")
        
        # Process in batches
        batch_size = self.batch_size
        processed = 0
        
        # Use tqdm for progress bar
        with tqdm(total=total_count, desc=f"Processing {category}") as pbar:
            while processed < total_count:
                # Calculate how many to process in this batch
                to_process = min(batch_size, total_count - processed)
                
                # Get batch of disclosures
                disclosures = self.get_disclosures_by_category(category, to_process, processed)
                
                if not disclosures:
                    logger.warning(f"No disclosures returned for category '{category}' at offset {processed}")
                    break
                
                logger.debug(f"Processing batch of {len(disclosures)} disclosures (offset: {processed})")
                
                # Extract items
                extracted_items = self.extract_items(disclosures)
                
                # Update database
                if extracted_items:
                    # Log a sample of the extracted items
                    sample_size = min(5, len(extracted_items))
                    logger.debug(f"Sample of extracted items: {extracted_items[:sample_size]}")
                    
                    self.update_items(extracted_items)
                
                # Update progress
                processed += len(disclosures)
                pbar.update(len(disclosures))
                
                # Log progress
                logger.info(f"Processed {processed}/{total_count} disclosures for category '{category}'")
                
                # Sleep a bit to avoid API issues
                time.sleep(1)
    
    def fix_ingestion_code(self):
        """
        Modify db_handler.py to correctly populate item field during ingestion.
        This method will print the necessary code changes but won't actually make them.
        """
        # This is just for reference, we'll handle this separately
        print("""
Replace:
item = disclosure.get("entity", "Unknown")

With:
item = extract_item_from_details(
    disclosure.get("category", "Unknown"),
    disclosure.get("subcategory", ""),
    disclosure.get("entity", "Unknown"),
    disclosure.get("details", "")
)
        """)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Extract meaningful item values from disclosure details")
    parser.add_argument("--db", default="disclosures.db", help="Path to the SQLite database")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of disclosures to process in a batch")
    parser.add_argument("--category", help="Process only a specific category")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update the database")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--limit", type=int, help="Limit the number of entries to process")
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    
    # Create extractor
    extractor = ItemExtractor(args.db, args.batch_size, args.dry_run)
    
    try:
        if args.category:
            # Process only the specified category
            extractor.process_category(args.category, limit=args.limit)
        else:
            # Process all categories
            extractor.process_all(limit=args.limit)
    
    finally:
        # Close database connection
        extractor.close()

if __name__ == "__main__":
    main() 