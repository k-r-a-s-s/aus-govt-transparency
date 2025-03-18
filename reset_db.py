#!/usr/bin/env python3
"""
Reset the database, removing all tables and recreating them.

This script is useful for testing purposes to start with a clean database after 
making schema changes or when major changes to the data model are implemented.
"""

import os
import argparse
import logging
import sqlite3
from typing import Optional
from db_handler import DatabaseHandler, Categories, Subcategories

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reset_database(db_path: str, backup: bool = True) -> None:
    """
    Reset the database by dropping all tables and recreating them.
    
    Args:
        db_path: Path to the SQLite database file
        backup: If True, create a backup of the database before resetting
    """
    if not os.path.exists(db_path):
        logger.info(f"Database file {db_path} does not exist. Will create a new one.")
        # Initialize a new database
        db = DatabaseHandler(db_path=db_path)
        logger.info(f"Created new database at {db_path}")
        return
    
    # Create backup if requested
    if backup:
        backup_path = f"{db_path}.backup"
        logger.info(f"Creating backup at {backup_path}")
        
        try:
            with open(db_path, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
            logger.info(f"Backup created successfully at {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            return
    
    # Delete and recreate the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        # Begin transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Drop all tables
        for table in tables:
            table_name = table[0]
            if table_name != 'sqlite_sequence':  # Skip internal SQLite tables
                logger.info(f"Dropping table: {table_name}")
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        # Commit transaction
        conn.commit()
        logger.info("All tables dropped successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error dropping tables: {str(e)}")
        return
    finally:
        conn.close()
    
    # Initialize database with new schema
    logger.info("Recreating database tables with updated schema")
    db = DatabaseHandler(db_path=db_path)
    logger.info("Database reset completed successfully")
    
    # Print category information for verification
    logger.info("\nVerifying category definitions:")
    for category in Categories.ALL:
        logger.info(f"Category: {category}")
        subcategories = Subcategories.MAPPING.get(category, [])
        for subcategory in subcategories:
            logger.info(f"  - Subcategory: {subcategory}")

def main():
    """Parse command line arguments and execute the reset."""
    parser = argparse.ArgumentParser(description="Reset the database by dropping all tables and recreating them")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database file")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating a backup before reset")
    
    args = parser.parse_args()
    
    reset_database(args.db_path, backup=not args.no_backup)
    
    logger.info("Database reset and schema recreation completed")

if __name__ == "__main__":
    main() 