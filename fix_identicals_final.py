#!/usr/bin/env python3
"""
Final script to fix the remaining entries where item and entity values are identical.
This uses a more direct approach with hardcoded fixes for specific patterns.
"""

import sqlite3
import logging
import re
from typing import List, Dict, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FinalItemFixer:
    """Class to handle the final fixes for entries with identical item and entity values."""
    
    def __init__(self, db_path: str = "disclosures.db", dry_run: bool = False):
        """Initialize the fixer."""
        self.db_path = db_path
        self.dry_run = dry_run
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Initialized FinalItemFixer with dry_run={dry_run}")
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
    
    def get_remaining_identical_entries(self) -> List[Dict[str, Any]]:
        """Get entries that still have identical item and entity values."""
        cursor = self.conn.cursor()
        
        query = """
        SELECT id, mp_name, category, item, entity, details
        FROM disclosures
        WHERE item = entity AND item != 'N/A' AND item != 'Unknown'
        ORDER BY category, mp_name
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
                "details": row["details"] if row["details"] else ""
            })
        
        cursor.close()
        logger.info(f"Found {len(results)} entries that still have identical item and entity values")
        
        return results
    
    def apply_hardcoded_fixes(self) -> List[Dict[str, Any]]:
        """Apply hardcoded fixes based on common patterns."""
        entries = self.get_remaining_identical_entries()
        
        updates = []
        for entry in entries:
            category = entry["category"]
            entity = entry["entity"]
            details = entry["details"]
            item = entry["item"]
            
            # Short circuit if we already have a different item
            if item != entity:
                continue
            
            # Asset category fixes
            if category == "Asset":
                # Handle organizations/clubs
                if re.search(r'club|association|society|forum|hospice|union|alliance|federation|foundation', 
                            entity.lower(), re.IGNORECASE):
                    updates.append({
                        "id": entry["id"],
                        "old_item": item,
                        "new_item": "Organizational Membership"
                    })
                    continue
                
                # Handle tickets/attendance
                if re.search(r'ticket|attend|complimentary', details.lower(), re.IGNORECASE):
                    updates.append({
                        "id": entry["id"],
                        "old_item": item,
                        "new_item": "Event Attendance"
                    })
                    continue
                
                # Handle various organizations
                if entity.lower().startswith("various") or "various" in entity.lower():
                    updates.append({
                        "id": entry["id"],
                        "old_item": item,
                        "new_item": "Multiple Affiliations"
                    })
                    continue
                
                # Handle motor vehicles with no details
                if re.search(r'motor|vehicle|car', entity.lower(), re.IGNORECASE) and details.lower() in ["", "unknown", "n/a"]:
                    updates.append({
                        "id": entry["id"],
                        "old_item": item,
                        "new_item": "Motor Vehicle"
                    })
                    continue
                
                # Handle acronyms that might be companies
                if re.match(r'^[A-Z]{2,5}$', entity) and "shares" not in details.lower():
                    updates.append({
                        "id": entry["id"],
                        "old_item": item,
                        "new_item": "Company Interest"
                    })
                    continue
                    
                # Handle three-letter acronyms likely to be companies
                if len(entity) <= 3 and entity.isupper():
                    updates.append({
                        "id": entry["id"],
                        "old_item": item,
                        "new_item": "Company Interest"
                    })
                    continue
            
            # Income category fixes
            elif category == "Income":
                # Handle salary entries
                if entity.lower() == "salary":
                    updates.append({
                        "id": entry["id"],
                        "old_item": item,
                        "new_item": "Employment Income"
                    })
                    continue
            
            # Add a generic fix for remaining entries
            if item == entity:
                # Extract the first word as a generic description
                first_word = entity.split()[0] if entity else "Interest"
                # Capitalize the first letter
                generic_item = first_word[0].upper() + first_word[1:].lower() if first_word else "Interest"
                
                # Make sure it's not too long
                if len(generic_item) > 30:
                    generic_item = generic_item[:30]
                
                # Add " Interest" suffix if it's likely an organization
                if re.search(r'pty|ltd|limited|inc|club|association', entity.lower(), re.IGNORECASE):
                    if not generic_item.endswith("Interest"):
                        generic_item = f"{generic_item} Interest"
                
                updates.append({
                    "id": entry["id"],
                    "old_item": item,
                    "new_item": generic_item
                })
        
        logger.info(f"Prepared {len(updates)} hardcoded fixes")
        
        # Show sample updates
        if updates:
            sample_size = min(10, len(updates))
            logger.info(f"Sample of {sample_size} updates:")
            for i in range(sample_size):
                logger.info(f"  {updates[i]['old_item']} -> {updates[i]['new_item']}")
        
        return updates
    
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
    
    def run(self) -> int:
        """Run the final fixes and update the database."""
        updates = self.apply_hardcoded_fixes()
        updated_count = self.update_items(updates)
        
        # Check if there are any remaining entries
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM disclosures WHERE item = entity AND item != 'N/A' AND item != 'Unknown'")
        remaining_count = cursor.fetchone()[0]
        cursor.close()
        
        if remaining_count > 0:
            logger.warning(f"There are still {remaining_count} entries with identical item and entity values")
        else:
            logger.info("All identical item and entity values have been fixed!")
        
        return updated_count

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Apply final fixes to entries with identical item and entity values")
    parser.add_argument("--db", default="disclosures.db", help="Path to the SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update the database")
    args = parser.parse_args()
    
    fixer = FinalItemFixer(args.db, args.dry_run)
    
    try:
        updated_count = fixer.run()
        logger.info(f"Successfully updated {updated_count} entries")
    
    finally:
        fixer.close()

if __name__ == "__main__":
    main() 