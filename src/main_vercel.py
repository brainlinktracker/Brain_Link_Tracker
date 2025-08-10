from flask import Flask, request, jsonify, send_file, redirect, render_template_string, send_from_directory
from flask_cors import CORS
import os
import hashlib
import secrets
import time
import requests
import json
from datetime import datetime, timedelta
import uuid
# from PIL import Image  # Commented out for Vercel compatibility
import io
import base64
from urllib.parse import urlparse
import socket
import dns.resolver
import geoip2.database
import geoip2.errors
from user_agents import parse
import bcrypt
from functools import wraps

# Database imports - using PostgreSQL for Vercel
try:
    import psycopg2
    from psycopg2 import Error, sql
    DATABASE_TYPE = "postgresql"
except ImportError:
    # Fallback to SQLite for local development
    import sqlite3
    DATABASE_TYPE = "sqlite"

app = Flask(__name__, static_folder='static')
CORS(app, origins="*")

# Configuration
SECRET_KEY = os.environ.get("SECRET_KEY", "7th-brain-advanced-link-tracker-secret-2024")
app.config['SECRET_KEY'] = SECRET_KEY

# Database configuration
if DATABASE_TYPE == "postgresql":
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_0y9XMKzHCBsN@ep-blue-resonance-add39g5q-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
else:
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "database", "app.db")

def get_db_connection():
    """Get a database connection"""
    if DATABASE_TYPE == "postgresql":
        return psycopg2.connect(DATABASE_URL)
    else:
        return sqlite3.connect(DATABASE_PATH)

