"""
pipeline.py
-----------
Master daily pipeline orchestrator for AIPulse.

Runs in sequence:
  1. Scrape new stories from all enabled sources
  2. Clean + score all scraped stories (LLM)
  3. Auto-approve top N stories by value_score
  4. Generate carousel PPTX for each approved story
  5. Generate podcast episode script → TTS audio → MP4 video
  6. Generate vertical Reel for each approved story
  7. Publish to Facebook + Instagram (if credentials set)
  8. Write pipeline_log.json with results summary

Usage:
    python pipeline.py                     # full run, publish
    python pipeline.py --no-publish        # skip social posting
    python pipeline.py --top-stories 3    # approve top 3 instead of 5
    python pipeline.py --skip-carousel    # skip carousel gen
    python pipeline.py --skip-reel        # skip reel gen
"""

import argparse
import json
import os
import sys
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db
import scraper
import cleaner
import writer
import tts
import renderer

BACKEND_DIR = Path(__file__).parent.parent
OUTPUT_DIR  = BACKEND_DIR / "output"
LOG_PATH    = OUTPUT_DIR / "pipeline_log.json"
LOG_TXT     = OUTPUT_DIR / "pipeline_log.txt"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Logging ──────────────────────────────────────────────────────────────────

_log_lines = []

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    _log_lines.append(line)


