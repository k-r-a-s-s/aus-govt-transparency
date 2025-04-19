import os
from dotenv import load_dotenv

# Load environment variables from .env.local in the project root
# Assumes the script is run from the project root or a subdirectory
load_dotenv(dotenv_path='.env.local', override=True)

import argparse
import time
import pandas as pd
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# --- Configuration ---
DEFAULT_MODEL_NAME = 'gemini-1.5-flash-latest'
DEFAULT_API_KEY_ENV = 'GOOGLE_API_KEY'
DEFAULT_BATCH_SIZE = 10  # Process 10 rows per batch (adjust as needed)
DEFAULT_MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5  # Wait time between retries

# --- Prompt Template ---
PROMPT_TEMPLATE = """Review the following entity name standardization attempt:
Original (after regex/case): '{regex_name}'
Proposed Fuzzy Match: '{fuzzy_name}'

Is the 'Proposed Fuzzy Match' a correct and ideal standardization for the 'Original'?

Respond ONLY with 'Yes' if it is correct.
Respond ONLY with the single best canonical/standard name if it is incorrect or could be improved. Do not add any explanation.
"""

# --- Helper Functions ---

def configure_gemini(api_key_env: str) -> bool:
    """Configures the Gemini client using an API key from an environment variable."""
    api_key = os.getenv(api_key_env)
    if not api_key:
        print("Please set the environment variable before running the script.")
        return False
    try:
        genai.configure(api_key=api_key)
        print("Gemini API configured successfully.")
        return True
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        return False

def call_gemini_with_retry(
    model_name: str,
    prompt: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    delay: int = RETRY_DELAY_SECONDS
) -> str | None:
    """Calls the Gemini API with retry logic for transient errors."""
    model = genai.GenerativeModel(model_name)
    retries = 0
    while retries <= max_retries:
        try:
            response = model.generate_content(prompt)
            # Check for empty or blocked response
            if not response.parts:
                 if response.prompt_feedback.block_reason:
                     print(f"Warning: Prompt blocked. Reason: {response.prompt_feedback.block_reason}")
                     return f"PROMPT_BLOCKED: {response.prompt_feedback.block_reason}" # Indicate blocking
                 else:
                     print("Warning: Received empty response from API.")
                     return None # Treat empty as failure for retry

            # Assuming text is in the first part if response is not empty
            return response.text.strip()

        except (google_exceptions.ResourceExhausted,
                google_exceptions.ServiceUnavailable,
                google_exceptions.InternalServerError,
                google_exceptions.DeadlineExceeded) as e:
            retries += 1
            print(f"API Error: {e}. Retry {retries}/{max_retries} in {delay}s...")
            if retries > max_retries:
                print("Max retries exceeded. Skipping this call.")
                return None
            time.sleep(delay)
        except Exception as e:
            # Handle other unexpected errors
            print(f"Unexpected Error calling Gemini API: {e}")
            return None # Non-retryable error

    return None # Should not be reached if max_retries > 0, but acts as fallback

