import os
import requests
import json
import sys
import random
import re
import io
from PIL import Image
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Ensure backend/src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

# Load environment variables
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, ".env"))

API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("LLM_MODEL", "meta-llama/llama-3-70b-instruct:free")


IMAGES_DIR = os.path.join(backend_dir, 'static', 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

CATEGORIES = [
    "Model Release",
    "Open Source Repository",
    "Research Paper",
    "Hardware & GPU Infrastructure",
    "Developer Tooling & SDKs",
    "AI SaaS & Consumer Product",
    "Industry & Startups",
    "Robotics & Embodied AI",
    "Safety & Alignment"
]

# Patterns to skip for ad/tracker images
_SKIP_PATTERNS = re.compile(r'pixel|tracking|spacer|logo|icon|avatar|1x1', re.IGNORECASE)


def extract_article_details(url):
    """GET the article URL, parse with BeautifulSoup, extract full_text and image_urls."""
    result = {'full_text': '', 'image_urls': []}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extract full_text from <p> tags
        paragraphs = soup.find_all('p')
        full_text = ' '.join(p.get_text(strip=True) for p in paragraphs)
        result['full_text'] = full_text[:5000]

        # Extract images
        image_urls = []

        # Try og:image first
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_urls.append(urljoin(url, og_image['content']))

        # Then all <img> tags
        for img in soup.find_all('img', src=True):
            src = img['src']

            # Skip data: URIs
            if src.startswith('data:'):
                continue

            # Skip common ad/tracker patterns
            if _SKIP_PATTERNS.search(src):
                continue

            # Check dimensions if available
            width = img.get('width')
            height = img.get('height')
            try:
                if width and int(width) < 250:
                    continue
                if height and int(height) < 250:
                    continue
            except (ValueError, TypeError):
                pass

            abs_url = urljoin(url, src)
            if abs_url not in image_urls:
                image_urls.append(abs_url)

        result['image_urls'] = image_urls[:5]
    except Exception as e:
        print(f"  Error extracting article details from {url}: {e}")

    return result


def download_images(image_urls, story_id):
    """Download images to IMAGES_DIR. Returns list of dicts with url, local_path, width, height, and aspect_ratio."""
    downloaded = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for index, img_url in enumerate(image_urls):
        try:
            resp = requests.get(img_url, headers=headers, timeout=10)
            resp.raise_for_status()
            
            # Verify and parse size using PIL
            img = Image.open(io.BytesIO(resp.content))
            width, height = img.size
            
            # Filter by size >= 250px
            if width < 250 or height < 250:
                print(f"  Skipping image {img_url}: size too small ({width}x{height})")
                continue
                
            # Filter out extreme aspect ratios (keep 0.5 to 2.5)
            aspect_ratio = width / height
            if aspect_ratio < 0.5 or aspect_ratio > 2.5:
                print(f"  Skipping image {img_url}: extreme aspect ratio ({aspect_ratio:.2f})")
                continue
                
            filename = f"story_{story_id}_{index}.jpg"
            filepath = os.path.join(IMAGES_DIR, filename)
            
            # Write to disk
            with open(filepath, 'wb') as f:
                f.write(resp.content)
                
            downloaded.append({
                'url': img_url,
                'local_path': f'/images/{filename}',
                'width': width,
                'height': height,
                'aspect_ratio': round(aspect_ratio, 2)
            })
        except Exception as e:
            print(f"  Error downloading image {img_url}: {e}")
    return downloaded



def clean_story(title, raw_summary):
    if not API_KEY or API_KEY == "your_openrouter_api_key_here":
        # Fallback heuristic classifier for development/offline testing
        is_pos = True
        
        # Simple heuristic mapping for categories
        lower_title = title.lower()
        if "repo" in lower_title or "github" in lower_title:
            cat = "Open Source Repository"
        elif "paper" in lower_title or "research" in lower_title or "arxiv" in lower_title:
            cat = "Research Paper"
        elif "gpu" in lower_title or "nvidia" in lower_title or "hardware" in lower_title or "vram" in lower_title:
            cat = "Hardware & GPU Infrastructure"
        elif "model" in lower_title or "claude" in lower_title or "llama" in lower_title or "gpt" in lower_title:
            cat = "Model Release"
        else:
            cat = random.choice(CATEGORIES)
            
        summary_clean = f"An interesting development in the AI space: {title}. This covers recent advancements that could have significant impacts for builders."
        return {
            "is_positive": is_pos,
            "category": cat,
            "clean_summary": summary_clean,
            "value_score": 5,
            "value_explanation": "A noteworthy development in the AI ecosystem relevant to developers and builders.",
            "niche_tags": ["AI"]
        }

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"""You are a technical editor for an AI news podcast targeting developers and tech enthusiasts.
Your job is to analyze scraped articles and determine if they represent valuable tech news or interesting developments in the AI space.
The content MUST be cutting-edge and provide true value to our readers (e.g., educational, tool-driven, or research-deep-dives).

Analyze the story and output a JSON object with:
1. "is_positive": (boolean) True if the story represents a highly valuable, cutting-edge AI release, research, repo, hardware news, startup news, or dev tool. False if it is outdated, generic news, spam/ad, or lacks actual technical substance and value-add.
2. "category": (string) Must be EXACTLY one of these categories: {", ".join(f'"{c}"' for c in CATEGORIES)}.
3. "clean_summary": (string) A 3-4 sentence clean, concise, technical summary written for a host to read aloud on a podcast. Focus heavily on the specifications, capabilities, and the tangible value-add for developers or builders. Explain *why* this matters. Keep it highly informative.
4. "value_score": (integer 1-10) How educational, teachable, or useful is this story for developers? 1 = low value, 10 = must-read.
5. "value_explanation": (string) A single sentence explaining why a developer should care about this story.
6. "niche_tags": (array of strings) 1-3 specific niche keyword tags like "AI Agents", "Quantization", "Text-to-Video", "RAG", "Fine-tuning", etc.

Respond ONLY with valid JSON. Do not include markdown formatting or backticks around the JSON."""

    user_content = f"Title: {title}\nRaw Details: {raw_summary}"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            parsed = json.loads(content)
            # Ensure category is in valid set, else default
            if parsed.get("category") not in CATEGORIES:
                parsed["category"] = "Model Release"
            # Ensure value_score is an int in range
            try:
                parsed["value_score"] = max(1, min(10, int(parsed.get("value_score", 5))))
            except (ValueError, TypeError):
                parsed["value_score"] = 5
            # Ensure niche_tags is a list
            if not isinstance(parsed.get("niche_tags"), list):
                parsed["niche_tags"] = ["AI"]
            return parsed
        else:
            print(f"LLM API Error: Status {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return None

def generate_approved_summary_llm(stories):
    if not stories:
        return "No approved stories available."

    if not API_KEY or API_KEY == "your_openrouter_api_key_here":
        # Fallback simple textual analysis
        categories = set(s.get("category", "Uncategorized") for s in stories)
        count = len(stories)
        if count == 1:
            return f"Today's episode features 1 story in {list(categories)[0]}. The show will focus on this single core update."
        else:
            cats_str = ", ".join(list(categories))
            return f"Today's episode features {count} stories covering {cats_str}. The discussion will weave these topics together, highlighting the latest releases and research developments."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    story_list_str = ""
    for idx, s in enumerate(stories):
        story_list_str += f"{idx+1}. [{s.get('category', 'General')}] {s.get('title')}\nSummary: {s.get('clean_summary')}\n\n"

    system_prompt = """You are a technical producer for a daily AI news podcast called AIPulse.
Analyze the list of approved stories for today's episode and write a cohesive, professional 2-3 sentence overview explaining the central theme, common threads, or the overall direction/focus of the podcast episode based on these topics. Make it sound like a compelling teaser or episode description. Do not list them mechanically."""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Approved Stories:\n{story_list_str}"}
        ],
        "temperature": 0.5
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            print(f"LLM Summary API Error: Status {response.status_code}")
    except Exception as e:
        print(f"Error generating approved summary: {e}")
    
    # Fallback if API fails
    categories = set(s.get("category", "Uncategorized") for s in stories)
    cats_str = ", ".join(list(categories))
    return f"Today's episode features {len(stories)} stories covering {cats_str}."


def run_cleaner():
    print("Running AI Technical Cleaner on scraped tech stories...")
    scraped_stories = db.get_stories_by_status("scraped")
    print(f"Found {len(scraped_stories)} new tech stories to clean.")
    
    cleaned_count = 0
    rejected_count = 0
    
    for story in scraped_stories[:30]:  # Process top 30
        print(f"Processing: {story['title'][:50]}...")
        cleaned = clean_story(story['title'], story['summary'])
        if cleaned:
            # Extract article details (full_text and images)
            article_details = extract_article_details(story['url'])
            full_text = article_details.get('full_text', '')
            image_urls = article_details.get('image_urls', [])

            # Download images locally
            downloaded_images = download_images(image_urls, story['id'])
            images_json_str = json.dumps(downloaded_images) if downloaded_images else None

            # Prepare niche_tags as JSON string for storage
            niche_tags = cleaned.get('niche_tags', [])
            niche_tags_str = json.dumps(niche_tags) if niche_tags else None

            # Save enrichment details to DB
            db.update_story_details(
                story_id=story['id'],
                images_json=images_json_str,
                value_score=cleaned.get('value_score'),
                value_explanation=cleaned.get('value_explanation'),
                full_text=full_text if full_text else None,
                niche_tags=niche_tags_str
            )

            if cleaned.get("is_positive"):
                db.update_story_status(
                    story_id=story['id'],
                    status="approved",
                    clean_summary=cleaned.get("clean_summary"),
                    category=cleaned.get("category")
                )
                print(f"-> APPROVED as [{cleaned.get('category')}]: {cleaned.get('clean_summary')[:80]}...")
                cleaned_count += 1
            else:
                db.update_story_status(story['id'], "rejected")
                print("-> REJECTED (Not tech/spam)")
                rejected_count += 1
        else:
            print("-> Skipped due to API error")
            
    print(f"Cleaner summary: {cleaned_count} approved, {rejected_count} rejected.")

if __name__ == "__main__":
    run_cleaner()
