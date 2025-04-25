#!/usr/bin/env python3
"""
Link disclosures to canonical entities in the database.

This script links each disclosure's raw_entity to a canonical entity in the entities table via entity_id,
using the DatabaseHandler.link_existing_disclosures_to_entities() method.
"""

import argparse
import logging
import sys
from src.preparation.db_handler import DatabaseHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Link disclosures to canonical entities in the database."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="disclosures.db",
        help="Path to the SQLite database file (default: disclosures.db)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="(Not yet implemented) Show what would be done without modifying the database."
    )
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    logger.info(f"Linking disclosures to entities in database: {args.db_path}")
    if args.dry_run:
        logger.warning("--dry-run is not yet implemented. Proceeding with actual changes.")
    try:
        db = DatabaseHandler(db_path=args.db_path)
        db.link_existing_disclosures_to_entities()
        logger.info("Entity linking complete.")
    except Exception as e:
        logger.error(f"Error during entity linking: {e}")
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main() 