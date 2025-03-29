#!/usr/bin/env python3
"""
Script to scrape MP names and party affiliations from Wikipedia for multiple parliaments.
Outputs a CSV file with the most recent party affiliation for each MP.
"""

import pandas as pd
import re
import os
import sys
import sqlite3
import traceback
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

# Add project root to path to allow importing from other modules
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Try to import from db_handler if available
try:
    from db_handler import DatabaseHandler
    HAS_DB_HANDLER = True
except ImportError:
    HAS_DB_HANDLER = False

# Parliament numbers and corresponding Wikipedia URLs
parliaments = {
    47: "https://en.wikipedia.org/wiki/Members_of_the_Australian_House_of_Representatives,_2022%E2%80%932025",
    46: "https://en.wikipedia.org/wiki/Members_of_the_Australian_House_of_Representatives,_2019%E2%80%932022",
    45: "https://en.wikipedia.org/wiki/Members_of_the_Australian_House_of_Representatives,_2016%E2%80%932019",
    44: "https://en.wikipedia.org/wiki/Members_of_the_Australian_House_of_Representatives,_2013%E2%80%932016",
    43: "https://en.wikipedia.org/wiki/Members_of_the_Australian_House_of_Representatives,_2010%E2%80%932013",
}

# Party name standardization mapping
PARTY_MAPPING = {
    "ALP": "Australian Labor Party",
    "Labor": "Australian Labor Party",
    "Australian Labor Party (ALP)": "Australian Labor Party",
    "Liberal": "Liberal Party of Australia",
    "LIB": "Liberal Party of Australia",
    "Liberal Party": "Liberal Party of Australia",
    "Liberal Party of Australia (LIB)": "Liberal Party of Australia",
    "NAT": "National Party of Australia",
    "National": "National Party of Australia",
    "The Nationals": "National Party of Australia",
    "National Party": "National Party of Australia",
    "Nationals": "National Party of Australia",
    "National Party of Australia (NAT)": "National Party of Australia",
    "GRN": "Australian Greens",
    "Greens": "Australian Greens",
    "The Greens": "Australian Greens",
    "Australian Greens (GRN)": "Australian Greens",
    "Independent": "Independent",
    "IND": "Independent",
    "LNP": "Liberal National Party",
    "Liberal National": "Liberal National Party",
    "Liberal National Party of Queensland": "Liberal National Party",
    "KAP": "Katter's Australian Party",
    "Katter's Australian": "Katter's Australian Party",
    "CA": "Centre Alliance",
    "Centre Alliance": "Centre Alliance",
    "Nick Xenophon Team": "Centre Alliance",
    "NXT": "Centre Alliance",
    "UAP": "United Australia Party",
    "Palmer United Party": "United Australia Party",
    "PUP": "United Australia Party",
    "One Nation": "Pauline Hanson's One Nation",
    "PHON": "Pauline Hanson's One Nation",
    "ONP": "Pauline Hanson's One Nation",
    "Jacqui Lambie Network": "Jacqui Lambie Network",
    "JLN": "Jacqui Lambie Network",
}

