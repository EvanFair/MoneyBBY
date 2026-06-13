from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import os
import sys
import sqlite3

# Ensure backend/src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db
import scraper
import cleaner
import writer
import tts
import renderer

app = FastAPI(title="AIPulse API")

# Enable CORS for frontend accessibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_dir = os.path.join(backend_dir, "output")
static_dir = os.path.join(backend_dir, "static")
images_dir = os.path.join(backend_dir, "static", "images")

# Create output/static/images dirs if missing
os.makedirs(output_dir, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)
os.makedirs(images_dir, exist_ok=True)

# Initialize database on startup
db.init_db()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class StatusUpdateRequest(BaseModel):
    status: str
    clean_summary: str = None
    category: str = None

class EpisodeCreateRequest(BaseModel):
    title: str = "Daily Wholesome Round-up"

class SourceCreateRequest(BaseModel):
    name: str
    url: str
    type: str
    volume_limit: int = 10

class SourceUpdateRequest(BaseModel):
    enabled: Optional[int] = None
    volume_limit: Optional[int] = None
    name: Optional[str] = None
    url: Optional[str] = None

# ---------------------------------------------------------------------------
# Story endpoints
# ---------------------------------------------------------------------------

@app.get("/api/stories")
def get_stories(status: str = "scraped", limit: int = None):
    if status not in ["scraped", "approved", "rejected", "used"]:
        raise HTTPException(status_code=400, detail="Invalid status parameter")
    if status == "scraped" and limit is not None:
        return db.get_top_scraped_stories(limit)
    return db.get_stories_by_status(status)

@app.post("/api/stories/{story_id}/status")
def update_story_status(story_id: int, req: StatusUpdateRequest):
    # Verify story exists
    conn = db.get_db_connection()
    story = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
    conn.close()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
        
    db.update_story_status(story_id, req.status, req.clean_summary, req.category)
    return {"message": f"Story {story_id} status updated to {req.status}"}

# ---------------------------------------------------------------------------
# Scrape / pipeline endpoints
# ---------------------------------------------------------------------------

@app.post("/api/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    def run_pipeline():
        print("Starting background scrape and clean pipeline...")
        scraper.run_scraper()
        cleaner.run_cleaner()
        print("Background pipeline completed.")
        
    background_tasks.add_task(run_pipeline)
    return {"message": "Scraper pipeline triggered in the background."}

# ---------------------------------------------------------------------------
# Episode endpoints
# ---------------------------------------------------------------------------

def generate_episode_pipeline(episode_id):
    # 1. Synthesize audio
    audio_path = tts.generate_audio_for_episode(episode_id)
    if audio_path:
        # 2. Render video
        renderer.generate_video_for_episode(episode_id)

@app.post("/api/episodes")
def create_episode(req: EpisodeCreateRequest, background_tasks: BackgroundTasks):
    result = writer.create_daily_episode(req.title)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to create episode. Make sure you have approved stories in the database.")
        
    episode_id, script = result
    
    # Run TTS and Rendering in the background to avoid API timeouts
    background_tasks.add_task(generate_episode_pipeline, episode_id)
    
    return {
        "message": "Episode draft created. Audio synthesis and video rendering started in the background.",
        "episode_id": episode_id,
        "script": script
    }

@app.get("/api/episodes")
def list_episodes():
    conn = db.get_db_connection()
    rows = conn.execute("SELECT * FROM episodes ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/episodes/{episode_id}")
def get_episode(episode_id: int):
    conn = db.get_db_connection()
    row = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Episode not found")
    return dict(row)

# ---------------------------------------------------------------------------
# Source CRUD endpoints
# ---------------------------------------------------------------------------

@app.get("/api/sources")
def get_sources():
    return db.get_sources()

@app.post("/api/sources")
def create_source(req: SourceCreateRequest):
    source_id = db.add_source(req.name, req.url, req.type, req.volume_limit)
    return {"message": "Source created", "source_id": source_id}

@app.put("/api/sources/{source_id}")
def update_source(source_id: int, req: SourceUpdateRequest):
    db.update_source(source_id, enabled=req.enabled, volume_limit=req.volume_limit, name=req.name, url=req.url)
    return {"message": f"Source {source_id} updated"}

@app.delete("/api/sources/{source_id}")
def delete_source(source_id: int):
    db.delete_source(source_id)
    return {"message": f"Source {source_id} deleted"}

# ---------------------------------------------------------------------------
# Trending tags & approved summary
# ---------------------------------------------------------------------------

@app.get("/api/trending-tags")
def get_trending_tags():
    raw_tags = db.get_trending_tags()
    return [{"tag": tag, "count": count} for tag, count in raw_tags]

APPROVED_SUMMARY_CACHE = {"key": None, "summary": None}

@app.get("/api/approved-summary")
def get_approved_summary():
    stories = db.get_stories_by_status("approved")
    if not stories:
        return {"summary": "No approved stories available.", "count": 0}
    
    # Generate cache key based on sorted IDs of approved stories
    story_ids = sorted([s["id"] for s in stories])
    cache_key = ",".join(map(str, story_ids))
    
    global APPROVED_SUMMARY_CACHE
    if APPROVED_SUMMARY_CACHE["key"] == cache_key:
        summary_text = APPROVED_SUMMARY_CACHE["summary"]
    else:
        summary_text = cleaner.generate_approved_summary_llm(stories)
        APPROVED_SUMMARY_CACHE["key"] = cache_key
        APPROVED_SUMMARY_CACHE["summary"] = summary_text
        
    return {"summary": summary_text, "count": len(stories)}


# ---------------------------------------------------------------------------
# Static file mounts — MUST come after all API route definitions
# ---------------------------------------------------------------------------

# Mount media outputs (so dashboard can play MP3/MP4 files directly)
app.mount("/output", StaticFiles(directory=output_dir), name="output")

# Mount images directory
app.mount("/images", StaticFiles(directory=images_dir), name="images")

# Mount static web files (dashboard UI) — catch-all MUST be LAST
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
