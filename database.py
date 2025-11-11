import sqlite3
import bcrypt
import json
from datetime import datetime
import os

DB_FILE = 'notes.db'
MEDIA_DIR = 'media'

def init_database():
    """Initialize the database and create tables if they don't exist"""
    if not os.path.exists(MEDIA_DIR):
        os.makedirs(MEDIA_DIR)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create notes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            source_chat_id TEXT NOT NULL,
            source_name TEXT,
            message_text TEXT,
            timestamp DATETIME NOT NULL,
            media_type TEXT,
            media_path TEXT
        )
    ''')
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Create default admin user if not exists
    cursor.execute('SELECT username FROM users WHERE username = ?', ('admin',))
    if cursor.fetchone() is None:
        password_hash = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt())
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                      ('admin', password_hash))
    
    conn.commit()
    conn.close()

def add_note(user_id, source_chat_id, source_name, message_text, media_type=None, media_path=None):
    """Add a new note to the database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT INTO notes (user_id, source_chat_id, source_name, message_text, timestamp, media_type, media_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, source_chat_id, source_name, message_text, timestamp, media_type, media_path))
    
    conn.commit()
    note_id = cursor.lastrowid
    conn.close()
    
    return note_id

def get_notes(user_id=None, source_chat_ids=None, limit=100, offset=0):
    """Get notes from the database with optional filtering"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    query = 'SELECT id, user_id, source_chat_id, source_name, message_text, timestamp, media_type, media_path FROM notes WHERE 1=1'
    params = []
    
    if user_id:
        query += ' AND user_id = ?'
        params.append(user_id)
    
    if source_chat_ids and len(source_chat_ids) > 0:
        placeholders = ','.join(['?' for _ in source_chat_ids])
        query += f' AND source_chat_id IN ({placeholders})'
        params.extend(source_chat_ids)
    
    query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    notes = cursor.fetchall()
    conn.close()
    
    return [
        {
            'id': note[0],
            'user_id': note[1],
            'source_chat_id': note[2],
            'source_name': note[3],
            'message_text': note[4],
            'timestamp': note[5],
            'media_type': note[6],
            'media_path': note[7]
        }
        for note in notes
    ]

def get_sources(user_id):
    """Get all unique sources for a user"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT source_chat_id, source_name
        FROM notes
        WHERE user_id = ?
        ORDER BY source_name
    ''', (user_id,))
    
    sources = cursor.fetchall()
    conn.close()
    
    return [{'id': s[0], 'name': s[1] or s[0]} for s in sources]

def count_notes(user_id=None, source_chat_ids=None):
    """Count total notes with optional filtering"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    query = 'SELECT COUNT(*) FROM notes WHERE 1=1'
    params = []
    
    if user_id:
        query += ' AND user_id = ?'
        params.append(user_id)
    
    if source_chat_ids and len(source_chat_ids) > 0:
        placeholders = ','.join(['?' for _ in source_chat_ids])
        query += f' AND source_chat_id IN ({placeholders})'
        params.extend(source_chat_ids)
    
    cursor.execute(query, params)
    count = cursor.fetchone()[0]
    conn.close()
    
    return count

def verify_user(username, password):
    """Verify user credentials"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    
    if result is None:
        return False
    
    return bcrypt.checkpw(password.encode('utf-8'), result[0])

def change_password(username, new_password):
    """Change user password"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
    cursor.execute('UPDATE users SET password_hash = ? WHERE username = ?', 
                  (password_hash, username))
    
    conn.commit()
    conn.close()
    
    return True
