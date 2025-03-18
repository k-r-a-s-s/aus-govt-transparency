#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup
import time
import argparse
from tqdm import tqdm
from typing import Dict, List, Tuple, Optional
import logging
from parliament_urls import PARLIAMENT_URLS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Base URL
BASE_URL = "https://www.aph.gov.au"
# Base output directory
BASE_OUTPUT_DIR = "pdfs"

def setup_output_directories() -> None:
    """
    Create the base output directory and subdirectories for each parliament.
    """
    # Create base directory
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    
    # Create subdirectories for each parliament
    for parliament in PARLIAMENT_URLS.keys():
        parliament_dir = os.path.join(BASE_OUTPUT_DIR, parliament.lower().replace("th", "").replace("rd", "").replace("nd", "").replace("st", ""))
        os.makedirs(parliament_dir, exist_ok=True)
        logger.info(f"Created directory: {parliament_dir}")

def extract_pdf_links(page_url: str, parliament: str) -> List[Tuple[str, str]]:
    """
    Extract PDF links from a parliament page.
    
    Args:
        page_url: URL of the parliament page
        parliament: Parliament identifier (e.g., "47th")
        
    Returns:
        List of tuples containing (pdf_url, pdf_filename)
    """
    logger.info(f"Fetching page content for {parliament} parliament: {page_url}")
    
    try:
        response = requests.get(page_url)
        response.raise_for_status()
        
        # Parse the page
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find all PDF links
        pdf_links = []
        
        # Different parliaments might have different HTML structures
        # We'll try different approaches
        
        # Look for links with .pdf extension
        for link in soup.find_all("a", href=True):
            href = link["href"].lower()
            if ".pdf" in href:
                # Extract the PDF filename
                if "/" in href:
                    pdf_filename = href.split("/")[-1]
                else:
                    pdf_filename = href
                
                # Ensure filename ends with .pdf
                if not pdf_filename.lower().endswith(".pdf"):
                    pdf_filename += ".pdf"
                
                # Construct the full URL if it's a relative path
                if href.startswith("http"):
                    pdf_url = href
                elif href.startswith("/"):
                    pdf_url = f"{BASE_URL}{href}"
                else:
                    pdf_url = f"{BASE_URL}/{href}"
                
                # Add MP identifier to filename if not present
                # Format: lastname_initial_parliament.pdf (e.g., smithj_47p.pdf)
                if "_" not in pdf_filename and parliament.lower().replace("th", "p").replace("rd", "p").replace("nd", "p").replace("st", "p") not in pdf_filename:
                    # Try to extract MP name from link text or parent elements
                    mp_name = link.get_text().strip()
                    if mp_name:
                        # Simplify name to lastname + first initial
                        name_parts = mp_name.split()
                        if len(name_parts) >= 2:
                            lastname = name_parts[-1].lower()
                            firstname_initial = name_parts[0][0].lower()
                            parliament_suffix = parliament.lower().replace("th", "p").replace("rd", "p").replace("nd", "p").replace("st", "p")
                            pdf_filename = f"{lastname}{firstname_initial}_{parliament_suffix}.pdf"
                
                pdf_links.append((pdf_url, pdf_filename))
        
        logger.info(f"Found {len(pdf_links)} PDF links for {parliament} parliament")
        return pdf_links
    
    except Exception as e:
        logger.error(f"Error fetching {parliament} parliament page: {str(e)}")
        return []

