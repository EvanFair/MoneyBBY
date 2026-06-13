"""
server.py — AIPulse FastAPI backend
Run with: uvicorn src.server:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os, sys, json, subprocess, threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db, scraper, cleaner, writer, tts, renderer

app = FastAPI(title="AIPulse API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_dir  = os.path.join(backend_dir, "output")
static_dir  = os.path.join(backend_dir, "static")
images_dir  = os.path.join(backend_dir, "static", "images")
for d in [output_dir, static_dir, images_dir]:
    os.makedirs(d, exist_ok=True)

db.init_db()
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ── Models ────────────────────────────────────────────────────────────────────
class StatusUpdateRequest(BaseModel):
    status: str
    clean_summary: Optional[str] = None
    category: Optional[str] = None

class EpisodeCreateRequest(BaseModel):
    title: str = "Daily AIPulse Tech Round-up"

class SourceCreateRequest(BaseModel):
    name: str; url: str; type: str; volume_limit: int = 10

class SourceUpdateRequest(BaseModel):
    enabled: Optional[int] = None
    volume_limit: Optional[int] = None
    name: Optional[str] = None
    url: Optional[str] = None

class AutoApproveRequest(BaseModel):
    limit: int = 5

class PublishCarouselRequest(BaseModel):
    story_id: int
    caption: Optional[str] = None
    platforms: Optional[List[str]] = None

class PublishReelRequest(BaseModel):
    episode_id: int
    caption: Optional[str] = None
    platforms: Optional[List[str]] = None

class PipelineRunRequest(BaseModel):
    top_stories:   int  = 5
    publish:       bool = False
    skip_carousel: bool = False
    skip_reel:     bool = False

# ── Stories ───────────────────────────────────────────────────────────────────
@app.get("/api/stories")
def get_stories(status: str = "scraped", limit: int = None):
    if status not in ["scraped","approved","rejected","used"]:
        raise HTTPException(400, "Invalid status")
    if status == "scraped" and limit is not None:
        return db.get_top_scraped_stories(limit)
    return db.get_stories_by_status(status)

@app.get("/api/stories/{story_id}")
def get_story(story_id: int):
    s = db.get_story_by_id(story_id)
    if not s: raise HTTPException(404, "Story not found")
    return s

@app.post("/api/stories/{story_id}/status")
def update_story_status(story_id: int, req: StatusUpdateRequest):
    if not db.get_story_by_id(story_id): raise HTTPException(404, "Story not found")
    db.update_story_status(story_id, req.status, req.clean_summary, req.category)
    return {"message": f"Story {story_id} updated to {req.status}"}

@app.post("/api/auto-approve")
def auto_approve(req: AutoApproveRequest):
    ids = db.auto_approve_top_stories(req.limit)
    return {"message": f"Auto-approved {len(ids)} stories", "approved": ids,
            "stories": [s for s in [db.get_story_by_id(i) for i in ids] if s]}

# ── Scrape ────────────────────────────────────────────────────────────────────
@app.post("/api/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    def run():
        scraper.run_scraper()
        cleaner.run_cleaner()
    background_tasks.add_task(run)
    return {"message": "Scraper pipeline triggered in background."}

# ── Episodes ──────────────────────────────────────────────────────────────────
@app.get("/api/episodes")
def get_episodes():
    return db.get_all_episodes()

@app.get("/api/episodes/{episode_id}")
def get_episode(episode_id: int):
    ep = db.get_episode_by_id(episode_id)
    if not ep: raise HTTPException(404, "Episode not found")
    return ep

@app.get("/api/episodes/{episode_id}/script")
def get_episode_script(episode_id: int):
    ep = db.get_episode_by_id(episode_id)
    if not ep: raise HTTPException(404, "Episode not found")
    try: return {"script": json.loads(ep["script_json"])}
    except: return {"script": []}

@app.post("/api/episodes")
def create_episode(req: EpisodeCreateRequest, background_tasks: BackgroundTasks):
    result = writer.create_daily_episode(req.title)
    if not result: raise HTTPException(400, "Failed — approve some stories first.")
    episode_id, script = result
    def gen_av(eid):
        audio = tts.generate_audio_for_episode(eid)
        if audio: renderer.generate_video_for_episode(eid)
    background_tasks.add_task(gen_av, episode_id)
    return {"message": f"Episode created. Audio/video generating.", "episode_id": episode_id, "lines": len(script)}

@app.post("/api/episodes/{episode_id}/generate")
def generate_episode_av(episode_id: int, background_tasks: BackgroundTasks):
    if not db.get_episode_by_id(episode_id): raise HTTPException(404, "Episode not found")
    def gen(eid):
        audio = tts.generate_audio_for_episode(eid)
        if audio: renderer.generate_video_for_episode(eid)
    background_tasks.add_task(gen, episode_id)
    return {"message": f"Generating audio + video for episode {episode_id}."}

# ── Sources ───────────────────────────────────────────────────────────────────
@app.get("/api/sources")
def get_sources(): return db.get_all_sources()

@app.post("/api/sources")
def create_source(req: SourceCreateRequest):
    sid = db.create_source(req.name, req.url, req.type, req.volume_limit)
    if not sid: raise HTTPException(409, "Source name already exists.")
    return {"message": f"Source '{req.name}' created.", "id": sid}

@app.put("/api/sources/{source_id}")
def update_source(source_id: int, req: SourceUpdateRequest):
    db.update_source(source_id, **{k:v for k,v in req.dict().items() if v is not None})
    return {"message": f"Source {source_id} updated."}

@app.delete("/api/sources/{source_id}")
def delete_source(source_id: int):
    db.delete_source(source_id)
    return {"message": f"Source {source_id} deleted."}

# ── Carousel generation ───────────────────────────────────────────────────────
@app.post("/api/stories/{story_id}/carousel")
def generate_carousel(story_id: int, background_tasks: BackgroundTasks):
    if not db.get_story_by_id(story_id): raise HTTPException(404, "Story not found")
    def run(sid):
        script   = os.path.join(backend_dir, "carousel", "generate_carousel.py")
        out_path = os.path.join(output_dir, f"carousel_{sid}.pptx")
        try:
            r = subprocess.run([sys.executable, script, "--story-id", str(sid), "--output", out_path],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0 and os.path.exists(out_path):
                db.update_story_carousel_path(sid, out_path)
        except Exception as e:
            print(f"[Carousel] Error #{sid}: {e}")
    background_tasks.add_task(run, story_id)
    return {"message": f"Carousel generation started for story {story_id}."}

# ── Reel generation ───────────────────────────────────────────────────────────
@app.post("/api/stories/{story_id}/reel")
def generate_reel(story_id: int, background_tasks: BackgroundTasks):
    if not db.get_story_by_id(story_id): raise HTTPException(404, "Story not found")
    def run(sid):
        try:
            from reel_generator import generate_reel_for_story
            generate_reel_for_story(sid)
        except Exception as e:
            print(f"[Reel] Error #{sid}: {e}")
    background_tasks.add_task(run, story_id)
    return {"message": f"Reel generation started for story {story_id}."}

@app.get("/api/stories/{story_id}/reel")
def get_reel(story_id: int):
    story = db.get_story_by_id(story_id)
    if not story: raise HTTPException(404, "Story not found")
    reel_path = story.get("reel_path")
    reel_url  = None
    if reel_path and os.path.exists(reel_path):
        try:
            reel_url = "/static/" + os.path.relpath(reel_path, static_dir).replace("\\", "/")
        except ValueError:
            reel_url = None
    return {"reel_path": reel_path, "reel_url": reel_url, "exists": bool(reel_url)}

# ── Publishing ────────────────────────────────────────────────────────────────
@app.post("/api/publish/carousel")
def publish_carousel(req: PublishCarouselRequest):
    try:
        from publisher import publish_story_carousel
        return {"results": publish_story_carousel(req.story_id, req.platforms or ["instagram","facebook"])}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/publish/reel")
def publish_reel(req: PublishReelRequest):
    try:
        from publisher import publish_episode_reel
        return {"results": publish_episode_reel(req.episode_id, req.platforms or ["instagram","facebook"])}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/posts")
def get_posts():
    conn = db.get_db_connection()
    rows = conn.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 200").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Pipeline control ──────────────────────────────────────────────────────────
_pipeline_running = False
_pipeline_lock    = threading.Lock()

@app.post("/api/pipeline/run")
def run_pipeline_endpoint(req: PipelineRunRequest, background_tasks: BackgroundTasks):
    global _pipeline_running
    if _pipeline_running: raise HTTPException(409, "Pipeline already running.")
    def execute():
        global _pipeline_running
        _pipeline_running = True
        try:
            from pipeline import run_pipeline
            run_pipeline(top_stories=req.top_stories, publish=req.publish,
                         skip_carousel=req.skip_carousel, skip_reel=req.skip_reel)
        finally:
            _pipeline_running = False
    background_tasks.add_task(execute)
    return {"message": "Pipeline started in background.", "running": True}

@app.get("/api/pipeline/status")
def pipeline_status():
    stats    = db.get_pipeline_stats()
    log_path = os.path.join(output_dir, "pipeline_log.json")
    last_run = None
    if os.path.exists(log_path):
        try:
            history  = json.loads(open(log_path).read())
            last_run = history[0].get("run_at") if history else None
        except: pass
    return {"running": _pipeline_running, "last_run": last_run, **stats}

@app.get("/api/pipeline/log")
def pipeline_log(lines: int = 100):
    log_txt = os.path.join(output_dir, "pipeline_log.txt")
    if not os.path.exists(log_txt): return {"lines": []}
    with open(log_txt, "r", encoding="utf-8", errors="ignore") as f:
        all_lines = f.readlines()
    return {"lines": [l.rstrip() for l in all_lines[-lines:]]}

# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    index = os.path.join(static_dir, "index.html")
    if os.path.exists(index): return FileResponse(index)
    return {"message": "AIPulse API running."}
