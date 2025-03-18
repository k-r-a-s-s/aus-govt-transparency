"""
Entity visualization module for creating visualizations of parliamentary disclosure entities.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import pandas as pd
from collections import Counter, defaultdict
from ..db.db_handler import DatabaseHandler
from ..entity.analyzer import EntityAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EntityVisualizer:
    """
    A class to create visualizations for parliamentary disclosure entities.
    """
    
    def __init__(self, db_path: str = "disclosures.db"):
        """
        Initialize the entity visualizer.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.db_handler = DatabaseHandler(db_path=db_path)
        self.analyzer = EntityAnalyzer(db_path=db_path)
        
        # Set up matplotlib style
        plt.style.use('ggplot')
    
    def visualize_entity_distribution(self, mp_name: str, output_dir: str = "outputs/visualizations") -> str:
        """
        Create a visualization of entity distribution by category for an MP.
        
        Args:
            mp_name: Name of the MP to visualize.
            output_dir: Directory to save the visualization.
            
        Returns:
            Path to the saved visualization.
        """
        logger.info(f"Creating entity distribution visualization for MP: {mp_name}")
        
        # Get all entities for this MP
        entities = self.db_handler.get_mp_entities(mp_name)
        
        if not entities:
            logger.warning(f"No entities found for MP: {mp_name}")
            return ""
        
        # Count entities by category
        category_counts = Counter([entity["category"] for entity in entities])
        
        # Create the visualization
        fig, ax = plt.subplots(figsize=(12, 8))
        
        categories = list(category_counts.keys())
        counts = list(category_counts.values())
        
        # Sort by count
        sorted_indices = sorted(range(len(counts)), key=lambda i: counts[i], reverse=True)
        categories = [categories[i] for i in sorted_indices]
        counts = [counts[i] for i in sorted_indices]
        
        bars = ax.bar(categories, counts, color='skyblue')
        
        # Add count labels on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{int(height)}',
                    ha='center', va='bottom', fontweight='bold')
        
        ax.set_title(f'Entity Distribution by Category for {mp_name}', fontsize=16)
        ax.set_xlabel('Category', fontsize=14)
        ax.set_ylabel('Number of Entities', fontsize=14)
        
        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        # Save the visualization
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{mp_name.replace(' ', '_')}_entity_distribution.png")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Saved entity distribution visualization to: {output_path}")
        
        return output_path
    
    def visualize_entity_changes_over_time(self, mp_name: str, output_dir: str = "outputs/visualizations") -> str:
        """
        Create a visualization of entity changes over time for an MP.
        
        Args:
            mp_name: Name of the MP to visualize.
            output_dir: Directory to save the visualization.
            
        Returns:
            Path to the saved visualization.
        """
        logger.info(f"Creating entity changes over time visualization for MP: {mp_name}")
        
        # Get entity timelines for this MP
        entity_timelines = self.analyzer.analyze_mp_entities(mp_name)
        
        if not entity_timelines:
            logger.warning(f"No entity timelines found for MP: {mp_name}")
            return ""
        
        # Prepare data for visualization
        dates = []
        categories = []
        
        for timeline in entity_timelines:
            for disclosure in timeline["timeline"]:
                date_str = disclosure["declaration_date"]
                try:
                    # Parse date string to datetime
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    dates.append(date)
                    categories.append(disclosure["category"])
                except ValueError:
                    logger.warning(f"Invalid date format: {date_str}")
        
        if not dates:
            logger.warning(f"No valid dates found for MP: {mp_name}")
            return ""
        
        # Create a DataFrame for easier manipulation
        df = pd.DataFrame({
            'date': dates,
            'category': categories
        })
        
        # Group by date and category, count occurrences
        df_grouped = df.groupby(['date', 'category']).size().unstack(fill_value=0)
        
        # Sort by date
        df_grouped = df_grouped.sort_index()
        
        # Create the visualization
        fig, ax = plt.subplots(figsize=(14, 10))
        
        # Plot stacked area chart
        df_grouped.plot(kind='area', stacked=True, alpha=0.7, ax=ax)
        
        ax.set_title(f'Entity Changes Over Time for {mp_name}', fontsize=16)
        ax.set_xlabel('Date', fontsize=14)
        ax.set_ylabel('Number of Entities', fontsize=14)
        
        # Format x-axis as dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        
        # Add legend
        ax.legend(title='Category', bbox_to_anchor=(1.05, 1), loc='upper left')
        
        plt.tight_layout()
        
        # Save the visualization
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{mp_name.replace(' ', '_')}_entity_changes_over_time.png")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Saved entity changes over time visualization to: {output_path}")
        
        return output_path
    
    def visualize_entity_comparison(self, mp_name1: str, mp_name2: str, output_dir: str = "outputs/visualizations") -> str:
        """
        Create a visualization comparing entities between two MPs.
        
        Args:
            mp_name1: Name of the first MP.
            mp_name2: Name of the second MP.
            output_dir: Directory to save the visualization.
            
        Returns:
            Path to the saved visualization.
        """
        logger.info(f"Creating entity comparison visualization for {mp_name1} and {mp_name2}")
        
        # Get comparison data
        comparison = self.analyzer.compare_mp_entities(mp_name1, mp_name2)
        
        if not comparison:
            logger.warning(f"No comparison data found for {mp_name1} and {mp_name2}")
            return ""
        
        # Get entity categories for both MPs
        entities1 = self.db_handler.get_mp_entities(mp_name1)
        entities2 = self.db_handler.get_mp_entities(mp_name2)
        
        category_counts1 = Counter([entity["category"] for entity in entities1])
        category_counts2 = Counter([entity["category"] for entity in entities2])
        
        # Get all unique categories
        all_categories = sorted(set(list(category_counts1.keys()) + list(category_counts2.keys())))
        
        # Create the visualization
        fig, ax = plt.subplots(figsize=(14, 10))
        
        x = range(len(all_categories))
        width = 0.35
        
        # Create bars
        bars1 = ax.bar([i - width/2 for i in x], 
                       [category_counts1.get(cat, 0) for cat in all_categories], 
                       width, label=mp_name1, color='skyblue')
        
        bars2 = ax.bar([i + width/2 for i in x], 
                       [category_counts2.get(cat, 0) for cat in all_categories], 
                       width, label=mp_name2, color='lightcoral')
        
        # Add labels and title
        ax.set_title(f'Entity Comparison: {mp_name1} vs {mp_name2}', fontsize=16)
        ax.set_xlabel('Category', fontsize=14)
        ax.set_ylabel('Number of Entities', fontsize=14)
        ax.set_xticks(x)
        ax.set_xticklabels(all_categories, rotation=45, ha='right')
        
        # Add legend
        ax.legend()
        
        # Add count labels on top of bars
        for bar in bars1:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{int(height)}',
                        ha='center', va='bottom', fontsize=9)
        
        for bar in bars2:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                        f'{int(height)}',
                        ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        
        # Save the visualization
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"comparison_{mp_name1.replace(' ', '_')}_{mp_name2.replace(' ', '_')}.png")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Saved entity comparison visualization to: {output_path}")
        
        return output_path 