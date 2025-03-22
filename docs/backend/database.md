# Database Schema and Operations

The Australian Government Transparency Project uses SQLite as its database engine. The database is managed through the `DatabaseHandler` class in `db_handler.py`.

## Database Schema

The database consists of several tables that store different aspects of the disclosure data:

### Disclosures Table

The main table that stores all disclosure entries extracted from PDFs.

```sql
CREATE TABLE IF NOT EXISTS disclosures (
    id TEXT PRIMARY KEY,
    mp_name TEXT NOT NULL,
    party TEXT,
    electorate TEXT,
    category TEXT,
    sub_category TEXT,
    item TEXT,
    entity TEXT,
    entity_id TEXT,
    declaration_date TEXT,
    details TEXT,
    temporal_type TEXT,
    start_date TEXT,
    end_date TEXT,
    pdf_url TEXT,
    pdf_page INTEGER,
    confidence REAL,
    last_updated TEXT
)
```

### Entities Table

Stores unique entities mentioned in disclosures.

```sql
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT,
    category TEXT,
    abn TEXT,
    description TEXT,
    first_appearance TEXT,
    last_appearance TEXT,
    appearances_count INTEGER DEFAULT 0
)
```

### Entity Appearances Table

Tracks when entities appear in disclosures.

```sql
CREATE TABLE IF NOT EXISTS entity_appearances (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    disclosure_id TEXT NOT NULL,
    appearance_date TEXT,
    FOREIGN KEY (entity_id) REFERENCES entities (id),
    FOREIGN KEY (disclosure_id) REFERENCES disclosures (id)
)
```

### MP Disclosure Stats Table

Stores statistics about MP disclosures.

```sql
CREATE TABLE IF NOT EXISTS mp_disclosure_stats (
    mp_name TEXT PRIMARY KEY,
    total_disclosures INTEGER,
    assets_count INTEGER,
    liabilities_count INTEGER,
    income_count INTEGER,
    gifts_count INTEGER,
    travel_count INTEGER,
    memberships_count INTEGER,
    unknown_count INTEGER,
    last_updated TEXT
)
```

## Database Indexes

Several indexes are created to optimize query performance:

```sql
CREATE INDEX IF NOT EXISTS idx_disclosures_mp_name ON disclosures (mp_name);
CREATE INDEX IF NOT EXISTS idx_disclosures_entity ON disclosures (entity);
CREATE INDEX IF NOT EXISTS idx_disclosures_category ON disclosures (category);
CREATE INDEX IF NOT EXISTS idx_disclosures_declaration_date ON disclosures (declaration_date);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities (name);
```

## The DatabaseHandler Class

The `DatabaseHandler` class in `db_handler.py` provides a comprehensive interface for interacting with the database. Here are the key methods:

### Initialization

```python
def __init__(self, db_path: str = "disclosures.db"):
    """
    Initialize the database handler.
    
    Args:
        db_path: Path to the SQLite database file.
    """
    self.db_path = db_path
    self.create_tables()
```

### Table Creation

```python
def create_tables(self):
    """Create database tables if they don't exist."""
    # Creates the tables defined in the schema
```

### Disclosure Operations

```python
def insert_disclosure(self, disclosure_data: Dict[str, Any]) -> str:
    """
    Insert a new disclosure into the database.
    
    Args:
        disclosure_data: Dictionary containing disclosure data.
        
    Returns:
        ID of the inserted disclosure.
    """
    # Inserts disclosure and returns its ID
```

```python
def update_disclosure(self, disclosure_id: str, update_data: Dict[str, Any]) -> bool:
    """
    Update an existing disclosure.
    
    Args:
        disclosure_id: ID of the disclosure to update.
        update_data: Dictionary containing fields to update.
        
    Returns:
        True if successful, False otherwise.
    """
    # Updates disclosure and returns success status
```

```python
def get_disclosures(self, **filters) -> List[Dict[str, Any]]:
    """
    Get disclosures with optional filtering.
    
    Args:
        **filters: Keyword arguments for filtering (mp_name, category, etc.)
        
    Returns:
        List of disclosure dictionaries.
    """
    # Retrieves disclosures based on filters
```

