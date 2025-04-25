#!/usr/bin/env python3
"""
CLI script to link disclosures to entities by copying each unique non-nil raw_entity from disclosures into entities (if not present),
and updating disclosures.entity_id to point to the correct entity. Uses canonical schema only.
"""
import argparse
import sqlite3
import uuid
from typing import Dict, Set, Optional

NIL_VALUES = {None, '', 'n/a', 'nil', 'unknown', 'not applicable', 'none'}

def normalize_entity(entity: Optional[str]) -> str:
    if not entity:
        return ''
    return entity.strip().lower()

def main():
    parser = argparse.ArgumentParser(description="Link disclosures to entities by raw_entity.")
    parser.add_argument('--db-path', type=str, default='disclosures.db', help='Path to the SQLite database')
    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Fetch all unique non-nil raw_entity values from disclosures
    cur.execute("SELECT DISTINCT raw_entity FROM disclosures WHERE raw_entity IS NOT NULL")
    raw_entities = {row['raw_entity'] for row in cur.fetchall()}
    filtered_entities = {e for e in raw_entities if normalize_entity(e) not in NIL_VALUES}

    # 2. Build mapping: canonical_name -> entity_id (existing)
    cur.execute("SELECT entity_id, canonical_name FROM entities")
    entity_map: Dict[str, str] = {normalize_entity(row['canonical_name']): row['entity_id'] for row in cur.fetchall()}

    # 3. Insert new entities for any missing canonical_name
    new_entities = []
    for entity in filtered_entities:
        norm = normalize_entity(entity)
        if norm not in entity_map:
            entity_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO entities (entity_id, canonical_name, iteration, status, notes) VALUES (?, ?, ?, ?, ?)",
                (entity_id, entity.strip(), 1, 'pending_review', None)
            )
            entity_map[norm] = entity_id
            new_entities.append((entity_id, entity.strip()))
    conn.commit()

    # 4. Update disclosures.entity_id for each disclosure with a matching raw_entity
    updated_count = 0
    for entity in filtered_entities:
        norm = normalize_entity(entity)
        entity_id = entity_map[norm]
        cur.execute(
            "UPDATE disclosures SET entity_id = ? WHERE raw_entity = ?",
            (entity_id, entity)
        )
        updated_count += cur.rowcount
    conn.commit()

    print(f"Linked {len(filtered_entities)} unique entities.")
    print(f"Inserted {len(new_entities)} new entities into the entities table.")
    print(f"Updated {updated_count} disclosures with entity_id.")

    conn.close()

if __name__ == "__main__":
    main() 