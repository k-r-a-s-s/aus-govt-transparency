#!/usr/bin/env python
"""
Double Disclosure Analysis

This script analyzes the disclosures database to identify entries that likely contain
multiple entities in a single entity field, such as "Shell and Optus" or "CBA, ANZ".

It performs several analyses:
1. Identifies potential double disclosures using common separators
2. Attempts to match existing canonical entities within these combined fields
3. Generates statistics on the prevalence of double disclosures
4. Creates a report with detailed findings and recommendations

Usage:
    python double_disclosure_analysis.py [--output_dir OUTPUT_DIR]
"""

import sqlite3
import re
import os
import json
import logging
import argparse
from typing import Dict, List, Tuple, Set, Any, Optional
import pandas as pd
from collections import Counter

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Common separators indicating multiple entities
SEPARATORS = [
    r'\band\b',   # "Shell and Optus"
    r'\b&\b',     # "Shell & Optus"
    r',',         # "CBA, ANZ"
    r'/',         # "CBA/ANZ"
    r'\+',        # "CBA+ANZ"
]

# Regular expression pattern for finding separators
SEPARATOR_PATTERN = '|'.join(SEPARATORS)

class DoubleDisclosureAnalyzer:
    """
    Analyzes the disclosures database to identify entries with multiple entities.
    """
    
    def __init__(self, db_path: str = "disclosures.db", output_dir: str = "double_disclosure_results"):
        """
        Initialize the analyzer.
        
        Args:
            db_path: Path to the SQLite database file
            output_dir: Directory for saving analysis results
        """
        self.db_path = db_path
        self.output_dir = output_dir
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # For storing results
        self.results = {
            "total_disclosures": 0,
            "potential_double_disclosures": 0,
            "separator_counts": {},
            "top_double_entities": [],
            "matched_canonical_entities": {},
            "entity_candidates": {}
        }
        
        # Load canonical entities
        self.canonical_entities = set()
        self.load_canonical_entities()
    
    def load_canonical_entities(self) -> None:
        """Load existing canonical entities from the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT DISTINCT canonical_entity FROM disclosures WHERE canonical_entity IS NOT NULL")
            entities = cursor.fetchall()
            
            self.canonical_entities = {entity[0] for entity in entities if entity[0]}
            logger.info(f"Loaded {len(self.canonical_entities)} canonical entities")
            
            conn.close()
        except Exception as e:
            logger.error(f"Error loading canonical entities: {e}")
    
    def get_total_disclosures(self) -> int:
        """Get the total number of disclosures in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM disclosures")
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def find_potential_double_disclosures(self) -> pd.DataFrame:
        """Find disclosures with potential multiple entities based on separators."""
        conn = sqlite3.connect(self.db_path)
        
        # Find entities with any of the separator patterns
        separator_pattern = f"entity REGEXP '{SEPARATOR_PATTERN}'"
        
        # SQLite doesn't support REGEXP by default, so create a custom function
        def regexp(pattern, text):
            if text is None:
                return False
            return re.search(pattern, text, re.IGNORECASE) is not None
        
        conn.create_function("REGEXP", 2, regexp)
        
        # Query for potential double disclosures
        query = f"""
        SELECT id, mp_name, party, electorate, declaration_date, category, sub_category, 
               entity, canonical_entity, item, details
        FROM disclosures
        WHERE {separator_pattern} AND entity != 'N/A'
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    
    def analyze_separators(self, entities: List[str]) -> Dict[str, int]:
        """Analyze which separators are most common in the potential double disclosures."""
        separator_counts = {sep: 0 for sep in SEPARATORS}
        
        for entity in entities:
            for sep_pattern in SEPARATORS:
                if re.search(sep_pattern, entity, re.IGNORECASE):
                    # Translate regex pattern to human-readable form for the report
                    readable_pattern = sep_pattern
                    if sep_pattern == r'\band\b':
                        readable_pattern = 'and'
                    elif sep_pattern == r'\b&\b':
                        readable_pattern = '&'
                    elif sep_pattern == r'\+':
                        readable_pattern = '+'
                    
                    separator_counts[sep_pattern] += 1
        
        return separator_counts
    
    def split_entity(self, entity: str) -> List[str]:
        """
        Split a combined entity into individual entities.
        
        For example: "Shell and Optus" -> ["Shell", "Optus"]
        """
        if not entity or entity == 'N/A':
            return []
        
        # Replace separators with a common delimiter for splitting
        processed = entity
        for sep in SEPARATORS:
            processed = re.sub(sep, '|', processed, flags=re.IGNORECASE)
        
        # Split by our delimiter and trim whitespace
        parts = [part.strip() for part in processed.split('|') if part.strip()]
        
        return parts
    
    def match_with_canonical_entities(self, entity_parts: List[str]) -> List[str]:
        """Match split entity parts with known canonical entities."""
        matched = []
        
        for part in entity_parts:
            # Check for exact match
            if part in self.canonical_entities:
                matched.append(part)
                continue
            
            # Check for close matches
            # This is a simple approach - could be enhanced with fuzzy matching
            for canonical in self.canonical_entities:
                if part.lower() in canonical.lower() or canonical.lower() in part.lower():
                    matched.append(canonical)
                    break
        
        return matched
    
    def analyze_double_disclosures(self) -> None:
        """Perform analysis on double disclosures."""
        logger.info("Starting double disclosure analysis")
        
        # Get total number of disclosures
        self.results["total_disclosures"] = self.get_total_disclosures()
        
        # Find potential double disclosures
        df = self.find_potential_double_disclosures()
        self.results["potential_double_disclosures"] = len(df)
        
        logger.info(f"Found {len(df)} potential double disclosures out of {self.results['total_disclosures']} total")
        
        if len(df) == 0:
            logger.warning("No potential double disclosures found")
            return
        
        # Analyze separators
        self.results["separator_counts"] = self.analyze_separators(df['entity'].tolist())
        
        # Find most common double entities
        entity_counter = Counter(df['entity'].tolist())
        self.results["top_double_entities"] = entity_counter.most_common(100)
        
        # Process each potential double disclosure
        all_split_entities = {}
        matched_canonical = {}
        
        for entity in df['entity'].unique():
            split_parts = self.split_entity(entity)
            if len(split_parts) > 1:  # Only consider actual splits
                all_split_entities[entity] = split_parts
                matched = self.match_with_canonical_entities(split_parts)
                if matched:
                    matched_canonical[entity] = matched
        
        self.results["entity_candidates"] = all_split_entities
        self.results["matched_canonical_entities"] = matched_canonical
        
        # Save the detailed results as CSV
        df.to_csv(os.path.join(self.output_dir, "potential_double_disclosures.csv"), index=False)
        
        logger.info("Analysis complete")
    
    def generate_report(self) -> str:
        """Generate a human-readable report of the analysis findings."""
        if not self.results["potential_double_disclosures"]:
            return "No potential double disclosures found."
        
        report = []
        report.append("# Double Disclosure Analysis Report")
        report.append("")
        report.append("## Summary")
        report.append("")
        report.append(f"- Total disclosures: {self.results['total_disclosures']}")
        report.append(f"- Potential double disclosures: {self.results['potential_double_disclosures']} ({(self.results['potential_double_disclosures'] / self.results['total_disclosures'] * 100):.2f}%)")
        report.append("")
        
        # Separator analysis
        report.append("## Separator Analysis")
        report.append("")
        report.append("Common separators found in entity names:")
        report.append("")
        
        for sep_pattern, count in sorted(self.results["separator_counts"].items(), key=lambda x: x[1], reverse=True):
            readable_sep = sep_pattern
            if sep_pattern == r'\band\b':
                readable_sep = '"and"'
            elif sep_pattern == r'\b&\b':
                readable_sep = '"&"'
            elif sep_pattern == r'\+':
                readable_sep = '"+"'
            elif sep_pattern == r',':
                readable_sep = '","'
            elif sep_pattern == r'/':
                readable_sep = '"/"'
            
            report.append(f"- {readable_sep}: {count} occurrences")
        
        report.append("")
        
        # Top double entities
        report.append("## Top Double Entities")
        report.append("")
        report.append("Most frequent potential double entities:")
        report.append("")
        
        for i, (entity, count) in enumerate(self.results["top_double_entities"][:20]):
            split_parts = self.split_entity(entity)
            parts_str = " | ".join(split_parts) if len(split_parts) > 1 else "N/A"
            report.append(f"{i+1}. \"{entity}\" ({count} occurrences) - Possible split: {parts_str}")
        
        report.append("")
        
        # Matched canonical entities
        report.append("## Matched Canonical Entities")
        report.append("")
        report.append("Double entities with matches to existing canonical entities:")
        report.append("")
        
        for i, (entity, matched) in enumerate(list(self.results["matched_canonical_entities"].items())[:20]):
            report.append(f"{i+1}. \"{entity}\" - Matched with: {', '.join(matched)}")
        
        report.append("")
        
        # Recommendations
        report.append("## Recommendations")
        report.append("")
        report.append("Based on the analysis, we recommend:")
        report.append("")
        report.append("1. Split double disclosures into individual disclosure records")
        report.append("2. Use existing canonical entities where possible")
        report.append("3. Update the data ingestion pipeline to automatically handle double disclosures")
        report.append("4. Consider normalizing banking institutions and other common entity groups")
        report.append("")
        
        # Implementation approach
        report.append("## Implementation Approach")
        report.append("")
        report.append("To handle double disclosures, we can:")
        report.append("")
        report.append("1. Create a script to identify and split double disclosures")
        report.append("2. For each double disclosure, create multiple new disclosure records")
        report.append("3. Maintain the original disclosure data in a new 'original_entity' field")
        report.append("4. Update all related database indexes and views")
        report.append("")
        
        return "\n".join(report)
    
    def save_results(self) -> None:
        """Save analysis results to files."""
        logger.info("Saving analysis results")
        
        # Save raw results as JSON
        with open(os.path.join(self.output_dir, "double_disclosure_analysis.json"), 'w') as f:
            # Convert sets to lists for JSON serialization
            serializable_results = self.results.copy()
            json.dump(serializable_results, f, indent=2)
        
        # Generate and save report
        report = self.generate_report()
        with open(os.path.join(self.output_dir, "double_disclosure_report.md"), 'w') as f:
            f.write(report)
        
        logger.info(f"Results saved to {self.output_dir}")
    
    def run(self) -> None:
        """Run the complete analysis."""
        logger.info("Starting double disclosure analysis")
        
        try:
            self.analyze_double_disclosures()
            self.save_results()
            logger.info("Analysis complete")
        except Exception as e:
            logger.error(f"Error during analysis: {e}")

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Analyze double disclosures in the database")
    parser.add_argument('--db_path', default="disclosures.db", help="Path to the database file")
    parser.add_argument('--output_dir', default="scripts/double_disclosure_results", 
                        help="Directory for saving analysis results")
    
    args = parser.parse_args()
    
    analyzer = DoubleDisclosureAnalyzer(db_path=args.db_path, output_dir=args.output_dir)
    analyzer.run()

if __name__ == '__main__':
    main() 