"""
Script to iteratively group similar normalized entities and verify groups using an LLM.

Workflow:
1.  Connects to `entity_grouping.db` to manage grouping state across iterations.
2.  Connects to `disclosures.db` to fetch all unique `normalized_entity` values.
3.  Excludes entities already marked as 'confirmed' in `entity_grouping.db` from previous iterations.
4.  Generates sentence embeddings (`all-MiniLM-L6-v2`) for the remaining entities.
5.  Calculates pairwise cosine similarity and builds a graph connecting entities above a similarity `--threshold`.
6.  Detects initial communities (potential groups) using the Louvain algorithm.
7.  Processes detected communities:
    *   **Multi-Member Communities:** 
        *   If `--no-llm-review` is **not** used: Sends the member list to the Google Gemini API with a detailed prompt asking for granular confirmation/rejection of each member based on belonging to a single primary parent entity.
        *   If `--no-llm-review` **is** used: Skips the API call and assigns a default 'pending_review' status to all members.
        *   Assigns a unique `community_ID` (e.g., "1-0", "1-1") based on the current `--iteration` and a group index.
    *   **Single-Member Communities:** (Entities not grouped with others at the threshold)
        *   Assigns a unique `community_ID`.
        *   Marks the single member as 'confirmed' immediately.
8.  Saves results to `entity_grouping.db`:
    *   Creates a record in `entity_communities` for each processed group (multi-member or confirmed single).
    *   Creates records in `entity_community_members` for **all** members of the processed groups, storing their specific `llm_community_status` ('confirmed', 'rejected', or 'pending_review').
9.  Outputs an intermediate JSON file (`iteration_<N>_reviewed_communities.json`) showing the groups processed and member statuses for the current iteration.

**Iteration:** Running the script with increasing `--iteration` numbers allows progressive refinement. Confirmed entities are excluded, allowing the process to focus on remaining ungrouped or rejected entities.

**Environment Setup:**

-   **Virtual Environment:** Strongly recommended to use `venv` or `pyenv`+`virtualenv` due to potential macOS stability issues with Conda, torch, and multiprocessing.
    ```bash
    # Example using venv
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
-   **Dependencies:** Requires `sentence-transformers`, `torch`, `networkx`, `python-louvain`, `google-generativeai`, `python-dotenv`. Ensure these are listed in `requirements.txt` and installed.
-   **API Key:** Requires `GOOGLE_API_KEY` environment variable (can be loaded from `.env.local`) for LLM review, unless `--no-llm-review` is used.

**Usage:**
-   Activate virtual environment.
-   Ensure `requirements.txt` is installed and `.env.local` (if needed) is present.
-   Delete `entity_grouping.db` if starting a completely fresh run.
-   Run iteratively:
    ```bash
    # First iteration (example)
    python scripts/vector_entity_grouping.py --iteration 1 --limit 300 --threshold 0.90
    # Optional: Skip LLM review for testing community detection
    # python scripts/vector_entity_grouping.py --iteration 1 --limit 300 --threshold 0.90 --no-llm-review 
    
    # Subsequent iterations
    python scripts/vector_entity_grouping.py --iteration 2 --threshold 0.90 # No limit needed usually
    python scripts/vector_entity_grouping.py --iteration 3 --threshold 0.90 
    # ...etc.
    ```

**Note on KMP_DUPLICATE_LIB_OK:**
-   Set to suppress harmless warnings on macOS related to multiple OpenMP libraries.

**Future Considerations / Next Steps:**

1.  **LLM Refinement:** Continuously evaluate the LLM prompt and response parsing. Test different models or prompting strategies if the current one struggles with specific edge cases (e.g., accurately distinguishing closely named but distinct companies like AMP/Ampol within a large candidate group).
2.  **Handling Single Entities:** Instead of immediately marking single-member communities as 'confirmed', consider a different status like 'individual' or 'singleton'. This could allow them to be potentially grouped in later iterations if new, closely related entities are processed.
3.  **Re-integrating Rejected Entities:** Develop a strategy to allow entities rejected from one group in an early iteration to potentially join an already *confirmed* group in a later iteration. This is important for cases where an entity (e.g., 'AMP Capital Fund X') is initially grouped incorrectly (e.g., with 'Ampol') and rejected, but should later join the main confirmed 'AMP' group. Potential approaches:
    *   **Dynamic Thresholds:** Gradually lower the similarity threshold in later iterations to allow slightly less similar (but potentially valid) rejected entities to connect to established confirmed groups.
    *   **Targeted Matching:** After initial iterations, specifically compare remaining rejected/pending entities against the *canonical names* or *members* of existing confirmed groups.
    *   **Allowing Confirmed Entities Back:** Revisit the logic of strictly excluding confirmed entities. Perhaps allow them back into the graph-building process under specific conditions or with different weighting.
"""