# Initialize database
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DATABASE_TYPE == "postgresql":
            # PostgreSQL table creation
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL DEFAULT 'member',
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    parent_id INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP WITH TIME ZONE,
                    subscription_status VARCHAR(50) DEFAULT 'inactive',
                    subscription_expires TIMESTAMP WITH TIME ZONE,
                    FOREIGN KEY (parent_id) REFERENCES users (id)
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    permission VARCHAR(255) NOT NULL,
                    granted_by INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (granted_by) REFERENCES users (id)
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    session_token VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'active',
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracking_links (
                    id SERIAL PRIMARY KEY,
                    campaign_id INTEGER,
                    user_id INTEGER NOT NULL,
                    original_url TEXT NOT NULL,
                    tracking_token VARCHAR(255) UNIQUE NOT NULL,
                    recipient_email VARCHAR(255),
                    recipient_name VARCHAR(255),
                    link_status VARCHAR(50) DEFAULT 'active',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    click_limit INTEGER DEFAULT 0,
                    click_count INTEGER DEFAULT 0,
                    last_clicked TIMESTAMP WITH TIME ZONE,
                    custom_message TEXT,
                    redirect_delay INTEGER DEFAULT 0,
                    password_protected BOOLEAN DEFAULT FALSE,
                    access_password VARCHAR(255),
                    geo_restrictions TEXT,
                    device_restrictions TEXT,
                    time_restrictions TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracking_events (
                    id SERIAL PRIMARY KEY,
                    tracking_token VARCHAR(255) NOT NULL,
                    event_type VARCHAR(100) NOT NULL,
                    ip_address INET,
                    user_agent TEXT,
                    referrer TEXT,
                    country VARCHAR(100),
                    city VARCHAR(100),
                    device_type VARCHAR(100),
                    browser VARCHAR(100),
                    os VARCHAR(100),
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    additional_data JSONB,
                    campaign_id INTEGER,
                    user_id INTEGER,
                    is_bot BOOLEAN DEFAULT FALSE,
                    bot_confidence DECIMAL(3,2),
                    bot_reason TEXT,
                    status VARCHAR(50) DEFAULT 'processed',
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
            """)
            
        else:
            # SQLite table creation (for local development)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'member',
                    status TEXT NOT NULL DEFAULT 'pending',
                    parent_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    subscription_status TEXT DEFAULT 'inactive',
                    subscription_expires TIMESTAMP,
                    FOREIGN KEY (parent_id) REFERENCES users (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    permission TEXT NOT NULL,
                    granted_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (granted_by) REFERENCES users (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tracking_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER,
                    user_id INTEGER NOT NULL,
                    original_url TEXT NOT NULL,
                    tracking_token TEXT UNIQUE NOT NULL,
                    recipient_email TEXT,
                    recipient_name TEXT,
                    link_status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    click_limit INTEGER DEFAULT 0,
                    click_count INTEGER DEFAULT 0,
                    last_clicked TIMESTAMP,
                    custom_message TEXT,
                    redirect_delay INTEGER DEFAULT 0,
                    password_protected INTEGER DEFAULT 0,
                    access_password TEXT,
                    geo_restrictions TEXT,
                    device_restrictions TEXT,
                    time_restrictions TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tracking_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracking_token TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    referrer TEXT,
                    country TEXT,
                    city TEXT,
                    device_type TEXT,
                    browser TEXT,
                    os TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    additional_data TEXT,
                    campaign_id INTEGER,
                    user_id INTEGER,
                    is_bot INTEGER DEFAULT 0,
                    bot_confidence REAL,
                    bot_reason TEXT,
                    status TEXT DEFAULT 'processed',
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
        
        # Check if admin user exists
        if DATABASE_TYPE == "postgresql":
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        else:
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        
        admin_count = cursor.fetchone()[0]
        
        if admin_count == 0:
            # Create default admin user
            admin_password = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            if DATABASE_TYPE == "postgresql":
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, role, status)
                    VALUES (%s, %s, %s, %s, %s)
                """, ("admin", "admin@brainlinktracker.com", admin_password, "admin", "active"))
            else:
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, role, status)
                    VALUES (?, ?, ?, ?, ?)
                """, ("admin", "admin@brainlinktracker.com", admin_password, "admin", "active"))
            
            print("✅ Default admin user created: admin / admin123")
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database initialized successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False

# Authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = request.headers.get('Authorization')
        if not session_token:
            return jsonify({'error': 'No authorization token provided'}), 401
        
        if session_token.startswith('Bearer '):
            session_token = session_token[7:]
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if DATABASE_TYPE == "postgresql":
                cursor.execute("""
                    SELECT u.id, u.username, u.role, u.status 
                    FROM users u 
                    JOIN user_sessions s ON u.id = s.user_id 
                    WHERE s.session_token = %s AND s.expires_at > CURRENT_TIMESTAMP
                """, (session_token,))
            else:
                cursor.execute("""
                    SELECT u.id, u.username, u.role, u.status 
                    FROM users u 
                    JOIN user_sessions s ON u.id = s.user_id 
                    WHERE s.session_token = ? AND s.expires_at > datetime('now')
                """, (session_token,))
            
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user:
                return jsonify({'error': 'Invalid or expired session'}), 401
            
            if user[3] != 'active':  # status
                return jsonify({'error': 'Account not active'}), 401
            
            # Add user info to request context
            request.current_user = {
                'id': user[0],
                'username': user[1],
                'role': user[2],
                'status': user[3]
            }
            
            return f(*args, **kwargs)
            
        except Exception as e:
            print(f"Auth error: {e}")
            return jsonify({'error': 'Authentication failed'}), 401
    
    return decorated_function

# Frontend serving routes
@app.route('/')
def serve_frontend():
    """Serve the main frontend page"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static_files(path):
    """Serve static files"""
    try:
        return send_from_directory(app.static_folder, path)
    except:
        # If file not found, serve index.html for SPA routing
        return send_from_directory(app.static_folder, 'index.html')

# Health check endpoint
@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'Brain Link Tracker API is running',
        'version': '1.0.0',
        'database': DATABASE_TYPE
    })

