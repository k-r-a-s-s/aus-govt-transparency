#!/usr/bin/env python3
import sqlite3
import json
import logging
import os
import argparse
from typing import Dict, List, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('entity_dedupe')

# Constants
DB_PATH = Path(__file__).parent.parent / "disclosures.db"
MAPPING_PATH = Path(__file__).parent / "entity_dedupe_results" / "proposed_entity_mapping.json"
REVIEWED_MAPPING_PATH = Path(__file__).parent / "entity_dedupe_results" / "reviewed_entity_mapping.json"

class EntityDeduperImplementation:
    """Implements entity deduplication by adding a canonical_entity column."""
    
    def __init__(self, db_path: Path, mapping_path: Path, dry_run: bool = False):
        """Initialize the deduper with paths to database and mapping file."""
        self.db_path = db_path
        self.mapping_path = mapping_path
        self.dry_run = dry_run
        self.entity_mapping: Dict[str, str] = {}  # entity -> canonical_entity
        
    def load_mapping(self) -> None:
        """Load the entity mapping from the JSON file."""
        logger.info(f"Loading entity mapping from {self.mapping_path}")
        
        try:
            with open(self.mapping_path, 'r') as f:
                canonical_to_variants = json.load(f)
            
            # Convert from canonical -> [variants] to variant -> canonical
            for canonical, variants in canonical_to_variants.items():
                # Map the canonical to itself
                self.entity_mapping[canonical] = canonical
                
                # Map each variant to the canonical
                for variant in variants:
                    self.entity_mapping[variant] = canonical
            
            logger.info(f"Loaded mapping for {len(self.entity_mapping)} entities")
            
        except Exception as e:
            logger.error(f"Error loading entity mapping: {e}")
            raise
    
    def check_column_exists(self, conn: sqlite3.Connection, table: str, column: str) -> bool:
        """Check if a column exists in a table."""
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [info[1] for info in cursor.fetchall()]
        return column in columns
    
    def add_canonical_column(self, conn: sqlite3.Connection) -> None:
        """Add the canonical_entity column to the disclosures table if it doesn't exist."""
        if not self.check_column_exists(conn, "disclosures", "canonical_entity"):
            logger.info("Adding canonical_entity column to disclosures table")
            if not self.dry_run:
                conn.execute("ALTER TABLE disclosures ADD COLUMN canonical_entity TEXT")
            else:
                logger.info("DRY RUN: Would add canonical_entity column")
        else:
            logger.info("canonical_entity column already exists")
    
    def update_canonical_entities(self, conn: sqlite3.Connection) -> None:
        """Update the canonical_entity column based on the mapping."""
        cursor = conn.cursor()
        
        # First, set canonical entity to be the same as entity for all rows
        logger.info("Setting default canonical entities (entity -> itself)")
        if not self.dry_run:
            conn.execute("UPDATE disclosures SET canonical_entity = entity WHERE canonical_entity IS NULL")
        else:
            logger.info("DRY RUN: Would set default canonical entities")
        
        # Update counts
        total_updated = 0
        
        # Now update based on our mapping
        logger.info("Updating canonical entities based on mapping")
        for entity, canonical in self.entity_mapping.items():
            if entity != canonical:  # Only update if the canonical is different
                if not self.dry_run:
                    cursor.execute(
                        "UPDATE disclosures SET canonical_entity = ? WHERE entity = ?",
                        (canonical, entity)
                    )
                    total_updated += cursor.rowcount
                else:
                    cursor.execute("SELECT COUNT(*) FROM disclosures WHERE entity = ?", (entity,))
                    count = cursor.fetchone()[0]
                    logger.info(f"DRY RUN: Would update {count} rows from '{entity}' to '{canonical}'")
                    total_updated += count
        
        logger.info(f"Updated canonical_entity for {total_updated} rows")
    
    def create_index(self, conn: sqlite3.Connection) -> None:
        """Create an index on the canonical_entity column for better query performance."""
        logger.info("Creating index on canonical_entity")
        if not self.dry_run:
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_canonical_entity ON disclosures(canonical_entity)")
            except sqlite3.OperationalError as e:
                logger.warning(f"Could not create index: {e}")
        else:
            logger.info("DRY RUN: Would create index on canonical_entity")
    
    def show_statistics(self, conn: sqlite3.Connection) -> None:
        """Show statistics about the entity deduplication."""
        cursor = conn.cursor()
        
        # Count of unique entities before and after deduplication
        cursor.execute("SELECT COUNT(DISTINCT entity) FROM disclosures")
        original_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT canonical_entity) FROM disclosures")
        canonical_count = cursor.fetchone()[0]
        
        reduction = original_count - canonical_count
        reduction_percent = (reduction / original_count) * 100 if original_count > 0 else 0
        
        logger.info(f"Original unique entities: {original_count}")
        logger.info(f"Canonical unique entities: {canonical_count}")
        logger.info(f"Reduction: {reduction} entities ({reduction_percent:.2f}%)")
        
        # Top 10 canonical entities by frequency
        cursor.execute("""
            SELECT canonical_entity, COUNT(*) as count
            FROM disclosures
            WHERE canonical_entity IS NOT NULL
            GROUP BY canonical_entity
            ORDER BY count DESC
            LIMIT 10
        """)
        
        logger.info("Top 10 canonical entities by frequency:")
        for i, (entity, count) in enumerate(cursor.fetchall()):
            logger.info(f"  {i+1}. {entity} ({count} occurrences)")
    
    def implement(self) -> None:
        """Run the full implementation process."""
        self.load_mapping()
        
        logger.info(f"Connecting to database at {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Start a transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Implement the changes
            self.add_canonical_column(conn)
            self.update_canonical_entities(conn)
            self.create_index(conn)
            
            # Commit if not dry run
            if not self.dry_run:
                conn.commit()
                logger.info("Changes committed to database")
            else:
                conn.rollback()
                logger.info("DRY RUN: Changes rolled back (not applied)")
            
            # Show statistics (even for dry run)
            if not self.dry_run:
                self.show_statistics(conn)
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error implementing entity deduplication: {e}")
            raise
        finally:
            conn.close()

def main():
    parser = argparse.ArgumentParser(description="Implement entity deduplication")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually modify the database")
    parser.add_argument("--db-path", type=str, help="Path to the database file")
    parser.add_argument("--mapping", type=str, help="Path to the mapping file (JSON)")
    parser.add_argument("--reviewed", action="store_true", help="Use the reviewed mapping file instead of the proposed one")
    
    args = parser.parse_args()
    
    db_path = Path(args.db_path) if args.db_path else DB_PATH
    
    if args.reviewed:
        mapping_path = REVIEWED_MAPPING_PATH
    else:
        mapping_path = Path(args.mapping) if args.mapping else MAPPING_PATH
    
    # Check if files exist
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        return
    
    if not mapping_path.exists():
        logger.error(f"Mapping file not found: {mapping_path}")
        return
    
    deduper = EntityDeduperImplementation(db_path, mapping_path, args.dry_run)
    deduper.implement()

if __name__ == "__main__":
    main() 