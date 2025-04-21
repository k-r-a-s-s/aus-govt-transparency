#!/usr/bin/env python3
"""
Main entry point for parsing Australian parliamentary disclosure PDFs using direct Gemini PDF processing (no OCR step).

This script orchestrates batch and single PDF processing, extracting structured data from PDFs using Gemini, and saving results to a database or JSON files. It is designed to work with the new modular pipeline and database schema (see refactor_plan.rmd and README.md).

Typical usage:
    python parse_disclosures.py --pdf-dir path/to/pdfs --db-path disclosures.db

Dependencies:
    - pdf_gemini_pipeline.py: Handles Gemini API calls for structured extraction
    - src/preparation/db_handler.py: Handles database operations
"""
import os
import argparse
import logging
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from dotenv import load_dotenv
from pdf_gemini_pipeline import GeminiPDFProcessor, get_pdf_page_count, split_pdf_by_page_ranges
from src.preparation.db_handler import DatabaseHandler
from src.parsing.pdf_gemini_pipeline import PDFSplitError

# Configure logging with both file and console handlers
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("process_disclosures.log", mode='w'),  # 'w' mode to start fresh
        logging.StreamHandler()  # This will output to console
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('.env.local')
api_key = os.getenv('GOOGLE_API_KEY')
logger.info(f"API Key present: {bool(api_key)}")