### Entity Operations

```python
def process_entity(self, entity_name: str, disclosure_id: str, appearance_date: str = None) -> str:
    """
    Process an entity mentioned in a disclosure.
    
    Args:
        entity_name: Name of the entity.
        disclosure_id: ID of the disclosure where the entity appears.
        appearance_date: Date when the entity appears.
        
    Returns:
        Entity ID.
    """
    # Processes entity and returns its ID
```

```python
def get_entities(self, **filters) -> List[Dict[str, Any]]:
    """
    Get entities with optional filtering.
    
    Args:
        **filters: Keyword arguments for filtering (name, entity_type, etc.)
        
    Returns:
        List of entity dictionaries.
    """
    # Retrieves entities based on filters
```

### Statistics Operations

```python
def update_mp_stats(self, mp_name: str) -> Dict[str, Any]:
    """
    Update statistics for an MP.
    
    Args:
        mp_name: Name of the MP to update statistics for.
        
    Returns:
        Dictionary of updated statistics.
    """
    # Updates statistics for an MP
```

```python
def get_mp_stats(self, mp_name: str = None) -> List[Dict[str, Any]]:
    """
    Get statistics for MPs.
    
    Args:
        mp_name: Optional name of a specific MP.
        
    Returns:
        List of MP statistics dictionaries.
    """
    # Retrieves MP statistics
```

### Utility Methods

```python
def filter_nil_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out entries with 'nil', 'n/a', etc.
    
    Args:
        entries: List of disclosure dictionaries.
        
    Returns:
        Filtered list of disclosures.
    """
    # Filters out 'nil' entries
```

```python
def create_backup(self, backup_path: str) -> bool:
    """
    Create a backup of the database.
    
    Args:
        backup_path: Path where to save the backup.
        
    Returns:
        True if successful, False otherwise.
    """
    # Creates a database backup
```

## Usage Examples

### Inserting a Disclosure

```python
from db_handler import DatabaseHandler

db = DatabaseHandler("disclosures.db")

disclosure_data = {
    "mp_name": "Jane Smith",
    "party": "Labor",
    "electorate": "Sydney",
    "category": "Asset",
    "sub_category": "Real Estate",
    "item": "Residential property",
    "entity": "N/A",
    "declaration_date": "2023-05-15",
    "details": "Family home in Sydney"
}

disclosure_id = db.insert_disclosure(disclosure_data)
print(f"Inserted disclosure with ID: {disclosure_id}")
```

### Querying Disclosures

```python
from db_handler import DatabaseHandler

db = DatabaseHandler("disclosures.db")

# Get all disclosures for a specific MP
mp_disclosures = db.get_disclosures(mp_name="Jane Smith")

# Get all Gift category disclosures
gift_disclosures = db.get_disclosures(category="Gift")

# Get disclosures with filtering
filtered_disclosures = db.get_disclosures(
    mp_name="Jane Smith",
    category="Asset",
    limit=10,
    offset=0
)
```

### Updating Statistics

```python
from db_handler import DatabaseHandler

db = DatabaseHandler("disclosures.db")

# Update statistics for a specific MP
stats = db.update_mp_stats("Jane Smith")
print(f"MP has {stats['total_disclosures']} total disclosures")

# Get statistics for all MPs
all_stats = db.get_mp_stats()
```

## Performance Considerations

- Use parameterized queries to prevent SQL injection
- Create appropriate indexes for frequently queried columns
- Implement batch operations for bulk inserts/updates
- Use transactions for operations that modify multiple tables

## Database Maintenance

### Creating a Backup

```python
from db_handler import DatabaseHandler

db = DatabaseHandler("disclosures.db")
db.create_backup("disclosures_backup.db")
```

### Resetting the Database

```python
from reset_db import reset_database

reset_database("disclosures.db")
```

## Next Steps

- [PDF Processing Pipeline](./pdf_processing.md)
- [Data Standardization Workflow](./data_standardization.md) 