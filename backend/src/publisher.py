"""
publisher.py
------------
Meta Graph API publisher for Facebook Pages and Instagram Business accounts.
Handles: Facebook post/photo, Instagram carousel, Instagram Reel.

Required .env keys:
    META_PAGE_ACCESS_TOKEN  — long-lived Page access token
    META_PAGE_ID            — Facebook Page ID
    META_IG_USER_ID         — Instagram Business account ID
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db
import caption_generator

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, ".env"))

PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.getenv("META_PAGE_ID", "")
IG_USER_ID        = os.getenv("META_IG_USER_ID", "")
GRAPH_API_BASE    = "https://graph.facebook.com/v19.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers():
    return {"Authorization": f"Bearer {PAGE_ACCESS_TOKEN}"}

def _check_credentials():
    missing = []
    if not PAGE_ACCESS_TOKEN: missing.append("META_PAGE_ACCESS_TOKEN")
    if not PAGE_ID:           missing.append("META_PAGE_ID")
    return missing

def _check_ig_credentials():
    missing = _check_credentials()
    if not IG_USER_ID: missing.append("META_IG_USER_ID")
    return missing

def _result(success, post_id=None, platform="unknown", error=None):
    return {"success": success, "post_id": post_id, "platform": platform, "error": error}


# ---------------------------------------------------------------------------
# Facebook
# ---------------------------------------------------------------------------

def post_to_facebook_page(message: str, image_path: str = None) -> dict:
    """
    Post a text update or photo to the configured Facebook Page.
    Returns: { success, post_id, platform, error }
    """
    missing = _check_credentials()
    if missing:
        return _result(False, platform="facebook", error=f"Missing env vars: {missing}")

    try:
        if image_path and os.path.exists(image_path):
            # Photo post
            url = f"{GRAPH_API_BASE}/{PAGE_ID}/photos"
            with open(image_path, "rb") as f:
                resp = requests.post(
                    url,
                    params={"access_token": PAGE_ACCESS_TOKEN},
                    files={"source": f},
                    data={"caption": message},
                    timeout=60,
                )
        else:
            # Text-only post
            url = f"{GRAPH_API_BASE}/{PAGE_ID}/feed"
            resp = requests.post(
                url,
                params={"access_token": PAGE_ACCESS_TOKEN},
                json={"message": message},
                timeout=30,
            )

        if resp.status_code == 200:
            post_id = resp.json().get("id", "")
            print(f"[Facebook] Posted successfully. ID: {post_id}")
            return _result(True, post_id=post_id, platform="facebook")
        else:
            err = resp.json().get("error", {}).get("message", resp.text)
            print(f"[Facebook] Post failed: {err}")
            return _result(False, platform="facebook", error=err)

    except Exception as e:
        print(f"[Facebook] Exception: {e}")
        return _result(False, platform="facebook", error=str(e))


# ---------------------------------------------------------------------------
# Instagram — Carousel
# ---------------------------------------------------------------------------

def post_carousel_to_instagram(image_paths: list, caption: str) -> dict:
    """
    Post a multi-image carousel to Instagram Business account.
    Steps: upload each image as carousel item → create carousel container → publish.
    Returns: { success, post_id, platform, error }
    """
    missing = _check_ig_credentials()
    if missing:
        return _result(False, platform="instagram_carousel", error=f"Missing env vars: {missing}")

    if not image_paths:
        return _result(False, platform="instagram_carousel", error="No image paths provided")

    try:
        # Step 1: Upload each image as a carousel item container
        item_ids = []
        for idx, img_path in enumerate(image_paths[:10]):  # Instagram max 10
            if not os.path.exists(img_path):
                print(f"  [IG Carousel] Skipping missing image: {img_path}")
                continue

            # Upload image to a public URL via FB photo upload (unpublished)
            upload_url = f"{GRAPH_API_BASE}/{IG_USER_ID}/media"
            with open(img_path, "rb") as f:
                upload_resp = requests.post(
                    upload_url,
                    params={"access_token": PAGE_ACCESS_TOKEN},
                    data={"is_carousel_item": "true", "media_type": "IMAGE"},
                    files={"image": f},
                    timeout=60,
                )

            if upload_resp.status_code != 200:
                err = upload_resp.json().get("error", {}).get("message", upload_resp.text)
                print(f"  [IG Carousel] Image {idx} upload failed: {err}")
                continue

            item_id = upload_resp.json().get("id")
            if item_id:
                item_ids.append(item_id)
                print(f"  [IG Carousel] Uploaded image {idx}: {item_id}")

        if not item_ids:
            return _result(False, platform="instagram_carousel", error="All image uploads failed")

        # Step 2: Create carousel container
        container_url = f"{GRAPH_API_BASE}/{IG_USER_ID}/media"
        container_resp = requests.post(
            container_url,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json={
                "media_type": "CAROUSEL",
                "children": item_ids,
                "caption": caption,
            },
            timeout=30,
        )

        if container_resp.status_code != 200:
            err = container_resp.json().get("error", {}).get("message", container_resp.text)
            return _result(False, platform="instagram_carousel", error=f"Container creation failed: {err}")

        creation_id = container_resp.json().get("id")
        print(f"  [IG Carousel] Container created: {creation_id}")

        # Step 3: Wait briefly then publish
        time.sleep(2)
        publish_url = f"{GRAPH_API_BASE}/{IG_USER_ID}/media_publish"
        publish_resp = requests.post(
            publish_url,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json={"creation_id": creation_id},
            timeout=30,
        )

        if publish_resp.status_code == 200:
            post_id = publish_resp.json().get("id", "")
            print(f"[IG Carousel] Published. Post ID: {post_id}")
            return _result(True, post_id=post_id, platform="instagram_carousel")
        else:
            err = publish_resp.json().get("error", {}).get("message", publish_resp.text)
            return _result(False, platform="instagram_carousel", error=f"Publish failed: {err}")

    except Exception as e:
        print(f"[IG Carousel] Exception: {e}")
        return _result(False, platform="instagram_carousel", error=str(e))


# ---------------------------------------------------------------------------
# Instagram — Reel
# ---------------------------------------------------------------------------

def post_reel_to_instagram(video_path: str, caption: str) -> dict:
    """
    Post a vertical MP4 as an Instagram Reel using resumable upload.
    Returns: { success, post_id, platform, error }
    """
    missing = _check_ig_credentials()
    if missing:
        return _result(False, platform="instagram_reel", error=f"Missing env vars: {missing}")

    if not os.path.exists(video_path):
        return _result(False, platform="instagram_reel", error=f"Video not found: {video_path}")

    try:
        file_size = os.path.getsize(video_path)

        # Step 1: Initialize resumable upload session
        init_url = f"{GRAPH_API_BASE}/{IG_USER_ID}/media"
        init_resp = requests.post(
            init_url,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json={
                "media_type": "REELS",
                "video_url": None,   # We'll use upload_type=resumable
                "upload_type": "resumable",
                "caption": caption,
            },
            timeout=30,
        )

        if init_resp.status_code != 200:
            # Fallback: try direct video_url method via publicly accessible path
            # (would need a public URL — skip and report error)
            err = init_resp.json().get("error", {}).get("message", init_resp.text)
            return _result(False, platform="instagram_reel", error=f"Reel init failed: {err}. Ensure video is publicly accessible or use video_url method.")

        upload_info = init_resp.json()
        creation_id = upload_info.get("id")
        upload_url  = upload_info.get("uri", "")

        print(f"  [IG Reel] Upload session created: {creation_id}")

        # Step 2: Upload video bytes
        with open(video_path, "rb") as f:
            upload_resp = requests.post(
                upload_url if upload_url.startswith("http") else f"https://rupload.facebook.com/video-upload/v19.0/{creation_id}",
                headers={
                    "Authorization": f"OAuth {PAGE_ACCESS_TOKEN}",
                    "Content-Type": "application/octet-stream",
                    "offset": "0",
                    "file_size": str(file_size),
                },
                data=f,
                timeout=300,
            )

        if upload_resp.status_code not in (200, 204):
            return _result(False, platform="instagram_reel", error=f"Video upload failed: {upload_resp.text}")

        print(f"  [IG Reel] Video uploaded. Waiting for processing...")
        time.sleep(10)  # Give Instagram time to process

        # Step 3: Publish
        publish_url = f"{GRAPH_API_BASE}/{IG_USER_ID}/media_publish"
        publish_resp = requests.post(
            publish_url,
            params={"access_token": PAGE_ACCESS_TOKEN},
            json={"creation_id": creation_id},
            timeout=30,
        )

        if publish_resp.status_code == 200:
            post_id = publish_resp.json().get("id", "")
            print(f"[IG Reel] Published. Post ID: {post_id}")
            return _result(True, post_id=post_id, platform="instagram_reel")
        else:
            err = publish_resp.json().get("error", {}).get("message", publish_resp.text)
            return _result(False, platform="instagram_reel", error=f"Publish failed: {err}")

    except Exception as e:
        print(f"[IG Reel] Exception: {e}")
        return _result(False, platform="instagram_reel", error=str(e))


# ---------------------------------------------------------------------------
# High-level helpers (used by pipeline.py)
# ---------------------------------------------------------------------------

def publish_story_carousel(story_id: int, platforms: list = None) -> list:
    """
    Generate caption + post the story's carousel images to requested platforms.
    platforms defaults to ["instagram", "facebook"]
    """
    if platforms is None:
        platforms = ["instagram", "facebook"]

    story = db.get_story_by_id(story_id)
    if not story:
        return [_result(False, platform=p, error=f"Story {story_id} not found") for p in platforms]

    results = []

    for platform in platforms:
        caption = caption_generator.generate_caption(story, platform)
        post_db_id = db.create_post_record(platform, story_id=story_id)

        if platform == "instagram":
            # Convert carousel PPTX to images first
            carousel_path = story.get("carousel_path")
            if not carousel_path or not os.path.exists(carousel_path):
                res = _result(False, platform="instagram_carousel", error="No carousel PPTX found for story")
                db.update_post_record(post_db_id, status="failed", error=res["error"])
                results.append(res)
                continue

            try:
                from pptx_to_images import convert_pptx_to_images
                output_dir = os.path.join(backend_dir, "output", f"carousel_{story_id}_images")
                image_paths = convert_pptx_to_images(carousel_path, output_dir)
            except Exception as e:
                res = _result(False, platform="instagram_carousel", error=f"PPTX conversion failed: {e}")
                db.update_post_record(post_db_id, status="failed", error=res["error"])
                results.append(res)
                continue

            res = post_carousel_to_instagram(image_paths, caption)

        elif platform == "facebook":
            # Post first carousel image + caption to Facebook
            carousel_path = story.get("carousel_path")
            img_path = None
            if carousel_path and os.path.exists(carousel_path):
                try:
                    from pptx_to_images import convert_pptx_to_images
                    output_dir = os.path.join(backend_dir, "output", f"carousel_{story_id}_images")
                    imgs = convert_pptx_to_images(carousel_path, output_dir)
                    img_path = imgs[0] if imgs else None
                except Exception:
                    pass
            res = post_to_facebook_page(caption, img_path)
        else:
            res = _result(False, platform=platform, error=f"Unknown platform: {platform}")

        if res["success"]:
            db.update_post_record(post_db_id, post_id=res["post_id"], status="posted")
        else:
            db.update_post_record(post_db_id, status="failed", error=res.get("error"))

        results.append(res)

    return results


def publish_episode_reel(episode_id: int, platforms: list = None) -> list:
    """Post the episode MP4 reel to requested platforms."""
    if platforms is None:
        platforms = ["instagram", "facebook"]

    episode = db.get_episode_by_id(episode_id)
    if not episode:
        return [_result(False, platform=p, error=f"Episode {episode_id} not found") for p in platforms]

    # Prefer the reel (vertical) path, fall back to standard video
    video_path = episode.get("reel_path") or episode.get("video_path")
    if not video_path or not os.path.exists(video_path):
        return [_result(False, platform=p, error="No video file found for episode") for p in platforms]

    caption = f"🎙️ AIPulse Daily Episode: {episode['title']} — your AI news briefing. Follow for daily updates. #AI #TechNews #AIPulse"
    results = []

    for platform in platforms:
        post_db_id = db.create_post_record(platform, episode_id=episode_id)
        if platform == "instagram":
            res = post_reel_to_instagram(video_path, caption)
        elif platform == "facebook":
            res = post_to_facebook_page(caption, video_path)
        else:
            res = _result(False, platform=platform, error=f"Unknown platform: {platform}")

        if res["success"]:
            db.update_post_record(post_db_id, post_id=res["post_id"], status="posted")
        else:
            db.update_post_record(post_db_id, status="failed", error=res.get("error"))

        results.append(res)

    return results


if __name__ == "__main__":
    print("Meta credentials loaded:")
    print(f"  PAGE_ID:    {PAGE_ID or '(not set)'}")
    print(f"  IG_USER_ID: {IG_USER_ID or '(not set)'}")
    print(f"  TOKEN:      {'SET' if PAGE_ACCESS_TOKEN else '(not set)'}")
