#!/usr/bin/env python3

import os
import sqlite3
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get database path from environment variable or use default
DB_PATH = os.getenv('DB_PATH', '../disclosures.db')

# Define party mappings to political blocs
PARTY_TO_BLOC = {
    # Coalition parties
    'Liberal Party of Australia': 'Coalition',
    'Liberal National Party': 'Coalition',
    'Liberal/Independent': 'Coalition',
    'National Party of Australia': 'Coalition',
    'Nationals WA': 'Coalition',
    'Country Liberal': 'Coalition',
    'LNP': 'Coalition',
    
    # Labor parties
    'Australian Labor Party': 'Labor',
    'Labor/Independent': 'Labor',
    
    # Greens
    'Australian Greens': 'Greens',
    
    # Other parties keep their original names
    'Independent': 'Independent',
    'Centre Alliance': 'Centre Alliance',
    'Katter\'s Australian Party': 'Katter\'s Australian Party',
    'Palmer United': 'Palmer United',
    'N/A': 'Unknown',
}

def check_column_exists(conn, table, column):
    """Check if a column exists in a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [info[1] for info in cursor.fetchall()]
    return column in columns

def add_political_bloc_column(conn):
    """Add a political_bloc column to the disclosures table if it doesn't exist."""
    if not check_column_exists(conn, 'disclosures', 'political_bloc'):
        logger.info("Adding political_bloc column to disclosures table")
        conn.execute("ALTER TABLE disclosures ADD COLUMN political_bloc TEXT")
        conn.commit()
    else:
        logger.info("political_bloc column already exists")

def update_political_blocs(conn):
    """Update the political_bloc column based on the party mappings."""
    logger.info("Updating political_bloc values")
    
    # Get all unique parties in the database
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT party FROM disclosures WHERE party IS NOT NULL")
    existing_parties = [row[0] for row in cursor.fetchall()]
    
    # Update each party's bloc
    for party in existing_parties:
        if party in PARTY_TO_BLOC:
            bloc = PARTY_TO_BLOC[party]
        else:
            # Default for any party not in our mapping
            bloc = 'Other'
            logger.warning(f"Party '{party}' not found in mappings, setting bloc to 'Other'")
        
        # Update records for this party
        conn.execute(
            "UPDATE disclosures SET political_bloc = ? WHERE party = ?",
            (bloc, party)
        )
    
    # Handle NULL party values
    conn.execute("UPDATE disclosures SET political_bloc = 'Unknown' WHERE party IS NULL OR party = ''")
    conn.commit()
    
def count_by_bloc(conn):
    """Count MPs by political bloc."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT political_bloc, COUNT(DISTINCT mp_name) 
        FROM disclosures 
        GROUP BY political_bloc 
        ORDER BY COUNT(DISTINCT mp_name) DESC
    """)
    results = cursor.fetchall()
    
    logger.info("MP count by political bloc:")
    for bloc, count in results:
        logger.info(f"  {bloc}: {count} MPs")

def main():
    """Main function to add and populate the political_bloc column."""
    logger.info(f"Connecting to database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Add the political_bloc column if it doesn't exist
        add_political_bloc_column(conn)
        
        # Update the political_bloc values
        update_political_blocs(conn)
        
        # Count MPs by bloc
        count_by_bloc(conn)
        
        logger.info("Successfully updated political_bloc column")
    except Exception as e:
        logger.error(f"Error updating political_bloc: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main() 