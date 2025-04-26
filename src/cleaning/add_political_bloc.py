"""
Add and populate the 'political_bloc' column in the mps table based on party name mappings.

- Liberal/National variants -> The Coalition
- Labor/Independent, Australian Labor Party -> Labor
- Any party containing 'Greens' -> Greens
- All others: use the party name as-is

Usage:
    python src/cleaning/add_political_bloc.py --db-path disclosures.db
"""

import argparse
import sqlite3
from typing import Dict, List

# Hardcoded mapping
COALITION_PARTIES = {
    "Liberal Party of Australia",
    "Liberal Party of Australia WA",
    "Liberal National Party",
    "Liberal / Independent",
    "Liberal/Independent",
    "National Party of Australia",
    "National / Independent",
    "Country Liberal",
}
LABOR_PARTIES = {
    "Labor/Independent",
    "Australian Labor Party",
}

def get_political_bloc(party: str) -> str:
    if party is None:
        return "Unknown"
    party_clean = party.strip()
    if party_clean in COALITION_PARTIES:
        return "The Coalition"
    if party_clean in LABOR_PARTIES:
        return "Labor"
    if "greens" in party_clean.lower():
        return "Greens"
    return party_clean

def add_and_populate_political_bloc(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Add column if not exists
    cursor.execute("PRAGMA table_info(mps)")
    columns = [row[1] for row in cursor.fetchall()]
    if "political_bloc" not in columns:
        cursor.execute("ALTER TABLE mps ADD COLUMN political_bloc TEXT")
        print("Added 'political_bloc' column to mps table.")
    # Get all MPs and their parties
    cursor.execute("SELECT mp_id, party FROM mps")
    mps = cursor.fetchall()
    updates: List[tuple] = []
    for mp_id, party in mps:
        bloc = get_political_bloc(party)
        updates.append((bloc, mp_id))
    # Update all rows
    cursor.executemany("UPDATE mps SET political_bloc = ? WHERE mp_id = ?", updates)
    conn.commit()
    # Print summary
    cursor.execute("SELECT political_bloc, COUNT(*) FROM mps GROUP BY political_bloc")
    summary = cursor.fetchall()
    print("Political bloc summary:")
    for bloc, count in summary:
        print(f"  {bloc}: {count}")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Add and populate the 'political_bloc' column in the mps table.")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database.")
    args = parser.parse_args()
    add_and_populate_political_bloc(args.db_path)

if __name__ == "__main__":
    main() 