def process_single_pdf(
    pdf_path: str,
    gemini_processor: GeminiPDFProcessor,
    db_handler: Optional[DatabaseHandler] = None,
    output_dir: Optional[str] = None,
    pdf_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a single PDF file and extract structured data using Gemini.
    Args:
        pdf_path: Path to the PDF file.
        gemini_processor: GeminiPDFProcessor instance.
        db_handler: Database handler instance. If provided, will store the structured data.
        output_dir: Directory to save the structured data as JSON. If None, will not save.
        pdf_dir: Root PDF directory, used to mirror subfolder structure in output.
    Returns:
        A dictionary containing the structured data extracted from the PDF.
    """
    logger.info(f"Processing PDF: {pdf_path}")
    try:
        # Step 1: Process PDF with Gemini
        logger.debug("Starting Gemini processing...")
        structured_data = gemini_processor.process_pdf(pdf_path)
        logger.debug(f"Gemini processing complete. Data received: {bool(structured_data)}")
        if structured_data:
            logger.debug(f"Data structure: {json.dumps(structured_data, indent=2)}")

        # Step 2: Save structured data as JSON if output directory provided (always do this, even if DB fails)
        if output_dir and structured_data:
            # Compute relative path from pdf_dir to pdf_path
            rel_path = os.path.relpath(pdf_path, start=pdf_dir) if pdf_dir else os.path.basename(pdf_path)
            rel_dir = os.path.dirname(rel_path)
            out_dir = os.path.join(output_dir, rel_dir)
            os.makedirs(out_dir, exist_ok=True)
            filename = os.path.splitext(os.path.basename(pdf_path))[0] + '.json'
            output_path = os.path.join(out_dir, filename)
            with open(output_path, "w") as f:
                json.dump(structured_data, f, indent=2)
            logger.info(f"Saved structured data to: {output_path}")

        # Step 3: Store structured data in database if handler provided
        if db_handler and structured_data:
            try:
                logger.debug("Storing data in database...")
                disclosure_ids = db_handler.store_structured_data(structured_data)
                structured_data["disclosure_ids"] = disclosure_ids
                logger.debug(f"Stored {len(disclosure_ids)} disclosures in database")
            except Exception as e:
                logger.error(f"DB error for {pdf_path}: {e}", exc_info=True)

        return structured_data
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {str(e)}", exc_info=True)  # Added exc_info for stack trace
        return {
            "error": str(e),
            "pdf_path": pdf_path
        }

def process_pdf_adaptive_split(
    pdf_path: str,
    gemini_processor: GeminiPDFProcessor,
    db_handler: Optional[DatabaseHandler] = None,
    output_dir: Optional[str] = None,
    min_chunk_size: int = 1,
    max_chunk_size: int = 20,
    pdf_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a PDF using adaptive page-based splitting and Gemini feedback loop.
    Only split if Gemini response is truncated due to token/output length, not for schema mismatches.
    """
    logger.info(f"Adaptive split processing for PDF: {pdf_path}")
    total_pages = get_pdf_page_count(pdf_path)
    logger.info(f"PDF has {total_pages} pages")

    def is_truncation_issue(finish_reason: Optional[str]) -> bool:
        # Gemini uses 'MAX_TOKENS', 'LENGTH', or similar for truncation
        return finish_reason is not None and finish_reason.upper() in ('MAX_TOKENS', 'LENGTH', 'OUTPUT_LIMIT')

    def process_chunk(chunk_bytes: bytes, chunk_range: range) -> Optional[Dict[str, Any]]:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as tmp:
            tmp.write(chunk_bytes)
            tmp.flush()
            # Set current chunk range for raw response naming
            gemini_processor.current_chunk_range = chunk_range
            try:
                logger.info(f"\n{'='*40}\nProcessing chunk: pages {chunk_range.start+1}-{chunk_range.stop}")
                result = gemini_processor.process_pdf(tmp.name)
                finish_reason = getattr(gemini_processor, 'last_finish_reason', None)
                usage_metadata = getattr(gemini_processor, 'last_usage_metadata', None)
                logger.info(f"Chunk finish_reason: {finish_reason}")
                logger.info(f"Chunk usage_metadata: {usage_metadata}\n{'='*40}")
                return {'result': result, 'finish_reason': finish_reason}
            except Exception as e:
                logger.error(f"Error processing chunk {chunk_range}: {e}")
                return None
            finally:
                gemini_processor.current_chunk_range = None

    def recursive_split(start: int, end: int) -> List[Dict[str, Any]]:
        if end - start <= 0:
            return []
        chunk_range = range(start, end)
        try:
            chunk_bytes = split_pdf_by_page_ranges(pdf_path, [chunk_range])[0]
        except PDFSplitError as e:
            logger.error(f"PDF splitting failed for chunk {chunk_range}: {e}")
            return [{
                'error': str(e),
                'pdf_path': pdf_path,
                'page_range': (start, end),
                'type': 'pdf_split_error'
            }]
        chunk_result = process_chunk(chunk_bytes, chunk_range)
        if not chunk_result or not chunk_result['result'] or not chunk_result['result'].get('disclosures'):
            logger.warning(f"Chunk {chunk_range} returned empty or invalid result. Treating as truncation/failure and splitting further.")
            if end - start <= min_chunk_size:
                logger.warning(f"Chunk {chunk_range} could not be processed cleanly, returning as-is (empty result at min chunk size).")
                return [chunk_result['result']] if chunk_result and chunk_result['result'] else []
            mid = (start + end) // 2
            logger.info(f"Splitting chunk {chunk_range} into {start}-{mid} and {mid}-{end} due to empty/truncated result.")
            return recursive_split(start, mid) + recursive_split(mid, end)
        result = chunk_result['result']
        finish_reason = chunk_result['finish_reason']
        if not is_truncation_issue(finish_reason):
            return [result]
        if end - start <= min_chunk_size:
            logger.warning(f"Chunk {chunk_range} could not be processed cleanly, returning as-is (finish_reason: {finish_reason}).")
            return [result] if result else []
        mid = (start + end) // 2
        logger.info(f"Splitting chunk {chunk_range} into {start}-{mid} and {mid}-{end} due to truncation (finish_reason: {finish_reason}).")
        return recursive_split(start, mid) + recursive_split(mid, end)

    results: List[Dict[str, Any]] = []
    if total_pages < max_chunk_size:
        logger.info("Trying one-shot extraction for small PDF")
        result = gemini_processor.process_pdf(pdf_path)
        finish_reason = getattr(gemini_processor, 'last_finish_reason', None)
        usage_metadata = getattr(gemini_processor, 'last_usage_metadata', None)
        logger.info(f"\n{'='*40}\nOne-shot finish_reason: {finish_reason}")
        logger.info(f"One-shot usage_metadata: {usage_metadata}\n{'='*40}")
        if not is_truncation_issue(finish_reason):
            results = [result]
        else:
            logger.warning("One-shot extraction truncated, splitting PDF")
            results = recursive_split(0, total_pages)
    else:
        logger.info(f"Splitting PDF into {max_chunk_size}-page chunks")
        page_ranges = [range(i, min(i+max_chunk_size, total_pages)) for i in range(0, total_pages, max_chunk_size)]
        for chunk_range in page_ranges:
            chunk_results = recursive_split(chunk_range.start, chunk_range.stop)
            results.extend(chunk_results)

    # Merge and deduplicate disclosures as before
    all_disclosures: List[Dict[str, Any]] = []
    seen: Set[Tuple] = set()
    meta = None
    for res in results:
        if not res or 'disclosures' not in res:
            continue
        if not meta:
            meta = {k: v for k, v in res.items() if k != 'disclosures'}
        for d in res['disclosures']:
            key = tuple(sorted((k, str(d.get(k))) for k in d.keys()))
            if key not in seen:
                seen.add(key)
                all_disclosures.append(d)
    merged = meta or {}
    merged['disclosures'] = all_disclosures
    merged['pdf_filename'] = os.path.basename(pdf_path)

    if output_dir:
        # Compute relative path from pdf_dir to pdf_path
        rel_path = os.path.relpath(pdf_path, start=pdf_dir) if pdf_dir else os.path.basename(pdf_path)
        rel_dir = os.path.dirname(rel_path)
        out_dir = os.path.join(output_dir, rel_dir)
        os.makedirs(out_dir, exist_ok=True)
        filename = os.path.splitext(os.path.basename(pdf_path))[0] + '.json'
        output_path = os.path.join(out_dir, filename)
        with open(output_path, "w") as f:
            json.dump(merged, f, indent=2)
        logger.info(f"Saved structured data to: {output_path}")
    if db_handler:
        try:
            db_handler.store_structured_data(merged)
        except Exception as e:
            logger.error(f"DB error for {pdf_path}: {e}", exc_info=True)
    return merged

def process_batch_pdfs(
    pdf_dir: str,
    gemini_processor: GeminiPDFProcessor,
    db_handler: Optional[DatabaseHandler] = None,
    output_dir: Optional[str] = None,
    limit: Optional[int] = None,
    adaptive_split: bool = False
) -> List[Dict[str, Any]]:
    """
    Process multiple PDFs in a directory using either adaptive split or legacy logic.
    Args:
        pdf_dir: Directory containing PDF files.
        gemini_processor: GeminiPDFProcessor instance.
        db_handler: Optional database handler.
        output_dir: Optional output directory for JSON.
        limit: Optional max number of PDFs to process.
        adaptive_split: Whether to use adaptive page-based splitting.
    Returns:
        List of structured data dicts for each PDF.
    """
    logger.info(f"Batch processing PDFs from: {pdf_dir} (adaptive_split={adaptive_split})")
    # Recursively find all PDFs in pdf_dir and subfolders
    pdf_files = []
    for root, _, files in os.walk(pdf_dir):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    pdf_files.sort()
    if limit is not None and limit > 0:
        pdf_files = pdf_files[:limit]
    results = []
    for pdf_path in pdf_files:
        try:
            if adaptive_split:
                result = process_pdf_adaptive_split(
                    pdf_path=pdf_path,
                    gemini_processor=gemini_processor,
                    db_handler=db_handler,
                    output_dir=output_dir,
                    pdf_dir=pdf_dir
                )
            else:
                result = process_single_pdf(
                    pdf_path=pdf_path,
                    gemini_processor=gemini_processor,
                    db_handler=db_handler,
                    output_dir=output_dir,
                    pdf_dir=pdf_dir
                )
            results.append(result)
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {e}")
            results.append({"error": str(e), "pdf_path": pdf_path})
    return results

def main():
    """
    Main function to process parliamentary disclosure PDFs using Gemini direct PDF processing.
    """
    parser = argparse.ArgumentParser(description="Process parliamentary disclosure PDFs with Gemini")
    parser.add_argument("--pdf", help="Path to a single PDF file to process")
    parser.add_argument("--pdf-dir", help="Directory containing PDF files to process")
    parser.add_argument("--output-dir", help="Directory to save structured data as JSON")
    parser.add_argument("--db-path", default="disclosures.db", help="Path to SQLite database file")
    parser.add_argument("--limit", type=int, help="Maximum number of PDFs to process")
    parser.add_argument("--skip-db", action="store_true", help="Skip storing data in database")
    parser.add_argument("--export-json", help="Export all database data to a JSON file")
    parser.add_argument("--save-raw-responses", action="store_true", help="Save raw Gemini responses for debugging")
    parser.add_argument("--adaptive-split", action="store_true", help="Use adaptive page-based PDF splitting (recommended for large PDFs)")
    args = parser.parse_args()

    # Always use absolute path for db_path
    db_path = os.path.abspath(args.db_path)
    logger.info(f"Using database at: {db_path}")
    gemini_processor = GeminiPDFProcessor(save_raw_response=args.save_raw_responses)
    db_handler = None if args.skip_db else DatabaseHandler(db_path=db_path)

    # Export database to JSON if requested
    if args.export_json and db_handler:
        db_handler.export_to_json(args.export_json)
        return

    # Process single PDF
    if args.pdf:
        if args.adaptive_split:
            process_pdf_adaptive_split(
                pdf_path=args.pdf,
                gemini_processor=gemini_processor,
                db_handler=db_handler,
                output_dir=args.output_dir,
                pdf_dir=os.path.dirname(args.pdf)
            )
        else:
            process_single_pdf(
                pdf_path=args.pdf,
                gemini_processor=gemini_processor,
                db_handler=db_handler,
                output_dir=args.output_dir,
                pdf_dir=os.path.dirname(args.pdf)
            )
    # Process batch PDFs
    elif args.pdf_dir:
        process_batch_pdfs(
            pdf_dir=args.pdf_dir,
            gemini_processor=gemini_processor,
            db_handler=db_handler,
            output_dir=args.output_dir,
            limit=args.limit,
            adaptive_split=args.adaptive_split
        )
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 