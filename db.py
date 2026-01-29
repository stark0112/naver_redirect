import psycopg
from psycopg.rows import dict_row
import os
from datetime import datetime

def get_db_connection():
    """Create and return a database connection"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise Exception('DATABASE_URL environment variable is not set')

    conn = psycopg.connect(database_url, row_factory=dict_row)
    return conn

def init_db():
    """Initialize database schema"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS links (
            code VARCHAR(11) PRIMARY KEY,
            product_name VARCHAR(255) DEFAULT '',
            queries TEXT[] NOT NULL DEFAULT '{}',
            acqs TEXT[] NOT NULL DEFAULT '{}',
            clicks INTEGER DEFAULT 0,
            click_history TIMESTAMP[] DEFAULT '{}',
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_links_created_at ON links(created_at DESC)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_links_code ON links(code)
    """)

    conn.commit()
    cur.close()
    conn.close()

def get_all_links():
    """Get all links from database"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT code, product_name, queries, acqs, clicks,
               click_history, created_at
        FROM links
        ORDER BY created_at DESC
    """)

    links = cur.fetchall()
    cur.close()
    conn.close()

    return [dict(link) for link in links]

def get_link_by_code(code):
    """Get a specific link by code"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT code, product_name, queries, acqs, clicks,
               click_history, created_at
        FROM links
        WHERE code = %s
    """, (code,))

    link = cur.fetchone()
    cur.close()
    conn.close()

    return dict(link) if link else None

def create_link(code, product_name, queries, acqs):
    """Create a new link"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO links (code, product_name, queries, acqs, clicks, click_history, created_at)
        VALUES (%s, %s, %s, %s, 0, %s, %s)
        RETURNING code, product_name, queries, acqs, clicks, created_at
    """, (code, product_name, queries, acqs, [], datetime.now()))

    link = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return dict(link) if link else None

def delete_link(code):
    """Delete a link by code"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM links WHERE code = %s", (code,))
    deleted_count = cur.rowcount

    conn.commit()
    cur.close()
    conn.close()

    return deleted_count > 0

def increment_click(code):
    """Increment click count and add to click history"""
    conn = get_db_connection()
    cur = conn.cursor()

    now = datetime.now()

    cur.execute("""
        UPDATE links
        SET clicks = clicks + 1,
            click_history = array_append(click_history, %s)
        WHERE code = %s
        RETURNING clicks
    """, (now, code))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return result['clicks'] if result else None

def add_query(code, query):
    """Add a query to a link"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE links
        SET queries = array_append(queries, %s)
        WHERE code = %s
        RETURNING queries
    """, (query, code))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return result['queries'] if result else None

def update_query(code, index, new_query):
    """Update a query at specific index"""
    conn = get_db_connection()
    cur = conn.cursor()

    # PostgreSQL arrays are 1-indexed
    cur.execute("""
        UPDATE links
        SET queries[%s] = %s
        WHERE code = %s
        RETURNING queries
    """, (index + 1, new_query, code))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return result['queries'] if result else None

def delete_query(code, index):
    """Delete a query at specific index"""
    conn = get_db_connection()
    cur = conn.cursor()

    # First get current queries
    cur.execute("SELECT queries FROM links WHERE code = %s", (code,))
    result = cur.fetchone()

    if not result:
        cur.close()
        conn.close()
        return None

    queries = list(result['queries'])
    if index < 0 or index >= len(queries):
        cur.close()
        conn.close()
        return None

    # Remove the query at index
    queries.pop(index)

    # Update with new array
    cur.execute("""
        UPDATE links
        SET queries = %s
        WHERE code = %s
        RETURNING queries
    """, (queries, code))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return result['queries'] if result else None

def add_acq(code, acq):
    """Add an acq to a link"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE links
        SET acqs = array_append(acqs, %s)
        WHERE code = %s
        RETURNING acqs
    """, (acq, code))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return result['acqs'] if result else None

def update_acq(code, index, new_acq):
    """Update an acq at specific index"""
    conn = get_db_connection()
    cur = conn.cursor()

    # PostgreSQL arrays are 1-indexed
    cur.execute("""
        UPDATE links
        SET acqs[%s] = %s
        WHERE code = %s
        RETURNING acqs
    """, (index + 1, new_acq, code))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return result['acqs'] if result else None

def delete_acq(code, index):
    """Delete an acq at specific index"""
    conn = get_db_connection()
    cur = conn.cursor()

    # First get current acqs
    cur.execute("SELECT acqs FROM links WHERE code = %s", (code,))
    result = cur.fetchone()

    if not result:
        cur.close()
        conn.close()
        return None

    acqs = list(result['acqs'])
    if index < 0 or index >= len(acqs):
        cur.close()
        conn.close()
        return None

    # Remove the acq at index
    acqs.pop(index)

    # Update with new array
    cur.execute("""
        UPDATE links
        SET acqs = %s
        WHERE code = %s
        RETURNING acqs
    """, (acqs, code))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return result['acqs'] if result else None

def get_stats():
    """Get dashboard statistics"""
    conn = get_db_connection()
    cur = conn.cursor()

    # Get total stats
    cur.execute("""
        SELECT
            COUNT(*) as total_links,
            COALESCE(SUM(array_length(queries, 1)), 0) + COALESCE(SUM(array_length(acqs, 1)), 0) as total_keywords,
            COALESCE(SUM(clicks), 0) as total_clicks
        FROM links
    """)

    stats = cur.fetchone()

    # Get today's clicks
    cur.execute("""
        SELECT COUNT(*) as today_clicks
        FROM links, unnest(click_history) as click_time
        WHERE DATE(click_time) = CURRENT_DATE
    """)

    today_result = cur.fetchone()
    today_clicks = today_result['today_clicks'] if today_result else 0

    # Get recent links
    cur.execute("""
        SELECT code, product_name,
               COALESCE(array_length(queries, 1), 0) + COALESCE(array_length(acqs, 1), 0) as keyword_count,
               clicks, created_at
        FROM links
        ORDER BY created_at DESC
        LIMIT 5
    """)

    recent_links = cur.fetchall()

    cur.close()
    conn.close()

    return {
        'totalLinks': stats['total_links'],
        'totalKeywords': stats['total_keywords'],
        'totalClicks': stats['total_clicks'],
        'todayClicks': today_clicks,
        'recentLinks': [dict(link) for link in recent_links]
    }
