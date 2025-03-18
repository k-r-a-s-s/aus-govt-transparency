#!/usr/bin/env python3
"""
Analyze entity timelines.

This script analyzes the timelines of entities for a specific MP or all MPs.
"""

import os
import argparse
import logging
import json
import sqlite3
from typing import Dict, Any, List
from db_handler import DatabaseHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def analyze_mp_entities(db_path: str, mp_name: str, output_dir: str = None):
    """
    Analyze entities for a specific MP.
    
    Args:
        db_path: Path to the SQLite database file.
        mp_name: Name of the MP to analyze.
        output_dir: Directory to save the analysis results.
    """
    logger.info(f"Analyzing entities for MP: {mp_name}")
    
    # Initialize database handler
    db_handler = DatabaseHandler(db_path=db_path)
    
    # Get all entities for this MP
    entities = db_handler.get_mp_entities(mp_name)
    
    logger.info(f"Found {len(entities)} entities for MP: {mp_name}")
    
    # Analyze each entity
    entity_timelines = []
    for entity in entities:
        entity_id = entity["id"]
        entity_timeline = db_handler.get_entity_timeline(entity_id)
        entity_timelines.append(entity_timeline)
    
    # Save results if output directory provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{mp_name.replace(' ', '_')}_entities.json")
        
        with open(output_path, "w") as f:
            json.dump(entity_timelines, f, indent=2)
        
        logger.info(f"Saved entity analysis to: {output_path}")
    
    return entity_timelines

def analyze_entity_changes(entity_timeline: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze changes in an entity's timeline.
    
    Args:
        entity_timeline: The entity timeline to analyze.
        
    Returns:
        A dictionary containing the analysis results.
    """
    entity = entity_timeline["entity"]
    timeline = entity_timeline["timeline"]
    
    # Sort timeline by declaration date
    timeline = sorted(timeline, key=lambda x: x["declaration_date"])
    
    # Analyze changes
    changes = []
    for i in range(1, len(timeline)):
        prev = timeline[i-1]
        curr = timeline[i]
        
        # Check for changes in details
        if prev["details"] != curr["details"]:
            changes.append({
                "type": "details_change",
                "date": curr["declaration_date"],
                "from": prev["details"],
                "to": curr["details"]
            })
    
    return {
        "entity": entity,
        "first_appearance": timeline[0]["declaration_date"] if timeline else None,
        "last_appearance": timeline[-1]["declaration_date"] if timeline else None,
        "num_appearances": len(timeline),
        "changes": changes
    }

def compare_mp_entities(db_path: str, mp_name1: str, mp_name2: str, output_dir: str = None):
    """
    Compare entities between two MPs.
    
    Args:
        db_path: Path to the SQLite database file.
        mp_name1: Name of the first MP.
        mp_name2: Name of the second MP.
        output_dir: Directory to save the comparison results.
    """
    logger.info(f"Comparing entities between {mp_name1} and {mp_name2}")
    
    # Initialize database handler
    db_handler = DatabaseHandler(db_path=db_path)
    
    # Compare entities
    comparison = db_handler.compare_mp_entities(mp_name1, mp_name2)
    
    # Print summary
    print(f"Comparison between {mp_name1} and {mp_name2}:")
    print(f"- {mp_name1} has {comparison['mp1_entity_count']} entities")
    print(f"- {mp_name2} has {comparison['mp2_entity_count']} entities")
    print(f"- They have {comparison['common_entity_count']} entities in common")
    
    if comparison['common_entities']:
        print("\nCommon entities:")
        for entity in comparison['common_entities']:
            print(f"- {entity['entity_type']}: {entity['canonical_name']}")
    
    # Save results if output directory provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"comparison_{mp_name1.replace(' ', '_')}_{mp_name2.replace(' ', '_')}.json")
        
        with open(output_path, "w") as f:
            json.dump(comparison, f, indent=2)
        
        logger.info(f"Saved comparison to: {output_path}")
    
    return comparison

def main():
    """
    Main function to analyze entity timelines.
    """
    parser = argparse.ArgumentParser(description="Analyze entity timelines")
    parser.add_argument("--mp", help="Name of the MP to analyze")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to SQLite database file")
    parser.add_argument("--output-dir", help="Directory to save analysis results")
    parser.add_argument("--entity-id", help="ID of a specific entity to analyze")
    parser.add_argument("--compare", nargs=2, metavar=('MP1', 'MP2'), help="Compare entities between two MPs")
    
    args = parser.parse_args()
    
    # Initialize database handler
    db_handler = DatabaseHandler(db_path=args.db_path)
    
    # Compare MPs
    if args.compare:
        mp_name1, mp_name2 = args.compare
        compare_mp_entities(args.db_path, mp_name1, mp_name2, args.output_dir)
    
    # Analyze specific entity
    elif args.entity_id:
        entity_timeline = db_handler.get_entity_timeline(args.entity_id)
        analysis = analyze_entity_changes(entity_timeline)
        
        print(f"Entity: {analysis['entity']['canonical_name']}")
        print(f"Type: {analysis['entity']['entity_type']}")
        print(f"First appearance: {analysis['first_appearance']}")
        print(f"Last appearance: {analysis['last_appearance']}")
        print(f"Number of appearances: {analysis['num_appearances']}")
        
        if analysis['changes']:
            print("\nChanges:")
            for change in analysis['changes']:
                print(f"  {change['date']}: {change['type']}")
                print(f"    From: {change['from']}")
                print(f"    To: {change['to']}")
        
        # Save results if output directory provided
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
            output_path = os.path.join(args.output_dir, f"entity_{args.entity_id}.json")
            
            with open(output_path, "w") as f:
                json.dump(analysis, f, indent=2)
            
            logger.info(f"Saved entity analysis to: {output_path}")
    
    # Analyze MP entities
    elif args.mp:
        analyze_mp_entities(args.db_path, args.mp, args.output_dir)
    
    # List all MPs
    else:
        conn = sqlite3.connect(args.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT mp_name FROM disclosures")
        mp_names = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        print("Available MPs:")
        for mp_name in sorted(mp_names):
            print(f"- {mp_name}")

if __name__ == "__main__":
    main() 