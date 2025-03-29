#!/usr/bin/env python
"""
Reset entity values back to match original_entity values.

This script resets the entity column to match the original_entity column for all rows,
while preserving all other data. This allows re-running the double disclosure entity
analysis from scratch.
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

class OriginalEntityResetter:
    """
    Reset entity values back to match original_entity values.
    """
    
    def __init__(
        self, 
        db_path: str,
        dry_run: bool = True,
        backup_db: bool = True
    ):
        """
        Initialize the resetter.
        
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
        
        # Check if original_entity column exists
        self._check_database_schema()
    
    def _check_database_schema(self):
        """
        Check if original_entity column exists in the database schema.
        """
        cursor = self.conn.cursor()
        
        # Check if original_entity column exists in disclosures table
        columns = cursor.execute("PRAGMA table_info(disclosures)").fetchall()
        column_names = [col["name"] for col in columns]
        
        if "original_entity" not in column_names:
            raise ValueError("original_entity column does not exist in disclosures table")
            
        logger.info("original_entity column exists in disclosures table")
    
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
    
    def reset_original_entities(self):
        """
        Reset entity values back to match original_entity values.
        """
        cursor = self.conn.cursor()
        
        # Count how many rows need to be updated
        cursor.execute(
            "SELECT COUNT(*) as count FROM disclosures WHERE original_entity IS NOT NULL AND entity != original_entity"
        )
        count = cursor.fetchone()["count"]
        
        if count == 0:
            logger.info("No rows need to be reset - all entity values already match original_entity values")
            return
            
        logger.info(f"Found {count} rows where entity differs from original_entity")
        
        if not self.dry_run:
            # Update all rows where entity differs from original_entity
            cursor.execute(
                "UPDATE disclosures SET entity = original_entity WHERE original_entity IS NOT NULL AND entity != original_entity"
            )
            self.conn.commit()
            logger.info(f"Reset {count} rows to have entity match original_entity")
        else:
            logger.info(f"[DRY RUN] Would reset {count} rows to have entity match original_entity")
            
            # Show a sample of rows that would be reset
            sample = cursor.execute(
                "SELECT entity, original_entity FROM disclosures "
                "WHERE original_entity IS NOT NULL AND entity != original_entity "
                "LIMIT 5"
            ).fetchall()
            
            logger.info("Sample of rows that would be reset:")
            for row in sample:
                logger.info(f"  {row['entity']} -> {row['original_entity']}")
    
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
            
            # Reset original entities
            self.reset_original_entities()
            
            logger.info("Original entity reset process complete")
            
            return True
        except Exception as e:
            logger.error(f"Error in original entity reset process: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
        finally:
            self.close()

def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description="Reset entity values back to match original_entity values")
    parser.add_argument("--db", default="disclosures.db", help="Path to SQLite database")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually apply changes to the database (default is dry run)")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating a database backup before making changes")
    
    args = parser.parse_args()
    
    # Run the resetter
    resetter = OriginalEntityResetter(
        db_path=args.db,
        dry_run=not args.no_dry_run,
        backup_db=not args.no_backup
    )
    
    success = resetter.run()
    
    # Provide next steps if this was a dry run
    if success and not args.no_dry_run:
        logger.info("\nNext steps:")
        logger.info("1. Review the output above to ensure the changes look correct")
        logger.info("2. Run the double disclosure script again to process all entities")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 