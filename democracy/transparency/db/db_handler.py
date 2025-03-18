import os
import json
import sqlite3
import logging
import uuid
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseHandler:
    """
    A class to handle database operations for storing structured data.
    """
    
    def __init__(self, db_path: str = "disclosures.db"):
        """
        Initialize the database handler.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._initialize_db()
    
    def _initialize_db(self):
        """
        Initialize the database schema if it doesn't exist.
        """
        logger.info(f"Initializing database at {self.db_path}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create disclosures table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS disclosures (
            id TEXT PRIMARY KEY,
            mp_name TEXT NOT NULL,
            party TEXT,
            electorate TEXT,
            declaration_date TEXT,
            category TEXT,
            item TEXT,
            details TEXT,
            pdf_url TEXT,
            sub_category TEXT,
            entity_id TEXT,
            entity TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        )
        ''')
        
        # Create entities table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            canonical_name TEXT NOT NULL,
            first_appearance_date TEXT,
            last_appearance_date TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            confidence_score FLOAT,
            mp_id TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create relationships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS relationships (
            relationship_id TEXT PRIMARY KEY,
            mp_name TEXT NOT NULL,
            entity TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            value TEXT,
            date_logged TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Check if entity_id column exists in disclosures, add it if not
        cursor.execute("PRAGMA table_info(disclosures)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "entity_id" not in columns:
            logger.info("Adding entity_id column to disclosures table")
            cursor.execute("ALTER TABLE disclosures ADD COLUMN entity_id TEXT REFERENCES entities(id)")
        
        # Check if sub_category column exists, add it if not
        if "sub_category" not in columns:
            logger.info("Adding sub_category column to disclosures table")
            cursor.execute("ALTER TABLE disclosures ADD COLUMN sub_category TEXT")
        
        conn.commit()
        conn.close()
    
    def store_structured_data(self, structured_data: Dict[str, Any]) -> List[str]:
        """
        Store structured data in the database.
        
        Args:
            structured_data: Dictionary containing structured data extracted from OCR text.
            
        Returns:
            A list of IDs for the inserted disclosure records.
        """
        logger.info(f"Storing structured data for MP: {structured_data.get('mp_name', 'Unknown')}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Get MP information
            mp_name = structured_data.get("mp_name", "Unknown")
            party = structured_data.get("party", "Unknown")
            electorate = structured_data.get("electorate", "Unknown")
            
            # Store disclosures
            disclosure_ids = []
            disclosures = structured_data.get("disclosures", [])
            
            for disclosure in disclosures:
                disclosure_id = str(uuid.uuid4())
                declaration_date = disclosure.get("declaration_date", "Unknown")
                category = disclosure.get("category", "Unknown")
                item = disclosure.get("entity", "Unknown")
                entity = item
                details = disclosure.get("details", "")
                pdf_url = disclosure.get("pdf_url", "")
                sub_category = disclosure.get("sub_category", "")
                
                # Find or create entity
                entity_id = self._find_or_create_entity(
                    cursor, 
                    mp_name, 
                    category, 
                    entity,
                    declaration_date
                )
                
                cursor.execute(
                    """
                    INSERT INTO disclosures 
                    (id, mp_name, party, electorate, declaration_date, category, item, details, pdf_url, sub_category, entity_id, entity) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (disclosure_id, mp_name, party, electorate, declaration_date, category, item, details, pdf_url, sub_category, entity_id, entity)
                )
                
                disclosure_ids.append(disclosure_id)
            
            # Store relationships
            relationships = structured_data.get("relationships", [])
            
            for relationship in relationships:
                relationship_id = str(uuid.uuid4())
                entity = relationship.get("entity", "Unknown")
                relationship_type = relationship.get("relationship_type", "Unknown")
                value = relationship.get("value", "Undisclosed")
                date_logged = relationship.get("date_logged", "Unknown")
                
                cursor.execute(
                    """
                    INSERT INTO relationships 
                    (relationship_id, mp_name, entity, relationship_type, value, date_logged) 
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (relationship_id, mp_name, entity, relationship_type, value, date_logged)
                )
            
            # Commit transaction
            conn.commit()
            
            logger.info(f"Successfully stored structured data for MP: {mp_name}")
            return disclosure_ids
            
        except Exception as e:
            # Rollback transaction on error
            conn.rollback()
            logger.error(f"Error storing structured data: {str(e)}")
            raise
            
        finally:
            conn.close()
    
    def _find_or_create_entity(self, cursor, mp_name: str, category: str, entity_name: str, declaration_date: str) -> str:
        """
        Find an existing entity or create a new one.
        
        Args:
            cursor: Database cursor
            mp_name: Name of the MP
            category: Category of the disclosure
            entity_name: Name of the entity
            declaration_date: Date of the declaration
            
        Returns:
            The ID of the found or created entity
        """
        # Skip if entity is N/A or Unknown
        if entity_name.lower() in ['n/a', 'unknown', 'nil', '']:
            return None
        
        # Normalize entity name
        normalized_name = self._normalize_entity_name(entity_name)
        
        # First, try to find an existing entity for this MP with same entity name regardless of category
        # This helps track the same company/organization across different declarations
        cursor.execute(
            """
            SELECT e.id, e.canonical_name, e.first_appearance_date, e.last_appearance_date, e.entity_type
            FROM entities e
            WHERE e.mp_id = ? AND e.canonical_name = ?
            """,
            (mp_name, normalized_name)
        )
        
        entity = cursor.fetchone()
        
        if entity:
            # Entity exists for this MP, update last_appearance_date if needed
            entity_id = entity[0]
            last_appearance_date = entity[3]
            
            if declaration_date != "Unknown" and (last_appearance_date == "Unknown" or declaration_date > last_appearance_date):
                cursor.execute(
                    """
                    UPDATE entities
                    SET last_appearance_date = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (declaration_date, entity_id)
                )
            
            return entity_id
        else:
            # If not found by name alone, try with category as well (traditional approach)
            cursor.execute(
                """
                SELECT e.id, e.canonical_name, e.first_appearance_date, e.last_appearance_date
                FROM entities e
                WHERE e.mp_id = ? AND e.entity_type = ? AND e.canonical_name = ?
                """,
                (mp_name, category, normalized_name)
            )
            
            entity = cursor.fetchone()
            
            if entity:
                # Entity exists for this MP and category, update last_appearance_date if needed
                entity_id = entity[0]
                last_appearance_date = entity[3]
                
                if declaration_date != "Unknown" and (last_appearance_date == "Unknown" or declaration_date > last_appearance_date):
                    cursor.execute(
                        """
                        UPDATE entities
                        SET last_appearance_date = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (declaration_date, entity_id)
                    )
                
                return entity_id
            else:
                # Create new entity
                entity_id = str(uuid.uuid4())
                
                cursor.execute(
                    """
                    INSERT INTO entities
                    (id, entity_type, canonical_name, first_appearance_date, last_appearance_date, is_active, confidence_score, mp_id, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (entity_id, category, normalized_name, declaration_date, declaration_date, True, 1.0, mp_name, "")
                )
                
                return entity_id
    
    def _normalize_entity_name(self, entity_name: str) -> str:
        """
        Normalize an entity name for consistent matching.
        
        Args:
            entity_name: The original entity name
            
        Returns:
            A normalized version of the entity name
        """
        if not entity_name:
            return ""
        
        # Convert to lowercase
        normalized = entity_name.lower()
        
        # Handle common company name variations
        company_variations = {
            'bhp': ['bhp', 'bhp billiton', 'bhp group', 'broken hill proprietary'],
            'qantas': ['qantas', 'qantas airways', 'qantas airlines'],
            'telstra': ['telstra', 'telstra corporation'],
            'commonwealth bank': ['commonwealth bank', 'cba', 'commonwealth bank of australia'],
            'nab': ['nab', 'national australia bank'],
            'westpac': ['westpac', 'westpac banking corporation'],
            'anz': ['anz', 'australia and new zealand banking group', 'australia & new zealand banking group']
        }
        
        # Check if the normalized name matches any of the variations
        for canonical, variations in company_variations.items():
            if any(variation in normalized for variation in variations):
                return canonical
        
        # Remove common prefixes/suffixes
        normalized = re.sub(r'\b(ltd|limited|inc|incorporated|pty|proprietary|p/l|pty ltd)\b', '', normalized)
        
        # Remove punctuation and extra whitespace
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def batch_store_structured_data(self, structured_data_list: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Store multiple structured data records in the database.
        
        Args:
            structured_data_list: List of dictionaries containing structured data.
            
        Returns:
            A list of lists of disclosure IDs for the inserted records.
        """
        logger.info(f"Batch storing {len(structured_data_list)} structured data records")
        
        disclosure_ids_list = []
        
        for structured_data in structured_data_list:
            try:
                disclosure_ids = self.store_structured_data(structured_data)
                disclosure_ids_list.append(disclosure_ids)
            except Exception as e:
                logger.error(f"Error storing structured data: {str(e)}")
                disclosure_ids_list.append([])
        
        return disclosure_ids_list
    
    def export_to_json(self, output_path: str) -> None:
        """
        Export all data to a JSON file.
        
        Args:
            output_path: Path to the output JSON file.
        """
        logger.info(f"Exporting database to JSON: {output_path}")
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Get all unique MPs
            cursor.execute("SELECT DISTINCT mp_name, party, electorate FROM disclosures")
            mps = [dict(row) for row in cursor.fetchall()]
            
            result = []
            
            # For each MP, get their disclosures and relationships
            for mp in mps:
                mp_name = mp["mp_name"]
                
                # Get disclosures
                cursor.execute("SELECT * FROM disclosures WHERE mp_name = ?", (mp_name,))
                disclosures = [dict(row) for row in cursor.fetchall()]
                
                # Get relationships
                cursor.execute("SELECT * FROM relationships WHERE mp_name = ?", (mp_name,))
                relationships = [dict(row) for row in cursor.fetchall()]
                
                # Create MP record
                mp_record = {
                    "mp_name": mp_name,
                    "party": mp["party"],
                    "electorate": mp["electorate"],
                    "disclosures": disclosures,
                    "relationships": relationships
                }
                
                result.append(mp_record)
            
            # Write to JSON file
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            
            logger.info(f"Successfully exported database to JSON: {output_path}")
            
        except Exception as e:
            logger.error(f"Error exporting database to JSON: {str(e)}")
            raise
            
        finally:
            conn.close()
    
    def get_entity_timeline(self, entity_id: str) -> Dict[str, Any]:
        """
        Get the timeline of a specific entity.
        
        Args:
            entity_id: The ID of the entity
            
        Returns:
            A dictionary containing entity information and its timeline of disclosures
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Get entity information
            cursor.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
            entity_row = cursor.fetchone()
            
            if not entity_row:
                logger.warning(f"Entity not found with ID: {entity_id}")
                return {"entity": {}, "timeline": []}
                
            entity = dict(entity_row)
            
            # Get all disclosures for this entity
            cursor.execute(
                """
                SELECT * FROM disclosures 
                WHERE entity_id = ? 
                ORDER BY declaration_date
                """, 
                (entity_id,)
            )
            
            disclosures = [dict(row) for row in cursor.fetchall()]
            
            return {
                "entity": entity,
                "timeline": disclosures
            }
            
        except Exception as e:
            logger.error(f"Error getting entity timeline: {str(e)}")
            return {"entity": {}, "timeline": []}
            
        finally:
            conn.close()
    
    def get_mp_entities(self, mp_name: str) -> List[Dict[str, Any]]:
        """
        Get all entities for a specific MP.
        
        Args:
            mp_name: The name of the MP
            
        Returns:
            A list of entities owned by the MP
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Get all entities for this MP
            cursor.execute(
                """
                SELECT * FROM entities 
                WHERE mp_id = ? 
                ORDER BY entity_type, canonical_name
                """, 
                (mp_name,)
            )
            
            entities = [dict(row) for row in cursor.fetchall()]
            
            return entities
            
        except Exception as e:
            logger.error(f"Error getting MP entities: {str(e)}")
            return []
            
        finally:
            conn.close()
    
    def get_entity_changes(self, entity_id: str) -> Dict[str, Any]:
        """
        Analyze changes in an entity's timeline.
        
        Args:
            entity_id: The ID of the entity
            
        Returns:
            A dictionary containing analysis of changes over time
        """
        entity_timeline = self.get_entity_timeline(entity_id)
        entity = entity_timeline["entity"]
        timeline = entity_timeline["timeline"]
        
        if not entity or not timeline:
            return {
                "entity_id": entity_id,
                "error": "Entity or timeline not found"
            }
        
        # Sort timeline by declaration date
        timeline = sorted(timeline, key=lambda x: x["declaration_date"])
        
        # Analyze changes
        changes = []
        for i in range(1, len(timeline)):
            prev = timeline[i-1]
            curr = timeline[i]
            
            # Check for changes in details
            if prev["details"] != curr["details"]:
                changes.append({
                    "type": "details_change",
                    "date": curr["declaration_date"],
                    "from": prev["details"],
                    "to": curr["details"]
                })
            
            # Check for changes in category
            if prev["category"] != curr["category"]:
                changes.append({
                    "type": "category_change",
                    "date": curr["declaration_date"],
                    "from": prev["category"],
                    "to": curr["category"]
                })
            
            # Check for changes in sub_category
            if prev.get("sub_category") != curr.get("sub_category"):
                changes.append({
                    "type": "sub_category_change",
                    "date": curr["declaration_date"],
                    "from": prev.get("sub_category"),
                    "to": curr.get("sub_category")
                })
        
        return {
            "entity": entity,
            "first_appearance": timeline[0]["declaration_date"] if timeline else None,
            "last_appearance": timeline[-1]["declaration_date"] if timeline else None,
            "num_appearances": len(timeline),
            "changes": changes
        }
    
    def get_mp_entity_summary(self, mp_name: str) -> Dict[str, Any]:
        """
        Get a summary of all entities for a specific MP.
        
        Args:
            mp_name: The name of the MP
            
        Returns:
            A dictionary containing summary information about the MP's entities
        """
        entities = self.get_mp_entities(mp_name)
        
        if not entities:
            return {
                "mp_name": mp_name,
                "entity_count": 0,
                "entities_by_type": {},
                "error": "No entities found"
            }
        
        # Group entities by type
        entities_by_type = {}
        for entity in entities:
            entity_type = entity["entity_type"]
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)
        
        # Count entities by type
        entity_counts = {
            entity_type: len(entities)
            for entity_type, entities in entities_by_type.items()
        }
        
        return {
            "mp_name": mp_name,
            "entity_count": len(entities),
            "entity_counts_by_type": entity_counts,
            "entities_by_type": entities_by_type
        }
    
    def compare_mp_entities(self, mp_name1: str, mp_name2: str) -> Dict[str, Any]:
        """
        Compare entities between two MPs.
        
        Args:
            mp_name1: Name of the first MP
            mp_name2: Name of the second MP
            
        Returns:
            A dictionary containing comparison results
        """
        entities1 = self.get_mp_entities(mp_name1)
        entities2 = self.get_mp_entities(mp_name2)
        
        # Group entities by type for each MP
        entities1_by_type = {}
        for entity in entities1:
            entity_type = entity["entity_type"]
            if entity_type not in entities1_by_type:
                entities1_by_type[entity_type] = []
            entities1_by_type[entity_type].append(entity)
        
        entities2_by_type = {}
        for entity in entities2:
            entity_type = entity["entity_type"]
            if entity_type not in entities2_by_type:
                entities2_by_type[entity_type] = []
            entities2_by_type[entity_type].append(entity)
        
        # Find common entity types
        common_types = set(entities1_by_type.keys()) & set(entities2_by_type.keys())
        
        # Find common entities (by normalized name)
        common_entities = []
        for entity_type in common_types:
            entities1_names = {self._normalize_entity_name(e["canonical_name"]): e for e in entities1_by_type[entity_type]}
            entities2_names = {self._normalize_entity_name(e["canonical_name"]): e for e in entities2_by_type[entity_type]}
            
            common_names = set(entities1_names.keys()) & set(entities2_names.keys())
            
            for name in common_names:
                common_entities.append({
                    "entity_type": entity_type,
                    "canonical_name": name,
                    "mp1_entity": entities1_names[name],
                    "mp2_entity": entities2_names[name]
                })
        
        return {
            "mp1": mp_name1,
            "mp2": mp_name2,
            "mp1_entity_count": len(entities1),
            "mp2_entity_count": len(entities2),
            "common_entity_count": len(common_entities),
            "common_entities": common_entities
        }
    
    def get_entity_by_name(self, entity_name: str, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find entities by name.
        
        Args:
            entity_name: Name of the entity to search for
            entity_type: Optional type of entity to filter by
            
        Returns:
            A list of matching entities
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Normalize entity name
            normalized_name = self._normalize_entity_name(entity_name)
            
            # Build query
            query = "SELECT * FROM entities WHERE canonical_name LIKE ?"
            params = [f"%{normalized_name}%"]
            
            if entity_type:
                query += " AND entity_type = ?"
                params.append(entity_type)
            
            # Execute query
            cursor.execute(query, params)
            entities = [dict(row) for row in cursor.fetchall()]
            
            return entities
            
        except Exception as e:
            logger.error(f"Error searching for entity: {str(e)}")
            return []
            
        finally:
            conn.close()
    
    def link_existing_disclosures_to_entities(self):
        """
        Link existing disclosures to entities.
        """
        logger.info("Linking existing disclosures to entities")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get all disclosures without entity_id
            cursor.execute(
                """
                SELECT id, mp_name, category, entity, item, declaration_date
                FROM disclosures
                WHERE entity_id IS NULL
                """
            )
            
            disclosures = cursor.fetchall()
            logger.info(f"Found {len(disclosures)} unlinked disclosures")
            
            # Link each disclosure to an entity
            for disclosure in disclosures:
                disclosure_id, mp_name, category, entity, item, declaration_date = disclosure
                
                # If entity is empty but item has a value, use item
                if not entity or entity.lower() in ['n/a', 'unknown', 'nil', '']:
                    entity = item
                
                # Skip if entity is still N/A or Unknown
                if not entity or entity.lower() in ['n/a', 'unknown', 'nil', '']:
                    continue
                
                # Find or create entity
                entity_id = self._find_or_create_entity(
                    cursor, 
                    mp_name, 
                    category, 
                    entity, 
                    declaration_date
                )
                
                # Update disclosure with entity_id
                if entity_id:
                    cursor.execute(
                        """
                        UPDATE disclosures
                        SET entity_id = ?
                        WHERE id = ?
                        """,
                        (entity_id, disclosure_id)
                    )
            
            # Commit transaction
            conn.commit()
            
            logger.info("Successfully linked existing disclosures to entities")
            
        except Exception as e:
            # Rollback transaction on error
            conn.rollback()
            logger.error(f"Error linking disclosures to entities: {str(e)}")
            raise
            
        finally:
            conn.close() 