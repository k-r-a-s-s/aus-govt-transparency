#!/usr/bin/env python3
"""
Standardize disclosure data in the database.

This script standardizes MP names and electorate names to ensure data consistency,
making it easier to analyze disclosure patterns across parliaments.
"""

import os
import logging
import argparse
import sqlite3
from typing import Dict, List, Tuple

# Import standardization modules
from standardize_mp_names import identify_mp_variations, update_mp_names, report_stats
from standardize_electorates import identify_electorate_variations, standardize_electorates, report_mp_electorate_changes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def backup_database(db_path: str) -> str:
    """
    Create a backup of the database before making changes.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        Path to the backup file
    """
    backup_path = f"{db_path}.backup"
    logger.info(f"Creating database backup at {backup_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        backup_conn = sqlite3.connect(backup_path)
        
        conn.backup(backup_conn)
        
        conn.close()
        backup_conn.close()
        
        logger.info(f"Database backup completed successfully")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create database backup: {str(e)}")
        raise

def generate_database_statistics(db_path: str) -> Dict[str, int]:
    """
    Generate statistics about the database contents.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        Dictionary with database statistics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {}
    
    # Count total disclosures
    cursor.execute("SELECT COUNT(*) FROM disclosures")
    stats["total_disclosures"] = cursor.fetchone()[0]
    
    # Count distinct MPs
    cursor.execute("SELECT COUNT(DISTINCT mp_name) FROM disclosures")
    stats["distinct_mps"] = cursor.fetchone()[0]
    
    # Count distinct electorates
    cursor.execute("SELECT COUNT(DISTINCT electorate) FROM disclosures WHERE electorate IS NOT NULL")
    stats["distinct_electorates"] = cursor.fetchone()[0]
    
    # Count by category
    cursor.execute("""
        SELECT category, COUNT(*) 
        FROM disclosures 
        GROUP BY category 
        ORDER BY COUNT(*) DESC
    """)
    stats["categories"] = {row[0]: row[1] for row in cursor.fetchall()}
    
    conn.close()
    return stats

def standardize_database(db_path: str, dry_run: bool = False) -> Dict[str, Dict[str, int]]:
    """
    Run all standardization processes on the database.
    
    Args:
        db_path: Path to the SQLite database
        dry_run: If True, only print changes without applying them
        
    Returns:
        Dictionary with statistics from each standardization step
    """
    all_stats = {}
    
    # Step 1: Back up the database (if not dry run)
    if not dry_run:
        backup_database(db_path)
    
    # Step 2: Generate initial statistics
    logger.info("Generating initial database statistics...")
    initial_stats = generate_database_statistics(db_path)
    all_stats["before_standardization"] = initial_stats
    
    logger.info(f"Initial database status:")
    logger.info(f"  - Total disclosures: {initial_stats['total_disclosures']}")
    logger.info(f"  - Distinct MPs: {initial_stats['distinct_mps']}")
    logger.info(f"  - Distinct electorates: {initial_stats['distinct_electorates']}")
    
    # Step 3: Standardize MP names
    logger.info("\n" + "="*80)
    logger.info("STAGE 1: MP NAME STANDARDIZATION")
    logger.info("="*80)
    
    # Identify MP name variations
    mp_variations = identify_mp_variations(db_path)
    
    # Update MP names in the database
    mp_stats = update_mp_names(db_path, mp_variations, dry_run)
    all_stats["mp_standardization"] = mp_stats
    
    # Generate report for MP standardization
    report_stats(mp_stats, mp_variations)
    
    # Step 4: Standardize electorate names
    logger.info("\n" + "="*80)
    logger.info("STAGE 2: ELECTORATE STANDARDIZATION")
    logger.info("="*80)
    
    # Identify electorate variations by MP
    electorate_variations = identify_electorate_variations(db_path)
    
    # Standardize electorate names
    electorate_stats = standardize_electorates(db_path, dry_run)
    all_stats["electorate_standardization"] = electorate_stats
    
    # Report MPs with multiple electorates after standardization
    if not dry_run:
        report_mp_electorate_changes(db_path)
    
    # Step 5: Generate final statistics
    if not dry_run:
        logger.info("\n" + "="*80)
        logger.info("FINAL DATABASE STATISTICS")
        logger.info("="*80)
        
        final_stats = generate_database_statistics(db_path)
        all_stats["after_standardization"] = final_stats
        
        logger.info(f"Final database status:")
        logger.info(f"  - Total disclosures: {final_stats['total_disclosures']}")
        logger.info(f"  - Distinct MPs: {final_stats['distinct_mps']}")
        logger.info(f"  - Distinct electorates: {final_stats['distinct_electorates']}")
        logger.info(f"  - MP reduction: {initial_stats['distinct_mps'] - final_stats['distinct_mps']} names merged")
        logger.info(f"  - Electorate reduction: {initial_stats['distinct_electorates'] - final_stats['distinct_electorates']} electorates standardized")
    
    return all_stats

def main():
    """Main function to parse arguments and run the standardization workflow."""
    parser = argparse.ArgumentParser(description="Standardize MP names and electorates in the database")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database file")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without applying them")
    
    args = parser.parse_args()
    
    logger.info(f"Starting data standardization workflow for database: {args.db_path}")
    
    try:
        # Run all standardization processes
        standardize_database(args.db_path, args.dry_run)
        
        # Provide guidance on next steps
        logger.info("\n" + "="*80)
        logger.info("STANDARDIZATION COMPLETE")
        logger.info("="*80)
        
        if not args.dry_run:
            logger.info("\nNext steps:")
            logger.info("1. Run category validation and statistics generation:")
            logger.info("   python update_categories.py")
            logger.info("2. Begin data analysis and visualization")
        else:
            logger.info("\nTo apply these changes, run without the --dry-run flag")
        
    except Exception as e:
        logger.error(f"Error during standardization: {str(e)}")
        raise
    
    logger.info("Done!")

if __name__ == "__main__":
    main() 