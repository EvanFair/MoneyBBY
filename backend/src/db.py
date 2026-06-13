import sqlite3
import os
import json

_default_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aipulse.db")
# DB_PATH can be overridden via AIPULSE_DB_PATH env var (useful for testing outside OneDrive)
DB_PATH = os.environ.get("AIPULSE_DB_PATH", _default_db)


def get_db_connection():
    path = os.environ.get("AIPULSE_DB_PATH", _default_db)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE, url TEXT, source TEXT, summary TEXT,
        clean_summary TEXT, category TEXT, status TEXT DEFAULT 'scraped',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, script_json TEXT, status TEXT DEFAULT 'draft',
        audio_path TEXT, video_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, url TEXT, type TEXT,
        enabled INTEGER DEFAULT 1, volume_limit INTEGER DEFAULT 10,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT, story_id INTEGER, episode_id INTEGER,
        post_id TEXT, status TEXT DEFAULT 'pending', error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    for col, typ in [("images_json","TEXT"),("value_score","INTEGER DEFAULT 0"),
                     ("value_explanation","TEXT"),("full_text","TEXT"),
                     ("niche_tags","TEXT"),("reel_path","TEXT"),("carousel_path","TEXT")]:
        try: cursor.execute(f"ALTER TABLE stories ADD COLUMN {col} {typ}")
        except: pass

    for col, typ in [("reel_path","TEXT")]:
        try: cursor.execute(f"ALTER TABLE episodes ADD COLUMN {col} {typ}")
        except: pass

    default_sources = [
        ('TechCrunch AI','https://techcrunch.com/category/artificial-intelligence/feed/','rss',1,5),
        ('VentureBeat AI','https://venturebeat.com/category/ai/feed/','rss',1,5),
        ('ArXiv ML','http://export.arxiv.org/rss/cs.CL','rss',1,10),
        ('Hacker News','AI,LLM,GPU,Claude,Gemini,OpenAI','hn',1,15),
        ('GitHub Trending','ai','github',1,10),
        ('Hugging Face','https://huggingface.co/api/daily_papers','huggingface',1,10),
        ('Google News AI','AI LLM,AI agents,open-weights AI,machine learning research','google_news',1,10),
    ]
    for name, url, stype, enabled, volume_limit in default_sources:
        cursor.execute(
            "INSERT OR IGNORE INTO sources (name,url,type,enabled,volume_limit) VALUES (?,?,?,?,?)",
            (name, url, stype, enabled, volume_limit))

    conn.commit()
    conn.close()
    print("Database initialized.")


# --- Stories ---
def insert_story(title, url, source, summary):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO stories (title,url,source,summary) VALUES (?,?,?,?)",
                  (title, url, source, summary))
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_stories_by_status(status):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM stories WHERE status=? ORDER BY value_score DESC, created_at DESC",
        (status,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_top_scraped_stories(limit):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM stories WHERE status='scraped' ORDER BY value_score DESC, created_at DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_story_status(story_id, status, clean_summary=None, category=None):
    conn = get_db_connection()
    if clean_summary is not None and category is not None:
        conn.execute("UPDATE stories SET status=?,clean_summary=?,category=? WHERE id=?",
                     (status, clean_summary, category, story_id))
    elif clean_summary is not None:
        conn.execute("UPDATE stories SET status=?,clean_summary=? WHERE id=?",
                     (status, clean_summary, story_id))
    else:
        conn.execute("UPDATE stories SET status=? WHERE id=?", (status, story_id))
    conn.commit()
    conn.close()

def update_story_reel_path(story_id, reel_path):
    conn = get_db_connection()
    conn.execute("UPDATE stories SET reel_path=? WHERE id=?", (reel_path, story_id))
    conn.commit(); conn.close()

def update_story_carousel_path(story_id, carousel_path):
    conn = get_db_connection()
    conn.execute("UPDATE stories SET carousel_path=? WHERE id=?", (carousel_path, story_id))
    conn.commit(); conn.close()

def auto_approve_top_stories(n=5):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT id FROM stories WHERE status='scraped' ORDER BY value_score DESC LIMIT ?", (n,)
    ).fetchall()
    ids = [r["id"] for r in rows]
    for sid in ids:
        conn.execute("UPDATE stories SET status='approved' WHERE id=?", (sid,))
    conn.commit(); conn.close()
    print(f"Auto-approved {len(ids)} stories.")
    return ids

def get_story_by_id(story_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM stories WHERE id=?", (story_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# --- Episodes ---
def create_episode(title, script):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO episodes (title,script_json) VALUES (?,?)",
              (title, json.dumps(script)))
    conn.commit()
    eid = c.lastrowid
    conn.close()
    return eid

def get_all_episodes():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM episodes ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_episode_by_id(episode_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

# --- Sources ---
def get_all_sources():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM sources ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_enabled_sources():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM sources WHERE enabled=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_source(name, url, stype, volume_limit=10):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO sources (name,url,type,enabled,volume_limit) VALUES (?,?,?,?,?)",
                  (name, url, stype, 1, volume_limit))
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def update_source(source_id, **kwargs):
    conn = get_db_connection()
    for key, val in kwargs.items():
        if val is not None:
            conn.execute(f"UPDATE sources SET {key}=? WHERE id=?", (val, source_id))
    conn.commit(); conn.close()

def delete_source(source_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
    conn.commit(); conn.close()

# --- Posts ---
def create_post_record(platform, story_id=None, episode_id=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO posts (platform,story_id,episode_id) VALUES (?,?,?)",
              (platform, story_id, episode_id))
    conn.commit()
    pid = c.lastrowid
    conn.close()
    return pid

def update_post_record(post_db_id, post_id=None, status="posted", error=None):
    conn = get_db_connection()
    conn.execute("UPDATE posts SET post_id=?,status=?,error=? WHERE id=?",
                 (post_id, status, error, post_db_id))
    conn.commit(); conn.close()

def get_posts_for_story(story_id):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM posts WHERE story_id=?", (story_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pipeline_stats():
    conn = get_db_connection()
    today = "date(created_at) = date('now')"
    scraped   = conn.execute(f"SELECT COUNT(*) FROM stories WHERE {today}").fetchone()[0]
    approved  = conn.execute(f"SELECT COUNT(*) FROM stories WHERE status='approved' AND {today}").fetchone()[0]
    carousels = conn.execute(f"SELECT COUNT(*) FROM stories WHERE carousel_path IS NOT NULL AND {today}").fetchone()[0]
    reels     = conn.execute(f"SELECT COUNT(*) FROM stories WHERE reel_path IS NOT NULL AND {today}").fetchone()[0]
    published = conn.execute(f"SELECT COUNT(*) FROM posts WHERE status='posted' AND {today}").fetchone()[0]
    conn.close()
    return {"stories_scraped": scraped, "stories_approved": approved,
            "carousels_generated": carousels, "reels_generated": reels,
            "posts_published": published}
