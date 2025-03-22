#!/usr/bin/env python3
"""
Script to remove nil/N/A entries from the disclosures database.
These entries don't provide useful information and just clutter the UI.
"""

import sqlite3
import logging
import os
import sys
from typing import List, Dict, Any
import argparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

DB_PATH = "disclosures.db"

def get_nil_condition() -> str:
    """Returns the SQL condition that identifies nil/N/A entries."""
    return """
        (
            (item IS NULL OR item = '' OR LOWER(item) IN ('n/a', 'nil', 'none', 'not applicable', 'unknown'))
            AND
            (entity IS NULL OR entity = '' OR LOWER(entity) IN ('n/a', 'nil', 'none', 'not applicable', 'unknown'))
            AND
            (details IS NULL OR details = '' OR LOWER(details) IN ('n/a', 'nil', 'none', 'not applicable', 'unknown'))
        )
    """

def count_nil_entries(conn: sqlite3.Connection, mp_name: str = None) -> Dict[str, Any]:
    """
    Count nil entries in the database, optionally filtered by MP name.
    
    Args:
        conn: Database connection
        mp_name: Optional MP name to filter by
        
    Returns:
        Dictionary with counts
    """
    cursor = conn.cursor()
    
    # Query parameters
    params = []
    mp_filter = ""
    if mp_name:
        mp_filter = "AND mp_name = ?"
        params.append(mp_name)
    
    # Count total entries
    cursor.execute(f"SELECT COUNT(*) FROM disclosures WHERE 1=1 {mp_filter}", params)
    total_count = cursor.fetchone()[0]
    
    # SQL condition for nil entries
    nil_condition = get_nil_condition()
    
    # Count nil entries
    cursor.execute(f"SELECT COUNT(*) FROM disclosures WHERE {nil_condition} {mp_filter}", params)
    nil_count = cursor.fetchone()[0]
    
    if total_count == 0:
        nil_percentage = 0
    else:
        nil_percentage = round(nil_count / total_count * 100, 2)
    
    return {
        "nil_entries": nil_count,
        "total_entries": total_count,
        "nil_percentage": nil_percentage
    }

def get_nil_entries_by_mp(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Get counts of nil entries grouped by MP.
    
    Args:
        conn: Database connection
        
    Returns:
        List of dictionaries with MP name and counts
    """
    cursor = conn.cursor()
    
    # Get all MPs
    cursor.execute("SELECT DISTINCT mp_name FROM disclosures ORDER BY mp_name")
    mps = [row[0] for row in cursor.fetchall()]
    
    results = []
    for mp in mps:
        counts = count_nil_entries(conn, mp)
        if counts["nil_entries"] > 0:
            results.append({
                "mp_name": mp,
                **counts
            })
    
    # Sort by percentage (highest first)
    results.sort(key=lambda x: x["nil_percentage"], reverse=True)
    
    return results

def remove_nil_entries(conn: sqlite3.Connection, mp_name: str = None, dry_run: bool = True) -> int:
    """
    Remove nil entries from the database.
    
    Args:
        conn: Database connection
        mp_name: Optional MP name to filter removals by
        dry_run: If True, only print what would be deleted
        
    Returns:
        Number of entries removed
    """
    cursor = conn.cursor()
    
    # Query parameters
    params = []
    mp_filter = ""
    if mp_name:
        mp_filter = "AND mp_name = ?"
        params.append(mp_name)
    
    # SQL condition for nil entries
    nil_condition = get_nil_condition()
    
    # Get count before deletion
    cursor.execute(f"SELECT COUNT(*) FROM disclosures WHERE {nil_condition} {mp_filter}", params)
    count_before = cursor.fetchone()[0]
    
    if dry_run:
        logger.info(f"Would remove {count_before} nil entries{' for ' + mp_name if mp_name else ''}")
        return count_before
    
    # Perform the deletion
    cursor.execute(f"DELETE FROM disclosures WHERE {nil_condition} {mp_filter}", params)
    conn.commit()
    
    # Verify deletion
    cursor.execute(f"SELECT COUNT(*) FROM disclosures WHERE {nil_condition} {mp_filter}", params)
    count_after = cursor.fetchone()[0]
    
    removed = count_before - count_after
    logger.info(f"Removed {removed} nil entries{' for ' + mp_name if mp_name else ''}")
    
    return removed

def main():
    parser = argparse.ArgumentParser(description="Remove nil/N/A entries from the disclosures database")
    parser.add_argument("--mp", help="Filter to a specific MP (default: all MPs)", default=None)
    parser.add_argument("--dry-run", help="Only print what would be deleted, don't make changes", action="store_true")
    parser.add_argument("--stats", help="Only show statistics, don't delete anything", action="store_true")
    args = parser.parse_args()
    
    # Connect to database
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found: {DB_PATH}")
        sys.exit(1)
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        if args.stats:
            # Show overall stats
            counts = count_nil_entries(conn, args.mp)
            logger.info(f"Total entries: {counts['total_entries']}")
            logger.info(f"Nil entries: {counts['nil_entries']}")
            logger.info(f"Percentage: {counts['nil_percentage']}%")
            
            # Show stats by MP
            if not args.mp:
                logger.info("\nMP breakdown (only showing MPs with nil entries):")
                mp_stats = get_nil_entries_by_mp(conn)
                for stat in mp_stats:
                    logger.info(f"{stat['mp_name']}: {stat['nil_entries']}/{stat['total_entries']} ({stat['nil_percentage']}%)")
        else:
            # Show what will be affected
            counts = count_nil_entries(conn, args.mp)
            logger.info(f"Found {counts['nil_entries']} nil entries out of {counts['total_entries']} total ({counts['nil_percentage']}%)")
            
            # Remove entries
            if not args.dry_run:
                if counts['nil_entries'] > 0:
                    confirm = input(f"Are you sure you want to delete {counts['nil_entries']} entries? (y/n): ")
                    if confirm.lower() != 'y':
                        logger.info("Aborted.")
                        return
                        
            removed = remove_nil_entries(conn, args.mp, args.dry_run)
            
            if not args.dry_run:
                logger.info(f"Successfully removed {removed} nil entries")
    finally:
        conn.close()

if __name__ == "__main__":
    main() 