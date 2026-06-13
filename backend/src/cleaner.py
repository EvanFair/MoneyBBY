import os
import requests
import json
import sys
import re
import io
from PIL import Image
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from urllib.parse import urljoin

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, ".env"))

API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL   = os.getenv("LLM_MODEL", "meta-llama/llama-3-70b-instruct:free")

IMAGES_DIR = os.path.join(backend_dir, "static", "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

CATEGORIES = [
    "Model Release", "Open Source Repository", "Research Paper",
    "Hardware & GPU Infrastructure", "Developer Tooling & SDKs",
    "AI SaaS & Consumer Product", "Industry & Startups",
    "Robotics & Embodied AI", "Safety & Alignment"
]

_SKIP_PATTERNS     = re.compile(r'pixel|tracking|spacer|logo|icon|avatar|1x1', re.IGNORECASE)
_SKIP_URL_PATTERNS = re.compile(
    r'social-thumbnails|gradient\.png|placeholder|logo-square|favicon|default_bg|header-bg|menu|banner',
    re.IGNORECASE
)


def extract_article_details(url):
    result = {"full_text": "", "image_urls": []}
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        paragraphs = soup.find_all("p")
        result["full_text"] = " ".join(p.get_text(strip=True) for p in paragraphs)[:5000]

        image_urls = []
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            og_url = urljoin(url, og["content"])
            if not _SKIP_URL_PATTERNS.search(og_url):
                image_urls.append(og_url)

        for img in soup.find_all("img", src=True):
            src = img["src"]
            if src.startswith("data:") or _SKIP_PATTERNS.search(src):
                continue
            abs_url = urljoin(url, src)
            if _SKIP_URL_PATTERNS.search(abs_url):
                continue
            try:
                w = img.get("width")
                h = img.get("height")
                if w and int(w) < 250: continue
                if h and int(h) < 250: continue
            except (ValueError, TypeError):
                pass
            if abs_url not in image_urls:
                image_urls.append(abs_url)

        result["image_urls"] = image_urls[:5]
    except Exception as e:
        print(f"  Error extracting details from {url}: {e}")
    return result


def download_images(image_urls, story_id):
    downloaded = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for index, img_url in enumerate(image_urls):
        try:
            resp = requests.get(img_url, headers=headers, timeout=10)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            width, height = img.size
            if width < 250 or height < 250:
                continue
            # Filter out extreme aspect ratios (banners/strips)
            ratio = width / height if height > 0 else 0
            if ratio > 5 or ratio < 0.1:
                continue
            ext = img.format.lower() if img.format else "jpg"
            filename = f"story_{story_id}_{index}.{ext}"
            local_path = os.path.join(IMAGES_DIR, filename)
            img.save(local_path)
            downloaded.append({
                "url": img_url,
                "local_path": local_path,
                "web_path": f"/static/images/{filename}",
                "width": width,
                "height": height,
                "aspect_ratio": round(ratio, 2)
            })
            if len(downloaded) >= 3:
                break
        except Exception as e:
            print(f"  Error downloading image {img_url}: {e}")
    return downloaded


def score_story(title, summary, full_text=""):
    """Score a story 1-100 for AI/tech relevance using LLM or keyword fallback."""
    # Keyword fallback (used when no API key or LLM fails)
    high_kw = ["llm","gpt","claude","gemini","openai","anthropic","mistral","llama","deepseek",
                "nvidia","gpu","model","agent","transformer","diffusion","rag","fine-tun","benchmark"]
    med_kw  = ["ai","ml","machine learning","neural","dataset","inference","compute","robot",
                "autonomous","synthetic","alignment","safety","multimodal","embedding"]
    text_lower = f"{title} {summary}".lower()
    score = 30
    for kw in high_kw:
        if kw in text_lower: score += 8
    for kw in med_kw:
        if kw in text_lower: score += 4
    score = min(score, 95)

    if not API_KEY or API_KEY.startswith("your_"):
        return score, "Keyword-based scoring (no API key)"

    try:
        prompt = (
            f"Score this tech/AI news story from 1-100 based on: newsworthiness, "
            f"AI/tech relevance, audience interest for a tech-savvy audience.\n\n"
            f"Title: {title}\nSummary: {summary[:400]}\n\n"
            f"Respond with JSON only: {{\"score\": <int>, \"explanation\": \"<one sentence>\"}}"
        )
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 80},
            timeout=15
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # Extract JSON even if wrapped in markdown
            m = re.search(r'\{.*\}', content, re.DOTALL)
            if m:
                data = json.loads(m.group())
                return int(data.get("score", score)), data.get("explanation", "")
    except Exception as e:
        print(f"  LLM scoring failed: {e}")
    return score, "Keyword-based scoring (LLM error)"