def _save_log(summary: dict):
    """Append today's run to pipeline_log.txt and write pipeline_log.json."""
    # Text log
    with open(LOG_TXT, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Run: {datetime.now().isoformat()}\n")
        for line in _log_lines:
            f.write(line + "\n")

    # JSON summary
    history = []
    if LOG_PATH.exists():
        try:
            history = json.loads(LOG_PATH.read_text())
        except Exception:
            history = []
    history.insert(0, summary)
    history = history[:30]  # Keep last 30 runs
    LOG_PATH.write_text(json.dumps(history, indent=2))


# ─── Step runners ─────────────────────────────────────────────────────────────

def step_scrape() -> int:
    log("STEP 1 — Scraping stories from all enabled sources...")
    try:
        scraper.run_scraper()
        count = len(db.get_stories_by_status("scraped"))
        log(f"  Scrape complete. Total pending stories: {count}")
        return count
    except Exception as e:
        log(f"  ERROR in scraper: {e}")
        return 0


def step_clean() -> int:
    log("STEP 2 — Cleaning and scoring stories with LLM...")
    try:
        cleaner.run_cleaner()
        pending = db.get_top_scraped_stories(100)
        log(f"  Cleaning complete. Stories with scores: {len(pending)}")
        return len(pending)
    except Exception as e:
        log(f"  ERROR in cleaner: {e}")
        return 0


def step_auto_approve(n: int = 5) -> list:
    log(f"STEP 3 — Auto-approving top {n} stories by value_score...")
    try:
        ids = db.auto_approve_top_stories(n)
        for sid in ids:
            story = db.get_story_by_id(sid)
            score = story.get("value_score", "?") if story else "?"
            title = story.get("title", "?")[:60] if story else "?"
            log(f"  ✓ #{sid} [{score}/10] {title}")
        return ids
    except Exception as e:
        log(f"  ERROR in auto-approve: {e}")
        return []


def step_generate_carousels(story_ids: list) -> dict:
    log(f"STEP 4 — Generating carousel PPTX for {len(story_ids)} stories...")
    results = {}
    carousel_script = BACKEND_DIR / "carousel" / "generate_carousel.py"

    if not carousel_script.exists():
        log(f"  WARNING: carousel script not found at {carousel_script}")
        return results

    for story_id in story_ids:
        try:
            output_path = str(OUTPUT_DIR / f"carousel_{story_id}.pptx")
            cmd = [sys.executable, str(carousel_script), "--story-id", str(story_id), "--output", output_path]
            log(f"  Generating carousel for story #{story_id}...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and Path(output_path).exists():
                db.update_story_carousel_path(story_id, output_path)
                results[story_id] = output_path
                log(f"  ✓ Carousel saved: {output_path}")
            else:
                log(f"  ✗ Carousel failed for #{story_id}: {result.stderr[-200:]}")
                results[story_id] = None
        except Exception as e:
            log(f"  ✗ Carousel error for #{story_id}: {e}")
            results[story_id] = None

    return results


def step_generate_episode() -> tuple:
    log("STEP 5 — Generating podcast episode (script + audio + video)...")
    try:
        date_str = datetime.now().strftime("%B %d, %Y")
        title = f"AIPulse Daily — {date_str}"
        result = writer.create_daily_episode(title)
        if not result:
            log("  ✗ Episode creation failed (no approved stories?)")
            return None, None

        episode_id, script = result
        log(f"  Script generated. Episode ID: {episode_id} ({len(script)} lines)")

        log("  Synthesizing TTS audio...")
        audio_path = tts.generate_audio_for_episode(episode_id)
        if audio_path:
            log(f"  ✓ Audio ready: {audio_path}")
        else:
            log("  ✗ Audio synthesis failed.")

        log("  Rendering MP4 video...")
        video_path = renderer.generate_video_for_episode(episode_id)
        if video_path:
            log(f"  ✓ Video ready: {video_path}")
        else:
            log("  ✗ Video render failed.")

        return episode_id, video_path

    except Exception as e:
        log(f"  ERROR in episode generation: {e}")
        traceback.print_exc()
        return None, None


def step_generate_reels(story_ids: list) -> dict:
    log(f"STEP 6 — Generating vertical Reels for {len(story_ids)} stories...")
    results = {}
    try:
        from reel_generator import generate_reel_for_story
    except ImportError as e:
        log(f"  ERROR: Could not import reel_generator: {e}")
        return results

    for story_id in story_ids:
        try:
            log(f"  Generating reel for story #{story_id}...")
            path = generate_reel_for_story(story_id)
            results[story_id] = path
            if path:
                log(f"  ✓ Reel saved: {path}")
            else:
                log(f"  ✗ Reel failed for #{story_id}")
        except Exception as e:
            log(f"  ✗ Reel error for #{story_id}: {e}")
            results[story_id] = None

    return results


def step_publish(story_ids: list, episode_id: int) -> dict:
    log("STEP 7 — Publishing to Facebook + Instagram...")
    summary = {"carousels": [], "episode": []}
    try:
        from publisher import publish_story_carousel, publish_episode_reel
    except ImportError as e:
        log(f"  ERROR: Could not import publisher: {e}")
        return summary

    # Publish carousel for each story
    for story_id in story_ids:
        try:
            log(f"  Publishing carousel for story #{story_id}...")
            results = publish_story_carousel(story_id)
            for r in results:
                status = "✓" if r["success"] else "✗"
                log(f"  {status} [{r['platform']}] {r.get('post_id', r.get('error', ''))}")
            summary["carousels"].append({"story_id": story_id, "results": results})
        except Exception as e:
            log(f"  ERROR publishing story #{story_id}: {e}")

    # Publish episode reel
    if episode_id:
        try:
            log(f"  Publishing episode #{episode_id} reel...")
            results = publish_episode_reel(episode_id)
            for r in results:
                status = "✓" if r["success"] else "✗"
                log(f"  {status} [{r['platform']}] {r.get('post_id', r.get('error', ''))}")
            summary["episode"] = results
        except Exception as e:
            log(f"  ERROR publishing episode: {e}")

    return summary


# ─── Main ─────────────────────────────────────────────────────────────────────

def run_pipeline(
    top_stories:    int  = 5,
    publish:        bool = True,
    skip_carousel:  bool = False,
    skip_reel:      bool = False,
) -> dict:
    start_time = datetime.now()
    log(f"{'='*60}")
    log(f"AIPulse Daily Pipeline — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'='*60}")

    summary = {
        "run_at":             start_time.isoformat(),
        "stories_scraped":    0,
        "stories_cleaned":    0,
        "stories_approved":   [],
        "carousels_generated": 0,
        "episode_id":         None,
        "reels_generated":    0,
        "posts_published":    0,
        "errors":             [],
    }

    try:
        # 1. Scrape
        summary["stories_scraped"] = step_scrape()

        # 2. Clean
        summary["stories_cleaned"] = step_clean()

        # 3. Auto-approve
        approved_ids = step_auto_approve(top_stories)
        summary["stories_approved"] = approved_ids

        if not approved_ids:
            log("  No stories approved — pipeline ending early.")
            _save_log(summary)
            return summary

        # 4. Carousels
        carousel_results = {}
        if not skip_carousel:
            carousel_results = step_generate_carousels(approved_ids)
            summary["carousels_generated"] = sum(1 for v in carousel_results.values() if v)
        else:
            log("STEP 4 — Carousel generation SKIPPED (--skip-carousel flag).")

        # 5. Episode
        episode_id, _ = step_generate_episode()
        summary["episode_id"] = episode_id

        # 6. Reels
        reel_results = {}
        if not skip_reel:
            reel_results = step_generate_reels(approved_ids)
            summary["reels_generated"] = sum(1 for v in reel_results.values() if v)
        else:
            log("STEP 6 — Reel generation SKIPPED (--skip-reel flag).")

        # 7. Publish
        if publish:
            publish_summary = step_publish(approved_ids, episode_id)
            total_posts = sum(
                1 for r in (
                    [res for c in publish_summary["carousels"] for res in c.get("results", [])]
                    + publish_summary["episode"]
                )
                if r.get("success")
            )
            summary["posts_published"] = total_posts
        else:
            log("STEP 7 — Publishing SKIPPED (--no-publish flag).")

    except Exception as e:
        err = f"Pipeline fatal error: {e}"
        log(f"ERROR: {err}")
        traceback.print_exc()
        summary["errors"].append(err)

    end_time = datetime.now()
    elapsed  = (end_time - start_time).total_seconds()
    log(f"{'='*60}")
    log(f"Pipeline complete in {elapsed:.1f}s")
    log(f"  Stories scraped:    {summary['stories_scraped']}")
    log(f"  Stories approved:   {len(summary['stories_approved'])}")
    log(f"  Carousels made:     {summary['carousels_generated']}")
    log(f"  Episode ID:         {summary['episode_id']}")
    log(f"  Reels made:         {summary['reels_generated']}")
    log(f"  Posts published:    {summary['posts_published']}")

    _save_log(summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIPulse daily content pipeline")
    parser.add_argument("--no-publish",     action="store_true", help="Skip social media publishing")
    parser.add_argument("--top-stories",    type=int, default=5, help="Number of stories to approve (default 5)")
    parser.add_argument("--skip-carousel",  action="store_true", help="Skip carousel PPTX generation")
    parser.add_argument("--skip-reel",      action="store_true", help="Skip vertical reel generation")
    args = parser.parse_args()

    run_pipeline(
        top_stories   = args.top_stories,
        publish       = not args.no_publish,
        skip_carousel = args.skip_carousel,
        skip_reel     = args.skip_reel,
    )
