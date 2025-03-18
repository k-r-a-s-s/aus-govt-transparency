#!/usr/bin/env python3
"""
Validate category data quality and generate comprehensive statistics.

This script ensures all disclosures follow the standardized categorization system
and generates statistical reports on the distribution of categories, subcategories,
and temporal types across the database.
"""

import os
import argparse
import logging
from db_handler import DatabaseHandler, Categories, Subcategories, TemporalTypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def update_categories(db_path: str, dry_run: bool = False):
    """
    Validate disclosure categories and generate statistics on category distribution.
    
    This function ensures all disclosures in the database adhere to the standardized
    category system and produces comprehensive statistics on the data distribution.
    
    Args:
        db_path: Path to the SQLite database file
        dry_run: If True, only print information without applying any changes
    """
    logger.info(f"Validating categories and generating statistics for database at {db_path}")
    
    # Initialize the database handler
    db = DatabaseHandler(db_path=db_path)
    
    # Validate and standardize categories
    if dry_run:
        logger.info("Dry run mode: Category validation information only")
        # Print out categorization system information
        logger.info("Standardized category system:")
        for category in Categories.ALL:
            subcategories = Subcategories.MAPPING.get(category, [])
            logger.info(f"Category: {category}")
            for subcategory in subcategories:
                logger.info(f"  - Subcategory: {subcategory}")
        
        logger.info("Temporal type system:")
        for temporal_type in TemporalTypes.ALL:
            logger.info(f"Temporal Type: {temporal_type}")
    else:
        # Validate categories and entity references
        logger.info("Validating categories and entity references...")
        updated_count = db.link_existing_disclosures_to_entities()
        logger.info(f"Validation complete: {updated_count} disclosures updated for consistency")
    
    # Generate comprehensive statistics
    logger.info("Generating disclosure statistics...")
    patterns = db.get_disclosure_patterns()
    
    # Print category stats
    logger.info("\nCategory Distribution:")
    for category, data in patterns.get("categories", {}).items():
        logger.info(f"{category}: {data['total']} disclosures")
        for subcategory, count in data.get("subcategories", {}).items():
            if subcategory:
                logger.info(f"  - {subcategory}: {count} disclosures")
    
    # Print temporal type stats
    logger.info("\nTemporal Type Distribution:")
    for temporal_type, count in patterns.get("temporal_types", {}).items():
        if temporal_type:
            logger.info(f"{temporal_type}: {count} disclosures")
    
    # Print persistence stats
    persistence = patterns.get("persistence", {})
    logger.info("\nItem Persistence:")
    logger.info(f"Long-term items (3+ years): {len(persistence.get('long_term', []))}")
    logger.info(f"Medium-term items (2 years): {len(persistence.get('medium_term', []))}")
    logger.info(f"Short-term items (1 year): {len(persistence.get('short_term', []))}")
    
    # Print a sample of long-term items
    long_term = persistence.get("long_term", [])[:5]  # Just take the first 5 for brevity
    if long_term:
        logger.info("\nSample Long-term Items:")
        for item in long_term:
            logger.info(f"{item['name']} ({item['category']}): Present for {item['years']} years")
    
    logger.info("Validation and statistics generation complete")

def main():
    """Main function to parse arguments and run validation and statistics generation."""
    parser = argparse.ArgumentParser(
        description="Validate disclosure categories and generate comprehensive statistics"
    )
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database file")
    parser.add_argument("--dry-run", action="store_true", help="Show statistics without applying any changes")
    
    args = parser.parse_args()
    
    update_categories(args.db_path, args.dry_run)
    
    logger.info("Done!")

if __name__ == "__main__":
    main() 