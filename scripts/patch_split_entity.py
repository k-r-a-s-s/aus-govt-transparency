#!/usr/bin/env python
"""
Patch Script for split_entity Column

This script ensures that the split_entity column is correctly populated by 
copying the value from the entity column for rows where split_entity is NULL 
but an original_entity exists (indicating the row resulted from a split).

Run this script AFTER apply_double_disclosure_entity_results.py and 
BEFORE standardize_entities.py.
"""

import sqlite3
import argparse
import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('patch_split_entity')

def patch_split_entity(db_path: str, dry_run: bool = False):
    """Connects to the DB and applies the patch."""
    
    conn = None
    updated_count = 0
    
    try:
        logger.info(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        patch_sql = """
            UPDATE disclosures 
            SET split_entity = entity 
            WHERE split_entity IS NULL 
              AND original_entity IS NOT NULL;
        """

        logger.info("Executing patch query:")
        logger.info(patch_sql)

        if dry_run:
            # Estimate affected rows
            cursor.execute("SELECT COUNT(*) FROM disclosures WHERE split_entity IS NULL AND original_entity IS NOT NULL")
            estimated_count = cursor.fetchone()[0]
            logger.info(f"DRY RUN: Would attempt to update split_entity for {estimated_count} rows.")
            updated_count = estimated_count
        else:
            # Execute the update
            cursor.execute(patch_sql)
            updated_count = cursor.rowcount
            conn.commit()
            logger.info(f"Patch applied successfully. Rows affected: {updated_count}")

    except sqlite3.Error as e:
        logger.error(f"Database error during patch: {e}")
        if conn:
            conn.rollback()
        sys.exit(1) # Exit with error status
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        if conn:
            conn.rollback()
        sys.exit(1) # Exit with error status
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")
            
    logger.info("Patch script finished.")

def main():
    parser = argparse.ArgumentParser(description=
        "Patch the split_entity column in the disclosures database."
    )
    parser.add_argument("--db", required=True, help="Path to the SQLite database file")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Show what would happen, but don't modify the database")

    args = parser.parse_args()

    patch_split_entity(db_path=args.db, dry_run=args.dry_run)

if __name__ == '__main__':
    main() 