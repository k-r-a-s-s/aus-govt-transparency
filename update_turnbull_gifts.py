#!/usr/bin/env python3
"""
Special script to update Malcolm Turnbull's gift entries with better item descriptions.
This focuses specifically on gifts that were surrendered and need clearer descriptions.
"""

import os
import sqlite3
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TurnbullGiftUpdater:
    """Class to update Malcolm Turnbull's gift entries with better descriptions."""
    
    def __init__(self, db_path: str = "disclosures.db", dry_run: bool = False):
        """Initialize the updater."""
        self.db_path = db_path
        self.dry_run = dry_run
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Initialized TurnbullGiftUpdater with dry_run={dry_run}")
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
    
    def get_turnbull_gifts(self) -> List[Dict[str, Any]]:
        """Get all of Malcolm Turnbull's gift entries."""
        cursor = self.conn.cursor()
        query = """
        SELECT id, mp_name, category, item, entity, details
        FROM disclosures
        WHERE mp_name = 'Malcolm Turnbull' AND category = 'Gift'
        """
        cursor.execute(query)
        
        # Convert rows to dictionaries
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "mp_name": row["mp_name"],
                "category": row["category"],
                "item": row["item"],
                "entity": row["entity"],
                "details": row["details"]
            })
        
        cursor.close()
        logger.info(f"Found {len(results)} gift entries for Malcolm Turnbull")
        return results
    
    def extract_gift_item(self, details: str) -> str:
        """Extract a meaningful gift item from the details."""
        # If empty or None
        if not details:
            return "Gift"
        
        # Remove ADDITION/DELETION markers
        details = re.sub(r'-\s*(ADDITION|DELETION)\s*$', '', details).strip()
        
        # Common patterns in Malcolm Turnbull's gift entries
        gift_patterns = [
            # Numbered items with description (very common pattern)
            r"Item\s*\d+\.?\s*([^\.]+?)(?:from|valued at|I have|\.|$)",
            r"Item:?\s*([^\.]+?)(?:from|valued at|I have|\.|$)",
            
            # Look for specific surrendered gifts
            r"(?:I have )?surrendered (?:this )?gift[^:]*:?\s*([^\.]+?)(?:to|valued at|\.|$)",
            r"([^\.]+)\s*Surrendered Gift",
            
            # Look for artwork, paintings, etc.
            r"((?:artwork|painting|canvas).+?)(?:by|valued at|\.|$)",
            r"((?:Indigenous|aboriginal)\s+artwork.+?)(?:by|valued at|title|\.|$)",
            r"(?:artwork|painting)?\s*by\s+([^,\.]+).+?[,\.]",
            
            # Look for specific items
            r"((?:bowl|frame|vase|book|cigars|token|crystal|tickets|jersey).+?)(?:from|by|valued at|\.|$)",
            
            # Hospitality items
            r"Hospitality:?\s*([^\.]+)"
        ]
        
        for pattern in gift_patterns:
            match = re.search(pattern, details, re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                # Remove any trailing punctuation or "from" phrases
                extracted = re.sub(r'[,;.]$', '', extracted)
                extracted = re.sub(r'\s+from\s+.*$', '', extracted, flags=re.IGNORECASE)
                # Remove "Item X" or "Item:" prefixes
                extracted = re.sub(r'^Item\s*\d*\.?:?\s*', '', extracted, flags=re.IGNORECASE)
                # Cap length and ensure it's meaningful
                if len(extracted) > 5:  # Make sure we have something substantial
                    return extracted[:100].strip()  # Limit to reasonable length
        
        # Special case for tickets
        if "ticket" in details.lower():
            ticket_match = re.search(r'tickets?\s+(?:to|for)\s+([^\.]+)', details, flags=re.IGNORECASE)
            if ticket_match:
                return f"Tickets to {ticket_match.group(1).strip()}"
        
        # If we get here, try to extract anything from between entity-like phrases
        parts = re.split(r'from|\bby\b|valued at', details, flags=re.IGNORECASE)
        if len(parts) > 1 and len(parts[0].strip()) > 5:
            clean_part = re.sub(r'^Item\s*\d*\.?:?\s*', '', parts[0], flags=re.IGNORECASE)
            return clean_part.strip()[:100]
        
        # Default fallback
        return "Gift"
    
    def update_items(self, updates: List[Dict[str, Any]]) -> int:
        """Update item values in the database."""
        if self.dry_run:
            logger.info(f"DRY RUN: Would update {len(updates)} items")
            return 0
        
        cursor = self.conn.cursor()
        updated_count = 0
        
        try:
            # Use a transaction for better performance
            cursor.execute("BEGIN TRANSACTION")
            
            for update in updates:
                cursor.execute(
                    "UPDATE disclosures SET item = ? WHERE id = ?",
                    (update["new_item"], update["id"])
                )
                updated_count += cursor.rowcount
            
            # Commit the transaction
            cursor.execute("COMMIT")
            logger.info(f"Updated {updated_count} items in the database")
            
        except Exception as e:
            # Rollback in case of error
            cursor.execute("ROLLBACK")
            logger.error(f"Error updating items: {str(e)}")
            raise
        
        finally:
            cursor.close()
        
        return updated_count
    
    def process_gifts(self) -> int:
        """Process all of Malcolm Turnbull's gift entries and update items."""
        # Get all gift entries
        gifts = self.get_turnbull_gifts()
        
        # Prepare updates
        updates = []
        for gift in gifts:
            current_item = gift["item"]
            
            # Skip if the item is already descriptive (not just the entity)
            if current_item != gift["entity"] and current_item not in ["N/A", "Unknown", "Gift"]:
                # Check if the current item is long and has poor formatting (like the AFL entry)
                if len(current_item) > 40 or "Item" in current_item:
                    # We'll try to improve it
                    pass
                else:
                    # Otherwise, it's probably good enough
                    continue
            
            # Extract a better item description
            new_item = self.extract_gift_item(gift["details"])
            
            # Add to updates if different
            if new_item != current_item:
                updates.append({
                    "id": gift["id"],
                    "old_item": current_item,
                    "new_item": new_item
                })
        
        logger.info(f"Found {len(updates)} gift entries that need updating")
        
        # Show sample updates
        if updates:
            sample_size = min(5, len(updates))
            logger.info(f"Sample of {sample_size} updates:")
            for i in range(sample_size):
                logger.info(f"  {updates[i]['old_item']} -> {updates[i]['new_item']}")
        
        # Update items in the database
        updated_count = self.update_items(updates)
        return updated_count

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Update Malcolm Turnbull's gift entries with better item descriptions")
    parser.add_argument("--db", default="disclosures.db", help="Path to the SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update the database")
    args = parser.parse_args()
    
    updater = TurnbullGiftUpdater(args.db, args.dry_run)
    
    try:
        updated_count = updater.process_gifts()
        logger.info(f"Successfully updated {updated_count} gift entries")
    
    finally:
        updater.close()

if __name__ == "__main__":
    main() 