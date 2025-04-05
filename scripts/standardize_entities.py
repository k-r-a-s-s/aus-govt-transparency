"""Entity Normalization Script for Disclosure Database

This script performs basic normalization on entity names. It reads the 
'split_entity' column, applies normalization rules (lowercase, remove 
non-alphanumeric/space/& characters, collapse whitespace), and saves the
result to a new 'normalized_entity' column.

This normalized column can then serve as input for more advanced processes 
like graph-based fuzzy grouping.
"""

import sqlite3
import re
import argparse
import time
from typing import List, Tuple

def normalize(name: str) -> str:
    """Apply basic normalization to a name."""
    if not name:
        return ""
    name = name.casefold().strip()
    # Keep alphanumeric, whitespace, and ampersand. Remove others.
    name = re.sub(r"[^\w\s&]", "", name)   
    # Collapse multiple whitespace characters into a single space.
    name = re.sub(r"\s+", " ", name)       
    return name.strip()

def get_db_connection(db_path, max_retries=3, timeout=60):
    """Get a database connection with retry mechanism."""
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(db_path, timeout=timeout)
            # Improve performance and reliability
            conn.execute("PRAGMA journal_mode=WAL;") 
            conn.execute("PRAGMA synchronous=NORMAL;")
            return conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                print(f"Database locked, retrying attempt {attempt + 2}/{max_retries}...")
                time.sleep(1)  # Wait 1 second before retrying
                continue
            raise
    raise sqlite3.OperationalError(f"Failed to connect to database '{db_path}' after {max_retries} attempts.")

def ensure_normalized_entity_column(db_path: str) -> None:
    """Ensure the normalized_entity column exists in the disclosures table."""
    print(f"Checking for 'normalized_entity' column in {db_path}...")
    conn = None
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(disclosures)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'normalized_entity' not in columns:
            print("Adding 'normalized_entity' column...")
            cursor.execute("ALTER TABLE disclosures ADD COLUMN normalized_entity TEXT")
            # Add an index for faster lookups if needed later
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_normalized_entity ON disclosures(normalized_entity)")
            conn.commit()
            print("'normalized_entity' column added and indexed.")
        else:
            print("'normalized_entity' column already exists.")
            
    except Exception as e:
        print(f"Error ensuring 'normalized_entity' column exists: {e}")
        # Optionally re-raise if it's critical
    finally:
        if conn:
            conn.close()

