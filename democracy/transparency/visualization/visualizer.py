#!/usr/bin/env python3
"""
Visualize entity timelines.

This script generates visualizations of entity timelines for a specific MP.
"""

import os
import argparse
import logging
import json
import sqlite3
from typing import Dict, Any, List
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import pandas as pd
from db_handler import DatabaseHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_date(date_str: str) -> datetime:
    """
    Parse a date string into a datetime object.
    
    Args:
        date_str: Date string in YYYY-MM-DD format.
        
    Returns:
        A datetime object.
    """
    if not date_str or date_str == "Unknown":
        return None
    
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        logger.warning(f"Could not parse date: {date_str}")
        return None

def visualize_entity_timeline(entity_timeline: Dict[str, Any], output_dir: str = None):
    """
    Visualize an entity's timeline.
    
    Args:
        entity_timeline: The entity timeline to visualize.
        output_dir: Directory to save the visualization.
    """
    entity = entity_timeline["entity"]
    timeline = entity_timeline["timeline"]
    
    if not timeline:
        logger.warning(f"No timeline data for entity: {entity.get('canonical_name', 'Unknown')}")
        return
    
    # Sort timeline by declaration date
    timeline = sorted(timeline, key=lambda x: x["declaration_date"])
    
    # Extract dates and details
    dates = [parse_date(item["declaration_date"]) for item in timeline]
    details = [item["details"] for item in timeline]
    
    # Filter out None dates
    valid_data = [(date, detail) for date, detail in zip(dates, details) if date]
    
    if not valid_data:
        logger.warning(f"No valid date data for entity: {entity.get('canonical_name', 'Unknown')}")
        return
    
    dates, details = zip(*valid_data)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot timeline
    ax.plot(dates, [1] * len(dates), 'o-', markersize=10)
    
    # Add details as annotations
    for i, (date, detail) in enumerate(zip(dates, details)):
        ax.annotate(
            detail,
            (mdates.date2num(date), 1),
            xytext=(0, 10 + (i % 3) * 20),  # Stagger annotations to avoid overlap
            textcoords="offset points",
            ha="center",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8),
            rotation=0
        )
    
    # Set title and labels
    ax.set_title(f"Timeline for {entity.get('canonical_name', 'Unknown')} ({entity.get('entity_type', 'Unknown')})")
    ax.set_yticks([])  # Hide y-axis
    
    # Format x-axis as dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    fig.autofmt_xdate()
    
    # Add grid
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Save figure if output directory provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        entity_id = entity.get("id", "unknown")
        entity_name = entity.get("canonical_name", "unknown").replace(" ", "_")
        output_path = os.path.join(output_dir, f"timeline_{entity_name}_{entity_id}.png")
        
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        logger.info(f"Saved entity timeline visualization to: {output_path}")
    
    plt.close(fig)

def visualize_mp_entities_by_type(mp_name: str, db_path: str, output_dir: str = None):
    """
    Visualize the distribution of entities by type for a specific MP.
    
    Args:
        mp_name: Name of the MP to analyze.
        db_path: Path to the SQLite database file.
        output_dir: Directory to save the visualization.
    """
    logger.info(f"Visualizing entity distribution for MP: {mp_name}")
    
    # Initialize database handler
    db_handler = DatabaseHandler(db_path=db_path)
    
    # Get entity summary
    summary = db_handler.get_mp_entity_summary(mp_name)
    
    if summary.get("error"):
        logger.warning(f"Error getting entity summary: {summary['error']}")
        return
    
    # Extract entity counts by type
    entity_counts = summary["entity_counts_by_type"]
    
    if not entity_counts:
        logger.warning(f"No entity data for MP: {mp_name}")
        return
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot bar chart
    types = list(entity_counts.keys())
    counts = list(entity_counts.values())
    
    bars = ax.bar(types, counts)
    
    # Add count labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{height}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom"
        )
    
    # Set title and labels
    ax.set_title(f"Entity Distribution by Type for {mp_name}")
    ax.set_xlabel("Entity Type")
    ax.set_ylabel("Count")
    
    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha="right")
    
    # Adjust layout
    plt.tight_layout()
    
    # Save figure if output directory provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{mp_name.replace(' ', '_')}_entity_distribution.png")
        
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        logger.info(f"Saved entity distribution visualization to: {output_path}")
    
    plt.close(fig)