def clean_summary(title, raw_summary, full_text=""):
    """Generate a clean 2-3 sentence summary using LLM or template fallback."""
    if not API_KEY or API_KEY.startswith("your_"):
        return f"{title}. {raw_summary[:200]}" if raw_summary else title

    try:
        context = full_text[:1000] if full_text else raw_summary[:500]
        prompt = (
            f"Write a clean, factual 2-3 sentence summary of this tech/AI news story. "
            f"No hype, no filler. Just the key facts.\n\n"
            f"Title: {title}\nContent: {context}\n\nSummary:"
        )
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 150},
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  LLM clean_summary failed: {e}")
    return f"{title}. {raw_summary[:300]}" if raw_summary else title


def categorize_story(title, summary):
    """Return category string using LLM or keyword fallback."""
    text_lower = f"{title} {summary}".lower()
    cat_map = {
        "Model Release":              ["release","launch","gpt","claude","gemini","llama","mistral"],
        "Open Source Repository":     ["open source","github","open-source","repo","weights"],
        "Research Paper":             ["paper","arxiv","research","study","findings","benchmark"],
        "Hardware & GPU Infrastructure": ["gpu","chip","nvidia","amd","hardware","inference server","tpu"],
        "Developer Tooling & SDKs":   ["sdk","api","library","framework","tool","plugin","integration"],
        "AI SaaS & Consumer Product": ["product","app","startup","platform","service","consumer","saas"],
        "Industry & Startups":        ["funding","investment","acquisition","startup","billion","valuation"],
        "Robotics & Embodied AI":     ["robot","embodied","physical","actuator","drone","autonomous vehicle"],
        "Safety & Alignment":         ["safety","alignment","risk","regulation","policy","bias","responsible"]
    }
    for cat, keywords in cat_map.items():
        if any(kw in text_lower for kw in keywords):
            return cat
    return "Industry & Startups"


def run_cleaner():
    """Process all scraped stories: score, clean summary, categorize, download images."""
    print("\n=== CLEANER STARTING ===")
    stories = db.get_stories_by_status("scraped")
    print(f"Processing {len(stories)} scraped stories...")

    for story in stories:
        sid     = story["id"]
        title   = story["title"]
        url     = story.get("url", "")
        summary = story.get("summary", "")
        print(f"\n  Processing story #{sid}: {title[:60]}...")

        # Extract article details
        details = extract_article_details(url) if url else {"full_text": "", "image_urls": []}
        full_text  = details["full_text"]
        image_urls = details["image_urls"]

        # Score the story
        value_score, value_explanation = score_story(title, summary, full_text)
        print(f"    Score: {value_score} — {value_explanation[:60]}")

        # Generate clean summary
        clean = clean_summary(title, summary, full_text)

        # Categorize
        category = categorize_story(title, summary)

        # Download images
        images_data = []
        if image_urls:
            images_data = download_images(image_urls, sid)
            print(f"    Downloaded {len(images_data)} images")

        # Update DB
        conn = db.get_db_connection()
        conn.execute(
            """UPDATE stories SET
               value_score=?, value_explanation=?, clean_summary=?, category=?,
               full_text=?, images_json=?, status='scraped'
               WHERE id=?""",
            (value_score, value_explanation, clean, category,
             full_text[:3000], json.dumps(images_data), sid)
        )
        conn.commit()
        conn.close()

    print(f"\n=== CLEANER DONE ===\n")


if __name__ == "__main__":
    db.init_db()
    run_cleaner()
