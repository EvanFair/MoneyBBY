from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
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

app = FastAPI(title="GoodNewsCast AI API")

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

# Create output/static dirs if missing
os.makedirs(output_dir, exist_ok=True)
os.makedirs(static_dir, exist_ok=True)

class StatusUpdateRequest(BaseModel):
    status: str
    clean_summary: str = None
    category: str = None

class EpisodeCreateRequest(BaseModel):
    title: str = "Daily Wholesome Round-up"

@app.get("/api/stories")
def get_stories(status: str = "scraped"):
    if status not in ["scraped", "approved", "rejected", "used"]:
        raise HTTPException(status_code=400, detail="Invalid status parameter")
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

@app.post("/api/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    def run_pipeline():
        print("Starting background scrape and clean pipeline...")
        scraper.run_scraper()
        cleaner.run_cleaner()
        print("Background pipeline completed.")
        
    background_tasks.add_task(run_pipeline)
    return {"message": "Scraper pipeline triggered in the background."}

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

# Mount media outputs (so dashboard can play MP3/MP4 files directly)
app.mount("/output", StaticFiles(directory=output_dir), name="output")

# Mount static web files (dashboard UI)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
