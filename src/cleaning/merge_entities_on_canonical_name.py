#!/usr/bin/env python3
"""
CLI script to merge entities in the main database based on canonical_name.
For each canonical_name, selects a single canonical entity_id (lowest UUID),
updates all disclosures to reference it, and marks obsolete entities as merged.
Idempotent, supports dry-run and verbose modes, and logs all changes.

Usage:
    python merge_entities_on_canonical_name.py [--db-path disclosures.db] [--dry-run] [--verbose]

TODO:
- Implement logic to mark obsolete entities (e.g., set notes='merged' or similar).
- Add more robust logging and error handling as needed.
"""

import argparse
import sqlite3
from typing import List, Dict, Any, Tuple
import sys
import os

DEFAULT_DB_PATH = "disclosures.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge entities on canonical_name and update disclosures.")
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH, help='Path to main disclosures database (default: disclosures.db)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done, but do not modify the database')
    parser.add_argument('--verbose', action='store_true', help='Print detailed logs')
    return parser.parse_args()


def fetch_entities_by_canonical_name(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch all entities grouped by canonical_name."""
    cursor = conn.cursor()
    cursor.execute("SELECT entity_id, canonical_name, iteration, notes FROM entities")
    rows = cursor.fetchall()
    entities_by_name: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        entity = {
            'entity_id': row[0],
            'canonical_name': row[1],
            'iteration': row[2],
            'notes': row[3],
        }
        entities_by_name.setdefault(entity['canonical_name'], []).append(entity)
    return entities_by_name


def update_disclosures_and_entities(conn: sqlite3.Connection, entities_by_name: Dict[str, List[Dict[str, Any]]], dry_run: bool = False, verbose: bool = False) -> Tuple[int, int, int]:
    """
    For each canonical_name, select a canonical entity_id (lowest UUID),
    update all disclosures to reference it, and mark obsolete entities as merged.
    Returns (disclosures_updated, entities_merged, canonical_entities).
    """
    disclosures_updated = 0
    entities_merged = 0
    canonical_entities = 0
    cursor = conn.cursor()
    for canonical_name, entities in entities_by_name.items():
        if not entities:
            continue
        # Select canonical entity_id (lowest UUID)
        canonical_entity = min(entities, key=lambda e: e['entity_id'])
        canonical_id = canonical_entity['entity_id']
        canonical_entities += 1
        # All other entity_ids are obsolete
        obsolete_entities = [e for e in entities if e['entity_id'] != canonical_id]
        obsolete_ids = [e['entity_id'] for e in obsolete_entities]
        if obsolete_ids:
            # Update disclosures to point to canonical_id
            if not dry_run:
                cursor.execute(
                    f"""
                    UPDATE disclosures
                    SET entity_id = ?
                    WHERE entity_id IN ({','.join(['?']*len(obsolete_ids))})
                    """,
                    (canonical_id, *obsolete_ids)
                )
            count = cursor.rowcount if not dry_run else 0
            disclosures_updated += count
            if verbose:
                print(f"Updated {count} disclosures to canonical entity_id {canonical_id} for '{canonical_name}'")
            # Mark obsolete entities as merged (set notes='merged')
            for eid in obsolete_ids:
                if not dry_run:
                    cursor.execute(
                        "UPDATE entities SET notes = ? WHERE entity_id = ?",
                        ("merged", eid)
                    )
                entities_merged += 1
                if verbose:
                    print(f"Marked entity {eid} as merged (obsolete) for '{canonical_name}'")
        else:
            if verbose:
                print(f"'{canonical_name}' already has a single canonical entity_id: {canonical_id}")
    return disclosures_updated, entities_merged, canonical_entities


def main() -> None:
    args = parse_args()
    if not os.path.exists(args.db_path):
        print(f"Error: Main database not found at {args.db_path}")
        sys.exit(1)
    conn = sqlite3.connect(args.db_path)
    try:
        entities_by_name = fetch_entities_by_canonical_name(conn)
        if args.verbose:
            print(f"Fetched {sum(len(v) for v in entities_by_name.values())} entities grouped into {len(entities_by_name)} canonical names.")
        disclosures_updated, entities_merged, canonical_entities = update_disclosures_and_entities(
            conn, entities_by_name, dry_run=args.dry_run, verbose=args.verbose
        )
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()
    print(f"Summary: {disclosures_updated} disclosures updated, {entities_merged} entities merged, {canonical_entities} canonical entities.")
    if args.dry_run:
        print("(Dry run: no changes were made.)")

if __name__ == "__main__":
    main() 