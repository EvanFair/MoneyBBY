"""
caption_generator.py
---------------------
Generate platform-appropriate captions for social media posts.
"""

import os
import json
import requests
import sys
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, ".env"))

API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL   = os.getenv("LLM_MODEL", "meta-llama/llama-3-70b-instruct:free")


def generate_caption(story: dict, platform: str = "instagram") -> str:
    """
    Generate a platform-appropriate caption for a story.
    platform: "instagram" | "facebook" | "tiktok"
    """
    title        = story.get("title", "AI Update")
    summary      = story.get("clean_summary") or story.get("summary", "")
    category     = story.get("category", "AI & Tech")
    source       = story.get("source", "")
    url          = story.get("url", "")
    niche_tags   = story.get("niche_tags", "")

    # Parse niche tags
    tags = []
    if niche_tags:
        try:
            tags = json.loads(niche_tags) if niche_tags.startswith("[") else niche_tags.split(",")
            tags = [t.strip() for t in tags if t.strip()]
        except Exception:
            tags = []

    if not API_KEY or API_KEY.startswith("your_"):
        return _fallback_caption(title, tags, platform, url)

    platform_instructions = {
        "instagram": (
            "3-4 punchy sentences. End with a question to drive comments. "
            "Then 5 relevant hashtags. End with: Follow for daily AI updates."
        ),
        "facebook": (
            "4-6 conversational sentences explaining why this matters. "
            "2-3 hashtags. Include source URL at end."
        ),
        "tiktok": (
            "2-3 ultra-short punchy lines. Very casual Gen-Z tone. "
            "5 trending hashtags. Under 150 characters total."
        ),
    }

    instructions = platform_instructions.get(platform, platform_instructions["instagram"])

    prompt = f"""Write a {platform} caption for this AI/tech story.

Story Title: {title}
Category: {category}
Summary: {summary[:400]}
Source: {source}
URL: {url}

Instructions: {instructions}

Write only the caption text. No explanation, no quotes around it."""

    try:
        url_api = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }
        resp = requests.post(url_api, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[Caption] LLM error: {e}")

    return _fallback_caption(title, tags, platform, url)


def _fallback_caption(title, tags, platform, url=""):
    hashtags = " ".join(f"#{t.replace(' ', '')}" for t in tags[:5]) if tags else "#AI #TechNews #AIPulse"
    if platform == "tiktok":
        return f"{title[:100]} {hashtags}"
    if platform == "facebook":
        return f"{title}\n\n{hashtags}\n{url}"
    return f"{title}\n\nWhat do you think? 👇\n\n{hashtags}\n\nFollow for daily AI updates."
