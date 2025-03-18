#!/usr/bin/env python3
"""
Standardize MP names in the database by removing middle names.

This script identifies MPs with multiple name variations (with and without middle names),
and standardizes them to a consistent format (first name + last name).
"""

import os
import sqlite3
import re
import logging
import argparse
from typing import Dict, List, Tuple, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def identify_mp_variations(db_path: str) -> Dict[str, List[str]]:
    """
    Identify MPs with multiple name variations in the database.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        Dictionary mapping standardized names to lists of variations
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all unique MP names
    cursor.execute("SELECT DISTINCT mp_name FROM disclosures ORDER BY mp_name")
    all_names = [row[0] for row in cursor.fetchall()]
    
    # Process names to identify variations
    name_variations = {}
    processed_names = set()
    
    for full_name in all_names:
        if full_name in processed_names:
            continue
        
        # Skip if name is None or empty
        if not full_name:
            continue
            
        # Split the name into parts
        name_parts = full_name.split()
        
        # Handle special cases or non-standard formats
        if len(name_parts) <= 1:
            # Single word name or unusual format, keep as is
            standardized = full_name
            name_variations[standardized] = [full_name]
            processed_names.add(full_name)
            continue
            
        # Extract first and last name
        first_name = name_parts[0]
        last_name = name_parts[-1]
        
        # Handle special cases with prefixes like "Van", "De", etc.
        prefixes = ["van", "von", "de", "del", "della", "di", "da", "dos", "du", "le", "la", "st.", "saint"]
        if len(name_parts) > 2 and name_parts[-2].lower() in prefixes:
            last_name = f"{name_parts[-2]} {last_name}"
            if len(name_parts) > 3 and name_parts[-3].lower() in prefixes:
                last_name = f"{name_parts[-3]} {last_name}"
        
        # Create standardized name (first + last)
        standardized = f"{first_name} {last_name}"
        
        # Find all variations of this name
        variations = []
        for name in all_names:
            if not name:
                continue
                
            name_parts_compare = name.split()
            if len(name_parts_compare) <= 1:
                continue
                
            first_name_compare = name_parts_compare[0]
            last_name_compare = name_parts_compare[-1]
            
            # Check for prefixes in last name
            if len(name_parts_compare) > 2 and name_parts_compare[-2].lower() in prefixes:
                last_name_compare = f"{name_parts_compare[-2]} {last_name_compare}"
                if len(name_parts_compare) > 3 and name_parts_compare[-3].lower() in prefixes:
                    last_name_compare = f"{name_parts_compare[-3]} {last_name_compare}"
            
            # Check if this is a variation of the current name
            if first_name_compare == first_name and last_name_compare == last_name:
                variations.append(name)
                processed_names.add(name)
        
        if variations:
            name_variations[standardized] = variations
    
    conn.close()
    return name_variations

def update_mp_names(db_path: str, name_variations: Dict[str, List[str]], dry_run: bool = False) -> Dict[str, int]:
    """
    Update MP names in the database to the standardized format.
    
    Args:
        db_path: Path to the SQLite database
        name_variations: Dictionary mapping standardized names to lists of variations
        dry_run: If True, only print changes without applying them
        
    Returns:
        Dictionary with statistics about the updates
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {
        "total_variations": 0,
        "mps_with_variations": 0,
        "records_updated": 0
    }
    
    # Start a transaction
    if not dry_run:
        cursor.execute("BEGIN TRANSACTION")
    
    logger.info(f"{'Simulating' if dry_run else 'Performing'} MP name standardization")
    
    # Process each MP name standardization
    for standardized, variations in name_variations.items():
        if len(variations) <= 1:
            continue  # No variations to standardize
            
        stats["mps_with_variations"] += 1
        stats["total_variations"] += len(variations) - 1
        
        logger.info(f"Standardizing {len(variations)} variations to '{standardized}':")
        for variation in variations:
            if variation != standardized:
                logger.info(f"  - '{variation}' → '{standardized}'")
                
                # Count affected records
                cursor.execute("SELECT COUNT(*) FROM disclosures WHERE mp_name = ?", (variation,))
                record_count = cursor.fetchone()[0]
                stats["records_updated"] += record_count
                
                # Update records if not a dry run
                if not dry_run:
                    cursor.execute("UPDATE disclosures SET mp_name = ? WHERE mp_name = ?", 
                                  (standardized, variation))
                    
                    # Also update relationships table if it exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='relationships'")
                    if cursor.fetchone():
                        cursor.execute("UPDATE relationships SET mp_name = ? WHERE mp_name = ?", 
                                      (standardized, variation))
    
    # Commit the transaction if not a dry run
    if not dry_run:
        conn.commit()
        logger.info(f"Successfully updated {stats['records_updated']} records")
    else:
        logger.info(f"Dry run: would update {stats['records_updated']} records")
    
    conn.close()
    return stats

def report_stats(stats: Dict[str, int], name_variations: Dict[str, List[str]]) -> None:
    """Print a summary report of the standardization process."""
    logger.info("\nStandardization Summary:")
    logger.info(f"Total MPs with name variations: {stats['mps_with_variations']}")
    logger.info(f"Total name variations standardized: {stats['total_variations']}")
    logger.info(f"Total records updated: {stats['records_updated']}")
    
    # Report MPs with the most variations
    mp_variation_counts = {name: len(vars) for name, vars in name_variations.items() if len(vars) > 1}
    if mp_variation_counts:
        max_variations = max(mp_variation_counts.values())
        most_variations = [name for name, count in mp_variation_counts.items() if count == max_variations]
        
        logger.info(f"\nMPs with the most name variations ({max_variations}):")
        for name in most_variations:
            variations = name_variations[name]
            logger.info(f"  - {name}: {', '.join(variations)}")

def main():
    """Main function to parse arguments and run the standardization."""
    parser = argparse.ArgumentParser(description="Standardize MP names by removing middle names")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database file")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without applying them")
    
    args = parser.parse_args()
    
    logger.info(f"Analyzing MP names in database: {args.db_path}")
    
    # Identify name variations
    name_variations = identify_mp_variations(args.db_path)
    
    # Update names in the database
    stats = update_mp_names(args.db_path, name_variations, args.dry_run)
    
    # Generate report
    report_stats(stats, name_variations)
    
    logger.info("Done!")

if __name__ == "__main__":
    main() 