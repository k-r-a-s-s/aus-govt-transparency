#!/usr/bin/env python3
"""
Script to fix entries where item and entity values are identical.
This applies category-specific extraction rules to get better item descriptions.
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

class IdenticalItemFixer:
    """Class to fix entries where item and entity values are identical."""
    
    def __init__(self, db_path: str = "disclosures.db", dry_run: bool = False):
        """Initialize the fixer."""
        self.db_path = db_path
        self.dry_run = dry_run
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Initialized IdenticalItemFixer with dry_run={dry_run}")
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
    
    def get_identical_entries(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get entries where item and entity values are identical."""
        cursor = self.conn.cursor()
        
        # Base query
        query = """
        SELECT id, mp_name, category, item, entity, details
        FROM disclosures
        WHERE item = entity AND item != 'N/A' AND item != 'Unknown'
        """
        
        # Add category filter if specified
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        
        # Limit results
        query += " LIMIT 10000"  # Reasonable limit to process in batches if needed
        
        cursor.execute(query, params)
        
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
        
        if category:
            logger.info(f"Found {len(results)} entries with identical item and entity values in category '{category}'")
        else:
            logger.info(f"Found {len(results)} entries with identical item and entity values across all categories")
        
        return results
    
    def extract_asset_item(self, entity: str, details: str) -> str:
        """Extract a meaningful asset item from the entity and details."""
        # Strip trailing ownership info
        entity_clean = re.sub(r'\s*\((?:Self|Spouse|Dependent|Joint)\)$', '', entity, flags=re.IGNORECASE)
        
        # Check for special patterns in details first
        if details:
            if 'accommodation' in details.lower() or 'hotel' in details.lower():
                return "Accommodation"
                
            if 'framed' in details.lower() and ('cartoon' in details.lower() or 'picture' in details.lower()):
                return "Artwork"
                
            if re.search(r'sale of .+ owned by', details.lower()):
                sale_match = re.search(r'sale of ([^,]+)', details.lower())
                if sale_match:
                    return f"Sale of {sale_match.group(1).strip()}"
                    
            if 'received a' in details.lower():
                return "Gift Received"
                
            if 'card holder' in details.lower():
                return "Card Holder"
                
            if 'attendance' in details.lower() and re.search(r'(dinner|open|event|session)', details.lower()):
                return "Event Attendance"
                
            if 'share in' in details.lower():
                if 'horse' in entity.lower() or 'horse' in details.lower():
                    return "Race Horse Ownership"
                else:
                    return "Share Ownership"
                    
            if 'saving' in details.lower():
                return "Savings Account"
                
            if 'superannuation' in details.lower():
                return "Superannuation"
                
            if 'dependent children' in details.lower() or 'spouse' in details.lower():
                return "Family Related"
        
        # Direct replacements for common identical values
        if entity_clean.lower() == 'dependent children':
            return "Family Related"
            
        if entity_clean.lower() == 'real estate':
            return "Property"
            
        if entity_clean.lower() == 'salary':
            return "Employment Income"
            
        if entity_clean.lower() == 'shares':
            return "Share Investments"
            
        if re.search(r'trade|pty|ltd', entity_clean, re.IGNORECASE) and 'shares in' in details.lower():
            company_name = re.search(r'shares in ([^,\.]+)', details.lower())
            if company_name:
                return f"Shares in {company_name.group(1).strip()}"
            else:
                return "Company Shares"
        
        # Common asset categories
        if re.search(r'real.?estate|property|house|apartment|land|farm', entity_clean, re.IGNORECASE):
            if 'house' in entity_clean.lower() or 'house' in details.lower():
                return "Residential House"
            elif 'apartment' in entity_clean.lower() or 'apartment' in details.lower() or 'unit' in details.lower():
                return "Apartment"
            elif 'land' in entity_clean.lower() or 'land' in details.lower():
                return "Land"
            elif 'farm' in entity_clean.lower() or 'farm' in details.lower():
                return "Farm Property"
            else:
                return "Real Estate"
        
        # Location-specific real estate
        if re.match(r'^[A-Z][a-z]+$', entity_clean) and len(entity_clean) > 3:  # Likely a suburb or location
            if details and ('residence' in details.lower() or 'house' in details.lower()):
                return f"Residential Property in {entity_clean}"
            else:
                return f"Property in {entity_clean}"
        
        if re.search(r'share|stock|investment|fund', entity_clean, re.IGNORECASE):
            if 'fund' in entity_clean.lower():
                return "Investment Fund"
            elif details and 'shares' in details.lower():
                company_match = re.search(r'([A-Za-z0-9]+) (Shares|shares)', details)
                if company_match:
                    return f"Shares in {company_match.group(1)}"
                else:
                    return "Shares"
            else:
                return "Shares"
        
        if re.search(r'bank|saving|deposit|cash|account|ing|nab|cba|westpac|anz', entity_clean, re.IGNORECASE):
            if details and 'savings' in details.lower():
                return "Savings Account"
            elif details and 'term deposit' in details.lower():
                return "Term Deposit"
            else:
                return "Bank Account"
        
        if re.search(r'car|vehicle|motor|toyota|holden|ford|cooper', entity_clean, re.IGNORECASE):
            return "Motor Vehicle"
        
        if re.search(r'super|retirement|cbus', entity_clean, re.IGNORECASE):
            return "Superannuation"
        
        # Specific named entities with common patterns
        if entity_clean.lower().startswith('mr ') or entity_clean.lower().startswith('mrs ') or entity_clean.lower().startswith('ms '):
            return "Personal Transaction"
            
        if re.search(r'(hong kong|region|administrative|government|department)', entity_clean, re.IGNORECASE):
            return "Government-Related Asset"
            
        if re.search(r'(sar)\b', entity_clean, re.IGNORECASE):
            return "Administrative Region"
        
        # Fallback
        return entity_clean
    
    def extract_income_item(self, entity: str, details: str) -> str:
        """Extract a meaningful income item from the entity and details."""
        # Check for common income types
        if re.search(r'salary|wage|employment', entity.lower()) or re.search(r'salary|wage|employment', details.lower()):
            return "Salary"
        
        if re.search(r'dividend|interest', entity.lower()) or re.search(r'dividend|interest', details.lower()):
            return "Investment Income"
        
        if re.search(r'rent', entity.lower()) or re.search(r'rent', details.lower()):
            return "Rental Income"
        
        if re.search(r'pension|retirement', entity.lower()) or re.search(r'pension|retirement', details.lower()):
            return "Pension"
        
        # For organizations, assume it's employment income
        if re.search(r'department|ministry|pty ltd|limited|inc|university|council', entity.lower()):
            return "Employment Income"
        
        # Fallback
        return "Income"
    
    def extract_gift_item(self, entity: str, details: str) -> str:
        """Extract a meaningful gift item from the entity and details."""
        # Check details for gift information
        if 'ticket' in details.lower() or 'ticket' in entity.lower():
            return "Tickets"
        
        if re.search(r'book|publication', details.lower()) or re.search(r'book|publication', entity.lower()):
            return "Books"
        
        if re.search(r'hospitality|dinner|lunch|breakfast', details.lower()):
            return "Hospitality"
        
        if re.search(r'travel|flight|accommodation', details.lower()):
            return "Travel"
        
        if re.search(r'artwork|painting|sculpture', details.lower()):
            return "Artwork"
        
        # If entity is likely the source, not the gift itself
        if re.search(r'club|association|foundation|company|pty|ltd|inc', entity.lower()):
            return "Gift"
        
        # Fallback
        return "Gift"
    
    def extract_membership_item(self, entity: str, details: str) -> str:
        """Extract a meaningful membership item from the entity and details."""
        # Check for membership types
        if re.search(r'club|association', entity.lower()):
            if re.search(r'sport|golf|tennis|football|rugby|cricket', entity.lower()):
                return "Sporting Club Membership"
            elif re.search(r'social|community', entity.lower()):
                return "Social Club Membership"
            else:
                return "Club Membership"
        
        if re.search(r'board|director|trustee', entity.lower()) or re.search(r'board|director|trustee', details.lower()):
            return "Board Membership"
        
        if re.search(r'professional|industry', entity.lower()) or re.search(r'professional|industry', details.lower()):
            return "Professional Association"
        
        # Fallback
        return "Membership"
    
    def extract_travel_item(self, entity: str, details: str) -> str:
        """Extract a meaningful travel item from the entity and details."""
        # Check for travel types
        if re.search(r'flight|air', entity.lower()) or re.search(r'flight|air', details.lower()):
            return "Flights"
        
        if re.search(r'accommodation|hotel|stay', entity.lower()) or re.search(r'accommodation|hotel|stay', details.lower()):
            return "Accommodation"
        
        if re.search(r'conference|event|meeting', entity.lower()) or re.search(r'conference|event|meeting', details.lower()):
            return "Conference Travel"
        
        # Fallback
        return "Travel"
    
    def extract_unknown_item(self, entity: str, details: str) -> str:
        """Extract a meaningful item from Unknown category entries."""
        # Check if details can give us a clue
        if details and details.lower() not in ['unknown', 'n/a', 'nil', 'self', 'spouse']:
            # Look for specific patterns
            if re.search(r'property|house|apartment|land', details.lower()):
                return "Property"
            
            if re.search(r'share|stock|investment', details.lower()):
                return "Investment"
            
            if re.search(r'salary|employment|income', details.lower()):
                return "Income"
            
            if re.search(r'gift|present', details.lower()):
                return "Gift"
            
            if re.search(r'travel|flight|accommodation', details.lower()):
                return "Travel"
            
            # If details is substantial, use it
            if len(details) > 5 and details != entity:
                return details
        
        # Entity-based fallbacks
        if re.search(r'pty|ltd|limited|inc', entity.lower()):
            return "Company Interest"
        
        # Fallback
        return "Interest"
    
    def extract_better_item(self, entry: Dict[str, Any]) -> str:
        """Extract a better item description based on category, entity and details."""
        category = entry["category"]
        entity = entry["entity"]
        details = entry["details"] if entry["details"] else ""
        
        # Apply category-specific extraction logic
        if category == "Asset":
            return self.extract_asset_item(entity, details)
        elif category == "Income":
            return self.extract_income_item(entity, details)
        elif category == "Gift":
            return self.extract_gift_item(entity, details)
        elif category == "Membership":
            return self.extract_membership_item(entity, details)
        elif category == "Travel":
            return self.extract_travel_item(entity, details)
        elif category == "Unknown":
            return self.extract_unknown_item(entity, details)
        else:
            # Fallback
            return entity
    
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
    
    def process_category(self, category: Optional[str] = None) -> int:
        """Process entries with identical item and entity values for a specific category."""
        # Get entries with identical item and entity values
        entries = self.get_identical_entries(category)
        
        # Prepare updates
        updates = []
        for entry in entries:
            # Extract a better item description
            new_item = self.extract_better_item(entry)
            
            # Add to updates if different
            if new_item != entry["item"]:
                updates.append({
                    "id": entry["id"],
                    "old_item": entry["item"],
                    "new_item": new_item
                })
        
        logger.info(f"Found {len(updates)} entries that need updating")
        
        # Show sample updates
        if updates:
            sample_size = min(5, len(updates))
            logger.info(f"Sample of {sample_size} updates:")
            for i in range(sample_size):
                logger.info(f"  {updates[i]['old_item']} -> {updates[i]['new_item']}")
        
        # Update items in the database
        updated_count = self.update_items(updates)
        return updated_count
    
    def process_all(self) -> Dict[str, int]:
        """Process all entries with identical item and entity values across all categories."""
        # Get all categories
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM disclosures")
        categories = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        # Process each category
        results = {}
        for category in categories:
            logger.info(f"Processing category: {category}")
            updated_count = self.process_category(category)
            results[category] = updated_count
        
        # Log summary
        total_updated = sum(results.values())
        logger.info(f"Total updated: {total_updated} entries across {len(categories)} categories")
        
        # Final check for any remaining identical item/entity values
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM disclosures WHERE item = entity AND item != 'N/A' AND item != 'Unknown'")
        remaining_count = cursor.fetchone()[0]
        cursor.close()
        
        if remaining_count > 0:
            logger.warning(f"There are still {remaining_count} entries with identical item and entity values")
            
            # Sample remaining entries
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, mp_name, category, item, entity, details 
                FROM disclosures 
                WHERE item = entity AND item != 'N/A' AND item != 'Unknown' 
                LIMIT 5
            """)
            
            remaining_entries = []
            for row in cursor.fetchall():
                remaining_entries.append({
                    "id": row[0],
                    "mp_name": row[1],
                    "category": row[2],
                    "item": row[3],
                    "entity": row[4],
                    "details": row[5]
                })
            cursor.close()
            
            logger.warning("Sample of remaining entries:")
            for entry in remaining_entries:
                logger.warning(f"  {entry['mp_name']} - {entry['category']} - {entry['item']} - {entry['details']}")
        else:
            logger.info("All identical item and entity values have been fixed!")
        
        return results

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix entries where item and entity values are identical")
    parser.add_argument("--db", default="disclosures.db", help="Path to the SQLite database")
    parser.add_argument("--category", help="Process only a specific category")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update the database")
    parser.add_argument("--force", action="store_true", help="Process all entries even if already processed once")
    args = parser.parse_args()
    
    fixer = IdenticalItemFixer(args.db, args.dry_run)
    
    try:
        if args.category:
            updated_count = fixer.process_category(args.category)
            logger.info(f"Successfully updated {updated_count} entries in category '{args.category}'")
        else:
            results = fixer.process_all()
            total_updated = sum(results.values())
            logger.info(f"Successfully updated {total_updated} entries across all categories")
    
    finally:
        fixer.close()

if __name__ == "__main__":
    main() 