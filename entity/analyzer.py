"""
Entity analyzer module for analyzing parliamentary disclosure entities.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from ..db.db_handler import DatabaseHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EntityAnalyzer:
    """
    A class to analyze entities in parliamentary disclosures.
    """
    
    def __init__(self, db_path: str = "disclosures.db"):
        """
        Initialize the entity analyzer.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.db_handler = DatabaseHandler(db_path=db_path)
    
    def analyze_mp_entities(self, mp_name: str, output_dir: str = None) -> List[Dict[str, Any]]:
        """
        Analyze entities for a specific MP.
        
        Args:
            mp_name: Name of the MP to analyze.
            output_dir: Directory to save the analysis results.
            
        Returns:
            A list of entity timelines.
        """
        logger.info(f"Analyzing entities for MP: {mp_name}")
        
        # Get all entities for this MP
        entities = self.db_handler.get_mp_entities(mp_name)
        
        logger.info(f"Found {len(entities)} entities for MP: {mp_name}")
        
        # Analyze each entity
        entity_timelines = []
        for entity in entities:
            entity_id = entity["id"]
            entity_timeline = self.db_handler.get_entity_timeline(entity_id)
            entity_timelines.append(entity_timeline)
        
        # Save results if output directory provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{mp_name.replace(' ', '_')}_entities.json")
            
            with open(output_path, "w") as f:
                json.dump(entity_timelines, f, indent=2)
            
            logger.info(f"Saved entity analysis to: {output_path}")
        
        return entity_timelines
    
    def analyze_entity_changes(self, entity_id: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Analyze changes in an entity's timeline.
        
        Args:
            entity_id: The ID of the entity to analyze.
            output_dir: Directory to save the analysis results.
            
        Returns:
            A dictionary containing the analysis results.
        """
        entity_timeline = self.db_handler.get_entity_timeline(entity_id)
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
            
            # Check for changes in category
            if prev["category"] != curr["category"]:
                changes.append({
                    "type": "category_change",
                    "date": curr["declaration_date"],
                    "from": prev["category"],
                    "to": curr["category"]
                })
            
            # Check for changes in sub_category
            if prev.get("sub_category") != curr.get("sub_category"):
                changes.append({
                    "type": "sub_category_change",
                    "date": curr["declaration_date"],
                    "from": prev.get("sub_category"),
                    "to": curr.get("sub_category")
                })
        
        analysis = {
            "entity": entity,
            "first_appearance": timeline[0]["declaration_date"] if timeline else None,
            "last_appearance": timeline[-1]["declaration_date"] if timeline else None,
            "num_appearances": len(timeline),
            "changes": changes
        }
        
        # Save results if output directory provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"entity_{entity_id}.json")
            
            with open(output_path, "w") as f:
                json.dump(analysis, f, indent=2)
            
            logger.info(f"Saved entity analysis to: {output_path}")
        
        return analysis
    
    def compare_mp_entities(self, mp_name1: str, mp_name2: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Compare entities between two MPs.
        
        Args:
            mp_name1: Name of the first MP.
            mp_name2: Name of the second MP.
            output_dir: Directory to save the comparison results.
            
        Returns:
            A dictionary containing comparison results.
        """
        logger.info(f"Comparing entities between {mp_name1} and {mp_name2}")
        
        # Compare entities
        comparison = self.db_handler.compare_mp_entities(mp_name1, mp_name2)
        
        # Save results if output directory provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"comparison_{mp_name1.replace(' ', '_')}_{mp_name2.replace(' ', '_')}.json")
            
            with open(output_path, "w") as f:
                json.dump(comparison, f, indent=2)
            
            logger.info(f"Saved comparison to: {output_path}")
        
        return comparison
    
    def get_all_mps(self) -> List[str]:
        """
        Get a list of all MPs in the database.
        
        Returns:
            A list of MP names.
        """
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT mp_name FROM disclosures")
        mp_names = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return sorted(mp_names) 