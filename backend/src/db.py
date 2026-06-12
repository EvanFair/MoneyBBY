import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "goodnews.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create stories table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE,
        url TEXT,
        source TEXT,
        summary TEXT,
        clean_summary TEXT,
        category TEXT,
        status TEXT DEFAULT 'scraped',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create episodes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        script_json TEXT,
        status TEXT DEFAULT 'draft',
        audio_path TEXT,
        video_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized successfully at:", DB_PATH)

def insert_story(title, url, source, summary):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO stories (title, url, source, summary) VALUES (?, ?, ?, ?)",
            (title, url, source, summary)
        )
        conn.commit()
        story_id = cursor.lastrowid
        return story_id
    except sqlite3.IntegrityError:
        # Story already exists (duplicate title)
        return None
    finally:
        conn.close()

def get_stories_by_status(status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stories WHERE status = ? ORDER BY created_at DESC", (status,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_story_status(story_id, status, clean_summary=None, category=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if clean_summary and category:
        cursor.execute(
            "UPDATE stories SET status = ?, clean_summary = ?, category = ? WHERE id = ?",
            (status, clean_summary, category, story_id)
        )
    else:
        cursor.execute(
            "UPDATE stories SET status = ? WHERE id = ?",
            (status, story_id)
        )
    conn.commit()
    conn.close()

def create_episode(title, script_data):
    conn = get_db_connection()
    cursor = conn.cursor()
    script_json = json.dumps(script_data)
    cursor.execute(
        "INSERT INTO episodes (title, script_json) VALUES (?, ?)",
        (title, script_json)
    )
    conn.commit()
    episode_id = cursor.lastrowid
    conn.close()
    return episode_id

if __name__ == "__main__":
    init_db()
