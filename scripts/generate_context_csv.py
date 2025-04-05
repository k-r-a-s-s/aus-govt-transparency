# filename: scripts/generate_context_csv.py
import sqlite3
import csv
import os
import logging

# --- Configuration ---
DATABASE_FILE = "disclosures.db" # Assumes DB is in the project root
OUTPUT_CSV_FILE = "short_normalized_entities_context.csv" # Output to project root
DETAILS_LENGTH_LIMIT = 500  # Max characters for the details_list column
MIN_ENTITY_LENGTH = 2
MAX_ENTITY_LENGTH = 5

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Determine Project Root and Paths ---
# Assumes this script is in the 'scripts' directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(project_root, DATABASE_FILE)
output_csv_path = os.path.join(project_root, OUTPUT_CSV_FILE)

# --- Main Logic ---
def generate_csv():
    logging.info(f"Connecting to database: {db_path}")
    if not os.path.exists(db_path):
        logging.error(f"Database file not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        # Use Row factory for easier access by column name
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        sql = f"""
        SELECT
            normalized_entity,
            GROUP_CONCAT(DISTINCT category) AS categories,
            GROUP_CONCAT(DISTINCT sub_category) AS sub_categories,
            GROUP_CONCAT(DISTINCT details) AS details_list
        FROM disclosures
        WHERE
            normalized_entity IS NOT NULL
            AND LENGTH(normalized_entity) >= ?
            AND LENGTH(normalized_entity) <= ?
        GROUP BY normalized_entity;
        """

        logging.info("Executing SQL query to fetch and group disclosures...")
        cursor.execute(sql, (MIN_ENTITY_LENGTH, MAX_ENTITY_LENGTH))
        results = cursor.fetchall()
        logging.info(f"Fetched {len(results)} grouped entities.")

        logging.info(f"Writing results to CSV: {output_csv_path}")
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            # Define header matching the SELECT query aliases + explicit quoting requirement
            fieldnames = ['normalized_entity', 'categories', 'sub_categories', 'details_list']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL) # Quote all fields

            writer.writeheader()
            written_count = 0
            for row in results:
                row_dict = dict(row) # Convert sqlite3.Row to dict

                # Truncate details_list if it exceeds the limit
                details = row_dict.get('details_list', '')
                if details and len(details) > DETAILS_LENGTH_LIMIT:
                    logging.debug(f"Truncating details for entity '{row_dict['normalized_entity']}' from {len(details)} to {DETAILS_LENGTH_LIMIT} chars.")
                    row_dict['details_list'] = details[:DETAILS_LENGTH_LIMIT] + "..." # Indicate truncation

                # Ensure categories and sub_categories are present even if null from DB
                row_dict['categories'] = row_dict.get('categories', '')
                row_dict['sub_categories'] = row_dict.get('sub_categories', '')

                writer.writerow(row_dict)
                written_count += 1

        logging.info(f"Successfully wrote {written_count} rows to {output_csv_path}")

    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    except IOError as e:
        logging.error(f"File writing error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")

if __name__ == "__main__":
    generate_csv() 