# Special cases for MP name matching
MP_NAME_SPECIAL_CASES = {
    # Format: 'db_name': 'wikipedia_name'
    "Nicholas David Champion": "Nick Champion",
    "Gregory Ivan Combet": "Greg Combet",
    "Stephen William Gibbons": "Steve Gibbons",
    "Robert Mitchell": "Rob Mitchell",
    "Donald James Randall": "Don Randall",
    "Peter Sidebottom": "Sid Sidebottom",
    "Antony Harold Windsor": "Tony Windsor",
    "Antonio Zappia": "Tony Zappia",
    "Christopher Bowen": "Chris Bowen",
    "Jennifer Louise Macklin": "Jenny Macklin",
    "Daniel Tehan": "Dan Tehan",
    "Van Manen, Albertus Johannes": "Bert Van Manen",
    "Albertus Van Manen": "Bert Van Manen",
    "Kenneth Wyatt": "Ken Wyatt",
    "Patrick Martin Conroy": "Pat Conroy",
    "Christopher John Crewther": "Chris Crewther",
    "Michael Randolph Freelander": "Mike Freelander",
    "Joshua Frydenberg": "Josh Frydenberg",
    "Alexander George Hawke": "Alex Hawke",
    "Christopher Hayes": "Chris Hayes",
    "Gerardine (Ged) Mary Kearney": "Ged Kearney",
    "Llewellyn Stephen O'Brien": "Llew O'Brien",
    "Edward Lynam O'Brien": "Ted O'Brien",
    "Kenneth Desmond O'Dowd": "Ken O'Dowd",
    "Catherine Elizabeth O'Toole": "Cathy O'Toole",
    "Antony (Tony) Pasin": "Tony Pasin",
    "Joshna Hamilton Wilson": "Josh Wilson",
    "Llewellyn O'brien": "Llew O'Brien",
    "Timothy Wilson": "Tim Wilson",
    "Timothy Watts": "Tim Watts",
    "Matthew Thistlethwaite": "Matt Thistlethwaite",
    "Ananda-Rajah": "Michelle Ananda-Rajah",
}

# Dictionary of MPs that are not found in Wikipedia tables (newer MPs, etc.)
FALLBACK_MP_PARTIES = {
    # Newer MPs not in Wikipedia tables yet
    "Ananda-Rajah": "Australian Labor Party",
    "Michelle Ananda-Rajah": "Australian Labor Party",
    "Jodie Belyea": "Australian Labor Party",
    "Max Chandler-Mather": "Australian Greens",
    "Kate Chaney": "Independent",
    "Zoe Daniel": "Independent",
    "Carina Garland": "Australian Labor Party",
    "Jerome Laxale": "Australian Labor Party",
    "Sam Lim": "Australian Labor Party",
    "Tracey Roberts": "Australian Labor Party",
    "Allegra Spender": "Independent",
    "Kylea Tink": "Independent",
    "Elizabeth Watson-Brown": "Australian Greens",
    
    # Special case for literal "Unknown" entries
    "Unknown": "N/A"  # These are not actual MPs but entries that couldn't be linked to a specific person
}

def clean_name(name: str) -> str:
    """
    Clean MP names by removing titles, brackets, and standardizing format.
    """
    # Handle non-string values (like NaN)
    if not isinstance(name, str):
        # Convert to string if it's a number, or use empty string for NaN
        if pd.isna(name):
            return ""
        try:
            name = str(name)
        except:
            return ""
    
    # Remove honorifics and titles
    name = re.sub(r'(Hon\.|Dr\.|Mr\.|Ms\.|Mrs\.|Sir|Dame)\s*', '', name)
    
    # Remove anything in brackets
    name = re.sub(r'\([^)]*\)', '', name)
    
    # Remove any trailing commas and extra whitespace
    name = re.sub(r',.*$', '', name)
    name = name.strip()
    
    return name

def normalize_mp_name(name: str) -> str:
    """
    Normalize an MP name for consistent matching across different formats.
    Handles different name orders, middle names, and removes non-essential parts.
    
    Args:
        name: MP name to normalize
        
    Returns:
        Normalized name for flexible matching
    """
    if not name or not isinstance(name, str):
        return ""
    
    # Convert to lowercase for case-insensitive matching
    name = name.lower()
    
    # Remove honorifics, titles, and suffixes
    name = re.sub(r'\b(hon\.|dr\.|mr\.|ms\.|mrs\.|sir|dame|mp)\b', '', name)
    
    # Remove anything in brackets or parentheses (birth dates, etc.)
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'\[[^\]]*\]', '', name)
    
    # Handle comma-separated names (e.g., "Smith, John")
    if ',' in name:
        parts = name.split(',')
        if len(parts) >= 2:
            # Rearrange "Last, First" to "First Last"
            name = f"{parts[1].strip()} {parts[0].strip()}"
    
    # Remove all punctuation and multiple spaces
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Extract just the first and last name for more flexible matching
    # This helps when middle names are inconsistently used
    parts = name.split()
    if len(parts) >= 2:
        # Keep first and last for simplest matching
        first_name = parts[0]
        last_name = parts[-1]
        return f"{first_name} {last_name}"
    
    return name

