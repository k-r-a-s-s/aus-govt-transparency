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
import argparse
from rapidfuzz import fuzz, process

# Add project root to path to allow importing from other modules
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Try to import from db_handler if available
try:
    from src.preparation.db_handler import DatabaseHandler
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
    "Unknown": "N/A",  # These are not actual MPs but entries that couldn't be linked to a specific person
    # Manual fixes for MPs with NULL party (from screenshot)
    "Robert Charles Baldwin": "Liberal Party of Australia",
    "Christopher Bowen": "Australian Labor Party",
    "Mark Christopher Butler": "Australian Labor Party",
    "Nicholas David Champion": "Australian Labor Party",
    "George Christensen": "Liberal National Party",
    "Anthony John Crook": "National Party of Australia",
    "John Alexander Forrest": "Liberal Party of Australia",
    "Bruce Griffin": "Liberal Party of Australia",
    "Alexander Hawke": "Liberal Party of Australia",
    "Stephen James Irons": "Liberal Party of Australia",
    "Ewan Thomas Jones": "Liberal National Party",
    "Stephen Patrick Jones": "Australian Labor Party",
    "Robert Carl Katter": "Katter's Australian Party",
    "MARKUS": "Liberal Party of Australia",
    "Judith Eleanor Moylan": "Liberal Party of Australia",
    "Bernard Ripoll": "Australian Labor Party",
    "Anthony David Hawthorn Smith": "Liberal Party of Australia",
    "Alexander Somlay": "Liberal Party of Australia",
    "Albertus Johannes Van Manen": "Liberal National Party",
    "Malcolm James Washer": "Liberal Party of Australia",
    "Andrew Damien Wilkie": "Independent",
    "Antony Harold Curties Windsor": "Independent",
    "Russell Evan Broadbent": "Liberal Party of Australia",
    "Malcolm Thomas Brough": "Liberal Party of Australia",
    "James Edward Chalmers": "Australian Labor Party",
    "Joseph Benedict Hockey": "Liberal Party of Australia",
    "Edham (Ed) Nurredin Husic": "Australian Labor Party",
    "Catherine McGowan": "Independent",
    "William Shorten": "Australian Labor Party",
    "Matthew Philip Williams": "Liberal Party of Australia",
    "Richard James Wilson": "Liberal Party of Australia",
    "Christopher Eyles Bowen": "Australian Labor Party",
    "DICK DUGALD MILTON": "Australian Labor Party",
    "Damian Kevin Drum": "National Party of Australia",
    "Katherine Margaret Ellis": "Australian Labor Party",
    "Timothy Jerome Hammond": "Australian Labor Party",
    "Gerardine (Ged) Mary Kearney": "Australian Labor Party",
    "JUSTINE TERRI KEAY": "Australian Labor Party",
    "Michael Kelly": "Australian Labor Party",
    "Charles Porter": "Liberal Party of Australia",
    "Robert Stuart Rowland": "Liberal Party of Australia",
    "Bridget Archer": "Liberal Party of Australia",
    "Jim Chalmers": "Australian Labor Party",
    "Warren Entsch": "Liberal National Party",
    "Andrew Hastie": "Liberal Party of Australia",
    "Clare O' Neil": "Australian Labor Party",
    "Alexander Somlyay": "Liberal Party of Australia",
    "Fiona Martin": "Liberal Party of Australia",
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
            name_candidates = [c for c in df.columns if any(term in c.lower() for term in ["member", "name", "mp"])]
            name_col = None
            # Try each candidate until we find one with non-empty values
            for candidate in name_candidates:
                if df[candidate].dropna().astype(str).str.strip().replace('', pd.NA).dropna().shape[0] > 0:
                    name_col = candidate
                    break
            
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
    Update the database with MP party information (mps table only).
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
                'party': row['Party'],
                'electorate': row.get('Electorate')
            }
        # Store name parts for similarity matching
        name_parts = get_name_parts(row['Name'])
        if name_parts[0] and name_parts[2]:  # Has first and last name
            similarity_lookups[row['Name']] = {
                'parts': name_parts,
                'party': row['Party'],
                'electorate': row.get('Electorate')
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
            # Get existing MPs from mps table
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT full_name, electorate FROM mps")
            existing_mps = [dict(row) for row in cursor.fetchall()]
            conn.close()
            # First pass: Exact matches (full_name + electorate)
            exact_match_count = 0
            matched_keys = set()
            for mp in existing_mps:
                key = (mp['full_name'], mp['electorate'])
                match = mp_data[(mp_data['Name'] == mp['full_name']) & (mp_data['Electorate'] == mp['electorate'])]
                if not match.empty:
                    party = match.iloc[0]['Party']
                    db.update_mps_party(mp['full_name'], party, mp['electorate'])
                    matched_keys.add(key)
                    exact_match_count += 1
            print(f"Updated party information for {exact_match_count} MPs with exact name+electorate matches in mps table")
            # Second pass: Normalized name matching (for unmatched)
            normalized_match_count = 0
            for mp in existing_mps:
                key = (mp['full_name'], mp['electorate'])
                if key in matched_keys:
                    continue
                # Special cases
                if mp['full_name'] in MP_NAME_SPECIAL_CASES:
                    wiki_name = MP_NAME_SPECIAL_CASES[mp['full_name']]
                    match = mp_data[(mp_data['Name'] == wiki_name) & (mp_data['Electorate'] == mp['electorate'])]
                    if not match.empty:
                        party = match.iloc[0]['Party']
                        db.update_mps_party(mp['full_name'], party, mp['electorate'])
                        matched_keys.add(key)
                        print(f"Special case match: '{mp['full_name']}' -> '{wiki_name}' (Party: {party})")
                        normalized_match_count += 1
                        continue
                # Normalized name
                norm_name = normalize_mp_name(mp['full_name'])
                if norm_name in normalized_lookup:
                    info = normalized_lookup[norm_name]
                    if info['electorate'] == mp['electorate']:
                        db.update_mps_party(mp['full_name'], info['party'], mp['electorate'])
                        matched_keys.add(key)
                        print(f"Normalized match: '{mp['full_name']}' -> '{info['original_name']}' (Party: {info['party']})")
                    normalized_match_count += 1
            print(f"Updated party information for {normalized_match_count} additional MPs with normalized name matching in mps table")
            # Third pass: Similarity-based matching for remaining MPs
            similarity_match_count = 0
            for mp in existing_mps:
                key = (mp['full_name'], mp['electorate'])
                if key in matched_keys:
                    continue
                best_match = None
                best_score = 0.7
                best_name = None
                for wiki_name, info in similarity_lookups.items():
                    if info['electorate'] != mp['electorate']:
                        continue
                    score = name_similarity_score(mp['full_name'], wiki_name)
                    if score > best_score:
                        best_score = score
                        best_match = info['party']
                        best_name = wiki_name
                if best_match:
                    db.update_mps_party(mp['full_name'], best_match, mp['electorate'])
                    matched_keys.add(key)
                    print(f"Similarity match ({best_score:.2f}): '{mp['full_name']}' -> '{best_name}' (Party: {best_match})")
                    similarity_match_count += 1
            print(f"Updated party information for {similarity_match_count} additional MPs with similarity matching in mps table")
            # Fourth pass: Fallback to manually curated MP data for remaining MPs
            fallback_match_count = 0
            for mp in existing_mps:
                key = (mp['full_name'], mp['electorate'])
                if key in matched_keys:
                    continue
                if mp['full_name'] in FALLBACK_MP_PARTIES:
                    party = FALLBACK_MP_PARTIES[mp['full_name']]
                    if party != "Unknown":
                        db.update_mps_party(mp['full_name'], party, mp['electorate'])
                        matched_keys.add(key)
                        print(f"Fallback match: '{mp['full_name']}' (Party: {party})")
                        fallback_match_count += 1
            print(f"Updated party information for {fallback_match_count} additional MPs with fallback data in mps table")
            print(f"Total MPs updated in mps table: {exact_match_count + normalized_match_count + similarity_match_count + fallback_match_count}")
            # --- Second fuzzy pass for NULL party MPs ---
            print("Starting fuzzy matching for MPs with NULL party...")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT full_name, electorate FROM mps WHERE party IS NULL OR party = ''")
            null_party_mps = [dict(row) for row in cursor.fetchall()]
            for mp in null_party_mps:
                mp_name = mp['full_name']
                mp_electorate = mp['electorate']
                # Find all Wikipedia MPs in the same electorate
                wiki_rows = mp_data[mp_data['Electorate'] == mp_electorate]
                if wiki_rows.empty:
                    continue
                # Fuzzy match on name within this electorate
                candidates = wiki_rows['Name'].tolist()
                if not candidates:
                    continue
                # Use rapidfuzz to get best match
                best_match, score, _ = process.extractOne(mp_name, candidates, scorer=fuzz.token_sort_ratio)
                if score >= 85:
                    party = wiki_rows[wiki_rows['Name'] == best_match]['Party'].iloc[0]
                    db.update_mps_party(mp_name, party, mp_electorate)
                    print(f"Fuzzy match ({score}): '{mp_name}' ~ '{best_match}' (Electorate: {mp_electorate}) -> {party}")
            conn.close()
        except Exception as e:
            print(f"Error updating database: {e}")
            traceback.print_exc()
    else:
        print("DatabaseHandler not available. Cannot update mps table.")

def main() -> None:
    """
    Main function to scrape MP data, save to CSV, and update database.
    """
    parser = argparse.ArgumentParser(description="Scrape MP party affiliations and update the mps table.")
    parser.add_argument('--db-path', default=None, help='Path to the SQLite database (default: disclosures.db in project root)')
    parser.add_argument('--output-path', default=None, help='Path to output CSV (default: output/all_mps_most_recent_party.csv)')
    args = parser.parse_args()

    # Determine project root (repo root, not src/cleaning)
    project_root = Path(__file__).resolve().parent.parent.parent
    output_dir = "output"
    output_file = "all_mps_most_recent_party.csv"
    default_output_path = os.path.join(output_dir, output_file)
    default_db_path = os.path.join(project_root, "disclosures.db")
    output_path = args.output_path if args.output_path else default_output_path
    db_path = args.db_path if args.db_path else default_db_path
    
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