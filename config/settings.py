"""
Configuration settings for the transparency package.
"""

import os
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database settings
DATABASE_PATH = os.environ.get("TRANSPARENCY_DB_PATH", "disclosures.db")

# PDF settings
PDF_DIR = os.environ.get("TRANSPARENCY_PDF_DIR", "pdfs")

# Output settings
OUTPUT_DIR = os.environ.get("TRANSPARENCY_OUTPUT_DIR", "outputs")
ANALYSIS_DIR = os.path.join(OUTPUT_DIR, "analysis")
VISUALIZATION_DIR = os.path.join(OUTPUT_DIR, "visualizations")

# Entity settings
ENTITY_SIMILARITY_THRESHOLD = float(os.environ.get("TRANSPARENCY_ENTITY_SIMILARITY_THRESHOLD", "0.8"))

# API settings
API_KEY = os.environ.get("TRANSPARENCY_API_KEY", "")
API_ENDPOINT = os.environ.get("TRANSPARENCY_API_ENDPOINT", "")

# Create directories if they don't exist
def create_directories():
    """Create necessary directories if they don't exist."""
    directories = [
        PDF_DIR,
        OUTPUT_DIR,
        ANALYSIS_DIR,
        VISUALIZATION_DIR
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Created directory: {directory}")

# Load settings from a JSON file
def load_settings(settings_file: str = "settings.json") -> Dict[str, Any]:
    """
    Load settings from a JSON file.
    
    Args:
        settings_file: Path to the settings file.
        
    Returns:
        A dictionary of settings.
    """
    import json
    
    if not os.path.exists(settings_file):
        logger.warning(f"Settings file not found: {settings_file}")
        return {}
    
    try:
        with open(settings_file, "r") as f:
            settings = json.load(f)
        
        logger.info(f"Loaded settings from: {settings_file}")
        return settings
    
    except Exception as e:
        logger.error(f"Error loading settings from {settings_file}: {str(e)}")
        return {}

# Save settings to a JSON file
def save_settings(settings: Dict[str, Any], settings_file: str = "settings.json") -> bool:
    """
    Save settings to a JSON file.
    
    Args:
        settings: A dictionary of settings.
        settings_file: Path to the settings file.
        
    Returns:
        True if successful, False otherwise.
    """
    import json
    
    try:
        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)
        
        logger.info(f"Saved settings to: {settings_file}")
        return True
    
    except Exception as e:
        logger.error(f"Error saving settings to {settings_file}: {str(e)}")
        return False

# Get all settings as a dictionary
def get_all_settings() -> Dict[str, Any]:
    """
    Get all settings as a dictionary.
    
    Returns:
        A dictionary of all settings.
    """
    return {
        "database": {
            "path": DATABASE_PATH
        },
        "pdf": {
            "dir": PDF_DIR
        },
        "output": {
            "dir": OUTPUT_DIR,
            "analysis_dir": ANALYSIS_DIR,
            "visualization_dir": VISUALIZATION_DIR
        },
        "entity": {
            "similarity_threshold": ENTITY_SIMILARITY_THRESHOLD
        },
        "api": {
            "key": API_KEY,
            "endpoint": API_ENDPOINT
        }
    } 