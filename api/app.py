import os
import sqlite3
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from dotenv import load_dotenv
from db_handler import DatabaseHandler

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Get database path from environment variable
DB_PATH = os.getenv('DB_PATH', '/Users/kevin/Documents/ProgrammingIsFun/PersonalProjects/g0v/aus-govt-transparency/disclosures.db')

# Path to the PDFs directory
PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'pdfs')

def get_db_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/disclosures', methods=['GET'])
def get_disclosures():
    """Get disclosures with filtering options."""
    # Get query parameters
    mp_name = request.args.get('mp_name', None)
    category = request.args.get('category', None)
    entity = request.args.get('entity', None)
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    filter_nil = request.args.get('filter_nil', 'true').lower() == 'true'
    
    # Build query
    query = """
        SELECT * FROM disclosures
        WHERE 1=1
    """
    params = []
    
    if mp_name:
        query += " AND mp_name LIKE ?"
        params.append(f'%{mp_name}%')
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if entity:
        query += " AND entity LIKE ?"
        params.append(f'%{entity}%')
    
    query += " ORDER BY declaration_date DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    # Execute query
    conn = get_db_connection()
    disclosures = conn.execute(query, params).fetchall()
    
    # Convert to list of dicts
    result = [dict(row) for row in disclosures]
    
    # Filter nil entries if requested
    if filter_nil:
        db_handler = DatabaseHandler(DB_PATH)
        result = db_handler.filter_nil_entries(result)
    
    conn.close()
    
    return jsonify(result)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics about disclosures, MPs, and entities."""
    filter_nil = request.args.get('filter_nil', 'true').lower() == 'true'
    conn = get_db_connection()
    
    # Base queries for with/without nil filtering
    if filter_nil:
        # Use a subquery to exclude nil entries
        nil_condition = """
            AND (
                (item NOT IN ('n/a', 'nil', 'none', 'unknown', '') OR item IS NULL)
                OR (entity NOT IN ('n/a', 'nil', 'none', 'unknown', '') OR entity IS NULL)
                OR (details IS NOT NULL AND details != '' AND details NOT IN ('n/a', 'nil', 'none', 'unknown'))
            )
        """
    else:
        nil_condition = ""
    
    # Get total disclosures
    total_disclosures = conn.execute(
        f'SELECT COUNT(*) as count FROM disclosures WHERE 1=1 {nil_condition}'
    ).fetchone()['count']
    
    # Get number of MPs with disclosures
    total_mps = conn.execute('SELECT COUNT(DISTINCT mp_name) as count FROM disclosures').fetchone()['count']
    
    # Get number of unique entities
    total_entities = conn.execute(
        f'''SELECT COUNT(DISTINCT entity) as count 
           FROM disclosures 
           WHERE entity IS NOT NULL AND entity != "" {nil_condition}'''
    ).fetchone()['count']
    
    # Get disclosure counts by category
    categories = conn.execute(f'''
        SELECT category, COUNT(*) as count 
        FROM disclosures 
        WHERE 1=1 {nil_condition}
        GROUP BY category 
        ORDER BY count DESC
    ''').fetchall()
    
    # Get top MPs by disclosure count
    top_mps = conn.execute(f'''
        SELECT mp_name, party, COUNT(*) as count 
        FROM disclosures
        WHERE 1=1 {nil_condition}
        GROUP BY mp_name 
        ORDER BY count DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return jsonify({
        'total_disclosures': total_disclosures,
        'total_mps': total_mps,
        'total_entities': total_entities,
        'categories': [dict(row) for row in categories],
        'top_mps': [dict(row) for row in top_mps]
    })

@app.route('/api/mps', methods=['GET'])
def get_mps():
    """Get list of MPs with filtering options."""
    # Get query parameters
    name = request.args.get('name', None)
    party = request.args.get('party', None)
    bloc = request.args.get('political_bloc', None)
    
    # Build query - Modified to handle duplicate MP names
    query = """
        WITH RankedMPs AS (
            SELECT 
                mp_name, 
                party, 
                electorate,
                political_bloc,
                ROW_NUMBER() OVER(PARTITION BY mp_name ORDER BY declaration_date DESC) as rn
        FROM disclosures
        WHERE 1=1
    """
    params = []
    
    if name:
        query += " AND mp_name LIKE ?"
        params.append(f'%{name}%')
    
    if party:
        query += " AND party = ?"
        params.append(party)
    
    if bloc:
        query += " AND political_bloc = ?"
        params.append(bloc)
    
    query += """
        )
        SELECT mp_name, party, electorate, political_bloc
        FROM RankedMPs
        WHERE rn = 1
        ORDER BY mp_name
    """
    
    # Execute query
    conn = get_db_connection()
    mps = conn.execute(query, params).fetchall()
    
    # Convert to list of dicts
    result = [dict(row) for row in mps]
    conn.close()
    
    return jsonify(result)

@app.route('/api/entities', methods=['GET'])
def get_entities():
    """
    Get a list of all unique entities.
    Optional query parameters:
    - canonical: If set to 'true', returns canonical entities
    """
    conn = get_db_connection()
    
    # Check if we should return canonical entities
    use_canonical = request.args.get('canonical', 'false').lower() == 'true'
    
    if use_canonical:
        query = """
        SELECT DISTINCT canonical_entity as entity, COUNT(*) as count
        FROM disclosures
        WHERE canonical_entity IS NOT NULL AND canonical_entity != ''
        GROUP BY canonical_entity
        ORDER BY count DESC
        """
    else:
    query = """
        SELECT DISTINCT entity, COUNT(*) as count
        FROM disclosures
        WHERE entity IS NOT NULL AND entity != ''
        GROUP BY entity
        ORDER BY count DESC
        """
    
    entities = conn.execute(query).fetchall()
    conn.close()
    
    # Convert to list of dicts
    entities_list = [{"entity": e[0], "count": e[1]} for e in entities]
    
    return jsonify(entities_list)

@app.route('/api/entity/<n>', methods=['GET'])
def get_entity(n):
    """
    Get details about a specific entity, including MPs connected to it.
    Optional query parameters:
    - canonical: If set to 'true', uses canonical entity name for lookup
    """
    conn = get_db_connection()
    
    # Check if we should use canonical entity
    use_canonical = request.args.get('canonical', 'false').lower() == 'true'
    
    if use_canonical:
        # Get information about the canonical entity
        query = """
        SELECT canonical_entity as entity, COUNT(*) as count
        FROM disclosures
        WHERE canonical_entity = ?
        GROUP BY canonical_entity
        """
        
        entity_info = conn.execute(query, (n,)).fetchone()
        
        if entity_info is None:
            conn.close()
            return jsonify({"error": "Entity not found"}), 404
        
        # Get all variant names of this canonical entity
        variant_query = """
        SELECT DISTINCT entity
        FROM disclosures
        WHERE canonical_entity = ? AND entity != canonical_entity
        """
        
        variants = conn.execute(variant_query, (n,)).fetchall()
        variant_names = [v[0] for v in variants]
        
        # Get connected MPs (from disclosures with this canonical entity)
        mp_query = """
        SELECT DISTINCT mp_name, party, electorate, political_bloc
        FROM disclosures
        WHERE canonical_entity = ?
        """
        
        connected_mps = conn.execute(mp_query, (n,)).fetchall()
        
    else:
        # Original behavior (by exact entity name)
        query = """
        SELECT entity, COUNT(*) as count
        FROM disclosures
        WHERE entity = ?
        GROUP BY entity
        """
        
        entity_info = conn.execute(query, (n,)).fetchone()
        
        if entity_info is None:
            conn.close()
            return jsonify({"error": "Entity not found"}), 404
        
        variant_names = []
        
        # Get connected MPs
        mp_query = """
        SELECT DISTINCT mp_name, party, electorate, political_bloc
        FROM disclosures
        WHERE entity = ?
        """
        
        connected_mps = conn.execute(mp_query, (n,)).fetchall()
    
    conn.close()
    
    # Convert to dict
    entity_data = {
        "entity": entity_info[0],
        "count": entity_info[1],
        "variants": variant_names,
        "connected_mps": [
            {"mp_name": mp[0], "party": mp[1], "electorate": mp[2], "political_bloc": mp[3]}
            for mp in connected_mps
        ]
    }
    
    return jsonify(entity_data)

@app.route('/api/search/entities', methods=['GET'])
def search_entities():
    """
    Search for entities by name.
    Required query parameters:
    - q: Search query
    Optional parameters:
    - canonical: If set to 'true', searches canonical entities
    - limit: Maximum number of results to return (default: 20)
    """
    search_term = request.args.get('q', '')
    if not search_term:
        return jsonify({"error": "Missing search term"}), 400
    
    use_canonical = request.args.get('canonical', 'false').lower() == 'true'
    limit = request.args.get('limit', 20, type=int)
    
    conn = get_db_connection()
    
    if use_canonical:
        query = """
        SELECT DISTINCT canonical_entity as entity, COUNT(*) as count
        FROM disclosures
        WHERE canonical_entity LIKE ?
        GROUP BY canonical_entity
        ORDER BY count DESC
        LIMIT ?
        """
    else:
        query = """
        SELECT DISTINCT entity, COUNT(*) as count
        FROM disclosures
        WHERE entity LIKE ?
        GROUP BY entity
        ORDER BY count DESC
        LIMIT ?
        """
    
    search_pattern = f"%{search_term}%"
    entities = conn.execute(query, (search_pattern, limit)).fetchall()
    conn.close()
    
    # Convert to list of dicts
    entities_list = [{"entity": e[0], "count": e[1]} for e in entities]
    
    return jsonify(entities_list)

@app.route('/api/network', methods=['GET'])
def get_network():
    """
    Get network data for entity explorer.
    Optional query parameters:
    - filter_nil: If 'true', filter out nil/n/a values (default: true)
    - canonical: If 'true', use canonical entity names (default: false)
    """
    filter_nil = request.args.get('filter_nil', 'true').lower() == 'true'
    use_canonical = request.args.get('canonical', 'false').lower() == 'true'
    
    conn = get_db_connection()
    
    # Prepare nil condition if needed
    if filter_nil:
        nil_condition = """
            AND (
                (item NOT IN ('n/a', 'nil', 'none', 'unknown', '') OR item IS NULL)
                OR (entity NOT IN ('n/a', 'nil', 'none', 'unknown', '') OR entity IS NULL)
                OR (details IS NOT NULL AND details != '' AND details NOT IN ('n/a', 'nil', 'none', 'unknown'))
            )
        """
    else:
        nil_condition = ""
    
    # Choose entity field based on canonical parameter
    entity_field = "canonical_entity" if use_canonical else "entity"
    
    # Get all MPs and their connections to entities
    query = f"""
        SELECT mp_name, party, {entity_field} as entity, COUNT(*) as weight
        FROM disclosures
        WHERE {entity_field} IS NOT NULL AND {entity_field} != '' {nil_condition}
        GROUP BY mp_name, {entity_field}
        ORDER BY weight DESC
    """
    
    connections = conn.execute(query).fetchall()
    conn.close()
    
    # Build network data
    nodes = {}
    links = []
    
    for conn in connections:
        mp_name = conn['mp_name']
        entity = conn['entity']
        party = conn['party']
        weight = conn['weight']
        
        # Add MP node if not exists
        if mp_name not in nodes:
            nodes[mp_name] = {
                'id': mp_name,
                'name': mp_name,
                'type': 'mp',
                'party': party
            }
        
        # Add entity node if not exists
        if entity not in nodes:
            nodes[entity] = {
                'id': entity,
                'name': entity,
                'type': 'entity'
            }
        
        # Add link
        links.append({
            'source': mp_name,
            'target': entity,
            'weight': weight
        })
    
    return jsonify({
        'nodes': list(nodes.values()),
        'links': links
    })

@app.route('/api/timeline', methods=['GET'])
def get_timeline():
    """Get disclosure timeline data."""
    filter_nil = request.args.get('filter_nil', 'true').lower() == 'true'
    conn = get_db_connection()
    
    # Prepare nil condition if needed
    if filter_nil:
        nil_condition = """
            AND (
                (item NOT IN ('n/a', 'nil', 'none', 'unknown', '') OR item IS NULL)
                OR (entity NOT IN ('n/a', 'nil', 'none', 'unknown', '') OR entity IS NULL)
                OR (details IS NOT NULL AND details != '' AND details NOT IN ('n/a', 'nil', 'none', 'unknown'))
            )
        """
    else:
        nil_condition = ""
    
    # Get disclosures by date
    query = f"""
        SELECT 
            substr(declaration_date, 1, 7) as month,
            COUNT(*) as count
        FROM disclosures
        WHERE declaration_date IS NOT NULL {nil_condition}
        GROUP BY month
        ORDER BY month
    """
    
    timeline = conn.execute(query).fetchall()
    
    # Get disclosures by category and date
    query_categories = f"""
        SELECT 
            substr(declaration_date, 1, 7) as month,
            category,
            COUNT(*) as count
        FROM disclosures
        WHERE declaration_date IS NOT NULL {nil_condition}
        GROUP BY month, category
        ORDER BY month, category
    """
    
    timeline_categories = conn.execute(query_categories).fetchall()
    
    # Process results
    months = {}
    for row in timeline:
        months[row['month']] = {
            'month': row['month'],
            'total': row['count'],
            'categories': {}
        }
    
    for row in timeline_categories:
        month = row['month']
        category = row['category']
        count = row['count']
        
        if month in months:
            months[month]['categories'][category] = count
    
    conn.close()
    
    return jsonify(list(months.values()))

@app.route('/api/mp/<name>', methods=['GET'])
def get_mp_details(name):
    """Get details for a specific MP, including their disclosures."""
    filter_nil = request.args.get('filter_nil', 'true').lower() == 'true'
    conn = get_db_connection()
    
    # Prepare nil condition if needed
    if filter_nil:
        nil_condition = """
            AND (
                (item NOT IN ('n/a', 'nil', 'none', 'unknown', '') OR item IS NULL)
                OR (entity NOT IN ('n/a', 'nil', 'none', 'unknown', '') OR entity IS NULL)
                OR (details IS NOT NULL AND details != '' AND details NOT IN ('n/a', 'nil', 'none', 'unknown'))
            )
        """
    else:
        nil_condition = ""
    
    # Get MP details
    mp_query = """
    SELECT DISTINCT mp_name, party, electorate, political_bloc 
    FROM disclosures 
    WHERE mp_name = ?
    LIMIT 1
    """
    mp = conn.execute(mp_query, (name,)).fetchone()
    
    if not mp:
        conn.close()
        return jsonify({'error': 'MP not found'}), 404
    
    mp_dict = dict(mp)
    
    # Get MP's disclosures
    disclosures = conn.execute(f'''
        SELECT * FROM disclosures 
        WHERE mp_name = ? {nil_condition}
        ORDER BY declaration_date DESC
    ''', (name,)).fetchall()
    
    mp_dict['disclosures'] = [dict(row) for row in disclosures]
    
    # Get disclosure counts by category
    categories = conn.execute(f'''
        SELECT category, COUNT(*) as count 
        FROM disclosures 
        WHERE mp_name = ? {nil_condition}
        GROUP BY category 
        ORDER BY count DESC
    ''', (name,)).fetchall()
    
    mp_dict['categories'] = [dict(row) for row in categories]
    
    # Get entities connected to this MP
    entities = conn.execute(f'''
        SELECT entity, COUNT(*) as count 
        FROM disclosures 
        WHERE mp_name = ? AND entity IS NOT NULL AND entity != '' {nil_condition}
        GROUP BY entity 
        ORDER BY count DESC 
        LIMIT 10
    ''', (name,)).fetchall()
    
    mp_dict['entities'] = [dict(row) for row in entities]
    
    conn.close()
    
    return jsonify(mp_dict)

@app.route('/api/pdf/<path:filename>', methods=['GET'])
def get_pdf(filename):
    """Serve PDF files."""
    # First try to locate the file directly
    if os.path.isfile(os.path.join(PDF_DIR, filename)):
        return send_from_directory(PDF_DIR, filename)
    
    # If not found, try searching in parliament subdirectories
    for parliament in os.listdir(PDF_DIR):
        parliament_dir = os.path.join(PDF_DIR, parliament)
        if os.path.isdir(parliament_dir) and os.path.isfile(os.path.join(parliament_dir, filename)):
            return send_from_directory(parliament_dir, filename)
    
    return jsonify({'error': 'PDF not found'}), 404

@app.route('/api/pdf-info/<mp_name>', methods=['GET'])
def get_pdf_info(mp_name):
    """Get information about PDFs available for a specific MP."""
    conn = get_db_connection()
    
    # Get MP's disclosures that have PDF URLs
    disclosures = conn.execute('''
        SELECT DISTINCT pdf_url, declaration_date
        FROM disclosures 
        WHERE mp_name = ? AND pdf_url IS NOT NULL AND pdf_url != ''
        ORDER BY declaration_date DESC
    ''', (mp_name,)).fetchall()
    
    pdf_info = [dict(row) for row in disclosures]
    conn.close()
    
    return jsonify(pdf_info)

@app.route('/api/nil-entries', methods=['GET'])
def get_nil_entries():
    """Get counts of nil entries in the database."""
    category = request.args.get('category', None)
    
    db_handler = DatabaseHandler(DB_PATH)
    counts = db_handler.count_nil_entries(category)
    
    # Add breakdown by category if no specific category is requested
    if not category:
        # Get all categories
        conn = get_db_connection()
        categories = conn.execute("SELECT DISTINCT category FROM disclosures").fetchall()
        conn.close()
        
        # Get counts for each category
        category_counts = {}
        for cat in categories:
            cat_name = cat['category']
            category_counts[cat_name] = db_handler.count_nil_entries(cat_name)
        
        counts['categories'] = category_counts
    
    return jsonify(counts)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3001))
    debug = os.environ.get('DEBUG', 'True').lower() in ['true', '1', 't']
    app.run(host='0.0.0.0', port=port, debug=debug)
