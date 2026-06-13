# AIPulse — App Purpose & Build Roadmap

---

## 🎯 App Purpose

**AIPulse** is a fully automated AI content factory for social media.

Every day it:
1. Goes online and scrapes the best AI & tech stories from RSS feeds, Hacker News, GitHub, Hugging Face, and Google News
2. Uses an LLM to score, clean, and categorize each story — auto-picking the highest-value ones
3. Generates multiple content formats from those stories: a podcast episode (MP3/MP4), Instagram/Facebook carousel posts (PPTX → images), and short-form video Reels
4. Automatically publishes the finished content to Facebook, Instagram, and other platforms on a schedule

The goal: zero daily effort. One pipeline, run once a day, produces a week's worth of polished social content.

---

## ✅ What's Already Built

| Module | File | Status |
|---|---|---|
| News Scraper | `backend/src/scraper.py` | ✅ Done — RSS, HN, GitHub, HuggingFace, Google News |
| Story Cleaner + Scorer | `backend/src/cleaner.py` | ✅ Done — LLM cleaning, image extraction, value scoring |
| Podcast Script Writer | `backend/src/writer.py` | ✅ Done — 3-agent dialogue (Alex/Joy/Bob personalities) |
| Text-to-Speech | `backend/src/tts.py` | ✅ Done — edge-tts voices, MP3 stitching |
| Video Renderer | `backend/src/renderer.py` | ✅ Done — static image + audio → MP4 via FFmpeg |
| Database | `backend/src/db.py` | ✅ Done — SQLite, stories/episodes/sources tables |
| REST API | `backend/src/server.py` | ✅ Done — FastAPI, all pipeline endpoints |
| Control Room UI | `backend/static/` | ✅ Done — Feed Curation, Episodes, Settings tabs |
| Carousel Generator | `backend/carousel/generate_carousel.py` | ✅ Done — 5-slide PPTX with LLM content + AI images |
| Brand Config | `backend/carousel/brand_config.json` | ✅ Done — customizable per-brand settings |

---

## 🚧 What's Left to Build

---

### PHASE 1 — Fix & Stabilize (Do First)

---

#### 1.1 — Fix Git Merge Conflicts in Frontend
**Status:** Blocked — `index.html` and `app.js` both have `<<<<<<< HEAD` conflict markers that will break the UI.

**What to do:** Resolve merge conflicts in both files, keeping the best version of each section.

**Prompt to use:**
```
I have two files with unresolved git merge conflicts: backend/static/index.html and backend/static/app.js.
Each file has <<<<<<< HEAD ... ======= ... >>>>>>> conflict markers.
Please read both files, resolve all conflicts by keeping the most complete/correct version of each section,
and rewrite the files cleanly with no conflict markers remaining.
```

---

#### 1.2 — Auto-Story Selection (Best Stories Pipeline)
**Status:** Missing — `value_score` is calculated but no code automatically picks top stories for the daily run. A human must manually approve in the UI.

**What to do:** Add an `/api/auto-approve` endpoint and a Python function that reads all `scraped` stories, sorts by `value_score` DESC, and auto-approves the top N (e.g. top 5).

**Prompt to use:**
```
In backend/src/db.py and backend/src/server.py for the AIPulse app, add:
1. A db function `auto_approve_top_stories(n=5)` that selects the top N stories with status='scraped'
   ordered by value_score DESC and sets their status to 'approved'.
2. A POST /api/auto-approve endpoint in server.py that calls this function.
   Accept an optional JSON body: { "limit": 5 }
This allows the daily scheduler to automatically select the best stories without human input.
```

---

### PHASE 2 — Daily Scheduler (The Core Automation)

---

#### 2.1 — Daily Pipeline Orchestrator Script
**Status:** Missing — There is no single script that chains all steps together automatically.

**What to do:** Create `backend/src/pipeline.py` — a master runner that executes the full pipeline in order: scrape → clean → auto-approve top stories → generate carousel for each story → generate podcast episode → post to social.

**Prompt to use:**
```
Create backend/src/pipeline.py for the AIPulse app.
This is the master daily pipeline orchestrator. It must run these steps in sequence:
1. scraper.run_scraper() — fetch new stories from all enabled sources
2. cleaner.run_cleaner() — clean, score, and categorize all scraped stories
3. Call /api/auto-approve or db.auto_approve_top_stories(5) — pick the best 5
4. For each approved story, run generate_carousel.py --story-id {id} to produce a PPTX
5. writer.create_daily_episode() — generate podcast script from approved stories
6. tts.generate_audio_for_episode(episode_id) — synthesize audio
7. renderer.generate_video_for_episode(episode_id) — render MP4
8. Call the social poster (Phase 3) to publish each carousel and the video
Log each step with timestamps. If any step fails, log the error and continue to next step.
Write results summary to backend/output/pipeline_log.json.
Add a __main__ block so it can be run with: python pipeline.py
```