def process_batch(df_batch: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """Processes a batch of rows, calling Gemini for each."""
    results = []
    total_rows = len(df_batch)
    for index, row in df_batch.iterrows():
        print(f"Processing row {index+1}/{total_rows} (ID: {row['disclosure_id']})...")
        regex_name = row['regex_standardized']
        fuzzy_name = row['fuzzy_match']

        # Basic validation
        if not isinstance(regex_name, str) or not isinstance(fuzzy_name, str) or not regex_name or not fuzzy_name:
            print(f"  Skipping row {index+1} due to missing/invalid names.")
            results.append({
                'llm_decision': 'Skipped',
                'llm_output': 'Invalid input names',
                'llm_corrected_name': None
            })
            continue

        prompt = PROMPT_TEMPLATE.format(regex_name=regex_name, fuzzy_name=fuzzy_name)
        llm_output = call_gemini_with_retry(model_name, prompt)

        decision = 'Error'
        corrected_name = None

        if llm_output is None:
            decision = 'Error'
            output_text = 'API Call Failed'
        elif llm_output.startswith('PROMPT_BLOCKED'):
             decision = 'Blocked'
             output_text = llm_output
        elif llm_output.strip().lower() == 'yes':
            decision = 'Yes'
            output_text = llm_output.strip()
        else:
            # Assume any other non-empty response is the corrected name
            decision = 'Corrected'
            output_text = llm_output.strip()
            corrected_name = output_text # Use the LLM output directly

        results.append({
            'llm_decision': decision,
            'llm_output': output_text,
            'llm_corrected_name': corrected_name
        })
        # Small delay to potentially help with rate limiting
        time.sleep(0.1)

    # Convert results list of dicts to DataFrame
    results_df = pd.DataFrame(results)
    # Add the results columns to the original batch DataFrame
    # Reset index is important if the original df_batch index isn't 0-based sequential
    df_batch = df_batch.reset_index(drop=True)
    results_df = results_df.reset_index(drop=True)
    return pd.concat([df_batch, results_df], axis=1)

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description='Verify fuzzy entity matches using Gemini LLM.')
    parser.add_argument('--input-csv', required=True, help='Path to the input CSV file from standardize_entities.py.')
    parser.add_argument('--output-csv', required=True, help='Path to save the verification results CSV.')
    parser.add_argument('--api-key-env', default=DEFAULT_API_KEY_ENV, help=f'Environment variable containing the Gemini API key (default: {DEFAULT_API_KEY_ENV}).')
    parser.add_argument('--model-name', default=DEFAULT_MODEL_NAME, help=f'Gemini model name (default: {DEFAULT_MODEL_NAME}).')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE, help=f'Number of rows to process per batch (default: {DEFAULT_BATCH_SIZE}).')
    parser.add_argument('--max-retries', type=int, default=DEFAULT_MAX_RETRIES, help=f'Max retries for API calls (default: {DEFAULT_MAX_RETRIES}).')

    args = parser.parse_args()

    print("--- Starting LLM Verification --- ")
    print(f"Input CSV: {args.input_csv}")
    print(f"Output CSV: {args.output_csv}")
    print(f"Model: {args.model_name}")
    print(f"Batch Size: {args.batch_size}")

    # 1. Configure Gemini
    if not configure_gemini(args.api_key_env):
        return # Stop if API key is not configured

    # 2. Read Input CSV
    try:
        df = pd.read_csv(args.input_csv)
        print(f"Read {len(df)} rows from {args.input_csv}")
        if df.empty:
            print("Input CSV is empty. Nothing to process.")
            # Create empty output file with headers
            pd.DataFrame(columns=list(df.columns) + ['llm_decision', 'llm_output', 'llm_corrected_name']).to_csv(args.output_csv, index=False)
            print(f"Empty results file created at {args.output_csv}")
            return
        # Ensure required columns exist
        required_cols = ['disclosure_id', 'regex_standardized', 'fuzzy_match']
        if not all(col in df.columns for col in required_cols):
            print(f"Error: Input CSV must contain columns: {required_cols}")
            return
    except FileNotFoundError:
        print(f"Error: Input CSV file not found at {args.input_csv}")
        return
    except Exception as e:
        print(f"Error reading input CSV: {e}")
        return

    # 3. Process in Batches
    all_results_df = pd.DataFrame()
    num_batches = (len(df) + args.batch_size - 1) // args.batch_size

    for i in range(num_batches):
        start_idx = i * args.batch_size
        end_idx = min((i + 1) * args.batch_size, len(df))
        df_batch = df[start_idx:end_idx]

        print(f"\n--- Processing Batch {i+1}/{num_batches} (Rows {start_idx+1}-{end_idx}) ---")
        processed_batch_df = process_batch(df_batch, args.model_name)
        all_results_df = pd.concat([all_results_df, processed_batch_df], ignore_index=True)

    # 4. Save Output CSV
    try:
        all_results_df.to_csv(args.output_csv, index=False, encoding='utf-8')
        print(f"\n--- Verification Complete --- ")
        print(f"Results saved to {args.output_csv}")
        # Print summary
        if not all_results_df.empty:
            print("\nVerification Summary:")
            print(all_results_df['llm_decision'].value_counts())
    except Exception as e:
        print(f"Error writing output CSV: {e}")


if __name__ == '__main__':
    main() 