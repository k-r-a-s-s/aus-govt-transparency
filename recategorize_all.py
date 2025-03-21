#!/usr/bin/env python3
"""
Recategorize All Unknown Entries

This script combines regex-based and LLM-based approaches to recategorize unknown entries
in the database, offering a complete pipeline for improving category data quality.
"""

import logging
import argparse
import os
import time
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def recategorize_complete_pipeline(
    db_path: str, 
    skip_regex: bool = False, 
    skip_llm: bool = False,
    llm_batch_size: int = 50,
    llm_max_entries: int = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Run the complete recategorization pipeline.
    
    Args:
        db_path: Path to the SQLite database
        skip_regex: If True, skip the regex-based recategorization
        skip_llm: If True, skip the LLM-based recategorization
        llm_batch_size: Batch size for LLM processing
        llm_max_entries: Maximum number of entries to process with LLM
        dry_run: If True, only print changes without applying them
        
    Returns:
        Combined statistics from both approaches
    """
    # Import recategorization modules here to avoid circular imports
    from recategorize_unknowns import UnknownRecategorizer
    from recategorize_unknowns_llm import LLMRecategorizer
    
    start_time = time.time()
    stats = {
        "regex": {},
        "llm": {},
        "total_time_seconds": 0
    }
    
    # Step 1: Regex-based recategorization
    if not skip_regex:
        logger.info("=== STEP 1: Regex-based Recategorization ===")
        regex_recategorizer = UnknownRecategorizer(db_path)
        stats["regex"] = regex_recategorizer.recategorize_all_unknowns(dry_run)
    
    # Step 2: LLM-based recategorization for remaining unknowns
    if not skip_llm:
        logger.info("\n=== STEP 2: LLM-based Recategorization ===")
        
        # Check if Google API key is available
        if not os.getenv("GOOGLE_API_KEY"):
            logger.warning("No Google API key found. Set GOOGLE_API_KEY environment variable to use LLM recategorization.")
            logger.warning("LLM-based recategorization will be skipped.")
        else:
            llm_recategorizer = LLMRecategorizer(db_path)
            stats["llm"] = llm_recategorizer.recategorize_with_llm(
                batch_size=llm_batch_size,
                max_entries=llm_max_entries,
                dry_run=dry_run
            )
    
    # Calculate total time
    end_time = time.time()
    stats["total_time_seconds"] = end_time - start_time
    
    # Summary report
    logger.info("\n=== RECATEGORIZATION SUMMARY ===")
    logger.info(f"Total processing time: {stats['total_time_seconds']:.1f} seconds")
    
    if "regex" in stats and stats["regex"]:
        logger.info(f"Regex approach: {stats['regex'].get('recategorized', 0)} entries recategorized " +
                   f"({stats['regex'].get('recategorized', 0)/stats['regex'].get('total', 1)*100:.1f}% of unknown entries)")
    
    if "llm" in stats and stats["llm"]:
        logger.info(f"LLM approach: {stats.get('llm', {}).get('recategorized', 0)} entries recategorized " +
                   f"({stats.get('llm', {}).get('recategorized', 0)/stats.get('llm', {}).get('total', 1)*100:.1f}% of remaining unknown entries)")
    
    total_recategorized = stats.get("regex", {}).get("recategorized", 0) + stats.get("llm", {}).get("recategorized", 0)
    total_original = stats.get("regex", {}).get("total", 0)
    
    if total_original:
        logger.info(f"Combined: {total_recategorized} entries recategorized " +
                   f"({total_recategorized/total_original*100:.1f}% of all unknown entries)")
    
    return stats

def main():
    """Main function to parse arguments and run the complete recategorization pipeline."""
    parser = argparse.ArgumentParser(description="Recategorize all unknown entries in the database")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database file")
    parser.add_argument("--skip-regex", action="store_true", help="Skip regex-based recategorization")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM-based recategorization")
    parser.add_argument("--llm-batch-size", type=int, default=50, help="Batch size for LLM processing")
    parser.add_argument("--llm-max-entries", type=int, help="Maximum number of entries to process with LLM")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without applying them")
    
    args = parser.parse_args()
    
    logger.info(f"Starting complete recategorization pipeline for database: {args.db_path}")
    
    recategorize_complete_pipeline(
        db_path=args.db_path,
        skip_regex=args.skip_regex,
        skip_llm=args.skip_llm,
        llm_batch_size=args.llm_batch_size,
        llm_max_entries=args.llm_max_entries,
        dry_run=args.dry_run
    )
    
    if args.dry_run:
        logger.info("\nTo apply these changes, run without the --dry-run flag")
    
    logger.info("Done!")

if __name__ == "__main__":
    main() 