def main():
    parser = argparse.ArgumentParser(description='Normalize entity names from split_entity column.')
    parser.add_argument('--db', required=True, help='Path to the SQLite database')
    args = parser.parse_args()

    # 1. Ensure the target column exists
    ensure_normalized_entity_column(args.db)

    conn = None
    try:
        # 2. Connect to the database
        conn = get_db_connection(args.db)
        cursor = conn.cursor()
        
        # 3. Fetch distinct non-null split_entity values
        print("Fetching distinct split entities...")
        cursor.execute("SELECT DISTINCT split_entity FROM disclosures WHERE split_entity IS NOT NULL AND split_entity != ''")
        original_entities: List[Tuple[str]] = cursor.fetchall()
        print(f"Found {len(original_entities)} unique split entities to normalize.")

        if not original_entities:
            print("No split entities found to normalize.")
            return

        # 4. Normalize the entities
        print("Normalizing entities...")
        update_data: List[Tuple[str, str]] = []
        processed_count = 0
        for (original_entity,) in original_entities:
            normalized_name = normalize(original_entity)
            # Only add to update list if normalization actually changed the name 
            # or if you want to ensure the column is populated even if identical
            # For initial population, let's include identical ones too.
            update_data.append((normalized_name, original_entity))
            processed_count += 1
            if processed_count % 1000 == 0:
                 print(f"  Processed {processed_count}/{len(original_entities)}...")

        # 5. Update the database
        if update_data:
            print(f"\nApplying {len(update_data)} normalization updates to the 'normalized_entity' column...")
            try:
                # Use executemany for potentially faster bulk updates
                cursor.executemany("""
                    UPDATE disclosures 
                    SET normalized_entity = ? 
                    WHERE split_entity = ?
                """, update_data)
                
                # Commit the changes
                conn.commit()
                print(f"Successfully updated {cursor.rowcount} rows.") # Reports total rows affected across all operations in executemany
            except sqlite3.Error as e:
                print(f"Database error during update: {e}")
                conn.rollback() # Roll back changes on error
        else:
            print("No normalization changes needed or no entities to process.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    main()

def normalize(name: str) -> str:
    """Apply basic normalization to a name."""
    if not name:
        return ""
    name = name.casefold().strip()
    # Keep alphanumeric, whitespace, and ampersand. Remove others.
    name = re.sub(r"[^\w\s&]", "", name)   
    # Collapse multiple whitespace characters into a single space.
    name = re.sub(r"\s+", " ", name)       
    return name.strip()

def get_db_connection(db_path, max_retries=3, timeout=60):
    """Get a database connection with retry mechanism."""
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(db_path, timeout=timeout)
            # Improve performance and reliability
            conn.execute("PRAGMA journal_mode=WAL;") 
            conn.execute("PRAGMA synchronous=NORMAL;")
            return conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                print(f"Database locked, retrying attempt {attempt + 2}/{max_retries}...")
                time.sleep(1)  # Wait 1 second before retrying
                continue
            raise
    raise sqlite3.OperationalError(f"Failed to connect to database '{db_path}' after {max_retries} attempts.")

def ensure_normalized_entity_column(db_path: str) -> None:
    """Ensure the normalized_entity column exists in the disclosures table."""
    print(f"Checking for 'normalized_entity' column in {db_path}...")
    conn = None
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(disclosures)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'normalized_entity' not in columns:
            print("Adding 'normalized_entity' column...")
            cursor.execute("ALTER TABLE disclosures ADD COLUMN normalized_entity TEXT")
            # Add an index for faster lookups if needed later
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_normalized_entity ON disclosures(normalized_entity)")
            conn.commit()
            print("'normalized_entity' column added and indexed.")
        else:
            print("'normalized_entity' column already exists.")
            
    except Exception as e:
        print(f"Error ensuring 'normalized_entity' column exists: {e}")
        # Optionally re-raise if it's critical
    finally:
        if conn:
            conn.close()

def main():
    parser = argparse.ArgumentParser(description='Normalize entity names from split_entity column.')
    parser.add_argument('--db', required=True, help='Path to the SQLite database')
    args = parser.parse_args()

    # 1. Ensure the target column exists
    ensure_normalized_entity_column(args.db)

    conn = None
    try:
        # 2. Connect to the database
        conn = get_db_connection(args.db)
        cursor = conn.cursor()
        
        # 3. Fetch distinct non-null split_entity values
        print("Fetching distinct split entities...")
        cursor.execute("SELECT DISTINCT split_entity FROM disclosures WHERE split_entity IS NOT NULL AND split_entity != ''")
        original_entities: List[Tuple[str]] = cursor.fetchall()
        print(f"Found {len(original_entities)} unique split entities to normalize.")

        if not original_entities:
            print("No split entities found to normalize.")
            return

        # 4. Normalize the entities
        print("Normalizing entities...")
        update_data: List[Tuple[str, str]] = []
        processed_count = 0
        for (original_entity,) in original_entities:
            normalized_name = normalize(original_entity)
            # Only add to update list if normalization actually changed the name 
            # or if you want to ensure the column is populated even if identical
            # For initial population, let's include identical ones too.
            update_data.append((normalized_name, original_entity))
            processed_count += 1
            if processed_count % 1000 == 0:
                 print(f"  Processed {processed_count}/{len(original_entities)}...")

        # 5. Update the database
        if update_data:
            print(f"\nApplying {len(update_data)} normalization updates to the 'normalized_entity' column...")
            try:
                # Use executemany for potentially faster bulk updates
                cursor.executemany("""
                    UPDATE disclosures 
                    SET normalized_entity = ? 
                    WHERE split_entity = ?
                """, update_data)
                
                # Commit the changes
                conn.commit()
                print(f"Successfully updated {cursor.rowcount} rows.") # Reports total rows affected across all operations in executemany
            except sqlite3.Error as e:
                print(f"Database error during update: {e}")
                conn.rollback() # Roll back changes on error
        else:
            print("No normalization changes needed or no entities to process.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    main()