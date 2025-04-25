"""
Entity Grouping and Canonicalization Pipeline

This module implements the iterative grouping and canonicalization of entities for the Australian Government Transparency Project.

---
**Environment Setup:**
- Use a Python virtual environment (venv), NOT conda, as recommended in the project documentation (see refactor_plan.rmd and development_diary.rmd).
- This is due to compatibility and stability issues with torch and multiprocessing on macOS when using conda. venv or pyenv+virtualenv is strongly recommended for this section of the pipeline.
---

Workflow:
1. Extract all unique `entity_id` (UUID) and `canonical_name` values from the `entities` table in `disclosures.db`.
2. Iteratively group similar entities using vector embeddings and community detection.
3. Use LLM supervision to confirm/reject group members.
4. Assign a canonical entity (with a UUID as `entity_id`) to each confirmed group.
5. Store all grouping and review results in a temporary `entity_grouping.db`.
6. Export a mapping of `{entity_id, canonical_name, status}` for migration.
7. A separate migration script will update `disclosures.db` and the canonical `entities` table using this mapping.

Notes:
- Temporary community/iteration IDs are used only for grouping; the final `entity_id` is a UUID and will be used in the canonical schema.
- The `entity_grouping.db` schema should be updated to store the actual UUID `entity_id` for each canonical group.
- All code is strongly typed and functional.

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
from typing import Dict, List, Tuple, Any, Optional, Literal
from google import genai
from google.genai import types
from dotenv import load_dotenv # Added for .env loading
import uuid
from pydantic import BaseModel, ValidationError
import pathlib

# Load environment variables from .env.local BEFORE accessing them
load_dotenv(dotenv_path=".env.local")

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Suppress noisy loggers from external libraries
import logging
for noisy_logger in [
    "httpx", "google", "google.auth", "googleapiclient", "google.cloud", "google.protobuf", "AFC"
]:
    logging.getLogger(noisy_logger).setLevel(logging.ERROR)

# --- LLM Configuration and Helpers ---

# Setup logging (ensure it's configured early)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use the new Google Gemini SDK (google-genai)
try:
    from google import genai
except ImportError as e:
    logger.error("google-genai SDK is not installed. Please install it with 'pip install google-genai'.")
    raise

# Configure the Gemini client (Requires GOOGLE_API_KEY environment variable)
try:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable not set or not loaded from .env.local.")
    client = genai.Client(api_key=GOOGLE_API_KEY)
    model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')
    logger.info(f"Gemini Client configured successfully using google-genai SDK. Model: {model_name}")
except Exception as e:
    logger.error(f"Error configuring Gemini Client: {e}")
    client = None
    logger.warning("Proceeding without LLM review capabilities.")

class LLMReviewResponseV2(BaseModel):
    canonical_name: str
    merged_names: List[str]
    rejected_names: List[str]

PROMPT_PATH = pathlib.Path(__file__).parent.parent / "cleaning" / "gemini_entity_grouping_prompt.txt"

def generate_llm_prompt(entity_names: List[str]) -> str:
    """Generates a prompt for the LLM to select a canonical name (from input), merged, and rejected names."""
    input_json = json.dumps({"entities_to_review": entity_names}, indent=2)
    with open(PROMPT_PATH, "r") as f:
        prompt_template = f.read()
    prompt = prompt_template.replace("{input_json}", input_json)
    return prompt

def extract_json_from_code_block(text: str) -> str:
    """Extract JSON object from a string, handling triple backticks and language tags."""
    import re
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        return match.group(1)
    return text  # fallback: return as is

def get_llm_review(entity_names: List[str], comm_id: int = None, iteration: int = None) -> Optional[Dict[str, Any]]:
    """Gets the LLM's review results for a group, enforcing canonical_name from input, merged_names, and rejected_names."""
    if not client:
        logger.warning("LLM client not available. Skipping review.")
        return None
    if len(entity_names) <= 1:
        return {
            'canonical_name': entity_names[0] if entity_names else '',
            'merged_names': entity_names,
            'rejected_names': []
        }
    prompt = generate_llm_prompt(entity_names)
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt],
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.0,
                    'top_p': 0.8,
                    'top_k': 40,
                    'candidate_count': 1
                }
            )
            raw_response_text = response.text.strip()
            # Try direct JSON parse first
            try:
                data = json.loads(raw_response_text)
            except json.JSONDecodeError:
                json_str = extract_json_from_code_block(raw_response_text)
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError as e:
                    context = f"Community {comm_id}: " if comm_id is not None else ""
                    logger.error(f"{context}Failed to parse Gemini response as JSON after extraction: {e}")
                    logger.error(f"{context}Response ends with: {raw_response_text[-500:]}")
                    logger.warning(f"{context}Gemini output is likely truncated or invalid (parse error). Returning None.")
                    continue
            # Validate required fields
            if not (isinstance(data, dict) and 'canonical_name' in data and 'merged_names' in data and 'rejected_names' in data):
                context = f"Community {comm_id}: " if comm_id is not None else ""
                logger.warning(f"{context}LLM response missing required keys. Response: {data}")
                continue
            canonical_name = data['canonical_name']
            merged_names = data['merged_names']
            rejected_names = data['rejected_names']
            # Validate canonical_name is in input
            if canonical_name not in entity_names:
                context = f"Community {comm_id}: " if comm_id is not None else ""
                logger.warning(f"{context}LLM selected canonical_name '{canonical_name}' not in input list. Defaulting to first input.")
                canonical_name = entity_names[0]
            # Validate merged/rejected names
            merged_names = [n for n in merged_names if n in entity_names]
            rejected_names = [n for n in rejected_names if n in entity_names]
            return {
                'canonical_name': canonical_name,
                'merged_names': merged_names,
                'rejected_names': rejected_names
            }
        except Exception as e:
            context = f"Community {comm_id}: " if comm_id is not None else ""
            logger.error(f"{context}Error calling LLM API or processing response (Attempt {attempt+1}) for group {entity_names[:3]}...: {e}")
        if attempt < max_retries - 1:
            logger.info("Retrying LLM call...")
            time.sleep(2)
    context = f"Community {comm_id}: " if comm_id is not None else ""
    logger.error(f"{context}LLM review failed after {max_retries} attempts for group {entity_names[:3]}...")
    return None

