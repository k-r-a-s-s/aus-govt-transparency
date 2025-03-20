#!/usr/bin/env python3
"""
Recategorize Unknown Entries

This module improves data quality by recategorizing entries marked as 'Unknown'
into more appropriate categories based on pattern matching and keyword analysis.
"""

import sqlite3
import logging
import argparse
import re
from typing import Dict, List, Tuple, Optional
from db_handler import DatabaseHandler, Categories, Subcategories, TemporalTypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UnknownRecategorizer:
    """A class for recategorizing unknown entries in the database."""
    
    # Pattern-based classification rules
    CLASSIFICATION_RULES = {
        # Real Estate/Property Classification
        Categories.ASSET: [
            # Residential Properties
            {
                'pattern': r'residen|house|home|apartment|dwelling|accommodation|property(?!.*investment)|flat',
                'subcategory': Subcategories.ASSET_REAL_ESTATE,
                'temporal_type': TemporalTypes.ONGOING
            },
            # Investment Properties
            {
                'pattern': r'investment\s*property|rental\s*property|investment.*real\s*estate|holiday\s*house',
                'subcategory': Subcategories.ASSET_REAL_ESTATE,
                'temporal_type': TemporalTypes.ONGOING
            },
            # Shares and Investments
            {
                'pattern': r'share(?!.*time)|shareholding|stock|investment(?!.*property)|portfolio',
                'subcategory': Subcategories.ASSET_SHARES,
                'temporal_type': TemporalTypes.ONGOING
            },
            # Trusts
            {
                'pattern': r'trust|beneficiary',
                'subcategory': Subcategories.ASSET_TRUST,
                'temporal_type': TemporalTypes.ONGOING
            },
            # Superannuation and funds
            {
                'pattern': r'superannuation|super\s*fund|pension\s*fund',
                'subcategory': Subcategories.ASSET_OTHER,
                'temporal_type': TemporalTypes.ONGOING
            },
            # Vehicles and movable assets
            {
                'pattern': r'car|vehicle|motor|boat|yacht',
                'subcategory': Subcategories.ASSET_OTHER,
                'temporal_type': TemporalTypes.ONGOING
            }
        ],
        
        # Memberships Classification
        Categories.MEMBERSHIP: [
            # Airline/Premium Memberships
            {
                'pattern': r'chairman\'s\s*lounge|virgin\s*club|lounge\s*member|qantas\s*(chairman|club|lounge)|virgin\s*(lounge|club|membership)',
                'subcategory': Subcategories.MEMBERSHIP_PROFESSIONAL,
                'temporal_type': TemporalTypes.ONGOING
            },
            # Professional Associations
            {
                'pattern': r'professional\s*association|national\s*press\s*club|industry\s*association|professional\s*body',
                'subcategory': Subcategories.MEMBERSHIP_PROFESSIONAL,
                'temporal_type': TemporalTypes.ONGOING
            },
            # Party and Organization Memberships
            {
                'pattern': r'member\s*of|membership|party\s*member|liberal\s*party|labor\s*party|ALP|LNP|union|honorary',
                'subcategory': Subcategories.MEMBERSHIP_OTHER,
                'temporal_type': TemporalTypes.ONGOING
            }
        ],
        
        # Income Classification
        Categories.INCOME: [
            # General Income
            {
                'pattern': r'income\s*from|salary|dividend|rent\s*from|rental\s*income|distribution',
                'subcategory': Subcategories.INCOME_OTHER,
                'temporal_type': TemporalTypes.RECURRING
            },
            # Royalties and IP Income
            {
                'pattern': r'royalt|author|book|publication|copyright|patent',
                'subcategory': Subcategories.INCOME_OTHER,
                'temporal_type': TemporalTypes.RECURRING
            },
            # Sale of personal items
            {
                'pattern': r'sold|sale|proceeds|auction',
                'subcategory': Subcategories.INCOME_OTHER,
                'temporal_type': TemporalTypes.ONE_TIME
            }
        ],
        
        # Gift Classification
        Categories.GIFT: [
            # Entertainment and tickets
            {
                'pattern': r'ticket|football|afl|nrl|final|match|concert|performance|entertainment',
                'subcategory': Subcategories.GIFT_ENTERTAINMENT,
                'temporal_type': TemporalTypes.ONE_TIME
            },
            # Electronics gifts
            {
                'pattern': r'ipad|tablet|phone|electronic|device|gadget|tech',
                'subcategory': Subcategories.GIFT_ELECTRONICS,
                'temporal_type': TemporalTypes.ONE_TIME
            },
            # Hospitality
            {
                'pattern': r'dinner|lunch|meal|hospitality|food|wine|alcohol|bottle|catering|hamper|chocolates',
                'subcategory': Subcategories.GIFT_HOSPITALITY,
                'temporal_type': TemporalTypes.ONE_TIME
            },
            # Clothing and apparel
            {
                'pattern': r'suit|tailor|jersey|clothing|shirt|tie|apparel|scarf|hat|cap|dress|uniform',
                'subcategory': Subcategories.GIFT_OTHER,
                'temporal_type': TemporalTypes.ONE_TIME
            },
            # Sports equipment and items
            {
                'pattern': r'cycling|golf|tennis|equipment|sporting|sport\s*item|trophy|medal',
                'subcategory': Subcategories.GIFT_OTHER,
                'temporal_type': TemporalTypes.ONE_TIME
            },
            # Decorative gifts
            {
                'pattern': r'artwork|painting|sculpture|ornament|plaque|award|commemorative|decorative',
                'subcategory': Subcategories.GIFT_DECORATIVE,
                'temporal_type': TemporalTypes.ONE_TIME
            }
        ],
        
        # Travel Classification
        Categories.TRAVEL: [
            # Air Travel
            {
                'pattern': r'flight|air.*travel|upgrade|airfare',
                'subcategory': Subcategories.TRAVEL_AIR,
                'temporal_type': TemporalTypes.ONE_TIME
            },
            # Other Travel
            {
                'pattern': r'travel|accommodation|hotel|resort|trip|tour|visit',
                'subcategory': Subcategories.TRAVEL_OTHER,
                'temporal_type': TemporalTypes.ONE_TIME
            },
            # Event entries and competitions
            {
                'pattern': r'entrance\s*fee|entry\s*fee|competition\s*entry',
                'subcategory': Subcategories.TRAVEL_OTHER,
                'temporal_type': TemporalTypes.ONE_TIME
            }
        ]
    }
    
    # Company names that indicate specific categories
    COMPANY_CATEGORY_MAPPING = {
        # Common stock companies
        'bhp': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'telstra': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'anz': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'cba': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'nab': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'wes': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'amp': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'iag': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'westpac': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'woolworths': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'commonwealth bank': (Categories.ASSET, Subcategories.ASSET_SHARES),
        'rio tinto': (Categories.ASSET, Subcategories.ASSET_SHARES),
        
        # Airlines and lounges
        'qantas': (Categories.MEMBERSHIP, Subcategories.MEMBERSHIP_PROFESSIONAL),
        'virgin': (Categories.MEMBERSHIP, Subcategories.MEMBERSHIP_PROFESSIONAL),
        'chairman\'s lounge': (Categories.MEMBERSHIP, Subcategories.MEMBERSHIP_PROFESSIONAL),
        
        # Sports and entertainment
        'afl': (Categories.GIFT, Subcategories.GIFT_ENTERTAINMENT),
        'nrl': (Categories.GIFT, Subcategories.GIFT_ENTERTAINMENT),
        'cricket australia': (Categories.GIFT, Subcategories.GIFT_ENTERTAINMENT),
        'football': (Categories.GIFT, Subcategories.GIFT_ENTERTAINMENT),
        'tennis': (Categories.GIFT, Subcategories.GIFT_ENTERTAINMENT),
        'australian open': (Categories.GIFT, Subcategories.GIFT_ENTERTAINMENT),
        'rugby': (Categories.GIFT, Subcategories.GIFT_ENTERTAINMENT),
        'grand final': (Categories.GIFT, Subcategories.GIFT_ENTERTAINMENT),
        
        # Publishers and media companies
        'university press': (Categories.INCOME, Subcategories.INCOME_OTHER),
        'publisher': (Categories.INCOME, Subcategories.INCOME_OTHER),
        'media': (Categories.INCOME, Subcategories.INCOME_OTHER),
        
        # Tailors and clothing
        'tailor': (Categories.GIFT, Subcategories.GIFT_OTHER),
        'suit': (Categories.GIFT, Subcategories.GIFT_OTHER),
        
        # Political parties
        'labor party': (Categories.MEMBERSHIP, Subcategories.MEMBERSHIP_OTHER),
        'liberal party': (Categories.MEMBERSHIP, Subcategories.MEMBERSHIP_OTHER),
        'national party': (Categories.MEMBERSHIP, Subcategories.MEMBERSHIP_OTHER),
        'greens': (Categories.MEMBERSHIP, Subcategories.MEMBERSHIP_OTHER),
    }
    
    def __init__(self, db_path: str):
        """
        Initialize the recategorizer.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.db = DatabaseHandler(db_path=db_path)
    
    def recategorize_all_unknowns(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Recategorize all unknown entries in the database.
        
        Args:
            dry_run: If True, only print changes without applying them
            
        Returns:
            Statistics about the recategorization
        """
        # Get connection to the database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Fetch all unknown entries
        cursor.execute("""
            SELECT id, item, details, sub_category
            FROM disclosures
            WHERE category = ?
        """, (Categories.UNKNOWN,))
        
        unknown_entries = cursor.fetchall()
        logger.info(f"Found {len(unknown_entries)} unknown entries to process")
        
        # Statistics for reporting
        stats = {
            'total': len(unknown_entries),
            'recategorized': 0,
            'by_category': {},
            'by_subcategory': {},
            'ignored': 0,
            'unchanged': 0,
            'samples': {
                'recategorized': [],
                'unchanged': []
            }
        }
        
        # Process each unknown entry
        for entry in unknown_entries:
            entry_id, item, details, sub_category = entry
            
            # Combine item and details for pattern matching
            combined_text = f"{item} {details}".lower()
            
            # Check if this is an empty/null entry that should be ignored
            if self._is_empty_entry(combined_text):
                stats['ignored'] += 1
                continue
            
            # Attempt to recategorize
            new_category, new_subcategory, new_temporal_type = self._classify_entry(item, details)
            
            if new_category != Categories.UNKNOWN:
                # Entry can be recategorized
                if not dry_run:
                    cursor.execute("""
                        UPDATE disclosures
                        SET category = ?, sub_category = ?, temporal_type = ?
                        WHERE id = ?
                    """, (new_category, new_subcategory, new_temporal_type, entry_id))
                
                # Update statistics
                stats['recategorized'] += 1
                stats['by_category'][new_category] = stats['by_category'].get(new_category, 0) + 1
                cat_subcat_key = f"{new_category}:{new_subcategory}"
                stats['by_subcategory'][cat_subcat_key] = stats['by_subcategory'].get(cat_subcat_key, 0) + 1
                
                # Store some sample recategorizations for review
                if len(stats['samples']['recategorized']) < 10:
                    stats['samples']['recategorized'].append({
                        'item': item,
                        'details': details,
                        'new_category': new_category,
                        'new_subcategory': new_subcategory
                    })
            else:
                # Entry remains unknown
                stats['unchanged'] += 1
                
                # Store some sample unchanged entries for review
                if len(stats['samples']['unchanged']) < 10:
                    stats['samples']['unchanged'].append({
                        'item': item,
                        'details': details
                    })
        
        if not dry_run:
            conn.commit()
        conn.close()
        
        # Report results
        self._report_results(stats, dry_run)
        return stats
    
    def _is_empty_entry(self, text: str) -> bool:
        """
        Check if an entry is effectively empty/null.
        
        Args:
            text: The combined item and details text
            
        Returns:
            True if the entry should be considered empty
        """
        # Check for entirely empty entries or entries with just N/A, nil, etc.
        empty_patterns = [
            r'^(?:n/?a|nil|none|not\s*applicable)$',
            r'^(?:n/?a|nil|none|not\s*applicable)\s+(?:n/?a|nil|none|not\s*applicable)$',
            r'^(?:spouse|partner|dependent\s*children):?\s*(?:n/?a|nil|none|not\s*applicable)$',
            r'^(?:self):?\s*(?:n/?a|nil|none|not\s*applicable)$'
        ]
        
        for pattern in empty_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _classify_entry(self, item: str, details: str) -> Tuple[str, str, str]:
        """
        Classify an entry based on pattern matching.
        
        Args:
            item: The item name
            details: The details text
            
        Returns:
            Tuple of (category, subcategory, temporal_type)
        """
        # Lowercase for case-insensitive matching
        item_lower = item.lower()
        details_lower = details.lower() if details else ""
        combined_text = f"{item_lower} {details_lower}"
        
        # First check if the item is a known company/entity in our mapping
        for company, (category, subcategory) in self.COMPANY_CATEGORY_MAPPING.items():
            if re.search(r'\b' + re.escape(company) + r'\b', item_lower) or re.search(r'\b' + re.escape(company) + r'\b', details_lower):
                # Determine temporal type based on category
                if category == Categories.ASSET:
                    temporal_type = TemporalTypes.ONGOING
                elif category == Categories.MEMBERSHIP:
                    temporal_type = TemporalTypes.ONGOING
                elif category == Categories.GIFT:
                    temporal_type = TemporalTypes.ONE_TIME
                else:
                    temporal_type = TemporalTypes.ONE_TIME
                
                return category, subcategory, temporal_type
        
        # Try each category's patterns
        for category, rules in self.CLASSIFICATION_RULES.items():
            for rule in rules:
                if re.search(rule['pattern'], combined_text, re.IGNORECASE):
                    return category, rule['subcategory'], rule['temporal_type']
        
        # Default if no patterns match
        return Categories.UNKNOWN, "Other", TemporalTypes.ONE_TIME
    
    def _report_results(self, stats: Dict[str, int], dry_run: bool) -> None:
        """
        Report the results of the recategorization.
        
        Args:
            stats: Statistics about the recategorization
            dry_run: Whether this was a dry run
        """
        mode = "DRY RUN - " if dry_run else ""
        logger.info(f"\n{mode}Recategorization Results:")
        logger.info(f"Total unknown entries processed: {stats['total']}")
        logger.info(f"Entries recategorized: {stats['recategorized']} ({stats['recategorized']/stats['total']*100:.1f}%)")
        logger.info(f"Entries ignored (empty/null): {stats['ignored']} ({stats['ignored']/stats['total']*100:.1f}%)")
        logger.info(f"Entries still unknown: {stats['unchanged']} ({stats['unchanged']/stats['total']*100:.1f}%)")
        
        if stats['by_category']:
            logger.info("\nRecategorized by category:")
            for category, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  - {category}: {count} entries ({count/stats['recategorized']*100:.1f}%)")
        
        if stats['by_subcategory']:
            logger.info("\nRecategorized by subcategory:")
            for cat_subcat, count in sorted(stats['by_subcategory'].items(), key=lambda x: x[1], reverse=True)[:10]:
                category, subcategory = cat_subcat.split(':')
                logger.info(f"  - {category} > {subcategory}: {count} entries")
        
        # Print sample recategorizations
        if stats['samples']['recategorized']:
            logger.info("\nSample Recategorizations:")
            for i, sample in enumerate(stats['samples']['recategorized'], 1):
                logger.info(f"  {i}. '{sample['item']}' ({sample['details'][:30]}...) → {sample['new_category']} > {sample['new_subcategory']}")
        
        # Print sample unchanged entries
        if stats['samples']['unchanged']:
            logger.info("\nSample Entries Still Unknown:")
            for i, sample in enumerate(stats['samples']['unchanged'], 1):
                logger.info(f"  {i}. '{sample['item']}' ({sample['details'][:30]}...)")

def main():
    """Main function to parse arguments and run the recategorization."""
    parser = argparse.ArgumentParser(description="Recategorize unknown entries in the database")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to the SQLite database file")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without applying them")
    
    args = parser.parse_args()
    
    logger.info(f"Starting unknown recategorization for database: {args.db_path}")
    
    recategorizer = UnknownRecategorizer(args.db_path)
    stats = recategorizer.recategorize_all_unknowns(args.dry_run)
    
    if args.dry_run:
        logger.info("\nTo apply these changes, run without the --dry-run flag")
    
    logger.info("Done!")

if __name__ == "__main__":
    main() 