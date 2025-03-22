# Data Standardization Workflow

Data standardization is a critical part of the Australian Government Transparency Project. It ensures consistency in MP names, electorates, categories, and other data, enabling reliable analysis and visualization.

## Overview

The data standardization process consists of several steps:

1. **MP Name Standardization**: Normalize MP names to a consistent format
2. **Electorate Standardization**: Standardize electorate names
3. **Category Recategorization**: Recategorize unknown or inconsistent categories
4. **Entity Standardization**: Normalize entity names and merge duplicates

## Key Components

### MP Name Standardization

MP name standardization is handled by the `standardize_mp_names.py` script. This script normalizes MP names by removing middle names, handling honorifics, and fixing inconsistencies.

**Key Files:**
- `standardize_mp_names.py`: Script for standardizing MP names

**Main Functions:**

```python
def standardize_mp_names(db_path: str = "disclosures.db", dry_run: bool = False) -> Dict[str, Any]:
    """
    Standardize MP names in the database.
    
    Args:
        db_path: Path to the SQLite database file
        dry_run: Whether to perform a dry run without making changes
        
    Returns:
        Dictionary with standardization statistics
    """
```

```python
def standardize_name(name: str) -> str:
    """
    Standardize a single MP name.
    
    Args:
        name: MP name to standardize
        
    Returns:
        Standardized MP name
    """
```

### Electorate Standardization

Electorate standardization is handled by the `standardize_electorates.py` script. This script normalizes electorate names by fixing case issues, handling renamed electorates, and ensuring consistency.

**Key Files:**
- `standardize_electorates.py`: Script for standardizing electorate names

**Main Functions:**

```python
def standardize_electorates(db_path: str = "disclosures.db", dry_run: bool = False) -> Dict[str, Any]:
    """
    Standardize electorate names in the database.
    
    Args:
        db_path: Path to the SQLite database file
        dry_run: Whether to perform a dry run without making changes
        
    Returns:
        Dictionary with standardization statistics
    """
```

```python
def standardize_electorate(electorate: str) -> str:
    """
    Standardize a single electorate name.
    
    Args:
        electorate: Electorate name to standardize
        
    Returns:
        Standardized electorate name
    """
```

### Category Recategorization

Category recategorization is handled by two scripts:
- `recategorize_unknowns.py`: Uses regex patterns to recategorize unknown entries
- `recategorize_unknowns_llm.py`: Uses LLM to recategorize remaining unknown entries

**Key Files:**
- `recategorize_unknowns.py`: Script for regex-based recategorization
- `recategorize_unknowns_llm.py`: Script for LLM-based recategorization
- `recategorize_all.py`: Script for running the complete recategorization pipeline

**Main Functions:**

```python
def recategorize(db_path: str = "disclosures.db", verbose: bool = False) -> Dict[str, Any]:
    """
    Recategorize unknown entries using regex patterns.
    
    Args:
        db_path: Path to the SQLite database file
        verbose: Whether to print detailed information
        
    Returns:
        Dictionary with recategorization statistics
    """
```

```python
def recategorize_with_llm(
    db_path: str = "disclosures.db",
    max_entries: int = 100,
    verbose: bool = False,
    retry_count: int = 3
) -> Dict[str, Any]:
    """
    Recategorize unknown entries using LLM.
    
    Args:
        db_path: Path to the SQLite database file
        max_entries: Maximum number of entries to recategorize
        verbose: Whether to print detailed information
        retry_count: Number of retries for failed recategorization
        
    Returns:
        Dictionary with recategorization statistics
    """
```

### Entity Standardization

Entity standardization is handled by the `merge_entities.py` script. This script identifies and merges duplicate entities.

**Key Files:**
- `merge_entities.py`: Script for merging duplicate entities
- `analyze_entities.py`: Script for analyzing entity data
- `visualize_entities.py`: Script for visualizing entity relationships

**Main Functions:**

```python
def merge_entities(
    db_path: str = "disclosures.db",
    similarity_threshold: float = 0.8,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Identify and merge duplicate entities.
    
    Args:
        db_path: Path to the SQLite database file
        similarity_threshold: Threshold for considering entities similar
        dry_run: Whether to perform a dry run without making changes
        
    Returns:
        Dictionary with merge statistics
    """
```