---

#### 2.2 — Windows Task Scheduler Setup (Auto Daily Run)
**Status:** Missing — Nothing triggers the pipeline automatically at a set time each day.

**What to do:** Create a `.bat` file and instructions to register the pipeline as a Windows scheduled task that runs at 7am daily.

**Prompt to use:**
```
Create two files for the AIPulse app:
1. backend/run_pipeline.bat — a Windows batch file that:
   - Activates the correct Python virtual environment (or uses system Python)
   - Runs: python backend/src/pipeline.py
   - Logs output to backend/output/pipeline_log.txt with today's date appended
2. backend/schedule_setup.bat — a one-time setup script that uses Windows Task Scheduler
   (schtasks command) to register run_pipeline.bat to run daily at 07:00 AM.
   Task name: AIPulseDailyPipeline
Include comments explaining how to run the setup script once.
```

---

### PHASE 3 — Social Media Publishing

---

#### 3.1 — Meta Graph API Integration (Facebook + Instagram)
**Status:** Missing — The "Social Accounts" and "Distribute" tabs exist in the UI but no backend publishing code exists.

**What to do:** Create `backend/src/publisher.py` with functions to post to Facebook Pages and Instagram Business accounts via the Meta Graph API.

**Prompt to use:**
```
Create backend/src/publisher.py for the AIPulse app.
Implement Meta Graph API posting for Facebook and Instagram.

Functions to build:
1. post_to_facebook_page(page_id, access_token, message, image_path=None)
   - If image_path provided: upload photo + caption using /PAGE_ID/photos endpoint
   - Otherwise: text post using /PAGE_ID/feed endpoint
   - Return: { success: bool, post_id: str, error: str }

2. post_carousel_to_instagram(ig_user_id, access_token, image_paths: list, caption: str)
   - Use the Instagram Graph API carousel post flow:
     a. Upload each image as a media container (POST /ig_user_id/media, is_carousel_item=true)
     b. Create a carousel container (POST /ig_user_id/media, media_type=CAROUSEL, children=[...])
     c. Publish (POST /ig_user_id/media_publish, creation_id=...)
   - Return: { success: bool, post_id: str, error: str }

3. post_reel_to_instagram(ig_user_id, access_token, video_path: str, caption: str)
   - Use resumable video upload for Reels
   - Return: { success: bool, post_id: str, error: str }

Store page_id, ig_user_id, and access_token in the .env file.
Add proper error handling and print logging throughout.
```

---

#### 3.2 — Social Publishing API Endpoints
**Status:** Missing — No server endpoints to trigger publishing from the UI "Distribute" tab.

**What to do:** Add publish endpoints to `server.py` that call `publisher.py`.

**Prompt to use:**
```
In backend/src/server.py for the AIPulse app, add the following API endpoints that use publisher.py:

POST /api/publish/facebook
  Body: { "episode_id": int, "story_id": int (optional), "message": str }
  Logic: if story_id provided, post the carousel images for that story. Otherwise post episode MP4.

POST /api/publish/instagram/carousel
  Body: { "story_id": int, "caption": str }
  Logic: convert the story's carousel PPTX slides to images (use LibreOffice or python-pptx),
  then post as Instagram carousel.

POST /api/publish/instagram/reel
  Body: { "episode_id": int, "caption": str }
  Logic: post the episode MP4 as an Instagram Reel.

Each endpoint should return { "success": bool, "post_id": str, "platform": str, "error": str }.
Store post results in a new 'posts' table in SQLite (columns: id, platform, story_id, episode_id, post_id, status, created_at).
```

---

#### 3.3 — PPTX to Images Converter (for Instagram Carousel)
**Status:** Missing — Instagram needs image files, but carousel output is a .pptx. Need conversion.

**What to do:** Add a function to convert carousel PPTX slides into PNG images.

