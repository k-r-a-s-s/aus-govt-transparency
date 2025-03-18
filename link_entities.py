#!/usr/bin/env python3
"""
Link existing disclosures to entities.

This script processes all existing disclosures and links them to entities in the database.
"""

import os
import argparse
import logging
from db_handler import DatabaseHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def link_entities(db_path: str):
    """
    Link existing disclosures to entities.
    
    Args:
        db_path: Path to the SQLite database file.
    """
    logger.info(f"Linking entities in database: {db_path}")
    
    # Initialize database handler
    db_handler = DatabaseHandler(db_path=db_path)
    
    # Link existing disclosures to entities
    db_handler.link_existing_disclosures_to_entities()
    
    logger.info("Entity linking complete")

def main():
    """
    Main function to link entities.
    """
    parser = argparse.ArgumentParser(description="Link existing disclosures to entities")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to SQLite database file")
    
    args = parser.parse_args()
    
    link_entities(args.db_path)

if __name__ == "__main__":
    main() 