```python
def calculate_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two entity names.
    
    Args:
        name1: First entity name
        name2: Second entity name
        
    Returns:
        Similarity score (0-1)
    """
```

## Complete Standardization Pipeline

The complete standardization pipeline is handled by the `standardize_data.py` script. This script coordinates all standardization steps.

**Key Files:**
- `standardize_data.py`: Main script for the complete standardization pipeline

**Main Functions:**

```python
def standardize_data(
    db_path: str = "disclosures.db",
    skip_mp_names: bool = False,
    skip_electorates: bool = False,
    skip_categories: bool = False,
    skip_entities: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Run the complete standardization pipeline.
    
    Args:
        db_path: Path to the SQLite database file
        skip_mp_names: Whether to skip MP name standardization
        skip_electorates: Whether to skip electorate standardization
        skip_categories: Whether to skip category recategorization
        skip_entities: Whether to skip entity standardization
        dry_run: Whether to perform a dry run without making changes
        
    Returns:
        Dictionary with standardization statistics
    """
```

## Standardization Rules

### MP Name Standardization Rules

1. **Honorifics**: Remove honorifics (Hon., Dr., etc.)
2. **Middle Names**: Remove middle names and initials
3. **Capitalization**: Ensure consistent capitalization
4. **Special Cases**: Handle special cases like hyphenated names

### Electorate Standardization Rules

1. **Capitalization**: Ensure proper capitalization (Title Case)
2. **Renamed Electorates**: Update renamed electorates
3. **Abbreviations**: Expand abbreviations (e.g., "Mt" to "Mount")
4. **Special Characters**: Handle special characters and spaces consistently

### Category Recategorization Rules

1. **Pattern Matching**: Use regex patterns to identify categories
2. **Keyword Mapping**: Map keywords to standard categories
3. **LLM Analysis**: Use LLM to analyze context for difficult cases
4. **Confidence Scoring**: Assign confidence scores to recategorizations

### Entity Standardization Rules

1. **Name Normalization**: Normalize entity names (case, punctuation, etc.)
2. **Abbreviation Handling**: Handle abbreviations (Ltd, Pty, etc.)
3. **Duplicate Detection**: Identify similar entities using string similarity
4. **Entity Merging**: Merge duplicate entities while preserving history

## Usage Examples

### Running the Complete Standardization Pipeline

```python
from standardize_data import standardize_data

stats = standardize_data(db_path="disclosures.db")
print(f"Standardized {stats['mp_names_updated']} MP names")
print(f"Standardized {stats['electorates_updated']} electorates")
print(f"Recategorized {stats['categories_updated']} entries")
print(f"Merged {stats['entities_merged']} entities")
```

### Standardizing MP Names

```python
from standardize_mp_names import standardize_mp_names

stats = standardize_mp_names(db_path="disclosures.db")
print(f"Standardized {stats['total_updated']} MP names")
print(f"Mapped {len(stats['name_mapping'])} unique names")
```

### Recategorizing Unknown Entries

```python
from recategorize_all import recategorize_all

stats = recategorize_all(db_path="disclosures.db")
print(f"Recategorized {stats['total_recategorized']} entries")
print(f"Remaining unknown: {stats['remaining_unknown']}")
```

## Command-Line Usage

The standardization scripts can also be run from the command line:

```bash
# Run the complete standardization pipeline
python standardize_data.py --db-path=disclosures.db

# Standardize MP names
python standardize_mp_names.py --db-path=disclosures.db

# Standardize electorates
python standardize_electorates.py --db-path=disclosures.db

# Run regex-based recategorization
python recategorize_unknowns.py --db-path=disclosures.db

# Run LLM-based recategorization
python recategorize_unknowns_llm.py --db-path=disclosures.db --max-entries=100

# Run the complete recategorization pipeline
python recategorize_all.py --db-path=disclosures.db
```

## Performance Considerations

- **Batch Processing**: Process entries in batches for efficiency
- **LLM Rate Limiting**: Respect LLM API rate limits for recategorization
- **Database Transactions**: Use transactions for bulk updates
- **Logging and Monitoring**: Log standardization changes for review

## Next Steps

- [API Endpoints Reference](../api/endpoints.md)
- [Utility Scripts Documentation](./scripts.md) 