import multiprocessing
multiprocessing.set_start_method("spawn", force=True)

import sqlite3
from sentence_transformers import SentenceTransformer, util
import os
import networkx as nx
import community as community_louvain
import json
import argparse
import time
import torch
import logging
from typing import Dict, List, Tuple, Any, Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv # Added for .env loading

# Load environment variables from .env.local BEFORE accessing them
load_dotenv(dotenv_path=".env.local")

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# --- LLM Configuration and Helpers ---

# Setup logging (ensure it's configured early)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Define logger here

# Configure the Gemini client (Requires GOOGLE_API_KEY environment variable)
try:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable not set or not loaded from .env.local.")
    client = genai.Client(api_key=GOOGLE_API_KEY)
    model_name = 'gemini-1.5-flash'
    logger.info("Gemini AI client configured successfully.")
except Exception as e:
    logger.error(f"Error configuring Gemini AI client: {e}")
    client = None
    logger.warning("Proceeding without LLM review capabilities.")

def generate_llm_prompt(entity_names: List[str]) -> str:
    """Generates a refined prompt for the LLM to perform granular review of potential corporate entities and output JSON."""
    input_json = json.dumps({"entities_to_review": entity_names}, indent=2)

    prompt = (
        f"Please analyze the following list of potential Australian corporate entity names provided in the JSON structure below.\n"
        f"These names might include parent companies, subsidiaries, specific funds, trusts, or different legal suffixes (e.g., Pty Ltd, Ltd, Inc).\n\n"
        f"1. Identify the single, primary *parent* corporate entity that you believe the majority of these names belong to or represent.\n"
        f"2. For EACH entity name in the original list, decide if it is either:\n"
        f"   a) A valid way of writing the name of that *single primary parent* entity (e.g., handling suffixes like Ltd/Pty Ltd, minor variations). OR\n"
        f"   b) The name of a specific fund, subsidiary, trust, or product clearly belonging *only* to that single primary parent entity.\n"
        f"3. Crucially, REJECT any names that belong to *different* parent companies, even if the names seem similar (e.g., distinguish between 'AMP' entities and 'Ampol' entities if both appear).\n"
        f"4. Return your analysis ONLY as a single JSON object containing one key: 'review_results'.\n"
        f"5. The value of 'review_results' must be another JSON object where:\n"
        f"   - Each key is one of the EXACT entity names from the original input list.\n"
        f"   - Each value is a string: \"confirmed\" (if it meets criteria 2a or 2b for the identified primary parent) or \"rejected\" (if it belongs to a different company or is unrelated/ambiguous).\n\n"
        f"Example Input JSON:\n"
        f"{{\n          \"entities_to_review\": [\"amp super fund\", \"amp growth fund\", \"ampol energy\", \"australian mutual provident society\"]\n        }}\n\n"
        f"Example Output JSON (Assuming primary parent is AMP):\n"
        f"{{\n          \"review_results\": {{\n            \"amp super fund\": \"confirmed\",\n            \"amp growth fund\": \"confirmed\",\n            \"ampol energy\": \"rejected\",\n            \"australian mutual provident society\": \"confirmed\" \n          }}\n        }}\n\n"
        f"Ensure the output is ONLY the JSON object, with no other text before or after it.\n\n"
        f"Input JSON to analyze:\n{input_json}\""
    )
    return prompt

