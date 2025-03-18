"""
Entity linker module for linking disclosures to entities.
"""

import logging
from typing import Dict, Any, List, Optional
from ..db.db_handler import DatabaseHandler
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EntityLinker:
    """
    A class to link disclosures to entities in the database.
    """
    
    def __init__(self, db_path: str = "disclosures.db"):
        """
        Initialize the entity linker.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.db_handler = DatabaseHandler(db_path=db_path)
    
    def link_all_disclosures(self) -> Dict[str, int]:
        """
        Link all disclosures to entities in the database.
        
        Returns:
            A dictionary with statistics about the linking process.
        """
        logger.info("Starting to link all disclosures to entities")
        
        # Get all disclosures without entity_id
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if entity_id column exists
        cursor.execute("PRAGMA table_info(disclosures)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "entity_id" not in columns:
            logger.error("entity_id column does not exist in disclosures table")
            conn.close()
            return {"error": "entity_id column does not exist"}
        
        # Get disclosures without entity_id
        cursor.execute("""
            SELECT id, mp_name, item, category, details, declaration_date, sub_category
            FROM disclosures
            WHERE entity_id IS NULL
        """)
        
        disclosures = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"Found {len(disclosures)} disclosures without entity_id")
        
        # Link each disclosure to an entity
        linked_count = 0
        for disclosure in disclosures:
            try:
                entity_id = self.db_handler._find_or_create_entity(
                    cursor,
                    disclosure["mp_name"],
                    disclosure["category"],
                    disclosure["item"],
                    disclosure["declaration_date"]
                )
                
                # Update the disclosure with the entity_id
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE disclosures SET entity_id = ? WHERE id = ?",
                    (entity_id, disclosure["id"])
                )
                conn.commit()
                conn.close()
                
                linked_count += 1
                
                if linked_count % 100 == 0:
                    logger.info(f"Linked {linked_count} disclosures so far")
                
            except Exception as e:
                logger.error(f"Error linking disclosure {disclosure['id']}: {str(e)}")
        
        logger.info(f"Finished linking disclosures. Linked {linked_count} out of {len(disclosures)}")
        
        return {
            "total_disclosures": len(disclosures),
            "linked_disclosures": linked_count
        }
    
    def update_entity_dates(self) -> Dict[str, int]:
        """
        Update first_seen and last_seen dates for all entities.
        
        Returns:
            A dictionary with statistics about the update process.
        """
        logger.info("Updating first_seen and last_seen dates for all entities")
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all entities
        cursor.execute("SELECT id FROM entities")
        entities = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"Found {len(entities)} entities to update")
        
        updated_count = 0
        for entity_id in entities:
            # Get earliest and latest declaration dates for this entity
            cursor.execute("""
                SELECT MIN(declaration_date) as first_seen, MAX(declaration_date) as last_seen
                FROM disclosures
                WHERE entity_id = ?
            """, (entity_id,))
            
            dates = cursor.fetchone()
            
            if dates and dates["first_seen"] and dates["last_seen"]:
                # Update the entity
                cursor.execute(
                    "UPDATE entities SET first_seen = ?, last_seen = ? WHERE id = ?",
                    (dates["first_seen"], dates["last_seen"], entity_id)
                )
                updated_count += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated dates for {updated_count} entities")
        
        return {
            "total_entities": len(entities),
            "updated_entities": updated_count
        }

    def _process_pending_disclosures(self):
        """Process disclosures that haven't been linked to entities yet."""
        self.logger.info("Processing pending disclosures")
        
        # Get pending disclosures
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT id, mp_name, entity, item, category, details, declaration_date, sub_category
                FROM disclosures
                WHERE entity_id IS NULL
                """
            )
            
            disclosures = cursor.fetchall()
            self.logger.info(f"Found {len(disclosures)} pending disclosures")
            
            # Process each disclosure
            for disc in disclosures:
                disc_id, mp_name, entity, item, category, details, declaration_date, sub_category = disc
                
                # If entity is empty but item has a value, use item
                if not entity or entity.lower() in ['n/a', 'unknown', 'nil', '']:
                    entity = item
                
                # Skip if entity is still not meaningful
                if not entity or entity.lower() in ['n/a', 'unknown', 'nil', '']:
                    continue
                
                entity_id = self.db_handler._find_or_create_entity(
                    cursor,
                    mp_name,
                    category,
                    entity,
                    declaration_date
                )
                
                if entity_id:
                    cursor.execute(
                        """
                        UPDATE disclosures
                        SET entity_id = ?
                        WHERE id = ?
                        """,
                        (entity_id, disc_id)
                    )
            
            conn.commit()
            conn.close()
            self.logger.info("Finished processing pending disclosures")
            
        except Exception as e:
            self.logger.error(f"Error processing pending disclosures: {e}")
            if conn:
                conn.close() 