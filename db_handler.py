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

# Standardized categories for disclosures
class Categories:
    """Standard categories for disclosures."""
    ASSET = "Asset"
    LIABILITY = "Liability"
    INCOME = "Income"
    MEMBERSHIP = "Membership"
    GIFT = "Gift"
    TRAVEL = "Travel"
    UNKNOWN = "Unknown"
    
    # List of all valid categories
    ALL = [ASSET, LIABILITY, INCOME, MEMBERSHIP, GIFT, TRAVEL, UNKNOWN]

# Subcategories for each main category
class Subcategories:
    """Subcategories for each category."""
    # Asset subcategories
    ASSET_REAL_ESTATE = "Real Estate"
    ASSET_SHARES = "Shares"
    ASSET_TRUST = "Trust"
    ASSET_OTHER = "Other Asset"
    
    # Liability subcategories
    LIABILITY_MORTGAGE = "Mortgage"
    LIABILITY_LOAN = "Loan"
    LIABILITY_CREDIT = "Credit"
    LIABILITY_OTHER = "Other Liability"
    
    # Income subcategories
    INCOME_SALARY = "Salary"
    INCOME_DIVIDEND = "Dividend"
    INCOME_OTHER = "Other Income"
    
    # Membership subcategories
    MEMBERSHIP_PROFESSIONAL = "Professional"
    MEMBERSHIP_OTHER = "Other Membership"
    
    # Gift subcategories
    GIFT_HOSPITALITY = "Hospitality"
    GIFT_ENTERTAINMENT = "Entertainment"
    GIFT_TRAVEL = "Travel Gift"
    GIFT_DECORATIVE = "Decorative"
    GIFT_ELECTRONICS = "Electronics"
    GIFT_OTHER = "Other Gift"
    
    # Travel subcategories
    TRAVEL_AIR = "Air Travel"
    TRAVEL_OTHER = "Other Travel"
    
    # Mapping from categories to their subcategories
    MAPPING = {
        Categories.ASSET: [ASSET_REAL_ESTATE, ASSET_SHARES, ASSET_TRUST, ASSET_OTHER],
        Categories.LIABILITY: [LIABILITY_MORTGAGE, LIABILITY_LOAN, LIABILITY_CREDIT, LIABILITY_OTHER],
        Categories.INCOME: [INCOME_SALARY, INCOME_DIVIDEND, INCOME_OTHER],
        Categories.MEMBERSHIP: [MEMBERSHIP_PROFESSIONAL, MEMBERSHIP_OTHER],
        Categories.GIFT: [GIFT_HOSPITALITY, GIFT_ENTERTAINMENT, GIFT_TRAVEL, GIFT_DECORATIVE, GIFT_ELECTRONICS, GIFT_OTHER],
        Categories.TRAVEL: [TRAVEL_AIR, TRAVEL_OTHER],
        Categories.UNKNOWN: ["Other"]
    }

