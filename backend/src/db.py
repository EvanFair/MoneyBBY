import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aipulse.db")

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
    print("Database initialized successf