#!/usr/bin/env python
"""
Prepare Data for Gemini Analysis of Double Disclosures

This script prepares data from the potential double disclosures dataset for analysis by Gemini.
It extracts the relevant columns and formats the data into batches suitable for API processing.

Usage:
    python prepare_gemini_entity_analysis.py [--input_file FILE] [--batch_size SIZE]
"""

import os
import json
import csv
import argparse
import logging
from typing import List, Dict, Any, Set
import pandas as pd
from collections import defaultdict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GeminiDataPreparer:
    """
    Prepares data for Gemini analysis of double disclosures.
    """
    
    def __init__(
        self,
        input_file: str = "scripts/double_disclosure_results/potential_double_disclosures.csv",
        output_dir: str = "scripts/gemini_analysis",
        batch_size: int = 50
    ):
        """
        Initialize the data preparer.
        
        Args:
            input_file: Path to the CSV file containing potential double disclosures
            output_dir: Directory for saving prepared data files
            batch_size: Number of entities per batch for Gemini analysis
        """
        self.input_file = input_file
        self.output_dir = output_dir
        self.batch_size = batch_size
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Will hold the processed data
        self.entities = {}
        self.entity_context = defaultdict(list)
        self.categorized_entities = defaultdict(list)
    
    def load_data(self) -> bool:
        """
        Load and preprocess the potential double disclosures data.
        
        Returns:
            bool: True if data was loaded successfully, False otherwise
        """
        try:
            if not os.path.exists(self.input_file):
                logger.error(f"Input file not found: {self.input_file}")
                return False
            
            # Load data with pandas for easy manipulation
            df = pd.read_csv(self.input_file)
            logger.info(f"Loaded {len(df)} potential double disclosure records")
            
            # Extract unique entities and their context
            for _, row in df.iterrows():
                entity = row['entity']
                if entity not in self.entities:
                    # Use the proposed split from the entity_candidates if available
                    proposed_split = None
                    
                    # Create a context object with relevant information
                    context = {
                        'mp_name': row['mp_name'],
                        'party': row['party'],
                        'category': row['category'],
                        'sub_category': row['sub_category'],
                        'item': row['item'],
                        'details': row['details'] if pd.notna(row['details']) else ""
                    }
                    
                    self.entity_context[entity].append(context)
            
            # Load entity_candidates file to get proposed splits
            analysis_file = os.path.join(os.path.dirname(self.input_file), "double_disclosure_analysis.json")
            if os.path.exists(analysis_file):
                with open(analysis_file, 'r') as f:
                    analysis_data = json.load(f)
                    entity_candidates = analysis_data.get("entity_candidates", {})
                    
                    for entity, proposed_splits in entity_candidates.items():
                        if entity in self.entity_context:
                            self.entities[entity] = {
                                'entity': entity,
                                'proposed_splits': proposed_splits,
                                'context': self.entity_context[entity][:5]  # Limit to 5 context examples
                            }
            else:
                # If analysis file not found, use entities without proposed splits
                for entity in self.entity_context:
                    self.entities[entity] = {
                        'entity': entity,
                        'proposed_splits': [],
                        'context': self.entity_context[entity][:5]  # Limit to 5 context examples
                    }
            
            logger.info(f"Prepared {len(self.entities)} unique entities for analysis")
            
            # Categorize entities by separator type for batch processing
            for entity in self.entities:
                # Simple categorization based on separator
                if " and " in entity.lower():
                    self.categorized_entities["and"].append(entity)
                elif "&" in entity:
                    self.categorized_entities["ampersand"].append(entity)
                elif "," in entity:
                    self.categorized_entities["comma"].append(entity)
                elif "/" in entity:
                    self.categorized_entities["slash"].append(entity)
                elif "+" in entity:
                    self.categorized_entities["plus"].append(entity)
                else:
                    self.categorized_entities["other"].append(entity)
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return False
    
    def create_batches(self) -> bool:
        """
        Create batches of entities for Gemini analysis.
        
        Returns:
            bool: True if batches were created successfully, False otherwise
        """
        try:
            batch_id = 1
            
            # Process each category separately to keep similar entities together
            for category, entities in self.categorized_entities.items():
                logger.info(f"Creating batches for category '{category}' with {len(entities)} entities")
                
                # Process entities in batches
                for i in range(0, len(entities), self.batch_size):
                    batch_entities = entities[i:i + self.batch_size]
                    
                    # Create a batch with entity details
                    batch = {
                        "batch_id": f"{category}_{batch_id}",
                        "category": category,
                        "entities": [self.entities[entity] for entity in batch_entities]
                    }
                    
                    # Save batch to file
                    batch_file = os.path.join(self.output_dir, f"batch_{category}_{batch_id}.json")
                    with open(batch_file, 'w') as f:
                        json.dump(batch, f, indent=2)
                    
                    logger.info(f"Created batch {batch_id} with {len(batch_entities)} entities, saved to {batch_file}")
                    batch_id += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating batches: {e}")
            return False
    
    def create_prompt_template(self) -> bool:
        """
        Create a prompt template for Gemini analysis.
        
        Returns:
            bool: True if template was created successfully, False otherwise
        """
        try:
            prompt_template = {
                "system_prompt": """You are an expert in Australian organizations, companies, and government entities. Your task is to analyze a list of entity names and determine whether each is:
1) A single organization with a compound name (like "Australian and New Zealand Banking Group Limited")
2) A true double disclosure where two or more separate entities are mentioned together (like "Shell and Optus")

Consider the Australian context carefully. Many legitimate Australian organizations contain words like "and" or "&" in their formal names.

For each entity, provide:
1. Classification: "SINGLE" or "MULTIPLE"
2. Confidence: HIGH, MEDIUM, or LOW
3. Explanation: Brief justification for your decision
4. If MULTIPLE, the correct split of the entity name into separate entities

Only classify as MULTIPLE with HIGH confidence if you are certain these are separate entities mentioned together. 
If you have any doubt, label as SINGLE or with lower confidence.""",
                "user_prompt_template": """Please analyze the following list of Australian entity names to determine if they are single organizations with compound names or true double disclosures (multiple entities):

{entity_list}

For each entity, provide your analysis in JSON format:
```json
{
  "entity_name": "Example Entity Name",
  "classification": "SINGLE or MULTIPLE",
  "confidence": "HIGH, MEDIUM, or LOW",
  "explanation": "Your reasoning here",
  "split_entities": ["Entity 1", "Entity 2"] (only if MULTIPLE)
}
```

Consider Australian context, organizational naming conventions, and the provided context for each entity. Focus on high-precision identification of true double disclosures."""
            }
            
            # Save template to file
            template_file = os.path.join(self.output_dir, "prompt_template.json")
            with open(template_file, 'w') as f:
                json.dump(prompt_template, f, indent=2)
            
            logger.info(f"Created prompt template at {template_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating prompt template: {e}")
            return False
    
    def run(self) -> bool:
        """
        Run the complete data preparation process.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Starting Gemini data preparation")
        
        if not self.load_data():
            return False
        
        if not self.create_batches():
            return False
        
        if not self.create_prompt_template():
            return False
        
        logger.info("Data preparation complete")
        return True

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Prepare data for Gemini analysis of double disclosures")
    parser.add_argument('--input-file', 
                        default="scripts/double_disclosure_results/potential_double_disclosures.csv",
                        help="Path to the CSV file containing potential double disclosures")
    parser.add_argument('--output-dir', 
                        default="scripts/gemini_analysis",
                        help="Directory for saving prepared data files")
    parser.add_argument('--batch-size', type=int, default=50,
                        help="Number of entities per batch for Gemini analysis")
    
    args = parser.parse_args()
    
    preparer = GeminiDataPreparer(
        input_file=args.input_file,
        output_dir=args.output_dir,
        batch_size=args.batch_size
    )
    
    success = preparer.run()
    return 0 if success else 1

if __name__ == '__main__':
    main() 