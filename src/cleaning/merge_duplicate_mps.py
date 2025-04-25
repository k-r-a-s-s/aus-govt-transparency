#!/usr/bin/env python3
"""
Script to canonicalize and merge duplicate MPs in the mps table, updating all references in disclosures.
- Detects duplicates by normalized name + electorate.
- Updates disclosures to use canonical mp_id.
- Removes duplicates from mps.
- Outputs a log of all merges.

Usage:
  python src/cleaning/merge_duplicate_mps.py --db-path disclosures.db [--dry-run] [--output-log merge_log.csv]
"""
import sqlite3
import argparse
import pandas as pd
from collections import defaultdict, Counter
import re

def normalize_name(name):
    if not name or not isinstance(name, str):
        return ""
    name = name.lower()
    name = re.sub(r'\b(hon\.|dr\.|mr\.|ms\.|mrs\.|sir|dame|mp)\b', '', name)
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'\[[^\]]*\]', '', name)
    name = re.sub(r'[\W_]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

# Manual merge overrides: (full_name, electorate) -> canonical_full_name
def get_manual_merge_overrides():
    # All variants of Chris Bowen in McMahon should be merged into 'Chris Bowen'
    return {
        ("Christopher Bowen", "Mc Mahon"): "Chris Bowen",
        ("Christopher Eyles Bowen", "McMahon"): "Chris Bowen",
        ("chris_bowen", "McMahon"): "Chris Bowen",
        ("christopher_bowen", "Mc Mahon"): "Chris Bowen",
        ("christopher_eyles_bowen", "McMahon"): "Chris Bowen",
        # Louise Markus manual merge
        ("MARKUS", "MACQUARIE"): "Louise Markus",
        ("markus", "MACQUARIE"): "Louise Markus",
        # Albertus Van Manen manual merge
        ("Albertus Van Manen", "Forde"): "Albertus Johannes Van Manen",
        ("albertus_van_manen", "Forde"): "Albertus Johannes Van Manen",
        # Milton Dick manual merge
        ("DICK DUGALD MILTON", "OXLEY"): "Milton Dick",
        ("dick_dugald_milton", "OXLEY"): "Milton Dick",
        # Clare O'Neil manual merge
        ("Clare O'Neil", "Hotham"): "Clare Ellen O'Neil",
        ("clare_o'neil", "HOTHAM"): "Clare Ellen O'Neil",
    }

def main():
    parser = argparse.ArgumentParser(description="Merge duplicate MPs and update references.")
    parser.add_argument('--db-path', required=True, help='Path to SQLite database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done, but do not modify the database')
    parser.add_argument('--output-log', default='merge_log.csv', help='CSV file to log merges')
    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path)
    mps = pd.read_sql_query("SELECT * FROM mps", conn)
    disclosures = pd.read_sql_query("SELECT * FROM disclosures", conn)

    # --- Manual merge overrides ---
    MANUAL_MERGE_OVERRIDES = get_manual_merge_overrides()
    # Build a mapping from (full_name, electorate) to mp_id, normalized for case and whitespace
    def norm(s):
        return s.lower().replace(' ', '') if isinstance(s, str) else s
    name_electorate_to_id = {(norm(row['full_name']), norm(row['electorate'])): row['mp_id'] for _, row in mps.iterrows()}
    merge_log = []
    for (from_name, electorate), to_name in MANUAL_MERGE_OVERRIDES.items():
        from_id = name_electorate_to_id.get((norm(from_name), norm(electorate)))
        to_id = name_electorate_to_id.get((norm(to_name), norm(electorate)))
        if from_id and to_id and from_id != to_id:
            if not args.dry_run:
                conn.execute("UPDATE disclosures SET mp_id = ? WHERE mp_id = ?", (to_id, from_id))
                conn.execute("DELETE FROM mps WHERE mp_id = ?", (from_id,))
            merge_log.append({'canonical_mp_id': to_id, 'merged_mp_id': from_id, 'full_name': from_name, 'electorate': electorate})

    # Build (normalized_name, electorate) -> list of mp_ids
    mps['norm_name'] = mps['full_name'].apply(normalize_name)
    mps['electorate_norm'] = mps['electorate'].str.lower().str.replace(r'\s+', '', regex=True)
    group_cols = ['norm_name', 'electorate_norm']
    grouped = mps.groupby(group_cols)

    for key, group in grouped:
        if len(group) <= 1:
            continue
        # Pick canonical: mp_id with most disclosures, else lex smallest
        mp_id_counts = Counter(disclosures[disclosures['mp_id'].isin(group['mp_id'])]['mp_id'])
        if mp_id_counts:
            canonical = mp_id_counts.most_common(1)[0][0]
        else:
            canonical = sorted(group['mp_id'])[0]
        duplicates = [mpid for mpid in group['mp_id'] if mpid != canonical]
        for dup in duplicates:
            merge_log.append({'canonical_mp_id': canonical, 'merged_mp_id': dup, 'full_name': group[group['mp_id']==dup]['full_name'].values[0], 'electorate': group[group['mp_id']==dup]['electorate'].values[0]})
            if not args.dry_run:
                # Update disclosures
                conn.execute("UPDATE disclosures SET mp_id = ? WHERE mp_id = ?", (canonical, dup))
                # Remove from mps
                conn.execute("DELETE FROM mps WHERE mp_id = ?", (dup,))
    if not args.dry_run:
        conn.commit()
    # Output log
    log_df = pd.DataFrame(merge_log)
    log_df.to_csv(args.output_log, index=False)
    print(f"Merges complete. {len(merge_log)} duplicates merged. Log written to {args.output_log}.")
    if args.dry_run:
        print("Dry run: no changes were made to the database.")

if __name__ == "__main__":
    main() 