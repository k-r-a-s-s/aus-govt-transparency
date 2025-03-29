#!/usr/bin/env python
"""
Test Gemini Entity Workflow

This script tests the Gemini-based double disclosure detection workflow
with a small sample of test data. It's intended for development and validation
purposes before running the full workflow on production data.

Usage:
    python test_gemini_entity_workflow.py --api-key YOUR_API_KEY
"""

import os
import sys
import json
import tempfile
import argparse
import logging
import sqlite3
from typing import List, Dict, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sample test data
TEST_ENTITIES = [
    "ANZ and Commonwealth Bank",
    "BHP/Rio Tinto",
    "Shell & Optus",
    "Coles, Woolworths",
    "Telstra + Optus",
    "Bank of Queensland and Suncorp",
    "Australian Federal Police",  # Not a double disclosure
    "Department of Home Affairs",  # Not a double disclosure
    "PwC Australia",  # Not a double disclosure
    "Commonwealth Bank of Australia"  # Not a double disclosure
]

class GeminiWorkflowTester:
    """
    Tests the Gemini-based double disclosure detection workflow.
    """
    
    def __init__(
        self, 
        api_key: str,
        temp_dir: Optional[str] = None,
        model: str = "gemini-1.5-flash-latest"
    ):
        """
        Initialize the tester.
        
        Args:
            api_key: Google API key for Gemini
            temp_dir: Directory to store temporary files (if None, uses system temp dir)
            model: Gemini model to use
        """
        self.api_key = api_key
        self.model = model
        
        # Set up temporary directories
        if temp_dir:
            self.temp_dir = temp_dir
            os.makedirs(self.temp_dir, exist_ok=True)
        else:
            self.temp_dir = tempfile.mkdtemp(prefix="gemini_test_")
        
        logger.info(f"Using temporary directory: {self.temp_dir}")
        
        # Set up paths
        self.csv_path = os.path.join(self.temp_dir, "test_entities.csv")
        self.batch_dir = os.path.join(self.temp_dir, "batches")
        self.results_dir = os.path.join(self.temp_dir, "results")
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        os.makedirs(self.batch_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
    
    def create_test_data(self) -> None:
        """Create test CSV file and database."""
        logger.info("Creating test data")
        
        # Create CSV file
        with open(self.csv_path, 'w') as f:
            f.write("entity,count,separators\n")
            for entity in TEST_ENTITIES:
                separator = ""
                if " and " in entity:
                    separator = "and"
                elif "/" in entity:
                    separator = "/"
                elif "&" in entity:
                    separator = "&"
                elif "," in entity:
                    separator = ","
                elif "+" in entity:
                    separator = "+"
                
                f.write(f'"{entity}",1,"{separator}"\n')
        
        logger.info(f"Created test CSV file with {len(TEST_ENTITIES)} entities")
        
        # Create test database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE disclosures (
            id TEXT PRIMARY KEY,
            entity TEXT NOT NULL,
            amount REAL,
            date TEXT,
            type TEXT,
            canonical_entity TEXT
        )
        ''')
        
        # Insert test data
        for i, entity in enumerate(TEST_ENTITIES):
            cursor.execute('''
            INSERT INTO disclosures (id, entity, amount, date, type, canonical_entity) 
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (f"test-{i}", entity, 1000, "2023-01-01", "Donation", entity))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created test database at {self.db_path}")
    
    def run_preparation_step(self) -> bool:
        """Run the data preparation step."""
        logger.info("Running data preparation step")
        
        try:
            from prepare_gemini_entity_analysis import GeminiDataPreparer
            
            preparer = GeminiDataPreparer(
                input_file=self.csv_path,
                output_dir=self.batch_dir,
                batch_size=5  # Small batch size for testing
            )
            
            preparer.run()
            return True
            
        except ImportError:
            logger.error("Could not import prepare_gemini_entity_analysis module")
            logger.info("Testing script directly")
            
            cmd = f"python scripts/prepare_gemini_entity_analysis.py --input-file {self.csv_path} --output-dir {self.batch_dir} --batch-size 5"
            logger.info(f"Running command: {cmd}")
            
            return os.system(cmd) == 0
    
    def run_analysis_step(self) -> bool:
        """Run the Gemini analysis step."""
        logger.info("Running Gemini analysis step")
        
        # Save API key to file
        api_key_file = os.path.join(self.temp_dir, "api_key.txt")
        with open(api_key_file, 'w') as f:
            f.write(self.api_key)
        
        try:
            from gemini_entity_analyzer import GeminiEntityAnalyzer
            
            analyzer = GeminiEntityAnalyzer(
                input_dir=self.batch_dir,
                output_dir=self.results_dir,
                api_key=self.api_key,
                model=self.model,
                max_retries=2
            )
            
            analyzer.run()
            return True
            
        except ImportError:
            logger.error("Could not import gemini_entity_analyzer module")
            logger.info("Testing script directly")
            
            cmd = f"python scripts/gemini_entity_analyzer.py --input-dir {self.batch_dir} --output-dir {self.results_dir} --api-key-file {api_key_file} --model {self.model}"
            logger.info(f"Running command: {cmd}")
            
            return os.system(cmd) == 0
    
    def run_summary_step(self) -> bool:
        """Run the summarization step."""
        logger.info("Running summarization step")
        
        compiled_results = os.path.join(self.results_dir, "compiled_results.json")
        summary_csv = os.path.join(self.results_dir, "summary.csv")
        
        try:
            from summarize_gemini_results import GeminiResultsSummarizer
            
            summarizer = GeminiResultsSummarizer(
                input_file=compiled_results,
                output_file=summary_csv
            )
            
            summarizer.run()
            return True
            
        except ImportError:
            logger.error("Could not import summarize_gemini_results module")
            logger.info("Testing script directly")
            
            cmd = f"python scripts/summarize_gemini_results.py --input-file {compiled_results} --output-file {summary_csv}"
            logger.info(f"Running command: {cmd}")
            
            return os.system(cmd) == 0
    
    def run_application_step(self, dry_run: bool = True) -> bool:
        """Run the application step."""
        logger.info(f"Running application step (dry_run={dry_run})")
        
        compiled_results = os.path.join(self.results_dir, "compiled_results.json")
        
        try:
            from apply_gemini_entity_results import GeminiResultsApplier
            
            applier = GeminiResultsApplier(
                input_file=compiled_results,
                db_path=self.db_path,
                dry_run=dry_run
            )
            
            applier.run()
            return True
            
        except ImportError:
            logger.error("Could not import apply_gemini_entity_results module")
            logger.info("Testing script directly")
            
            cmd = f"python scripts/apply_gemini_entity_results.py --input-file {compiled_results} --db-path {self.db_path}"
            if dry_run:
                cmd += " --dry-run"
                
            logger.info(f"Running command: {cmd}")
            
            return os.system(cmd) == 0
    
    def verify_results(self) -> bool:
        """Verify the results of the workflow."""
        logger.info("Verifying results")
        
        # Check if the results file exists
        compiled_results = os.path.join(self.results_dir, "compiled_results.json")
        if not os.path.exists(compiled_results):
            logger.error(f"Compiled results file not found: {compiled_results}")
            return False
        
        # Load and print results
        with open(compiled_results, 'r') as f:
            results = json.load(f)
        
        total_entities = results.get("total_entities_analyzed", 0)
        entity_results = results.get("entity_results", [])
        
        logger.info(f"Results summary:")
        logger.info(f"- Total entities analyzed: {total_entities}")
        logger.info(f"- Total entity results: {len(entity_results)}")
        
        # Count by classification and confidence
        classifications = {}
        confidences = {}
        
        for entity in entity_results:
            classification = entity.get("classification", "UNKNOWN")
            confidence = entity.get("confidence", "UNKNOWN")
            
            classifications[classification] = classifications.get(classification, 0) + 1
            confidences[confidence] = confidences.get(confidence, 0) + 1
        
        logger.info("Classifications:")
        for c, count in classifications.items():
            logger.info(f"- {c}: {count}")
        
        logger.info("Confidences:")
        for c, count in confidences.items():
            logger.info(f"- {c}: {count}")
        
        # Check database for changes (if applied)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if original_entity column exists
            cursor.execute("PRAGMA table_info(disclosures)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'original_entity' in columns:
                cursor.execute("SELECT COUNT(*) FROM disclosures WHERE original_entity IS NOT NULL")
                count = cursor.fetchone()[0]
                logger.info(f"Database has {count} records with original_entity set")
            
            conn.close()
        except Exception as e:
            logger.error(f"Error checking database: {e}")
        
        return True
    
    def run_workflow(self, apply_changes: bool = False) -> bool:
        """
        Run the complete workflow.
        
        Args:
            apply_changes: If True, actually apply changes to the database
            
        Returns:
            bool: True if workflow completed successfully, False otherwise
        """
        logger.info("Starting Gemini workflow test")
        
        # Create test data
        self.create_test_data()
        
        # Run preparation step
        if not self.run_preparation_step():
            logger.error("Preparation step failed")
            return False
        
        # Run analysis step
        if not self.run_analysis_step():
            logger.error("Analysis step failed")
            return False
        
        # Run summary step
        if not self.run_summary_step():
            logger.error("Summary step failed")
            return False
        
        # Run application step (dry run)
        if not self.run_application_step(dry_run=True):
            logger.error("Application step (dry run) failed")
            return False
        
        # Apply changes if requested
        if apply_changes:
            if not self.run_application_step(dry_run=False):
                logger.error("Application step failed")
                return False
        
        # Verify results
        if not self.verify_results():
            logger.error("Results verification failed")
            return False
        
        logger.info("Workflow test completed successfully")
        return True

def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description="Test the Gemini-based double disclosure detection workflow")
    parser.add_argument('--api-key', required=True,
                        help="Google API key for Gemini")
    parser.add_argument('--api-key-file',
                        help="File containing Google API key for Gemini")
    parser.add_argument('--temp-dir',
                        help="Directory to store temporary files")
    parser.add_argument('--model', default="gemini-1.5-flash-latest",
                        help="Gemini model to use")
    parser.add_argument('--apply', action='store_true',
                        help="Actually apply changes to the test database")
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key
    if args.api_key_file:
        with open(args.api_key_file, 'r') as f:
            api_key = f.read().strip()
    
    tester = GeminiWorkflowTester(
        api_key=api_key,
        temp_dir=args.temp_dir,
        model=args.model
    )
    
    success = tester.run_workflow(apply_changes=args.apply)
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main()) 