**Prompt to use:**
```
In the AIPulse project, create backend/src/pptx_to_images.py.
This module converts a .pptx carousel file into a list of PNG images, one per slide.

Function: convert_pptx_to_images(pptx_path: str, output_dir: str) -> list[str]
  - Try method 1: Use LibreOffice headless (soffice --headless --convert-to png)
  - If LibreOffice not available, try method 2: Use python-pptx + Pillow to render each slide
    (render slide thumbnails by iterating shapes and drawing text/images onto a PIL canvas,
    output at 1080x1080 for Instagram square format)
  - Return list of output PNG file paths in slide order
  - Log clearly which method was used

Also add a test block at the bottom:
  if __name__ == "__main__":
      import sys
      paths = convert_pptx_to_images(sys.argv[1], "output/slide_images")
      print("Generated:", paths)
```

---

### PHASE 4 — Reel / Short Video Generation

---

#### 4.1 — Dynamic Reel Generator (Animated Video)
**Status:** Partially done — Current renderer.py only creates a static background + audio MP4. No text overlays, no animations, no reel-format video.

**What to do:** Create `backend/src/reel_generator.py` that produces vertical (9:16) short-form video with text overlays, story headline, branding, and background music using MoviePy or FFmpeg.

**Prompt to use:**
```
Create backend/src/reel_generator.py for the AIPulse app.
This generates a vertical (1080x1920, 9:16) Instagram/TikTok Reel from a story.

Use MoviePy (pip install moviepy) or FFmpeg subprocess calls.

Function: generate_reel_for_story(story_id: int, output_path: str = None) -> str

Pipeline:
1. Load story from aipulse.db (title, clean_summary, category, images_json)
2. Download the best story image (from images_json) as the background — blur and darken it to 1080x1920
   If no image, use a solid dark background with animated gradient overlay (use FFmpeg drawgradient filter)
3. Add text overlays using FFmpeg drawtext or MoviePy TextClip:
   - Top pill badge: story category (e.g. "MODEL RELEASE") — green pill, white text, top center
   - Main headline: story title, large bold white text, center screen, word-wrapped to ~4 words per line
   - Source credit: small text bottom left (e.g. "Source: TechCrunch")
   - Branding: "@yourhandle" or brand name, bottom right
4. Add a subtle zoom-in animation on the background (Ken Burns effect via FFmpeg scale/zoompan filter)
5. Add the episode audio OR a short 30-second background music track (if backend/audio/bg_music.mp3 exists)
6. Output at 1080x1920 as an MP4, ~30 seconds, H.264, AAC audio
7. Save to backend/output/reel_{story_id}.mp4 and update stories table: reel_path column

Add a __main__ block: python reel_generator.py --story-id 42
```

---

#### 4.2 — Add Reel Path to Database
**Status:** Missing — DB schema has no `reel_path` column for stories.

**Prompt to use:**
```
In backend/src/db.py for AIPulse, add the following to init_db():
- In the new_columns list, add: ("reel_path", "TEXT")
- Add a function: update_story_reel_path(story_id: int, reel_path: str)
  that does: UPDATE stories SET reel_path = ? WHERE id = ?
Also add a GET /api/stories/{story_id}/reel endpoint in server.py that returns
{ "reel_path": str, "reel_url": str } — serving the file from /static/reels/.
```

---

### PHASE 5 — UI & Dashboard Polish

---

#### 5.1 — Distribute Tab: Real Publishing UI
**Status:** Stubbed — The "Distribute" tab exists in the frontend but has no real publish buttons connected to the new API endpoints.

**Prompt to use:**
```
In backend/static/app.js and backend/static/index.html for AIPulse, build out the "Distribute" tab fully.

It should show:
1. A list of today's approved stories, each with:
   - Story title
   - "Post Carousel to Instagram" button → calls POST /api/publish/instagram/carousel
   - "Post to Facebook" button → calls POST /api/publish/facebook
   - "Post Reel" button → calls POST /api/publish/instagram/reel
   - Status badge showing last post result (posted / failed / pending)
2. An "Episode" section showing the latest episode with:
   - "Post Episode Reel to Instagram" button
   - "Post Episode to Facebook" button
3. A "Post All" button at the top that triggers all platforms for all approved content

Show loading spinners during API calls and toast notifications on success/failure.
Style matches the existing dark theme in style.css.
```

---

#### 5.2 — Pipeline Status Dashboard
**Status:** Missing — No way to see if the daily pipeline ran, what it did, or if anything failed.

