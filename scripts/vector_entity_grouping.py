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


"""
Script to identify similar named entities from an SQLite database using sentence-transformer embeddings.

This script performs the following steps:
1. Connects to a local SQLite database and fetches distinct `normalized_entity` values from the `disclosures` table.
2. Generates sentence embeddings for each entity using the `all-MiniLM-L6-v2` model from the `sentence-transformers` library.
3. Computes pairwise cosine similarity between all entities.
4. Prints the top 3 most similar entities for each entry (excluding itself).

Requirements:
- `sentence-transformers`
- `torch`
- A modern virtual environment (e.g., Python's `venv` or `virtualenv`) is **recommended** over Conda environments.

Why use a `venv`:
- On macOS, using `torch` with multiprocessing in Conda environments can cause segmentation faults due to issues with the `resource_tracker` and leaked semaphore objects.
- This script explicitly sets the multiprocessing start method to `"spawn"` to avoid these issues, but even then, Conda's integration with `torch` on macOS may still lead to crashes.
- Running the script in a clean `venv` has been observed to resolve these errors reliably.

Environment variable:
- `KMP_DUPLICATE_LIB_OK = TRUE` is set to suppress warnings from Intel's MKL used by PyTorch on macOS.

Usage:
- Ensure the database path is correctly set in the `DB_PATH` variable.
- Run the script from a `venv` environment to avoid platform-specific multiprocessing issues.
"""


os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# --- Database Functions for Grouping DB ---

def create_grouping_db_tables(conn):
    cursor = conn.cursor()
    # Communities Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entity_communities (
        community_id INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_name TEXT NOT NULL,
        iteration INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_review', -- pending_review, confirmed, rejected
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Community Members Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entity_community_members (
        member_id INTEGER PRIMARY KEY AUTOINCREMENT,
        community_id INTEGER NOT NULL,
        normalized_entity TEXT NOT NULL,
        FOREIGN KEY (community_id) REFERENCES entity_communities (community_id)
    )
    """)
    # Index for faster lookup
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_member_entity ON entity_community_members (normalized_entity)")
    conn.commit()

def get_confirmed_entities(conn):
    cursor = conn.cursor()
    cursor.execute("""
    SELECT DISTINCT m.normalized_entity
    FROM entity_community_members m
    JOIN entity_communities c ON m.community_id = c.community_id
    WHERE c.status = 'confirmed'
    """)
    confirmed = {row[0] for row in cursor.fetchall()}
    return confirmed

def save_communities_to_db(conn, communities_dict, iteration):
    cursor = conn.cursor()
    saved_count = 0
    for canonical_name, members in communities_dict.items():
        # Insert into entity_communities
        cursor.execute("""
        INSERT INTO entity_communities (canonical_name, iteration, status)
        VALUES (?, ?, ?)
        """, (canonical_name, iteration, 'pending_review'))
        community_id = cursor.lastrowid

        # Insert members into entity_community_members
        member_data = [(community_id, member) for member in members]
        cursor.executemany("""
        INSERT INTO entity_community_members (community_id, normalized_entity)
        VALUES (?, ?)
        """, member_data)
        saved_count += 1
    conn.commit()
    return saved_count

# --- Arguments ---
def parse_args():
    parser = argparse.ArgumentParser(description='Group similar entities using sentence embeddings and community detection, saving results to a database.')
    parser.add_argument('--disclosures_db_path', type=str, default='/Users/kevin/Documents/ProgrammingIsFun/PersonalProjects/g0v/aus-govt-transparency/disclosures.db', help='Path to the source disclosures SQLite database file.')
    parser.add_argument('--grouping_db_path', type=str, default='entity_grouping.db', help='Path to the entity grouping results SQLite database file.')
    parser.add_argument('--threshold', type=float, default=0.75, help='Cosine similarity threshold for building the graph.')
    parser.add_argument('--iteration', type=int, default=1, help='Current iteration number for grouping.')
    parser.add_argument('--limit', type=int, default=None, help='Limit the number of entities fetched for testing.')
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

    final_communities_output = {}
    multi_member_community_count = 0
    single_member_community_count = 0

    if edge_count > 0:
        print("Detecting communities using Louvain algorithm...")
        partition = community_louvain.best_partition(G, weight='weight', random_state=42)

        communities_by_id = {}
        for node_index, community_id in partition.items():
            if community_id not in communities_by_id:
                communities_by_id[community_id] = []
            communities_by_id[community_id].append(node_index)
        print(f"Found {len(communities_by_id)} raw communities.")

        print("\n--- Processing Communities for Output ---")
        processed_indices = set()
        for community_id, members_indices in communities_by_id.items():
            if any(idx in processed_indices for idx in members_indices):
                 continue

            member_names = sorted([entities_to_process[idx] for idx in members_indices])

            if len(member_names) > 1:
                multi_member_community_count += 1
                canonical_name = member_names[0]
                final_communities_output[canonical_name] = member_names
                for idx in members_indices:
                    processed_indices.add(idx)
            elif len(member_names) == 1:
                 node_index = members_indices[0]
                 if node_index not in processed_indices:
                    single_member_community_count += 1
                    processed_indices.add(node_index)

        print(f"Processed into {multi_member_community_count} multi-member communities.")
        print(f"Identified {single_member_community_count} single-member communities (not saved).")
    else:
        print("No edges created at the specified threshold. No communities to save.")
        # All entities are single-member communities
        single_member_community_count = len(entities_to_process)
        print(f"Identified {single_member_community_count} single-member communities (not saved).")

    # --- Save Results to Grouping DB ---
    if multi_member_community_count > 0:
        print(f"\nSaving {multi_member_community_count} communities to {GROUPING_DB_PATH} for iteration {ITERATION}...")
        saved_count = save_communities_to_db(conn_grouping, final_communities_output, ITERATION)
        print(f"Successfully saved {saved_count} communities.")
    else:
        print("\nNo multi-member communities found to save.")

    conn_grouping.close()

    end_time = time.time()
    print(f"\nScript finished in {end_time - start_time:.2f} seconds.")
    print("Done.")

