"""Entity Standardization Script for Disclosure Database

This script standardizes entity names through multiple stages, with each stage building upon the previous one.
The data flows through the following columns in sequence:

1. entity (Original): Raw entity names extracted from PDF documents by Gemini
2. split_entity: Entity names after splitting compound entities (e.g., "A and B" -> ["A", "B"])
3. regex_standardized: Entity names after regex-based standardization (Stage 1)
4. fuzzy_match: Final entity names after fuzzy matching (Stage 2)

Data Flow and Dependencies:
- split_entity depends on entity (run apply_double_disclosure_entity_results.py first)
- regex_standardized depends on split_entity
- fuzzy_match depends on regex_standardized

Each stage preserves the original data while adding new standardized versions in their respective columns.
Protected entities and special cases are preserved throughout all stages.
"""

import sqlite3
import re
from typing import List, Dict, Set, Tuple
import argparse
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import time
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

class StandardizationRule(Enum):
    KEEP_ORIGINAL = "keep_original"
    REMOVE_SUFFIX = "remove_suffix"
    STANDARDIZE_SUFFIX = "standardize_suffix"
    TITLE_CASE = "title_case"
    MOST_COMMON = "most_common"

class EntityCaseRule(Enum):
    PRESERVE_UPPERCASE = "preserve_uppercase"  # e.g., "ETF" stays "ETF"
    USE_SPECIFIED_CASE = "use_specified_case"  # e.g., "ebay" becomes "eBay"
    EXPAND_TO_FULL = "expand_to_full"         # e.g., "ETF" -> "Exchange Traded Fund"
    TITLE_CASE = "title_case"                 # e.g., "commonwealth bank" -> "Commonwealth Bank"

# Dictionary of special cases and their case rules
SPECIAL_CASES = {
    # Companies with special capitalization
    'eBay': ('eBay', EntityCaseRule.USE_SPECIFIED_CASE),
    'BankSA': ('BankSA', EntityCaseRule.USE_SPECIFIED_CASE),
    'BankVic': ('BankVic', EntityCaseRule.USE_SPECIFIED_CASE),
    'ING Direct': ('ING Direct', EntityCaseRule.USE_SPECIFIED_CASE),
    'ING Bank': ('ING Bank', EntityCaseRule.USE_SPECIFIED_CASE),
    'ME Bank': ('ME Bank', EntityCaseRule.USE_SPECIFIED_CASE),
    'UBank': ('UBank', EntityCaseRule.USE_SPECIFIED_CASE),
    'QBank': ('QBank', EntityCaseRule.USE_SPECIFIED_CASE),
    'NatWest': ('NatWest', EntityCaseRule.USE_SPECIFIED_CASE),
    'MyState': ('MyState', EntityCaseRule.USE_SPECIFIED_CASE),
    'MyState Financial': ('MyState Financial', EntityCaseRule.USE_SPECIFIED_CASE),
    'SkinB5': ('SkinB5', EntityCaseRule.USE_SPECIFIED_CASE),
    'TehanTrade': ('TehanTrade', EntityCaseRule.USE_SPECIFIED_CASE),
    'Child PsychCorp': ('Child PsychCorp', EntityCaseRule.USE_SPECIFIED_CASE),
    'RQ Supplements': ('RQ Supplements', EntityCaseRule.USE_SPECIFIED_CASE),
    'RBW Enterprises': ('RBW Enterprises', EntityCaseRule.USE_SPECIFIED_CASE),
    'Imagio': ('Imagio', EntityCaseRule.USE_SPECIFIED_CASE),
    'Ezra Properties': ('Ezra Properties', EntityCaseRule.USE_SPECIFIED_CASE),
    'Aznur': ('Aznur', EntityCaseRule.USE_SPECIFIED_CASE),
    'Astra Enterprises': ('Astra Enterprises', EntityCaseRule.USE_SPECIFIED_CASE),
    'BGC Residential': ('BGC Residential', EntityCaseRule.USE_SPECIFIED_CASE),
    'DP & KS': ('DP & KS', EntityCaseRule.USE_SPECIFIED_CASE),
    'RE & TM': ('RE & TM', EntityCaseRule.USE_SPECIFIED_CASE),
    'WGN': ('WGN', EntityCaseRule.USE_SPECIFIED_CASE),
    'NSW': ('NSW', EntityCaseRule.USE_SPECIFIED_CASE),
    'WA': ('WA', EntityCaseRule.USE_SPECIFIED_CASE),
    'SA': ('SA', EntityCaseRule.USE_SPECIFIED_CASE),
    'ACT': ('ACT', EntityCaseRule.USE_SPECIFIED_CASE),
    'QLD': ('QLD', EntityCaseRule.USE_SPECIFIED_CASE),
    
    # State abbreviations to expand
    'New South Wales': ('New South Wales', EntityCaseRule.EXPAND_TO_FULL),
    'Victoria': ('Victoria', EntityCaseRule.EXPAND_TO_FULL),
    'Queensland': ('Queensland', EntityCaseRule.EXPAND_TO_FULL),
    'Western Australia': ('Western Australia', EntityCaseRule.EXPAND_TO_FULL),
    'South Australia': ('South Australia', EntityCaseRule.EXPAND_TO_FULL),
    'Tasmania': ('Tasmania', EntityCaseRule.EXPAND_TO_FULL),
    'Northern Territory': ('Northern Territory', EntityCaseRule.EXPAND_TO_FULL),
    'Australian Capital Territory': ('Australian Capital Territory', EntityCaseRule.EXPAND_TO_FULL),
}

