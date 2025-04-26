#!/usr/bin/env python3
"""
CLI script to import all canonicalized entities from the entity grouping database
(outputs/entity_grouping/entity_grouping.db, table: entity_canonicalization)
into the main database's entities table. Idempotent and safe for repeated use.

Usage:
    python import_canonical_entities.py [--db-path disclosures.db] [--entity-grouping-db outputs/entity_grouping/entity_grouping.db] [--dry-run] [--verbose]

Notes:
- Only fields present in the main schema are used: entity_id, canonical_name, iteration (from iteration_finalized), notes (original_name).
- The status and updated_at fields from the grouping DB are ignored.
"""

import argparse
import sqlite3
from typing import List, Dict, Any, Tuple
import sys
import os

DEFAULT_DB_PATH = "disclosures.db"
DEFAULT_ENTITY_GROUPING_DB = "outputs/entity_grouping/entity_grouping.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import canonicalized entities into main database.")
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH, help='Path to main disclosures database (default: disclosures.db)')
    parser.add_argument('--entity-grouping-db', type=str, default=DEFAULT_ENTITY_GROUPING_DB, help='Path to entity grouping database (default: outputs/entity_grouping/entity_grouping.db)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done, but do not modify the database')
    parser.add_argument('--verbose', action='store_true', help='Print detailed logs')
    return parser.parse_args()


def fetch_canonical_entities(entity_grouping_db: str) -> List[Dict[str, Any]]:
    """Fetch all rows from entity_canonicalization table."""
    conn = sqlite3.connect(entity_grouping_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM entity_canonicalization")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def upsert_entity(conn: sqlite3.Connection, entity: Dict[str, Any], dry_run: bool = False) -> str:
    """
    Insert or update an entity in the entities table. Returns 'inserted', 'updated', or 'skipped'.
    Only fields present in the main schema are used. Maps iteration_finalized -> iteration. Ignores status and updated_at.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT entity_id, canonical_name, iteration, notes FROM entities WHERE entity_id = ?", (entity['entity_id'],))
    existing = cursor.fetchone()
    # Map fields
    canonical_name = entity.get('canonical_name')
    iteration = entity.get('iteration_finalized')
    notes = entity.get('original_name')  # Store original_name in notes for audit
    if existing:
        # Compare fields to see if update is needed
        update_needed = (
            canonical_name != existing[1] or
            iteration != existing[2] or
            notes != existing[3]
        )
        if update_needed:
            if not dry_run:
                cursor.execute(
                    """
                    UPDATE entities SET
                        canonical_name = ?,
                        iteration = ?,
                        notes = ?
                    WHERE entity_id = ?
                    """,
                    (
                        canonical_name,
                        iteration,
                        notes,
                        entity['entity_id'],
                    )
                )
            return 'updated'
        else:
            return 'skipped'
    else:
        if not dry_run:
            cursor.execute(
                """
                INSERT INTO entities (entity_id, canonical_name, iteration, notes)
                VALUES (?, ?, ?, ?)
                """,
                (
                    entity['entity_id'],
                    canonical_name,
                    iteration,
                    notes,
                )
            )
        return 'inserted'


def main() -> None:
    args = parse_args()
    if not os.path.exists(args.entity_grouping_db):
        print(f"Error: Entity grouping DB not found at {args.entity_grouping_db}")
        sys.exit(1)
    if not os.path.exists(args.db_path):
        print(f"Error: Main database not found at {args.db_path}")
        sys.exit(1)
    entities = fetch_canonical_entities(args.entity_grouping_db)
    if args.verbose:
        print(f"Fetched {len(entities)} canonicalized entities from grouping DB.")
    inserted, updated, skipped = 0, 0, 0
    conn = sqlite3.connect(args.db_path)
    try:
        for entity in entities:
            result = upsert_entity(conn, entity, dry_run=args.dry_run)
            if result == 'inserted':
                inserted += 1
                if args.verbose:
                    print(f"Inserted entity: {entity['entity_id']} ({entity.get('canonical_name')})")
            elif result == 'updated':
                updated += 1
                if args.verbose:
                    print(f"Updated entity: {entity['entity_id']} ({entity.get('canonical_name')})")
            else:
                skipped += 1
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()
    print(f"Summary: {inserted} inserted, {updated} updated, {skipped} skipped.")
    if args.dry_run:
        print("(Dry run: no changes were made.)")

if __name__ == "__main__":
    main() 