def get_name_parts(name: str) -> Tuple[str, List[str], str]:
    """
    Split a name into its component parts: first name, middle names, and last name.
    
    Args:
        name: Full name to split
        
    Returns:
        Tuple of (first_name, middle_names, last_name)
    """
    if not name or not isinstance(name, str):
        return ("", [], "")
    
    # Clean the name first
    clean = clean_name(name)
    
    # Split into parts
    parts = clean.split()
    
    if len(parts) == 1:
        return (parts[0], [], "")
    elif len(parts) == 2:
        return (parts[0], [], parts[1])
    else:
        return (parts[0], parts[1:-1], parts[-1])

def name_similarity_score(name1: str, name2: str) -> float:
    """
    Calculate a similarity score between two names.
    
    Args:
        name1: First name
        name2: Second name
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not name1 or not name2:
        return 0.0
    
    # Get name parts
    first1, middle1, last1 = get_name_parts(name1)
    first2, middle2, last2 = get_name_parts(name2)
    
    # Score starts at 0
    score = 0.0
    
    # Last name match is most important (50% of score)
    if last1.lower() == last2.lower():
        score += 0.5
    
    # First name match (30% of score)
    if first1.lower() == first2.lower():
        score += 0.3
    # First name initial match (15% of score)
    elif first1 and first2 and first1[0].lower() == first2[0].lower():
        score += 0.15
    
    # Middle name matching (20% of score)
    if middle1 and middle2:
        # Check if any middle names match
        middle_match = any(m1.lower() == m2.lower() for m1 in middle1 for m2 in middle2)
        if middle_match:
            score += 0.15
        # Check if any middle initials match
        elif any(m1[0].lower() == m2[0].lower() for m1 in middle1 for m2 in middle2 if m1 and m2):
            score += 0.05
    
    return score

def standardize_party(party: str) -> str:
    """
    Standardize party names to a consistent format.
    """
    # Handle non-string values (like NaN)
    if not isinstance(party, str):
        # Convert to string if it's a number, or use "Unknown" for NaN
        if pd.isna(party):
            return "Unknown"
        try:
            party = str(party)
        except:
            return "Unknown"
    
    # Remove any trailing numbers or footnotes
    party = re.sub(r'\[\d+\]', '', party)
    party = re.sub(r'\(\d+\)', '', party)
    party = party.strip()
    
    # Look up in mapping
    return PARTY_MAPPING.get(party, party)

def clean_party_footnotes(party: str) -> str:
    """
    Clean party names by removing footnote annotations like [f], [g], etc.
    """
    if not isinstance(party, str):
        return "Unknown"
    
    # Remove footnote annotations like [f], [g], [i], [ii], etc.
    cleaned = re.sub(r'\s*\[[a-z]+\](?:\s*/.*)?', '', party)
    cleaned = re.sub(r'\s*\[[a-z]+\](?:\s*\[[a-z]+\])*', '', cleaned)
    cleaned = re.sub(r'\.mw-parser-output.*', '', cleaned)
    
    # Extra cleaning for specific cases
    if 'Liberal National' in cleaned:
        return 'Liberal National Party'
    
    return cleaned.strip()

def get_mp_data() -> pd.DataFrame:
    """
    Scrape MP information from Wikipedia for multiple parliaments.
    
    Returns:
        DataFrame with MP names and their most recent party affiliations.
    """
    all_data = []

    for parliament, url in parliaments.items():
        print(f"Scraping Parliament {parliament}...")
        try:
            tables = pd.read_html(url)

            # Heuristic: Find the largest table that has "Member" or "Name" column
            target_table = None
            max_rows = 0
            for table in tables:
                # Convert column names to strings to handle any non-string types
                str_columns = [str(c).strip() for c in table.columns]
                
                if any("Member" in col or "Name" in col for col in str_columns):
                    if len(table) > max_rows:  # Find the largest relevant table
                        target_table = table
                        max_rows = len(table)

            if target_table is None:
                print(f"Warning: No suitable table found for Parliament {parliament}")
                continue

            df = target_table.copy()

            # Print column names for debugging
            print(f"Columns found: {list(df.columns)}")
            
            # Print a sample of rows to inspect the data
            print("\nSample data from the table:")
            print(df.head(3))

            # Normalize column names
            df.columns = [str(c).strip() for c in df.columns]
            
            # Find the name column
            name_col = next((c for c in df.columns if any(term in c.lower() for term in ["member", "name", "mp"])), None)
            
            # For party, try different approaches - there might be multiple party columns
            party_cols = [c for c in df.columns if "party" in c.lower()]
            
            # For electorate, look for columns that might contain electorate information
            electorate_cols = [c for c in df.columns if any(term in c.lower() for term in ["electorate", "division", "constituency", "seat"])]
            electorate_col = electorate_cols[0] if electorate_cols else None
            
            if not name_col or not party_cols:
                print(f"Skipping Parliament {parliament} due to missing columns.")
                continue
            
            # Try to find the best party column - some might have actual party values while others might be empty
            selected_party_col = None
            
            # Check each party column to find one with meaningful data
            for party_col in party_cols:
                # Get the first few non-null party values
                sample_parties = df[party_col].dropna().head(5).tolist()
                print(f"Sample parties from '{party_col}': {sample_parties}")
                
                # If we find parties that match our known parties, use this column
                if any(p in PARTY_MAPPING or any(known in str(p).lower() for known in ["labor", "liberal", "national", "green"]) 
                       for p in sample_parties):
                    selected_party_col = party_col
                    break
            
            # If we didn't find a good party column, use the first one
            if not selected_party_col and party_cols:
                selected_party_col = party_cols[0]
            
            print(f"Using columns: Name='{name_col}', Party='{selected_party_col}', Electorate='{electorate_col}'")

            # Clean and extract relevant columns
            if electorate_col:
                df_cleaned = df[[name_col, selected_party_col, electorate_col]].copy()
                df_cleaned.columns = ["Name", "Party", "Electorate"]
            else:
                df_cleaned = df[[name_col, selected_party_col]].copy()
                df_cleaned.columns = ["Name", "Party"]
                df_cleaned["Electorate"] = None
            
            # Clean names and standardize parties
            df_cleaned["Name"] = df_cleaned["Name"].apply(clean_name)
            df_cleaned["Party"] = df_cleaned["Party"].apply(standardize_party)
            
            # Filter out empty values and table headers mistakenly parsed as data
            df_cleaned = df_cleaned[
                (df_cleaned["Name"].str.strip() != "") & 
                (df_cleaned["Name"].str.lower() != "member") &
                (df_cleaned["Party"].str.strip() != "")
            ]
            
            # Add parliament number
            df_cleaned["Parliament"] = parliament
            
            # Add start and end years for the parliament
            years_match = re.search(r'(\d{4})%E2%80%93(\d{4})', url)
            if years_match:
                df_cleaned["Start_Year"] = int(years_match.group(1))
                df_cleaned["End_Year"] = int(years_match.group(2))

            all_data.append(df_cleaned)
            
            print(f"  Found {len(df_cleaned)} MPs for Parliament {parliament}")
            print(f"  Party distribution: \n{df_cleaned['Party'].value_counts().head(10)}\n")
            
        except Exception as e:
            print(f"Error processing Parliament {parliament}: {e}")
            import traceback
            traceback.print_exc()

    if not all_data:
        raise ValueError("No data was scraped from any parliament")

    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)

    # Sort by Parliament descending so we keep most recent first
    combined_df = combined_df.sort_values(by="Parliament", ascending=False)

    # Drop duplicates, keeping most recent party affiliation
    deduped_df = combined_df.drop_duplicates(subset="Name", keep="first").reset_index(drop=True)
    
    # Remove any rows with empty names (final check)
    deduped_df = deduped_df[deduped_df["Name"].str.strip() != ""]
    
    return deduped_df

def update_database(mp_data: pd.DataFrame, db_path: str) -> None:
    """
    Update the database with MP party information.
    
    Args:
        mp_data: DataFrame with MP data
        db_path: Path to the SQLite database
    """
    # Create a lookup of normalized names to original names and parties
    normalized_lookup = {}
    similarity_lookups = {}
    electorate_lookup = {}
    
    for _, row in mp_data.iterrows():
        # Regular normalization
        norm_name = normalize_mp_name(row['Name'])
        if norm_name:
            normalized_lookup[norm_name] = {
                'original_name': row['Name'],
                'party': row['Party']
            }
        
        # Store name parts for similarity matching
        name_parts = get_name_parts(row['Name'])
        if name_parts[0] and name_parts[2]:  # Has first and last name
            similarity_lookups[row['Name']] = {
                'parts': name_parts,
                'party': row['Party']
            }
            
        # Create electorate lookup if available
        if 'Electorate' in row and row['Electorate'] and isinstance(row['Electorate'], str):
            electorate = row['Electorate'].strip()
            if electorate:
                if electorate not in electorate_lookup:
                    electorate_lookup[electorate] = []
                electorate_lookup[electorate].append({
                    'name': row['Name'],
                    'party': row['Party']
                })
    
    if HAS_DB_HANDLER:
        try:
            db = DatabaseHandler(db_path)
            
            # Get existing MPs with electorates if possible
            existing_mps = db.get_all_mps()
            
            # First pass: Exact matches
            exact_match_count = 0
            matched_names = set()
            
            for mp in existing_mps:
                if mp['name'] in mp_data['Name'].values:
                    party = mp_data[mp_data['Name'] == mp['name']].iloc[0]['Party']
                    db.update_mp_party(mp['name'], party)
                    matched_names.add(mp['name'])
                    exact_match_count += 1
            
            print(f"Updated party information for {exact_match_count} MPs with exact name matches")
            
            # Second pass: Normalized name matching
            normalized_match_count = 0
            
            for mp in existing_mps:
                # Skip MPs already matched
                if mp['name'] in matched_names:
                    continue
                
                # Check special cases first
                if mp['name'] in MP_NAME_SPECIAL_CASES:
                    wiki_name = MP_NAME_SPECIAL_CASES[mp['name']]
                    if wiki_name in mp_data['Name'].values:
                        party = mp_data[mp_data['Name'] == wiki_name].iloc[0]['Party']
                        db.update_mp_party(mp['name'], party)
                        matched_names.add(mp['name'])
                        print(f"Special case match: '{mp['name']}' -> '{wiki_name}' (Party: {party})")
                        normalized_match_count += 1
                        continue
                
                # Try normalized matching
                norm_name = normalize_mp_name(mp['name'])
                if norm_name in normalized_lookup:
                    matched_info = normalized_lookup[norm_name]
                    db.update_mp_party(mp['name'], matched_info['party'])
                    matched_names.add(mp['name'])
                    print(f"Normalized match: '{mp['name']}' -> '{matched_info['original_name']}' (Party: {matched_info['party']})")
                    normalized_match_count += 1
            
            print(f"Updated party information for {normalized_match_count} additional MPs with normalized name matching")
            
            # Third pass: Similarity-based matching for remaining MPs
            similarity_match_count = 0
            
            for mp in existing_mps:
                # Skip MPs already matched
                if mp['name'] in matched_names:
                    continue
                
                best_match = None
                best_score = 0.7  # Threshold score to consider a match
                best_name = None
                
                for wiki_name, info in similarity_lookups.items():
                    score = name_similarity_score(mp['name'], wiki_name)
                    if score > best_score:
                        best_score = score
                        best_match = info['party']
                        best_name = wiki_name
                
                if best_match:
                    db.update_mp_party(mp['name'], best_match)
                    matched_names.add(mp['name'])
                    print(f"Similarity match ({best_score:.2f}): '{mp['name']}' -> '{best_name}' (Party: {best_match})")
                    similarity_match_count += 1
            
            print(f"Updated party information for {similarity_match_count} additional MPs with similarity matching")
            
            # Fourth pass: Electorate-based matching for remaining MPs
            electorate_match_count = 0
            
            # Get electorates from the database for unmatched MPs
            try:
                for mp in existing_mps:
                    # Skip MPs already matched
                    if mp['name'] in matched_names:
                        continue
                    
                    # Get the MP's electorate
                    mp_electorate = None
                    if 'electorate' in mp and mp['electorate']:
                        mp_electorate = mp['electorate']
                    else:
                        # Try to get electorate from disclosures
                        results = db.query_db(
                            "SELECT DISTINCT electorate FROM disclosures WHERE mp_name = ? AND electorate IS NOT NULL AND electorate != ''",
                            (mp['name'],)
                        )
                        if results:
                            mp_electorate = results[0]['electorate']
                    
                    # If we have an electorate and it's in our lookup, try to match
                    if mp_electorate and mp_electorate in electorate_lookup:
                        # If only one MP in this electorate in our dataset, it's likely the same person
                        if len(electorate_lookup[mp_electorate]) == 1:
                            mp_info = electorate_lookup[mp_electorate][0]
                            db.update_mp_party(mp['name'], mp_info['party'])
                            matched_names.add(mp['name'])
                            print(f"Electorate match: '{mp['name']}' -> '{mp_info['name']}' (Electorate: {mp_electorate}, Party: {mp_info['party']})")
                            electorate_match_count += 1
                        else:
                            # Multiple MPs from the same electorate, try to find the closest name match
                            best_match = None
                            best_score = 0.5  # Lower threshold because we already have electorate match
                            best_name = None
                            
                            for mp_info in electorate_lookup[mp_electorate]:
                                score = name_similarity_score(mp['name'], mp_info['name'])
                                if score > best_score:
                                    best_score = score
                                    best_match = mp_info['party']
                                    best_name = mp_info['name']
                            
                            if best_match:
                                db.update_mp_party(mp['name'], best_match)
                                matched_names.add(mp['name'])
                                print(f"Electorate+name match ({best_score:.2f}): '{mp['name']}' -> '{best_name}' (Electorate: {mp_electorate}, Party: {best_match})")
                                electorate_match_count += 1
            except Exception as e:
                print(f"Error during electorate matching: {e}")
            
            print(f"Updated party information for {electorate_match_count} additional MPs with electorate matching")
            
            # Fifth pass: Fallback to manually curated MP data for remaining MPs
            fallback_match_count = 0
            
            for mp in existing_mps:
                # Skip MPs already matched
                if mp['name'] in matched_names:
                    continue
                
                # Check if we have a fallback entry for this MP
                if mp['name'] in FALLBACK_MP_PARTIES:
                    party = FALLBACK_MP_PARTIES[mp['name']]
                    if party != "Unknown":  # Only update if we have actual party information
                        db.update_mp_party(mp['name'], party)
                        matched_names.add(mp['name'])
                        print(f"Fallback match: '{mp['name']}' (Party: {party})")
                        fallback_match_count += 1
            
            print(f"Updated party information for {fallback_match_count} additional MPs with fallback data")
            print(f"Total MPs updated: {exact_match_count + normalized_match_count + similarity_match_count + electorate_match_count + fallback_match_count}")
            
        except Exception as e:
            print(f"Error updating database: {e}")
            traceback.print_exc()
    else:
        # Fallback if db_handler is not available
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get all unique MP names from the database
            cursor.execute("SELECT DISTINCT mp_name FROM disclosures")
            db_mp_names = [row[0] for row in cursor.fetchall()]
            
            # First pass: Exact matches
            exact_match_count = 0
            matched_names = set()
            
            for db_mp_name in db_mp_names:
                if db_mp_name in mp_data['Name'].values:
                    party = mp_data[mp_data['Name'] == db_mp_name].iloc[0]['Party']
                    cursor.execute(
                        "UPDATE disclosures SET party = ? WHERE mp_name = ?",
                        (party, db_mp_name)
                    )
                    exact_match_count += cursor.rowcount
                    matched_names.add(db_mp_name)
            
            print(f"Updated party information for {exact_match_count} MPs with exact name matches")
            
            # Second pass: Normalized name matching and special cases
            normalized_match_count = 0
            
            for db_mp_name in db_mp_names:
                # Skip MPs already matched
                if db_mp_name in matched_names:
                    continue
                
                # Check special cases first
                if db_mp_name in MP_NAME_SPECIAL_CASES:
                    wiki_name = MP_NAME_SPECIAL_CASES[db_mp_name]
                    if wiki_name in mp_data['Name'].values:
                        party = mp_data[mp_data['Name'] == wiki_name].iloc[0]['Party']
                        cursor.execute(
                            "UPDATE disclosures SET party = ? WHERE mp_name = ?",
                            (party, db_mp_name)
                        )
                        updated_rows = cursor.rowcount
                        if updated_rows > 0:
                            print(f"Special case match: '{db_mp_name}' -> '{wiki_name}' (Party: {party}, Records: {updated_rows})")
                            normalized_match_count += updated_rows
                            matched_names.add(db_mp_name)
                        continue
                
                # Try normalized matching
                norm_name = normalize_mp_name(db_mp_name)
                if norm_name in normalized_lookup:
                    matched_info = normalized_lookup[norm_name]
                    cursor.execute(
                        "UPDATE disclosures SET party = ? WHERE mp_name = ?",
                        (matched_info['party'], db_mp_name)
                    )
                    updated_rows = cursor.rowcount
                    if updated_rows > 0:
                        print(f"Normalized match: '{db_mp_name}' -> '{matched_info['original_name']}' (Party: {matched_info['party']}, Records: {updated_rows})")
                        normalized_match_count += updated_rows
                        matched_names.add(db_mp_name)
            
            print(f"Updated party information for {normalized_match_count} additional records with normalized name matching")
            
            # Third pass: Similarity-based matching for remaining MPs
            similarity_match_count = 0
            
            for db_mp_name in db_mp_names:
                # Skip MPs already matched
                if db_mp_name in matched_names:
                    continue
                
                best_match = None
                best_score = 0.7  # Threshold score to consider a match
                best_name = None
                
                for wiki_name, info in similarity_lookups.items():
                    score = name_similarity_score(db_mp_name, wiki_name)
                    if score > best_score:
                        best_score = score
                        best_match = info['party']
                        best_name = wiki_name
                
                if best_match:
                    cursor.execute(
                        "UPDATE disclosures SET party = ? WHERE mp_name = ?",
                        (best_match, db_mp_name)
                    )
                    updated_rows = cursor.rowcount
                    if updated_rows > 0:
                        print(f"Similarity match ({best_score:.2f}): '{db_mp_name}' -> '{best_name}' (Party: {best_match}, Records: {updated_rows})")
                        similarity_match_count += updated_rows
                        matched_names.add(db_mp_name)
            
            # Fourth pass: Electorate-based matching for remaining MPs
            electorate_match_count = 0
            
            # Get unique mp_name to electorate mappings for unmatched MPs
            cursor.execute(
                "SELECT DISTINCT mp_name, electorate FROM disclosures WHERE mp_name IN ({}) AND electorate IS NOT NULL AND electorate != ''".format(
                    ','.join(['?'] * len([n for n in db_mp_names if n not in matched_names]))
                ),
                [n for n in db_mp_names if n not in matched_names]
            )
            mp_electorates = {}
            for row in cursor.fetchall():
                if row[0] not in mp_electorates and row[1]:  # mp_name -> electorate
                    mp_electorates[row[0]] = row[1]
            
            # Use electorates to match remaining MPs
            for db_mp_name, electorate in mp_electorates.items():
                if electorate in electorate_lookup:
                    # If only one MP in this electorate in our dataset, it's likely the same person
                    if len(electorate_lookup[electorate]) == 1:
                        mp_info = electorate_lookup[electorate][0]
                        cursor.execute(
                            "UPDATE disclosures SET party = ? WHERE mp_name = ?",
                            (mp_info['party'], db_mp_name)
                        )
                        updated_rows = cursor.rowcount
                        if updated_rows > 0:
                            print(f"Electorate match: '{db_mp_name}' -> '{mp_info['name']}' (Electorate: {electorate}, Party: {mp_info['party']}, Records: {updated_rows})")
                            electorate_match_count += updated_rows
                            matched_names.add(db_mp_name)
                    else:
                        # Multiple MPs from the same electorate, try to find the closest name match
                        best_match = None
                        best_score = 0.5  # Lower threshold because we already have electorate match
                        best_name = None
                        
                        for mp_info in electorate_lookup[electorate]:
                            score = name_similarity_score(db_mp_name, mp_info['name'])
                            if score > best_score:
                                best_score = score
                                best_match = mp_info['party']
                                best_name = mp_info['name']
                        
                        if best_match:
                            cursor.execute(
                                "UPDATE disclosures SET party = ? WHERE mp_name = ?",
                                (best_match, db_mp_name)
                            )
                            updated_rows = cursor.rowcount
                            if updated_rows > 0:
                                print(f"Electorate+name match ({best_score:.2f}): '{db_mp_name}' -> '{best_name}' (Electorate: {electorate}, Party: {best_match}, Records: {updated_rows})")
                                electorate_match_count += updated_rows
                                matched_names.add(db_mp_name)
            
            # Fifth pass: Fallback to manually curated MP data for remaining MPs
            fallback_match_count = 0
            
            for db_mp_name in db_mp_names:
                # Skip MPs already matched
                if db_mp_name in matched_names:
                    continue
                
                # Check if we have a fallback entry for this MP
                if db_mp_name in FALLBACK_MP_PARTIES:
                    party = FALLBACK_MP_PARTIES[db_mp_name]
                    if party != "Unknown":  # Only update if we have actual party information
                        cursor.execute(
                            "UPDATE disclosures SET party = ? WHERE mp_name = ?",
                            (party, db_mp_name)
                        )
                        updated_rows = cursor.rowcount
                        if updated_rows > 0:
                            print(f"Fallback match: '{db_mp_name}' (Party: {party}, Records: {updated_rows})")
                            fallback_match_count += updated_rows
                            matched_names.add(db_mp_name)
            
            conn.commit()
            print(f"Updated party information for {fallback_match_count} additional records with fallback data")
            print(f"Total records updated: {exact_match_count + normalized_match_count + similarity_match_count + electorate_match_count + fallback_match_count}")
            
        except Exception as e:
            print(f"Error updating database: {e}")
            traceback.print_exc()
        finally:
            if 'conn' in locals():
                conn.close()

def main() -> None:
    """
    Main function to scrape MP data, save to CSV, and update database.
    """
    output_dir = "output"
    output_file = "all_mps_most_recent_party.csv"
    output_path = os.path.join(output_dir, output_file)
    db_path = os.path.join(project_root, "disclosures.db")
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print("Starting MP data scraping...")
    mp_data = get_mp_data()
    
    # Add timestamp column
    mp_data['scraped_date'] = pd.Timestamp.now().strftime('%Y-%m-%d')
    
    # Clean party names by removing footnote annotations
    mp_data['Party'] = mp_data['Party'].apply(clean_party_footnotes)
    
    # Save to CSV
    mp_data.to_csv(output_path, index=False)
    
    print(f"✅ Done! Saved {len(mp_data)} MP records to '{output_path}'")
    print(f"Party distribution: \n{mp_data['Party'].value_counts()}")
    
    # Update database if it exists
    if os.path.exists(db_path):
        print(f"Updating database at {db_path}")
        update_database(mp_data, db_path)
    else:
        print(f"Database not found at {db_path}")

if __name__ == "__main__":
    main() 