# Dictionary of acronyms that should be preserved in uppercase
ACRONYMS = {
    'AFL', 'NFL', 'MCC', 'NRL', 'SANFL', 'RSL', 'SLSC', 'ABC', 'AAMI', 'ETF',
    'APESMA', 'AIJAC', 'AICE', 'RRRC', 'FOGS', 'GDF', 'BGC', 'GPT', 'APA',
    'VISA', 'VOCUS', 'VICSUPER', 'MEDIASUPER', 'REST', 'AWB', 'DDH', 'RBW',
    'RQ', 'RE', 'TM', 'KJ', 'AJ', 'KS', 'DP', 'NB', 'ME', 'UB', 'QB', 'ING',
    'AMEX', 'UNICEF', 'ETF', 'SMSF', 'ALP', 'LNP', 'UNSW', 'UQ', 'USYD', 'ANU',
    'CSIRO', 'MUP', 'AICE', 'RRRC', 'FOGS', 'GDF', 'BGC', 'GPT', 'APA', 'VISA',
    'VOCUS', 'VICSUPER', 'MEDIASUPER', 'REST', 'AWB', 'DDH', 'RBW', 'RQ', 'RE',
    'TM', 'KJ', 'AJ', 'KS', 'DP', 'NB'
}

@dataclass
class Config:
    fuzzy_threshold: float
    company_suffix_rule: StandardizationRule
    case_rule: StandardizationRule
    standard_suffix: str
    use_fuzzy_matching: bool

