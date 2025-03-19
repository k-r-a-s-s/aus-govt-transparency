import os
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Get database path from environment variable
DB_PATH = os.getenv('DB_PATH', '/Users/kevin/Documents/ProgrammingIsFun/PersonalProjects/g0v/aus-govt-transparency/disclosures.db')

def get_db_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/disclosures', methods=['GET'])
def get_disclosures():
    """Get all disclosures with filtering options."""
    # Get query parameters
    mp_name = request.args.get('mp', None)
    category = request.args.get('category', None)
    entity = request.args.get('entity', None)
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    # Build query
    query = """
        SELECT d.*, m.name as mp_name, m.party
        FROM disclosures d
        JOIN mps m ON d.mp_id = m.id
        WHERE 1=1
    """
    params = []
    
    if mp_name:
        query += " AND m.name LIKE ?"
        params.append(f'%{mp_name}%')
    
    if category:
        query += " AND d.category = ?"
        params.append(category)
        
    if entity:
        query += " AND d.entity LIKE ?"
        params.append(f'%{entity}%')
    
    query += " ORDER BY d.date DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    # Execute query
    conn = get_db_connection()
    disclosures = conn.execute(query, params).fetchall()
    
    # Convert to list of dicts
    result = [dict(row) for row in disclosures]
    conn.close()
    
    return jsonify(result)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics about disclosures, MPs, and entities."""
    conn = get_db_connection()
    
    # Get total disclosures
    total_disclosures = conn.execute('SELECT COUNT(*) as count FROM disclosures').fetchone()['count']
    
    # Get number of MPs with disclosures
    total_mps = conn.execute('SELECT COUNT(DISTINCT mp_id) as count FROM disclosures').fetchone()['count']
    
    # Get number of unique entities
    total_entities = conn.execute('SELECT COUNT(DISTINCT entity) as count FROM disclosures WHERE entity IS NOT NULL AND entity != ""').fetchone()['count']
    
    # Get disclosure counts by category
    categories = conn.execute('''
        SELECT category, COUNT(*) as count 
        FROM disclosures 
        GROUP BY category 
        ORDER BY count DESC
    ''').fetchall()
    
    # Get top MPs by disclosure count
    top_mps = conn.execute('''
        SELECT m.name, m.party, COUNT(*) as count 
        FROM disclosures d
        JOIN mps m ON d.mp_id = m.id
        GROUP BY d.mp_id 
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
    
    # Build query
    query = "SELECT * FROM mps WHERE 1=1"
    params = []
    
    if name:
        query += " AND name LIKE ?"
        params.append(f'%{name}%')
    
    if party:
        query += " AND party = ?"
        params.append(party)
    
    query += " ORDER BY name"
    
    # Execute query
    conn = get_db_connection()
    mps = conn.execute(query, params).fetchall()
    
    # Convert to list of dicts
    result = [dict(row) for row in mps]
    conn.close()
    
    return jsonify(result)

@app.route('/api/entities', methods=['GET'])
def get_entities():
    """Get list of entities mentioned in disclosures."""
    # Get query parameters
    name = request.args.get('name', None)
    limit = request.args.get('limit', 100, type=int)
    
    # Build query
    query = """
        SELECT entity, COUNT(*) as count
        FROM disclosures
        WHERE entity IS NOT NULL AND entity != ''
    """
    params = []
    
    if name:
        query += " AND entity LIKE ?"
        params.append(f'%{name}%')
    
    query += " GROUP BY entity ORDER BY count DESC LIMIT ?"
    params.append(limit)
    
    # Execute query
    conn = get_db_connection()
    entities = conn.execute(query, params).fetchall()
    
    # Convert to list of dicts
    result = [dict(row) for row in entities]
    conn.close()
    
    return jsonify(result)

@app.route('/api/network', methods=['GET'])
def get_network():
    """Get network data for entity explorer."""
    conn = get_db_connection()
    
    # Get all MPs and their connections to entities
    query = """
        SELECT m.name as mp_name, m.party, d.entity, COUNT(*) as weight
        FROM disclosures d
        JOIN mps m ON d.mp_id = m.id
        WHERE d.entity IS NOT NULL AND d.entity != ''
        GROUP BY m.name, d.entity
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
    conn = get_db_connection()
    
    # Get disclosures by date
    query = """
        SELECT 
            strftime('%Y-%m', date) as month,
            COUNT(*) as count
        FROM disclosures
        WHERE date IS NOT NULL
        GROUP BY month
        ORDER BY month
    """
    
    timeline = conn.execute(query).fetchall()
    
    # Get disclosures by category and date
    query_categories = """
        SELECT 
            strftime('%Y-%m', date) as month,
            category,
            COUNT(*) as count
        FROM disclosures
        WHERE date IS NOT NULL
        GROUP BY month, category
        ORDER BY month
    """
    
    category_timeline = conn.execute(query_categories).fetchall()
    conn.close()
    
    # Format data for chart
    result = {
        'timeline': [dict(row) for row in timeline],
        'categories': [dict(row) for row in category_timeline]
    }
    
    return jsonify(result)

@app.route('/api/mp/<name>', methods=['GET'])
def get_mp_details(name):
    """Get details for a specific MP, including their disclosures."""
    conn = get_db_connection()
    
    # Get MP details
    mp = conn.execute('SELECT * FROM mps WHERE name = ?', (name,)).fetchone()
    
    if not mp:
        conn.close()
        return jsonify({'error': 'MP not found'}), 404
    
    mp_dict = dict(mp)
    
    # Get MP's disclosures
    disclosures = conn.execute('''
        SELECT * FROM disclosures 
        WHERE mp_id = ? 
        ORDER BY date DESC
    ''', (mp['id'],)).fetchall()
    
    mp_dict['disclosures'] = [dict(row) for row in disclosures]
    
    # Get disclosure counts by category
    categories = conn.execute('''
        SELECT category, COUNT(*) as count 
        FROM disclosures 
        WHERE mp_id = ?
        GROUP BY category 
        ORDER BY count DESC
    ''', (mp['id'],)).fetchall()
    
    mp_dict['categories'] = [dict(row) for row in categories]
    
    # Get entities connected to this MP
    entities = conn.execute('''
        SELECT entity, COUNT(*) as count 
        FROM disclosures 
        WHERE mp_id = ? AND entity IS NOT NULL AND entity != ''
        GROUP BY entity 
        ORDER BY count DESC 
        LIMIT 10
    ''', (mp['id'],)).fetchall()
    
    mp_dict['entities'] = [dict(row) for row in entities]
    
    conn.close()
    
    return jsonify(mp_dict)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3001))
    debug = os.environ.get('DEBUG', 'True').lower() in ['true', '1', 't']
    app.run(host='0.0.0.0', port=port, debug=debug)
