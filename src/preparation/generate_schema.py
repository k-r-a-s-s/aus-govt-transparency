import sqlite3
from typing import Optional

DB_PATH_DEFAULT = "disclosures.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mps (
    mp_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    electorate TEXT,
    party TEXT,
    wikidata_id TEXT
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    iteration INTEGER,
    status TEXT CHECK(status IN ('confirmed', 'rejected', 'pending_review')),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS disclosures (
    disclosure_id TEXT PRIMARY KEY,
    mp_id TEXT NOT NULL,
    pdf_filename TEXT NOT NULL,
    date TEXT NOT NULL,
    raw_description TEXT NOT NULL,
    raw_entity TEXT,
    category TEXT,
    interest_type TEXT CHECK(interest_type IN ('acquired', 'disposed', 'held')),
    entity_id TEXT,
    FOREIGN KEY (mp_id) REFERENCES mps(mp_id),
    FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
);

CREATE INDEX IF NOT EXISTS idx_disclosures_mp_id ON disclosures(mp_id);
CREATE INDEX IF NOT EXISTS idx_disclosures_entity_id ON disclosures(entity_id);
CREATE INDEX IF NOT EXISTS idx_disclosures_type ON disclosures(interest_type);
"""

def create_schema(db_path: str = DB_PATH_DEFAULT) -> None:
    """
    Create the canonical schema for the MP financial disclosures database.
    This includes the mps, disclosures, and entities tables, and relevant indexes.
    """
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create the canonical schema for the MP financial disclosures database.")
    parser.add_argument("--db-path", type=str, default=DB_PATH_DEFAULT, help="Path to the SQLite database file.")
    args = parser.parse_args()

    create_schema(args.db_path)
    print(f"Schema created in {args.db_path}") 