def clean_entity_name(name: str) -> str:
    """Clean entity name by removing common variations."""
    if not name:
        return ""
        
    # Make a protected list of common entity names that should never be modified
    protected_names = [
        "Victoria Racing Club", "Victoria", "Prudential", "Lorne Surf Lifesaving Club",
        "Italian Government", "Parramatta Economic Development Forum", "Canterbury", 
        "Swan Valley Regional Council", "Ipswich Motorway Construction Company", "Origin Alliance",
        "South Australia", "Western Australia", "Northern Territory", "New South Wales",
        "Queensland", "Tasmania", "Australian Capital Territory", "Nauru", 
        "President of the Republic of Nauru", "Republic of Nauru"
    ]
    
    # State names that should be treated as special cases
    state_names = [
        "victoria", "queensland", "tasmania", "northern territory", 
        "south australia", "western australia", "new south wales",
        "australian capital territory"
    ]
    
    # Check if it's a protected name first (case-insensitive)
    for protected in protected_names:
        if name.lower() == protected.lower():
            return protected.lower()
            
    # Also if it's an exact match to a state name, return it unchanged
    if name.lower() in state_names:
        return name.lower()
    
    # 1. Remove common company suffixes
    name = re.sub(r'\s*(pty\.?\s*ltd|limited|ltd\.?|inc\.?|incorporated|plc|llc)$', '', name, flags=re.IGNORECASE)
    
    # 2. Handle apostrophes/possessives consistently
    name = re.sub(r'\'s\b', 's', name)  # Convert "Company's" to "Companys" 
    
    # 3. Replace ampersands with "and"
    name = re.sub(r'\s*&\s*', ' and ', name)
    
    # 4. Keep common abbreviations intact - with word boundaries
    for abbr in ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'NT', 'ACT']:
        name = re.sub(rf'\b{abbr}\b', abbr, name, flags=re.IGNORECASE)
    
    # 5. Remove only problematic punctuation, not all of it
    name = re.sub(r'[.,:;]', ' ', name)
    name = ' '.join(name.split())  # Normalize spacing
    
    # Final check for state name matches
    result = name.lower()
    for state in state_names:
        if result == state:
            return name.lower()  # Return original case if it matches a state name
            
    return result

def get_db_connection(db_path, max_retries=3, timeout=60):
    """Get a database connection with retry mechanism."""
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(db_path, timeout=timeout)
            return conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(1)  # Wait 1 second before retrying
                continue
            raise
    raise sqlite3.OperationalError("Failed to connect to database after multiple attempts")

def get_entity_counts(db_path):
    """Get counts of each entity from the database."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT regex_standardized, COUNT(*) as count 
            FROM disclosures 
            WHERE regex_standardized IS NOT NULL 
            GROUP BY regex_standardized 
            ORDER BY count DESC
        """)
        return dict(cursor.fetchall())
    finally:
        conn.close()

def standardize_name(name: str, config: Config) -> str:
    """Standardize an entity name according to the configuration rules."""
    if not name:
        return name
        
    # Skip if entity contains 'and' or '&' as it's likely already been split
    if ' and ' in name.lower() or ' & ' in name.lower():
        return name  # Keep the original
        
    # Protected entity names that should never be modified
    protected_entities = [
        "Victoria Racing Club", "Victoria", "Prudential", "Lorne Surf Lifesaving Club",
        "Italian Government", "Parramatta Economic Development Forum", "Canterbury", 
        "Swan Valley Regional Council", "Ipswich Motorway Construction Company", "Origin Alliance",
        "South Australia", "Western Australia", "Northern Territory", "New South Wales",
        "Queensland", "Tasmania", "Australian Capital Territory", "Nauru", 
        "President of the Republic of Nauru", "Republic of Nauru", "Melbourne Cricket Club"
    ]
    
    # Check if it's a protected entity (case-insensitive comparison)
    if any(name.lower() == protected.lower() for protected in protected_entities):
        return name
        
    # Handle company suffixes based on config
    if config.company_suffix_rule == StandardizationRule.REMOVE_SUFFIX:
        for suffix in ['pty', 'limited', 'ltd', 'inc', 'incorporated', 'plc', 'llc']:
            if name.lower().endswith(suffix.lower()):
                name = name[:-len(suffix)].strip()
    elif config.company_suffix_rule == StandardizationRule.STANDARDIZE_SUFFIX:
        for suffix in ['pty', 'limited', 'ltd', 'inc', 'incorporated', 'plc', 'llc']:
            if name.lower().endswith(suffix.lower()):
                name = name[:-len(suffix)].strip() + " Pty Ltd"
                
    # Handle case based on config
    if config.case_rule == StandardizationRule.TITLE_CASE:
        name = name.title()
    elif config.case_rule == StandardizationRule.MOST_COMMON:
        # This will be handled by the group processing
        pass
    
    return name.strip()