@app.route('/api/debug')
def debug_info():
    """Debug endpoint to check database connection and user count"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check user count
        if DATABASE_TYPE == "postgresql":
            cursor.execute("SELECT COUNT(*) FROM users")
        else:
            cursor.execute("SELECT COUNT(*) FROM users")
        
        user_count = cursor.fetchone()[0]
        
        # Check if Brain user exists
        if DATABASE_TYPE == "postgresql":
            cursor.execute("SELECT username, role, status FROM users WHERE username = %s", ("Brain",))
        else:
            cursor.execute("SELECT username, role, status FROM users WHERE username = ?", ("Brain",))
        
        brain_user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'database_type': DATABASE_TYPE,
            'database_url_set': 'DATABASE_URL' in os.environ,
            'user_count': user_count,
            'brain_user_exists': brain_user is not None,
            'brain_user_info': brain_user if brain_user else None
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'database_type': DATABASE_TYPE,
            'database_url_set': 'DATABASE_URL' in os.environ
        }), 500

# Authentication endpoints
@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DATABASE_TYPE == "postgresql":
            cursor.execute("SELECT id, username, password_hash, role, status FROM users WHERE username = %s", (username,))
        else:
            cursor.execute("SELECT id, username, password_hash, role, status FROM users WHERE username = ?", (username,))
        
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Invalid credentials'}), 401
        
        user_id, username, password_hash, role, status = user
        
        if status != 'active':
            cursor.close()
            conn.close()
            return jsonify({'error': 'Account not active'}), 401
        
        if not bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
            cursor.close()
            conn.close()
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Create session
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=7)
        
        if DATABASE_TYPE == "postgresql":
            cursor.execute("""
                INSERT INTO user_sessions (user_id, session_token, expires_at)
                VALUES (%s, %s, %s)
            """, (user_id, session_token, expires_at))
            
            cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user_id,))
        else:
            cursor.execute("""
                INSERT INTO user_sessions (user_id, session_token, expires_at)
                VALUES (?, ?, ?)
            """, (user_id, session_token, expires_at))
            
            cursor.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'Login successful',
            'token': session_token,
            'user': {
                'id': user_id,
                'username': username,
                'role': role
            }
        })
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """User logout endpoint"""
    try:
        session_token = request.headers.get('Authorization')
        if session_token.startswith('Bearer '):
            session_token = session_token[7:]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DATABASE_TYPE == "postgresql":
            cursor.execute("DELETE FROM user_sessions WHERE session_token = %s", (session_token,))
        else:
            cursor.execute("DELETE FROM user_sessions WHERE session_token = ?", (session_token,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'Logout successful'})
        
    except Exception as e:
        print(f"Logout error: {e}")
        return jsonify({'error': 'Logout failed'}), 500

# User management endpoints
@app.route('/api/auth/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not username or not email or not password:
            return jsonify({'error': 'Username, email, and password required'}), 400
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if DATABASE_TYPE == "postgresql":
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, role, status)
                    VALUES (%s, %s, %s, %s, %s)
                """, (username, email, password_hash, "member", "pending"))
            else:
                cursor.execute("""
                    INSERT INTO users (username, email, password_hash, role, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, email, password_hash, "member", "pending"))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'message': 'Registration successful'})
            
        except Exception as e:
            cursor.close()
            conn.close()
            if 'UNIQUE constraint failed' in str(e) or 'duplicate key' in str(e):
                return jsonify({'error': 'Username or email already exists'}), 400
            raise e
            
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return send_from_directory(app.static_folder, 'index.html')

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    init_db()
    print(f"✅ Brain Link Tracker starting with {DATABASE_TYPE} database...")
    app.run(host='0.0.0.0', port=5000, debug=True)


# User management endpoints
@app.route('/api/users', methods=['GET'])
@require_auth
def get_users():
    """Get all users (admin only)"""
    try:
        if request.current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DATABASE_TYPE == "postgresql":
            cursor.execute("""
                SELECT id, username, email, role, status, created_at, last_login
                FROM users ORDER BY created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT id, username, email, role, status, created_at, last_login
                FROM users ORDER BY created_at DESC
            """)
        
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        user_list = []
        for user in users:
            user_list.append({
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'role': user[3],
                'status': user[4],
                'created_at': user[5],
                'last_login': user[6]
            })
        
        return jsonify(user_list)
        
    except Exception as e:
        print(f"Get users error: {e}")
        return jsonify({'error': 'Failed to fetch users'}), 500

@app.route('/api/users/<int:user_id>/approve', methods=['POST'])
@require_auth
def approve_user(user_id):
    """Approve a pending user (admin only)"""
    try:
        if request.current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DATABASE_TYPE == "postgresql":
            cursor.execute("UPDATE users SET status = 'active' WHERE id = %s", (user_id,))
        else:
            cursor.execute("UPDATE users SET status = 'active' WHERE id = ?", (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'User approved successfully'})
        
    except Exception as e:
        print(f"Approve user error: {e}")
        return jsonify({'error': 'Failed to approve user'}), 500

@app.route('/api/users/<int:user_id>/reject', methods=['POST'])
@require_auth
def reject_user(user_id):
    """Reject a pending user (admin only)"""
    try:
        if request.current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DATABASE_TYPE == "postgresql":
            cursor.execute("UPDATE users SET status = 'rejected' WHERE id = %s", (user_id,))
        else:
            cursor.execute("UPDATE users SET status = 'rejected' WHERE id = ?", (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'User rejected successfully'})
        
    except Exception as e:
        print(f"Reject user error: {e}")
        return jsonify({'error': 'Failed to reject user'}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_auth
def delete_user(user_id):
    """Delete a user (admin only)"""
    try:
        if request.current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DATABASE_TYPE == "postgresql":
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        else:
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'message': 'User deleted successfully'})
        
    except Exception as e:
        print(f"Delete user error: {e}")
        return jsonify({'error': 'Failed to delete user'}), 500

@app.route('/api/analytics', methods=['GET'])
@require_auth
def get_analytics():
    """Get analytics data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user counts
        if DATABASE_TYPE == "postgresql":
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
            active_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'")
            pending_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_users = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
            active_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'")
            pending_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_users = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'total_users': total_users,
            'active_users': active_users,
            'pending_users': pending_users,
            'admin_users': admin_users,
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Analytics error: {e}")
        return jsonify({'error': 'Failed to fetch analytics'}), 500


@app.route('/api/tracking-links', methods=['GET'])
@require_auth
def get_tracking_links():
    """Get all tracking links for the authenticated user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DATABASE_TYPE == "postgresql":
            cursor.execute("""
                SELECT id, original_url, tracking_token, recipient_email, 
                       created_at, click_count, link_status, 
                       'https://brain-link-tracker-zeta.vercel.app/track/click/' || tracking_token AS tracking_url,
                       'https://brain-link-tracker-zeta.vercel.app/pixel/' || tracking_token AS pixel_url
                FROM tracking_links 
                ORDER BY created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT id, original_url, tracking_token, recipient_email, 
                       created_at, click_count, link_status, 
                       'https://brain-link-tracker-zeta.vercel.app/track/click/' || tracking_token AS tracking_url,
                       'https://brain-link-tracker-zeta.vercel.app/pixel/' || tracking_token AS pixel_url
                FROM tracking_links 
                ORDER BY created_at DESC
            """)
        
        links = cursor.fetchall()
        cursor.close()
        conn.close()
        
        tracking_links = []
        for link in links:
            tracking_links.append({
                'id': link[0],
                'original_url': link[1],
                'tracking_token': link[2],
                'recipient_email': link[3],
                'created_at': link[4],
                'click_count': link[5] if len(link) > 5 else 0,
                'status': link[6] if len(link) > 6 else 'active',
                'campaign_name': 'Default Campaign'  # Default since not in schema
            })
        
        return jsonify({
            'success': True,
            'tracking_links': tracking_links
        })
        
    except Exception as e:
        print(f"Get tracking links error: {e}")
        return jsonify({'success': False, 'error': 'Failed to fetch tracking links'}), 500

@app.route('/api/tracking-links', methods=['POST'])
@require_auth
def create_tracking_link():
    """Create a new tracking link"""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({'success': False, 'error': 'URL is required'}), 400
        
        original_url = data['url']
        campaign_name = data.get('campaign_name', '')
        recipient_email = data.get('email', '')
        user_id = request.current_user['id']  # Get user ID from authenticated user
        
        # Generate a unique tracking token
        import secrets
        tracking_token = secrets.token_urlsafe(16)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if DATABASE_TYPE == "postgresql":
            cursor.execute("""
                INSERT INTO tracking_links (user_id, original_url, tracking_token, recipient_email, created_at, link_status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, original_url, tracking_token, recipient_email, datetime.now(), 'active'))
            link_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                INSERT INTO tracking_links (user_id, original_url, tracking_token, recipient_email, created_at, link_status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, original_url, tracking_token, recipient_email, datetime.now().isoformat(), 'active'))
            link_id = cursor.lastrowid
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Generate the tracking URL
        tracking_url = f"https://brain-link-tracker-zeta.vercel.app/track/click/{tracking_token}"
        
        return jsonify({
            'success': True,
            'tracking_link': {
                'id': link_id,
                'original_url': original_url,
                'tracking_token': tracking_token,
                'tracking_url': tracking_url,
                'campaign_name': campaign_name,
                'recipient_email': recipient_email,
                'created_at': datetime.now().isoformat(),
                'status': 'active'
            }
        })
        
    except Exception as e:
        print(f"Create tracking link error: {e}")
        return jsonify({'success': False, 'error': 'Failed to create tracking link'}), 500

