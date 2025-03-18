#!/usr/bin/env python3
import os
import argparse
import logging
import json
import subprocess
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from gemini_pdf_processor import GeminiPDFProcessor
from db_handler import DatabaseHandler
from parliament_urls import PARLIAMENT_URLS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')

def scrape_parliament_pdfs(parliament: Optional[str] = None, all_parliaments: bool = False) -> None:
    """
    Scrape parliamentary disclosure PDFs.
    
    Args:
        parliament: Specific parliament to scrape (e.g., '47th')
        all_parliaments: Whether to scrape all parliaments
    """
    logger.info("Starting PDF scraping process")
    
    # Build command
    cmd = ["python", "scrape_parliament.py"]
    
    if parliament:
        cmd.extend(["--parliament", parliament])
    elif all_parliaments:
        cmd.append("--all")
    
    # Run the scraper
    logger.info(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        logger.info("PDF scraping completed successfully")
        logger.info(result.stdout)
    else:
        logger.error(f"PDF scraping failed with exit code {result.returncode}")
        logger.error(result.stderr)
        raise Exception("PDF scraping failed")

def process_pdfs(
    parliament: Optional[str] = None,
    all_parliaments: bool = False,
    output_dir: str = "outputs",
    store_in_db: bool = False,
    db_path: str = "disclosures.db",
    limit: Optional[int] = None,
    skip_post_processing: bool = False,
    requests_per_minute: int = 15,
    requests_per_day: int = 1500,
    continue_on_error: bool = False
) -> Dict[str, Any]:
    """
    Process parliamentary disclosure PDFs with Gemini.
    
    Args:
        parliament: Specific parliament to process (e.g., '47th')
        all_parliaments: Whether to process all parliaments
        output_dir: Directory to save the structured data as JSON
        store_in_db: Whether to store the structured data in the database
        db_path: Path to the SQLite database file
        limit: Maximum number of PDFs to process per parliament
        skip_post_processing: Whether to skip post-processing of extracted data
        requests_per_minute: Maximum number of API requests per minute
        requests_per_day: Maximum number of API requests per day
        continue_on_error: Whether to continue processing if an error occurs
        
    Returns:
        Dictionary with processing statistics
    """
    logger.info("Starting PDF processing with Gemini")
    
    # Initialize the Gemini PDF processor with custom rate limits
    gemini_processor = GeminiPDFProcessor(apply_post_processing=not skip_post_processing)
    gemini_processor.rate_limiter.requests_per_minute = requests_per_minute
    gemini_processor.rate_limiter.requests_per_day = requests_per_day
    
    # Initialize database handler if needed
    db_handler = None
    if store_in_db:
        db_handler = DatabaseHandler(db_path=db_path)
        # Create a backup of the database before making changes
        backup_path = f"{db_path}.backup"
        logger.info(f"Creating database backup at {backup_path}")
        db_handler.create_backup(backup_path)
    
    # Determine which parliaments to process
    parliaments_to_process = []
    
    if parliament:
        if parliament in PARLIAMENT_URLS:
            parliaments_to_process = [parliament]
        else:
            logger.error(f"Parliament {parliament} not found in configuration")
            return {"error": f"Parliament {parliament} not found"}
    elif all_parliaments:
        parliaments_to_process = list(PARLIAMENT_URLS.keys())
    else:
        # Default to the latest parliament (47th)
        parliaments_to_process = ["47th"]
    
    # Sort parliaments chronologically
    parliaments_to_process.sort(key=lambda p: int(p.replace("th", "").replace("rd", "").replace("nd", "").replace("st", "")))
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each parliament
    stats = {
        "total_processed": 0,
        "total_success": 0,
        "total_failed": 0,
        "total_rate_limited": 0,
        "parliaments": {}
    }
    
    for parliament_id in parliaments_to_process:
        logger.info(f"Processing {parliament_id} parliament")
        
        # Determine PDF directory
        pdf_dir = os.path.join("pdfs", parliament_id.lower().replace("th", "").replace("rd", "").replace("nd", "").replace("st", ""))
        
        if not os.path.exists(pdf_dir):
            logger.warning(f"PDF directory not found: {pdf_dir}")
            stats["parliaments"][parliament_id] = {"error": "PDF directory not found"}
            continue
        
        # Process PDFs
        try:
            # Create parliament output directory
            parliament_output_dir = os.path.join(output_dir, parliament_id.lower().replace("th", "").replace("rd", "").replace("nd", "").replace("st", ""))
            os.makedirs(parliament_output_dir, exist_ok=True)
            
            # Process PDFs with rate limiting
            results = gemini_processor.batch_process_pdfs(pdf_dir, limit=limit)
            
            # Count successes, failures, and rate limits
            success_count = sum(1 for r in results if "error" not in r)
            failed_count = sum(1 for r in results if "error" in r and not str(r.get("error", "")).startswith("Rate limit error"))
            rate_limited_count = sum(1 for r in results if "error" in r and str(r.get("error", "")).startswith("Rate limit error"))
            
            # Update stats
            stats["total_processed"] += len(results)
            stats["total_success"] += success_count
            stats["total_failed"] += failed_count
            stats["total_rate_limited"] += rate_limited_count
            stats["parliaments"][parliament_id] = {
                "processed": len(results),
                "success": success_count,
                "failed": failed_count,
                "rate_limited": rate_limited_count
            }
            
            # Store in database if requested
            if db_handler:
                success_stored = 0
                for result in results:
                    if "error" not in result:
                        try:
                            disclosure_ids = db_handler.store_structured_data(result)
                            logger.info(f"Stored structured data in database with IDs: {disclosure_ids}")
                            success_stored += 1
                        except Exception as e:
                            logger.error(f"Error storing structured data in database: {str(e)}")
                
                logger.info(f"Successfully stored {success_stored} out of {success_count} documents in database")
                stats["parliaments"][parliament_id]["stored_in_db"] = success_stored
            
            # Save the structured data to files
            for result in results:
                try:
                    if "error" not in result:
                        # Get PDF filename
                        pdf_path = result.get("pdf_path", "")
                        pdf_filename = os.path.basename(pdf_path)
                        
                        # Create output filename
                        output_filename = f"{os.path.splitext(pdf_filename)[0]}_gemini.json"
                        output_path = os.path.join(parliament_output_dir, output_filename)
                        
                        # Save to file
                        with open(output_path, "w") as f:
                            json.dump(result, f, indent=2)
                        
                        logger.info(f"Saved structured data to: {output_path}")
                except Exception as e:
                    logger.error(f"Error saving structured data to file: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error processing {parliament_id} parliament: {str(e)}")
            stats["parliaments"][parliament_id] = {"error": str(e)}
            
            if not continue_on_error:
                logger.error("Stopping processing due to error. Use --continue-on-error to ignore errors.")
                break
    
    # Save overall stats to file
    stats_path = os.path.join(output_dir, "processing_stats.json")
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    
    logger.info("PDF processing complete")
    logger.info(f"Total processed: {stats['total_processed']}")
    logger.info(f"Total success: {stats['total_success']}")
    logger.info(f"Total failed: {stats['total_failed']}")
    logger.info(f"Total rate limited: {stats['total_rate_limited']}")
    logger.info(f"Full statistics saved to: {stats_path}")
    
    return stats

def main():
    """
    Main function to orchestrate the parliamentary disclosure processing pipeline.
    """
    parser = argparse.ArgumentParser(description="Process parliamentary disclosure PDFs")
    parser.add_argument("--parliament", help="Specific parliament to process (e.g., '47th')")
    parser.add_argument("--all", action="store_true", help="Process all parliaments")
    parser.add_argument("--output-dir", default="outputs", help="Directory to save structured data as JSON")
    parser.add_argument("--store-in-db", action="store_true", help="Store structured data in the database")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to SQLite database file")
    parser.add_argument("--limit", type=int, help="Maximum number of PDFs to process per parliament")
    parser.add_argument("--skip-scraping", action="store_true", help="Skip the PDF scraping step")
    parser.add_argument("--skip-post-processing", action="store_true", help="Skip post-processing of extracted data")
    parser.add_argument("--rpm", type=int, default=15, help="Requests per minute rate limit (default: 15)")
    parser.add_argument("--rpd", type=int, default=1500, help="Requests per day rate limit (default: 1500)")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue processing if an error occurs")
    
    args = parser.parse_args()
    
    try:
        # Step 1: Scrape PDFs (if not skipped)
        if not args.skip_scraping:
            scrape_parliament_pdfs(args.parliament, args.all)
        else:
            logger.info("Skipping PDF scraping step")
        
        # Step 2: Process PDFs with Gemini
        process_pdfs(
            parliament=args.parliament,
            all_parliaments=args.all,
            output_dir=args.output_dir,
            store_in_db=args.store_in_db,
            db_path=args.db_path,
            limit=args.limit,
            skip_post_processing=args.skip_post_processing,
            requests_per_minute=args.rpm,
            requests_per_day=args.rpd,
            continue_on_error=args.continue_on_error
        )
        
        logger.info("Parliamentary disclosure processing pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Error in parliamentary disclosure processing pipeline: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 