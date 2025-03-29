#!/usr/bin/env python
"""
Summarize Gemini double disclosure entity analysis results.

This script processes the compiled results from the Gemini AI analysis of potential 
double disclosure entities and generates detailed summary reports, statistics, 
and a CSV file for easier review in a spreadsheet application.
"""

import os
import sys
import json
import csv
import argparse
import logging
from typing import Dict, List, Any, Tuple
from collections import Counter

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GeminiDoubleDisclosureAnalyzer:
    """
    Summarize and analyze Gemini AI results for double disclosure entity detection.
    
    This class processes the output from Gemini AI entity analysis, which identifies
    whether entities in the database represent multiple separate entities that should
    be split (true double disclosures) or single organizations with compound names.
    """
    
    def __init__(self, input_file: str, output_dir: str):
        """
        Initialize the analyzer.
        
        Args:
            input_file: Path to the compiled results JSON file
            output_dir: Directory to save summary files to
        """
        self.input_file = input_file
        self.output_dir = output_dir
        
        # Ensure output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def load_results(self) -> Dict[str, Any]:
        """
        Load double disclosure analysis results from JSON file.
        
        Returns:
            Dict[str, Any]: Loaded results
        """
        logger.info(f"Loading results from {self.input_file}")
        with open(self.input_file, 'r') as f:
            results = json.load(f)
        
        return results
    
    def generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a summary of the double disclosure analysis results.
        
        Args:
            results: Loaded analysis results
            
        Returns:
            Dict[str, Any]: Summary statistics
        """
        logger.info("Generating summary statistics")
        
        # Extract basic statistics already in the results
        total_entities = results.get("total_entities_analyzed", 0)
        classification_counts = results.get("classification_counts", {})
        confidence_counts = results.get("confidence_counts", {})
        high_confidence_multiple_count = results.get("high_confidence_multiple_count", 0)
        
        # Calculate percentages
        single_percentage = (classification_counts.get("single", 0) / total_entities * 100) if total_entities > 0 else 0
        multiple_percentage = (classification_counts.get("multiple", 0) / total_entities * 100) if total_entities > 0 else 0
        high_confidence_percentage = (confidence_counts.get("high", 0) / total_entities * 100) if total_entities > 0 else 0
        high_confidence_multiple_percentage = (high_confidence_multiple_count / total_entities * 100) if total_entities > 0 else 0
        
        # Count by category (using first part of batch_id)
        entity_results = results.get("entity_results", [])
        categories = Counter()
        
        # Count entities with specific separators
        separator_counts = {
            "and": 0,
            "ampersand": 0,
            "comma": 0,
            "slash": 0,
            "plus": 0,
            "other": 0
        }
        
        for entity in entity_results:
            entity_name = entity.get("entity_name", "")
            classification = entity.get("classification", "")
            confidence = entity.get("confidence", "")
            
            # Count by separator
            if " and " in entity_name or entity_name.startswith("and ") or entity_name.endswith(" and"):
                separator_counts["and"] += 1
            elif "&" in entity_name:
                separator_counts["ampersand"] += 1
            elif "," in entity_name:
                separator_counts["comma"] += 1
            elif "/" in entity_name:
                separator_counts["slash"] += 1
            elif "+" in entity_name:
                separator_counts["plus"] += 1
            else:
                separator_counts["other"] += 1
        
        # Generate summary
        summary = {
            "total_entities_analyzed": total_entities,
            "classification_counts": classification_counts,
            "confidence_counts": confidence_counts,
            "high_confidence_multiple_count": high_confidence_multiple_count,
            "percentages": {
                "single": round(single_percentage, 2),
                "multiple": round(multiple_percentage, 2),
                "high_confidence": round(high_confidence_percentage, 2),
                "high_confidence_multiple": round(high_confidence_multiple_percentage, 2)
            },
            "separator_counts": separator_counts
        }
        
        return summary
    
    def export_to_csv(self, results: Dict[str, Any]) -> str:
        """
        Export double disclosure entity results to CSV for easier review.
        
        Args:
            results: Loaded analysis results
            
        Returns:
            str: Path to the generated CSV file
        """
        entity_results = results.get("entity_results", [])
        
        # Sort results - high confidence multiples first, then by classification and confidence
        sorted_results = sorted(
            entity_results,
            key=lambda x: (
                0 if x.get("classification") == "MULTIPLE" and x.get("confidence") == "HIGH" else 1,
                0 if x.get("classification") == "MULTIPLE" else 1,
                0 if x.get("confidence") == "HIGH" else (1 if x.get("confidence") == "MEDIUM" else 2)
            )
        )
        
        # Define CSV file path
        csv_file = os.path.join(self.output_dir, "double_disclosure_entity_analysis.csv")
        logger.info(f"Exporting {len(sorted_results)} entities to {csv_file}")
        
        # Write to CSV
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Entity Name", 
                "Classification", 
                "Confidence", 
                "Split Entities", 
                "Explanation"
            ])
            
            for entity in sorted_results:
                split_entities = ", ".join(entity.get("split_entities", []))
                writer.writerow([
                    entity.get("entity_name", ""),
                    entity.get("classification", ""),
                    entity.get("confidence", ""),
                    split_entities,
                    entity.get("explanation", "")
                ])
        
        return csv_file
    
    def save_summary(self, summary: Dict[str, Any]) -> str:
        """
        Save summary statistics to a JSON file.
        
        Args:
            summary: Generated summary statistics
            
        Returns:
            str: Path to the saved summary file
        """
        summary_file = os.path.join(self.output_dir, "double_disclosure_analysis_summary.json")
        logger.info(f"Saving summary statistics to {summary_file}")
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary_file
    
    def generate_markdown_report(self, summary: Dict[str, Any], csv_file: str) -> str:
        """
        Generate a markdown report from the summary statistics.
        
        Args:
            summary: Generated summary statistics
            csv_file: Path to the generated CSV file
            
        Returns:
            str: Path to the generated markdown report
        """
        report_file = os.path.join(self.output_dir, "double_disclosure_analysis_report.md")
        logger.info(f"Generating markdown report to {report_file}")
        
        with open(report_file, 'w') as f:
            f.write("# Double Disclosure Entity Analysis Report\n\n")
            
            f.write("## Summary\n\n")
            f.write(f"- Total entities analyzed: {summary['total_entities_analyzed']}\n")
            f.write(f"- Single entities: {summary['classification_counts'].get('single', 0)} ({summary['percentages']['single']}%)\n")
            f.write(f"- Multiple entities: {summary['classification_counts'].get('multiple', 0)} ({summary['percentages']['multiple']}%)\n")
            f.write(f"- High confidence classifications: {summary['confidence_counts'].get('high', 0)} ({summary['percentages']['high_confidence']}%)\n")
            f.write(f"- High confidence multiple entities: {summary['high_confidence_multiple_count']} ({summary['percentages']['high_confidence_multiple']}%)\n\n")
            
            f.write("## Entities by Separator\n\n")
            f.write("| Separator | Count |\n")
            f.write("|-----------|-------|\n")
            for separator, count in summary['separator_counts'].items():
                f.write(f"| {separator} | {count} |\n")
            
            f.write("\n## Next Steps\n\n")
            f.write(f"1. Review the [CSV file]({os.path.basename(csv_file)}) to validate the analysis results\n")
            f.write("2. Focus on high confidence multiple entities for database updates\n")
            f.write("3. Manually review medium and low confidence classifications\n")
            f.write("4. Update the database schema with a new column for original_entity\n")
            f.write("5. Apply the validated mappings to split entities in the database\n")
        
        return report_file
    
    def run(self) -> Tuple[str, str, str]:
        """
        Run the summarization process.
        
        Returns:
            Tuple[str, str, str]: Paths to the summary file, CSV file, and markdown report
        """
        results = self.load_results()
        summary = self.generate_summary(results)
        csv_file = self.export_to_csv(results)
        summary_file = self.save_summary(summary)
        report_file = self.generate_markdown_report(summary, csv_file)
        
        logger.info("Double disclosure entity analysis summarization complete")
        return summary_file, csv_file, report_file

def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description="Summarize Gemini double disclosure entity analysis results")
    parser.add_argument("--input-file", default="scripts/gemini_results/compiled_results.json", help="Path to compiled results JSON file")
    parser.add_argument("--output-dir", default="scripts/gemini_summary", help="Directory to save summary files to")
    
    args = parser.parse_args()
    
    # Run the summarization
    analyzer = GeminiDoubleDisclosureAnalyzer(
        input_file=args.input_file,
        output_dir=args.output_dir
    )
    
    analyzer.run()

if __name__ == "__main__":
    main() 