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
    
    def update_database(self, entities_to_split: List[Dict[str, Any]]):
        """
        Update the database with the split entities.
        
        Args:
            entities_to_split: List of entities to split
        """
        if not entities_to_split:
            logger.info("No entities to split")
            return
            
        # Backup the database if needed
        if not self.dry_run:
            self._backup_database()
        
        cursor = self.conn.cursor()
        total_updates = 0
        
        # Process each entity to split
        for entity_data in entities_to_split:
            original_entity = entity_data.get("entity_name", "")
            split_entities = entity_data.get("split_entities", [])
            
            if not original_entity or not split_entities:
                continue
                
            # Find all disclosures with this entity
            query = "SELECT id, entity, canonical_entity, original_entity FROM disclosures WHERE entity = ?"
            rows = cursor.execute(query, (original_entity,)).fetchall()
            
            if not rows:
                logger.warning(f"No disclosures found for entity: {original_entity}")
                continue
                
            # For now, we'll only update the first split entity in each disclosure
            # This ensures we don't duplicate disclosures, which would require more complex logic
            first_split_entity = split_entities[0].strip()
            
            # Update the entity name but preserve the original in original_entity
            logger.info(f"Updating entity: {original_entity} -> {first_split_entity}")
            
            update_count = 0
            for row in rows:
                # If this is the first update for this disclosure, set original_entity
                if not self.dry_run:
                    cursor.execute(
                        "UPDATE disclosures SET entity = ?, original_entity = ? WHERE id = ?",
                        (first_split_entity, original_entity, row["id"])
                    )
                update_count += 1
            
            # Log the updates
            if self.dry_run:
                logger.info(f"[DRY RUN] Would update {update_count} disclosures for entity: {original_entity}")
            else:
                logger.info(f"Updated {update_count} disclosures for entity: {original_entity}")
            total_updates += update_count
        
        # Commit changes
        if not self.dry_run:
            self.conn.commit()
            logger.info(f"Committed {total_updates} updates to the database")
        else:
            logger.info(f"[DRY RUN] Would commit {total_updates} updates to the database")
    
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
            self.update_database(entities_to_split)
            
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