#!/usr/bin/env python
"""
Create a split_entity column in the database and populate it.

This script adds a split_entity column to the disclosures table and populates it
with the current entity values. This allows future standardization to operate on
the split entities while preserving the original entity information.
"""

import os
import sys
import argparse
import logging
import sqlite3
from typing import Dict, List, Any, Tuple
from collections import defaultdict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SplitEntityAdder:
    """
    Add split_entity column to the database and populate it.
    """
    
    def __init__(
        self, 
        db_path: str,
        dry_run: bool = True,
        backup_db: bool = True
    ):
        """
        Initialize the adder.
        
        Args:
            db_path: Path to the SQLite database
            dry_run: If True, only show what would be changed without making actual changes
            backup_db: If True, create a backup of the database before making changes
        """
        self.db_path = db_path
        self.dry_run = dry_run
        self.backup_db = backup_db
        
        # Connect to the database
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def _backup_database(self):
        """
        Create a backup of the database before making changes.
        """
        if not self.backup_db:
            return
            
        import shutil
        from datetime import datetime
        
        backup_path = f"{self.db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Creating backup of database at {backup_path}")
        
        if not self.dry_run:
            shutil.copy2(self.db_path, backup_path)
        else:
            logger.info(f"[DRY RUN] Would create backup at {backup_path}")
        
        return backup_path
    
    def add_split_entity_column(self):
        """
        Add split_entity column to disclosures table.
        """
        cursor = self.conn.cursor()
        
        # Check if split_entity column already exists
        columns = cursor.execute("PRAGMA table_info(disclosures)").fetchall()
        column_names = [col["name"] for col in columns]
        
        if "split_entity" in column_names:
            logger.info("split_entity column already exists in disclosures table")
            return False
            
        logger.info("Adding split_entity column to disclosures table")
        
        if not self.dry_run:
            # Add the column and set it to the current entity value
            cursor.execute("ALTER TABLE disclosures ADD COLUMN split_entity TEXT")
            cursor.execute("UPDATE disclosures SET split_entity = entity")
                
            # Create an index on split_entity for faster lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_split_entity ON disclosures(split_entity)")
                
            self.conn.commit()
            logger.info("Added split_entity column and populated it with entity values")
            return True
        else:
            logger.info("[DRY RUN] Would add split_entity column and populate it with entity values")
            return False
    
    def close(self):
        """
        Close the database connection.
        """
        if self.conn:
            self.conn.close()
    
    def run(self):
        """
        Run the entire process.
        """
        try:
            # Create backup if needed
            if self.backup_db:
                self._backup_database()
            
            # Add split_entity column
            self.add_split_entity_column()
            
            logger.info("Split entity column creation process complete")
            
            return True
        except Exception as e:
            logger.error(f"Error in split entity column creation process: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
        finally:
            self.close()

def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description="Add split_entity column to database")
    parser.add_argument("--db", default="disclosures.db", help="Path to SQLite database")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually apply changes to the database (default is dry run)")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating a database backup before making changes")
    
    args = parser.parse_args()
    
    # Run the adder
    adder = SplitEntityAdder(
        db_path=args.db,
        dry_run=not args.no_dry_run,
        backup_db=not args.no_backup
    )
    
    success = adder.run()
    
    # Provide next steps if this was successful
    if success:
        if args.no_dry_run:
            logger.info("\nNext steps:")
            logger.info("1. The split_entity column has been added and populated with entity values")
            logger.info("2. You can now run entity standardization on the split_entity column")
        else:
            logger.info("\nNext steps:")
            logger.info("1. Run with --no-dry-run to actually apply the changes")
            logger.info("2. Then run entity standardization on the split_entity column")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 