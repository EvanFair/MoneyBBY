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

# Patterns to skip generic placeholder social thumbnails, gradient banners, or generic page screenshots
_SKIP_IMAGE_URL_PATTERNS = re.compile(
    r'social-thumbnails|gradient\.png|placeholder|logo-square|favicon|default_bg|header-bg|menu|banner',
    re.IGNORECASE
)


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

        # Try og:image first (if not a generic placeholder/social thumbnail)
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            og_url = urljoin(url, og_image['content'])
            if not _SKIP_IMAGE_URL_PATTERNS.search(og_url):
                image_urls.append(og_url)

        # Then all <img> tags
        for img in soup.find_all('img', src=True):
            src = img['src']

            # Skip data: URIs
            if src.startswith('data:'):
                continue

            # Skip common ad/tracker patterns
            if _SKIP_PATTERNS.search(src):
                continue

            # Filter out generic layouts/bannering
            abs_url = urljoin(url, src)
            if _SKIP_IMAGE_URL_PATTERNS.search(abs_url):
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
        # Smart local heuristic classifier for offline testing/development
        is_pos = True
        
        lower_title = title.lower()
        lower_summary = raw_summary.lower() if raw_summary else ""
        combined_text = lower_title + " " + lower_summary
        
        # 1. Determine Category
        if "repo" in lower_title or "github" in lower_title:
            cat = "Open Source Repository"
        elif "paper" in lower_title or "research" in lower_title or "arxiv" in lower_title:
            cat = "Research Paper"
        elif "gpu" in lower_title or "nvidia" in lower_title or "hardware" in lower_title or "vram" in lower_title or "tpu" in lower_title:
            cat = "Hardware & GPU Infrastructure"
        elif "model" in lower_title or "claude" in lower_title or "llama" in lower_title or "gpt" in lower_title or "deepseek" in lower_title or "gemini" in lower_title or "weights" in lower_title:
            cat = "Model Release"
        elif "tool" in lower_title or "sdk" in lower_title or "api" in lower_title or "framework" in lower_title or "agentic" in lower_title or "compiler" in lower_title:
            cat = "Developer Tooling & SDKs"
        elif "saas" in lower_title or "product" in lower_title or "app" in lower_title or "startup" in lower_title or "business" in lower_title:
            cat = "AI SaaS & Consumer Product"
        elif "robot" in lower_title or "embodied" in lower_title or "humanoid" in lower_title or "manipulation" in lower_title:
            cat = "Robotics & Embodied AI"
        elif "safety" in lower_title or "alignment" in lower_title or "policy" in lower_title or "ethics" in lower_title or "risk" in lower_title:
            cat = "Safety & Alignment"
        else:
            cat = "Model Release"
            
        # 2. Dynamic Score Calculation based on keywords
        score = 5  # Base score
        
        # High value technical/actionable terms
        high_value_keywords = [
            "release", "open-source", "framework", "agent", "benchmark", "quantization", 
            "fine-tuning", "vram", "performance", "local", "productivity", "tip", "tutorial",
            "guide", "speedup", "efficiency", "frugal", "low-cost", "fast", "runs on",
            "weights", "free", "diy", "self-host", "tool"
        ]
        # Low value generic/corporate/hype terms
        low_value_keywords = [
            "partners", "announces", "market", "policy", "funding", "invests", 
            "legal", "court", "lawsuit", "ethics", "gulag", "soul-crushing", "regulates",
            "stock", "ceo", "board", "merger", "acquisition"
        ]
        
        for kw in high_value_keywords:
            if kw in combined_text:
                score += 1
        for kw in low_value_keywords:
            if kw in combined_text:
                score -= 1
                
        # Limit score between 3 and 9 (leaves 10 for absolute human-curated excellence)
        score = max(3, min(9, score))
        
        # 3. Dynamic Niche Tags Extraction
        tags = []
        tag_mappings = {
            "agent": "AI Agents",
            "quantiz": "Quantization",
            "gguf": "Quantization",
            "gpu": "Hardware",
            "vram": "Hardware",
            "local": "Local Tech",
            "fine-tune": "Fine-Tuning",
            "lora": "Fine-Tuning",
            "rag": "RAG",
            "vector": "RAG",
            "search": "Search/Retrieval",
            "robot": "Robotics",
            "embodied": "Robotics",
            "paper": "Research",
            "research": "Research",
            "repo": "Open Source",
            "github": "Open Source",
            "productivity": "Productivity",
            "speed": "Performance",
            "efficiency": "Optimization"
        }
        for kw, tag_val in tag_mappings.items():
            if kw in combined_text:
                if tag_val not in tags:
                    tags.append(tag_val)
                    
        if not tags:
            tags = ["Cutting-Edge Tech"]
        else:
            tags = tags[:3]
            
        # 4. Clean summary builder
        clean_text = raw_summary or ""
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # Split sentences
        sentences = re.split(r'(?<=[.!?]) +', clean_text)
        sentences = [s for s in sentences if s and not s.startswith("Sign up") and not s.startswith("log into") and "cookie" not in s.lower() and "subscribe" not in s.lower()]
        
        if len(sentences) >= 2:
            summary_clean = " ".join(sentences[:3])
        else:
            summary_clean = f"A notable update on {title}. This covers recent advancements that could have significant impacts for builders."
            
        if len(summary_clean) > 350:
            summary_clean = summary_clean[:350] + "..."
            
        # 5. Value explanation
        explanation = "A noteworthy development in the tech and AI ecosystem relevant to optimizing workflows."
        if "Open Source" in tags:
            explanation = "An open-source repository that developers can use or self-host to save time."
        elif "Robotics" in tags:
            explanation = "New developments in embodied AI and robotic control algorithms."
        elif "Hardware" in tags:
            explanation = "Hardware specifications and memory footprint optimizations for running models."
        elif "AI Agents" in tags:
            explanation = "An agentic framework that can automate complex browser or API tasks."
        elif "Productivity" in tags:
            explanation = "Practical tip to simplify daily workflows and save hours of manual work."
            
        return {
            "is_positive": is_pos,
            "category": cat,
            "clean_summary": summary_clean,
            "value_score": score,
            "value_explanation": explanation,
            "niche_tags": tags
        }

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"""You are a technical producer and content editor for AIPulse, a daily AI news service.
Your job is to analyze scraped articles and determine if they represent valuable, cutting-edge AI news, practical tools, tutorials, or updates.
We are targeting developers, creators, and general tech-adjacent audiences (remembering that 96% of people on Earth haven't touched AI yet). Focus on practical utility: tools that simplify daily tasks, optimize workflows, or make life better/faster.

Analyze the story and output a JSON object with:
1. "is_positive": (boolean) True if the story represents a highly valuable, practical AI tool, library, open-source repo, model release, or actionable technique that teaches how to incorporate AI into daily life/work. False if it is generic news, hype/politics, outdated, spam, or lacks technical substance or practical value-add.
2. "category": (string) Must be EXACTLY one of these categories: {", ".join(f'"{c}"' for c in CATEGORIES)}.
3. "clean_summary": (string) A 3-4 sentence clean, concise summary written for a host to read aloud on a podcast. Focus heavily on practical specs, capabilities, and the tangible value-add (how it makes daily life/work faster, cheaper, or better). Explain exactly *why* this matters to someone looking to adopt AI.
4. "value_score": (integer 1-10) How practical, educational, or useful is this story? Give high scores (8-10) for highly actionable tools, repositories, or tips that simplify workflows. Give low scores for high-level theory or generic corporate announcements.
5. "value_explanation": (string) A single sentence explaining the practical benefit of this story (e.g., "Saves developers 2 hours of boilerplate coding by automating X" or "Allows creators to generate high-res videos locally without a GPU").
6. "niche_tags": (array of strings) 1-3 specific niche keyword tags like "AI Agents", "Quantization", "Text-to-Video", "Workflow Hack", "Local LLM", "Productivity", etc.

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
                    status="scraped",
                    clean_summary=cleaned.get("clean_summary"),
                    category=cleaned.get("category")
                )
                print(f"-> KEPT PENDING (scraped) as [{cleaned.get('category')}]: {cleaned.get('clean_summary')[:80]}...")
                cleaned_count += 1
            else:
                db.update_story_status(story['id'], "rejected")
                print("-> REJECTED (Not AI/spam)")
                rejected_count += 1
        else:
            print("-> Skipped due to API error")
            
    print(f"Cleaner summary: {cleaned_count} approved, {rejected_count} rejected.")

if __name__ == "__main__":
    run_cleaner()
