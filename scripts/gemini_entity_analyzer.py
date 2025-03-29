#!/usr/bin/env python
"""
Gemini Entity Analyzer

This script uses Google's Gemini Flash 2.0 to analyze potential double disclosure entities.
It processes batches prepared by the prepare_gemini_entity_analysis.py script and classifies
entities as single or multiple based on context and Australian naming conventions.

Usage:
    python gemini_entity_analyzer.py [--input_dir DIR] [--output_dir DIR] [--batch_id BATCH_ID]
"""

import os
import sys
import json
import argparse
import logging
import time
from typing import List, Dict, Any
import google.generativeai as genai

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GeminiEntityAnalyzer:
    """
    Uses Gemini to analyze and classify potential double disclosure entities.
    """
    
    def __init__(
        self,
        input_dir: str = "scripts/gemini_analysis",
        output_dir: str = "scripts/gemini_results",
        api_key: str = None,
        api_key_file: str = None,
        model_name: str = "gemini-flash-2.0",
        max_retries: int = 3,
        delay_between_retries: float = 2.0
    ):
        """
        Initialize the analyzer.
        
        Args:
            input_dir: Directory containing batch files prepared for Gemini
            output_dir: Directory for saving analysis results
            api_key: Google AI API key (if None, will look for GOOGLE_API_KEY env var)
            api_key_file: Path to file containing the API key
            model_name: Gemini model to use
            max_retries: Maximum number of retries for API calls
            delay_between_retries: Delay between retries in seconds
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.model_name = model_name
        self.max_retries = max_retries
        self.delay_between_retries = delay_between_retries
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize Gemini API - handle API key from various sources with priority:
        # 1. Direct api_key parameter
        # 2. API key file
        # 3. GOOGLE_API_KEY environment variable
        if api_key:
            self.api_key = api_key
        elif api_key_file and os.path.exists(api_key_file):
            with open(api_key_file, 'r') as f:
                self.api_key = f.read().strip()
        else:
            self.api_key = os.environ.get("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError("API key must be provided via --api-key parameter, --api-key-file, or GOOGLE_API_KEY environment variable")
        
        genai.configure(api_key=self.api_key)
        
        # Load prompt template
        self.prompt_template_file = os.path.join(input_dir, "prompt_template.json")
        if not os.path.exists(self.prompt_template_file):
            raise FileNotFoundError(f"Prompt template file not found: {self.prompt_template_file}")
        
        with open(self.prompt_template_file, 'r') as f:
            self.prompt_template = json.load(f)
        
        # Set up Gemini model
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.prompt_template["system_prompt"],
            safety_settings=[
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        )
    
    def format_entity_prompt(self, batch: Dict[str, Any]) -> str:
        """
        Format a batch of entities into a prompt for Gemini.
        
        Args:
            batch: Batch of entities to analyze
            
        Returns:
            str: Formatted prompt text
        """
        entity_list = []
        
        for i, entity_data in enumerate(batch["entities"], 1):
            # Ensure entity is a string
            entity = str(entity_data.get("entity", ""))
            
            # Get proposed splits and ensure they're all strings
            proposed_splits = []
            for split in entity_data.get("proposed_splits", []):
                if split is not None:  # Skip None values
                    proposed_splits.append(str(split))
            
            # Get contexts and ensure all values are properly handled
            contexts = entity_data.get("context", [])
            
            entity_info = f"{i}. \"{entity}\"\n"
            
            # Add proposed splits if available
            if proposed_splits:
                entity_info += f"   Proposed splits: {' | '.join(proposed_splits)}\n"
            
            # Add context examples if available
            if contexts:
                entity_info += "   Context examples:\n"
                for j, context in enumerate(contexts, 1):
                    # Convert all values to strings and handle None values
                    details = str(context.get("details", "")) if context.get("details") is not None else ""
                    item = str(context.get("item", "")) if context.get("item") is not None else ""
                    category = str(context.get("category", "")) if context.get("category") is not None else ""
                    sub_category = str(context.get("sub_category", "")) if context.get("sub_category") is not None else ""
                    
                    # Strip whitespace from string values
                    details = details.strip()
                    item = item.strip()
                    category = category.strip()
                    sub_category = sub_category.strip()
                    
                    context_str = f"     Example {j}: "
                    if category:
                        context_str += f"Category: {category}"
                        if sub_category:
                            context_str += f", Sub-category: {sub_category}. "
                        else:
                            context_str += ". "
                    
                    if item:
                        context_str += f"Item: {item}. "
                    
                    if details:
                        context_str += f"Details: {details}"
                    
                    entity_info += context_str + "\n"
            
            entity_list.append(entity_info)
        
        # Format the prompt using the template, but escape any curly braces in the entity list
        entities_text = "\n".join(entity_list)
        
        # Get the template and replace the {entity_list} placeholder
        template = self.prompt_template["user_prompt_template"]
        
        # Special handling to avoid issues with curly braces in the entity list
        # We'll manually replace the placeholder instead of using .format()
        if "{entity_list}" in template:
            prompt = template.replace("{entity_list}", entities_text)
        else:
            # Fallback if placeholder not found
            prompt = template + "\n\n" + entities_text
        
        return prompt
    
    def analyze_batch(self, batch_file: str) -> Dict[str, Any]:
        """
        Analyze a batch of entities using Gemini.
        
        Args:
            batch_file: Path to the batch file to process
            
        Returns:
            Dict[str, Any]: Analysis results for the batch
        """
        try:
            # Load batch data
            with open(batch_file, 'r') as f:
                batch_data = f.read()
                try:
                    batch = json.loads(batch_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing batch file {batch_file}: {e}")
                    logger.debug(f"First 100 characters of batch file: {batch_data[:100]}")
                    raise
            
            batch_id = batch.get("batch_id", os.path.basename(batch_file).replace("batch_", "").replace(".json", ""))
            num_entities = len(batch.get("entities", []))
            logger.info(f"Analyzing batch {batch_id} with {num_entities} entities")
            
            if "entities" not in batch or not batch["entities"]:
                logger.warning(f"No entities found in batch {batch_id}")
                return {
                    "batch_id": batch_id,
                    "error": "No entities found in batch",
                    "entities_count": 0,
                    "analysis_results": [],
                    "raw_response": ""
                }
            
            # Format the prompt for Gemini
            prompt = self.format_entity_prompt(batch)
            
            # Call Gemini API with retries
            response = None
            for retry in range(self.max_retries):
                try:
                    response = self.model.generate_content(prompt)
                    break
                except Exception as e:
                    logger.error(f"Gemini API error: {e}")
                    if retry < self.max_retries - 1:
                        logger.warning(f"Retry {retry+1}/{self.max_retries} after error: {e}")
                        time.sleep(self.delay_between_retries)
                    else:
                        raise
            
            if not response:
                raise Exception("Failed to get response from Gemini after retries")
            
            # Process the response
            response_text = response.text
            logger.debug(f"Raw response text (first 200 chars): {response_text[:200]}")
            
            # First try: Look for JSON array in the response
            clean_text = response_text.strip()
            results = []
            
            # Try to find JSON array in code blocks
            import re
            json_block_pattern = r'```(?:json)?\s*(\[\s*\{.*?\}\s*\])\s*```'
            json_matches = re.search(json_block_pattern, clean_text, re.DOTALL)
            
            if json_matches:
                try:
                    json_array = json_matches.group(1).strip()
                    logger.debug(f"Found JSON array in code block (first 100 chars): {json_array[:100]}")
                    results = json.loads(json_array)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON array in code block: {e}")
            
            # Second try: Look for individual JSON objects in the response
            if not results:
                # Look for entire response as JSON array
                if clean_text.startswith('[') and clean_text.endswith(']'):
                    try:
                        logger.debug(f"Trying to parse response as JSON array (first 100 chars): {clean_text[:100]}")
                        results = json.loads(clean_text)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse response as JSON array: {e}")
            
            # Third try: Look for a sequence of JSON objects separated by newlines
            if not results:
                try:
                    # Split by newlines and look for JSON objects
                    object_pattern = r'(\{[^}]*"entity_name"[^}]*\})'
                    matches = re.findall(object_pattern, clean_text, re.DOTALL)
                    logger.debug(f"Found {len(matches)} potential JSON objects using regex")
                    
                    if matches:
                        for i, match in enumerate(matches):
                            try:
                                obj = json.loads(match.strip())
                                if "entity_name" in obj:
                                    results.append(obj)
                            except json.JSONDecodeError:
                                # Skip invalid JSON
                                pass
                except Exception as e:
                    logger.warning(f"Error in regex object extraction: {e}")
            
            # Final attempt: Use the extraction method
            if not results:
                logger.debug("Using fallback text extraction method")
                results = self.extract_results_from_text(response_text, batch)
            
            # Create output structure
            output = {
                "batch_id": batch_id,
                "category": batch.get("category", "unknown"),
                "entities_count": num_entities,
                "analysis_results": results,
                "raw_response": response_text
            }
            
            return output
            
        except Exception as e:
            logger.error(f"Error analyzing batch {os.path.basename(batch_file)}: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return {
                "batch_id": os.path.basename(batch_file).replace("batch_", "").replace(".json", ""),
                "error": str(e),
                "entities_count": 0,
                "analysis_results": [],
                "raw_response": ""
            }
    
    def extract_results_from_text(self, text: str, batch: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract structured results from a potentially non-JSON response.
        
        Args:
            text: Response text from Gemini
            batch: Original batch data for reference
            
        Returns:
            List[Dict[str, Any]]: Extracted results
        """
        results = []
        entity_names = [entity_data["entity"] for entity_data in batch["entities"]]
        
        # First attempt: Try to find and parse JSON objects in the text
        try:
            # Look for JSON objects in the response
            import re
            json_pattern = r'(\{[^{}]*"entity_name"[^{}]*\})'
            matches = re.findall(json_pattern, text, re.DOTALL)
            
            if matches:
                for match in matches:
                    try:
                        # Clean up the match and parse as JSON
                        clean_json = match.strip()
                        # Make sure it's a valid JSON object
                        if not (clean_json.startswith('{') and clean_json.endswith('}')):
                            clean_json = '{' + clean_json + '}'
                        
                        # Replace any newlines or extra whitespace in the JSON
                        clean_json = re.sub(r'\s+', ' ', clean_json)
                        
                        # Attempt to parse
                        result = json.loads(clean_json)
                        if "entity_name" in result:
                            results.append(result)
                    except json.JSONDecodeError:
                        logger.debug(f"Failed to parse potential JSON object: {match[:50]}...")
        except Exception as e:
            logger.debug(f"Error in regex JSON extraction: {e}")
        
        # If we got results from JSON parsing, return them
        if results:
            return results
            
        # Fallback method: Try to extract structured data from text
        current_entity = None
        current_data = {}
        
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line contains an entity name
            for entity in entity_names:
                if f'"{entity}"' in line or f"'{entity}'" in line or line.startswith(f"{entity}:"):
                    # Save previous entity data if it exists
                    if current_entity and current_data:
                        results.append(current_data)
                    
                    # Start new entity
                    current_entity = entity
                    current_data = {"entity_name": entity}
                    break
            
            # Extract classification
            if current_entity:
                if "SINGLE" in line.upper():
                    current_data["classification"] = "SINGLE"
                elif "MULTIPLE" in line.upper():
                    current_data["classification"] = "MULTIPLE"
                
                # Extract confidence
                if "HIGH" in line.upper():
                    current_data["confidence"] = "HIGH"
                elif "MEDIUM" in line.upper():
                    current_data["confidence"] = "MEDIUM"
                elif "LOW" in line.upper():
                    current_data["confidence"] = "LOW"
                
                # Extract explanation (simple approach)
                if "explanation" in line.lower() or "reason" in line.lower():
                    explanation_parts = line.split(":", 1)
                    if len(explanation_parts) > 1:
                        current_data["explanation"] = explanation_parts[1].strip()
                
                # Extract split entities if MULTIPLE
                if current_data.get("classification") == "MULTIPLE" and ("split" in line.lower() or "|" in line):
                    if "|" in line:
                        split_parts = line.split("|")
                        split_entities = [part.strip() for part in split_parts if part.strip()]
                        if split_entities:
                            current_data["split_entities"] = split_entities
                    elif ":" in line and ("split" in line.lower() or "entities" in line.lower()):
                        # Try to extract a list after a colon
                        parts = line.split(":", 1)
                        if len(parts) > 1 and parts[1].strip():
                            # Look for entities that might be separated by commas or other delimiters
                            potential_list = parts[1].strip()
                            if "," in potential_list:
                                split_entities = [e.strip(' "\'[]') for e in potential_list.split(",") if e.strip()]
                                if split_entities:
                                    current_data["split_entities"] = split_entities
        
        # Add the last entity if it exists
        if current_entity and current_data:
            results.append(current_data)
        
        # If we couldn't extract any results, create placeholder results with default values
        if not results:
            for entity in entity_names:
                results.append({
                    "entity_name": entity,
                    "classification": "SINGLE",  # Default to SINGLE as safer option
                    "confidence": "LOW",
                    "explanation": "Failed to extract proper analysis from Gemini response",
                    "processing_error": True
                })
        
        return results
    
    def process_batches(self, batch_id: str = None) -> List[Dict[str, Any]]:
        """
        Process all batches in the input directory or a specific batch.
        
        Args:
            batch_id: Optional specific batch ID to process
            
        Returns:
            List[Dict[str, Any]]: Results for all processed batches
        """
        # Find batch files
        batch_files = []
        for filename in os.listdir(self.input_dir):
            if filename.startswith("batch_") and filename.endswith(".json"):
                if batch_id is None or batch_id in filename:
                    batch_files.append(os.path.join(self.input_dir, filename))
        
        if not batch_files:
            logger.warning(f"No batch files found in {self.input_dir}" + 
                          (f" matching batch_id {batch_id}" if batch_id else ""))
            return []
        
        logger.info(f"Found {len(batch_files)} batch files to process")
        
        # Process each batch and collect results
        all_results = []
        for batch_file in batch_files:
            try:
                results = self.analyze_batch(batch_file)
                all_results.append(results)
                
                # Save individual batch results
                batch_id = results["batch_id"]
                output_file = os.path.join(self.output_dir, f"results_{batch_id}.json")
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2)
                
                logger.info(f"Saved results for batch {batch_id} to {output_file}")
                
                # Add a small delay between API calls
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_file}: {e}")
        
        return all_results
    
    def compile_results(self, all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compile all batch results into a comprehensive summary.
        
        Args:
            all_results: Results from all processed batches
            
        Returns:
            Dict[str, Any]: Compiled summary
        """
        # Gather all entity results
        all_entities = []
        entity_counts = {
            "total": 0,
            "single": 0,
            "multiple": 0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "high_confidence_multiple": 0
        }
        
        for batch_result in all_results:
            for entity_result in batch_result.get("analysis_results", []):
                all_entities.append(entity_result)
                
                # Count statistics
                entity_counts["total"] += 1
                
                classification = entity_result.get("classification", "").upper()
                confidence = entity_result.get("confidence", "").upper()
                
                if classification == "SINGLE":
                    entity_counts["single"] += 1
                elif classification == "MULTIPLE":
                    entity_counts["multiple"] += 1
                    if confidence == "HIGH":
                        entity_counts["high_confidence_multiple"] += 1
                
                if confidence == "HIGH":
                    entity_counts["high_confidence"] += 1
                elif confidence == "MEDIUM":
                    entity_counts["medium_confidence"] += 1
                elif confidence == "LOW":
                    entity_counts["low_confidence"] += 1
        
        # Create a summary
        summary = {
            "total_entities_analyzed": entity_counts["total"],
            "classification_counts": {
                "single": entity_counts["single"],
                "multiple": entity_counts["multiple"]
            },
            "confidence_counts": {
                "high": entity_counts["high_confidence"],
                "medium": entity_counts["medium_confidence"],
                "low": entity_counts["low_confidence"]
            },
            "high_confidence_multiple_count": entity_counts["high_confidence_multiple"],
            "entity_results": all_entities
        }
        
        # Save the compiled results
        output_file = os.path.join(self.output_dir, "compiled_results.json")
        with open(output_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Saved compiled results to {output_file}")
        
        return summary
    
    def run(self, batch_id: str = None) -> Dict[str, Any]:
        """
        Run the complete analysis process.
        
        Args:
            batch_id: Optional specific batch ID to process
            
        Returns:
            Dict[str, Any]: Compiled summary of results
        """
        logger.info("Starting Gemini entity analysis")
        
        all_results = self.process_batches(batch_id)
        
        if not all_results:
            logger.warning("No results to compile")
            return {}
        
        summary = self.compile_results(all_results)
        
        logger.info("Analysis complete")
        return summary

def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description="Analyze batches of entity data using Gemini to identify true double disclosures.")
    parser.add_argument("--input-dir", default="scripts/gemini_batches", help="Directory containing batch files to process")
    parser.add_argument("--output-dir", default="scripts/gemini_results", help="Directory to save results to")
    parser.add_argument("--api-key", help="Google Gemini API key")
    parser.add_argument("--api-key-file", default=".gemini_api_key", help="File containing Google Gemini API key")
    parser.add_argument("--batch-id", help="Optional specific batch ID to process (e.g., 'and_1')")
    parser.add_argument("--model", default="gemini-1.5-flash-latest", help="Gemini model to use")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Create the output directory if it doesn't exist
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # Run the analysis
    analyzer = GeminiEntityAnalyzer(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        api_key=args.api_key,
        api_key_file=args.api_key_file,
        model_name=args.model
    )
    
    analyzer.run(batch_id=args.batch_id)

if __name__ == '__main__':
    main() 