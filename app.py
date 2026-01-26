from flask import Flask, render_template, jsonify, request, redirect
import json
import os
import random
import string
from datetime import datetime, timedelta

app = Flask(__name__)

# Data file path
DATA_FILE = 'data.json'

# Initialize data file if not exists
def init_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({'links': []}, f, ensure_ascii=False, indent=2)

def load_data():
    init_data()
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
    data = load_data()

    # Find link by code
    link = None
    for l in data['links']:
        if l['code'] == code:
            link = l
            break

    if not link:
        return "Link not found", 404

    # Increment click count
    link['clicks'] = link.get('clicks', 0) + 1

    # Add click timestamp
    now = datetime.now().isoformat()
    if 'clickHistory' not in link:
        link['clickHistory'] = []
    link['clickHistory'].append(now)

    save_data(data)

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
    data = load_data()
    links = data['links']

    total_links = len(links)
    total_keywords = sum(len(link.get('queries', [])) + len(link.get('acqs', [])) for link in links)
    total_clicks = sum(link.get('clicks', 0) for link in links)

    # Calculate today's clicks
    today = datetime.now().date()
    today_clicks = 0

    for link in links:
        if 'clickHistory' in link:
            for click_time in link['clickHistory']:
                click_date = datetime.fromisoformat(click_time).date()
                if click_date == today:
                    today_clicks += 1

    # Get recent links (top 5)
    recent_links = sorted(links, key=lambda x: x['createdAt'], reverse=True)[:5]
    recent_links_data = [{
        'code': link['code'],
        'keywordCount': len(link.get('queries', [])) + len(link.get('acqs', [])),
        'clicks': link.get('clicks', 0),
        'createdAt': link['createdAt']
    } for link in recent_links]

    return jsonify({
        'totalLinks': total_links,
        'totalKeywords': total_keywords,
        'totalClicks': total_clicks,
        'todayClicks': today_clicks,
        'recentLinks': recent_links_data
    })

@app.route('/api/links', methods=['GET'])
def get_links():
    """Get all links"""
    data = load_data()

    links_data = [{
        'code': link['code'],
        'productName': link.get('productName', ''),
        'keywordCount': len(link.get('queries', [])) + len(link.get('acqs', [])),
        'clicks': link.get('clicks', 0),
        'createdAt': link['createdAt']
    } for link in data['links']]

    # Sort by creation date (newest first)
    links_data.sort(key=lambda x: x['createdAt'], reverse=True)

    return jsonify({'links': links_data})

@app.route('/api/links/<code>', methods=['GET'])
def get_link(code):
    """Get specific link details"""
    data = load_data()

    link = None
    for l in data['links']:
        if l['code'] == code:
            link = l
            break

    if not link:
        return jsonify({'error': 'Link not found'}), 404

    return jsonify({
        'code': link['code'],
        'productName': link.get('productName', ''),
        'queries': link.get('queries', []),
        'acqs': link.get('acqs', []),
        'keywords': link.get('keywords', []),  # Backward compatibility
        'clicks': link.get('clicks', 0),
        'createdAt': link['createdAt']
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
    data = load_data()
    existing_codes = {link['code'] for link in data['links']}

    code = generate_code()
    while code in existing_codes:
        code = generate_code()

    # Create new link
    new_link = {
        'code': code,
        'productName': product_name,
        'queries': queries,
        'acqs': acqs,
        'clicks': 0,
        'clickHistory': [],
        'createdAt': datetime.now().isoformat()
    }

    data['links'].append(new_link)
    save_data(data)

    return jsonify({
        'code': code,
        'productName': product_name,
        'queries': queries,
        'acqs': acqs,
        'createdAt': new_link['createdAt']
    }), 201

@app.route('/api/links/<code>', methods=['DELETE'])
def delete_link(code):
    """Delete a link"""
    data = load_data()

    # Find and remove link
    original_length = len(data['links'])
    data['links'] = [l for l in data['links'] if l['code'] != code]

    if len(data['links']) == original_length:
        return jsonify({'error': 'Link not found'}), 404

    save_data(data)
    return jsonify({'message': 'Link deleted'}), 200

# ===== INITIALIZATION =====
# Initialize data on startup
init_data()

# ===== RUN =====
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