def get_llm_review(entity_names: List[str]) -> Optional[Dict[str, str]]:
    """Gets the LLM's granular review results for a group.

    Returns:
        A dictionary mapping each input entity name to 'confirmed' or 'rejected',
        or None if the review failed.
    """
    if not client:
        logger.warning("LLM client not available. Skipping review.")
        return None

    # Handle single entity groups directly
    if len(entity_names) <= 1:
        return {name: 'confirmed' for name in entity_names}

    prompt = generate_llm_prompt(entity_names)
    max_retries = 2
    for attempt in range(max_retries):
        try:
            logger.debug(f"Sending prompt to LLM (Attempt {attempt+1}/{max_retries}): {prompt[:300]}...")
            response = client.generate_content(model_name, prompt)

            # Extract JSON block (handle potential markdown fences)
            raw_response_text = response.text.strip()
            if raw_response_text.startswith('```json'):
                raw_response_text = raw_response_text[7:]
            if raw_response_text.endswith('```'):
                raw_response_text = raw_response_text[:-3]
            raw_response_text = raw_response_text.strip()

            logger.info(f"LLM raw JSON response: {raw_response_text}")
            parsed_json = json.loads(raw_response_text)

            # Validate the parsed JSON structure
            if isinstance(parsed_json, dict) and 'review_results' in parsed_json:
                review_results = parsed_json['review_results']
                if isinstance(review_results, dict):
                    # Validate keys and values
                    validated_results = {}
                    all_keys_valid = True
                    for name in entity_names: # Ensure all original names are present
                        if name in review_results:
                            status = review_results[name]
                            if status in ["confirmed", "rejected"]:
                                validated_results[name] = status
                            else:
                                logger.warning(f"LLM returned invalid status '{status}' for entity '{name}'. Defaulting to rejected.")
                                validated_results[name] = 'rejected'
                                all_keys_valid = False # Mark as partially invalid if status is wrong
                        else:
                            logger.warning(f"LLM response missing expected entity '{name}'. Defaulting to rejected.")
                            validated_results[name] = 'rejected'
                            all_keys_valid = False # Mark as invalid if key is missing
                    if all_keys_valid and len(validated_results) == len(entity_names):
                         logger.info(f"LLM review successful. Confirmed: {sum(1 for s in validated_results.values() if s=='confirmed')}, Rejected: {sum(1 for s in validated_results.values() if s=='rejected')}")
                         return validated_results
                    else:
                         logger.warning("LLM response validation failed (missing/invalid keys/values). Using default rejections.")
                         return {name: 'rejected' for name in entity_names} # Fallback on validation failure
                else:
                     logger.warning(f"LLM response 'review_results' is not a dictionary. Content: {review_results}")
            else:
                 logger.warning(f"LLM response missing 'review_results' key or is not a dictionary. Response: {parsed_json}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode LLM JSON response (Attempt {attempt+1}): {e}. Response: {raw_response_text}")
        except Exception as e:
            logger.error(f"Error calling LLM API or processing response (Attempt {attempt+1}) for group {entity_names[:3]}...: {e}")

        # If loop finishes without returning, it means all retries failed
        if attempt < max_retries - 1:
             logger.info("Retrying LLM call...")
             time.sleep(2) # Basic backoff

    logger.error(f"LLM review failed after {max_retries} attempts for group {entity_names[:3]}...")
    return None # Indicate review failed completely

# --- Database Functions for Grouping DB ---