def visualize_entity_changes_over_time(mp_name: str, db_path: str, output_dir: str = None):
    """
    Visualize how an MP's entities change over time.
    
    Args:
        mp_name: Name of the MP to analyze.
        db_path: Path to the SQLite database file.
        output_dir: Directory to save the visualization.
    """
    logger.info(f"Visualizing entity changes over time for MP: {mp_name}")
    
    # Initialize database handler
    db_handler = DatabaseHandler(db_path=db_path)
    
    # Get all entities for this MP
    entities = db_handler.get_mp_entities(mp_name)
    
    if not entities:
        logger.warning(f"No entities found for MP: {mp_name}")
        return
    
    # Collect all declaration dates
    all_dates = []
    for entity in entities:
        entity_id = entity["id"]
        entity_timeline = db_handler.get_entity_timeline(entity_id)
        
        for disclosure in entity_timeline["timeline"]:
            date_str = disclosure["declaration_date"]
            if date_str and date_str != "Unknown":
                date = parse_date(date_str)
                if date:
                    all_dates.append((date, entity["entity_type"]))
    
    if not all_dates:
        logger.warning(f"No valid dates found for MP: {mp_name}")
        return
    
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(all_dates, columns=["date", "entity_type"])
    
    # Group by date and entity type, and count
    df_grouped = df.groupby([pd.Grouper(key="date", freq="M"), "entity_type"]).size().unstack(fill_value=0)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot stacked area chart
    df_grouped.plot.area(ax=ax, stacked=True, alpha=0.7)
    
    # Set title and labels
    ax.set_title(f"Entity Changes Over Time for {mp_name}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Number of Disclosures")
    
    # Format x-axis as dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    fig.autofmt_xdate()
    
    # Add legend
    ax.legend(title="Entity Type", bbox_to_anchor=(1.05, 1), loc="upper left")
    
    # Add grid
    ax.grid(True, linestyle='--', alpha=0.3)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save figure if output directory provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{mp_name.replace(' ', '_')}_entity_changes_over_time.png")
        
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        logger.info(f"Saved entity changes visualization to: {output_path}")
    
    plt.close(fig)

def main():
    """
    Main function to visualize entity timelines.
    """
    parser = argparse.ArgumentParser(description="Visualize entity timelines")
    parser.add_argument("--mp", help="Name of the MP to visualize")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to SQLite database file")
    parser.add_argument("--output-dir", default="outputs/visualizations", help="Directory to save visualizations")
    parser.add_argument("--entity-id", help="ID of a specific entity to visualize")
    parser.add_argument("--all-visualizations", action="store_true", help="Generate all visualizations for the MP")
    
    args = parser.parse_args()
    
    # Initialize database handler
    db_handler = DatabaseHandler(db_path=args.db_path)
    
    # Visualize specific entity
    if args.entity_id:
        entity_timeline = db_handler.get_entity_timeline(args.entity_id)
        visualize_entity_timeline(entity_timeline, args.output_dir)
    
    # Visualize MP entities
    elif args.mp:
        if args.all_visualizations:
            # Generate all visualizations
            visualize_mp_entities_by_type(args.mp, args.db_path, args.output_dir)
            visualize_entity_changes_over_time(args.mp, args.db_path, args.output_dir)
            
            # Visualize each entity's timeline
            entities = db_handler.get_mp_entities(args.mp)
            for entity in entities:
                entity_id = entity["id"]
                entity_timeline = db_handler.get_entity_timeline(entity_id)
                visualize_entity_timeline(entity_timeline, args.output_dir)
        else:
            # Just generate entity distribution visualization
            visualize_mp_entities_by_type(args.mp, args.db_path, args.output_dir)
    
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