@app.route('/api/admin/users', methods=['GET'])
@require_auth
def get_admin_users():
    """Get all users for admin management (alias for /api/users)"""
    return get_users()

@app.route('/api/campaigns', methods=['GET'])
@require_auth
def get_campaigns():
    """Get all campaigns"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get unique campaigns from tracking_links
        if DATABASE_TYPE == "postgresql":
            cursor.execute("""
                SELECT DISTINCT campaign_name, COUNT(*) as link_count,
                       MIN(created_at) as created_at
                FROM tracking_links 
                WHERE campaign_name IS NOT NULL AND campaign_name != ''
                GROUP BY campaign_name
                ORDER BY created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT DISTINCT campaign_name, COUNT(*) as link_count,
                       MIN(created_at) as created_at
                FROM tracking_links 
                WHERE campaign_name IS NOT NULL AND campaign_name != ''
                GROUP BY campaign_name
                ORDER BY created_at DESC
            """)
        
        campaigns = cursor.fetchall()
        cursor.close()
        conn.close()
        
        campaign_list = []
        for campaign in campaigns:
            campaign_list.append({
                'name': campaign[0],
                'link_count': campaign[1],
                'created_at': campaign[2],
                'status': 'active'
            })
        
        return jsonify({
            'success': True,
            'campaigns': campaign_list
        })
        
    except Exception as e:
        print(f"Get campaigns error: {e}")
        return jsonify({'success': False, 'error': 'Failed to fetch campaigns'}), 500



@app.route('/track/click/<tracking_token>')
def track_click(tracking_token):
    """Handle tracking link clicks and redirect to original URL"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the tracking link details
        if DATABASE_TYPE == "postgresql":
            cursor.execute("""
                SELECT original_url, click_count, link_status, redirect_delay
                FROM tracking_links 
                WHERE tracking_token = %s AND link_status = 'active'
            """, (tracking_token,))
        else:
            cursor.execute("""
                SELECT original_url, click_count, link_status, redirect_delay
                FROM tracking_links 
                WHERE tracking_token = ? AND link_status = 'active'
            """, (tracking_token,))
        
        link_data = cursor.fetchone()
        
        if not link_data:
            cursor.close()
            conn.close()
            return "Tracking link not found or expired", 404
        
        original_url, click_count, link_status, redirect_delay = link_data
        
        # Update click count and last clicked timestamp
        if DATABASE_TYPE == "postgresql":
            cursor.execute("""
                UPDATE tracking_links 
                SET click_count = click_count + 1, last_clicked = CURRENT_TIMESTAMP
                WHERE tracking_token = %s
            """, (tracking_token,))
        else:
            cursor.execute("""
                UPDATE tracking_links 
                SET click_count = click_count + 1, last_clicked = datetime('now')
                WHERE tracking_token = ?
            """, (tracking_token,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Ensure the URL has a protocol
        if not original_url.startswith(('http://', 'https://')):
            original_url = 'https://' + original_url
        
        # Apply redirect delay if specified
        redirect_delay = redirect_delay or 0
        if redirect_delay > 0:
            time.sleep(redirect_delay)
        
        # Redirect to the original URL
        return redirect(original_url, code=302)
        
    except Exception as e:
        print(f"Track click error: {e}")
        return "Error processing tracking link", 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

