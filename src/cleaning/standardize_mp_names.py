#!/usr/bin/env python3
"""
Standardize MP names in the database by removing middle names.

This script identifies MPs with multiple name variations (with and without middle names),
and standardizes them to a consistent format (first name + last name).
"""

import os
import sqlite3
import re
import logging
import argparse
from typing import Dict, List, Tuple, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def identify_mp_variations_in_mps(db_path: str) -> Dict[Tuple[str, str], List[str]]:
    """
    Identify MPs with multiple name variations in the mps table, grouped by electorate.
    Args:
        db_path: Path to the SQLite database
    Returns:
        Dictionary mapping (electorate, standardized_name) to lists of variations
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, electorate FROM mps WHERE electorate IS NOT NULL")
    all_rows = cursor.fetchall()
    name_variations: Dict[Tuple[str, str], List[str]] = {}
    processed: Set[Tuple[str, str]] = set()
    prefixes = ["van", "von", "de", "del", "della", "di", "da", "dos", "du", "le", "la", "st.", "saint"]
    for full_name, electorate in all_rows:
        if (electorate, full_name) in processed:
            continue
        if not full_name or not electorate:
            continue
        name_parts = full_name.split()
        if len(name_parts) <= 1:
            standardized = full_name
        else:
            first_name = name_parts[0]
            last_name = name_parts[-1]
            if len(name_parts) > 2 and name_parts[-2].lower() in prefixes:
                last_name = f"{name_parts[-2]} {last_name}"
                if len(name_parts) > 3 and name_parts[-3].lower() in prefixes:
                    last_name = f"{name_parts[-3]} {last_name}"
            standardized = f"{first_name} {last_name}"
        variations = []
        for name2, elec2 in all_rows:
            if elec2 != electorate or not name2:
                continue
            name2_parts = name2.split()
            if len(name2_parts) <= 1:
                continue
            first2 = name2_parts[0]
            last2 = name2_parts[-1]
            if len(name2_parts) > 2 and name2_parts[-2].lower() in prefixes:
                last2 = f"{name2_parts[-2]} {last2}"
                if len(name2_parts) > 3 and name2_parts[-3].lower() in prefixes:
                    last2 = f"{name2_parts[-3]} {last2}"
            if first2 == standardized.split()[0] and last2 == standardized.split()[-1]:
                variations.append(name2)
                processed.add((electorate, name2))
        if variations:
            name_variations[(electorate, standardized)] = variations
    conn.close()
    return name_variations


def update_mp_names_in_mps(db_path: str, name_variations: Dict[Tuple[str, str], List[str]], dry_run: bool = False) -> Dict[str, int]:
    """
    Update MP names in the mps table to the standardized format, grouped by electorate.
    Args:
        db_path: Path to the SQLite database
        name_variations: Dictionary mapping (electorate, standardized_name) to lists of variations
        dry_run: If True, only print changes without applying them
    Returns:
        Dictionary with statistics about the updates
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    stats = {
        "total_variations": 0,
        "mps_with_variations": 0,
        "records_updated": 0
    }
    if not dry_run:
        cursor.execute("BEGIN TRANSACTION")
    logger.info(f"{'Simulating' if dry_run else 'Performing'} MP name standardization in mps table")
    for (electorate, standardized), variations in name_variations.items():
        if len(variations) <= 1:
            continue
        stats["mps_with_variations"] += 1
        stats["total_variations"] += len(variations) - 1
        # Choose the shortest name as canonical
        canonical = min(variations, key=lambda n: len(n))
        logger.info(f"Standardizing {len(variations)} variations in '{electorate}' to '{canonical}':")
        for variation in variations:
            if variation != canonical:
                logger.info(f"  - '{variation}' → '{canonical}' (electorate: {electorate})")
                cursor.execute("SELECT COUNT(*) FROM mps WHERE full_name = ? AND electorate = ?", (variation, electorate))
                record_count = cursor.fetchone()[0]
                stats["records_updated"] += record_count
                if not dry_run:
                    cursor.execute("UPDATE mps SET full_name = ? WHERE full_name = ? AND electorate = ?", (canonical, variation, electorate))
    if not dry_run:
        conn.commit()
        logger.info(f"Successfully updated {stats['records_updated']} records")
    else:
        logger.info(f"Dry run: would update {stats['records_updated']} records")
    conn.close()
    return stats


def report_stats_in_mps(stats: Dict[str, int], name_variations: Dict[Tuple[str, str], List[str]]) -> None:
    logger.info("\nStandardization Summary (mps table):")
    logger.info(f"Total MPs with name variations: {stats['mps_with_variations']}")
    logger.info(f"Total name variations standardized: {stats['total_variations']}")
    logger.info(f"Total records updated: {stats['records_updated']}")
    mp_variation_counts = {k: len(v) for k, v in name_variations.items() if len(v) > 1}
    if mp_variation_counts:
        max_variations = max(mp_variation_counts.values())
        most_variations = [k for k, count in mp_variation_counts.items() if count == max_variations]
        logger.info(f"\nMPs with the most name variations ({max_variations}):")
        for (electorate, name) in most_variations:
            variations = name_variations[(electorate, name)]
            logger.info(f"  - {name} ({electorate}): {', '.join(variations)}")


def main():
    parser = argparse.ArgumentParser(description="Standardize MP names by removing middle names, grouped by electorate (mps table only)")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database file")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without applying them")
    args = parser.parse_args()
    logger.info(f"Analyzing MP names in mps table: {args.db_path}")
    name_variations = identify_mp_variations_in_mps(args.db_path)
    stats = update_mp_names_in_mps(args.db_path, name_variations, args.dry_run)
    report_stats_in_mps(stats, name_variations)
    logger.info("Done!")

if __name__ == "__main__":
    main() 