# Temporal types for disclosures
class TemporalTypes:
    ONE_TIME = "one-time"    # A single occurrence (e.g., a gift)
    RECURRING = "recurring"  # Repeats periodically (e.g., dividend payment)
    ONGOING = "ongoing"      # Continues indefinitely (e.g., share ownership)
    
    # List of all valid temporal types
    ALL = [ONE_TIME, RECURRING, ONGOING]

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
            mp_name TEXT,
            party TEXT,
            electorate TEXT,
            declaration_date TEXT,
            category TEXT CHECK(category IN (
                'Asset', 'Income', 'Gift', 'Travel', 'Liability', 'Membership', 'Unknown'
            )),
            sub_category TEXT,
            item TEXT,
            temporal_type TEXT CHECK(temporal_type IN ('one-time', 'recurring', 'ongoing')),
            start_date TEXT,
            end_date TEXT,
            details TEXT,
            pdf_url TEXT,
            entity_id TEXT,
            entity TEXT,
            FOREIGN KEY (entity_id) REFERENCES entities(id)
        )
        ''')
        
        # Create entities table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            entity_type TEXT,
            canonical_name TEXT,
            normalized_name TEXT,
            mp_id TEXT,
            UNIQUE (normalized_name, entity_type, mp_id)
        )
        ''')
        
        # Create relationships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS relationships (
            relationship_id TEXT PRIMARY KEY,
            mp_name TEXT,
            entity TEXT,
            relationship_type TEXT,
            value TEXT,
            date_logged TEXT
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
        
        # Check if temporal_type column exists, add it if not
        if "temporal_type" not in columns:
            logger.info("Adding temporal_type column to disclosures table")
            cursor.execute("ALTER TABLE disclosures ADD COLUMN temporal_type TEXT")
        
        # Check if start_date column exists, add it if not
        if "start_date" not in columns:
            logger.info("Adding start_date column to disclosures table")
            cursor.execute("ALTER TABLE disclosures ADD COLUMN start_date TEXT")
        
        # Check if end_date column exists, add it if not
        if "end_date" not in columns:
            logger.info("Adding end_date column to disclosures table")
            cursor.execute("ALTER TABLE disclosures ADD COLUMN end_date TEXT")
        
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
                
                # Get category info
                category = disclosure.get("category", "Unknown")
                
                # Enforce category standards
                if category not in Categories.ALL:
                    logger.warning(f"Invalid category '{category}' detected. Converting to appropriate category if possible.")
                    # Try to determine the most appropriate category
                    matched = False
                    
                    # Special case mapping for common legacy categories
                    special_mapping = {
                        "Liabilities": Categories.LIABILITY,
                        "Savings/Investments": Categories.ASSET,
                        "Partnerships": Categories.MEMBERSHIP,
                        "Directorships": Categories.MEMBERSHIP,
                        "Other Interests": Categories.UNKNOWN
                    }
                    
                    if category in special_mapping:
                        category = special_mapping[category]
                        matched = True
                    else:
                        # Try general matching
                        for cat_name, cat_value in vars(Categories).items():
                            if cat_name.isupper() and isinstance(cat_value, str):
                                if category.lower() in cat_value.lower():
                                    category = cat_value
                                    matched = True
                                    break
                    
                    if not matched:
                        logger.warning(f"Could not match to standard category. Using 'Unknown'.")
                        category = Categories.UNKNOWN
                
                # Handle subcategory
                sub_category = disclosure.get("sub_category", "")
                
                # If no subcategory provided but we can infer it
                if not sub_category and category in Categories.ALL:
                    category_mapping = {
                        "Shares": Subcategories.ASSET_SHARES,
                        "Real Estate": Subcategories.ASSET_REAL_ESTATE,
                        "Trust": Subcategories.ASSET_TRUST,
                        "Directorships": Subcategories.MEMBERSHIP_PROFESSIONAL,
                        "Hospitality": Subcategories.GIFT_HOSPITALITY
                    }
                    
                    # Check if the disclosure details help determine subcategory
                    details = disclosure.get("details", "").lower()
                    if "mortgage" in details:
                        sub_category = Subcategories.LIABILITY_MORTGAGE
                    elif "loan" in details:
                        sub_category = Subcategories.LIABILITY_LOAN
                    elif "credit" in details:
                        sub_category = Subcategories.LIABILITY_CREDIT
                    elif "ticket" in details and "sport" in details:
                        sub_category = Subcategories.GIFT_ENTERTAINMENT
                    
                    # Default to generic subcategory if needed
                    if not sub_category:
                        if category == Categories.ASSET:
                            sub_category = Subcategories.ASSET_OTHER
                        elif category == Categories.LIABILITY:
                            sub_category = Subcategories.LIABILITY_OTHER
                        elif category == Categories.INCOME:
                            sub_category = Subcategories.INCOME_OTHER
                        elif category == Categories.MEMBERSHIP:
                            sub_category = Subcategories.MEMBERSHIP_OTHER
                        elif category == Categories.GIFT:
                            sub_category = Subcategories.GIFT_OTHER
                        elif category == Categories.TRAVEL:
                            sub_category = Subcategories.TRAVEL_OTHER
                
                # Item and entity information
                item = disclosure.get("entity", "Unknown")
                entity = item
                details = disclosure.get("details", "")
                pdf_url = disclosure.get("pdf_url", "")
                
                # Determine temporal type based on category
                temporal_type = disclosure.get("temporal_type", "")
                if not temporal_type:
                    if category == Categories.ASSET:
                        temporal_type = TemporalTypes.ONGOING
                    elif category == Categories.LIABILITY:
                        temporal_type = TemporalTypes.ONGOING
                    elif category == Categories.INCOME:
                        if sub_category and isinstance(sub_category, str) and ("dividend" in sub_category.lower() or "salary" in sub_category.lower()):
                            temporal_type = TemporalTypes.RECURRING
                        else:
                            temporal_type = TemporalTypes.ONE_TIME
                    elif category == Categories.MEMBERSHIP:
                        temporal_type = TemporalTypes.RECURRING
                    elif category == Categories.GIFT or category == Categories.TRAVEL:
                        temporal_type = TemporalTypes.ONE_TIME
                    else:
                        temporal_type = TemporalTypes.ONE_TIME  # Default
                
                # Start and end dates (if available)
                start_date = disclosure.get("start_date", declaration_date)
                end_date = disclosure.get("end_date", "")
                
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
                    (id, mp_name, party, electorate, declaration_date, category, sub_category, 
                    item, temporal_type, start_date, end_date, details, pdf_url, entity_id, entity) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (disclosure_id, mp_name, party, electorate, declaration_date, category, sub_category, 
                    item, temporal_type, start_date, end_date, details, pdf_url, entity_id, entity)
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
    
    def _find_or_create_entity(self, cursor, mp_name, entity_type, canonical_name, first_appearance_date=None):
        """
        Find an existing entity or create a new one.
        
        Args:
            cursor: Database cursor
            mp_name: Name of the MP
            entity_type: Type of entity (e.g., 'Shares', 'Trust', etc.)
            canonical_name: Canonical name of the entity
            first_appearance_date: First date this entity appeared in a disclosure
            
        Returns:
            Entity ID
        """
        if not canonical_name or canonical_name == "Unknown":
            return None
        
        # Normalize the entity name for matching
        normalized_name = self._normalize_entity_name(canonical_name)
        
        # Look for existing entity
        cursor.execute(
            "SELECT id FROM entities WHERE normalized_name = ? AND entity_type = ? AND mp_id = ?",
            (normalized_name, entity_type, mp_name)
        )
        
        result = cursor.fetchone()
        
        if result:
            # Found existing entity
            return result[0]
        else:
            # Create new entity
            entity_id = str(uuid.uuid4())
            
            cursor.execute(
                """
                INSERT INTO entities 
                (id, entity_type, canonical_name, normalized_name, mp_id) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (entity_id, entity_type, canonical_name, normalized_name, mp_name)
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
        Link existing disclosures to entities and ensure they adhere to the standardized category system.
        """
        logger.info("Linking existing disclosures to entities and standardizing categories")
        
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
            
            unlinked_disclosures = cursor.fetchall()
            logger.info(f"Found {len(unlinked_disclosures)} unlinked disclosures")
            
            # Link each disclosure to an entity
            linked_count = 0
            for disclosure in unlinked_disclosures:
                disclosure_id, mp_name, category, entity, item, declaration_date = disclosure
                
                # If entity is empty but item has a value, use item
                if not entity or entity.lower() in ['n/a', 'unknown', 'nil', '']:
                    entity = item
                
                # Skip if entity is still N/A or Unknown
                if not entity or entity.lower() in ['n/a', 'unknown', 'nil', '']:
                    continue
                
                # Ensure category is valid
                original_category = category
                if category not in Categories.ALL:
                    # Try to determine the most appropriate category
                    matched = False
                    
                    # Special case mapping for common legacy categories
                    special_mapping = {
                        "Liabilities": Categories.LIABILITY,
                        "Savings/Investments": Categories.ASSET,
                        "Partnerships": Categories.MEMBERSHIP,
                        "Directorships": Categories.MEMBERSHIP,
                        "Other Interests": Categories.UNKNOWN
                    }
                    
                    if category in special_mapping:
                        category = special_mapping[category]
                        matched = True
                    else:
                        # Try general matching
                        for cat_name, cat_value in vars(Categories).items():
                            if cat_name.isupper() and isinstance(cat_value, str):
                                if category.lower() in cat_value.lower():
                                    category = cat_value
                                    matched = True
                                    break
                    
                    if not matched:
                        logger.warning(f"Could not match '{category}' to standard category. Using 'Unknown'.")
                        category = Categories.UNKNOWN
                
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
                    linked_count += 1
            
            logger.info(f"Linked {linked_count} disclosures to entities")
            
            # Update categories for all disclosures to ensure standardization
            cursor.execute(
                """
                SELECT id, category, sub_category, details
                FROM disclosures
                """
            )
            
            all_disclosures = cursor.fetchall()
            updated_count = 0
            
            for disclosure in all_disclosures:
                disclosure_id, category, sub_category, details = disclosure
                
                # Ensure category is valid
                original_category = category
                if category not in Categories.ALL:
                    # Try to determine the most appropriate category
                    matched = False
                    
                    # Special case mapping for common legacy categories
                    special_mapping = {
                        "Liabilities": Categories.LIABILITY,
                        "Savings/Investments": Categories.ASSET,
                        "Partnerships": Categories.MEMBERSHIP,
                        "Directorships": Categories.MEMBERSHIP,
                        "Other Interests": Categories.UNKNOWN
                    }
                    
                    if category in special_mapping:
                        category = special_mapping[category]
                        matched = True
                    else:
                        # Try general matching
                        for cat_name, cat_value in vars(Categories).items():
                            if cat_name.isupper() and isinstance(cat_value, str):
                                if category.lower() in cat_value.lower():
                                    category = cat_value
                                    matched = True
                                    break
                    
                    if not matched:
                        logger.warning(f"Could not match '{category}' to standard category. Using 'Unknown'.")
                        category = Categories.UNKNOWN
                
                # Ensure subcategory is appropriate
                if not sub_category or (category in Categories.ALL and sub_category not in Subcategories.MAPPING.get(category, [])):
                    # Check if details help determine subcategory
                    details_text = details.lower() if details else ""
                    
                    if category == Categories.ASSET:
                        if "shares" in details_text or "stock" in details_text:
                            sub_category = Subcategories.ASSET_SHARES
                        elif "real estate" in details_text or "property" in details_text:
                            sub_category = Subcategories.ASSET_REAL_ESTATE
                        elif "trust" in details_text:
                            sub_category = Subcategories.ASSET_TRUST
                        else:
                            sub_category = Subcategories.ASSET_OTHER
                    elif category == Categories.LIABILITY:
                        if "mortgage" in details_text:
                            sub_category = Subcategories.LIABILITY_MORTGAGE
                        elif "loan" in details_text:
                            sub_category = Subcategories.LIABILITY_LOAN
                        elif "credit" in details_text:
                            sub_category = Subcategories.LIABILITY_CREDIT
                        else:
                            sub_category = Subcategories.LIABILITY_OTHER
                    elif category == Categories.INCOME:
                        if "dividend" in details_text:
                            sub_category = Subcategories.INCOME_DIVIDEND
                        elif "salary" in details_text or "wage" in details_text:
                            sub_category = Subcategories.INCOME_SALARY
                        else:
                            sub_category = Subcategories.INCOME_OTHER
                    elif category == Categories.MEMBERSHIP:
                        if "director" in details_text or "board" in details_text or "professional" in details_text:
                            sub_category = Subcategories.MEMBERSHIP_PROFESSIONAL
                        else:
                            sub_category = Subcategories.MEMBERSHIP_OTHER
                    elif category == Categories.GIFT:
                        if "ticket" in details_text and ("sport" in details_text or "entertainment" in details_text):
                            sub_category = Subcategories.GIFT_ENTERTAINMENT
                        elif "hospitality" in details_text or "dinner" in details_text or "lunch" in details_text:
                            sub_category = Subcategories.GIFT_HOSPITALITY
                        else:
                            sub_category = Subcategories.GIFT_OTHER
                    elif category == Categories.TRAVEL:
                        if "flight" in details_text or "air" in details_text:
                            sub_category = Subcategories.TRAVEL_AIR
                        else:
                            sub_category = Subcategories.TRAVEL_OTHER
                    else:
                        sub_category = "Other"
                
                # Set temporal type based on category
                temporal_type = None
                cursor.execute("SELECT temporal_type FROM disclosures WHERE id = ?", (disclosure_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    temporal_type = result[0]
                
                if not temporal_type:
                    if category == Categories.ASSET:
                        temporal_type = TemporalTypes.ONGOING
                    elif category == Categories.LIABILITY:
                        temporal_type = TemporalTypes.ONGOING
                    elif category == Categories.INCOME:
                        if sub_category == Subcategories.INCOME_DIVIDEND or sub_category == Subcategories.INCOME_SALARY:
                            temporal_type = TemporalTypes.RECURRING
                        else:
                            temporal_type = TemporalTypes.ONE_TIME
                    elif category == Categories.MEMBERSHIP:
                        temporal_type = TemporalTypes.RECURRING
                    else:  # Gift, Travel, or Unknown
                        temporal_type = TemporalTypes.ONE_TIME
                
                # Update the disclosure with corrected category, subcategory, and temporal_type
                if category != original_category or sub_category != disclosure[2] or not temporal_type:
                    cursor.execute(
                        """
                        UPDATE disclosures
                        SET category = ?, sub_category = ?, temporal_type = ?
                        WHERE id = ?
                        """,
                        (category, sub_category, temporal_type, disclosure_id)
                    )
                    updated_count += 1
            
            conn.commit()
            logger.info(f"Updated categories for {updated_count} disclosures")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error linking disclosures to entities: {str(e)}")
            conn.rollback()
            raise
            
        finally:
            conn.close()
    
    def get_disclosure_patterns(self, mp_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze disclosure patterns by category and temporal type.
        
        Args:
            mp_name: Optional MP name to filter by
            
        Returns:
            A dictionary containing pattern analysis
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Base query
            query = """
                SELECT 
                    category, 
                    sub_category, 
                    temporal_type, 
                    strftime('%Y', declaration_date) as year,
                    COUNT(*) as count
                FROM disclosures
                WHERE category IS NOT NULL
            """
            params = []
            
            # Add MP filter if provided
            if mp_name:
                query += " AND mp_name = ?"
                params.append(mp_name)
            
            # Group and order
            query += """
                GROUP BY category, sub_category, temporal_type, year
                ORDER BY year, category, sub_category
            """
            
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            
            # Organize results
            categories = {}
            temporal_types = {}
            yearly_trends = {}
            
            for row in results:
                category = row["category"]
                sub_category = row["sub_category"]
                temporal_type = row["temporal_type"]
                year = row["year"]
                count = row["count"]
                
                # Categories breakdown
                if category not in categories:
                    categories[category] = {
                        "total": 0,
                        "subcategories": {}
                    }
                
                categories[category]["total"] += count
                
                if sub_category:
                    if sub_category not in categories[category]["subcategories"]:
                        categories[category]["subcategories"][sub_category] = 0
                    categories[category]["subcategories"][sub_category] += count
                
                # Temporal types breakdown
                if temporal_type:
                    if temporal_type not in temporal_types:
                        temporal_types[temporal_type] = 0
                    temporal_types[temporal_type] += count
                
                # Yearly trends
                if year:
                    if year not in yearly_trends:
                        yearly_trends[year] = {
                            "total": 0,
                            "categories": {}
                        }
                    
                    yearly_trends[year]["total"] += count
                    
                    if category not in yearly_trends[year]["categories"]:
                        yearly_trends[year]["categories"][category] = 0
                    
                    yearly_trends[year]["categories"][category] += count
            
            # Get some details about persistence of items over time
            query = """
                SELECT
                    category,
                    entity_id,
                    COUNT(DISTINCT strftime('%Y', declaration_date)) as years_present
                FROM disclosures
                WHERE entity_id IS NOT NULL
            """
            
            if mp_name:
                query += " AND mp_name = ?"
            
            query += """
                GROUP BY category, entity_id
                ORDER BY years_present DESC
            """
            
            cursor.execute(query, params)
            persistence_results = [dict(row) for row in cursor.fetchall()]
            
            # Analyze persistence
            persistence = {
                "long_term": [],  # Items persisting for 3+ years
                "medium_term": [], # Items persisting for 2 years
                "short_term": []  # Items appearing only in 1 year
            }
            
            for row in persistence_results:
                entity_id = row["entity_id"]
                years = row["years_present"]
                category = row["category"]
                
                # Get entity details
                cursor.execute(
                    """
                    SELECT canonical_name, entity_type
                    FROM entities
                    WHERE id = ?
                    """,
                    (entity_id,)
                )
                
                entity_row = cursor.fetchone()
                if entity_row:
                    entity_name = entity_row["canonical_name"]
                    entity_type = entity_row["entity_type"]
                    
                    item = {
                        "entity_id": entity_id,
                        "name": entity_name,
                        "type": entity_type,
                        "category": category,
                        "years": years
                    }
                    
                    if years >= 3:
                        persistence["long_term"].append(item)
                    elif years == 2:
                        persistence["medium_term"].append(item)
                    else:
                        persistence["short_term"].append(item)
            
            return {
                "categories": categories,
                "temporal_types": temporal_types,
                "yearly_trends": yearly_trends,
                "persistence": persistence
            }
            
        except Exception as e:
            logger.error(f"Error analyzing disclosure patterns: {str(e)}")
            return {}
            
        finally:
            conn.close() 