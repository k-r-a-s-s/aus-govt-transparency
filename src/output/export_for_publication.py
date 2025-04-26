"""
Export the final, cleaned disclosures dataset for public use and Kaggle.

- Outputs a single CSV with all relevant fields (joined from mps, disclosures, entities).
- Optionally generates a Kaggle-ready package (README, schema).
- Strongly typed, functional, and modular.
"""

import argparse
import os
import pandas as pd
from typing import Optional
from src.preparation.db_handler import DatabaseHandler

def export_to_csv(
    db_path: str,
    csv_path: str,
    verbose: bool = False
) -> pd.DataFrame:
    db = DatabaseHandler(db_path)
    import sqlite3
    conn = sqlite3.connect(db_path)
    query = """
    SELECT
        d.disclosure_id,
        d.date,
        d.category,
        d.interest_type,
        d.sub_category,
        d.raw_description,
        d.raw_entity,
        d.pdf_filename,
        m.mp_id,
        m.full_name,
        m.electorate,
        m.political_bloc,
        m.party,
        e.canonical_name AS entity_canonical_name
    FROM disclosures d
    LEFT JOIN mps m ON d.mp_id = m.mp_id
    LEFT JOIN entities e ON d.entity_id = e.entity_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    col_order = [
        "full_name",
        "political_bloc",
        "date",
        "category",
        "sub_category",
        "interest_type",
        "raw_description",
        "entity_canonical_name",
        "pdf_filename",
        "mp_id",
        "electorate",
        "raw_entity",
        "party",
        "disclosure_id"
    ]
    df = df[col_order]
    if verbose:
        print(f"Exporting {len(df)} disclosures to {csv_path} with columns: {col_order}")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    if verbose:
        print(f"CSV export complete: {csv_path}")
    return df

def main():
    parser = argparse.ArgumentParser(description="Export final disclosures dataset for public use and Kaggle.")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database.")
    parser.add_argument("--csv-path", default="outputs/disclosures_final.csv", help="Path to output CSV file.")
    parser.add_argument("--kaggle-dir", default=None, help="If set, output Kaggle package to this directory.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output.")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.csv_path), exist_ok=True)
    df = export_to_csv(args.db_path, args.csv_path, args.verbose)

    if args.kaggle_dir:
        import shutil
        import json
        os.makedirs(args.kaggle_dir, exist_ok=True)
        # Copy CSV (with correct columns)
        kaggle_csv = os.path.join(args.kaggle_dir, "disclosures.csv")
        df.to_csv(kaggle_csv, index=False, encoding="utf-8")
        # Write Excel file
        kaggle_excel = os.path.join(args.kaggle_dir, "disclosures.xlsx")
        df.to_excel(kaggle_excel, index=False, engine="openpyxl")
        if args.verbose:
            print(f"Excel export complete: {kaggle_excel}")
        # Write README.md with correct field order
        with open(os.path.join(args.kaggle_dir, "README.md"), "w") as f:
            f.write("# Australian Parliamentarians' Financial Disclosures\n\n")
            f.write("This dataset contains all cleaned, canonicalized financial disclosures for Australian MPs, extracted and standardized by the aus-govt-transparency pipeline.\n\n")
            f.write("## Fields\n")
            f.write("- `full_name`: MP full name\n")
            f.write("- `political_bloc`: Political bloc (e.g., The Coalition, Labor, Greens)\n")
            f.write("- `date`: Disclosure date (YYYY-MM-DD)\n")
            f.write("- `category`: Disclosure category (e.g., Shares, Real Estate)\n")
            f.write("- `sub_category`: Subcategory (if available)\n")
            f.write("- `interest_type`: Nature of interest (acquired/disposed/held)\n")
            f.write("- `raw_description`: Original disclosure text\n")
            f.write("- `entity_canonical_name`: Canonical entity name\n")
            f.write("- `pdf_filename`: Source PDF file\n")
            f.write("- `mp_id`: Canonical MP ID\n")
            f.write("- `electorate`: MP electorate\n")
            f.write("- `raw_entity`: Raw entity string\n")
            f.write("- `party`: MP party (original, as in official records)\n")
            f.write("- `disclosure_id`: Unique disclosure identifier\n")
            f.write("\nSee https://github.com/g0v/aus-govt-transparency for pipeline and schema details.\n")
        # Write schema.json (with correct columns)
        schema = [
            {"name": "full_name", "type": "string", "description": "MP full name"},
            {"name": "political_bloc", "type": "string", "description": "Political bloc (e.g., The Coalition, Labor, Greens)"},
            {"name": "date", "type": "string", "description": "Disclosure date (YYYY-MM-DD)"},
            {"name": "category", "type": "string", "description": "Disclosure category"},
            {"name": "sub_category", "type": "string", "description": "Disclosure subcategory"},
            {"name": "interest_type", "type": "string", "description": "Nature of interest (acquired/disposed/held)"},
            {"name": "raw_description", "type": "string", "description": "Original disclosure text"},
            {"name": "entity_canonical_name", "type": "string", "description": "Canonical entity name"},
            {"name": "pdf_filename", "type": "string", "description": "Source PDF file"},
            {"name": "mp_id", "type": "string", "description": "Canonical MP ID"},
            {"name": "electorate", "type": "string", "description": "MP electorate"},
            {"name": "raw_entity", "type": "string", "description": "Raw entity string"},
            {"name": "party", "type": "string", "description": "MP party (original, as in official records)"},
            {"name": "disclosure_id", "type": "string", "description": "Unique disclosure identifier"},
        ]
        with open(os.path.join(args.kaggle_dir, "schema.json"), "w") as f:
            json.dump(schema, f, indent=2)
        if args.verbose:
            print(f"Kaggle package written to {args.kaggle_dir}")

if __name__ == "__main__":
    main() 