def ensure_regex_standardized_column(db_path: str) -> None:
    """Ensure the regex_standardized column exists."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(disclosures)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'regex_standardized' not in columns:
        cursor.execute("""
            ALTER TABLE disclosures 
            ADD COLUMN regex_standardized TEXT
        """)
        conn.commit()
    
    conn.close()

def ensure_split_entity_column(db_path: str) -> None:
    """Ensure the split_entity column exists."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(disclosures)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'split_entity' not in columns:
        cursor.execute("""
            ALTER TABLE disclosures 
            ADD COLUMN split_entity TEXT
        """)
        conn.commit()
    
    conn.close()

def ensure_fuzzy_match_column(db_path: str) -> None:
    """Ensure the fuzzy_match column exists."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(disclosures)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'fuzzy_match' not in columns:
        cursor.execute("""
            ALTER TABLE disclosures 
            ADD COLUMN fuzzy_match TEXT
        """)
        conn.commit()
    
    conn.close()

def apply_regex_standardization(cursor, config, auto=False):
    """Apply regex-based standardization to entities."""
    # First, copy split_entity to regex_standardized for all rows where it's NULL
    cursor.execute("""
        UPDATE disclosures 
        SET regex_standardized = split_entity 
        WHERE regex_standardized IS NULL
    """)
    
    # Get unique entities that need standardization
    cursor.execute("""
        SELECT DISTINCT split_entity 
        FROM disclosures 
        WHERE split_entity IS NOT NULL
    """)
    entities = [row[0] for row in cursor.fetchall()]
    
    # Apply regex standardization
    standardized = {}
    for entity in entities:
        if entity:
            result = standardize_name(entity, config)
            if result != entity:
                print(f"Regex Stage: {entity} -> {result}")  # Debug log
                standardized[entity] = result
    
    # Update database with standardized names
    for original, standardized_name in standardized.items():
        cursor.execute("""
            UPDATE disclosures 
            SET regex_standardized = ? 
            WHERE split_entity = ?
        """, (standardized_name, original))
    
    return standardized

def group_similar_entities(entities: List[str], config: Config) -> Dict[str, List[str]]:
    """Group similar entities together using fuzzy matching."""
    # Protected entity names that should never be changed
    protected_entities = {
        'Melbourne Cricket Club',
        'Melbourne Cricket Club (MCC)',
        'Victoria Racing Club',
        'Victoria Racing Club (VRC)',
        'Australian Broadcasting Corporation',
        'Australian Broadcasting Corporation (ABC)',
        'Commonwealth Bank of Australia',
        'Commonwealth Bank of Australia (CBA)',
        'National Rugby League',
        'National Rugby League (NRL)',
        'Australian Football League',
        'Australian Football League (AFL)',
    }

    # Skip protected entities
    entities = [e for e in entities if e not in protected_entities]
    
    # Create groups of similar entities
    groups = {}
    processed = set()
    
    for entity in entities:
        if entity in processed:
            continue
            
        # Create a new group with this entity
        group = [entity]
        processed.add(entity)
        
        # Find similar entities
        for other in entities:
            if other == entity or other in processed or other in protected_entities:
                continue
                
            # Calculate similarity using token_set_ratio
            similarity = fuzz.token_set_ratio(entity.lower(), other.lower())
            if similarity >= config.fuzzy_threshold:
                group.append(other)
                processed.add(other)
        
        # Only add groups with more than one entity
        if len(group) > 1:
            # Sort group by length (shortest first) and then alphabetically
            group.sort(key=lambda x: (len(x), x))
            # Only use the standard name if it's not a protected entity
            standard_name = group[0]
            if standard_name not in protected_entities:
                groups[standard_name] = group
    
    return groups

def apply_fuzzy_matching(cursor, config, auto=False):
    """Apply fuzzy matching to find similar entities."""
    # First, copy regex_standardized to fuzzy_match for all rows where it's NULL
    cursor.execute("""
        UPDATE disclosures 
        SET fuzzy_match = regex_standardized 
        WHERE fuzzy_match IS NULL
    """)
    
    # Get entity counts for non-standardized rows
    cursor.execute("""
        SELECT regex_standardized, COUNT(*) as count 
        FROM disclosures 
        WHERE regex_standardized IS NOT NULL 
        AND regex_standardized != fuzzy_match  -- Only process rows that haven't been matched
        GROUP BY regex_standardized 
        ORDER BY count DESC
    """)
    entity_counts = dict(cursor.fetchall())
    
    # Group similar entities
    groups = group_similar_entities(entity_counts.keys(), config)
    
    # Create mapping for standardization
    mapping = {}
    for standard_name, similar_entities in groups.items():
        for entity in similar_entities:
            if entity != standard_name:
                print(f"Fuzzy Stage: {entity} -> {standard_name}")  # Debug log
                mapping[entity] = standard_name
    
    # Update database with fuzzy matches
    for original, standardized in mapping.items():
        cursor.execute("""
            UPDATE disclosures 
            SET fuzzy_match = ? 
            WHERE regex_standardized = ?
        """, (standardized, original))
    
    return mapping

def standardize_regex(name: str) -> str:
    """Standardize entity names using regex patterns."""
    if not name:
        return name
    
    # Skip if entity contains 'and' or '&' as it's likely already been split
    if ' and ' in name.lower() or ' & ' in name.lower():
        return name  # Keep the original
    
    # Protected entity names that should never be modified
    protected_names = [
        "Victoria Racing Club", "Victoria", "Prudential", "Lorne Surf Lifesaving Club",
        "Italian Government", "Parramatta Economic Development Forum", "Canterbury", 
        "Swan Valley Regional Council", "Ipswich Motorway Construction Company", "Origin Alliance",
        "South Australia", "Western Australia", "Northern Territory", "New South Wales",
        "Queensland", "Tasmania", "Australian Capital Territory", "Nauru", 
        "President of the Republic of Nauru", "Republic of Nauru"
    ]
    
    # Check if it's a protected name (case-insensitive comparison)
    for protected in protected_names:
        if name.lower() == protected.lower():
            return name  # Return unchanged
    
    # Convert to title case for consistent handling
    name = name.title()
    
    # Standardize possessives
    name = re.sub(r'\'s\b', '', name)  # Remove possessives
    
    # Standardize state/territory abbreviations - ONLY where they're clearly abbreviations
    state_abbreviations = {
        'NSW': 'New South Wales',
        'VIC': 'Victoria',
        'QLD': 'Queensland',
        'WA': 'Western Australia',
        'SA': 'South Australia',
        'TAS': 'Tasmania',
        'NT': 'Northern Territory',
        'ACT': 'Australian Capital Territory'
    }
    
    # Very strict rules for state/territory expansion - only with word boundaries
    for abbr, full in state_abbreviations.items():
        # 1. Only if it's the exact string (e.g., "NSW") - with word boundaries
        name = re.sub(rf'^{abbr}$', full, name)
            
        # 2. After a comma followed by a space (e.g., "Sydney, NSW") - with word boundaries
        name = re.sub(rf',\s+\b{abbr}\b$', f', {full}', name)
        
        # 3. In a postal address pattern (e.g., "Sydney NSW 2000") - with word boundaries
        name = re.sub(rf'\b([A-Za-z]+)\s+\b{abbr}\b\s+(\d{{4}})\b', fr'\1 {full} \2', name)
    
    # Standardize corporate suffixes
    corporate_suffixes = [
        r'\s+(Pty\s+Ltd|Pty\.?\s+Ltd\.?|Pty\s+Limited|Pty\.?\s+Limited)',
        r'\s+(Limited|Ltd\.?|Ltd)',
        r'\s+(Inc\.?|Incorporated)',
        r'\s+(P/L|P\.L\.?)',
        r'\s+(Group|Holdings)',
        r'\s+(Corp\.?|Corporation)',
        r'\s+(Trust|Fund)',
        r'\s+(Super|Superannuation)',
        r'\s+(Foundation|Foundation\.)',
        r'\s+(Club|Club\.)',
        r'\s+(Society|Society\.)',
        r'\s+(Council|Council\.)',
        r'\s+(Institute|Institute\.)',
        r'\s+(Association|Association\.)',
        r'\s+(Union|Union\.)',
        r'\s+(Office|Office\.)',
        r'\s+(Centre|Center)',
        r'\s+(Project|Project\.)',
        r'\s+(Team|Team\.)',
        r'\s+(Organisers|Organizers)',
        r'\s+(Shares|Share)',
        r'\s+(Pty\.?\s+Pty\.?\s+Ltd\.?)',  # Handle double Pty Ltd
        r'\s+(Pty\.?\s+Pty\.?\s+Limited)',  # Handle double Pty Limited
        r'\s+(Pty\.?\s+Ltd\.?\s+Pty\.?\s+Ltd\.?)',  # Handle double Pty Ltd
        r'\s+(Pty\.?\s+Limited\s+Pty\.?\s+Limited)',  # Handle double Pty Limited
        r'\s+(Pty\.?\s+Ltd\.?\s+Limited)',  # Handle mixed suffixes
        r'\s+(Pty\.?\s+Limited\s+Ltd\.?)',  # Handle mixed suffixes
    ]
    
    # Remove corporate suffixes only at the end of the name
    for suffix in corporate_suffixes:
        name = re.sub(f'{suffix}$', '', name, flags=re.IGNORECASE)
    
    # Clean up any remaining whitespace
    name = re.sub(r'\s+', ' ', name)
    name = name.strip()
    
    # Final check - if the result is just a state name, revert to original
    for state in state_abbreviations.values():
        if name.lower() == state.lower():
            return name
    
    return name

def standardize_acronyms(name: str) -> str:
    """Standardize common acronyms and short names to their simple, commonly recognized names."""
    if not name:
        return name
    
    # Skip if entity contains 'and' or '&' as it's likely already been split
    if ' and ' in name.lower() or ' & ' in name.lower():
        return name  # Keep the original
    
    # Protected entity names that should never be standardized
    protected_entities = [
        "Victoria Racing Club", "Victoria", "Prudential", "Lorne Surf Lifesaving Club",
        "Italian Government", "Parramatta Economic Development Forum", "Canterbury", 
        "Swan Valley Regional Council", "Ipswich Motorway Construction Company", "Origin Alliance",
        "South Australia", "Western Australia", "Northern Territory", "New South Wales",
        "Queensland", "Tasmania", "Australian Capital Territory", "Nauru", 
        "President of the Republic of Nauru", "Republic of Nauru"
    ]
    
    # Check if it's a protected entity (case-insensitive comparison)
    if any(name.lower() == protected.lower() for protected in protected_entities):
        return name
        
    # Dictionary of acronyms and their standard simple names
    acronyms = {
        # Banks
        'ANZ': 'ANZ Bank',
        'CBA': 'Commonwealth Bank',
        'NAB': 'NAB',
        'WBC': 'Westpac',
        'STG': 'St George Bank',
        
        # Companies
        'WES': 'Wesfarmers',
        'WOW': 'Woolworths',
        'TLS': 'Telstra',
        'QAN': 'Qantas',
        
        # States/Territories
        'NSW': 'New South Wales',
        'VIC': 'Victoria',
        'QLD': 'Queensland',
        'WA': 'Western Australia',
        'SA': 'South Australia',
        'TAS': 'Tasmania',
        'NT': 'Northern Territory',
        'ACT': 'Australian Capital Territory',
        
        # Common Institutions
        'SMSF': 'Self Managed Super Fund',
        'VICSUPER': 'Victorian Super',
        'MEDIASUPER': 'Media Super',
        
        # Other Common Acronyms
        'ALP': 'Australian Labor Party',
        'LNP': 'Liberal National Party',
        'UNSW': 'University of New South Wales',
        'UQ': 'University of Queensland',
        'USYD': 'University of Sydney',
        'ANU': 'Australian National University',
        'CSIRO': 'CSIRO',
        
        # Sports Organizations
        'AFL': 'Australian Football League',
        'NFL': 'National Football League',
        'MCC': 'Melbourne Cricket Club',
        'NRL': 'National Rugby League',
        'SANFL': 'South Australian National Football League',
        'RSL': 'Returned and Services League',
        'SLSC': 'Surf Life Saving Club',
        
        # Other Organizations
        'ABC': 'Australian Broadcasting Corporation',
        'AAMI': 'Australian Associated Motor Insurers',
        'MUP': 'Melbourne University Press',
        'ETF': 'Exchange Traded Fund',
        'APESMA': 'Association of Professional Engineers, Scientists and Managers Australia',
        'AIJAC': 'Australia/Israel & Jewish Affairs Council',
        'AICE': 'Australia-Israel Cultural Exchange',
        'RRRC': 'Reef and Rainforest Research Centre',
        'FOGS': 'Former Origin Greats',
        'GDF': 'Global Development Fund',
        'BGC': 'BGC Partners',
        'GPT': 'GPT Group',
        'APA': 'APA Group',
        'VISA': 'Visa Inc',
        'VOCUS': 'Vocus Group',
        'REST': 'Rest Super',
        'AWB': 'Australian Wheat Board',
        'DDH': 'DDH Graham',
        'RBW': 'RBW Enterprises',
        'RQ': 'RQ Supplements',
        'RE': 'RE Group',
        'TM': 'TM Group',
        'KJ': 'KJ Group',
        'AJ': 'AJ Group',
        'KS': 'KS Group',
        'DP': 'DP Group',
        'NB': 'NB Group'
    }
    
    # Only check for exact matches - whole word only
    name_upper = name.upper()
    
    # Check if the entire name is an acronym - exact match only
    if name_upper in acronyms and len(name_upper) == len(name):
        return acronyms[name_upper]
    
    # Handle specific patterns for state abbreviations - with word boundaries
    for abbr, full in {k: v for k, v in acronyms.items() if k in ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'NT', 'ACT']}.items():
        # After a comma and space (e.g., "Perth, WA")
        name = re.sub(rf',\s+\b{abbr}\b$', f', {full}', name, flags=re.IGNORECASE)
        # As a postal code with numbers (e.g., "Sydney NSW 2000")
        name = re.sub(rf'\b([A-Za-z]+)\s+\b{abbr}\b\s+(\d{{4}})\b', fr'\1 {full} \2', name, flags=re.IGNORECASE)
    
    return name

def apply_acronym_standardization(cursor, config, auto=False):
    """Standardize acronyms and abbreviations."""
    # First, copy split_entity to regex_standardized for all rows where it's NULL
    cursor.execute("""
        UPDATE disclosures 
        SET regex_standardized = split_entity 
        WHERE regex_standardized IS NULL
    """)
    
    # Get unique entities
    cursor.execute("""
        SELECT DISTINCT split_entity 
        FROM disclosures 
        WHERE split_entity IS NOT NULL
    """)
    entities = [row[0] for row in cursor.fetchall()]
    
    # Apply acronym standardization
    standardized = {}
    for entity in entities:
        if entity:
            result = standardize_acronyms(entity)
            if result != entity:
                print(f"Acronym Stage: {entity} -> {result}")  # Debug log
                standardized[entity] = result
    
    # Update database with standardized names
    for original, standardized_name in standardized.items():
        cursor.execute("""
            UPDATE disclosures 
            SET regex_standardized = ? 
            WHERE split_entity = ?
        """, (standardized_name, original))
    
    return standardized

def standardize_case(name: str) -> str:
    """Apply case rules to a name."""
    if not name:
        return name
        
    # Skip if entity contains 'and' or '&' as it's likely already been split
    if ' and ' in name.lower() or ' & ' in name.lower():
        return name  # Keep the original
        
    # Check special cases first (case-insensitive)
    name_upper = name.upper()
    for special_case, (standard_name, rule) in SPECIAL_CASES.items():
        if name_upper == special_case.upper():
            if rule == EntityCaseRule.USE_SPECIFIED_CASE:
                return standard_name  # Use the exact case specified
            elif rule == EntityCaseRule.PRESERVE_UPPERCASE:
                return name.upper()  # Force uppercase
            elif rule == EntityCaseRule.EXPAND_TO_FULL:
                return standard_name  # Use full name
    
    # Check if it's an acronym (case-insensitive)
    if name_upper in ACRONYMS:
        return name_upper
    
    # Default to title case
    return name.title()

def apply_case_standardization(cursor, config):
    """Apply case standardization to entities.
    
    This stage updates the regex_standardized column in place.
    Protected entities and special cases maintain their original casing.
    """
    # Get unique entities
    cursor.execute("""
        SELECT DISTINCT regex_standardized 
        FROM disclosures 
        WHERE regex_standardized IS NOT NULL
    """)
    entities = [row[0] for row in cursor.fetchall()]
    
    # Apply case standardization
    standardized = {}
    for entity in entities:
        if entity:
            result = standardize_case(entity)
            if result != entity:
                standardized[entity] = result
    
    # Update database with standardized names
    for original, standardized_name in standardized.items():
        cursor.execute("""
            UPDATE disclosures 
            SET regex_standardized = ? 
            WHERE regex_standardized = ?
        """, (standardized_name, original))
    
    return standardized

def load_config() -> Config:
    """Load standardization configuration."""
    return Config(
        fuzzy_threshold=0.85,
        company_suffix_rule=StandardizationRule.STANDARDIZE_SUFFIX,
        case_rule=StandardizationRule.TITLE_CASE,
        standard_suffix='Pty Ltd',
        use_fuzzy_matching=True
    )

def main():
    parser = argparse.ArgumentParser(description='Standardize entity names in the database')
    parser.add_argument('--db', required=True, help='Path to the SQLite database')
    parser.add_argument('--auto', action='store_true', help='Run in automatic mode without confirmation')
    parser.add_argument('--skip-acronyms', action='store_true', help='Skip acronym standardization')
    args = parser.parse_args()

    # Load configuration
    config = load_config()

    # Ensure required columns exist
    ensure_split_entity_column(args.db)
    ensure_regex_standardized_column(args.db)
    ensure_fuzzy_match_column(args.db)

    # Get a single database connection for the entire process
    conn = get_db_connection(args.db)
    try:
        cursor = conn.cursor()
        
        # Stage 1a: Acronym standardization
        if not args.skip_acronyms:
            print("\n=== Stage 1a: Acronym Standardization ===")
            acronym_mapping = apply_acronym_standardization(cursor, config, args.auto)
            print(f"\nApplied {len(acronym_mapping)} acronym standardizations")
            conn.commit()

        # Stage 1b: Regex-based standardization
        print("\n=== Stage 1b: Regex-based Standardization ===")
        regex_mapping = apply_regex_standardization(cursor, config, args.auto)
        print(f"\nApplied {len(regex_mapping)} regex-based standardizations")
        conn.commit()

        # Stage 2: Fuzzy matching
        print("\n=== Stage 2: Fuzzy Matching ===")
        fuzzy_mapping = apply_fuzzy_matching(cursor, config, args.auto)
        print(f"\nApplied {len(fuzzy_mapping)} fuzzy matching standardizations")
        conn.commit()

        # Stage 3: Case standardization
        print("\n=== Stage 3: Case Standardization ===")
        case_mapping = apply_case_standardization(cursor, config)
        print(f"\nApplied {len(case_mapping)} case standardizations")
        conn.commit()

        print(f"\nTotal standardizations applied: {len(acronym_mapping) + len(regex_mapping) + len(fuzzy_mapping) + len(case_mapping)}")

    finally:
        conn.close()

if __name__ == '__main__':
    main() 