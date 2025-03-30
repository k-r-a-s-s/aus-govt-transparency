import argparse
import pandas as pd
import sqlite3
import time

def get_db_connection(db_path, max_retries=3, timeout=60):
    """Get a database connection with retry mechanism."""
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(db_path, timeout=timeout)
            return conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                print(f"Database locked, retrying attempt {attempt + 2}/{max_retries}...")
                time.sleep(1)  # Wait 1 second before retrying
                continue
            raise
    raise sqlite3.OperationalError("Failed to connect to database after multiple attempts")

def main():
    parser = argparse.ArgumentParser(description='Update disclosures database with LLM verified fuzzy matches.')
    parser.add_argument('--input-csv', required=True, help='Path to the LLM verification results CSV (from verify_fuzzy_matches_llm.py).')
    parser.add_argument('--db', required=True, help='Path to the SQLite database (e.g., disclosures.db).')

    args = parser.parse_args()

    print("--- Starting Database Update from LLM Verification ---")
    print(f"Input CSV: {args.input_csv}")
    print(f"Database: {args.db}")

    # 1. Read Input CSV
    try:
        df = pd.read_csv(args.input_csv)
        print(f"Read {len(df)} rows from {args.input_csv}")
        # Ensure required columns exist
        required_cols = ['disclosure_id', 'llm_decision', 'llm_corrected_name']
        if not all(col in df.columns for col in required_cols):
            print(f"Error: Input CSV must contain columns: {required_cols}")
            return

        # Filter for rows that need updating
        df_updates = df[(df['llm_decision'] == 'Corrected') & (df['llm_corrected_name'].notna()) & (df['llm_corrected_name'] != '')].copy()
        print(f"Found {len(df_updates)} rows marked for correction by LLM.")

        if df_updates.empty:
            print("No rows require updating in the database.")
            print("--- Database Update Complete ---")
            return

    except FileNotFoundError:
        print(f"Error: Input CSV file not found at {args.input_csv}")
        return
    except Exception as e:
        print(f"Error reading or processing input CSV: {e}")
        return

    # 2. Prepare update data
    # Create list of tuples: (corrected_name, disclosure_id)
    update_data = [
        (row['llm_corrected_name'], row['disclosure_id'])
        for index, row in df_updates.iterrows()
    ]

    # 3. Update Database
    conn = None
    updated_count = 0
    try:
        conn = get_db_connection(args.db)
        cursor = conn.cursor()
        print(f"Updating {len(update_data)} records in the database...")

        # Use executemany for potentially faster updates
        update_sql = """
            UPDATE disclosures
            SET fuzzy_match = ?
            WHERE disclosure_id = ?;
        """
        cursor.executemany(update_sql, update_data)
        updated_count = cursor.rowcount # Note: executemany rowcount might be -1 or unreliable depending on driver/db

        conn.commit()
        print(f"Database commit successful.")
        # Verify count if rowcount is unreliable
        if updated_count == -1:
             print("Row count from executemany is unreliable, update presumed successful based on commit.")
             print(f"Attempted to update {len(update_data)} records.")
        else:
             print(f"Successfully updated {updated_count} rows in the database.")
             if updated_count != len(update_data):
                  print(f"Warning: Expected to update {len(update_data)} rows, but reported {updated_count}. Check disclosure IDs.")

    except sqlite3.Error as e:
        print(f"Database Error during update: {e}")
        if conn:
            conn.rollback() # Rollback changes on error
            print("Database changes rolled back.")
    except Exception as e:
        print(f"An unexpected error occurred during database update: {e}")
        if conn:
            conn.rollback()
            print("Database changes rolled back.")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

    print("--- Database Update Complete ---")

if __name__ == '__main__':
    main() 