"""
This file contains the function that will be integrated into db_handler.py
to correctly populate the item field during data ingestion.
"""

import re
from typing import Optional

def extract_item_from_details(category: str, subcategory: str, entity: str, details: str) -> str:
    """
    Extract a meaningful item value based on disclosure details.
    
    Args:
        category: The disclosure category
        subcategory: The disclosure subcategory (if any)
        entity: The entity associated with the disclosure
        details: The detailed description
        
    Returns:
        A meaningful item value
    """
    # Default fallbacks by category
    category_defaults = {
        "Gift": "Gift",
        "Asset": "Asset",
        "Income": "Income",
        "Liability": "Liability",
        "Travel": "Travel",
        "Hospitality": "Hospitality",
        "Unknown": "Unknown"
    }
    
    # Subcategory-specific defaults
    subcategory_mapping = {
        "Shares": "Shares",
        "Property": "Property",
        "Trusts": "Trust",
        "Savings": "Savings Account",
        "Mortgage": "Mortgage",
        "Personal Loan": "Personal Loan",
        "Credit Card": "Credit Card",
        "Salary": "Salary",
        "Pension": "Pension",
        "Dividends": "Dividends",
        "Rental Income": "Rental Income"
    }
    
    # Lowercase details for easier pattern matching
    details_lower = details.lower() if details else ""
    
    # Extract based on category
    if category == "Gift":
        # Try to extract gift type from details
        gift_patterns = [
            # Format: "Gift of X" or "X gift"
            r"gift of ([^\.]+)",
            r"([^\.]+) gift",
            # Look for surrendered gifts
            r"surrendered this gift[^:]*:([^\.]+)",
            r"surrendered this gift[^-]*-([^\.]+)",
            # Look for specific gift types
            r"book[s]* titled ([^\.]+)",
            r"bottle[s]* of ([^\.]+)",
            r"([^\.]+) (statue|ornament|trophy|medal|plaque)",
            r"(statue|ornament|trophy|medal|plaque) ([^\.]+)"
        ]
        
        for pattern in gift_patterns:
            match = re.search(pattern, details_lower)
            if match:
                found_item = match.group(1).strip() if len(match.groups()) == 1 else f"{match.group(1)} {match.group(2)}".strip()
                if found_item and len(found_item) < 50:  # Reasonable length check
                    return found_item.title()
        
        # If we can't extract a specific gift, use generic terms
        if "book" in details_lower:
            return "Book"
        if "wine" in details_lower or "champagne" in details_lower:
            return "Wine/Champagne"
        if "ticket" in details_lower:
            return "Tickets"
        if "artwork" in details_lower or "painting" in details_lower:
            return "Artwork"
        if "watch" in details_lower:
            return "Watch"
        
        # Default for gifts
        return "Gift"
    
    elif category == "Asset" and "property" in details_lower:
        # Try to extract property type
        property_types = {
            "residential": "Residential Property",
            "investment": "Investment Property", 
            "house": "House",
            "apartment": "Apartment",
            "unit": "Unit",
            "flat": "Apartment",
            "farm": "Farm",
            "land": "Land",
            "commercial": "Commercial Property",
            "rural": "Rural Property",
            "holiday": "Holiday Property",
            "vacation": "Vacation Property"
        }
        
        # Look for property types
        for key, value in property_types.items():
            if key in details_lower:
                # Look for location
                location_match = re.search(r'in ([^,\.]+)', details_lower)
                if location_match:
                    location = location_match.group(1).strip().title()
                    return f"{value} in {location}"
                return value
        
        # Default for property
        return "Property"
    
    elif category == "Asset" and "share" in details_lower:
        # Determine if we can extract share type
        if "bank" in details_lower or any(bank in details_lower for bank in ["commonwealth", "westpac", "anz", "nab"]):
            return "Bank Shares"
        if "mining" in details_lower or any(miner in details_lower for miner in ["bhp", "rio", "fortescue"]):
            return "Mining Shares"
        if "energy" in details_lower or "oil" in details_lower or "gas" in details_lower:
            return "Energy Shares"
        if "telecom" in details_lower:
            return "Telecom Shares"
        
        # Default for shares
        return "Shares"
    
    elif category == "Income":
        if "salary" in details_lower or "wage" in details_lower:
            return "Salary"
        if "dividend" in details_lower:
            return "Dividends"
        if "pension" in details_lower or "retirement" in details_lower:
            return "Pension"
        if "consult" in details_lower:
            return "Consulting Fee"
        if "rent" in details_lower:
            return "Rental Income"
        if "speaking" in details_lower or "lecture" in details_lower:
            return "Speaking/Lecturing Fee"
        if "director" in details_lower:
            return "Director's Fee"
        
        # Default for income
        return "Income"
    
    elif category == "Liability":
        if "mortgage" in details_lower:
            # Check if it's for investment property
            if "investment" in details_lower:
                return "Investment Property Mortgage"
            return "Mortgage"
        if "loan" in details_lower:
            if "personal" in details_lower:
                return "Personal Loan"
            if "car" in details_lower:
                return "Car Loan"
            if "investment" in details_lower:
                return "Investment Loan"
            return "Loan"
        if "credit" in details_lower and "card" in details_lower:
            return "Credit Card"
        
        # Default for liability
        return "Liability"
    
    elif category == "Travel":
        if "upgrade" in details_lower:
            return "Flight Upgrade"
        if "flight" in details_lower:
            return "Flights"
        if "accommodation" in details_lower:
            return "Accommodation"
        if "lounge" in details_lower:
            return "Lounge Access"
        
        # Default for travel
        return "Travel"
    
    # If we get here, try to use subcategory mapping or category default
    if subcategory and subcategory in subcategory_mapping:
        return subcategory_mapping[subcategory]
    
    return category_defaults.get(category, "Unknown") 