def create_grouping_db_tables(conn):
    cursor = conn.cursor()
    # Communities Table (Using community_ID as PK)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entity_communities (
        community_ID TEXT PRIMARY KEY, -- Format: 'iteration-group_index'
        iteration INTEGER NOT NULL,
        group_index_in_iteration INTEGER NOT NULL,
        canonical_name TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_community_iteration ON entity_communities (iteration)")

    # Community Members Table (Referencing community_ID)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entity_community_members (
        member_id INTEGER PRIMARY KEY AUTOINCREMENT,
        community_ID TEXT NOT NULL, -- FK to entity_communities
        iteration INTEGER NOT NULL, -- Iteration this membership record was created/confirmed
        normalized_entity TEXT NOT NULL,
        llm_community_status TEXT NOT NULL, -- Renamed from member_status ('confirmed', 'rejected', 'pending_review')
        FOREIGN KEY (community_ID) REFERENCES entity_communities (community_ID)
    )
    """)
    # Indices for faster lookup
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_entity ON entity_community_members (normalized_entity)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_community_id_ref ON entity_community_members (community_ID)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_iteration ON entity_community_members (iteration)") # Index on iteration
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_status ON entity_community_members (llm_community_status)") # Index on renamed status

    # Clean up old indices if they exist from previous schema versions
    cursor.execute("DROP INDEX IF EXISTS idx_member_community_ref")

    conn.commit()

def get_confirmed_entities(conn):
    cursor = conn.cursor()
    # Query based on llm_community_status in the members table
    cursor.execute("""
    SELECT DISTINCT m.normalized_entity
    FROM entity_community_members m
    WHERE m.llm_community_status = 'confirmed'
    """)
    confirmed = {row[0] for row in cursor.fetchall()}
    return confirmed

def save_communities_to_db(conn, communities_data):
    """Saves detected communities and ALL their reviewed members to the database.

    Args:
        conn: The database connection object.
        communities_data: A dictionary where keys are community_ID (e.g., "1-0")
                          and values are tuples of 
                          (iteration, group_index, canonical_name, member_status_dict).
                          member_status_dict maps entity_name -> 'confirmed', 'rejected', or None/pending
    """
    cursor = conn.cursor()
    saved_community_count = 0
    saved_member_count = 0

    # Insert ALL processed communities
    community_insert_data = []
    all_community_ids = list(communities_data.keys()) # Get all IDs we processed

    for community_id in all_community_ids:
        iteration, group_index, canonical_name, _ = communities_data[community_id]
        # community_ID, iteration, group_index_in_iteration, canonical_name
        community_insert_data.append((community_id, iteration, group_index, canonical_name))

    if community_insert_data:
        cursor.executemany("""
        INSERT INTO entity_communities (community_ID, iteration, group_index_in_iteration, canonical_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(community_ID) DO NOTHING;
        """, community_insert_data)
        saved_community_count = cursor.rowcount
        logger.info(f"Inserted/Updated {saved_community_count} community records.")
    else:
        logger.info("No communities were processed by LLM to insert.")
        return 0

    # Prepare and insert ALL reviewed members for the processed communities
    member_insert_data = []
    for community_id in all_community_ids:
        iteration, _, _, member_statuses = communities_data[community_id]
        for member_name, status in member_statuses.items():
            # Use the status provided by LLM, default to pending_review if None
            final_status = status if status in ['confirmed', 'rejected'] else 'pending_review'
            # community_ID, iteration, normalized_entity, llm_community_status
            member_insert_data.append((community_id, iteration, member_name, final_status))

    if member_insert_data:
        cursor.executemany("""
        INSERT INTO entity_community_members (community_ID, iteration, normalized_entity, llm_community_status)
        VALUES (?, ?, ?, ?)
        """, member_insert_data)
        saved_member_count = cursor.rowcount
        logger.info(f"Inserted {saved_member_count} member records (including confirmed and rejected).")

    conn.commit()
    return saved_community_count

# --- Arguments ---
def parse_args():
    parser = argparse.ArgumentParser(description='Group similar entities using sentence embeddings, LLM review, and community detection, saving results to a database.')
    parser.add_argument('--disclosures_db_path', type=str, default='/Users/kevin/Documents/ProgrammingIsFun/PersonalProjects/g0v/aus-govt-transparency/disclosures.db', help='Path to the source disclosures SQLite database file.')
    parser.add_argument('--grouping_db_path', type=str, default='entity_grouping.db', help='Path to the entity grouping results SQLite database file.')
    parser.add_argument('--threshold', type=float, default=0.75, help='Cosine similarity threshold for building the graph.')
    parser.add_argument('--iteration', type=int, default=1, help='Current iteration number for grouping.')
    parser.add_argument('--limit', type=int, default=None, help='Limit the number of entities fetched for testing.')
    parser.add_argument('--no-llm-review', action='store_true', help='Skip the LLM review step (for testing community detection).')
    parser.epilog = "Requires the GOOGLE_API_KEY environment variable to be set for LLM review functionality (unless --no-llm-review is used)."
    return parser.parse_args()

# --- Main Script --- #
if __name__ == "__main__":
    start_time = time.time()
    args = parse_args()

    DISCLOSURES_DB_PATH = args.disclosures_db_path
    GROUPING_DB_PATH = args.grouping_db_path
    SIMILARITY_THRESHOLD = args.threshold
    ITERATION = args.iteration
    LIMIT = args.limit
    SKIP_LLM_REVIEW = args.no_llm_review

    print(f"--- Configuration ---")
    print(f"Disclosures DB Path: {DISCLOSURES_DB_PATH}")
    print(f"Grouping DB Path: {GROUPING_DB_PATH}")
    print(f"Similarity Threshold: {SIMILARITY_THRESHOLD}")
    print(f"Iteration: {ITERATION}")
    if LIMIT:
        print(f"Entity Limit: {LIMIT}")
    print("---------------------")

    # --- Setup Grouping DB ---
    print(f"Connecting to grouping database: {GROUPING_DB_PATH}")
    conn_grouping = sqlite3.connect(GROUPING_DB_PATH)
    print("Ensuring grouping tables exist...")
    create_grouping_db_tables(conn_grouping)

    # --- Fetch Entities ---
    # Get all unique entities from disclosures DB
    print(f"Connecting to disclosures database: {DISCLOSURES_DB_PATH}")
    conn_disclosures = sqlite3.connect(DISCLOSURES_DB_PATH)
    cursor_disclosures = conn_disclosures.cursor()
    query = "SELECT DISTINCT normalized_entity FROM disclosures WHERE normalized_entity IS NOT NULL AND normalized_entity != ''"
    # Note: LIMIT here is only for testing the whole script, not for selecting final entities
    if LIMIT:
        query += f" ORDER BY normalized_entity LIMIT {LIMIT}" # Order by for consistent limit results

    print("Fetching all unique entities from disclosures DB...")
    cursor_disclosures.execute(query)
    all_entity_names_tuples = cursor_disclosures.fetchall()
    conn_disclosures.close()
    all_entity_names = {name[0] for name in all_entity_names_tuples}
    print(f"Fetched {len(all_entity_names)} total unique entities.")

    # Get entities already confirmed in previous iterations
    print("Fetching confirmed entities from previous iterations...")
    confirmed_entities = get_confirmed_entities(conn_grouping)
    print(f"Found {len(confirmed_entities)} confirmed entities to exclude.")

    # Filter entities for this iteration
    entities_to_process = sorted(list(all_entity_names - confirmed_entities))
    if not entities_to_process:
        print("No entities left to process for this iteration. Exiting.")
        conn_grouping.close()
        import sys
        sys.exit(0)

    print(f"Processing {len(entities_to_process)} entities for iteration {ITERATION}.")

    # --- Embeddings and Similarity ---
    print("\nLoading sentence transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2', device='cuda' if torch.cuda.is_available() else 'cpu') # Use GPU if available

    print("Creating embeddings...")
    embeddings = model.encode(entities_to_process, convert_to_tensor=True, show_progress_bar=True, batch_size=128) # Increased batch size

    print("Calculating cosine similarities...")
    cosine_scores = util.pytorch_cos_sim(embeddings, embeddings)

    # --- Graph Building and Community Detection ---
    print("\nBuilding graph...")
    G = nx.Graph()
    # Map name to index within the entities_to_process list
    entity_index_map = {name: i for i, name in enumerate(entities_to_process)}
    for i in range(len(entities_to_process)):
        G.add_node(i)

    edge_count = 0
    for i in range(len(entities_to_process)):
        for j in range(i + 1, len(entities_to_process)):
            score = cosine_scores[i, j].item()
            if score >= SIMILARITY_THRESHOLD:
                G.add_edge(i, j, weight=score)
                edge_count += 1

    print(f"Graph built with {G.number_of_nodes()} nodes and {edge_count} edges.")

    # This will store {group_index_in_iteration: (canonical_name, {member_name: status})}
    final_communities_to_save = {}
    multi_member_community_count = 0
    single_member_community_count = 0
    group_index_counter = 0 # Counter for group index within this iteration

    if edge_count > 0:
        print("\n--- Detecting Communities and Processing ---") # Combined heading - Corrected syntax
        # 1. Detect communities
        partition = community_louvain.best_partition(G, weight='weight', random_state=42)
        logger.info(f"Louvain detected {len(set(partition.values()))} initial partitions.")

        # 2. Group nodes by community ID
        communities_by_id: Dict[Any, List[int]] = {}
        for node_index, community_id in partition.items():
            if community_id not in communities_by_id:
                communities_by_id[community_id] = []
            communities_by_id[community_id].append(node_index)
        logger.info(f"Grouped into {len(communities_by_id)} communities.")

        # 3. Process each community
        processed_indices = set()
        communities_for_saving: Dict[str, Tuple[int, int, str, Dict[str, str]]] = {} 
        group_index_counter = 0
        llm_reviewed_count = 0
        llm_total_confirmed = 0
        llm_total_rejected = 0
        llm_failed_group_count = 0

        # Sort items for deterministic processing
        sorted_community_items = sorted(communities_by_id.items())

        for community_id, members_indices in sorted_community_items: # Iterate through the grouped communities
            # Ensure members_indices is the list of nodes for THIS community_id
            # (No longer rebuilding it incorrectly inside the loop)

            # Skip if any member already processed (safeguard, less likely needed now)
            if any(idx in processed_indices for idx in members_indices):
                 logger.warning(f"Community ID {community_id} contains already processed members. Skipping.") # Log if this happens
                 continue

            member_names = sorted([entities_to_process[idx] for idx in members_indices])

            if len(member_names) > 1:
                current_group_index = group_index_counter
                community_id_str = f"{ITERATION}-{current_group_index}"
                canonical_name = member_names[0]
                member_review_statuses = None # Initialize

                if not SKIP_LLM_REVIEW:
                    # --- LLM Review Step ---
                    logger.info(f"Sending group {community_id_str} for LLM review: {member_names[:5]}...")
                    member_review_statuses = get_llm_review(member_names)
                    llm_reviewed_count += 1

                    if member_review_statuses:
                        num_confirmed = sum(1 for status in member_review_statuses.values() if status == 'confirmed')
                        num_rejected = sum(1 for status in member_review_statuses.values() if status == 'rejected')
                        num_pending = len(member_review_statuses) - num_confirmed - num_rejected

                        if num_confirmed > 0:
                            llm_total_confirmed += num_confirmed
                            llm_total_rejected += num_rejected
                            logger.info(f"Group {community_id_str} review complete: {num_confirmed} confirmed, {num_rejected} rejected.")
                        else:
                            # Handle case where LLM call succeeded but confirmed 0 (all rejected)
                            llm_total_rejected += len(member_review_statuses)
                            logger.info(f"Group {community_id_str} review complete: 0 confirmed, {len(member_review_statuses)} rejected.")
                    else:
                        # Handle case where get_llm_review returns None after retries
                        llm_failed_group_count += 1
                        logger.warning(f"LLM review API call failed for group {community_id_str}. Group will not be saved.")
                else:
                    # --- Skip LLM Review --- 
                    logger.info(f"Skipping LLM review for group {community_id_str} due to --no-llm-review flag.")
                    # Assign default status (pending_review)
                    member_review_statuses = {name: 'pending_review' for name in member_names}
                    # We didn't technically fail the API call, so don't increment llm_failed_group_count here
                    # We also didn't confirm/reject via LLM

                # --- Process group based on review (or lack thereof) ---
                if member_review_statuses: # Should always be true now unless get_llm_review returns None after retries
                    num_confirmed = sum(1 for status in member_review_statuses.values() if status == 'confirmed')
                    num_rejected = sum(1 for status in member_review_statuses.values() if status == 'rejected')
                    num_pending = len(member_review_statuses) - num_confirmed - num_rejected

                    if not SKIP_LLM_REVIEW:
                         if num_confirmed > 0:
                             llm_total_confirmed += num_confirmed
                             llm_total_rejected += num_rejected
                             logger.info(f"Group {community_id_str} review complete: {num_confirmed} confirmed, {num_rejected} rejected.")
                         else:
                             # Handle case where LLM call succeeded but confirmed 0 (all rejected)
                             llm_total_rejected += len(member_review_statuses)
                             logger.info(f"Group {community_id_str} review complete: 0 confirmed, {len(member_review_statuses)} rejected.")
                    
                    # Save group if it wasn't an LLM failure OR if we skipped LLM review
                    # Previously only saved if num_confirmed > 0, now we save if status dict exists
                    multi_member_community_count += 1
                    communities_for_saving[community_id_str] = (ITERATION, current_group_index, canonical_name, member_review_statuses)
                    group_index_counter += 1 
                    
                else: # This branch now only happens if get_llm_review failed after retries
                    llm_failed_group_count += 1
                    logger.warning(f"LLM review API call failed for group {community_id_str}. Group will not be saved.")
                    group_index_counter += 1
                # --- End group processing ---

                # Mark members as processed for this iteration's graph building
                for idx in members_indices:
                    processed_indices.add(idx)

            elif len(member_names) == 1:
                 # Handle single-member communities - Mark as confirmed immediately
                 node_index = members_indices[0]
                 if node_index not in processed_indices:
                    single_member_name = member_names[0]
                    single_member_community_count += 1 # Keep track for logging
                    # Create a community record for this single confirmed entity
                    current_group_index = group_index_counter
                    community_id_str = f"{ITERATION}-{current_group_index}" # Assign a unique ID
                    canonical_name = single_member_name # Canonical is itself
                    member_review_statuses = {single_member_name: 'confirmed'}
                    # Add to data to be saved
                    communities_for_saving[community_id_str] = (ITERATION, current_group_index, canonical_name, member_review_statuses)
                    group_index_counter += 1
                    processed_indices.add(node_index) # Mark as processed
                    logger.info(f"Identified single entity '{single_member_name}' (ID: {community_id_str}). Marking as confirmed.")

        print(f"Processed {multi_member_community_count} multi-member communities found by graph algorithm.")
        if not SKIP_LLM_REVIEW:
            if llm_reviewed_count > 0:
                print(f"  LLM Results: {llm_total_confirmed} total members confirmed, {llm_total_rejected} total members rejected.")
                if llm_failed_group_count > 0:
                    print(f"  LLM API call failed for {llm_failed_group_count} groups.")
            else:
                 print("  LLM Review skipped (LLM client unavailable or no multi-member groups).")
        else:
            print("  LLM Review was skipped via --no-llm-review flag.")
        print(f"Processed {single_member_community_count} single-member entities (marked as confirmed).")

    else:
        print("No edges created at the specified threshold. Marking all as single entities.")
        # If no edges, all entities are single-member communities
        single_member_community_count = 0
        communities_for_saving: Dict[str, Tuple[int, int, str, Dict[str, str]]] = {} # Redefine locally
        group_index_counter = 0 # Reset counter
        for i, entity_name in enumerate(entities_to_process):
             current_group_index = group_index_counter
             community_id_str = f"{ITERATION}-{current_group_index}" # Assign unique ID
             canonical_name = entity_name
             member_review_statuses = {entity_name: 'confirmed'}
             communities_for_saving[community_id_str] = (ITERATION, current_group_index, canonical_name, member_review_statuses)
             group_index_counter += 1
             single_member_community_count += 1
        print(f"Marked {single_member_community_count} entities as confirmed.")

    # --- Intermediate Output for Debugging ---
    intermediate_output_file = f"iteration_{ITERATION}_reviewed_communities.json"
    logger.info(f"Saving intermediate results for iteration {ITERATION} to {intermediate_output_file}...")
    try:
        # Prepare data for JSON - Key is community_ID string
        # communities_for_saving already has the correct structure
        json_output_data = {
            comm_id: {
                "iteration": data[0],
                "group_index": data[1],
                "canonical_name": data[2],
                "member_statuses": data[3]
            }
            for comm_id, data in communities_for_saving.items()
        }
        with open(intermediate_output_file, 'w') as f_out:
            json.dump(json_output_data, f_out, indent=2)
        logger.info(f"Successfully saved intermediate results to {intermediate_output_file}.")
    except Exception as e:
        logger.error(f"Failed to save intermediate results: {e}")
    # --- End Intermediate Output ---

    # --- Save Results to Grouping DB ---
    # No longer filter here, save_communities_to_db handles all reviewed communities
    communities_to_save_final = communities_for_saving

    if communities_to_save_final:
        print(f"\nSaving {len(communities_to_save_final)} processed communities and their member statuses to {GROUPING_DB_PATH} for iteration {ITERATION}...")
        # Pass the dict keyed by community_ID
        saved_count = save_communities_to_db(conn_grouping, communities_to_save_final)
        print(f"Successfully saved {saved_count} community records.")
    else:
        print("\nNo multi-member communities were reviewed by LLM in this iteration.")

    conn_grouping.close()

    end_time = time.time()
    print(f"\nScript finished in {end_time - start_time:.2f} seconds.")
    print("Done.")