def download_pdfs(pdf_links: List[Tuple[str, str]], parliament: str) -> Dict[str, int]:
    """
    Download PDFs from the extracted links.
    
    Args:
        pdf_links: List of tuples containing (pdf_url, pdf_filename)
        parliament: Parliament identifier (e.g., "47th")
        
    Returns:
        Dictionary with download statistics
    """
    # Determine output directory
    output_dir = os.path.join(BASE_OUTPUT_DIR, parliament.lower().replace("th", "").replace("rd", "").replace("nd", "").replace("st", ""))
    
    # Initialize counters
    stats = {
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "total": len(pdf_links)
    }
    
    logger.info(f"Downloading {len(pdf_links)} PDFs for {parliament} parliament")
    
    # Download PDFs with progress bar
    for pdf_url, pdf_name in tqdm(pdf_links, desc=f"Downloading {parliament} PDFs"):
        pdf_path = os.path.join(output_dir, pdf_name)
        
        # Skip if file already exists
        if os.path.exists(pdf_path):
            stats["skipped"] += 1
            continue
        
        try:
            # Add a small delay to avoid overwhelming the server
            time.sleep(0.5)
            
            pdf_response = requests.get(pdf_url, timeout=30)
            
            # Check if the request was successful
            if pdf_response.status_code == 200:
                with open(pdf_path, "wb") as f:
                    f.write(pdf_response.content)
                stats["success"] += 1
                logger.debug(f"Downloaded: {pdf_name}")
            else:
                logger.warning(f"Failed to download {pdf_name}: HTTP {pdf_response.status_code}")
                stats["failed"] += 1
        except Exception as e:
            logger.error(f"Error downloading {pdf_name}: {str(e)}")
            stats["failed"] += 1
    
    return stats

def scrape_parliament(parliament: str) -> Dict[str, int]:
    """
    Scrape PDFs for a specific parliament.
    
    Args:
        parliament: Parliament identifier (e.g., "47th")
        
    Returns:
        Dictionary with download statistics
    """
    if parliament not in PARLIAMENT_URLS:
        logger.error(f"Parliament {parliament} not found in configuration")
        return {"error": f"Parliament {parliament} not found"}
    
    page_url = PARLIAMENT_URLS[parliament]
    pdf_links = extract_pdf_links(page_url, parliament)
    
    if not pdf_links:
        logger.warning(f"No PDF links found for {parliament} parliament")
        return {"error": "No PDF links found"}
    
    return download_pdfs(pdf_links, parliament)

def main():
    """
    Main function to scrape parliamentary disclosure PDFs.
    """
    parser = argparse.ArgumentParser(description="Scrape parliamentary disclosure PDFs")
    parser.add_argument("--parliament", help="Specific parliament to scrape (e.g., '47th')")
    parser.add_argument("--all", action="store_true", help="Scrape all parliaments")
    parser.add_argument("--limit", type=int, help="Maximum number of PDFs to download per parliament")
    
    args = parser.parse_args()
    
    # Setup output directories
    setup_output_directories()
    
    # Determine which parliaments to scrape
    parliaments_to_scrape = []
    
    if args.parliament:
        if args.parliament in PARLIAMENT_URLS:
            parliaments_to_scrape = [args.parliament]
        else:
            logger.error(f"Parliament {args.parliament} not found in configuration")
            return
    elif args.all:
        parliaments_to_scrape = list(PARLIAMENT_URLS.keys())
    else:
        # Default to the latest parliament (47th)
        parliaments_to_scrape = ["47th"]
    
    # Scrape each parliament
    overall_stats = {
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "total": 0
    }
    
    for parliament in parliaments_to_scrape:
        logger.info(f"Processing {parliament} parliament")
        page_url = PARLIAMENT_URLS[parliament]
        pdf_links = extract_pdf_links(page_url, parliament)
        
        # Apply limit if specified
        if args.limit and args.limit > 0:
            pdf_links = pdf_links[:args.limit]
            logger.info(f"Limiting to {args.limit} PDFs for {parliament} parliament")
        
        stats = download_pdfs(pdf_links, parliament)
        
        # Update overall stats
        if "error" not in stats:
            for key in overall_stats:
                if key in stats:
                    overall_stats[key] += stats[key]
            
            # Print summary for this parliament
            logger.info(f"\n{parliament} Parliament Download Summary:")
            logger.info(f"  - Successfully downloaded: {stats.get('success', 0)}")
            logger.info(f"  - Failed downloads: {stats.get('failed', 0)}")
            logger.info(f"  - Skipped (already exist): {stats.get('skipped', 0)}")
            logger.info(f"  - Total files processed: {stats.get('total', 0)}")
    
    # Print overall summary
    logger.info("\nOverall Download Summary:")
    logger.info(f"  - Successfully downloaded: {overall_stats['success']}")
    logger.info(f"  - Failed downloads: {overall_stats['failed']}")
    logger.info(f"  - Skipped (already exist): {overall_stats['skipped']}")
    logger.info(f"  - Total files processed: {overall_stats['total']}")

if __name__ == "__main__":
    main() 