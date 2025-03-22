#!/usr/bin/env python3
"""
Recategorize Unknown Entries Using LLM

This module improves data quality by recategorizing entries that remain as 'Unknown'
after regex-based categorization, using Google's Gemini API to analyze the entries.
"""

import sqlite3
import logging
import argparse
import json
import os
import time
import google.generativeai as genai
from typing import Dict, List, Tuple, Optional, Any
from db_handler import DatabaseHandler, Categories, Subcategories, TemporalTypes
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LLMRecategorizer:
    """A class for recategorizing unknown entries using Google's Gemini API."""
    
    def __init__(self, db_path: str):
        """
        Initialize the LLM recategorizer.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.db = DatabaseHandler(db_path=db_path)
        self.api_key = os.getenv("GOOGLE_API_KEY")
        
        if not self.api_key:
            logger.warning("No Google API key found. Set GOOGLE_API_KEY environment variable.")
        else:
            # Configure the Gemini API
            genai.configure(api_key=self.api_key)
            
            # Get the Gemini model
            self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def recategorize_with_llm(self, batch_size: int = 50, max_entries: int = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Recategorize unknown entries using Gemini.
        
        Args:
            batch_size: Number of entries to process in each batch
            max_entries: Maximum number of entries to process (None for all)
            dry_run: If True, only print changes without applying them
            
        Returns:
            Statistics about the recategorization
        """
        if not self.api_key:
            logger.error("Cannot proceed without a Google API key.")
            return {
                "error": "No API key",
                "recategorized": 0,
                "total": 0
            }
        
        # Get connection to the database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Fetch all remaining unknown entries
        cursor.execute("""
            SELECT id, item, details, sub_category
            FROM disclosures
            WHERE category = ?
        """, (Categories.UNKNOWN,))
        
        unknown_entries = cursor.fetchall()
        logger.info(f"Found {len(unknown_entries)} remaining unknown entries to process")
        
        # Apply max_entries limit if specified
        if max_entries is not None and max_entries < len(unknown_entries):
            unknown_entries = unknown_entries[:max_entries]
            logger.info(f"Limited processing to {max_entries} entries")
        
        # Statistics for reporting
        stats = {
            'total': len(unknown_entries),
            'recategorized': 0,
            'by_category': {},
            'by_subcategory': {},
            'skipped': 0,
            'errors': 0,
            'samples': {
                'recategorized': [],
            }
        }
        
        # Dynamically adjust the batch size for large sets
        effective_batch_size = min(batch_size, 20) if len(unknown_entries) > 50 else batch_size
        logger.info(f"Using batch size of {effective_batch_size} entries")
        
        # Process entries in batches
        for i in range(0, len(unknown_entries), effective_batch_size):
            batch = unknown_entries[i:i+effective_batch_size]
            batch_num = i//effective_batch_size + 1
            total_batches = (len(unknown_entries) + effective_batch_size - 1)//effective_batch_size
            logger.info(f"Processing batch {batch_num}/{total_batches}")
            
            batch_start_time = time.time()
            batch_stats = {
                'processed': 0,
                'recategorized': 0,
                'skipped': 0,
                'errors': 0
            }
            
            try:
                # Create batch for LLM processing
                batch_data = []
                for entry_id, item, details, sub_category in batch:
                    # Skip empty entries
                    if not item or item.lower() in ["n/a", "none", "nil", "unknown"] and not details:
                        stats['skipped'] += 1
                        batch_stats['skipped'] += 1
                        continue
                    
                    batch_data.append({
                        "id": entry_id,
                        "item": item,
                        "details": details if details else "",
                    })
                
                if not batch_data:
                    continue
                
                # Get categorizations from LLM
                categorizations = self._get_llm_categorizations(batch_data)
                
                # Apply categorizations
                for result in categorizations:
                    batch_stats['processed'] += 1
                    
                    entry_id = result.get("id")
                    new_category = result.get("category")
                    new_subcategory = result.get("subcategory")
                    new_temporal_type = result.get("temporal_type")
                    
                    # Validate category
                    if new_category not in Categories.ALL:
                        logger.warning(f"Invalid category '{new_category}' received from LLM")
                        new_category = Categories.UNKNOWN
                    
                    # Validate temporal_type
                    if new_temporal_type not in TemporalTypes.ALL:
                        logger.warning(f"Invalid temporal_type '{new_temporal_type}' received from LLM")
                        # Assign default temporal_type based on category
                        if new_category == Categories.ASSET or new_category == Categories.MEMBERSHIP:
                            new_temporal_type = TemporalTypes.ONGOING
                        elif new_category == Categories.INCOME:
                            new_temporal_type = TemporalTypes.RECURRING
                        else:
                            new_temporal_type = TemporalTypes.ONE_TIME
                    
                    # Update database
                    if new_category != Categories.UNKNOWN and not dry_run:
                        cursor.execute("""
                            UPDATE disclosures
                            SET category = ?, sub_category = ?, temporal_type = ?
                            WHERE id = ?
                        """, (new_category, new_subcategory, new_temporal_type, entry_id))
                    
                    # Update statistics
                    if new_category != Categories.UNKNOWN:
                        stats['recategorized'] += 1
                        batch_stats['recategorized'] += 1
                        stats['by_category'][new_category] = stats['by_category'].get(new_category, 0) + 1
                        cat_subcat_key = f"{new_category}:{new_subcategory}"
                        stats['by_subcategory'][cat_subcat_key] = stats['by_subcategory'].get(cat_subcat_key, 0) + 1
                        
                        # Store some sample recategorizations for review
                        if len(stats['samples']['recategorized']) < 10:
                            item_detail = next((e[1], e[2]) for e in batch if e[0] == entry_id)
                            stats['samples']['recategorized'].append({
                                'item': item_detail[0],
                                'details': item_detail[1],
                                'new_category': new_category,
                                'new_subcategory': new_subcategory
                            })
                
                # Commit changes for this batch
                if not dry_run:
                    conn.commit()
                
                batch_time = time.time() - batch_start_time
                logger.info(f"Batch {batch_num}/{total_batches} completed in {batch_time:.1f}s: {batch_stats['processed']} processed, {batch_stats['recategorized']} recategorized ({batch_stats['recategorized']/len(batch)*100:.1f}% success rate)")
                
                # Add a small delay to avoid API rate limits
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {str(e)}")
                stats['errors'] += 1
                batch_stats['errors'] += 1
                # Wait a bit longer if we hit an error
                time.sleep(3)
        
        if not dry_run:
            conn.commit()
        conn.close()
        
        # Report results
        self._report_results(stats, dry_run)
        return stats
    
    def _get_llm_categorizations(self, entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Get categorizations from the Gemini API.
        
        Args:
            entries: List of entries to categorize
            
        Returns:
            List of categorization results
        """
        # Prepare the prompt for the LLM
        prompt = self._create_categorization_prompt(entries)
        
        try:
            # Call Gemini API
            generation_config = {
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Log the first 100 chars of the response for debugging
            llm_response = response.text
            if llm_response is None:
                logger.error("Received empty response from Gemini API")
                return []
                
            logger.debug(f"LLM response preview: {llm_response[:100]}...")
            
            # Extract JSON data from response
            results = self._extract_json_from_response(llm_response, entries)
            
            # Log all results to see raw categorizations
            logger.info(f"Raw categorizations from Gemini (before filtering):")
            for i, result in enumerate(results, 1):
                entry_id = result.get("id", "unknown")
                category = result.get("category", "not_provided")
                subcategory = result.get("subcategory", "not_provided")
                temporal_type = result.get("temporal_type", "not_provided")
                logger.info(f"  {i}. ID: {entry_id}, Category: {category}, Subcategory: {subcategory}, Temporal: {temporal_type}")
            
            # Clean up subcategory fields if they contain category prefixes
            for result in results:
                if "subcategory" in result and "category" in result:
                    subcategory = result.get("subcategory")
                    category = result.get("category")
                    
                    # Skip if either is None
                    if subcategory is None or category is None:
                        continue
                    
                    # Remove the category prefix if it exists
                    prefix = f"{category} > "
                    if subcategory.startswith(prefix):
                        result["subcategory"] = subcategory[len(prefix):]
                        logger.debug(f"Cleaned up subcategory from '{subcategory}' to '{result['subcategory']}'")
            
            return results
            
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}")
            raise
            
    def _extract_json_from_response(self, llm_response: str, entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Extract JSON data from the LLM response.
        
        Args:
            llm_response: The text response from the LLM
            entries: The original entries being categorized (for context)
            
        Returns:
            List of categorization results
        """
        try:
            # Try to parse the response directly first
            response_data = json.loads(llm_response)
            logger.debug("Successfully parsed LLM response as standard JSON")
            
            # Check if it's a JSON object with a 'results' or 'categorizations' key
            if isinstance(response_data, dict):
                if 'results' in response_data:
                    return response_data['results']
                elif 'categorizations' in response_data:
                    return response_data['categorizations']
                elif 'entries' in response_data:
                    return response_data['entries']
                
                # If it's a JSON object but none of the expected keys are present,
                # check if it matches our expected format (array of objects with id, category, etc.)
                if len(entries) == 1 and 'id' in response_data and 'category' in response_data:
                    # Single entry response
                    return [response_data]
            
            # If it's already an array, return it directly
            if isinstance(response_data, list):
                return response_data
            
            # If we get here, the response format wasn't what we expected
            logger.warning(f"Unexpected JSON format, trying to extract array from: {llm_response[:200]}...")
            
        except json.JSONDecodeError:
            logger.warning(f"Standard JSON parsing failed, attempting alternative extraction methods...")
        
        # Try alternative extraction methods
        try:
            # Check for JSON array in a code block
            if "```json" in llm_response:
                # Extract JSON from code block
                start_idx = llm_response.find("```json") + 7
                end_idx = llm_response.rfind("```")
                if start_idx >= 7 and end_idx > start_idx:
                    json_str = llm_response[start_idx:end_idx].strip()
                    
                    # Try to repair incomplete JSON - look for last complete object
                    try:
                        result = json.loads(json_str)
                        logger.info(f"Successfully extracted JSON from code block with {len(result) if isinstance(result, list) else 1} items")
                        return result
                    except json.JSONDecodeError as e:
                        # If error is about the end of the JSON, try to find last complete object
                        if "Extra data" in str(e) or "Expecting" in str(e):
                            # Find position of last complete object
                            last_obj_end = json_str.rfind("}")
                            if last_obj_end > 0:
                                # Find the beginning of the array
                                array_start = json_str.find("[")
                                if array_start >= 0 and array_start < last_obj_end:
                                    # Find last complete object (find matching bracket)
                                    bracket_count = 0
                                    in_string = False
                                    escape_next = False
                                    last_complete_pos = -1
                                    
                                    for i, char in enumerate(json_str[array_start:last_obj_end+1]):
                                        pos = array_start + i
                                        if escape_next:
                                            escape_next = False
                                            continue
                                            
                                        if char == '\\' and not escape_next:
                                            escape_next = True
                                        elif char == '"' and not escape_next:
                                            in_string = not in_string
                                        elif not in_string:
                                            if char == '{':
                                                bracket_count += 1
                                            elif char == '}':
                                                bracket_count -= 1
                                                if bracket_count == 0 and json_str[array_start:pos+1].count('{') > 0:
                                                    last_complete_pos = pos
                                    
                                    if last_complete_pos > 0:
                                        # Try parsing up to last complete object plus closing array bracket
                                        truncated_json = json_str[array_start:last_complete_pos+1] + "]"
                                        result = json.loads(truncated_json)
                                        logger.info(f"Successfully parsed truncated JSON with {len(result)} items")
                                        return result
                        
                        # If we got here, our repair attempt failed
                        raise
            
            # Try markdown code block format
            elif "```" in llm_response:
                start_idx = llm_response.find("```") + 3
                end_idx = llm_response.rfind("```")
                if start_idx >= 3 and end_idx > start_idx:
                    # Skip language identifier if present
                    if start_idx < end_idx and llm_response[start_idx] == '\n':
                        start_idx += 1
                    json_str = llm_response[start_idx:end_idx].strip()
                    
                    # Try to repair incomplete JSON
                    try:
                        result = json.loads(json_str)
                        logger.info(f"Successfully extracted JSON from markdown code block with {len(result) if isinstance(result, list) else 1} items")
                        return result
                    except json.JSONDecodeError as e:
                        # Similar repair logic as above
                        if "Extra data" in str(e) or "Expecting" in str(e):
                            last_obj_end = json_str.rfind("}")
                            array_start = json_str.find("[")
                            if last_obj_end > 0 and array_start >= 0 and array_start < last_obj_end:
                                truncated_json = json_str[array_start:last_obj_end+1] + "]"
                                result = json.loads(truncated_json)
                                logger.info(f"Successfully parsed truncated markdown JSON with {len(result)} items")
                                return result
                        raise
            
            # Try to find JSON array directly
            start_idx = llm_response.find('[')
            end_idx = llm_response.rfind(']') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = llm_response[start_idx:end_idx]
                try:
                    result = json.loads(json_str)
                    logger.info(f"Successfully extracted direct JSON array with {len(result)} items")
                    return result
                except json.JSONDecodeError as e:
                    # Similar repair logic for direct arrays
                    if "Extra data" in str(e) or "Expecting" in str(e):
                        last_obj_end = json_str.rfind("}")
                        if last_obj_end > 0:
                            truncated_json = json_str[:last_obj_end+1] + "]"
                            result = json.loads(truncated_json)
                            logger.info(f"Successfully parsed truncated direct JSON with {len(result)} items")
                            return result
                    raise
                
            # Try to find JSON object directly
            start_idx = llm_response.find('{')
            end_idx = llm_response.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = llm_response[start_idx:end_idx]
                data = json.loads(json_str)
                logger.info(f"Successfully extracted JSON object")
                
                # Process the data similar to above
                if isinstance(data, dict):
                    if any(k in data for k in ['results', 'categorizations', 'entries']):
                        key = next(k for k in ['results', 'categorizations', 'entries'] if k in data)
                        return data[key]
                    
                    # If it looks like a single entry response
                    if len(entries) == 1 and 'id' in data and 'category' in data:
                        return [data]
            
            # If we got here, we couldn't find valid JSON
            logger.error(f"All JSON extraction methods failed. Full response: {llm_response}")
            
            # As a last resort, try to manually construct results from the response
            if "id" in llm_response and "category" in llm_response:
                # Try to parse each individual entry
                results = []
                for entry in entries:
                    entry_id = entry["id"]
                    # Find this ID in the response
                    id_start = llm_response.find(f'"id": "{entry_id}"')
                    if id_start > 0:
                        # Find the object containing this ID
                        obj_start = llm_response.rfind("{", 0, id_start)
                        obj_end = llm_response.find("}", id_start)
                        if obj_start >= 0 and obj_end > 0:
                            # Extract the category, subcategory, and temporal_type
                            category_match = re.search(r'"category":\s*"([^"]+)"', llm_response[id_start:obj_end])
                            subcategory_match = re.search(r'"subcategory":\s*"([^"]+)"', llm_response[id_start:obj_end])
                            temporal_match = re.search(r'"temporal_type":\s*"([^"]+)"', llm_response[id_start:obj_end])
                            
                            if category_match:
                                result = {
                                    "id": entry_id,
                                    "category": category_match.group(1),
                                    "subcategory": subcategory_match.group(1) if subcategory_match else None,
                                    "temporal_type": temporal_match.group(1) if temporal_match else "one-time"
                                }
                                results.append(result)
                
                if results:
                    logger.info(f"Successfully manually extracted {len(results)} results from malformed JSON using regex")
                    return results
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to extract JSON from response: {str(e)}")
            logger.error(f"Full response: {llm_response}")
            
        # Return empty list as fallback
        logger.error(f"Could not parse LLM response, returning empty list")
        return []
    
    def _create_categorization_prompt(self, entries: List[Dict[str, str]]) -> str:
        """
        Create a prompt for the LLM to categorize entries.
        
        Args:
            entries: List of entries to categorize
            
        Returns:
            Prompt string for the LLM
        """
        categories_info = """
Valid categories:
- Asset: Physical or financial assets owned by the MP
- Income: Sources of income for the MP
- Gift: Items or benefits given to the MP
- Travel: Travel benefits or expenses
- Liability: Debts or financial obligations
- Membership: Memberships in organizations
- Unknown: Only use this if you really cannot determine the category

Valid subcategories:
For Asset:
- Real Estate: Properties, homes, apartments
- Shares: Company shares, stocks, investments
- Trust: Trust funds or beneficiary positions
- Other Asset: Other assets not in the above categories

For Income:
- Salary: Primary employment income
- Dividend: Income from investments
- Other Income: Other income sources

For Membership:
- Professional: Professional associations, airline lounges
- Other Membership: Other types of membership

For Gift:
- Hospitality: Food, drink, entertainment events
- Entertainment: Tickets to events, performances
- Travel Gift: Travel benefits given as gifts
- Decorative: Artwork, ornaments, commemorative items
- Electronics: Electronic devices
- Other Gift: Other types of gifts

For Travel:
- Air Travel: Flights, air travel
- Other Travel: Other travel benefits

For Liability:
- Mortgage: Home loans
- Loan: Other loans
- Credit: Credit cards, lines of credit
- Other Liability: Other liabilities

Temporal types (IMPORTANT - use EXACTLY one of these strings):
- "one-time": Single occurrences (e.g., a gift)
- "recurring": Repeats periodically (e.g., dividend payment)
- "ongoing": Continues indefinitely (e.g., share ownership)
"""
        
        entries_json = json.dumps(entries, indent=2)
        
        return f"""
I need you to categorize the following political disclosure entries. These are items that politicians have declared as part of their required disclosures.

{categories_info}

Here are the entries to categorize:
{entries_json}

For each entry, analyze the "item" and "details" fields to determine the most appropriate category, subcategory, and temporal type.

Your response format must be a JSON array like this:
[
  {{
    "id": "entry_id",
    "category": "chosen_category",
    "subcategory": "chosen_subcategory", 
    "temporal_type": "one-time" | "recurring" | "ongoing"
  }},
  ...
]

IMPORTANT:
1. For temporal_type, use EXACTLY one of: "one-time", "recurring", or "ongoing"
2. For subcategory, use ONLY the subcategory name WITHOUT the category prefix
3. The response must be valid JSON that can be parsed with standard JSON tools
4. Do NOT include any other text or explanations, ONLY the JSON array

Respond ONLY with the JSON array, nothing else before or after.
"""
    
    def _report_results(self, stats: Dict[str, Any], dry_run: bool) -> None:
        """
        Report the results of the recategorization.
        
        Args:
            stats: Statistics about the recategorization
            dry_run: Whether this was a dry run
        """
        mode = "DRY RUN - " if dry_run else ""
        logger.info(f"\n{mode}LLM Recategorization Results:")
        logger.info(f"Total entries processed: {stats['total']}")
        logger.info(f"Entries recategorized: {stats['recategorized']} ({stats['recategorized']/stats['total']*100:.1f}% if stats['total'] else 0)")
        logger.info(f"Entries skipped: {stats['skipped']}")
        logger.info(f"Errors: {stats['errors']}")
        
        if stats['by_category']:
            logger.info("\nRecategorized by category:")
            for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  - {category}: {count} entries ({count/stats['recategorized']*100:.1f}% if stats['recategorized'] else 0)")
        
        if stats['by_subcategory']:
            logger.info("\nRecategorized by subcategory:")
            for cat_subcat, count in sorted(stats['by_subcategory'].items(), key=lambda x: x[1], reverse=True)[:10]:
                category, subcategory = cat_subcat.split(':')
                # Remove redundant category prefix from subcategory if present
                if subcategory.startswith(f"{category} > "):
                    subcategory = subcategory[len(f"{category} > "):]
                logger.info(f"  - {category} > {subcategory}: {count} entries")
        
        # Print sample recategorizations
        if stats['samples']['recategorized']:
            logger.info("\nSample Recategorizations:")
            for i, sample in enumerate(stats['samples']['recategorized'], 1):
                # Clean up subcategory display
                subcategory = sample['new_subcategory']
                if subcategory.startswith(f"{sample['new_category']} > "):
                    subcategory = subcategory[len(f"{sample['new_category']} > "):]
                logger.info(f"  {i}. '{sample['item']}' ({sample['details'][:30]}...) → {sample['new_category']} > {subcategory}")

def main():
    """Main function to parse arguments and run the LLM recategorization."""
    parser = argparse.ArgumentParser(description="Recategorize unknown entries using Gemini API")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database file")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of entries to process in each batch")
    parser.add_argument("--max-entries", type=int, help="Maximum number of entries to process")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without applying them")
    
    args = parser.parse_args()
    
    logger.info(f"Starting LLM recategorization for database: {args.db_path}")
    
    recategorizer = LLMRecategorizer(args.db_path)
    stats = recategorizer.recategorize_with_llm(
        batch_size=args.batch_size,
        max_entries=args.max_entries,
        dry_run=args.dry_run
    )
    
    if args.dry_run:
        logger.info("\nTo apply these changes, run without the --dry-run flag")
    
    logger.info("Done!")

if __name__ == "__main__":
    main() 