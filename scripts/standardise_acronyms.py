# filename: expand_entities.py
import csv
import os
import json
import logging
import time
import re
import sys # Add sys import

# Add project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
logging.info(f"Added project root to sys.path: {project_root}")

# Load environment variables from .env.local
try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(project_root, '.env.local')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
        logging.info(f"Loaded environment variables from {dotenv_path}")
    else:
        logging.warning(f".env.local file not found at {dotenv_path}, relying on system environment variables.")
except ImportError:
    logging.warning("python-dotenv library not found. pip install python-dotenv. Relying on system environment variables.")

# Diagnostic: Check if the specific file exists before attempting import
rate_limiter_path = os.path.join(project_root, 'utils', 'rate_limiter.py')
if os.path.exists(rate_limiter_path):
    logging.info(f"Confirmed utils/rate_limiter.py exists at: {rate_limiter_path}")
else:
    logging.warning(f"File utils/rate_limiter.py NOT FOUND at expected path: {rate_limiter_path}")

try:
    from google import generativeai as genai
    from google.generativeai import types
    from google.generativeai.types import generation_types
except ImportError:
    print("Please install the Google Generative AI library: pip install google-generativeai")
    exit(1)

# Try to import the RateLimiter, fallback to a simple timer if not found
try:
    from src.common.rate_limiter import RateLimiter
    RATE_LIMITER_AVAILABLE = True
    logging.info("Successfully imported RateLimiter from src.common.") # Added success log
except ImportError as e: # Add exception details to log
    logging.warning(f"ImportError trying to import RateLimiter: {e}. Check src/common/rate_limiter.py.") # Updated message
    RATE_LIMITER_AVAILABLE = False # Ensure fallback is triggered
    # Define a placeholder class if the import fails - THIS SHOULD NO LONGER BE NEEDED
    class RateLimiter:
        def __init__(self, requests_per_minute, requests_per_day):
            self.delay = 60.0 / requests_per_minute
            logging.info(f"Initialized PLACEHOLDER rate limiter with delay: {self.delay:.2f}s")

        def wait_if_needed(self):
            time.sleep(self.delay)

# --- Configuration ---
# Construct paths relative to the project root
CSV_FILE = os.path.join(project_root, "short_normalized_entities_context.csv")
OUTPUT_FILE = os.path.join(project_root, "expanded_entities.csv") # CHANGED to .csv
MODEL_NAME = "gemini-2.0-flash" # As per guidance
API_KEY = os.environ.get("GOOGLE_API_KEY")
CHUNK_SIZE = 200 # Number of entities to process per API call
MAX_RETRIES = 3
REQUESTS_PER_MINUTE = 15 # Default free tier RPM for Gemini 2.0 Flash
REQUESTS_PER_DAY = 1500 # Default free tier RPD (not strictly enforced here)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Rate Limiter Setup ---
# This now uses the imported RateLimiter class if available
rate_limiter = RateLimiter(requests_per_minute=REQUESTS_PER_MINUTE, requests_per_day=REQUESTS_PER_DAY)

# --- Gemini Client Setup ---
model = None # Define global model variable

if not API_KEY:
    logging.error("GOOGLE_API_KEY environment variable not set.")
    exit(1)

try:
    # Configure the client using the API key
    genai.configure(api_key=API_KEY)
    # Initialize the specific model globally
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        logging.info(f"Gemini model {MODEL_NAME} initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Gemini model {MODEL_NAME}: {e}")
        exit(1)

except Exception as e:
    logging.error(f"Failed to configure Gemini client: {e}")
    exit(1)

# --- Helper Functions ---
def read_entities_from_csv(filepath):
    """Reads the 'normalized_entity' column from the CSV file, returns unique sorted list."""
    entities = set()
    try:
        with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
            # Handle potential quote escaping issues if needed
            reader = csv.DictReader(csvfile, skipinitialspace=True)
            if 'normalized_entity' not in reader.fieldnames:
                logging.error(f"'normalized_entity' column not found in {filepath}")
                return []
            for row in reader:
                entity = row.get('normalized_entity', '').strip()
                # Simple cleaning: remove extra quotes if they exist
                if entity.startswith('"') and entity.endswith('"'):
                    entity = entity[1:-1]
                if entity:
                    entities.add(entity)
        logging.info(f"Read {len(entities)} unique entities from {filepath}")
        return sorted(list(entities))
    except FileNotFoundError:
        logging.error(f"CSV file not found: {filepath}")
        return []
    except Exception as e:
        logging.error(f"Error reading CSV file {filepath}: {e}")
        return []

