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
import uuid
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
            
        # Check if split_entity column exists
        if "split_entity" not in column_names:
            logger.info("Adding split_entity column to disclosures table")
            if not self.dry_run:
                cursor.execute("ALTER TABLE disclosures ADD COLUMN split_entity TEXT")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_split_entity ON disclosures(split_entity)")
                self.conn.commit()
            else:
                logger.info("[DRY RUN] Would add split_entity column to disclosures table")
        else:
            logger.info("split_entity column already exists in disclosures table")
            
        # Verify the columns exist after potential creation
        columns = cursor.execute("PRAGMA table_info(disclosures)").fetchall()
        column_names = [col["name"] for col in columns]
        if "original_entity" not in column_names:
            raise ValueError("Failed to create original_entity column")
        if "split_entity" not in column_names:
            raise ValueError("Failed to create split_entity column")
    
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
        """Update the database by splitting entities identified as MULTIPLE."""
        cursor = self.conn.cursor()

        # Ensure required columns exist
        self._check_database_schema()

        # Load analysis results
        analysis_data = self.load_analysis_results()
        entities_to_split = self.filter_high_confidence_splits(analysis_data)

        if not entities_to_split:
            logger.info("No entities meet the criteria for splitting.")
            return

        # Backup before proceeding (if enabled and not dry run)
        if not self.dry_run:
            self._backup_database()

        total_rows_updated = 0
        total_rows_inserted = 0
        processed_original_entities = set()

        # Get column names from the disclosures table dynamically
        cursor.execute("PRAGMA table_info(disclosures)")
        table_columns = [col["name"] for col in cursor.fetchall()]
        # Ensure 'id' is present for error checking, though value will be replaced for inserts
        if 'id' not in table_columns:
            raise ValueError("Table 'disclosures' must have an 'id' column.")
        # Prepare column string for INSERT
        column_str = ", ".join([f'"{col}"' for col in table_columns]) # Quote names just in case
        placeholder_str = ", ".join(["?"] * len(table_columns))

        logger.info("Starting database update process...")

        for entity_data in entities_to_split:
            original_entity = entity_data.get("entity_name")
            split_entities = [s.strip() for s in entity_data.get("split_entities", []) if s and s.strip()]

            if not original_entity or len(split_entities) < 2: # Must have at least 2 splits
                logger.warning(f"Skipping invalid split data for original entity: '{original_entity}'")
                continue

            # Avoid processing the same original entity multiple times if it appears duplicates in input
            if original_entity in processed_original_entities:
                continue
            processed_original_entities.add(original_entity)

            logger.info(f"--- Processing entity: '{original_entity}' -> {split_entities} ---")

            # Find rows that need splitting for this entity
            # We only want rows where the entity *is* the original compound name
            # (i.e., it hasn't potentially been processed in a previous run)
            cursor.execute(
                "SELECT * FROM disclosures WHERE entity = ?",
                (original_entity,)
            )
            rows_to_process = cursor.fetchall()

            if not rows_to_process:
                logger.warning(f"  No unprocessed rows found matching '{original_entity}'. It might have been processed already.")
                continue

            logger.info(f"  Found {len(rows_to_process)} rows to split for '{original_entity}'.")

            first_split = split_entities[0]
            subsequent_splits = split_entities[1:]

            for row_dict in [dict(row) for row in rows_to_process]: # Convert rows to dicts
                original_row_id = row_dict['id']

                # 1. Update the existing row for the *first* split entity
                update_sql = "UPDATE disclosures SET entity = ?, original_entity = ? WHERE id = ?"
                update_values = (first_split, original_entity, original_row_id)
                if not self.dry_run:
                    cursor.execute(update_sql, update_values)
                logger.debug(f"  [UPDATE ID: {original_row_id}] entity='{first_split}', original_entity='{original_entity}' (split_entity untouched here)")
                total_rows_updated += 1

                # 2. Insert new rows for *subsequent* split entities
                for next_split in subsequent_splits:
                    new_id = str(uuid.uuid4())
                    logger.debug(f"Generated new UUID for split: {new_id}")
                    
                    # Explicitly define data for the new row, copying from original
                    new_row_data = {
                        'id': new_id,  # This should ALWAYS be included
                        'entity': next_split,
                        'original_entity': original_entity,
                        'parliament': row_dict.get('parliament'),
                        'member_id': row_dict.get('member_id'),
                        'first_name': row_dict.get('first_name'),
                        'last_name': row_dict.get('last_name'),
                        'electorate': row_dict.get('electorate'),
                        'state': row_dict.get('state'),
                        'party': row_dict.get('party'),
                        'date': row_dict.get('date'),
                        'category': row_dict.get('category'),
                        'sub_category': row_dict.get('sub_category'),
                        'item': row_dict.get('item'),
                        'details': row_dict.get('details'),
                        'source_url': row_dict.get('source_url'),
                        'term_id': row_dict.get('term_id'),
                        'volume': row_dict.get('volume'),
                        'additional_notes': row_dict.get('additional_notes'),
                        'page_number': row_dict.get('page_number'),
                        'source_file': row_dict.get('source_file'),
                        'amount': row_dict.get('amount'),
                        'last_updated': row_dict.get('last_updated'), 
                        'term_start_date': row_dict.get('term_start_date'),
                        'term_end_date': row_dict.get('term_end_date'),
                        'type': row_dict.get('type'),
                        'document_id': row_dict.get('document_id'),
                    }

                    # Debug log the table columns
                    logger.debug(f"Table columns: {table_columns}")
                    logger.debug(f"Original new_row_data: {new_row_data}")

                    # Ensure critical fields are always included
                    filtered_new_row_data = {
                        'id': new_id,  # Force include id
                        'entity': next_split,  # Force include entity
                        'original_entity': original_entity,  # Force include original_entity
                        'split_entity': next_split,  # Force include split_entity matching entity
                    }
                    # Add other non-None values that exist in table_columns
                    filtered_new_row_data.update({
                        k: v for k, v in new_row_data.items() 
                        if k in table_columns 
                        and v is not None 
                        and k not in filtered_new_row_data  # Don't overwrite forced fields
                    })

                    logger.debug(f"Filtered new_row_data: {filtered_new_row_data}")
                    
                    valid_columns = list(filtered_new_row_data.keys())
                    column_str = ", ".join([f'"{col}"' for col in valid_columns])
                    placeholder_str = ", ".join(["?"] * len(valid_columns))
                    values_tuple = tuple(filtered_new_row_data[col] for col in valid_columns)

                    # Debug log the SQL and values
                    logger.debug(f"INSERT SQL: {column_str}")
                    logger.debug(f"INSERT values: {values_tuple}")

                    insert_sql = f"INSERT INTO disclosures ({column_str}) VALUES ({placeholder_str})"
                    
                    if not values_tuple: 
                         logger.warning(f"Skipping INSERT for split '{next_split}' from '{original_entity}' as no valid data was prepared.")
                         continue
                         
                    if not self.dry_run:
                        try:
                            cursor.execute(insert_sql, values_tuple)
                            logger.debug(f"Successfully executed INSERT for {new_id}")
                        except Exception as e:
                             logger.error(f"Error executing INSERT for split '{next_split}' (New ID: {new_id}): {e}")
                             logger.error(f"SQL: {insert_sql}")
                             logger.error(f"Values: {values_tuple}")
                             raise 
                             
                    logger.debug(f"  [INSERT NEW ID: {new_id}] entity='{next_split}', original_entity='{original_entity}' (split_entity untouched here)")
                    total_rows_inserted += 1

        # Commit initial updates/inserts if not dry run
        if not self.dry_run:
            logger.info("Committing initial row updates/inserts...")
            self.conn.commit()
            logger.info("Initial commit successful.")

        # --- 3. Final Patch Step for split_entity ---
        logger.info("Applying final patch to populate split_entity where NULL...")
        patch_sql = """
            UPDATE disclosures 
            SET split_entity = entity 
            WHERE split_entity IS NULL 
              AND original_entity IS NOT NULL;
        """
        patch_rows_affected = 0
        if not self.dry_run:
            try:
                cursor.execute(patch_sql)
                patch_rows_affected = cursor.rowcount # Get affected rows for this specific statement
                self.conn.commit() # Commit the patch separately
                logger.info(f"Patch commit successful. Updated split_entity for {patch_rows_affected} rows.")
            except Exception as e:
                logger.error(f"Error applying split_entity patch: {e}")
                self.conn.rollback() # Rollback patch on error
        else:
            # Estimate affected rows in dry run
            cursor.execute("SELECT COUNT(*) FROM disclosures WHERE split_entity IS NULL AND original_entity IS NOT NULL")
            estimated_patch_count = cursor.fetchone()[0]
            logger.info(f"DRY RUN: Would attempt to patch split_entity for {estimated_patch_count} rows.")
            patch_rows_affected = estimated_patch_count # Use estimate for logging

        # Log summary (consider adding patch count here)
        logger.info(f"--- Update Summary ---")
        logger.info(f"Original entities processed for splitting: {len(processed_original_entities)}")
        logger.info(f"Rows updated (for first split): {total_rows_updated}")
        logger.info(f"New rows inserted (for subsequent splits): {total_rows_inserted}")
        logger.info(f"Rows patched (split_entity populated): {patch_rows_affected}")
        
        if self.dry_run:
             logger.info("DRY RUN: No changes were committed to the database.")

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
            logger.info("Database connection closed.")
    
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