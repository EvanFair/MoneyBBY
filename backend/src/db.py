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

    # Safely add new columns to stories table
    new_columns = [
        ("images_json", "TEXT"),
        ("value_score", "INTEGER DEFAULT 0"),
        ("value_explanation", "TEXT"),
        ("full_text", "TEXT"),
        ("niche_tags", "TEXT"),
    ]
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE stories ADD COLUMN {col_name} {col_type}")
        except Exception:
            pass  # Column already exists

    # Create sources table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        url TEXT,
        type TEXT,
        enabled INTEGER DEFAULT 1,
        volume_limit INTEGER DEFAULT 10,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Auto-seed default sources
    default_sources = [
        ('TechCrunch AI', 'https://techcrunch.com/category/artificial-intelligence/feed/', 'rss', 1, 5),
        ('VentureBeat AI', 'https://venturebeat.com/category/ai/feed/', 'rss', 1, 5),
        ('ArXiv ML', 'http://export.arxiv.org/rss/cs.CL', 'rss', 1, 10),
        ('Hacker News', 'AI,LLM,GPU,Claude,Gemini,OpenAI', 'hn', 1, 15),
        ('GitHub Trending', 'ai', 'github', 1, 10),
        ('Hugging Face', 'https://huggingface.co/api/daily_papers', 'huggingface', 1, 10),
        ('Google News AI', 'AI LLM,AI agents,open-weights AI,machine learning research', 'google_news', 1, 10),
    ]
    for name, url, stype, enabled, volume_limit in default_sources:
        cursor.execute(
            "INSERT OR IGNORE INTO sources (name, url, type, enabled, volume_limit) VALUES (?, ?, ?, ?, ?)",
            (name, url, stype, enabled, volume_limit)
        )

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

# ---------------------------------------------------------------------------
# Source CRUD helpers
# ---------------------------------------------------------------------------

def get_sources():
    """Returns all sources as a list of dicts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sources ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_source(name, url, source_type, volume_limit=10):
    """Inserts a new source and returns its id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sources (name, url, type, volume_limit) VALUES (?, ?, ?, ?)",
        (name, url, source_type, volume_limit)
    )
    conn.commit()
    source_id = cursor.lastrowid
    conn.close()
    return source_id

def update_source(source_id, enabled=None, volume_limit=None, name=None, url=None):
    """Updates fields on an existing source."""
    conn = get_db_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    if enabled is not None:
        fields.append("enabled = ?")
        values.append(enabled)
    if volume_limit is not None:
        fields.append("volume_limit = ?")
        values.append(volume_limit)
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if url is not None:
        fields.append("url = ?")
        values.append(url)
    if fields:
        values.append(source_id)
        cursor.execute(f"UPDATE sources SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()

def delete_source(source_id):
    """Deletes a source by id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Enhanced story helpers
# ---------------------------------------------------------------------------

def get_top_scraped_stories(limit=10):
    """Returns the top `limit` scraped stories ordered by value_score DESC, then created_at DESC."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM stories WHERE status = 'scraped' ORDER BY value_score DESC, created_at DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_trending_tags():
    """Returns a list of (tag, count) tuples from the niche_tags of all approved stories."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT niche_tags FROM stories WHERE status = 'approved' AND niche_tags IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()

    tag_counts = {}
    for row in rows:
        try:
            tags = json.loads(row["niche_tags"])
            if isinstance(tags, list):
                for tag in tags:
                    tag = tag.strip()
                    if tag:
                        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass

    # Sort by count descending
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_tags

def update_story_details(story_id, images_json=None, value_score=None, value_explanation=None, full_text=None, niche_tags=None):
    """Updates the enrichment fields on a story."""
    conn = get_db_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    if images_json is not None:
        fields.append("images_json = ?")
        values.append(images_json)
    if value_score is not None:
        fields.append("value_score = ?")
        values.append(value_score)
    if value_explanation is not None:
        fields.append("value_explanation = ?")
        values.append(value_explanation)
    if full_text is not None:
        fields.append("full_text = ?")
        values.append(full_text)
    if niche_tags is not None:
        fields.append("niche_tags = ?")
        values.append(niche_tags)
    if fields:
        values.append(story_id)
        cursor.execute(f"UPDATE stories SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