def create_expansion_prompt(entity_list):
    """Creates the prompt for Gemini to expand entity names."""
    # Using f-string for clarity
    prompt = f"""
You are an expert assistant specializing in Australian corporate entities, government bodies, banks, and institutions.
Your task is to expand the following potentially abbreviated or normalized entity names into their most likely full, formal names.
Focus on Australian context.

Provide the expansion for each entity in the list below. If you are unsure or cannot determine a likely full name for an entity, return the original entity name as the expansion. Do not invent names.

Input Entities:
{', '.join(entity_list)}

Output the results ONLY as a valid JSON object mapping each original input entity name (string) to its most likely expanded full name (string).

Example Format:
{{
  "ANZ": "Australia and New Zealand Banking Group",
  "CBA": "Commonwealth Bank of Australia",
  "ATO": "Australian Taxation Office",
  "UNKNOWN_ACRONYM": "UNKNOWN_ACRONYM",
  "NonAbbreviatedName": "NonAbbreviatedName"
}}

JSON Output:
"""
    return prompt

def parse_json_response(response_text):
    """Parses JSON from LLM response with error handling, adapted from guidance."""
    try:
        # Remove potential markdown backticks and language identifier
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text, re.IGNORECASE)
        if json_match:
            json_str = json_match.group(1)
        else:
            # If not in backticks, assume the response is the JSON object itself
            json_str = response_text.strip()

        # Basic cleaning: remove trailing commas before closing braces/brackets
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

        # Attempt to parse
        parsed_data = json.loads(json_str)

        if not isinstance(parsed_data, dict):
             raise ValueError("Parsed JSON is not a dictionary object.")
        return parsed_data
    except json.JSONDecodeError as e:
        logging.error(f"JSON Decode Error: {e}. Response text segment: '{response_text[:200]}...'")
        return None
    except ValueError as e:
         logging.error(f"Error processing JSON response: {e}. Response text segment: '{response_text[:200]}...'")
         return None
    except Exception as e:
        logging.error(f"Unexpected error parsing JSON response: {e}")
        logging.debug(f"Raw response: {response_text}")
        return None

def generate_expansions_with_retry(entity_chunk, retry_count=0):
    """Generates expansions for a chunk of entities with error handling and retries."""
    prompt = create_expansion_prompt(entity_chunk)
    generation_config = types.GenerationConfig(
        # max_output_tokens=2048, # Let model decide, should be sufficient
        temperature=0.1,         # Lower temperature for more deterministic, factual output
        # top_p=0.95,            # Default
        # top_k=40               # Default
    )
    # Configure safety settings to be less restrictive if needed, but start with defaults
    # BLOCK_NONE can be risky, BLOCK_ONLY_HIGH is often a good balance.
    # Let's try BLOCK_MEDIUM_AND_ABOVE first (default)
    # Updated safety settings based on AttributeError: Use dicts
    safety_settings=[
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        },
    ]

    try:
        if not model:
            logging.error("Gemini model is not initialized. Cannot proceed.")
            return None

        rate_limiter.wait_if_needed()
        logging.info(f"Sending chunk of {len(entity_chunk)} entities to Gemini (Attempt {retry_count + 1})...")

        # Use the global model instance to generate content
        response = model.generate_content(
            contents=[prompt],
            generation_config=generation_config,
            safety_settings=safety_settings,
            # stream=False # Default
        )

        # --- Response Validation (Simplified - Removed FinishReason check) ---
        if not response.candidates:
            logging.warning(f"Received no candidates in response for chunk starting with '{entity_chunk[0]}'.")
            # Check for prompt feedback block reason if available
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback and hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
                logging.error(f"Request blocked due to {response.prompt_feedback.block_reason}. Details: {getattr(response.prompt_feedback, 'safety_ratings', 'N/A')}")
            # Check for safety ratings on the candidate if it exists
            elif response.candidates and hasattr(response.candidates[0], 'safety_ratings') and response.candidates[0].safety_ratings:
                 problematic_ratings = [r for r in response.candidates[0].safety_ratings if r.probability not in (types.HarmProbability.NEGLIGIBLE, types.HarmProbability.LOW)]
                 if problematic_ratings:
                      logging.warning(f"Potential safety issue detected in response candidate: {problematic_ratings}")
            return None # Indicate failure for this chunk

        # Get the first candidate
        candidate = response.candidates[0]

        # Explicitly check for non-successful finish reasons BEFORE accessing text
        finish_reason_code = getattr(candidate, 'finish_reason', None) # Use getattr for safety
        # Known codes: 1=STOP, 2=MAX_TOKENS, 3=SAFETY, 4=RECITATION, 5=OTHER
        if finish_reason_code is not None and finish_reason_code != 1: # 1 is the success code (STOP)
            logging.warning(f"Generation finished with non-STOP reason: {finish_reason_code}. Check API docs for meaning (e.g., 3=SAFETY, 4=RECITATION). Chunk starting with '{entity_chunk[0]}'.")
            # Log safety ratings if available and reason is SAFETY (3)
            if finish_reason_code == 3 and hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                 problematic_ratings = [r for r in candidate.safety_ratings if r.probability not in (types.HarmProbability.NEGLIGIBLE, types.HarmProbability.LOW)]
                 if problematic_ratings:
                      logging.warning(f"Potential safety issue detected in response candidate: {problematic_ratings}")
            return None # Treat non-STOP reasons as failure for this script's purpose

        # --- Parse successful response --- 
        # Proceed to parse if we have candidates and finish_reason was STOP (or None, assuming success)
        if not hasattr(response, 'text') or not response.text:
            logging.warning(f"Response received but contains no text content for chunk starting with '{entity_chunk[0]}'.")
            return None

        parsed_result = parse_json_response(response.text)
        return parsed_result

    # Specific exception handling based on google.generativeai types
    except generation_types.BlockedPromptException as bpe:
        logging.error(f"Prompt blocked for chunk starting with '{entity_chunk[0]}': {bpe}")
        return None
    except generation_types.StopCandidateException as sce:
        # This might happen if finish_reason is MAX_TOKENS or SAFETY
        logging.error(f"Generation stopped unexpectedly for chunk starting with '{entity_chunk[0]}': {sce}")
        # Try parsing partial text if available
        if hasattr(sce, 'partial_text') and sce.partial_text:
            logging.info("Attempting to parse partial text...")
            return parse_json_response(sce.partial_text)
        return None
    except Exception as e:
        error_str = str(e).upper()
        # Broader check for rate limit related errors (adjust based on observed errors)
        is_rate_limit = "RESOURCE_EXHAUSTED" in error_str or "RATE LIMIT" in error_str or "429" in error_str

        if is_rate_limit and retry_count < MAX_RETRIES:
            # Exponential backoff
            wait_time = min(2 ** (retry_count + 1), 60) # 2, 4, 8 seconds...
            logging.warning(f"Rate limit error (Retry {retry_count + 1}/{MAX_RETRIES}). Waiting {wait_time}s...")
            time.sleep(wait_time)
            return generate_expansions_with_retry(entity_chunk, retry_count + 1)
        else:
            logging.error(f"Unhandled error generating content for chunk starting with '{entity_chunk[0]}': {e}")
            # If not rate limit or retries exhausted, return None for this chunk
            return None

