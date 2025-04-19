#!/usr/bin/env python3
"""
Merge duplicate entities in the database.

This script identifies and merges duplicate entities in the database, 
such as 'BHP' and 'BHP Billiton', ensuring they're treated as the same entity
across different declarations and parliaments.
"""

import os
import argparse
import logging
import sqlite3
import re
from typing import Dict, List, Tuple, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EntityMerger:
    """
    A class to identify and merge duplicate entities in the database.
    """
    
    def __init__(self, db_path: str = "disclosures.db"):
        """
        Initialize the entity merger.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        
        # Define company name mappings - canonical name : list of variations
        self.company_variations = {
            'bhp': ['bhp', 'bhp billiton', 'bhp group', 'broken hill proprietary'],
            'qantas': ['qantas', 'qantas airways', 'qantas airlines'],
            'telstra': ['telstra', 'telstra corporation'],
            'commonwealth bank': ['commonwealth bank', 'cba', 'commonwealth bank of australia'],
            'nab': ['nab', 'national australia bank'],
            'westpac': ['westpac', 'westpac banking corporation'],
            'anz': ['anz', 'australia and new zealand banking group', 'australia & new zealand banking group']
        }
    
    def normalize_entity_name(self, entity_name: str) -> str:
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
        
        # Check if the normalized name matches any of the variations
        for canonical, variations in self.company_variations.items():
            if any(variation in normalized for variation in variations):
                return canonical
        
        # Remove common prefixes/suffixes
        normalized = re.sub(r'\b(ltd|limited|inc|incorporated|pty|proprietary|p/l|pty ltd)\b', '', normalized)
        
        # Remove punctuation and extra whitespace
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def find_duplicate_entities(self) -> List[Dict[str, Any]]:
        """
        Find duplicate entities that should be merged.
        
        Returns:
            A list of groups, where each group is entities that should be merged.
        """
        logger.info("Finding duplicate entities")
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all entities
        cursor.execute("SELECT id, entity_type, canonical_name, mp_id FROM entities")
        entities = [dict(row) for row in cursor.fetchall()]
        
        # Group entities by MP
        entities_by_mp = {}
        for entity in entities:
            mp_id = entity["mp_id"]
            if mp_id not in entities_by_mp:
                entities_by_mp[mp_id] = []
            entities_by_mp[mp_id].append(entity)
        
        # For each MP, find duplicates using our improved normalization
        duplicate_groups = []
        
        for mp_id, mp_entities in entities_by_mp.items():
            # Group by normalized name
            normalized_groups = {}
            
            for entity in mp_entities:
                normalized_name = self.normalize_entity_name(entity["canonical_name"])
                if normalized_name not in normalized_groups:
                    normalized_groups[normalized_name] = []
                normalized_groups[normalized_name].append(entity)
            
            # Add groups with more than one entity (these are duplicates)
            for normalized_name, group in normalized_groups.items():
                if len(group) > 1:
                    duplicate_groups.append({
                        "mp_id": mp_id,
                        "normalized_name": normalized_name,
                        "entities": group
                    })
        
        conn.close()
        
        logger.info(f"Found {len(duplicate_groups)} groups of duplicate entities")
        
        return duplicate_groups
    
    def merge_entity_group(self, group: Dict[str, Any]) -> bool:
        """
        Merge a group of duplicate entities into a single entity.
        
        Args:
            group: A group of duplicate entities
            
        Returns:
            True if merge was successful, False otherwise
        """
        mp_id = group["mp_id"]
        normalized_name = group["normalized_name"]
        entities = group["entities"]
        
        logger.info(f"Merging {len(entities)} entities for MP {mp_id} with normalized name '{normalized_name}'")
        
        if len(entities) < 2:
            logger.warning("Not enough entities to merge")
            return False
        
        # Choose the primary entity (the one to keep)
        # Preference for 'Shares' type if present, otherwise just take the first one
        primary_entity = next((e for e in entities if e["entity_type"].lower() == "shares"), entities[0])
        
        # Get entity IDs to update
        primary_id = primary_entity["id"]
        secondary_ids = [e["id"] for e in entities if e["id"] != primary_id]
        
        logger.info(f"Primary entity: {primary_id} ({primary_entity['canonical_name']})")
        logger.info(f"Secondary entities to merge: {', '.join(secondary_ids)}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Update all disclosures that point to secondary entities to point to primary entity
            cursor.execute(
                """
                UPDATE disclosures
                SET entity_id = ?
                WHERE entity_id IN ({})
                """.format(','.join(['?'] * len(secondary_ids))),
                [primary_id] + secondary_ids
            )
            
            updated_rows = cursor.rowcount
            logger.info(f"Updated {updated_rows} disclosures to point to primary entity")
            
            # Delete the secondary entities
            cursor.execute(
                """
                DELETE FROM entities
                WHERE id IN ({})
                """.format(','.join(['?'] * len(secondary_ids))),
                secondary_ids
            )
            
            deleted_rows = cursor.rowcount
            logger.info(f"Deleted {deleted_rows} secondary entities")
            
            # Update the canonical name of the primary entity if needed
            # For consistency, we use the normalized form
            cursor.execute(
                """
                UPDATE entities
                SET canonical_name = ?
                WHERE id = ?
                """,
                (normalized_name, primary_id)
            )
            
            # Commit transaction
            conn.commit()
            
            logger.info(f"Successfully merged entities for MP {mp_id} with normalized name '{normalized_name}'")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error merging entities: {str(e)}")
            return False
            
        finally:
            conn.close()
    
    def merge_all_duplicates(self) -> int:
        """
        Find and merge all duplicate entities in the database.
        
        Returns:
            The number of entity groups that were successfully merged
        """
        duplicate_groups = self.find_duplicate_entities()
        
        successful_merges = 0
        for group in duplicate_groups:
            if self.merge_entity_group(group):
                successful_merges += 1
        
        logger.info(f"Successfully merged {successful_merges} out of {len(duplicate_groups)} duplicate groups")
        
        return successful_merges
    
    def merge_specific_entities(self, entity_ids: List[str], into_id: str) -> bool:
        """
        Merge specific entities into a target entity by ID.
        
        Args:
            entity_ids: List of entity IDs to merge
            into_id: ID of the target entity to merge into
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Merging entities {', '.join(entity_ids)} into {into_id}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Begin transaction
            conn.execute("BEGIN TRANSACTION")
            
            # Update all disclosures that point to the source entities to point to the target entity
            cursor.execute(
                """
                UPDATE disclosures
                SET entity_id = ?
                WHERE entity_id IN ({})
                """.format(','.join(['?'] * len(entity_ids))),
                [into_id] + entity_ids
            )
            
            updated_rows = cursor.rowcount
            logger.info(f"Updated {updated_rows} disclosures to point to target entity")
            
            # Delete the source entities
            cursor.execute(
                """
                DELETE FROM entities
                WHERE id IN ({})
                """.format(','.join(['?'] * len(entity_ids))),
                entity_ids
            )
            
            deleted_rows = cursor.rowcount
            logger.info(f"Deleted {deleted_rows} source entities")
            
            # Commit transaction
            conn.commit()
            
            logger.info(f"Successfully merged entities {', '.join(entity_ids)} into {into_id}")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error merging entities: {str(e)}")
            return False
            
        finally:
            conn.close()