**Prompt to use:**
```
Add a "Pipeline" tab to the AIPulse control room UI (backend/static/index.html and app.js).

Frontend:
- Add a nav button "⚙️ Pipeline" that shows tab-pipeline
- Show a "Run Pipeline Now" button → calls POST /api/pipeline/run
- Show a log feed: last 50 lines from pipeline_log.json, auto-refreshing every 30s
- Show a status summary row: Stories scraped today / Stories approved / Carousels made / Reels made / Posts published

Backend (server.py):
- POST /api/pipeline/run — runs pipeline.py as a background subprocess, streams output to pipeline_log.json
- GET /api/pipeline/status — returns { last_run: datetime, stories_scraped: int, stories_approved: int,
  carousels_generated: int, reels_generated: int, posts_published: int }
- GET /api/pipeline/log — returns last 100 lines of pipeline_log.txt as a list of strings
```

---

### PHASE 6 — Content Quality & Templates

---

#### 6.1 — Multiple Carousel Templates
**Status:** Only one PPTX template exists (`carousel_template.pptx`). Different post types need different layouts.

**Prompt to use:**
```
In the AIPulse carousel system, add support for multiple PPTX templates.

1. In brand_config.json, add a "templates" array:
   { "templates": ["carousel_template.pptx", "template_minimal.pptx", "template_bold.pptx"] }

2. In generate_carousel.py, modify the LLM prompt to also return a "template" field
   suggesting which template fits the story type ("bold" for breaking news, "minimal" for research).

3. Add a select_template(story, content) function that maps story category to a template file.
   - "Model Release" → template_bold.pptx
   - "Research Paper" → template_minimal.pptx
   - Everything else → carousel_template.pptx (default)

4. Duplicate and rename carousel_template.pptx to template_minimal.pptx and template_bold.pptx
   (we'll customise layouts separately). Wire up the selection logic.
```

---

#### 6.2 — Auto-Caption Generator for Posts
**Status:** Missing — Publishing endpoints need captions. No system generates Instagram/Facebook captions with hashtags.

**Prompt to use:**
```
Create backend/src/caption_generator.py for AIPulse.

Function: generate_caption(story: dict, platform: str = "instagram") -> str
  - Call the LLM (same pattern as writer.py / cleaner.py — use OPENROUTER_API_KEY)
  - Prompt it to write a platform-appropriate caption for the story:
    * Instagram: 3-4 punchy sentences, 1 question, 5 relevant hashtags, ends with a CTA ("Follow for daily AI")
    * Facebook: 4-6 sentences, more conversational, 2-3 hashtags, link back to source
    * TikTok: 2-3 short punchy lines, 5 trending hashtags, ultra casual tone
  - Return the caption as a plain string
  - Fallback (no API key): return story title + top 5 hashtags from niche_tags field

Add to publisher.py: call generate_caption(story, platform) automatically before each post
if the caller doesn't pass a caption explicitly.
```

---

## 📋 Build Order Checklist

Work through these in order. Each phase builds on the previous.

- [ ] **1.1** Fix git merge conflicts in `index.html` + `app.js`
- [ ] **1.2** Auto-approve top stories endpoint (`/api/auto-approve`)
- [ ] **2.1** Master pipeline orchestrator (`pipeline.py`)
- [ ] **2.2** Windows Task Scheduler setup (daily 7am auto-run)
- [ ] **3.1** Meta Graph API publisher (`publisher.py`) — Facebook + Instagram
- [ ] **3.2** Publishing API endpoints in `server.py`
- [ ] **3.3** PPTX → PNG image converter (`pptx_to_images.py`)
- [ ] **4.1** Reel / short video generator (`reel_generator.py`)
- [ ] **4.2** Add `reel_path` column to DB + `/api/stories/{id}/reel` endpoint
- [ ] **5.1** Distribute tab: wire up real publish buttons in the UI
- [ ] **5.2** Pipeline status dashboard tab in the UI
- [ ] **6.1** Multiple carousel templates support
- [ ] **6.2** Auto-caption generator (`caption_generator.py`)

---

## 🔑 API Keys Needed

| Key | What For | Where to Get |
|---|---|---|
| `OPENROUTER_API_KEY` or `OPENAI_API_KEY` | LLM (already wired) | openrouter.ai or platform.openai.com |
| `ANTHROPIC_API_KEY` | Claude (already wired) | console.anthropic.com |
| `PIAPI_API_KEY` | AI image generation (already wired) | piapi.ai |
| `META_PAGE_ACCESS_TOKEN` | Facebook + Instagram posting | Meta for Developers → Graph API Explorer |
| `META_PAGE_ID` | Facebook Page ID | Meta Business Suite |
| `META_IG_USER_ID` | Instagram Business account ID | Meta Graph API |

---

*Generated: June 2026 — AIPulse v1 Roadmap*