# --- Main Execution Logic ---
def main():
    logging.info("Starting entity expansion process...")
    entities = read_entities_from_csv(CSV_FILE)

    if not entities:
        logging.warning("No entities found or error reading CSV. Exiting.")
        return

    all_expansions = {}
    total_entities = len(entities)
    processed_count = 0
    chunks = [entities[i:min(i + CHUNK_SIZE, total_entities)] for i in range(0, total_entities, CHUNK_SIZE)]
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks):
        logging.info(f"--- Processing chunk {i + 1}/{total_chunks} ({len(chunk)} entities) ---")

        expansions = generate_expansions_with_retry(chunk)

        if expansions and isinstance(expansions, dict):
            processed_chunk_count = 0
            # Verify response keys and add to overall results
            for entity in chunk:
                expanded_name = expansions.get(entity)
                if expanded_name is None:
                     logging.warning(f"LLM response missing key for '{entity}' in chunk {i+1}. Using original.")
                     all_expansions[entity] = entity # Use original as fallback
                else:
                     all_expansions[entity] = str(expanded_name) # Ensure it's a string
                     processed_chunk_count += 1

            # Check for extra keys returned by the model
            extra_keys = set(expansions.keys()) - set(chunk)
            if extra_keys:
                 logging.warning(f"LLM response included {len(extra_keys)} unexpected keys: {list(extra_keys)[:5]}...") # Log first few unexpected keys

            logging.info(f"Successfully processed {processed_chunk_count}/{len(chunk)} entities from LLM response for chunk {i+1}.")

        else:
            logging.error(f"Failed to get valid JSON dictionary for chunk {i+1} (starts with '{chunk[0]}'). Using original entities.")
            # Add original entities for the failed chunk
            for entity in chunk:
                all_expansions[entity] = entity

        processed_count += len(chunk)
        logging.info(f"Progress: {processed_count}/{total_entities} entities considered.")
        # Optional: Add a small delay between chunks even if not rate limited
        # time.sleep(1)

    # --- Save Results ---
    logging.info(f"Total unique entities considered: {total_entities}")
    logging.info(f"Total expansions generated (including fallbacks): {len(all_expansions)}")
    try:
        # Write results to CSV
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['original_entity', 'expanded_entity']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            # Sort by original entity for consistent output
            for entity in sorted(all_expansions.keys()):
                writer.writerow({'original_entity': entity, 'expanded_entity': all_expansions[entity]})

        logging.info(f"Expansion results saved to {OUTPUT_FILE}")
    except IOError as e:
        logging.error(f"Error saving results to {OUTPUT_FILE}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error saving results: {e}")


    logging.info("Entity expansion process finished.")

if __name__ == "__main__":
    main()