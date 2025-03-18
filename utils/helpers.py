"""
Helper utilities for the transparency package.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def normalize_entity_name(entity_name: str) -> str:
    """
    Normalize an entity name by removing extra whitespace, converting to lowercase,
    and removing common prefixes/suffixes.
    
    Args:
        entity_name: The entity name to normalize.
        
    Returns:
        The normalized entity name.
    """
    if not entity_name:
        return ""
    
    # Convert to lowercase
    normalized = entity_name.lower()
    
    # Remove extra whitespace
    normalized = " ".join(normalized.split())
    
    # Remove common prefixes
    prefixes = ["the ", "mr ", "mrs ", "ms ", "dr "]
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    
    # Remove common suffixes
    suffixes = [" ltd", " limited", " inc", " incorporated", " pty", " proprietary"]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
    
    # Remove punctuation
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    # Remove extra whitespace again
    normalized = " ".join(normalized.split())
    
    return normalized

def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string into a datetime object.
    
    Args:
        date_str: The date string to parse.
        
    Returns:
        A datetime object, or None if parsing fails.
    """
    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %B %Y",
        "%B %d, %Y"
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    logger.warning(f"Could not parse date: {date_str}")
    return None

def format_date(date_obj: Union[datetime, str]) -> str:
    """
    Format a datetime object or date string as YYYY-MM-DD.
    
    Args:
        date_obj: The datetime object or date string to format.
        
    Returns:
        A formatted date string.
    """
    if isinstance(date_obj, str):
        date_obj = parse_date(date_obj)
        if not date_obj:
            return ""
    
    return date_obj.strftime("%Y-%m-%d")

def save_json(data: Any, output_path: str) -> bool:
    """
    Save data to a JSON file.
    
    Args:
        data: The data to save.
        output_path: The path to save the data to.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved data to: {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving data to {output_path}: {str(e)}")
        return False

def load_json(input_path: str) -> Optional[Any]:
    """
    Load data from a JSON file.
    
    Args:
        input_path: The path to load the data from.
        
    Returns:
        The loaded data, or None if loading fails.
    """
    try:
        with open(input_path, "r") as f:
            data = json.load(f)
        
        logger.info(f"Loaded data from: {input_path}")
        return data
    
    except Exception as e:
        logger.error(f"Error loading data from {input_path}: {str(e)}")
        return None

def calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate the similarity between two strings using Levenshtein distance.
    
    Args:
        str1: The first string.
        str2: The second string.
        
    Returns:
        A similarity score between 0 and 1.
    """
    # Normalize strings
    str1 = normalize_entity_name(str1)
    str2 = normalize_entity_name(str2)
    
    if not str1 or not str2:
        return 0.0
    
    # Simple case: exact match
    if str1 == str2:
        return 1.0
    
    # Calculate Levenshtein distance
    try:
        import Levenshtein
        distance = Levenshtein.distance(str1, str2)
        max_len = max(len(str1), len(str2))
        
        if max_len == 0:
            return 0.0
        
        return 1.0 - (distance / max_len)
    
    except ImportError:
        # Fallback to a simpler similarity measure
        # Count common words
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        common_words = words1.intersection(words2)
        all_words = words1.union(words2)
        
        if not all_words:
            return 0.0
        
        return len(common_words) / len(all_words) 