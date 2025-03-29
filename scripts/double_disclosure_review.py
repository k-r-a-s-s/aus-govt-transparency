#!/usr/bin/env python
"""
Double Disclosure Review Utility

This script helps with the manual review of potential double disclosures.
It extracts the top potential double disclosures from the analysis results
and creates a template file for manual editing and review.

Usage:
    python double_disclosure_review.py [--limit N] [--output FILE]
"""

import json
import os
import argparse
import logging
from typing import Dict, List, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DoubleDisclosureReviewer:
    """
    Utility for reviewing double disclosures.
    """
    
    def __init__(
        self,
        analysis_file: str = "scripts/double_disclosure_results/double_disclosure_analysis.json",
        output_file: str = "scripts/double_disclosure_results/reviewed_double_disclosures.json",
        limit: int = 100
    ):
        """
        Initialize the reviewer.
        
        Args:
            analysis_file: Path to the analysis results file
            output_file: Path to save the review template
            limit: Number of top entities to extract for review
        """
        self.analysis_file = analysis_file
        self.output_file = output_file
        self.limit = limit
        
        # Will hold the loaded analysis data
        self.analysis_data = {}
        
        # Will hold the entity candidates for review
        self.entity_candidates = {}
    
    def load_analysis_data(self) -> bool:
        """
        Load the analysis results.
        
        Returns:
            bool: True if file was loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(self.analysis_file):
                logger.error(f"Analysis file not found: {self.analysis_file}")
                return False
            
            with open(self.analysis_file, 'r') as f:
                self.analysis_data = json.load(f)
            
            logger.info(f"Loaded analysis data with {len(self.analysis_data.get('top_double_entities', []))} top double entities")
            return True
            
        except Exception as e:
            logger.error(f"Error loading analysis data: {e}")
            return False
    
    def create_review_template(self) -> bool:
        """
        Create a template file for manual review.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract entity candidates from the analysis
            entity_candidates = self.analysis_data.get("entity_candidates", {})
            
            # Get the top entities based on frequency
            top_entities = []
            for entity, count in self.analysis_data.get("top_double_entities", []):
                if entity in entity_candidates and len(top_entities) < self.limit:
                    top_entities.append(entity)
            
            # Create the review template
            review_template = {}
            for entity in top_entities:
                # Get the split candidates
                split_candidates = entity_candidates.get(entity, [])
                
                # Add to the template
                if split_candidates:
                    review_template[entity] = split_candidates
            
            # Save the template
            with open(self.output_file, 'w') as f:
                json.dump(review_template, f, indent=2)
            
            logger.info(f"Created review template with {len(review_template)} entries at {self.output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating review template: {e}")
            return False
    
    def load_existing_reviewed(self, reviewed_file: str) -> dict:
        """
        Load an existing reviewed file if it exists.
        
        Args:
            reviewed_file: Path to the reviewed file
            
        Returns:
            dict: The loaded data or an empty dict if file doesn't exist
        """
        if not os.path.exists(reviewed_file):
            return {}
        
        try:
            with open(reviewed_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading existing reviewed file: {e}")
            return {}
    
    def merge_into_full_mapping(self, reviewed_subset_file: str) -> bool:
        """
        Merge a reviewed subset into the full mapping file.
        
        Args:
            reviewed_subset_file: Path to the reviewed subset file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Load the reviewed subset
            if not os.path.exists(reviewed_subset_file):
                logger.error(f"Reviewed subset file not found: {reviewed_subset_file}")
                return False
            
            with open(reviewed_subset_file, 'r') as f:
                reviewed_subset = json.load(f)
            
            # Load the proposed full mapping if it exists
            proposed_mapping_file = os.path.join(
                os.path.dirname(self.output_file), 
                "proposed_entity_mapping.json"
            )
            
            proposed_mapping = self.load_existing_reviewed(proposed_mapping_file)
            
            if not proposed_mapping:
                # If no proposed mapping exists, create one from the template
                if not self.load_analysis_data():
                    return False
                
                self.create_review_template()
                proposed_mapping = self.load_existing_reviewed(self.output_file)
            
            # Merge the reviewed subset into the full mapping
            for entity, split_entities in reviewed_subset.items():
                proposed_mapping[entity] = split_entities
            
            # Save the merged mapping
            full_mapping_file = os.path.join(
                os.path.dirname(self.output_file), 
                "reviewed_entity_mapping.json"
            )
            
            with open(full_mapping_file, 'w') as f:
                json.dump(proposed_mapping, f, indent=2)
            
            logger.info(f"Merged reviewed subset into full mapping at {full_mapping_file}")
            logger.info(f"Total entities in full mapping: {len(proposed_mapping)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error merging reviewed subset: {e}")
            return False
    
    def extract_subset(self, pattern: str) -> bool:
        """
        Extract a subset of entities containing a specific pattern for targeted review.
        
        Args:
            pattern: The pattern to match in entity names (case insensitive)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.load_analysis_data():
                return False
            
            # Extract entity candidates containing the pattern
            entity_candidates = self.analysis_data.get("entity_candidates", {})
            subset = {}
            
            for entity, split_candidates in entity_candidates.items():
                if pattern.lower() in entity.lower():
                    subset[entity] = split_candidates
            
            if not subset:
                logger.warning(f"No entities found containing pattern: {pattern}")
                return False
            
            # Save the subset
            subset_file = os.path.join(
                os.path.dirname(self.output_file), 
                f"review_{pattern.lower()}.json"
            )
            
            with open(subset_file, 'w') as f:
                json.dump(subset, f, indent=2)
            
            logger.info(f"Extracted {len(subset)} entities containing '{pattern}' to {subset_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error extracting subset: {e}")
            return False
    
    def run(self) -> bool:
        """
        Run the reviewer to create the template.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Starting double disclosure review template creation")
        
        if not self.load_analysis_data():
            return False
        
        return self.create_review_template()

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Create a template for reviewing double disclosures")
    parser.add_argument('--analysis-file', 
                        default="scripts/double_disclosure_results/double_disclosure_analysis.json",
                        help="Path to the analysis results file")
    parser.add_argument('--output-file', 
                        default="scripts/double_disclosure_results/proposed_entity_mapping.json",
                        help="Path to save the review template")
    parser.add_argument('--limit', type=int, default=100,
                        help="Number of top entities to extract for review")
    parser.add_argument('--extract', type=str,
                        help="Extract entities containing this pattern for targeted review")
    parser.add_argument('--merge', type=str,
                        help="Merge a reviewed subset file into the full mapping")
    
    args = parser.parse_args()
    
    reviewer = DoubleDisclosureReviewer(
        analysis_file=args.analysis_file,
        output_file=args.output_file,
        limit=args.limit
    )
    
    if args.extract:
        return 0 if reviewer.extract_subset(args.extract) else 1
    elif args.merge:
        return 0 if reviewer.merge_into_full_mapping(args.merge) else 1
    else:
        return 0 if reviewer.run() else 1

if __name__ == '__main__':
    main() 