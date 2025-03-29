#!/usr/bin/env python
"""
Apply Gemini Entity Analysis Results

This script processes the results from Gemini entity analysis and applies
them to the database. It focuses on high-confidence multiple entity identifications
and updates the database accordingly.

Usage:
    python apply_gemini_entity_results.py [--input_file FILE] [--db_path PATH] [--dry_run]
"""

import os
import json
import sqlite3
import argparse
import logging
import uuid
from typing import List, Dict, Any, Tuple, Set

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GeminiResultsApplier:
    """
    Applies Gemini analysis results to the database.
    """
    
    def __init__(
        self,
        input_file: str = "scripts/gemini_results/compiled_results.json",
        db_path: str = "disclosures.db",
        dry_run: bool = False,
        confidence_threshold: str = "HIGH",
        apply_only_high_confidence_multiples: bool = True
    ):
        """
        Initialize the applier.
        
        Args:
            input_file: Path to the compiled results from Gemini analysis
            db_path: Path to the SQLite database
            dry_run: If True, don't actually modify the database
            confidence_threshold: Minimum confidence level to apply changes (HIGH, MEDIUM, LOW)
            apply_only_high_confidence_multiples: If True, only apply MULTIPLE entities with HIGH confidence
        """
        self.input_file = input_file
        self.db_path = db_path
        self.dry_run = dry_run
        self.confidence_threshold = confidence_threshold
        self.apply_only_high_confidence_multiples = apply_only_high_confidence_multiples
        
        # Will hold the processed results
        self.results = {}
        self.entities_to_apply = []
        
        # Stats tracking
        self.stats = {
            "total_entities": 0,
            "filtered_entities": 0,
            "rows_updated": 0,
            "new_rows_created": 0,
            "errors": 0
        }
    
    def load_results(self) -> bool:
        """
        Load the Gemini analysis results.
        
        Returns:
            bool: True if results were loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(self.input_file):
                logger.error(f"Input file not found: {self.input_file}")
                return False
            
            with open(self.input_file, 'r') as f:
                self.results = json.load(f)
            
            self.stats["total_entities"] = self.results.get("total_entities_analyzed", 0)
            logger.info(f"Loaded results for {self.stats['total_entities']} entities")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading results: {e}")
            return False
    
    def filter_entities_to_apply(self) -> bool:
        """
        Filter entities based on confidence and classification.
        
        Returns:
            bool: True if filtering was successful, False otherwise
        """
        try:
            all_entities = self.results.get("entity_results", [])
            confidence_levels = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
            threshold_level = confidence_levels.get(self.confidence_threshold.upper(), 3)
            
            # Filter entities
            for entity in all_entities:
                entity_name = entity.get("entity_name")
                classification = entity.get("classification", "").upper()
                confidence = entity.get("confidence", "").upper()
                split_entities = entity.get("split_entities", [])
                
                # Skip entities with confidence below threshold
                if confidence_levels.get(confidence, 0) < threshold_level:
                    logger.debug(f"Skipping {entity_name} due to low confidence: {confidence}")
                    continue
                
                # Apply only MULTIPLE entities or all depending on settings
                if self.apply_only_high_confidence_multiples:
                    if classification == "MULTIPLE" and confidence == "HIGH" and len(split_entities) > 1:
                        self.entities_to_apply.append(entity)
                else:
                    if classification == "MULTIPLE" and len(split_entities) > 1:
                        self.entities_to_apply.append(entity)
            
            self.stats["filtered_entities"] = len(self.entities_to_apply)
            logger.info(f"Selected {self.stats['filtered_entities']} entities to apply to database")
            
            return True
            
        except Exception as e:
            logger.error(f"Error filtering entities: {e}")
            return False
    
    def apply_to_database(self) -> bool:
        """
        Apply filtered entity changes to the database.
        
        Returns:
            bool: True if changes were applied successfully, False otherwise
        """
        if not self.entities_to_apply:
            logger.warning("No entities to apply to database")
            return True
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if original_entity column exists
            cursor.execute("PRAGMA table_info(disclosures)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'original_entity' not in columns:
                logger.info("Adding original_entity column to disclosures table")
                if not self.dry_run:
                    cursor.execute("ALTER TABLE disclosures ADD COLUMN original_entity TEXT")
                    cursor.execute("UPDATE disclosures SET original_entity = entity")
                    conn.commit()
            
            # Process each entity
            for entity_data in self.entities_to_apply:
                entity_name = entity_data["entity_name"]
                split_entities = entity_data["split_entities"]
                
                logger.info(f"Processing entity: {entity_name} -> {split_entities}")
                
                # Find all disclosures with this entity
                cursor.execute(
                    "SELECT * FROM disclosures WHERE entity = ?",
                    (entity_name,)
                )
                rows = cursor.fetchall()
                
                if not rows:
                    logger.warning(f"No disclosures found for entity: {entity_name}")
                    continue
                
                # Get column names
                cursor.execute("PRAGMA table_info(disclosures)")
                column_info = cursor.fetchall()
                column_names = [column[1] for column in column_info]
                
                # Process each row with this entity
                for row in rows:
                    row_dict = {column_names[i]: row[i] for i in range(len(column_names))}
                    original_id = row_dict['id']
                    
                    # For each split entity, create a new disclosure record
                    for i, split_entity in enumerate(split_entities):
                        # Skip first entity for the original record
                        if i == 0:
                            # Update the original record
                            if not self.dry_run:
                                update_query = """
                                UPDATE disclosures
                                SET entity = ?, original_entity = ?
                                WHERE id = ?
                                """
                                cursor.execute(update_query, (split_entity, entity_name, original_id))
                            
                            self.stats["rows_updated"] += 1
                            logger.debug(f"Updated original record {original_id} to entity {split_entity}")
                        else:
                            # Create a new record for additional entities
                            new_id = str(uuid.uuid4())
                            new_row = row_dict.copy()
                            new_row['id'] = new_id
                            new_row['entity'] = split_entity
                            new_row['original_entity'] = entity_name
                            
                            if not self.dry_run:
                                # Build insert query dynamically
                                columns_str = ', '.join(new_row.keys())
                                placeholders = ', '.join(['?'] * len(new_row))
                                insert_query = f"INSERT INTO disclosures ({columns_str}) VALUES ({placeholders})"
                                
                                cursor.execute(insert_query, list(new_row.values()))
                            
                            self.stats["new_rows_created"] += 1
                            logger.debug(f"Created new record {new_id} for entity {split_entity}")
            
            if not self.dry_run:
                conn.commit()
                logger.info("Changes committed to database")
            else:
                logger.info("DRY RUN: No changes were made to the database")
            
            conn.close()
            
            logger.info(f"Updated {self.stats['rows_updated']} rows and created {self.stats['new_rows_created']} new rows")
            return True
            
        except Exception as e:
            logger.error(f"Error applying changes to database: {e}")
            if 'conn' in locals() and conn:
                conn.rollback()
                conn.close()
                logger.info("Changes rolled back")
            self.stats["errors"] += 1
            return False
    
    def save_report(self) -> bool:
        """
        Save a report of applied changes.
        
        Returns:
            bool: True if report was saved successfully, False otherwise
        """
        try:
            # Create a detailed report
            report = {
                "dry_run": self.dry_run,
                "stats": self.stats,
                "applied_entities": [
                    {
                        "entity_name": entity["entity_name"],
                        "confidence": entity["confidence"],
                        "split_entities": entity["split_entities"],
                        "explanation": entity.get("explanation", "")
                    }
                    for entity in self.entities_to_apply
                ]
            }
            
            # Save the report
            output_dir = os.path.dirname(self.input_file)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(output_dir, f"application_report_{timestamp}.json")
            
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Saved application report to {report_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            return False
    
    def run(self) -> Dict[str, Any]:
        """
        Run the complete application process.
        
        Returns:
            Dict[str, Any]: Statistics from the application process
        """
        logger.info(f"Starting application of Gemini results (dry_run={self.dry_run})")
        
        if not self.load_results():
            return self.stats
        
        if not self.filter_entities_to_apply():
            return self.stats
        
        if not self.apply_to_database():
            return self.stats
        
        self.save_report()
        
        logger.info("Application complete")
        return self.stats

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Apply Gemini entity analysis results to database")
    parser.add_argument('--input-file', 
                        default="scripts/gemini_results/compiled_results.json",
                        help="Path to the compiled results from Gemini analysis")
    parser.add_argument('--db-path', 
                        default="disclosures.db",
                        help="Path to the SQLite database")
    parser.add_argument('--dry-run', action='store_true',
                        help="Don't actually modify the database, just show what would happen")
    parser.add_argument('--confidence', 
                        default="HIGH",
                        choices=["HIGH", "MEDIUM", "LOW"],
                        help="Minimum confidence level to apply changes")
    parser.add_argument('--all-confidences', action='store_true',
                        help="Apply MULTIPLE entities with all confidence levels (not just HIGH)")
    
    args = parser.parse_args()
    
    applier = GeminiResultsApplier(
        input_file=args.input_file,
        db_path=args.db_path,
        dry_run=args.dry_run,
        confidence_threshold=args.confidence,
        apply_only_high_confidence_multiples=not args.all_confidences
    )
    
    applier.run()
    return 0

if __name__ == '__main__':
    import time
    main() 