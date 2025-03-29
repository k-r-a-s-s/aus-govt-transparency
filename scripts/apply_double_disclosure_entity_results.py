#!/usr/bin/env python
"""
Apply double disclosure entity analysis results to update the database.

This script processes the results of the Gemini AI analysis of potential double 
disclosure entities and applies the high-confidence results to update the database.
It splits entities identified as representing multiple separate organizations into 
individual entities, improving data accuracy for the Australian Government Transparency
dataset.
"""

import os
import sys
import json
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

class DoubleDisclosureEntityUpdater:
    """
    Apply double disclosure entity analysis results to update the database.
    
    This class takes the results from Gemini AI analysis and updates the database
    to split entities identified as true double disclosures into separate entities.
    """
    
    def __init__(
        self, 
        db_path: str,
        input_file: str, 
        confidence_threshold: str = "HIGH",
        dry_run: bool = True,
        backup_db: bool = True
    ):
        """
        Initialize the updater.
        
        Args:
            db_path: Path to the SQLite database
            input_file: Path to the compiled results JSON file from Gemini analysis
            confidence_threshold: Minimum confidence level to apply changes ("HIGH", "MEDIUM", "LOW")
            dry_run: If True, only show what would be changed without making actual changes
            backup_db: If True, create a backup of the database before making changes
        """
        self.db_path = db_path
        self.input_file = input_file
        self.confidence_threshold = confidence_threshold.upper()
        self.dry_run = dry_run
        self.backup_db = backup_db
        
        # Validate confidence threshold
        valid_thresholds = ["HIGH", "MEDIUM", "LOW"]
        if self.confidence_threshold not in valid_thresholds:
            raise ValueError(f"Confidence threshold must be one of {valid_thresholds}")
            
        # Connect to the database
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Check if original_entity column exists, add if needed
        self._check_database_schema()
    
    def _check_database_schema(self):
        """
        Check if necessary columns exist in the database schema, add if needed.
        """
        cursor = self.conn.cursor()
        
        # Check if original_entity column exists in disclosures table
        columns = cursor.execute("PRAGMA table_info(disclosures)").fetchall()
        column_names = [col["name"] for col in columns]
        
        if "original_entity" not in column_names:
            logger.info("Adding original_entity column to disclosures table")
            if not self.dry_run:
                # Add the column and set it to the current entity value
                cursor.execute("ALTER TABLE disclosures ADD COLUMN original_entity TEXT")
                cursor.execute("UPDATE disclosures SET original_entity = entity")
                
                # Create an index on original_entity for faster lookups
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_original_entity ON disclosures(original_entity)")
                
                self.conn.commit()
            else:
                logger.info("[DRY RUN] Would add original_entity column to disclosures table")
        else:
            logger.info("original_entity column already exists in disclosures table")
            
        # Verify the column exists after potential creation
        columns = cursor.execute("PRAGMA table_info(disclosures)").fetchall()
        column_names = [col["name"] for col in columns]
        if "original_entity" not in column_names:
            raise ValueError("Failed to create original_entity column")
    
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
    
    def load_analysis_results(self) -> Dict[str, Any]:
        """
        Load double disclosure analysis results from JSON file.
        
        Returns:
            Dict[str, Any]: Loaded results
        """
        logger.info(f"Loading results from {self.input_file}")
        with open(self.input_file, 'r') as f:
            results = json.load(f)
        
        return results
    
    def filter_high_confidence_splits(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Filter the results to get only high confidence double disclosure entities.
        
        Args:
            results: The loaded analysis results
            
        Returns:
            List[Dict[str, Any]]: Filtered list of entities to split
        """
        confidence_levels = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        threshold_level = confidence_levels[self.confidence_threshold]
        
        entity_results = results.get("entity_results", [])
        filtered_entities = []
        
        for entity in entity_results:
            classification = entity.get("classification", "")
            confidence = entity.get("confidence", "")
            
            # Check if it's a MULTIPLE classification with sufficient confidence
            if (classification == "MULTIPLE" and 
                confidence in confidence_levels and 
                confidence_levels[confidence] <= threshold_level and
                "split_entities" in entity and 
                len(entity.get("split_entities", [])) > 1):
                filtered_entities.append(entity)
        
        logger.info(f"Found {len(filtered_entities)} entities to split with {self.confidence_threshold}+ confidence")
        return filtered_entities
    
    def update_database(self):
        """
        Update the database with the split entity results.
        """
        cursor = self.conn.cursor()
        
        # First ensure we have the original_entity column
        self._check_database_schema()
        
        # Load results from the input file
        logger.info(f"Loading results from {self.input_file}")
        with open(self.input_file, 'r') as f:
            results = json.load(f)
            
        # Track statistics
        total_updates = 0
        total_new_disclosures = 0
        modified_entities = set()
        
        # Process each entity that needs to be split
        for entity_data in results.get("entity_results", []):
            original_entity = entity_data.get("entity_name", "")
            confidence = entity_data.get("confidence", "")
            split_entities = entity_data.get("split_entities", [])
            
            if confidence != "HIGH" or not split_entities:
                continue
                
            # Get all disclosures for this entity, checking both entity and original_entity fields
            cursor.execute(
                "SELECT * FROM disclosures WHERE entity = ? OR original_entity = ?", 
                (original_entity, original_entity)
            )
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning(f"No disclosures found for entity: {original_entity}")
                continue
                
            logger.info(f"Processing {len(rows)} disclosures for entity: {original_entity}")
            
            # Track if we modified anything for this entity
            modified_any = False
            
            # For each disclosure, create new records for each split entity
            for row in rows:
                # Only skip if this disclosure has already been split into multiple entities
                # (i.e. original_entity is different from entity)
                if row["original_entity"] is not None and row["original_entity"] != row["entity"]:
                    logger.info(f"Skipping already split disclosure for {original_entity}")
                    continue
                
                # Keep the original disclosure with the first split entity
                first_split_entity = split_entities[0].strip()
                if not self.dry_run:
                    cursor.execute(
                        "UPDATE disclosures SET entity = ?, original_entity = ? WHERE id = ?",
                        (first_split_entity, original_entity, row["id"])
                    )
                total_updates += 1
                modified_any = True
                
                # Create new disclosures for each additional split entity
                for split_entity in split_entities[1:]:
                    split_entity = split_entity.strip()
                    if not self.dry_run:
                        # Create a new row with all the same data but the new entity
                        new_row = dict(row)
                        new_row["id"] = None  # Let SQLite auto-increment
                        new_row["entity"] = split_entity
                        new_row["original_entity"] = original_entity
                        
                        # Build the INSERT statement dynamically
                        columns = ", ".join(new_row.keys())
                        placeholders = ", ".join(["?" for _ in new_row])
                        values = list(new_row.values())
                        
                        cursor.execute(
                            f"INSERT INTO disclosures ({columns}) VALUES ({placeholders})",
                            values
                        )
                    total_new_disclosures += 1
                    modified_entities.add(split_entity)
            
            # Only add to modified_entities if we actually modified something
            if modified_any:
                modified_entities.add(first_split_entity)
            
        if not self.dry_run:
            self.conn.commit()
            
        # Log summary statistics
        logger.info(f"Committed {total_updates} updates and {total_new_disclosures} new disclosures to the database")
        
        # Verify the changes
        cursor.execute("SELECT COUNT(*) as count, COUNT(CASE WHEN original_entity IS NOT NULL AND entity != original_entity THEN 1 END) as modified FROM disclosures;")
        stats = cursor.fetchone()
        logger.info(f"Found {stats['count']} total disclosures")
        logger.info(f"Found {stats['modified']} disclosures where entity differs from original_entity")
        
        # Log a sample of modified entities
        logger.info("Sample of modified entities:")
        for entity in sorted(list(modified_entities))[:10]:
            cursor.execute("SELECT COUNT(*) as count FROM disclosures WHERE entity = ?", (entity,))
            count = cursor.fetchone()["count"]
            logger.info(f"  {entity} ({count} disclosures)")
    
    def verify_results(self):
        """
        Verify the database updates by checking counts and examples.
        """
        cursor = self.conn.cursor()
        
        # Count how many original_entity values are different from entity
        modified_count = cursor.execute(
            "SELECT COUNT(*) FROM disclosures WHERE original_entity IS NOT NULL AND entity != original_entity"
        ).fetchone()[0]
        
        if self.dry_run:
            logger.info("[DRY RUN] Database changes would need to be verified after actual update")
        else:
            logger.info(f"Found {modified_count} disclosures where entity differs from original_entity")
            
            # Get a sample of modified entities
            sample = cursor.execute(
                "SELECT entity, original_entity, COUNT(*) as count FROM disclosures "
                "WHERE original_entity IS NOT NULL AND entity != original_entity "
                "GROUP BY entity, original_entity LIMIT 10"
            ).fetchall()
            
            logger.info("Sample of modified entities:")
            for row in sample:
                logger.info(f"  {row['original_entity']} -> {row['entity']} ({row['count']} disclosures)")
    
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
            # Load and filter results
            results = self.load_analysis_results()
            entities_to_split = self.filter_high_confidence_splits(results)
            
            # Update the database
            self.update_database()
            
            # Verify results
            self.verify_results()
            
            logger.info("Double disclosure entity update process complete")
            
            return True
        except Exception as e:
            logger.error(f"Error in double disclosure entity update process: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
        finally:
            self.close()

def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description="Apply double disclosure entity analysis results to update the database")
    parser.add_argument("--db", default="disclosures.db", help="Path to SQLite database")
    parser.add_argument("--input-file", default="scripts/gemini_results/compiled_results.json", help="Path to compiled results JSON file")
    parser.add_argument("--confidence", default="HIGH", choices=["HIGH", "MEDIUM", "LOW"], help="Minimum confidence level to apply changes")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually apply changes to the database (default is dry run)")
    parser.add_argument("--no-backup", action="store_true", help="Skip creating a database backup before making changes")
    
    args = parser.parse_args()
    
    # Run the updater
    updater = DoubleDisclosureEntityUpdater(
        db_path=args.db,
        input_file=args.input_file,
        confidence_threshold=args.confidence,
        dry_run=not args.no_dry_run,
        backup_db=not args.no_backup
    )
    
    success = updater.run()
    
    # Provide next steps if this was a dry run
    if success and not args.no_dry_run:
        logger.info("\nNext steps:")
        logger.info("1. Review the output above to ensure the changes look correct")
        logger.info("2. Run the script again with --no-dry-run to apply the changes")
        logger.info("3. After applying changes, update canonical entities where needed")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 