def main():
    """
    Main function to merge duplicate entities.
    """
    parser = argparse.ArgumentParser(description="Merge duplicate entities in the database")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to SQLite database file")
    parser.add_argument("--auto", action="store_true", help="Automatically merge all detected duplicates")
    parser.add_argument("--merge", nargs="+", metavar="ENTITY_ID", help="Specific entity IDs to merge")
    parser.add_argument("--into", metavar="TARGET_ID", help="Target entity ID to merge into")
    
    args = parser.parse_args()
    
    merger = EntityMerger(db_path=args.db_path)
    
    if args.auto:
        # Automatically merge all duplicates
        merged_count = merger.merge_all_duplicates()
        print(f"Merged {merged_count} groups of duplicate entities")
    
    elif args.merge and args.into:
        # Merge specific entities
        if merger.merge_specific_entities(args.merge, args.into):
            print(f"Successfully merged entities {', '.join(args.merge)} into {args.into}")
        else:
            print("Failed to merge entities")
    
    else:
        # Just find and list duplicates
        duplicate_groups = merger.find_duplicate_entities()
        
        if not duplicate_groups:
            print("No duplicate entities found")
        else:
            print(f"Found {len(duplicate_groups)} groups of duplicate entities:")
            
            for i, group in enumerate(duplicate_groups):
                print(f"\nGroup {i+1}: MP {group['mp_id']}, Normalized: {group['normalized_name']}")
                for entity in group["entities"]:
                    print(f"  - {entity['id']}: {entity['entity_type']} - {entity['canonical_name']}")
            
            print("\nTo merge, use:")
            print("  python merge_entities.py --auto  # Merge all duplicates")
            print("  python merge_entities.py --merge [IDs...] --into [TARGET_ID]  # Merge specific entities")

if __name__ == "__main__":
    main() 