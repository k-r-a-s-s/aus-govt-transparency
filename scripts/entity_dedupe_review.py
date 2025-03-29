#!/usr/bin/env python3
import json
import pandas as pd
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Set, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('entity_dedupe_review')

# Constants
RESULTS_DIR = Path(__file__).parent / "entity_dedupe_results"
PROPOSED_MAPPING_PATH = RESULTS_DIR / "proposed_entity_mapping.json"
REVIEWED_MAPPING_PATH = RESULTS_DIR / "reviewed_entity_mapping.json"
ENTITY_GROUPS_CSV = RESULTS_DIR / "entity_groups_for_review.csv"

class EntityMappingReviewer:
    """Helper for reviewing and modifying entity mappings."""
    
    def __init__(self):
        """Initialize the reviewer with default paths."""
        self.proposed_mapping: Dict[str, List[str]] = {}
        self.groups_df: Optional[pd.DataFrame] = None
        
    def load_proposed_mapping(self) -> None:
        """Load the proposed mapping from the JSON file."""
        logger.info(f"Loading proposed mapping from {PROPOSED_MAPPING_PATH}")
        try:
            with open(PROPOSED_MAPPING_PATH, 'r') as f:
                self.proposed_mapping = json.load(f)
            
            logger.info(f"Loaded mapping with {len(self.proposed_mapping)} canonical entities")
            
        except Exception as e:
            logger.error(f"Error loading proposed mapping: {e}")
            raise
    
    def load_groups_csv(self) -> None:
        """Load the entity groups CSV file."""
        logger.info(f"Loading entity groups from {ENTITY_GROUPS_CSV}")
        try:
            self.groups_df = pd.read_csv(ENTITY_GROUPS_CSV)
            logger.info(f"Loaded {len(self.groups_df)} entity group entries")
            
        except Exception as e:
            logger.error(f"Error loading entity groups CSV: {e}")
            raise
    
    def search_entities(self, search_term: str) -> pd.DataFrame:
        """Search for entities containing the search term."""
        if self.groups_df is None:
            self.load_groups_csv()
            
        mask = (
            self.groups_df['canonical_name'].str.contains(search_term, case=False, na=False) |
            self.groups_df['entity_name'].str.contains(search_term, case=False, na=False)
        )
        
        results = self.groups_df[mask].copy()
        return results
    
    def extract_subset_mapping(self, search_term: str) -> Dict[str, List[str]]:
        """Extract a subset of the mapping containing the search term."""
        self.load_proposed_mapping()
        
        subset_mapping = {}
        
        # Find canonicals containing the search term
        for canonical, variants in self.proposed_mapping.items():
            if search_term.lower() in canonical.lower():
                subset_mapping[canonical] = variants
                continue
                
            # Check if any variants contain the search term
            matching_variants = [v for v in variants if search_term.lower() in v.lower()]
            if matching_variants:
                subset_mapping[canonical] = variants
        
        return subset_mapping
    
    def save_subset_for_review(self, subset_mapping: Dict[str, List[str]], output_path: Path) -> None:
        """Save a subset of the mapping to a file for review."""
        with open(output_path, 'w') as f:
            json.dump(subset_mapping, f, indent=2)
            
        logger.info(f"Saved subset with {len(subset_mapping)} canonicals to {output_path}")
    
    def merge_reviewed_subset(self, reviewed_subset_path: Path) -> None:
        """Merge a reviewed subset back into the full mapping."""
        self.load_proposed_mapping()
        
        # Load the reviewed subset
        with open(reviewed_subset_path, 'r') as f:
            reviewed_subset = json.load(f)
            
        # Create a new mapping by overwriting with the reviewed subset
        full_mapping = self.proposed_mapping.copy()
        for canonical, variants in reviewed_subset.items():
            full_mapping[canonical] = variants
            
        # Check if there are new canonicals in the reviewed subset
        new_canonicals = set(reviewed_subset.keys()) - set(self.proposed_mapping.keys())
        if new_canonicals:
            logger.info(f"Found {len(new_canonicals)} new canonical entities in the reviewed subset")
            
        # Save the updated full mapping
        with open(REVIEWED_MAPPING_PATH, 'w') as f:
            json.dump(full_mapping, f, indent=2)
            
        logger.info(f"Merged reviewed subset into full mapping at {REVIEWED_MAPPING_PATH}")
    
    def generate_focused_review(self, search_term: str, output_path: Optional[Path] = None) -> None:
        """Generate a focused review for entities matching a search term."""
        subset_mapping = self.extract_subset_mapping(search_term)
        
        if not subset_mapping:
            logger.warning(f"No entities found matching '{search_term}'")
            return
            
        if output_path is None:
            output_path = RESULTS_DIR / f"review_{search_term.lower().replace(' ', '_')}.json"
            
        self.save_subset_for_review(subset_mapping, output_path)
        
        # Also show entities in the console
        logger.info(f"Found {len(subset_mapping)} canonical entities matching '{search_term}':")
        
        for i, (canonical, variants) in enumerate(subset_mapping.items()):
            if i < 10:  # Only show first 10 for brevity
                logger.info(f"  {i+1}. {canonical}:")
                for var in variants[:5]:  # Show only first 5 variants
                    logger.info(f"     - {var}")
                
                if len(variants) > 5:
                    logger.info(f"     - ... and {len(variants) - 5} more variants")
            
        if len(subset_mapping) > 10:
            logger.info(f"  ... and {len(subset_mapping) - 10} more canonical entities")
            
        logger.info(f"Review the extracted mapping in {output_path}")
        logger.info("After review, use the --merge option to incorporate your changes back")

def main():
    parser = argparse.ArgumentParser(description="Review and modify entity mappings")
    parser.add_argument("--search", type=str, help="Search term to extract a subset of entities for review")
    parser.add_argument("--output", type=str, help="Output path for the extracted subset")
    parser.add_argument("--merge", type=str, help="Path to a reviewed subset to merge back into the full mapping")
    
    args = parser.parse_args()
    
    reviewer = EntityMappingReviewer()
    
    if args.search:
        output_path = Path(args.output) if args.output else None
        reviewer.generate_focused_review(args.search, output_path)
        
    elif args.merge:
        reviewed_path = Path(args.merge)
        if not reviewed_path.exists():
            logger.error(f"Reviewed subset file not found: {reviewed_path}")
            return
            
        reviewer.merge_reviewed_subset(reviewed_path)
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 