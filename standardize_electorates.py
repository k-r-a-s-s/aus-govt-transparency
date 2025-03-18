#!/usr/bin/env python3
"""
Standardize electorate names in the database.

This script standardizes electorate names to fix case inconsistencies,
standardize renamed electorates, and ensure consistent formatting.
"""

import os
import sqlite3
import logging
import argparse
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mapping of old/inconsistent electorate names to standardized names
# Based on official renames and case standardization
ELECTORATE_MAPPING = {
    # Format: 'inconsistent_name': 'standardized_name'
    
    # Case inconsistencies
    'bonner': 'Bonner',
    'BONNER': 'Bonner',
    'BASS': 'Bass',
    'BLAIR': 'Blair',
    'DAWSON': 'Dawson',
    'GRIFFITH': 'Griffith',
    'HOLT': 'Holt',
    'JagaJaga': 'Jagajaga',
    'LALOR': 'Lalor',
    'LEICHHARDT': 'Leichhardt',
    'Macarthur': 'MacArthur',
    'MONASH': 'Monash',
    'RANKIN': 'Rankin',
    'WATSON': 'Watson',
    
    # Renamed electorates
    'Denison': 'Clark',          # Renamed in 2018
    'Throsby': 'Whitlam',        # Renamed in 2016
    'Charlton': 'Shortland',     # Renamed in 2016
    'Murray': 'Nicholls',        # Renamed in 2019
    'McMillan': 'Monash',        # Renamed in 2019
    'Batman': 'Cooper',          # Renamed in 2019
    'Wakefield': 'Spence',       # Renamed in 2019
    'Makin': 'Spence',           # Renamed in 2019 (shared redistribution)
    'Melbourne Ports': 'Macnamara', # Renamed in 2019
    'Port Adelaide': 'Hindmarsh',   # Merged in 2019
    'Monaro': 'Eden-Monaro',        # Correcting error
    'Fraser': 'Fenner',             # Renamed in 2016
    
    # Standardizing spacing and formatting
    'Mc Millan': 'Monash',      # Renamed and fixing spacing
    'Eden Monaro': 'Eden-Monaro', # Adding hyphen
}

def identify_electorate_variations(db_path: str) -> Dict[str, List[str]]:
    """
    Identify all electorate variations in the database.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        Dictionary mapping MPs to their electorate variations
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all MPs with multiple electorates
    cursor.execute("""
        SELECT mp_name, GROUP_CONCAT(DISTINCT electorate) as electorates 
        FROM disclosures 
        GROUP BY mp_name 
        HAVING COUNT(DISTINCT electorate) > 1
    """)
    
    mp_electorate_variations = {}
    for row in cursor.fetchall():
        mp_name, electorates = row
        electorate_list = electorates.split(',')
        mp_electorate_variations[mp_name] = electorate_list
    
    conn.close()
    return mp_electorate_variations

def standardize_electorates(db_path: str, dry_run: bool = False) -> Dict[str, int]:
    """
    Standardize electorate names in the database.
    
    Args:
        db_path: Path to the SQLite database
        dry_run: If True, only print changes without applying them
        
    Returns:
        Dictionary with statistics about the updates
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {
        "total_variations": 0,
        "total_mappings": len(ELECTORATE_MAPPING),
        "records_updated": 0
    }
    
    # Start a transaction
    if not dry_run:
        cursor.execute("BEGIN TRANSACTION")
    
    logger.info(f"{'Simulating' if dry_run else 'Performing'} electorate standardization")
    
    # Get list of all unique electorates in the database
    cursor.execute("SELECT DISTINCT electorate FROM disclosures WHERE electorate IS NOT NULL")
    electorates = [row[0] for row in cursor.fetchall() if row[0]]
    
    # Process each electorate mapping
    for old_name, new_name in ELECTORATE_MAPPING.items():
        if old_name in electorates:
            # Count affected records
            cursor.execute("SELECT COUNT(*) FROM disclosures WHERE electorate = ?", (old_name,))
            record_count = cursor.fetchone()[0]
            
            if record_count > 0:
                logger.info(f"Standardizing electorate: '{old_name}' → '{new_name}' ({record_count} records)")
                stats["total_variations"] += 1
                stats["records_updated"] += record_count
                
                # Update records if not a dry run
                if not dry_run:
                    cursor.execute("UPDATE disclosures SET electorate = ? WHERE electorate = ?", 
                                  (new_name, old_name))
    
    # Commit the transaction if not a dry run
    if not dry_run:
        conn.commit()
        logger.info(f"Successfully updated {stats['records_updated']} records for {stats['total_variations']} electorate variations")
    else:
        logger.info(f"Dry run: would update {stats['records_updated']} records for {stats['total_variations']} electorate variations")
    
    conn.close()
    return stats

def report_mp_electorate_changes(db_path: str) -> None:
    """
    Report MPs who have changed electorates over time.
    This distinguishes between electorate renames and actual MP moves.
    
    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Find MPs with multiple electorates after standardization
    cursor.execute("""
        SELECT mp_name, GROUP_CONCAT(DISTINCT electorate) as electorates, 
               COUNT(DISTINCT electorate) as electorate_count
        FROM disclosures 
        GROUP BY mp_name 
        HAVING electorate_count > 1
        ORDER BY electorate_count DESC, mp_name
    """)
    
    results = cursor.fetchall()
    
    if results:
        logger.info("\nMPs with multiple electorates after standardization:")
        logger.info("(These may represent actual moves between electorates)")
        
        for mp_name, electorates, count in results:
            logger.info(f"  - {mp_name}: {electorates} ({count} electorates)")
    else:
        logger.info("\nNo MPs with multiple electorates after standardization")
    
    conn.close()

def main():
    """Main function to parse arguments and run the standardization."""
    parser = argparse.ArgumentParser(description="Standardize electorate names in the database")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database file")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without applying them")
    
    args = parser.parse_args()
    
    logger.info(f"Analyzing electorate names in database: {args.db_path}")
    
    # Identify electorate variations by MP
    mp_variations = identify_electorate_variations(args.db_path)
    logger.info(f"Found {len(mp_variations)} MPs with multiple electorates")
    
    # Standardize electorate names
    stats = standardize_electorates(args.db_path, args.dry_run)
    
    # Report MPs with multiple electorates after standardization
    if not args.dry_run:
        report_mp_electorate_changes(args.db_path)
    
    logger.info("Done!")

if __name__ == "__main__":
    main() 