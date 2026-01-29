from flask import Flask, render_template, jsonify, request, redirect
import random
import string
from datetime import datetime
import db

app = Flask(__name__)

def generate_code(length=11):
    """Generate random alphanumeric code"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_ackey():
    """Generate random 8-character ackey"""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(8))

# ===== ROUTES =====

@app.route('/')
def index():
    """Main admin page"""
    return render_template('index.html')

@app.route('/r/<code>')
def redirect_link(code):
    """Redirect to random Naver search URL"""
    link = db.get_link_by_code(code)

    if not link:
        return "Link not found", 404

    # Increment click count
    db.increment_click(code)

    # Choose random query and acq separately
    query = random.choice(link['queries'])
    acq = random.choice(link['acqs'])

    # Generate random parameters
    ackey = generate_ackey()
    acr = random.randint(0, 10)

    # Build Naver URL
    url = f"https://m.search.naver.com/search.naver?sm=mtp_sug.top&where=m&query={query}&ackey={ackey}&acq={acq}&acr={acr}&qdt=0"

    return redirect(url)

# ===== API ROUTES =====

@app.route('/api/stats')
def get_stats():
    """Get dashboard statistics"""
    stats = db.get_stats()

    # Format recent links
    recent_links_data = [{
        'code': link['code'],
        'keywordCount': link['keyword_count'],
        'clicks': link['clicks'],
        'createdAt': link['created_at'].isoformat()
    } for link in stats['recentLinks']]

    return jsonify({
        'totalLinks': stats['totalLinks'],
        'totalKeywords': stats['totalKeywords'],
        'totalClicks': stats['totalClicks'],
        'todayClicks': stats['todayClicks'],
        'recentLinks': recent_links_data
    })

@app.route('/api/links', methods=['GET'])
def get_links():
    """Get all links"""
    links = db.get_all_links()

    links_data = [{
        'code': link['code'],
        'productName': link.get('product_name', ''),
        'keywordCount': len(link.get('queries', [])) + len(link.get('acqs', [])),
        'clicks': link.get('clicks', 0),
        'createdAt': link['created_at'].isoformat()
    } for link in links]

    return jsonify({'links': links_data})

@app.route('/api/links/<code>', methods=['GET'])
def get_link(code):
    """Get specific link details"""
    link = db.get_link_by_code(code)

    if not link:
        return jsonify({'error': 'Link not found'}), 404

    return jsonify({
        'code': link['code'],
        'productName': link.get('product_name', ''),
        'queries': link.get('queries', []),
        'acqs': link.get('acqs', []),
        'keywords': [],  # Backward compatibility
        'clicks': link.get('clicks', 0),
        'createdAt': link['created_at'].isoformat()
    })

@app.route('/api/links', methods=['POST'])
def create_link():
    """Create new redirect link"""
    req_data = request.json

    product_name = req_data.get('productName', '')
    queries = req_data.get('queries', [])
    acqs = req_data.get('acqs', [])
    keywords = req_data.get('keywords', [])  # Backward compatibility

    # Support both new format (queries/acqs) and old format (keywords)
    if queries and acqs:
        # New format
        if not queries or not acqs:
            return jsonify({'error': 'At least one query and one acq is required'}), 400
    elif keywords:
        # Old format - convert to new format
        queries = [k['query'] for k in keywords]
        acqs = [k['acq'] for k in keywords]
    else:
        return jsonify({'error': 'At least one query and one acq is required'}), 400

    # Generate unique code
    all_links = db.get_all_links()
    existing_codes = {link['code'] for link in all_links}

    code = generate_code()
    while code in existing_codes:
        code = generate_code()

    # Create new link
    new_link = db.create_link(code, product_name, queries, acqs)

    return jsonify({
        'code': new_link['code'],
        'productName': new_link['product_name'],
        'queries': new_link['queries'],
        'acqs': new_link['acqs'],
        'createdAt': new_link['created_at'].isoformat()
    }), 201

@app.route('/api/links/<code>', methods=['DELETE'])
def delete_link(code):
    """Delete a link"""
    deleted = db.delete_link(code)

    if not deleted:
        return jsonify({'error': 'Link not found'}), 404

    return jsonify({'message': 'Link deleted'}), 200

@app.route('/api/links/<code>/queries', methods=['POST'])
def add_query(code):
    """Add a query to a link"""
    req_data = request.json

    query = req_data.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query is required'}), 400

    # Add query
    queries = db.add_query(code, query)

    if queries is None:
        return jsonify({'error': 'Link not found'}), 404

    return jsonify({'message': 'Query added', 'queries': queries}), 200

@app.route('/api/links/<code>/queries/<int:index>', methods=['DELETE'])
def delete_query(code, index):
    """Delete a query from a link"""
    # Get current link to check constraints
    link = db.get_link_by_code(code)

    if not link:
        return jsonify({'error': 'Link not found'}), 404

    queries = link.get('queries', [])
    if index < 0 or index >= len(queries):
        return jsonify({'error': 'Invalid index'}), 400

    # Prevent deleting last query
    if len(queries) <= 1:
        return jsonify({'error': 'Cannot delete last query'}), 400

    # Delete query
    updated_queries = db.delete_query(code, index)

    if updated_queries is None:
        return jsonify({'error': 'Failed to delete query'}), 500

    return jsonify({'message': 'Query deleted', 'queries': updated_queries}), 200

@app.route('/api/links/<code>/queries/<int:index>', methods=['PUT'])
def update_query(code, index):
    """Update a query in a link"""
    req_data = request.json

    new_query = req_data.get('query', '').strip()
    if not new_query:
        return jsonify({'error': 'Query is required'}), 400

    # Get current link to check constraints
    link = db.get_link_by_code(code)

    if not link:
        return jsonify({'error': 'Link not found'}), 404

    queries = link.get('queries', [])
    if index < 0 or index >= len(queries):
        return jsonify({'error': 'Invalid index'}), 400

    # Update query
    updated_queries = db.update_query(code, index, new_query)

    if updated_queries is None:
        return jsonify({'error': 'Failed to update query'}), 500

    return jsonify({'message': 'Query updated', 'queries': updated_queries}), 200

@app.route('/api/links/<code>/acqs', methods=['POST'])
def add_acq(code):
    """Add an acq to a link"""
    req_data = request.json

    acq = req_data.get('acq', '').strip()
    if not acq:
        return jsonify({'error': 'Acq is required'}), 400

    # Add acq
    acqs = db.add_acq(code, acq)

    if acqs is None:
        return jsonify({'error': 'Link not found'}), 404

    return jsonify({'message': 'Acq added', 'acqs': acqs}), 200

@app.route('/api/links/<code>/acqs/<int:index>', methods=['DELETE'])
def delete_acq(code, index):
    """Delete an acq from a link"""
    # Get current link to check constraints
    link = db.get_link_by_code(code)

    if not link:
        return jsonify({'error': 'Link not found'}), 404

    acqs = link.get('acqs', [])
    if index < 0 or index >= len(acqs):
        return jsonify({'error': 'Invalid index'}), 400

    # Prevent deleting last acq
    if len(acqs) <= 1:
        return jsonify({'error': 'Cannot delete last acq'}), 400

    # Delete acq
    updated_acqs = db.delete_acq(code, index)

    if updated_acqs is None:
        return jsonify({'error': 'Failed to delete acq'}), 500

    return jsonify({'message': 'Acq deleted', 'acqs': updated_acqs}), 200

@app.route('/api/links/<code>/acqs/<int:index>', methods=['PUT'])
def update_acq(code, index):
    """Update an acq in a link"""
    req_data = request.json

    new_acq = req_data.get('acq', '').strip()
    if not new_acq:
        return jsonify({'error': 'Acq is required'}), 400

    # Get current link to check constraints
    link = db.get_link_by_code(code)

    if not link:
        return jsonify({'error': 'Link not found'}), 404

    acqs = link.get('acqs', [])
    if index < 0 or index >= len(acqs):
        return jsonify({'error': 'Invalid index'}), 400

    # Update acq
    updated_acqs = db.update_acq(code, index, new_acq)

    if updated_acqs is None:
        return jsonify({'error': 'Failed to update acq'}), 500

    return jsonify({'message': 'Acq updated', 'acqs': updated_acqs}), 200

# ===== INITIALIZATION =====
# Initialize database on startup
try:
    db.init_db()
except Exception as e:
    print(f"Warning: Could not initialize database: {e}")
    print("Make sure DATABASE_URL environment variable is set")

# ===== RUN =====
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