# --- Database Functions for Grouping DB ---

def create_grouping_db_tables(conn: sqlite3.Connection) -> None:
    """
    Create the entity_canonicalization table in entity_grouping.db.
    This table records, for each entity UUID, the original name and the canonical name assigned after grouping.
    UUIDs are never changed or merged; only the canonical_name is updated.
    """
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entity_canonicalization (
        entity_id TEXT PRIMARY KEY,         -- The original UUID from the main entities table
        original_name TEXT NOT NULL,        -- The original canonical_name before grouping
        canonical_name TEXT NOT NULL,       -- The canonical name assigned after grouping
        status TEXT,                        -- e.g., 'finalized', 'singleton', 'merged'
        iteration_finalized INTEGER,        -- Which iteration this entity was finalized in
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()

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

def upsert_entity_canonicalization(
    conn: sqlite3.Connection,
    entity_id: str,
    original_name: str,
    canonical_name: str,
    status: str,
    iteration_finalized: int
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO entity_canonicalization (entity_id, original_name, canonical_name, status, iteration_finalized, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(entity_id) DO UPDATE SET
            canonical_name=excluded.canonical_name,
            status=excluded.status,
            iteration_finalized=excluded.iteration_finalized,
            updated_at=CURRENT_TIMESTAMP
        """,
        (entity_id, original_name, canonical_name, status, iteration_finalized)
    )
    conn.commit()

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

# --- Output Directory Configuration ---
OUTPUT_DIR = os.path.join('outputs', 'entity_grouping')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Extraction ---
def extract_unique_entities(disclosures_db_path: str) -> List[Tuple[str, str]]:
    """
    Extract all unique (entity_id, canonical_name) pairs from the entities table in disclosures.db.
    Returns a list of (entity_id, canonical_name) tuples.
    """
    conn = sqlite3.connect(disclosures_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT entity_id, canonical_name FROM entities WHERE entity_id IS NOT NULL AND canonical_name IS NOT NULL")
    results = cursor.fetchall()
    conn.close()
    return [(str(row[0]), str(row[1])) for row in results]

# --- Vectorization & Similarity Graph ---
def build_similarity_graph(
    entities: List[Tuple[str, str]],
    threshold: float = 0.75
) -> Tuple[nx.Graph, Dict[int, Tuple[str, str]]]:
    """
    Generate embeddings for all canonical_name values, compute cosine similarity, and build a graph.
    Nodes are indexed by integer; node_map maps index to (entity_id, canonical_name).
    Edges connect nodes with similarity >= threshold.
    Returns (graph, node_map).
    """
    if not entities:
        raise ValueError("No entities provided for vectorization.")
    names = [name for _, name in entities]
    node_map = {i: entities[i] for i in range(len(entities))}
    print(f"Loading sentence transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2', device='cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Encoding {len(names)} entity names...")
    embeddings = model.encode(names, convert_to_tensor=True, show_progress_bar=True, batch_size=128)
    print("Computing cosine similarity matrix...")
    cosine_scores = util.pytorch_cos_sim(embeddings, embeddings)
    print("Building similarity graph...")
    G = nx.Graph()
    for i in range(len(names)):
        G.add_node(i)
    edge_count = 0
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            score = cosine_scores[i, j].item()
            if score >= threshold:
                G.add_edge(i, j, weight=score)
                edge_count += 1
    print(f"Graph built: {G.number_of_nodes()} nodes, {edge_count} edges (threshold={threshold})")
    return G, node_map

# --- Community Detection ---
def detect_communities_louvain(G: nx.Graph) -> Dict[int, list]:
    """
    Detect communities in the similarity graph using the Louvain algorithm.
    Returns a mapping from community_id (int) to a list of node indices.
    """
    partition = community_louvain.best_partition(G, weight='weight', random_state=42)
    communities: Dict[int, list] = {}
    for node_idx, comm_id in partition.items():
        communities.setdefault(comm_id, []).append(node_idx)
    return communities

# --- Stepwise Pipeline Functions ---
def step_extract(disclosures_db_path: str, limit: Optional[int], output_path: str = None) -> None:
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, "entities_extracted.json")
    entities = extract_unique_entities(disclosures_db_path)
    if limit is not None:
        entities = entities[:limit]
    with open(output_path, "w") as f:
        json.dump(entities, f)
    print(f"[STEP: extract] Extracted {len(entities)} entities and saved to {output_path}")

def step_vectorize(input_path: str = None, output_prefix: str = None) -> None:
    if input_path is None:
        input_path = os.path.join(OUTPUT_DIR, "entities_extracted.json")
    if output_prefix is None:
        output_prefix = os.path.join(OUTPUT_DIR, "entity_graph.json")
    with open(input_path) as f:
        entities = json.load(f)
    G, node_map = build_similarity_graph(entities)
    # Save as edge list and node map
    nx.write_edgelist(G, output_prefix + ".edgelist")
    with open(output_prefix + ".nodemap", "w") as f:
        json.dump(node_map, f)
    print(f"[STEP: vectorize] Saved graph edge list to {output_prefix}.edgelist and node map to {output_prefix}.nodemap")

def step_detect_communities(graph_path: str = None, node_map_path: str = None, output_path: str = None) -> None:
    if graph_path is None:
        graph_path = os.path.join(OUTPUT_DIR, "entity_graph.json.edgelist")
    if node_map_path is None:
        node_map_path = os.path.join(OUTPUT_DIR, "entity_graph.json.nodemap")
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, "communities.json")
    G = nx.read_edgelist(graph_path, nodetype=int)
    with open(node_map_path) as f:
        node_map = {int(k): tuple(v) for k, v in json.load(f).items()}
    communities = detect_communities_louvain(G)
    # Save as {community_id: [node indices]}
    with open(output_path, "w") as f:
        json.dump(communities, f)
    print(f"[STEP: detect_communities] Saved communities to {output_path}")

def step_llm_review(communities_path: str = None, node_map_path: str = None, output_path: str = None) -> None:
    if communities_path is None:
        communities_path = os.path.join(OUTPUT_DIR, "communities.json")
    if node_map_path is None:
        node_map_path = os.path.join(OUTPUT_DIR, "entity_graph.json.nodemap")
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, "llm_reviews.json")
    with open(communities_path) as f:
        communities = {int(k): v for k, v in json.load(f).items()}
    with open(node_map_path) as f:
        node_map = {int(k): tuple(v) for k, v in json.load(f).items()}
    results = {}
    for comm_id, members in communities.items():
        member_names = [node_map[idx][1] for idx in members]
        if len(members) == 1:
            continue
        llm_result = get_llm_review(member_names, comm_id=comm_id)
        results[comm_id] = llm_result
        if llm_result:
            canonical_name = llm_result['canonical_name']
            merged_names = llm_result['merged_names']
            rejected_names = llm_result['rejected_names']
            print(f"Community {comm_id}: Success: Canonical={canonical_name}, Merged={len(merged_names)}, Rejected={len(rejected_names)}")
        else:
            print(f"Community {comm_id}: ERROR: LLM review failed or returned invalid response.")
    with open(output_path, "w") as f:
        json.dump(results, f)
    print(f"[STEP: llm_review] Saved LLM review results to {output_path}")

MAX_ITERATIONS = 4
THRESHOLDS = [0.8, 0.75, 0.7, 0.65]  # Per-iteration cosine similarity thresholds for entity grouping

def save_json(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2)

def load_json(path):
    with open(path) as f:
        return json.load(f)

def step_iterative_grouping(initial_entities_path: str = None, grouping_db_path: str = 'entity_grouping.db'):
    """Run iterative entity grouping and canonicalization for up to MAX_ITERATIONS rounds, with variable similarity thresholds per iteration."""
    if initial_entities_path is None:
        initial_entities_path = os.path.join(OUTPUT_DIR, "entities_extracted.json")
    pool = load_json(initial_entities_path)
    # pool: List[Tuple[entity_id, canonical_name]]
    pool = [{'entity_id': eid, 'canonical_name': name} for eid, name in pool]
    singletons = {}
    iteration_logs = []
    conn = sqlite3.connect(grouping_db_path)
    create_grouping_db_tables(conn)
    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f'--- Iteration {iteration} ---')
        iter_dir = os.path.join(OUTPUT_DIR, f'iteration_{iteration}')
        os.makedirs(iter_dir, exist_ok=True)

        # Use the threshold for this iteration (or last if more iterations than thresholds)
        threshold = THRESHOLDS[iteration - 1] if iteration - 1 < len(THRESHOLDS) else THRESHOLDS[-1]

        # 1. Vectorize and build graph for current pool
        entities = [(e['entity_id'], e['canonical_name']) for e in pool]
        G, node_map = build_similarity_graph(entities, threshold=threshold)
        save_json(node_map, os.path.join(iter_dir, 'node_map.json'))
        nx.write_edgelist(G, os.path.join(iter_dir, 'graph.edgelist'))

        # 2. Community detection
        communities = detect_communities_louvain(G)
        save_json(communities, os.path.join(iter_dir, 'communities.json'))

        # 3. LLM review for each community
        llm_reviews = {}
        for comm_id, members in communities.items():
            member_names = [node_map[idx][1] for idx in members]
            if len(members) == 1:
                # Track singleton
                singletons.setdefault(member_names[0], 0)
                singletons[member_names[0]] += 1
                continue
            llm_result = get_llm_review(member_names, comm_id=comm_id)
            llm_reviews[comm_id] = llm_result
        save_json(llm_reviews, os.path.join(iter_dir, 'llm_reviews.json'))

        # 4. Update pool for next iteration and update canonicalization table
        new_pool = []
        used_entity_ids = set()
        # Build a reverse lookup: name -> entity_id from node_map
        name_to_entity_id = {original_name: entity_id for idx, (entity_id, original_name) in node_map.items()}
        status_map = {}  # entity_id -> status for this iteration
        for comm_id, review in llm_reviews.items():
            if not review:
                continue
            canonical_name = review['canonical_name']
            merged_names = review['merged_names']
            # Mark canonical entity as 'canonical', others as 'merged'
            if canonical_name in name_to_entity_id:
                eid = name_to_entity_id[canonical_name]
                status_map[eid] = 'canonical'
            for name in merged_names:
                if name != canonical_name and name in name_to_entity_id:
                    eid = name_to_entity_id[name]
                    status_map[eid] = 'merged'
            for name in review['rejected_names']:
                if name in name_to_entity_id:
                    eid = name_to_entity_id[name]
                    # Rejected names are not merged, so will be handled as singleton if alone in their group
                    # We'll update their status below if needed
                    pass
            # Log merges, canonicalizations, etc.
            iteration_logs.append({'iteration': iteration, 'community': comm_id, 'review': review})
            # Print detailed log for this community
            print(f"[Iteration {iteration}] Community {comm_id}:\n  Canonical: {canonical_name}\n  Merged: {merged_names}\n  Rejected: {review['rejected_names']}")
            # Update canonicalization table for all merged entities
            for idx, (entity_id, original_name) in node_map.items():
                if original_name == canonical_name:
                    upsert_entity_canonicalization(
                        conn=conn,
                        entity_id=entity_id,
                        original_name=original_name,
                        canonical_name=canonical_name,
                        status='canonical',
                        iteration_finalized=iteration
                    )
                elif original_name in merged_names:
                    upsert_entity_canonicalization(
                        conn=conn,
                        entity_id=entity_id,
                        original_name=original_name,
                        canonical_name=canonical_name,
                        status='merged',
                        iteration_finalized=iteration
                    )
        # Add singletons that haven't reached MAX_ITERATIONS
        for name, count in singletons.items():
            if name in name_to_entity_id:
                eid = name_to_entity_id[name]
                # Check previous status in DB
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM entity_canonicalization WHERE entity_id = ?", (eid,))
                row = cursor.fetchone()
                previous_status = row[0] if row else None
                if previous_status == 'canonical':
                    status_map[eid] = 'canonical'
                    upsert_entity_canonicalization(
                        conn=conn,
                        entity_id=eid,
                        original_name=name,
                        canonical_name=name,
                        status='canonical',
                        iteration_finalized=iteration
                    )
                else:
                    status_map[eid] = 'singleton'
                    upsert_entity_canonicalization(
                        conn=conn,
                        entity_id=eid,
                        original_name=name,
                        canonical_name=name,
                        status='singleton',
                        iteration_finalized=iteration
                    )
        # Only pool canonical and singleton entities for next iteration
        for eid, status in status_map.items():
            if status in ('singleton', 'canonical') and eid not in used_entity_ids:
                # Fetch the latest canonical name for this eid from the DB
                cursor = conn.cursor()
                cursor.execute("SELECT canonical_name FROM entity_canonicalization WHERE entity_id = ?", (eid,))
                row = cursor.fetchone()
                canonical_name = row[0] if row else None
                if canonical_name:
                    new_pool.append({'entity_id': eid, 'canonical_name': canonical_name})
                    used_entity_ids.add(eid)
        pool = new_pool
        save_json(pool, os.path.join(iter_dir, 'pool.json'))

        if not pool:
            print('No more entities to group. Stopping early.')
            break

    # Save final logs and finalized singletons
    save_json(iteration_logs, os.path.join(OUTPUT_DIR, 'iteration_logs.json'))
    # Save final pool
    save_json(pool, os.path.join(OUTPUT_DIR, 'final_pool.json'))
    conn.close()
    print(f"[STEP: iterative_grouping] Completed {iteration} iterations. Logs and final pool saved.")

# --- CLI Entrypoint ---
def main():
    parser = argparse.ArgumentParser(description="Entity grouping pipeline (stepwise CLI)")
    parser.add_argument('--step', type=str, choices=['extract', 'vectorize', 'detect_communities', 'llm_review', 'merge', 'persist', 'export', 'iterative_grouping', 'all'], default='all', help='Pipeline step to run')
    parser.add_argument('--disclosures_db_path', type=str, default='disclosures.db', help='Path to the source disclosures SQLite database file.')
    parser.add_argument('--grouping_db_path', type=str, default=os.path.join(OUTPUT_DIR, 'entity_grouping.db'), help='Path to the entity grouping results SQLite database file.')
    parser.add_argument('--limit', type=int, default=None, help='Limit the number of entities fetched for testing.')
    args = parser.parse_args()

    if args.step == 'extract':
        step_extract(args.disclosures_db_path, args.limit)
    elif args.step == 'vectorize':
        step_vectorize()
    elif args.step == 'detect_communities':
        step_detect_communities()
    elif args.step == 'iterative_grouping':
        step_iterative_grouping(grouping_db_path=args.grouping_db_path)
    elif args.step == 'all':
        step_extract(args.disclosures_db_path, args.limit)
        step_iterative_grouping(grouping_db_path=args.grouping_db_path)
    else:
        print(f"[ERROR] Step '{args.step}' not implemented yet.")

if __name__ == "__main__":
    main()

