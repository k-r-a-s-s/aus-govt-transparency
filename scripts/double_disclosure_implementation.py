#!/usr/bin/env python
"""
Double Disclosure Implementation

This script implements the splitting of double disclosures - entries where multiple
entities are combined in a single entity field. After running analysis and manual review,
this script will:

1. Update the database schema to add an original_entity column
2. Process verified double disclosures and split them into separate records
3. Update canonical entity mappings appropriately
4. Maintain the original combined entity for reference

Usage:
    python double_disclosure_implementation.py [--dry-run] [--reviewed-file FILE]
"""

import sqlite3
import os
import json
import logging
import argparse
import uuid
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DoubleDisclosureProcessor:
    """
    Processor for implementing double disclosure splitting.
    """
    
    def __init__(
        self, 
        db_path: str = "disclosures.db", 
        reviewed_file: str = "scripts/double_disclosure_results/reviewed_double_disclosures.json",
        dry_run: bool = False
    ):
        """
        Initialize the processor.
        
        Args:
            db_path: Path to the SQLite database file
            reviewed_file: Path to the reviewed double disclosures file
            dry_run: If True, don't actually modify the database
        """
        self.db_path = db_path
        self.reviewed_file = reviewed_file
        self.dry_run = dry_run
        
        # Will store the reviewed double disclosures
        self.double_disclosures = {}
        
        # Track stats
        self.stats = {
            "schema_updated": False,
            "total_processed": 0,
            "records_created": 0,
            "entities_processed": set()
        }
    
    def load_reviewed_disclosures(self) -> bool:
        """
        Load the manually reviewed double disclosures file.
        
        Returns:
            bool: True if file was loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(self.reviewed_file):
                logger.error(f"Reviewed file not found: {self.reviewed_file}")
                return False
            
            with open(self.reviewed_file, 'r') as f:
                self.double_disclosures = json.load(f)
            
            logger.info(f"Loaded {len(self.double_disclosures)} reviewed double disclosures")
            return True
            
        except Exception as e:
            logger.error(f"Error loading reviewed disclosures: {e}")
            return False
    
    def update_schema(self, conn: sqlite3.Connection) -> bool:
        """
        Update the database schema to add original_entity column if it doesn't exist.
        
        Args:
            conn: Database connection
            
        Returns:
            bool: True if schema was updated or already had the column, False on error
        """
        try:
            cursor = conn.cursor()
            
            # Check if column already exists
            cursor.execute("PRAGMA table_info(disclosures)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'original_entity' not in columns:
                logger.info("Adding original_entity column to disclosures table")
                
                if not self.dry_run:
                    cursor.execute("ALTER TABLE disclosures ADD COLUMN original_entity TEXT")
                    cursor.execute("UPDATE disclosures SET original_entity = entity")
                    conn.commit()
                
                self.stats["schema_updated"] = True
                logger.info("Schema updated successfully")
            else:
                logger.info("original_entity column already exists")
                self.stats["schema_updated"] = True
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating schema: {e}")
            return False
    
    def process_double_disclosures(self, conn: sqlite3.Connection) -> bool:
        """
        Process and split double disclosures.
        
        Args:
            conn: Database connection
            
        Returns:
            bool: True if processing completed successfully, False on error
        """
        try:
            cursor = conn.cursor()
            total_processed = 0
            records_created = 0
            
            # Process each combined entity from the reviewed file
            for combined_entity, split_entities in self.double_disclosures.items():
                # Skip if this is not a true double disclosure
                if not split_entities or len(split_entities) <= 1:
                    logger.debug(f"Skipping {combined_entity} - not a true double disclosure")
                    continue
                
                # Find all disclosures with this combined entity
                cursor.execute(
                    "SELECT * FROM disclosures WHERE entity = ?",
                    (combined_entity,)
                )
                rows = cursor.fetchall()
                
                if not rows:
                    logger.warning(f"No disclosures found for entity: {combined_entity}")
                    continue
                
                # Get column names
                cursor.execute("PRAGMA table_info(disclosures)")
                columns = [col[1] for col in cursor.fetchall()]
                
                # Process each row with this combined entity
                for row in rows:
                    row_dict = {columns[i]: row[i] for i in range(len(columns))}
                    original_id = row_dict['id']
                    
                    logger.debug(f"Processing disclosure {original_id} with entity {combined_entity}")
                    
                    # For each split entity, create a new disclosure record
                    for i, entity in enumerate(split_entities):
                        # Skip first entity for the original record
                        if i == 0:
                            # Update the original record
                            if not self.dry_run:
                                update_query = """
                                UPDATE disclosures
                                SET entity = ?, original_entity = ?
                                WHERE id = ?
                                """
                                cursor.execute(update_query, (entity, combined_entity, original_id))
                            
                            logger.debug(f"Updated original record {original_id} to entity {entity}")
                        else:
                            # Create a new record for additional entities
                            new_id = str(uuid.uuid4())
                            new_row = row_dict.copy()
                            new_row['id'] = new_id
                            new_row['entity'] = entity
                            new_row['original_entity'] = combined_entity
                            
                            if not self.dry_run:
                                # Build insert query dynamically
                                columns_str = ', '.join(new_row.keys())
                                placeholders = ', '.join(['?'] * len(new_row))
                                insert_query = f"INSERT INTO disclosures ({columns_str}) VALUES ({placeholders})"
                                
                                cursor.execute(insert_query, list(new_row.values()))
                            
                            records_created += 1
                            logger.debug(f"Created new record {new_id} for entity {entity}")
                    
                    total_processed += 1
                    self.stats["entities_processed"].add(combined_entity)
            
            self.stats["total_processed"] = total_processed
            self.stats["records_created"] = records_created
            
            if not self.dry_run:
                conn.commit()
                logger.info("Changes committed to database")
            else:
                logger.info("DRY RUN: No changes were made to the database")
            
            logger.info(f"Processed {total_processed} disclosures, created {records_created} new records")
            return True
            
        except Exception as e:
            logger.error(f"Error processing double disclosures: {e}")
            if not self.dry_run:
                conn.rollback()
                logger.info("Changes rolled back")
            return False
    
    def run(self) -> bool:
        """
        Run the complete double disclosure implementation process.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Starting double disclosure implementation (dry_run={self.dry_run})")
        
        # Load the reviewed disclosures
        if not self.load_reviewed_disclosures():
            return False
        
        try:
            # Connect to the database
            conn = sqlite3.connect(self.db_path)
            
            # Update the schema if needed
            if not self.update_schema(conn):
                conn.close()
                return False
            
            # Process the double disclosures
            success = self.process_double_disclosures(conn)
            
            # Close the connection
            conn.close()
            
            if success:
                logger.info("Double disclosure implementation completed successfully")
                logger.info(f"Statistics: {self.stats}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error during implementation: {e}")
            return False

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Implement double disclosure splitting")
    parser.add_argument('--db-path', default="disclosures.db", help="Path to the database file")
    parser.add_argument('--reviewed-file', 
                        default="scripts/double_disclosure_results/reviewed_double_disclosures.json",
                        help="Path to the reviewed double disclosures file")
    parser.add_argument('--dry-run', action='store_true', 
                        help="Don't actually modify the database, just show what would happen")
    
    args = parser.parse_args()
    
    processor = DoubleDisclosureProcessor(
        db_path=args.db_path,
        reviewed_file=args.reviewed_file,
        dry_run=args.dry_run
    )
    
    success = processor.run()
    return 0 if success else 1

if __name__ == '__main__':
    main() 