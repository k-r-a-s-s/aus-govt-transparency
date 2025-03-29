#!/usr/bin/env python3
import sqlite3
import pandas as pd
import numpy as np
import json
import logging
import os
from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path
from rapidfuzz import fuzz, process
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('entity_dedupe')

# Constants
DB_PATH = Path(__file__).parent.parent / "disclosures.db"
OUTPUT_PATH = Path(__file__).parent / "entity_dedupe_results"
SIMILARITY_THRESHOLD = 80  # Default threshold for fuzzy matching
MIN_ENTITY_LENGTH = 4  # Ignore very short entity names

class EntityDedupeAnalyzer:
    """Analyze entity names in the database to find potential duplicates."""
    
    def __init__(self, db_path: Path, threshold: int = SIMILARITY_THRESHOLD):
        """Initialize the analyzer with the database path."""
        self.db_path = db_path
        self.threshold = threshold
        self.entities: Dict[str, int] = {}  # entity name -> count
        self.ignore_patterns: List[str] = []
        
        # Create output directory if it doesn't exist
        OUTPUT_PATH.mkdir(exist_ok=True)
        
    def load_entities_from_db(self) -> None:
        """Extract all unique entities from the database with their counts."""
        logger.info(f"Connecting to database at {self.db_path}")
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Query to get all entities and their counts
            query = """
            SELECT entity, COUNT(*) as count
            FROM disclosures
            WHERE entity IS NOT NULL AND trim(entity) != ''
            GROUP BY entity
            ORDER BY count DESC
            """
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            # Convert to dictionary for easier access
            self.entities = dict(zip(df['entity'], df['count']))
            
            logger.info(f"Loaded {len(self.entities)} unique entities from database")
            
            # Save top entities to file for reference
            top_entities = pd.DataFrame({
                'entity': list(self.entities.keys()),
                'count': list(self.entities.values())
            }).head(100)
            
            top_entities.to_csv(OUTPUT_PATH / "top_entities.csv", index=False)
            logger.info(f"Saved top 100 entities to {OUTPUT_PATH}/top_entities.csv")
            
        except Exception as e:
            logger.error(f"Error loading entities from database: {e}")
            raise
    
    def find_similar_entities(self) -> Dict[str, List[Dict[str, any]]]:
        """
        Find similar entities using fuzzy matching.
        Returns a dictionary mapping canonical names to lists of similar entities.
        """
        logger.info("Finding similar entities...")
        
        # Filter out very short entities to reduce noise
        filtered_entities = {k: v for k, v in self.entities.items() 
                           if len(k) >= MIN_ENTITY_LENGTH}
        
        entity_names = list(filtered_entities.keys())
        similarity_groups = defaultdict(list)
        
        # Track which entities have been processed
        processed = set()
        
        # Process entities in order of frequency (most frequent first)
        sorted_entities = sorted(filtered_entities.items(), 
                                key=lambda x: x[1], reverse=True)
        
        for canonical, count in sorted_entities:
            if canonical in processed:
                continue
                
            # Skip processing this entity if it matches any ignore pattern
            if any(pattern.lower() in canonical.lower() for pattern in self.ignore_patterns):
                continue
                
            # Find similar entities
            matches = process.extract(
                canonical, 
                entity_names,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=self.threshold,
                limit=50
            )
            
            # Skip if only found itself
            if len(matches) <= 1:
                continue
                
            # Add matches to the group
            for match_name, score, _ in matches:
                if match_name != canonical and match_name not in processed:
                    similarity_groups[canonical].append({
                        'entity': match_name,
                        'score': score,
                        'count': filtered_entities[match_name]
                    })
                    processed.add(match_name)
            
            # Mark canonical as processed
            processed.add(canonical)
        
        # Filter out groups with only the canonical entity
        similarity_groups = {k: v for k, v in similarity_groups.items() if v}
        
        logger.info(f"Found {len(similarity_groups)} groups of similar entities")
        return similarity_groups
    
    def generate_mapping_file(self, similarity_groups: Dict[str, List[Dict[str, any]]]) -> None:
        """Generate a proposed mapping file based on similarity groups."""
        mapping = {}
        
        for canonical, variants in similarity_groups.items():
            # Add the variants to the mapping
            variant_names = [item['entity'] for item in variants]
            mapping[canonical] = variant_names
        
        # Save mapping to file
        with open(OUTPUT_PATH / "proposed_entity_mapping.json", 'w') as f:
            json.dump(mapping, f, indent=2)
        
        logger.info(f"Saved proposed entity mapping to {OUTPUT_PATH}/proposed_entity_mapping.json")
        
        # Save the full similarity results with scores for reference
        with open(OUTPUT_PATH / "entity_similarity_groups.json", 'w') as f:
            json.dump(similarity_groups, f, indent=2)
            
        logger.info(f"Saved detailed similarity groups to {OUTPUT_PATH}/entity_similarity_groups.json")
    
    def generate_example_groups(self, similarity_groups: Dict[str, List[Dict[str, any]]]) -> None:
        """Generate a CSV with example groups for easier review."""
        all_groups = []
        
        for canonical, variants in similarity_groups.items():
            # Add canonical to the group
            group_data = {
                'canonical_name': canonical,
                'entity_name': canonical,
                'similarity_score': 100,
                'count': self.entities.get(canonical, 0),
                'group_id': len(all_groups) + 1
            }
            all_groups.append(group_data)
            
            # Add all variants
            for variant in variants:
                group_data = {
                    'canonical_name': canonical,
                    'entity_name': variant['entity'],
                    'similarity_score': variant['score'],
                    'count': variant['count'],
                    'group_id': len(all_groups)
                }
                all_groups.append(group_data)
        
        # Convert to DataFrame and save
        df = pd.DataFrame(all_groups)
        df.to_csv(OUTPUT_PATH / "entity_groups_for_review.csv", index=False)
        logger.info(f"Saved entity groups for review to {OUTPUT_PATH}/entity_groups_for_review.csv")
    
    def analyze(self) -> None:
        """Run the complete analysis process."""
        self.load_entities_from_db()
        similarity_groups = self.find_similar_entities()
        self.generate_mapping_file(similarity_groups)
        self.generate_example_groups(similarity_groups)
        
        # Print some statistics
        total_groups = len(similarity_groups)
        total_variants = sum(len(variants) for variants in similarity_groups.values())
        
        logger.info(f"Analysis complete.")
        logger.info(f"Found {total_groups} potential duplicate groups with {total_variants} total variant names")
        logger.info(f"Review the results in the {OUTPUT_PATH} directory")
        
        # Search for "Shell" to demonstrate the specific example
        self._search_example("Shell")
        
    def _search_example(self, search_term: str) -> None:
        """Search for a specific term in entities and show examples."""
        matching_entities = [name for name in self.entities.keys() 
                            if search_term.lower() in name.lower()]
        
        if matching_entities:
            logger.info(f"\nExample - Found {len(matching_entities)} entities containing '{search_term}':")
            for i, entity in enumerate(sorted(matching_entities)[:10]):
                logger.info(f"  {i+1}. {entity} ({self.entities[entity]} occurrences)")
            
            if len(matching_entities) > 10:
                logger.info(f"  ... and {len(matching_entities) - 10} more")

if __name__ == "__main__":
    analyzer = EntityDedupeAnalyzer(DB_PATH)
    analyzer.analyze() 