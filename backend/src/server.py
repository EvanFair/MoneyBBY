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
        
   